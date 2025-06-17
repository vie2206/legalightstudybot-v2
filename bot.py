# bot.py
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from database import init_db
from study_tasks import register_handlers as register_task_handlers

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")  # e.g. https://yourapp.onrender.com
PORT = int(os.getenv("PORT", "10000"))

# Valid study task types for /task_start
VALID_TASK_TYPES = [
    'CLAT_MOCK', 'SECTIONAL', 'NEWSPAPER', 'EDITORIAL', 'GK_CA', 'MATHS',
    'LEGAL_REASONING', 'LOGICAL_REASONING', 'CLATOPEDIA', 'SELF_STUDY',
    'ENGLISH', 'STUDY_TASK'
]

async def start(update, context):
    await update.message.reply_text(
        "👋 Hello! I'm Legalight Study Bot.\n"
        "Use /help to see available commands."
    )

async def help_cmd(update, context):
    types_str = ', '.join(VALID_TASK_TYPES)
    await update.message.reply_text(
        "Available commands:\n"
        "/task_start <type>  – start a stopwatch task\n"
        "/task_status       – show your current task time\n"
        "/task_pause        – pause it\n"
        "/task_resume       – resume it\n"
        "/task_stop         – stop & log it\n"
        "/help              – this message\n\n"
        "Usage: /task_start <type>\n"
        f"Valid types: {types_str}"
    )

async def unknown_cmd(update, context):
    await update.message.reply_text(
        "Sorry, I didn't recognize that command. Use /help to see what I can do."
    )

def main():
    # 1) ensure database tables exist
    init_db()

    # 2) build the Telegram application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3) register core commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler(None, unknown_cmd))

    # 4) register the study-task module handlers
    register_task_handlers(app)

    # 5) launch via webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )

if __name__ == "__main__":
    main()
