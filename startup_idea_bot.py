import logging
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

USERS_FILE = "users.json"
conversation_history = {}

LANG, MENU, IDEA_FLOW = range(3)

# ===================== USERS =====================
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

# ===================== AI =====================
def clean_text(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'#{1,6}\s?', '', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    return text.strip()

def get_system_prompt(lang: str) -> str:
    if lang == "en":
        return (
            "You are an experienced startup mentor and business expert. "
            "Always respond in English only. "
            "IMPORTANT: Never use ** __ * _ # backtick markdown symbols. Use only plain text and emojis. "
            "Be concise, practical and encouraging."
        )
    else:
        return (
            "Sen tajribali startup mentor va biznes ekspertisan. "
            "Har doim faqat O'zbek tilida javob ber. "
            "MUHIM: Hech qachon ** __ * _ # ` belgilarini ishlatma. Faqat oddiy matn va emoji ishlat. "
            "Qisqa, amaliy va rag'batlantiruvchi bo'l."
        )

def ask_ai(user_id: int, user_message: str, lang: str = "uz") -> str:
    client = Groq(api_key=GROQ_API_KEY)
    system = get_system_prompt(lang)

    if user_id not in conversation_history:
        conversation_history[user_id] = [{"role": "system", "content": system}]
    else:
        conversation_history[user_id][0] = {"role": "system", "content": system}

    conversation_history[user_id].append({"role": "user", "content": user_message})

    if len(conversation_history[user_id]) > 21:
        sys_msg = conversation_history[user_id][0]
        conversation_history[user_id] = [sys_msg] + conversation_history[user_id][-20:]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_history[user_id],
        max_tokens=2048,
        temperature=0.7
    )

    reply = clean_text(response.choices[0].message.content)
    conversation_history[user_id].append({"role": "assistant", "content": reply})
    return reply

def ask_ai_once(prompt: str, lang: str = "uz") -> str:
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": get_system_prompt(lang)},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2048,
        temperature=0.7
    )
    return clean_text(response.choices[0].message.content)

# ===================== TEXTS =====================
TEXTS = {
    "uz": {
        "welcome": "Tilni tanlang / Choose language:",
        "start": "👋 Salom! Men Startup Mind botman 🧠🚀\n\nMen sizni startup dunyosiga bosqichma-bosqich yo'naltiraman!\n\nQuyidagi tugmalardan birini tanlang:",
        "menu": ["💡 Startup g'oya", "📊 Ideani tahlil qil", "🗺 Yo'l xaritasi", "💬 Erkin suhbat"],
        "idea_q1": "💡 Zo'r! Qaysi soha sizni qiziqtiradi?\n\nMasalan: fintech, health, education, ecommerce, logistics...",
        "idea_q2": "💰 Ajoyib! Sizda qancha boshlang'ich kapital bor?\n\n1️⃣ 0 - 1,000$\n2️⃣ 1,000 - 10,000$\n3️⃣ 10,000$+",
        "idea_q3": "🎯 Yaxshi! Siz qaysi muammoni hal qilmoqchisiz?\n\nQisqacha yozing:",
        "generating": "🤖 Tayyorlanmoqda... ⏳",
        "error": "⚠️ Xatolik yuz berdi. Qayta urinib ko'ring.",
        "reset_done": "🔄 Suhbat tozalandi!",
        "next_action": "Keyingi amalni tanlang:",
        "help": "📖 Buyruqlar:\n\n/start - Botni boshlash\n/reset - Suhbatni tozalash\n/help - Yordam\n\nTugmalar:\n💡 Startup g'oya - 3 savol orqali idea\n📊 Tahlil - Ideangizni baholash\n🗺 Yo'l xaritasi - 6 oylik plan\n💬 Erkin suhbat - Istalgan savol",
    },
    "en": {
        "welcome": "Tilni tanlang / Choose language:",
        "start": "👋 Hello! I'm Startup Mind Bot 🧠🚀\n\nI'll guide you through the startup world step by step!\n\nChoose from the menu below:",
        "menu": ["💡 Startup Idea", "📊 Analyze Idea", "🗺 Roadmap", "💬 Free Chat"],
        "idea_q1": "💡 Great! Which industry interests you?\n\nExamples: fintech, health, education, ecommerce, logistics...",
        "idea_q2": "💰 Amazing! What's your initial capital?\n\n1️⃣ 0 - $1,000\n2️⃣ $1,000 - $10,000\n3️⃣ $10,000+",
        "idea_q3": "🎯 Good! What problem do you want to solve?\n\nWrite briefly:",
        "generating": "🤖 Generating... ⏳",
        "error": "⚠️ An error occurred. Please try again.",
        "reset_done": "🔄 Conversation cleared!",
        "next_action": "Choose next action:",
        "help": "📖 Commands:\n\n/start - Start bot\n/reset - Clear chat\n/help - Help\n\nButtons:\n💡 Startup Idea - 3-question idea flow\n📊 Analyze - Rate your idea\n🗺 Roadmap - 6-month plan\n💬 Free Chat - Ask anything",
    }
}

def get_menu_keyboard(lang: str):
    menu = TEXTS[lang]["menu"]
    return ReplyKeyboardMarkup([[menu[0], menu[1]], [menu[2], menu[3]]], resize_keyboard=True)

# ===================== HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.message.from_user.id)
    keyboard = [["🇺🇿 O'zbek", "🇬🇧 English"]]
    await update.message.reply_text(
        TEXTS["uz"]["welcome"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return LANG

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    lang = "en" if "English" in text else "uz"
    context.user_data["lang"] = lang

    if user_id in conversation_history:
        del conversation_history[user_id]

    await update.message.reply_text(
        TEXTS[lang]["start"],
        reply_markup=get_menu_keyboard(lang)
    )
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = context.user_data.get("lang", "uz")
    menu = TEXTS[lang]["menu"]

    if text not in menu:
        context.user_data["mode"] = "chat"
        result = ask_ai(update.message.from_user.id, text, lang)
        await update.message.reply_text(result)
        return MENU

    if text == menu[0]:
        context.user_data["idea_step"] = 1
        context.user_data["idea_data"] = {}
        context.user_data["mode"] = "idea"
        await update.message.reply_text(TEXTS[lang]["idea_q1"], reply_markup=ReplyKeyboardRemove())
        return IDEA_FLOW

    elif text == menu[1]:
        context.user_data["mode"] = "analyze"
        msg = "Write your startup idea to analyze:" if lang == "en" else "Tahlil qilish uchun startup ideangizni yozing:"
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
        return IDEA_FLOW

    elif text == menu[2]:
        context.user_data["mode"] = "roadmap"
        msg = "Write your startup idea for roadmap:" if lang == "en" else "Yo'l xaritasi uchun startup ideangizni yozing:"
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
        return IDEA_FLOW

    else:
        context.user_data["mode"] = "chat"
        msg = "Ask me anything about startups! 💬" if lang == "en" else "Startup haqida xohlagan savolingizni bering! 💬"
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
        return IDEA_FLOW

async def idea_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    lang = context.user_data.get("lang", "uz")
    mode = context.user_data.get("mode", "chat")
    step = context.user_data.get("idea_step", 0)

    await update.message.reply_text(TEXTS[lang]["generating"])

    try:
        if mode == "analyze":
            if lang == "en":
                prompt = f"Analyze this startup idea professionally:\nIdea: {text}\n\n1. SCORE (out of 10)\n2. MARKET ANALYSIS\n3. TARGET AUDIENCE\n4. COMPETITORS\n5. MONETIZATION\n6. RISKS\n7. RECOMMENDATION"
                header = f"📊 ANALYSIS: {text[:50]}\n\n"
            else:
                prompt = f"Quyidagi startup ideani professional tahlil qil:\nIdea: {text}\n\n1. BAHO (10 dan)\n2. BOZOR TAHLILI\n3. TARGET AUDITORIYA\n4. RAQOBATCHILAR\n5. MONETIZATSIYA\n6. XATARLAR\n7. TAVSIYA"
                header = f"📊 TAHLIL: {text[:50]}\n\n"
            result = ask_ai_once(prompt, lang)
            await update.message.reply_text(header + result)
            return await back_to_menu(update, context)

        elif mode == "roadmap":
            if lang == "en":
                prompt = f"Create a 6-month roadmap for this startup:\n{text}\n\nFor each month: 3 main tasks, KPI metric, estimated budget.\nMonths: PREPARATION, MVP BUILD, TESTING, LAUNCH, GROWTH, SCALE"
                header = f"🗺 6-MONTH ROADMAP: {text[:50]}\n\n"
            else:
                prompt = f"Quyidagi startup uchun 6 oylik yo'l xaritasi tuz:\n{text}\n\nHar oy uchun: 3 ta asosiy vazifa, KPI ko'rsatkichi, taxminiy byudjet.\nOylar: TAYYORGARLIK, MVP QURISH, SINOV, LAUNCH, O'SISH, SCALE"
                header = f"🗺 6 OYLIK YO'L XARITASI: {text[:50]}\n\n"
            result = ask_ai_once(prompt, lang)
            await update.message.reply_text(header + result)
            return await back_to_menu(update, context)

        elif mode == "idea":
            if step == 1:
                context.user_data["idea_data"]["industry"] = text
                context.user_data["idea_step"] = 2
                await update.message.reply_text(TEXTS[lang]["idea_q2"])
                return IDEA_FLOW
            elif step == 2:
                context.user_data["idea_data"]["capital"] = text
                context.user_data["idea_step"] = 3
                await update.message.reply_text(TEXTS[lang]["idea_q3"])
                return IDEA_FLOW
            elif step == 3:
                data = context.user_data["idea_data"]
                data["problem"] = text
                if lang == "en":
                    prompt = f"Generate 3 unique startup ideas based on:\nIndustry: {data['industry']}\nCapital: {data['capital']}\nProblem to solve: {data['problem']}\n\nFor each idea:\nName + one-line description\n💡 What it does\n👥 Target audience\n💰 How it makes money\n📈 Growth potential: High/Medium/Low"
                    header = "🚀 YOUR 3 STARTUP IDEAS:\n\n"
                    footer = "\n\n💬 Which one do you like? I can help you develop it further!"
                else:
                    prompt = f"Quyidagi ma'lumotlarga asoslanib 3 ta noyob startup idea ber:\nSoha: {data['industry']}\nKapital: {data['capital']}\nHal qilmoqchi muammo: {data['problem']}\n\nHar bir idea uchun:\nNomi + bir qatorli tavsif\n💡 Nima qiladi\n👥 Target auditoriya\n💰 Qanday pul ishlaydi\n📈 O'sish potentsiali: Yuqori/O'rta/Past"
                    header = "🚀 SIZNING 3 TA STARTUP GOYANGIZ:\n\n"
                    footer = "\n\n💬 Qaysi biri yoqdi? Rivojlantirishga yordam beraman!"
                result = ask_ai_once(prompt, lang)
                await update.message.reply_text(header + result + footer)
                context.user_data["idea_step"] = 0
                context.user_data["mode"] = "chat"
                return await back_to_menu(update, context)

        else:
            result = ask_ai(user_id, text, lang)
            await update.message.reply_text(result)
            return IDEA_FLOW

    except Exception as e:
        logging.error(f"Xato: {e}")
        await update.message.reply_text(TEXTS[lang]["error"])
        return IDEA_FLOW

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "uz")
    await update.message.reply_text(TEXTS[lang]["next_action"], reply_markup=get_menu_keyboard(lang))
    return MENU

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in conversation_history:
        del conversation_history[user_id]
    lang = context.user_data.get("lang", "uz")
    context.user_data.clear()
    await update.message.reply_text(TEXTS[lang]["reset_done"])
    return await start(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "uz")
    await update.message.reply_text(TEXTS[lang]["help"])

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Sizda bu huquq yo'q.")
        return
    if not context.args:
        await update.message.reply_text("Misol: /broadcast Xabar matni")
        return
    message_text = " ".join(context.args)
    users = get_all_users()
    sent, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 Startup Mind Bot:\n\n{message_text}")
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Yuborildi: {sent} ta\n❌ Yuborilmadi: {failed} ta\n👥 Jami: {len(users)} ta")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Sizda bu huquq yo'q.")
        return
    users = get_all_users()
    await update.message.reply_text(
        f"📊 Bot statistikasi:\n\n"
        f"👥 Jami foydalanuvchilar: {len(users)} ta\n"
        f"💬 Hozir faol: {len(conversation_history)} ta"
    )

# ===================== MAIN =====================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_language)],
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
            IDEA_FLOW: [MessageHandler(filters.TEXT & ~filters.COMMAND, idea_flow)],
        },
        fallbacks=[
            CommandHandler("reset", reset),
            CommandHandler("start", start),
            CommandHandler("help", help_command),
        ],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))

    print("✅ Startup Mind Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()