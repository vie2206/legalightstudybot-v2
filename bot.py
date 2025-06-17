# bot.py
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from database import init_db
from study_tasks import register_handlers as register_task_handlers

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")  # e.g. https://yourapp.onrender.com
PORT        = int(os.getenv("PORT", "10000"))

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
    # 1) ensure our tables exist
    init_db()

    # 2) build the bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3) register core commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # 4) register the study‐task module
    register_task_handlers(app)

    # 5) run webhook (built‐in)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        path="/webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )

if __name__ == "__main__":
    main()
