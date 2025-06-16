import os, logging, asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

# --- Load env ---
load_dotenv()
TOKEN     = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://…/webhook

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask app ---
app = Flask(__name__)

# --- Telegram Application (no Updater/polling) ---
telegram_app = ApplicationBuilder().token(TOKEN).updater(None).build()

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Type /start to begin. More features coming soon!")

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Sorry, I didn’t understand that. Try /help or /start!")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_cmd))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

# --- Webhook route (PATH only!) ---
@app.post("/webhook")
async def webhook():
    """Receive updates at POST /webhook"""
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    # Initialize, process, and shutdown automatically
    async with telegram_app:
        await telegram_app.process_update(update)
    return "OK", 200

# --- Startup: set the webhook with Telegram ---
async def on_startup():
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

if __name__ == "__main__":
    # Schedule the webhook setup before serving
    asyncio.run(on_startup())
    # Then start Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
