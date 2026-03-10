import logging
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
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

# ConversationHandler states
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

def ask_ai(user_id: int, user_message: str, lang: str = "uz") -> str:
    client = Groq(api_key=GROQ_API_KEY)

    if lang == "en":
        system = """You are an experienced startup mentor and business expert.
Chat with the user in English.
IMPORTANT: Never use ** __ * _ # ` symbols. Use only plain text and emoji.
Remember conversation history and guide the user step by step."""
    else:
        system = """Sen tajribali startup mentor va biznes ekspertisan.
Foydalanuvchi bilan O'zbek tilida suhbatlashasаn.
MUHIM: Hech qachon ** __ * _ # ` belgilarini ishlatma. Faqat oddiy matn va emoji ishlat.
Suhbat tarixini eslab qol va foydalanuvchini bosqichma-bosqich yo'naltir."""

    if user_id not in conversation_history:
        conversation_history[user_id] = [{"role": "system", "content": system}]

    conversation_history[user_id].append({"role": "user", "content": user_message})

    if len(conversation_history[user_id]) > 21:
        sys_msg = conversation_history[user_id][0]
        conversation_history[user_id] = [sys_msg] + conversation_history[user_id][-20:]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_history[user_id],
        max_tokens=2048
    )

    reply = clean_text(response.choices[0].message.content)
    conversation_history[user_id].append({"role": "assistant", "content": reply})
    return reply

def ask_ai_once(prompt: str, lang: str = "uz") -> str:
    client = Groq(api_key=GROQ_API_KEY)
    sys_content = "You are a startup expert. Answer in English. Never use ** __ * _ # ` symbols." if lang == "en" else "Sen startup ekspertsan. O'zbek tilida javob ber. Hech qachon ** __ * _ # ` belgilarini ishlatma."
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": sys_content},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2048
    )
    return clean_text(response.choices[0].message.content)


# ===================== TEXTS =====================
TEXTS = {
    "uz": {
        "welcome": "Tilni tanlang / Choose language:",
        "start": "👋 Salom! Men Startup Mind botman 🧠🚀\n\nMen sizni startup dunyosiga bosqichma-bosqich yo'naltiraman!\n\nQuyidagi tugmalardan birini tanlang:",
        "menu": ["💡 Startup g'oya", "📊 Ideani tahlil qil", "🗺 Yo'l xaritasi", "💬 Erkin suhbat"],
        "idea_q1": "Zo'r! Qaysi soha sizni qiziqtiradi?\n\nMasalan: fintech, health, education, ecommerce, logistics...",
        "idea_q2": "Ajoyib! Sizda qancha boshlang'ich kapital bor?\n\n1. 0 - 1000$\n2. 1000 - 10,000$\n3. 10,000$+",
        "idea_q3": "Yaxshi! Siz qaysi muammoni hal qilmoqchisiz? Qisqacha yozing:",
        "generating": "🤖 Tayyorlanmoqda... ⏳",
        "error": "Xatolik yuz berdi. Qayta urinib koring.",
        "reset_done": "🔄 Suhbat tozalandi!",
        "help": "📖 Buyruqlar:\n/start - Botni boshlash\n/reset - Suhbatni tozalash\n/help - Yordam",
    },
    "en": {
        "welcome": "Tilni tanlang / Choose language:",
        "start": "👋 Hello! I'm Startup Mind Bot 🧠🚀\n\nI'll guide you through the startup world step by step!\n\nChoose from the menu below:",
        "menu": ["💡 Startup Idea", "📊 Analyze Idea", "🗺 Roadmap", "💬 Free Chat"],
        "idea_q1": "Great! Which industry interests you?\n\nExamples: fintech, health, education, ecommerce, logistics...",
        "idea_q2": "Amazing! What's your initial capital?\n\n1. 0 - $1,000\n2. $1,000 - $10,000\n3. $10,000+",
        "idea_q3": "Good! What problem do you want to solve? Write briefly:",
        "generating": "🤖 Generating... ⏳",
        "error": "An error occurred. Please try again.",
        "reset_done": "🔄 Conversation cleared!",
        "help": "📖 Commands:\n/start - Start bot\n/reset - Clear chat\n/help - Help",
    }
}

def t(user_id: int, key: str, context) -> str:
    lang = context.user_data.get("lang", "uz")
    return TEXTS[lang][key]


# ===================== HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.message.from_user.id)
    keyboard = [["🇺🇿 O'zbek", "🇬🇧 English"]]
    await update.message.reply_text(
        "Tilni tanlang / Choose language:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return LANG

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if "English" in text:
        context.user_data["lang"] = "en"
    else:
        context.user_data["lang"] = "uz"

    lang = context.user_data["lang"]
    if user_id in conversation_history:
        del conversation_history[user_id]

    menu = TEXTS[lang]["menu"]
    keyboard = [[menu[0], menu[1]], [menu[2], menu[3]]]
    await update.message.reply_text(
        TEXTS[lang]["start"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    lang = context.user_data.get("lang", "uz")
    menu = TEXTS[lang]["menu"]

    if text == menu[0]:  # Startup idea
        context.user_data["idea_step"] = 1
        context.user_data["idea_data"] = {}
        await update.message.reply_text(TEXTS[lang]["idea_q1"], reply_markup=ReplyKeyboardRemove())
        return IDEA_FLOW

    elif text == menu[1]:  # Analyze
        if lang == "en":
            await update.message.reply_text("Write your startup idea to analyze:", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("Tahlil qilish uchun startup ideangizni yozing:", reply_markup=ReplyKeyboardRemove())
        context.user_data["mode"] = "analyze"
        return IDEA_FLOW

    elif text == menu[2]:  # Roadmap
        if lang == "en":
            await update.message.reply_text("Write your startup idea for roadmap:", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("Yo'l xaritasi uchun startup ideangizni yozing:", reply_markup=ReplyKeyboardRemove())
        context.user_data["mode"] = "roadmap"
        return IDEA_FLOW

    else:  # Free chat
        context.user_data["mode"] = "chat"
        if lang == "en":
            await update.message.reply_text("Ask me anything about startups! 💬", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("Startup haqida xohlagan savolingizni bering! 💬", reply_markup=ReplyKeyboardRemove())
        return IDEA_FLOW

async def idea_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    lang = context.user_data.get("lang", "uz")
    mode = context.user_data.get("mode", "")
    step = context.user_data.get("idea_step", 0)

    await update.message.reply_text(TEXTS[lang]["generating"])

    try:
        # Analyze mode
        if mode == "analyze":
            if lang == "en":
                prompt = f"Analyze this startup idea professionally:\nIdea: {text}\n\n1. SCORE (out of 10)\n2. MARKET ANALYSIS\n3. TARGET AUDIENCE\n4. COMPETITORS\n5. MONETIZATION\n6. RISKS\n7. RECOMMENDATION"
            else:
                prompt = f"Quyidagi startup ideani professional tahlil qil:\nIdea: {text}\n\n1. BAHO (10 dan)\n2. BOZOR TAHLILI\n3. TARGET AUDITORIYA\n4. RAQOBATCHILAR\n5. MONETIZATSIYA\n6. XATARLAR\n7. TAVSIYA"
            result = ask_ai_once(prompt, lang)
            header = f"📊 ANALYSIS: {text.upper()}\n\n" if lang == "en" else f"📊 TAHLIL: {text.upper()}\n\n"
            await update.message.reply_text(header + result)
            return await back_to_menu(update, context)

        # Roadmap mode
        elif mode == "roadmap":
            if lang == "en":
                prompt = f"Create a 6-month roadmap for this startup:\n{text}\n\nFor each month: 3 main tasks, success metrics, estimated budget\nMonth 1-6: PREPARATION, MVP, TESTING, LAUNCH, GROWTH, SCALE"
            else:
                prompt = f"Quyidagi startup uchun 6 oylik yo'l xaritasi tuz:\n{text}\n\nHar oy: 3 ta asosiy vazifa, muvaffaqiyat ko'rsatkichi, taxminiy byudjet\n1-6 oy: TAYYORGARLIK, MVP, SINOV, LAUNCH, OSISH, SCALE"
            result = ask_ai_once(prompt, lang)
            header = f"🗺 6-MONTH ROADMAP: {text.upper()}\n\n" if lang == "en" else f"🗺 6 OYLIK YO'L XARITASI: {text.upper()}\n\n"
            await update.message.reply_text(header + result)
            return await back_to_menu(update, context)

        # Idea flow - step by step
        elif step == 1:
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
                prompt = f"""Generate 3 startup ideas based on:
Industry: {data['industry']}
Capital: {data['capital']}
Problem to solve: {data['problem']}

For each idea:
1 Name
💡 Idea: brief description
👥 Target: who is it for
💰 Monetization: how to earn
📈 Growth potential: high/medium/low"""
            else:
                prompt = f"""Quyidagi ma'lumotlarga asoslanib 3 ta startup idea ber:
Soha: {data['industry']}
Kapital: {data['capital']}
Hal qilmoqchi muammo: {data['problem']}

Har bir idea uchun:
1 Nomi
💡 Idea: qisqa tavsif
👥 Target: kim uchun
💰 Monetizatsiya: qanday pul ishlaydi
📈 O'sish potentsiali: yuqori/o'rta/past"""

            result = ask_ai_once(prompt, lang)
            header = "🚀 YOUR STARTUP IDEAS:\n\n" if lang == "en" else "🚀 SIZNING STARTUP GOYALARINGIZ:\n\n"
            footer = "\n\n💬 Which one do you like? Tell me and I'll help develop it!" if lang == "en" else "\n\n💬 Qaysi biri yoqdi? Ayting, rivojlantirishga yordam beraman!"
            await update.message.reply_text(header + result + footer)
            context.user_data["idea_step"] = 0
            context.user_data["mode"] = "chat"
            return IDEA_FLOW

        # Free chat
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
    menu = TEXTS[lang]["menu"]
    keyboard = [[menu[0], menu[1]], [menu[2], menu[3]]]
    msg = "Choose next action:" if lang == "en" else "Keyingi amalni tanlang:"
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return MENU

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in conversation_history:
        del conversation_history[user_id]
    context.user_data.clear()
    lang = "uz"
    await update.message.reply_text(TEXTS[lang]["reset_done"])
    return await start(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "uz")
    await update.message.reply_text(TEXTS[lang]["help"])

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Sizda bu huquq yoq.")
        return
    if not context.args:
        await update.message.reply_text("Misol: /broadcast Xabar matni")
        return
    message_text = " ".join(context.args)
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 Startup Mind Bot:\n\n{message_text}")
            sent += 1
        except:
            pass
    await update.message.reply_text(f"✅ Yuborildi: {sent}/{len(users)} ta")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Sizda bu huquq yoq.")
        return
    users = get_all_users()
    await update.message.reply_text(f"📊 Jami: {len(users)} ta\n💬 Faol: {len(conversation_history)} ta")


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
        ]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))

    print("✅ Startup Mind Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()