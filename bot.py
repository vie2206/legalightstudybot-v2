import os
import logging

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

# ─── Load environment & configure logging ───────────────────────────────────────
load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")    # e.g. https://yourapp.onrender.com
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set in environment")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Core command handlers ──────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "📚 *Commands:*\n"
        "/start — Restart bot\n"
        "/help  — Show this help message\n\n"
        "⏲️ *Pomodoro Timer* (/timer …)\n"
        "📅 *Countdown* (/countdown …)\n"
    )

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Unknown command. Try /help."
    )

# ─── Application setup & webhook launch ────────────────────────────────────────
def main():
    # Build the application
    app = ApplicationBuilder().token(TOKEN).build()

    # Register core handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))

    # Register your feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)

    # Catch-all for any other /command
    app.add_handler(MessageHandler(filters.COMMAND, fallback))

    # Configure the Telegram menu of slash commands
    app.bot.set_my_commands([
        BotCommand("start",            "Restart the bot"),
        BotCommand("help",             "Show help message"),
        BotCommand("timer",            "Start a Pomodoro session"),
        BotCommand("timer_pause",      "Pause session"),
        BotCommand("timer_resume",     "Resume session"),
        BotCommand("timer_status",     "Show remaining time"),
        BotCommand("timer_stop",       "Cancel session"),
        BotCommand("countdown",        "Start live countdown"),
        BotCommand("countdown_status", "Show remaining once"),
        BotCommand("countdown_stop",   "Cancel live countdown"),
    ])
    logger.info("✅ Commands registered")

    # Start the built-in webhook server (no Flask)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )

if __name__ == "__main__":
    main()
