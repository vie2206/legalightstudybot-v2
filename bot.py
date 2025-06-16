import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# Initialize Flask
app = Flask(__name__)

# Get the bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Create the Telegram bot application
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Define command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

# Add handlers to the bot
telegram_app.add_handler(CommandHandler("start", start))

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
        return "OK", 200

# Basic home page route
@app.route("/", methods=["GET"])
def index():
    return "🤖 LegalightStudyBot is running."

# Set the webhook when the app starts
@app.before_first_request
def set_webhook():
    webhook_url = os.getenv("WEBHOOK_URL", "https://legalightstudybot-docker.onrender.com/webhook")
    telegram_app.bot.set_webhook(webhook_url)
    print(f"🚀 Webhook set: {webhook_url}")

# Run the Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
