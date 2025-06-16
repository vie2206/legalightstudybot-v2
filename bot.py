import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://your-app.onrender.com

app = Flask(__name__)

telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()


# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Here to help! 📚 Try /start or send a message.")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))


@app.route("/", methods=["GET"])
def index():
    return "LegalightStudyBot is running!"


@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
        return "ok"


if __name__ == "__main__":
    # Set webhook
    import asyncio
    async def setup():
        await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        print("✅ Webhook set!")

    asyncio.run(setup())

    # Start Flask app
    app.run(host="0.0.0.0", port=10000)
