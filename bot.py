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

# ────────── local feature modules ──────────
import database
import timer
import countdown
import streak
import study_tasks
import doubts                    # new two-step doubt system

# ────────── config / environment ──────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")          # e.g. https://legalightstudybot.onrender.com
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))

# Your Telegram user-id → receives all doubt notifications
ADMIN_ID = 803299591

# ────────── logging ──────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ────────── command menu pushed to Telegram clients ──────────
COMMAND_MENU = [
    BotCommand("start",            "Restart the bot"),
    BotCommand("help",             "Show help message"),
    BotCommand("task_start",       "Start stopwatch task"),
    BotCommand("task_status",      "Show task timer"),
    BotCommand("task_pause",       "Pause task"),
    BotCommand("task_resume",      "Resume task"),
    BotCommand("task_stop",        "Stop & log task"),
    BotCommand("timer",            "Pomodoro presets"),
    BotCommand("timer_status",     "Pomodoro status"),
    BotCommand("timer_pause",      "Pause Pomodoro"),
    BotCommand("timer_resume",     "Resume Pomodoro"),
    BotCommand("timer_stop",       "Stop Pomodoro"),
    BotCommand("countdown",        "Start live countdown"),
    BotCommand("countdownstatus",  "Countdown status"),
    BotCommand("countdownstop",    "Cancel countdown"),
    BotCommand("checkin",          "Record today’s study"),
    BotCommand("mystreak",         "Show study streak"),
    BotCommand("streak_alerts",    "Toggle streak alerts"),
    BotCommand("doubt",            "Raise a study doubt"),   # ← new
]
KNOWN_CMDS = [c.command for c in COMMAND_MENU]

async def _set_bot_menu(app: Application):
    """Runs once at startup – pushes slash-command menu to Telegram clients."""
    await app.bot.set_my_commands(COMMAND_MENU)

# ────────── build the PTB Application ──────────
def build_app() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_set_bot_menu)          # push menu after login
        .build()
    )

    # basic /start & /help
    async def _start(u, _):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see everything I can do."
        )

    async def _help(u, _):
        await u.message.reply_markdown(
            "*Quick guide*\n"
            "• `/task_start MATHS` – stopwatch task\n"
            "• `/timer` – choose a Pomodoro preset\n"
            "• `/countdown 2025-12-31 23:59:59 Exam Day`\n"
            "• Raise questions with `/doubt`\n"
            "Tap the menu button ↓ for the full list."
        )

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # plug-in feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)
    doubts.register_handlers(app, ADMIN_ID)      # ← pass admin-id

    # fallback for unknown commands
    unknown_filter = filters.COMMAND & (~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})"))
    async def _unknown(u, _):
        await u.message.reply_text("❓ Unknown command – type /help.")

    app.add_handler(MessageHandler(unknown_filter, _unknown))
    return app

# ────────── main entry point ──────────
if __name__ == "__main__":
    # ensure DB tables exist
    database.init_db()

    application = build_app()
    webhook_url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook → %s  (port %s)", webhook_url, PORT)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        stop_signals=None,      # Render kills the container itself
    )
