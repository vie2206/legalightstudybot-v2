import os
import logging
import asyncio

from telegram import BotCommand
from telegram.ext import (
    ApplicationBuilder,
)
import timer

from dotenv import load_dotenv

# — Load environment —
load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://yourapp.onrender.com/webhook
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set in environment")

# — Logging setup —
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# — Slash commands to register —
SLASH_COMMANDS = [
    BotCommand("timer",        "Start/cancel/check Pomodoro (/timer [work] [break])"),
    BotCommand("timer_stop",   "Cancel the Pomodoro"),
    BotCommand("timer_status", "Show remaining time"),
    # add more as you implement them...
]

async def main():
    # 1) Build application
    app = ApplicationBuilder().token(TOKEN).build()

    # 2) Register handlers
    timer.register_handlers(app)
    # later: countdown.register_handlers(app), etc.

    # 3) Initialize & start
    await app.initialize()
    await app.start()

    # 4) Register slash commands
    await app.bot.set_my_commands(SLASH_COMMANDS)
    logger.info("✅ Registered slash-commands")

    # 5) Set Telegram webhook
    await app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

    # 6) Start the webhook listener
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook"
    )

    # 7) Run until interrupted
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
