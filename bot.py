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

import countdown
import timer        # ← your pomodoro module
from dotenv import load_dotenv

load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# — core handlers —
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\nUse /help to see commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "📚 *Commands:*\n"
        "/start — Restart bot\n"
        "/help  — This message\n\n"
        "⏲️ *Pomodoro* (/timer …)\n"
        "📅 *Countdown* (/countdown …)\n"
        # add more here as you build them
    )

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Sorry, I didn't understand that. Try /help.")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # 1️⃣ Register feature handlers FIRST
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))

    # Pomodoro timers
    timer.register_handlers(app)

    # Countdown
    countdown.register_handlers(app)

    # 2️⃣ Then register the catch-all fallback
    app.add_handler(MessageHandler(filters.COMMAND, fallback))

    # initialize + start
    await app.initialize()
    await app.start()

    # set the menu in Telegram UI
    cmds = [
        BotCommand("start",            "Restart the bot"),
        BotCommand("help",             "Show help"),
        BotCommand("timer",            "Start a Pomodoro"),
        BotCommand("timer_status",     "Check Pomodoro"),
        BotCommand("timer_stop",       "Stop Pomodoro"),
        BotCommand("countdown",        "Start live countdown"),
        BotCommand("countdown_status", "Show remaining once"),
        BotCommand("countdown_stop",   "Cancel countdown"),
    ]
    await app.bot.set_my_commands(cmds)
    logger.info("✅ Commands registered")

    # webhook
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL,
    )
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
