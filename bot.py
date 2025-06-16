import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from flask import Flask, request
import asyncio

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Example: https://yourapp.onrender.com

app = Flask(__name__)

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Need help? Try /start or /countdown")

# Add more commands as needed

# Telegram application setup
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "ok"

@app.route("/")
def home():
    return "Legalight Bot Running - Webhook Mode ✅"

if __name__ == '__main__':
    telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
