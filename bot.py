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

# Flask app
flask_app = Flask(__name__)

# Use global event loop
loop = asyncio.get_event_loop()

# Create the bot application
app = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start received")
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📨 Echo: {update.message.text}")
    await update.message.reply_text(f"You said: {update.message.text}")

# Add handlers to app
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", start))  # Same reply as start
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# --- Webhook Route ---
@flask_app.route("/")
def home():
    return "✅ Bot is up!"

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, app.bot)

        # Schedule the update processing
        asyncio.run_coroutine_threadsafe(app.process_update(update), loop)
        print(f"✅ Update received: {update_data}")
    except Exception as e:
        print(f"❌ Webhook processing error: {e}")
    return "ok"

# --- Initialize bot ---
async def setup_bot():
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"🚀 Webhook set to: {WEBHOOK_URL}/webhook")

# --- Start everything ---
if __name__ == "__main__":
    loop.run_until_complete(setup_bot())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
