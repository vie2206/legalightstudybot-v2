import os
import logging
import asyncio
from flask import Flask, request
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application

import timer        # your timer module
import countdown    # your countdown module
import quiz         # the new quiz.py stub

# load .env
load_dotenv()
TOKEN      = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.onrender.com

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# create the Telegram Application
telegram_app = Application.builder().token(TOKEN).build()

# register each feature’s handlers
timer.register_handlers(telegram_app)
countdown.register_handlers(telegram_app)
quiz.register_handlers(telegram_app)

# flask app to receive webhooks
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "✅ Bot is running"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True)
    update  = Update.de_json(payload, telegram_app.bot)
    # dispatch to PTB
    asyncio.run(telegram_app.process_update(update))
    return "OK"

if __name__ == "__main__":
    # tell Telegram where to send updates
    telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")  
    # start Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
