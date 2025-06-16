import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Create Flask app
app = Flask(__name__)

# Create Telegram bot application
telegram_app = Application.builder().token(BOT_TOKEN).build()

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

# Add command handler to Telegram app
telegram_app.add_handler(CommandHandler("start", start))

# Flask webhook route
@app.post("/webhook")
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.initialize()
        await telegram_app.process_update(update)
        return "ok"

# Flask test root route
@app.get("/")
def index():
    return "✅ LegalightStudyBot is live!"

# Port binding for Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
