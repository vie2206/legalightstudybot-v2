# bot.py
import logging, os
from dotenv import load_dotenv

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import database, timer, countdown, streak, study_tasks, doubts

load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))

# ← Add your Telegram user ID here:
ADMIN_ID = 803299591

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger(__name__)

COMMAND_MENU = [
    BotCommand("start",          "Restart the bot"),
    BotCommand("help",           "Show help message"),
    BotCommand("doubt",          "Raise a doubt (private→public)"),
    # … all your other commands …
]

KNOWN_CMDS = [c.command for c in COMMAND_MENU]

async def _set_bot_menu(app: Application):
    await app.bot.set_my_commands(COMMAND_MENU)

def build_app() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_set_bot_menu)
        .build()
    )

    # /start & /help
    async def _start(u, c):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see commands."
        )
    async def _help(u, c):
        await u.message.reply_markdown(
            "*How to use the bot*\n"
            "• `/doubt` – raise a question\n"
            "• Tap Menu ↓ for the full list."
        )
    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)
    doubts.register_handlers(app, ADMIN_ID)    # ← pass the admin ID here

    # unknown🔸fallback
    unknown_filter = filters.COMMAND & (~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})"))
    async def _unknown(u, c):
        await u.message.reply_text("❓ Unknown command – type /help.")
    app.add_handler(MessageHandler(unknown_filter, _unknown))

    return app

if __name__ == "__main__":
    database.init_db()
    application = build_app()
    webhook_url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook → %s (port %s)", webhook_url, PORT)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        stop_signals=None,
    )
