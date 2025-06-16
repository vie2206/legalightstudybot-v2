import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

# Load environment variables (optional)
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://yourdomain.com

telegram_app = Application.builder().token(TOKEN).build()

# Handlers
async def start(update: Update, context):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context):
    await update.message.reply_text("Here's how I can help you...")

async def echo(update: Update, context):
    await update.message.reply_text(update.message.text)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# Flask App
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "✅ LegalightStudyBot is running!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception as e:
        print(f"Error: {e}")
        return "Something went wrong", 500
    return "ok"

# Run webhook
if __name__ == "__main__":
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/webhook",
        app=app
    )
