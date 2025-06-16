import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)
from telegram.ext.webhook import WebhookServer
from aiohttp import web

# Logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram Bot Token and Webhook URL
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://legalightstudybot-docker.onrender.com/webhook")
PORT = int(os.environ.get("PORT", 10000))

# Flask App
flask_app = Flask(__name__)

# Telegram Application
telegram_app = Application.builder().token(BOT_TOKEN).build()


# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💡 Use /start to begin your journey.\nMore features coming soon!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔁 You said: {update.message.text}")

# Add handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("hello", echo))


# === FLASK ROUTES ===
@flask_app.route('/')
def home():
    return "✅ LegalightStudyBot is running."

@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception as e:
        logger.error("❌ Error in webhook: %s", e)
    return 'OK'


# === ENTRY POINT ===
if __name__ == '__main__':
    async def main():
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook set: {WEBHOOK_URL}")

        runner = web.AppRunner(web.WSGIApp(flask_app))
        await runner.setup()
        site = web.TCPSite(runner, host='0.0.0.0', port=PORT)
        await site.start()
        print(f"🚀 Bot is live at {WEBHOOK_URL}")

        while True:
            await asyncio.sleep(3600)

    asyncio.run(main())
