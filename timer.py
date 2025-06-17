# bot.py
import os
import logging
import asyncio

from telegram import BotCommand, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

import timer  # our Pomodoro module; later you’ll import countdown, quiz, etc.

from dotenv import load_dotenv

load_dotenv()

TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. "https://yourapp.onrender.com/webhook"
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set in environment")

# ——— Setup logging ——————————————————————————————————
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ——— Build the bot application —————————————————————
app = ApplicationBuilder().token(TOKEN).build()

# ——— Register feature modules —————————————————————
timer.register_handlers(app)
# later, when you have countdown.py:
# countdown.register_handlers(app)
# quiz.register_handlers(app)
# …and so on.

# ——— Register slash-commands with Telegram ———————————
async def set_commands():
    cmds = [
        BotCommand("timer", "Start/cancel/check Pomodoro (/timer [work] [break])"),
        BotCommand("timer_stop", "Cancel the Pomodoro"),
        BotCommand("timer_status", "Show remaining time"),
        # add your other commands as you build them...
    ]
    await app.bot.set_my_commands(cmds)
    logger.info("✅ Registered slash-commands")

# ——— Bootstrap: set commands & webhook ——————————————
async def bootstrap():
    await set_commands()
    await app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

# Run our bootstrap on the single event loop, then hand off to PTB’s webhook server
if __name__ == "__main__":
    # 1) initialize commands + webhook
    asyncio.run(bootstrap())

    # 2) start listening for Telegram on /webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_path="/webhook",
        webhook_url=WEBHOOK_URL
    )
