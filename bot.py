# bot.py
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from database import init_db
from study_tasks import register_handlers as register_task_handlers

# Load .env (BOT_TOKEN, WEBHOOK_URL, etc)
load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")  # e.g. https://legalightstudybot-docker.onrender.com
PORT        = int(os.getenv("PORT", "10000"))

# — Core command handlers —
async def start(update, context):
    await update.message.reply_text(
        "👋 Hello! I'm Legalight Study Bot.\n"
        "Use /task_start to begin a study task."
    )

async def help_cmd(update, context):
    await update.message.reply_text(
        "Available commands:\n"
        "/task_start <type>  – start a stopwatch task\n"
        "/task_status       – show your current task time\n"
        "/task_pause        – pause it\n"
        "/task_resume       – resume it\n"
        "/task_stop         – stop & log it\n"
        "/help              – this message"
    )

def main():
    # 1️⃣ Ensure database tables exist
    init_db()

    # 2️⃣ Build the Telegram application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3️⃣ Register core commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # 4️⃣ Wire in your study‐task module
    register_task_handlers(app)

    # 5️⃣ Launch via webhook
    app.run_webhook(
        listen="0.0.0.0",                 # accept traffic on any interface
        port=PORT,                        # Render’s assigned port
        url_path="/webhook",              # the HTTP path Telegram will POST to
        webhook_url=f"{WEBHOOK_URL}/webhook"  # full URL Telegram should call
    )

if __name__ == "__main__":
    main()
