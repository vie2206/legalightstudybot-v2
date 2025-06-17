# bot.py
import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters
)
from database import init_db
from study_tasks import register_handlers as register_task_handlers, VALID_TASK_TYPES

# Load environment variables
def load_config():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    webhook = os.getenv("WEBHOOK_URL", "").rstrip("/")
    port = int(os.getenv("PORT", "10000"))
    if not token or not webhook:
        raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set in environment.")
    return token, webhook, port

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
    # Catch-all for unsupported commands
    await update.message.reply_text(
        "❓ Sorry, I didn't recognize that command. Use /help to see what I can do."
    )


def main():
    # 1) initialize database tables
    init_db()

    # 2) load settings
    token, webhook_url, port = load_config()

    # 3) build the Telegram application
    app = ApplicationBuilder().token(token).build()

    # 4) register core handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # 5) register study-task module handlers
    register_task_handlers(app)

    # 6) catch-all unknown commands (after all others)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    # 7) start webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/webhook",
        webhook_url=f"{webhook_url}/webhook"
    )

if __name__ == "__main__":
    main()
