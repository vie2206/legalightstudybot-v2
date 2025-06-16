import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Flask app
flask_app = Flask(__name__)

# Telegram application
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start received")
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📨 Echo: {update.message.text}")
    await update.message.reply_text(f"You said: {update.message.text}")

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# Webhook route
@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, app.bot)
        asyncio.get_event_loop().create_task(app.process_update(update))
        print(f"✅ Update received and dispatched: {update_data}")
    except Exception as e:
        print(f"❌ Error handling update: {e}")
    return "ok"

@flask_app.route("/")
def index():
    return "✅ Legalight Bot is running"

# Start Telegram + Flask
async def run_bot():
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"🚀 Webhook set to: {WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_bot())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
