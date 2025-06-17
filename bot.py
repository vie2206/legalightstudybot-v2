# bot.py

import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import timer        # Pomodoro module
import countdown    # Countdown module

# — Load environment —
load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://legalightstudybot-docker.onrender.com

# — Logging —
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# — Core command handlers —
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome back to LegalightStudyBot!\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Commands:\n"
        "/start — Restart bot\n"
        "/help — This message\n\n"
        "⏲️ Pomodoro: /timer <name> <work_min> <break_min>\n"
        "⏳ Countdown: /countdown YYYY-MM-DD [HH:MM:SS] <label>\n"
    )

def register_handlers(app: Application):
    # core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    # feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)

def main():
    # Build application
    app = Application.builder().token(TOKEN).build()
    register_handlers(app)

    # Webhook settings
    port     = int(os.environ.get("PORT", 10000))
    path     = "/webhook"
    full_url = f"{WEBHOOK_URL}{path}"

    logger.info(
        "Starting PTB webhook server on port %d, path %r → %s",
        port, path, full_url
    )

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=path,
        webhook_url=full_url,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
