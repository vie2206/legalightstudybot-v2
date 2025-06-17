import os
import logging
import asyncio

from telegram import BotCommand
from telegram.ext import ApplicationBuilder

import timer  # our Pomodoro module

from dotenv import load_dotenv

# — Load environment —
load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. "https://yourapp.onrender.com/webhook"
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("Please set BOT_TOKEN and WEBHOOK_URL in your environment")

# — Logging setup —
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# — Build the Telegram application —
app = ApplicationBuilder().token(TOKEN).build()

# — Register feature handlers —
timer.register_handlers(app)
# later: countdown.register_handlers(app), quiz.register_handlers(app), etc.

# — Define slash-commands —
async def set_commands():
    commands = [
        BotCommand("timer",        "Start/cancel/check Pomodoro (/timer [work] [break])"),
        BotCommand("timer_stop",   "Cancel the Pomodoro"),
        BotCommand("timer_status", "Show remaining time"),
        # add more as you build features…
    ]
    await app.bot.set_my_commands(commands)
    logger.info("✅ Registered slash-commands")

# — Bootstrap: set commands & webhook —
async def bootstrap():
    await set_commands()
    await app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

if __name__ == "__main__":
    # 1) Initialize commands + webhook
    asyncio.run(bootstrap())

    # 2) Run PTB’s built-in webhook server on the same event-loop
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        path="/webhook",
    )
