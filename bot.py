import os
import asyncio
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import timer
import countdown
import streak

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # root URL, no '/webhook'

# Initialize Flask app
flask_app = Flask(__name__)

# Initialize Telegram application
telegram_app = Application.builder().token(TOKEN).build()

# Register module handlers
timer.register_handlers(telegram_app)
countdown.register_handlers(telegram_app)
streak.register_handlers(telegram_app)

# Help command
def help_text():
    return (
        "🤖 *Legalight Study Bot Commands*\n\n"
        "/help - Show this help message\n"
        "/task_start `<type>` - Start a task stopwatch\n"
        "/task_status - Show current task time\n"
        "/task_pause - Pause current task\n"
        "/task_resume - Resume paused task\n"
        "/task_stop - Stop & log task time\n"
        "/countdown <YYYY-MM-DD> <Event> - Show real-time countdown\n"
        "/checkin - Record today's study check-in\n"
        "/mystreak - Show your current streak\n"
        "/streak_alerts [on|off] - Toggle streak alerts"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(help_text())

# Unknown command handler
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Sorry, I didn't recognize that command. Use /help to see available commands."
    )

# Register help and fallback handlers
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

# Webhook endpoint
@flask_app.post("/webhook")
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

if __name__ == "__main__":
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )
