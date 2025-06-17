import os
import logging
import asyncio
from telegram import BotCommand, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import timer
import countdown
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://yourapp.onrender.com/webhook
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set in environment")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Core Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 *LegalightStudyBot Commands:*\n"
        "/start - Restart the bot\n"
        "/help - Show this help message\n\n"
        "*Pomodoro Timer*\n"
        "/timer `<name>` `<study_min>` `<break_min>` - Start a session\n"
        "/timer_pause - Pause current session\n"
        "/timer_resume - Resume paused session\n"
        "/timer_status - Show remaining time\n"
        "/timer_stop - Cancel session\n\n"
        "*Date Countdown*\n"
        "/countdown `<YYYY-MM-DD>` `[HH:MM:SS]` `<label>` `[--pin]` - Live countdown\n"
        "/countdown_status - Show remaining time once\n"
        "/countdown_stop - Cancel live countdown\n"
    )
    await update.message.reply_markdown(help_text)

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Sorry, I didn't understand that command. Try /help."
    )

# --- Main Application ---
async def main():
    # Build application
    app = ApplicationBuilder().token(TOKEN).build()

    # Register core handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    # Fallback for any unknown /command
    app.add_handler(MessageHandler(filters.COMMAND, fallback))

    # Register feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)

    # Initialize and start
    await app.initialize()
    await app.start()

    # Configure slash commands
    commands = [
        BotCommand("start",            "Restart the bot"),
        BotCommand("help",             "Show help message"),
        BotCommand("timer",            "Start a session (name study break)"),
        BotCommand("timer_pause",      "Pause session"),
        BotCommand("timer_resume",     "Resume session"),
        BotCommand("timer_status",     "Show remaining time"),
        BotCommand("timer_stop",       "Cancel session"),
        BotCommand("countdown",        "Live countdown to date/time"),
        BotCommand("countdown_status", "Show remaining time once"),
        BotCommand("countdown_stop",   "Cancel live countdown"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("✅ Registered slash-commands")

    # Start webhook listener & set webhook
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL,
    )
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

    # Run until manually stopped
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
