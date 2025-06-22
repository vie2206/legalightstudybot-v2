# bot.py
import logging
import os
from dotenv import load_dotenv

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import database
import timer
import countdown
import streak
import study_tasks
import doubts

# ────────── Environment & Logging ──────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))
# Your Telegram user ID to receive admin callbacks
ADMIN_ID     = int(os.getenv("ADMIN_ID", "803299591"))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger(__name__)

# ────────── Telegram Command Menu ──────────
COMMAND_MENU = [
    BotCommand("start",         "Restart the bot"),
    BotCommand("help",          "Show help message"),
    BotCommand("task_start",    "Start stopwatch study task"),
    BotCommand("task_status",   "Show task timer"),
    BotCommand("task_pause",    "Pause task"),
    BotCommand("task_resume",   "Resume task"),
    BotCommand("task_stop",     "Stop & log task"),
    BotCommand("timer",         "Start Pomodoro"),
    BotCommand("timer_status",  "Pomodoro status"),
    BotCommand("timer_pause",   "Pause Pomodoro"),
    BotCommand("timer_resume",  "Resume Pomodoro"),
    BotCommand("timer_stop",    "Stop Pomodoro"),
    BotCommand("countdown",        "Start live countdown"),
    BotCommand("countdownstatus",  "Countdown status"),
    BotCommand("countdownstop",    "Cancel countdown"),
    BotCommand("checkin",       "Record today’s check-in"),
    BotCommand("mystreak",      "Show study streak"),
    BotCommand("streak_alerts", "Toggle streak alerts"),
    BotCommand("doubt",         "Raise a study doubt"),  # newly added
]
KNOWN_CMDS = [c.command for c in COMMAND_MENU]

# ────────── Build Application ──────────
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
    async def _start(update, context):
        await update.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see commands."
        )
    async def _help(update, context):
        await update.message.reply_markdown(
            "*How to use the bot*\n"
            "• `/task_start MATHS` – begin stopwatch\n"
            "• `/timer` – pick a Pomodoro preset\n"
            "• `/countdown` – live event timer\n"
            "• `/checkin`, `/mystreak`, `/streak_alerts on`\n"
            "• `/doubt` – submit your question privately or publicly\n"
            "\nTap the menu (↓) for the full list."
        )

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # Plug-in modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)
    doubts.register_handlers(app, ADMIN_ID)

    # Unknown command fallback
    unknown_filter = filters.COMMAND & ~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})")
    async def _unknown(update, context):
        await update.message.reply_text("❓ Unknown command – type /help.")
    app.add_handler(MessageHandler(unknown_filter, _unknown))

    return app

# ────────── Main Entrypoint ──────────
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
        stop_signals=None,  # Render manages shutdown itself
    )
