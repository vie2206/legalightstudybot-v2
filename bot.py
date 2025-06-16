import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- Config ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

flask_app = Flask(__name__)
app: Application = Application.builder().token(BOT_TOKEN).build()


# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start received")
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /help received")
    await update.message.reply_text("🛟 Use /start to begin.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📨 Echo: {update.message.text}")
    await update.message.reply_text(f"You said: {update.message.text}")

# Add handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


# --- Webhook Route ---
@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), app.bot)
        asyncio.run(app.process_update(update))
        print("✅ Update processed")
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
    return "ok"

@flask_app.route("/")
def home():
    return "✅ Bot is running."


# --- Start everything ---
async def init():
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"🚀 Webhook set: {WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    asyncio.run(init())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
