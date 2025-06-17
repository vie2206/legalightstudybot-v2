import os
import logging
import asyncio

from telegram import BotCommand, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import countdown    # our countdown module
from dotenv import load_dotenv

# ——— Load env & logging ———
load_dotenv()
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # e.g. https://yourapp.onrender.com
PORT        = int(os.getenv("PORT", "10000"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL must be set")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ——— Core handlers ———
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "📚 *Commands:*\n"
        "/start — Restart bot\n"
        "/help — This message\n\n"
        "*Countdown*\n"
        "/countdown `<YYYY-MM-DD>` `[HH:MM:SS]` `<label>` `[--pin]`\n"
        "    Start a live countdown\n"
        "/countdown_status — Show remaining once\n"
        "/countdown_stop — Cancel live countdown\n"
    )

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Unknown command. Try /help."
    )

# ——— Main ———
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # core
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("help",        help_cmd))
    app.add_handler(MessageHandler(filters.COMMAND, fallback))

    # countdown module
    countdown.register_handlers(app)

    # initialize + start
    await app.initialize()
    await app.start()

    # set slash-commands
    cmds = [
        BotCommand("start",            "Restart the bot"),
        BotCommand("help",             "Show help"),
        BotCommand("countdown",        "Start live countdown"),
        BotCommand("countdown_status", "Show remaining once"),
        BotCommand("countdown_stop",   "Cancel countdown"),
    ]
    await app.bot.set_my_commands(cmds)
    logger.info("✅ Commands registered")

    # webhook
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL,
    )
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")

    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
