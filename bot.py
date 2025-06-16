import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# --- Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # No trailing slash

# --- Flask App ---
flask_app = Flask(__name__)
loop = asyncio.get_event_loop()

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start received")
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /help received")
    await update.message.reply_text("🛟 Need help? Try /start or stay tuned for more features.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📨 Message received: {update.message.text}")
    await update.message.reply_text(f"You said: {update.message.text}")

# --- Telegram Application ---
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# --- Webhook Routes ---
@flask_app.route("/")
def home():
    return "✅ Bot is running"

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        loop.create_task(telegram_app.process_update(update))
        print(f"✅ Update forwarded: {update}")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
    return "ok"

# --- Initialization ---
async def run_bot():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("🚀 Webhook set!")

# --- Main ---
if __name__ == "__main__":
    loop.run_until_complete(run_bot())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
