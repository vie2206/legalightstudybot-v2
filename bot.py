import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # eg. https://legalightstudybot-docker.onrender.com

# --- FLASK APP SETUP ---
flask_app = Flask(__name__)

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛟 Need help? Try /start or stay tuned for more features.")

# --- TELEGRAM APP INITIALIZATION ---
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))

# Initialize the bot (safe for webhook use)
asyncio.run(telegram_app.initialize())

# --- FLASK ROUTES ---
@flask_app.route("/")
def home():
    return "Legalight StudyBot is alive ✨"

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "ok"

# Set webhook on startup
asyncio.run(telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook"))

# --- RUN THE SERVER ---
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
