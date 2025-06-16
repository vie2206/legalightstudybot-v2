import os
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Flask(__name__)

# Telegram bot setup
application = ApplicationBuilder().token(BOT_TOKEN).build()


# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

# Echo message handler
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📨 You said: {update.message.text}")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("hello", echo))


@app.route("/")
def home():
    return "Legalight StudyBot is alive!"


@app.route("/webhook", methods=["POST"])
def webhook():
    """Process Telegram updates via webhook"""
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
    return "OK"
