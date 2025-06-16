import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import asyncio

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://legalightstudybot-docker.onrender.com/webhook")

# Create the bot application
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Define command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

telegram_app.add_handler(CommandHandler("start", start))

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
        return "OK", 200

# Root route
@app.route("/", methods=["GET"])
def index():
    return "✅ LegalightStudyBot is live."

# Set webhook manually once when running
async def set_webhook_once():
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    print(f"🚀 Webhook set: {WEBHOOK_URL}")

# Run the bot and flask together
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_webhook_once())
    app.run(host="0.0.0.0", port=port)
