import os
import logging
import asyncio

from telegram import BotCommand
from telegram.ext import ApplicationBuilder

import timer
from dotenv import load_dotenv

load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # must start with https://
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL (https://...) must be set")

# — Logging —
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slash commands list
SLASH_COMMANDS = [
    BotCommand("timer",        "Start/cancel/check Pomodoro"),
    BotCommand("timer_stop",   "Cancel the Pomodoro"),
    BotCommand("timer_status", "Show remaining time"),
]

async def main():
    # 1) build application
    app = ApplicationBuilder().token(TOKEN).build()

    # 2) register handlers
    timer.register_handlers(app)

    # 3) initialize & start (no polling)
    await app.initialize()
    await app.start()

    # 4) set slash-commands
    await app.bot.set_my_commands(SLASH_COMMANDS)
    logger.info("✅ Registered slash-commands")

    # 5) start webhook listener & set the webhook in one go
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL,
    )
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

    # 6) idle (keep running)
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
