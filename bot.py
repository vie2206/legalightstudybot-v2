import os, logging
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Load configuration from environment
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Error: BOT_TOKEN environment variable is not set.")

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. "https://your-app.onrender.com/webhook"
# Determine the webhook route path from the URL (default to '/webhook' if not provided)
if WEBHOOK_URL:
    from urllib.parse import urlparse
    parsed = urlparse(WEBHOOK_URL)
    WEBHOOK_PATH = parsed.path if parsed.path else "/webhook"
else:
    WEBHOOK_PATH = "/webhook"  # default path if WEBHOOK_URL not set

# Initialize the Telegram bot application (disable polling Updater)
application = ApplicationBuilder().token(BOT_TOKEN).updater(None).build()

# Configure logging for visibility (optional)
logging.basicConfig(level=logging.INFO)
logging.getLogger("telegram").setLevel(logging.WARNING)  # Reduce verbosity of PTB logs

# Define command handler callbacks
async def start(update: Update, context):
    """Send a welcome message on /start"""
    welcome_text = "👋 Hello! I'm your Legalight Study Bot. We can do hard things 💪"
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context):
    """Send a help message on /help"""
    help_text = (
        "Here are some commands you can use:\n"
        "/start – Start the bot and get a welcome message\n"
        "/help – Show this help message\n"
        "If you enter an unrecognized command, I'll let you know."
    )
    await update.message.reply_text(help_text)

async def unknown(update: Update, context):
    """Respond to unknown commands"""
    await update.message.reply_text("❓ Sorry, I didn't understand that command.")

# Register handlers with the application
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
# Fallback for unknown commands – must be added *after* known commands
application.add_handler(MessageHandler(filters.COMMAND, unknown))

# Create Flask app and define routes
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health_check():
    """Health-check endpoint (optional)"""
    return "OK", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    """Webhook endpoint to receive updates from Telegram"""
    if request.headers.get("content-type") == "application/json":
        # Decode the incoming Update
        update = Update.de_json(request.get_json(force=True), application.bot)
        # Process the update within the application context (initialize & shutdown automatically) [oai_citation:3‡stackoverflow.com](https://stackoverflow.com/questions/75985888/telegram-bot-with-python-telegram-bot-v20-via-serverless-function#:~:text=%40app.route%28%27%2F%27%2C%20methods%3D,process_update%28update%29%20return%20%28%27%27%2C%20204%29%20else)
        async with application:
            await application.process_update(update)
        return "OK", 200  # Respond quickly with 200 to Telegram
    return "Unsupported Media Type", 415

if __name__ == "__main__":
    # Optional: Set the Telegram webhook on startup (one-time setup)
    if WEBHOOK_URL:
        import asyncio
        try:
            asyncio.run(application.bot.set_webhook(WEBHOOK_URL))
            logging.info(f"Webhook set to {WEBHOOK_URL}")
        except Exception as e:
            logging.error(f"Failed to set webhook: {e}")

    # Start Flask server (Render will provide the PORT environment variable)
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
