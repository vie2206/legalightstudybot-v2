import os
import telegram
from flask import Flask, request
from telegram.ext import ApplicationBuilder, CommandHandler
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. "https://legalightstudybot-docker.onrender.com"

telegram_app = ApplicationBuilder().token(TOKEN).build()

# --- Handlers ---
async def start(update, context):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update, context):
    await update.message.reply_text("⚙️ Type /start to begin.\nMore features coming soon!")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))

# --- Flask App ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Legalight Study Bot is live."

@app.route('/webhook', methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.initialize()  # ✅ IMPORTANT FIX
        await telegram_app.process_update(update)
        return "ok"

# --- Set webhook on startup ---
async def set_webhook():
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=10000)
