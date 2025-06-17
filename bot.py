# Project skeleton for LegalightStudyBot
# ======================================
# Main entrypoint: bot.py
import os
import logging
import asyncio
import timer
from flask import Flask, request
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

# Load environment
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Full URL to webhook (e.g. https://.../webhook)
if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set in environment")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask and Telegram Application
app = Flask(__name__)
bot_app = ApplicationBuilder().token(TOKEN).updater(None).build()

# Register slash commands at startup
def set_bot_commands():
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("help", "Show help info"),
        BotCommand("timer", "Start/cancel/check Pomodoro timer"),
        BotCommand("timer_stop", "Cancel a running Pomodoro"),
        BotCommand("timer_status", "Show remaining Pomodoro time"),
        # Add other commands here as features are implemented
    ]
    return bot_app.bot.set_my_commands(commands)

# Import feature modules
timer.register_handlers(bot_app)
# countdown.register_handlers(bot_app)
# quiz.register_handlers(bot_app)
# streaks.register_handlers(bot_app)
# badges.register_handlers(bot_app)
# summary.register_handlers(bot_app)
# reminders.register_handlers(bot_app)
# sheets.register_handlers(bot_app)
# admin.register_handlers(bot_app)
# settings.register_handlers(bot_app)
# autolog.register_handlers(bot_app)
# motivational.register_handlers(bot_app)

# Webhook endpoint
@app.post("/webhook")
async def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot_app.bot)
    async with bot_app:
        await bot_app.process_update(update)
    return "OK", 200

# Startup: set webhook and commands
async def on_startup():
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")
    await set_bot_commands()
    logger.info("Slash commands registered")

if __name__ == "__main__":
    # Initialize Telegram application and set up webhook/commands
    asyncio.run(on_startup())
    # Run Flask app
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
