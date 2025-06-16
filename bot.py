import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://legalightstudybot-docker.onrender.com/webhook")
PORT = int(os.environ.get("PORT", 10000))

# Create Flask app
flask_app = Flask(__name__)

# Create Telegram bot application
telegram_app = Application.builder().token(BOT_TOKEN).build()

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💡 Use /start to begin your journey.\nMore features coming soon!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔁 You said: {update.message.text}")

# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("hello", echo))

# === FLASK ROUTES ===
@flask_app.route('/')
def index():
    return "✅ LegalightStudyBot is running."

@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception as e:
        logger.error(f"❌ Error in webhook: {e}")
    return 'OK'

# === RUN EVERYTHING ===
if __name__ == '__main__':
    async def main():
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook set to: {WEBHOOK_URL}")

        from aiohttp import web
        runner = web.AppRunner(web.WSGIApp(flask_app))
        await runner.setup()
        site = web.TCPSite(runner, host='0.0.0.0', port=PORT)
        await site.start()
        print(f"🚀 Bot is live on port {PORT}")

        while True:
            await asyncio.sleep(3600)

    asyncio.run(main())
