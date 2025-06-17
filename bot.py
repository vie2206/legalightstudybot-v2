# bot.py  ───────────────────────────────────────────────────────────────
# Main entry point for Legalight Study Bot
# Compatible with python-telegram-bot 20.x

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

# local feature modules
import database
import timer
import countdown
import streak
import study_tasks

# ─────────────────────── env / logging ────────────────────────────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")           # e.g. https://your-app.onrender.com
WEBHOOK_PATH = "webhook"                          # do *not* include leading slash
PORT         = int(os.getenv("PORT", 10000))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────── slash-command menu ───────────────────────────
COMMAND_MENU = [
    # basics
    BotCommand("start",  "Restart the bot"),
    BotCommand("help",   "Show help"),
    # study-task stopwatch
    BotCommand("task_start",  "Start stopwatch task"),
    BotCommand("task_status", "Task status"),
    BotCommand("task_pause",  "Pause task"),
    BotCommand("task_resume", "Resume task"),
    BotCommand("task_stop",   "Stop & log task"),
    # classic pomodoro timer
    BotCommand("timer",        "Pomodoro presets"),
    BotCommand("timer_status", "Pomodoro status"),
    BotCommand("timer_pause",  "Pause Pomodoro"),
    BotCommand("timer_resume", "Resume Pomodoro"),
    BotCommand("timer_stop",   "Stop Pomodoro"),
    # countdown
    BotCommand("countdown",        "Start live countdown"),
    BotCommand("countdownstatus",  "Countdown status"),
    BotCommand("countdownstop",    "Cancel countdown"),
    # streaks
    BotCommand("checkin",      "Daily study check-in"),
    BotCommand("mystreak",     "Show streak"),
    BotCommand("streak_alerts","Toggle streak alerts"),
]

async def _set_bot_menu(app: Application):
    """Runs once on startup → pushes /menu to Telegram clients."""
    await app.bot.set_my_commands(COMMAND_MENU)

# ─────────────────────── app builder ──────────────────────────────────
def build_app() -> Application:
    builder = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_set_bot_menu)      # async hook after initialization
    )
    app = builder.build()

    # ------------ /start & /help ------------
    async def cmd_start(u, c):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to explore."
        )

    async def cmd_help(u, c):
        await u.message.reply_markdown(
            "*How to use the bot*\n"
            "• `/task_start` → pick a study task (inline)\n"
            "• `/timer` → choose a Pomodoro preset\n"
            "• `/countdown 2025-12-31 23:59:59 New Year`\n"
            "• `/checkin` & `/mystreak` for streaks\n\n"
            "Open the • Menu • button below for every command."
        )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))

    # ------------ plug-in feature modules ------------
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)

    # ------------ unknown command fallback ------------
    async def unknown_cmd(u, _):
        await u.message.reply_text("❓ Unknown command – type /help.")
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    return app

# ─────────────────────── main ─────────────────────────────────────────
if __name__ == "__main__":
    # ensure DB schema exists
    database.init_db()

    application = build_app()
    webhook_url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook → %s  (port %s)", webhook_url, PORT)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        stop_signals=None,     # Render kills the container itself
    )
