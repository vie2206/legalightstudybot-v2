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

import timer        # your Pomodoro module
import countdown    # your countdown module
import quiz         # your QuizBot-wrapper module

load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.onrender.com

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ——— Core commands ———
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Commands:\n"
        "/start — Restart bot\n"
        "/help — This message\n\n"
        "⏲️ Pomodoro: /timer <name> <work_min> <break_min>\n"
        "⏳ Countdown: /countdown YYYY-MM-DD [HH:MM:SS] <label> [--pin]\n"
        "🎉 Quiz: /quiz_start [topic]  /quiz_winner\n"
        # … extend as you add modules …
    )

def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    timer.register_handlers(app)
    countdown.register_handlers(app)
    quiz.register_handlers(app)

def main():
    # Build
    app = Application.builder().token(TOKEN).build()
    register_handlers(app)

    # Launch built-in webhook server (PTB 20.7 signature)
    port     = int(os.environ.get("PORT", 10000))
    path     = "/webhook"                             # must match Telegram’s URL path
    full_url = f"{WEBHOOK_URL}{path}"                 # e.g. https://.../webhook

    logger.info("Starting webhook on port %d with path %r → %s", port, path, full_url)
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=path,            # <— not webhook_path
        webhook_url=full_url,     # PTB will call set_webhook under the hood
        drop_pending_updates=True # optional: avoid old updates
    )

if __name__ == "__main__":
    main()
