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
import timer         # your pomodoro module
import countdown     # your countdown module
import quiz          # the quiz stub from above

load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.onrender.com

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# build the Application
app = Application.builder().token(TOKEN).build()

# core commands
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
        "🎉 Quiz: /quiz_start [topic], /quiz_winner\n"
        # … list other top-level commands …
    )

# register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))

timer.register_handlers(app)
countdown.register_handlers(app)
quiz.register_handlers(app)

def main():
    """Launch the built-in webhook server."""
    # 1) Tell Telegram where to send updates
    webhook_path = "/webhook"
    full_webhook = f"{WEBHOOK_URL}{webhook_path}"
    logger.info("Setting webhook to %s", full_webhook)
    app.bot.set_webhook(full_webhook)

    # 2) Start PTB's webhook server on the given port
    port = int(os.environ.get("PORT", 10000))
    logger.info("Starting webhook server on port %d", port)
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_path=webhook_path,
    )

if __name__ == "__main__":
    main()
