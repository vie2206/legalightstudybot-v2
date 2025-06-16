import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Set up Flask app and global loop
flask_app = Flask(__name__)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Set up Telegram Application
app = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start received")
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📨 Echo: {update.message.text}")
    await update.message.reply_text(f"You said: {update.message.text}")

# Register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# --- Flask Webhook Route ---
@flask_app.route("/")
def home():
    return "✅ Bot is running."

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), app.bot)
        asyncio.run_coroutine_threadsafe(app.process_update(update), loop)
        print("✅ Update dispatched to Telegram bot loop")
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
    return "ok"

# --- Initialize everything ---
async def init_bot():
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"🚀 Webhook set to: {WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    loop.run_until_complete(init_bot())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
