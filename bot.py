import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
)
import countdown  # our countdown module

# Load from environment
BOT_TOKEN   = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g. https://yourapp.onrender.com

# Flask app
app = Flask(__name__)

# Telegram Application
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ─── BASIC HANDLERS ────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Commands:* (Markdown)\n"
        "/start — Restart bot\n"
        "/help — This message\n\n"
        "⏳ *Countdown:* /countdown <YYYY-MM-DD> [HH:MM:SS] <label> [--pin]\n"
        "/countdown_status — Show remaining once\n"
        "/countdown_stop — Cancel live countdown",
        parse_mode="Markdown",
    )

# register basic commands
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help",  help_cmd))

# ─── COUNTDOWN HANDLERS ─────────────────────────────────────────────────────────
# this will add /countdown, /countdown_status & /countdown_stop
countdown.register_handlers(telegram_app)

# ─── WEBHOOK ROUTE ──────────────────────────────────────────────────────────────
@app.post("/webhook")
async def telegram_webhook():
    """Receive updates from Telegram."""
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

# ─── RUN ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/webhook",
        app=app,
    )
