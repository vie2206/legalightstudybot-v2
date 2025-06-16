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

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

flask_app = Flask(__name__)
update_queue = asyncio.Queue()

app = ApplicationBuilder().token(BOT_TOKEN).update_queue(update_queue).build()

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start received")
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📨 Echo: {update.message.text}")
    await update.message.reply_text(f"You said: {update.message.text}")

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", start))  # Alias for /start
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# --- Webhook route ---
@flask_app.route("/")
def home():
    return "✅ Bot is running."

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update_json = request.get_json(force=True)
        update = Update.de_json(update_json, app.bot)
        update_queue.put_nowait(update)
        print(f"✅ Update pushed to queue: {update_json}")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
    return "ok"

# --- Start everything ---
async def start_bot():
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await app.start()
    print(f"🚀 Webhook set to: {WEBHOOK_URL}/webhook")
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
