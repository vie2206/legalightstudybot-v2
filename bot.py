# bot.py
import asyncio
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

# ─────────── local feature modules ───────────
import database          # database.py  -> init_db()
import timer             # timer.py     -> register_handlers(app)
import countdown         # countdown.py -> register_handlers(app)
import streak            # streak.py    -> register_handlers(app)
import study_tasks       # study_tasks.py -> register_handlers(app)

# ─────────── env / logging ───────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")              # e.g. https://…render.com
WEBHOOK_PATH = "webhook"                             # relative path
PORT         = int(os.getenv("PORT", 10000))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)
log = logging.getLogger(__name__)


# ─────────── BUILD APPLICATION ───────────
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # ── basic /start and /help ────────────────────────────────────────────
    async def start(update, ctx):
        await update.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*\n"
            "Use /help to see commands."
        )

    async def help_cmd(update, ctx):
        await update.message.reply_markdown(
            "*How to use Legalight Study Bot*\n\n"
            "• `/task_start MATHS` – begin a stopwatch for Maths revision.\n"
            "  `/task_pause`, `/task_resume`, `/task_stop` control it.\n\n"
            "• `/timer` – tap a preset (25 | 5, 50 | 10) or choose *Custom*.\n"
            "  `/timer_status` shows remaining time.\n\n"
            "• `/countdown 2025-12-31 23:59:59 New Year` – start a live timer.\n\n"
            "• `/checkin` records today, `/mystreak` shows your streak.\n"
            "  `/streak_alerts on` – DM if you miss a day.\n\n"
            "Type `/help` anytime to see this again.",
            disable_web_page_preview=True,
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))

    # ── plug-in feature modules ───────────────────────────────────────────
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)

    # ── fallback: unknown commands ────────────────────────────────────────
    async def unknown_cmd(update, ctx):
        await update.message.reply_text(
            "❓ Sorry, I didn't recognize that command.  Use /help to see the list."
        )
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    # ── command-menu for Telegram “Menu” button ───────────────────────────
    commands = [
        BotCommand("start",          "Restart the bot"),
        BotCommand("help",           "Show help message"),

        BotCommand("task_start",     "Start a stopwatch study task"),
        BotCommand("task_status",    "Show task timer"),
        BotCommand("task_pause",     "Pause the task"),
        BotCommand("task_resume",    "Resume the task"),
        BotCommand("task_stop",      "Stop & log the task"),

        BotCommand("timer",          "Start a Pomodoro session"),
        BotCommand("timer_status",   "Pomodoro status"),
        BotCommand("timer_pause",    "Pause Pomodoro"),
        BotCommand("timer_resume",   "Resume Pomodoro"),
        BotCommand("timer_stop",     "Stop Pomodoro"),

        BotCommand("countdown",        "Start a live countdown"),
        BotCommand("countdownstatus",  "Countdown status"),
        BotCommand("countdownstop",    "Cancel countdown"),

        BotCommand("checkin",        "Record today's check-in"),
        BotCommand("mystreak",       "Show your study streak"),
        BotCommand("streak_alerts",  "Toggle streak-break alerts"),
    ]

    async def post_init(app: Application):
        await app.bot.set_my_commands(commands)
    app.post_init(post_init)

    return app


# ─────────── MAIN ENTRY ───────────
if __name__ == "__main__":
    # ensure DB tables exist
    database.init_db()

    application = build_app()

    full_webhook = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info(
        "Starting webhook on port %s with path '/%s' → %s",
        PORT, WEBHOOK_PATH, full_webhook
    )

    # PTB handles its own asyncio loop
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=full_webhook,
        stop_signals=None,            # Render kills container itself
    )
