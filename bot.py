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

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # without trailing slash

flask_app = Flask(__name__)
loop = asyncio.get_event_loop()

# --- Telegram Application Setup ---
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start received")
    if update.message:
        await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /help received")
    if update.message:
        await update.message.reply_text("🛟 Use /start to begin. More commands coming soon!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📨 Echo: {update.message.text}")
    if update.message:
        await update.message.reply_text(f"You said: {update.message.text}")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# --- Webhook Route ---
@flask_app.route("/")
def home():
    return "✅ LegalightStudyBot is live!"

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update_json = request.get_json(force=True)
        print(f"📥 Raw Update JSON: {update_json}")
        update = Update.de_json(update_json, telegram_app.bot)
        loop.create_task(telegram_app.process_update(update))
        print("✅ Update forwarded to Telegram handlers.")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
    return "ok"

# --- Bot Startup ---
async def run_bot():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print(f"🚀 Webhook set to: {WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    loop.run_until_complete(run_bot())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
