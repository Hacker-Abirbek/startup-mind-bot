import logging
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os
import re
import json

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # .env ga o'z ID ingizni qo'shing

USERS_FILE = "users.json"
conversation_history = {}


# ===================== FOYDALANUVCHILAR BAZASI =====================
def load_users() -> set:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_user(user_id: int):
    users = load_users()
    users.add(user_id)
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)


def get_all_users() -> list:
    return list(load_users())


# ===================== AI FUNKSIYALAR =====================
def clean_text(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'#{1,6}\s?', '', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    return text.strip()


def ask_ai(user_id: int, user_message: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)

    if user_id not in conversation_history:
        conversation_history[user_id] = [
            {
                "role": "system",
                "content": """Sen tajribali startup mentor va biznes ekspertisan.
Foydalanuvchi bilan O'zbek tilida suhbatlashasаn.
MUHIM: Hech qachon ** __ * _ # ` belgilarini ishlatma. Faqat oddiy matn va emoji ishlat.
Suhbat tarixini eslab qol va oldingi javoblarga asoslanib gapir."""
            }
        ]

    conversation_history[user_id].append({"role": "user", "content": user_message})

    if len(conversation_history[user_id]) > 21:
        system_msg = conversation_history[user_id][0]
        conversation_history[user_id] = [system_msg] + conversation_history[user_id][-20:]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_history[user_id],
        max_tokens=2048
    )

    reply = clean_text(response.choices[0].message.content)
    conversation_history[user_id].append({"role": "assistant", "content": reply})
    return reply


def ask_ai_once(prompt: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Sen startup ekspert va biznes analitiksan. O'zbek tilida javob ber. Hech qachon ** __ * _ # ` belgilarini ishlatma."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2048
    )
    return clean_text(response.choices[0].message.content)


# ===================== BOT HANDLERLAR =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)

    if user_id in conversation_history:
        del conversation_history[user_id]

    await update.message.reply_text(
        "👋 Salom! Men Startup Mind botman 🧠🚀\n\n"
        "Sizning shaxsiy startup mentoringizman!\n\n"
        "Nima qila olaman:\n"
        "💬 Har qanday savolingizga javob beraman\n"
        "💡 /idea - Startup goyalar\n"
        "📊 /analyze - Ideangizni tahlil qilaman\n"
        "🗺 /roadmap - 6 oylik yo'l xaritasi\n"
        "🔄 /reset - Suhbatni tozalash\n\n"
        "Boshlaylikmi? Ideangizni yozing! ✨"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in conversation_history:
        del conversation_history[user_id]
    await update.message.reply_text("🔄 Suhbat tozalandi! Yangi boshlaylikmi? 🚀")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Buyruqlar:\n\n"
        "/start - Botni boshlash\n"
        "/idea [soha] - Startup goyalar\n"
        "/analyze [idea] - Ideani tahlil qilish\n"
        "/roadmap [idea] - 6 oylik yo'l xaritasi\n"
        "/reset - Suhbatni tozalash\n"
        "/help - Yordam\n\n"
        "Yoki shunchaki xohlagan narsangizni yozing! 💬"
    )


async def idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)

    if not context.args:
        await update.message.reply_text("Soha nomini kiriting!\nMisol: /idea fintech")
        return

    soha = " ".join(context.args)
    await update.message.reply_text(f"🤖 {soha} sohasida idealar tayyorlanmoqda... ⏳")

    try:
        result = ask_ai(user_id, f"{soha} sohasida menga 3 ta startup idea ber.")
        await update.message.reply_text(f"🚀 {soha.upper()} sohasida idealar:\n\n{result}")
    except Exception as e:
        logging.error(f"Xato: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib koring.")


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)

    if not context.args:
        await update.message.reply_text("Ideangizni kiriting!\nMisol: /analyze onlayn dorixona")
        return

    idea_text = " ".join(context.args)
    await update.message.reply_text("📊 Tahlil qilinmoqda... ⏳")

    prompt = f"""Quyidagi startup ideani professional tahlil qil:
Idea: {idea_text}

1. IDEA BAHOSI (10 dan necha ball) - kuchli va zaif tomonlari
2. BOZOR TAHLILI - hajmi, o'sish sur'ati, O'zbekistondagi holat
3. TARGET AUDITORIYA - kim uchun, muammosi nima
4. RAQOBATCHILAR - kimlar bor, farqingiz nima
5. MONETIZATSIYA - qanday pul ishlash, taxminiy daromad
6. XATARLAR - muammolar va yechimlar
7. TAVSIYA - amalga oshirish kerakmi?"""

    try:
        result = ask_ai_once(prompt)
        await update.message.reply_text(f"📊 TAHLIL: {idea_text.upper()}\n\n{result}")
    except Exception as e:
        logging.error(f"Xato: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib koring.")


async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)

    if not context.args:
        await update.message.reply_text("Startup ideangizni kiriting!\nMisol: /roadmap onlayn ta'lim")
        return

    idea_text = " ".join(context.args)
    await update.message.reply_text("🗺 Yo'l xaritasi tayyorlanmoqda... ⏳")

    prompt = f"""Quyidagi startup uchun 6 oylik yo'l xaritasi tuz:
Startup: {idea_text}

Har oy uchun:
- Asosiy 3 ta vazifa
- Muvaffaqiyat ko'rsatkichi
- Taxminiy byudjet

OY 1 - TAYYORGARLIK
OY 2 - MVP YARATISH
OY 3 - SINOV VA FEEDBACK
OY 4 - RASMIY LAUNCH
OY 5 - O'SISH
OY 6 - SCALE VA INVESTITSIYA"""

    try:
        result = ask_ai_once(prompt)
        await update.message.reply_text(f"🗺 6 OYLIK YO'L XARITASI:\n{idea_text.upper()}\n\n{result}")
    except Exception as e:
        logging.error(f"Xato: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib koring.")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Faqat admin yuborishi mumkin
    if user_id != ADMIN_ID:
        await update.message.reply_text("Sizda bu buyruqdan foydalanish huquqi yoq.")
        return

    if not context.args:
        await update.message.reply_text(
            "Xabar matnini kiriting!\n"
            "Misol: /broadcast Yangi funksiya qo'shildi!"
        )
        return

    message_text = " ".join(context.args)
    users = get_all_users()
    sent = 0
    failed = 0

    await update.message.reply_text(f"📤 {len(users)} ta foydalanuvchiga yuborilmoqda...")

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 Startup Mind Bot:\n\n{message_text}"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Yuborildi: {sent} ta\n"
        f"❌ Yuborilmadi: {failed} ta\n"
        f"👥 Jami foydalanuvchilar: {len(users)} ta"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("Sizda bu buyruqdan foydalanish huquqi yoq.")
        return

    users = get_all_users()
    active = len(conversation_history)

    await update.message.reply_text(
        f"📊 BOT STATISTIKASI:\n\n"
        f"👥 Jami foydalanuvchilar: {len(users)} ta\n"
        f"💬 Hozir faol: {active} ta\n"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)
    user_text = update.message.text.strip()
    await update.message.reply_text("🤖 Javob tayyorlanmoqda... ⏳")

    try:
        result = ask_ai(user_id, user_text)
        await update.message.reply_text(result)
    except Exception as e:
        logging.error(f"Xato: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib koring.")


# ===================== MAIN =====================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("idea", idea))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("roadmap", roadmap))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Startup Mind Bot ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()