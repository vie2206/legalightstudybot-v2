# bot.py

import os, logging, asyncio
from telegram import BotCommand
from telegram.ext import ApplicationBuilder
import timer
from dotenv import load_dotenv

load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://.../webhook
PORT        = int(os.getenv("PORT", "10000"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # register Pomodoro (+ pause/resume!)
    timer.register_handlers(app)

    await app.initialize()
    await app.start()

    # slash commands
    cmds = [
        BotCommand("timer",        "Start a session (/timer name study break)"),
        BotCommand("timer_pause",  "Pause current session"),
        BotCommand("timer_resume", "Resume paused session"),
        BotCommand("timer_status", "Check remaining time"),
        BotCommand("timer_stop",   "Cancel session"),
    ]
    await app.bot.set_my_commands(cmds)
    logger.info("✅ Commands set")

    # webhook in one shot
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL,
    )
    logger.info(f"✅ Webhook at {WEBHOOK_URL}")

    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
