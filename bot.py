import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g., https://yourapp.onrender.com

app = Flask(__name__)
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

telegram_app.add_handler(CommandHandler("start", start))

# Webhook route
@app.post("/webhook")
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

@app.route("/", methods=["GET"])
def home():
    return "LegalightStudyBot is running!"

@app.before_first_request
def init_webhook():
    telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("✅ Webhook set successfully.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
