# bot.py
import os
import asyncio
from dotenv import load_dotenv

from flask import Flask, request, abort
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# import your feature modules
import timer
import countdown
import quiz

# load .env (BOT_TOKEN, WEBHOOK_URL)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN environment variable")

# ─── Flask app ──────────────────────────────────────────────────────────────
flask_app = Flask(__name__)

# ─── Telegram Application ────────────────────────────────────────────────────
app = ApplicationBuilder().token(BOT_TOKEN).build()

# ─── Core Handlers ───────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n"
        "Use /help to see all available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Commands*:\n"
        "/start — Restart bot\n"
        "/help — This message\n\n"
        "⏲️ Timer:\n"
        "/timer `<name> <work_mins> <break_mins>`\n"
        "/timer_status\n"
        "/timer_stop\n\n"
        "📅 Countdown:\n"
        "/countdown `<YYYY-MM-DD> [HH:MM:SS] <label>`\n"
        "/countdown_status\n"
        "/countdown_stop\n\n"
        "🎉 Quiz & Winners:\n"
        "/quiz_start `<topic>`\n"
        "/quiz_winner\n\n"
        "🔥 Streaks, 🎖️ Badges, 📊 Summaries, ⏰ Reminders, 🤗 Motivation, etc.",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # catches *any* unknown /command
    await update.message.reply_text("❓ Unknown command. Try /help.")

# register core
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(MessageHandler(filters.COMMAND, fallback))

# ─── Feature Modules ─────────────────────────────────────────────────────────
# each of these files (timer.py, countdown.py, quiz.py) must define:
#     def register_handlers(app: Application): ...
timer.register_handlers(app)
countdown.register_handlers(app)
quiz.register_handlers(app)

# ─── Webhook Endpoint ────────────────────────────────────────────────────────
@flask_app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Receives updates from Telegram and dispatches to PTB."""
    data = request.get_json(force=True)
    if not data:
        return "no data", 400
    update = Update.de_json(data, app.bot)
    # we spin up a fresh event loop per update
    asyncio.run(app.process_update(update))
    return "OK"

# health-check
@flask_app.route("/", methods=["GET"])
def health_check():
    return "LegalightStudyBot is running!"

# ─── Entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # You can optionally set your webhook here via Telegram API,
    # or set it manually with:
    #   curl -F "url=https://<your-url>/webhook" https://api.telegram.org/bot<token>/setWebhook
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
