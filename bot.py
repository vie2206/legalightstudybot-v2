from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults
import os
import asyncio

# Set your Telegram Bot Token as environment variable or paste directly here
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Or replace with your token directly as a string

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot app
telegram_app = Application.builder().token(BOT_TOKEN).defaults(Defaults(parse_mode='HTML')).build()

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

# Add command handler
telegram_app.add_handler(CommandHandler("start", start))

# Root route (for testing if Render is live)
@app.route('/')
def home():
    return '✅ LegalightStudyBot is live!'

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return 'ok'

# Start webhook on Render (port 10000)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url="https://legalightstudybot-docker.onrender.com/webhook"
    )
