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

# ─── Load env & configure logging ───────────────────────────────────────────────
load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://yourapp.onrender.com
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set in your environment")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Core handlers ──────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "📚 *Commands:*\n"
        "/start — Restart the bot\n"
        "/help  — Show this message\n\n"
        "⏲️ *Pomodoro* (/timer …)\n"
        "📅 *Countdown* (/countdown …)\n"
    )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command. Try /help.")


# ─── Main application setup & webhook launch ──────────────────────────────────
async def main():
    # 1) Build the Application
    app = ApplicationBuilder().token(TOKEN).build()

    # 2) Register core handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))

    # 3) Register your feature modules *before* fallback
    timer.register_handlers(app)
    countdown.register_handlers(app)

    # 4) Fallback for any other /command
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    # 5) Initialize & start
    await app.initialize()
    await app.start()

    # 6) Set the Telegram “slash-command” menu (must be awaited)
    commands = [
        BotCommand("start",            "Restart the bot"),
        BotCommand("help",             "Show help message"),
        BotCommand("timer",            "Start a Pomodoro session"),
        BotCommand("timer_status",     "Show remaining time"),
        BotCommand("timer_pause",      "Pause session"),
        BotCommand("timer_resume",     "Resume session"),
        BotCommand("timer_stop",       "Cancel session"),
        BotCommand("countdown",        "Start live countdown"),
        BotCommand("countdown_status", "Show remaining once"),
        BotCommand("countdown_stop",   "Cancel live countdown"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("✅ Commands registered")

    # 7) Launch webhook listener and set the webhook URL
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}/webhook")

    # 8) Idle until Ctrl-C or termination
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
