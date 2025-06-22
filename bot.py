# bot.py  – full module
import logging, os
from dotenv import load_dotenv

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import database
import timer, countdown, streak, study_tasks, doubts     # feature modules

# ─────────────── env / constants ───────────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")            # e.g. https://…render.com
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))

ADMIN_ID = 803299591                               # ← your Telegram ID

# ─────────────── logging ───────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────── command-menu shown in Telegram ───────────────
COMMAND_MENU = [
    BotCommand("start",          "Restart the bot"),
    BotCommand("help",           "Show help"),
    BotCommand("doubt",          "Raise a study doubt"),

    BotCommand("task_start",     "Stop-watch study task"),
    BotCommand("task_status",    "Task timer status"),
    BotCommand("task_pause",     "Pause task"),
    BotCommand("task_resume",    "Resume task"),
    BotCommand("task_stop",      "Stop & log task"),

    BotCommand("timer",          "Pomodoro timer"),
    BotCommand("timer_status",   "Pomodoro status"),
    BotCommand("timer_pause",    "Pause Pomodoro"),
    BotCommand("timer_resume",   "Resume Pomodoro"),
    BotCommand("timer_stop",     "Stop Pomodoro"),

    BotCommand("countdown",        "Event countdown"),
    BotCommand("countdownstatus",  "Countdown status"),
    BotCommand("countdownstop",    "Cancel countdown"),

    BotCommand("checkin",        "Daily study check-in"),
    BotCommand("mystreak",       "Show streak"),
    BotCommand("streak_alerts",  "Toggle streak alerts"),
]
KNOWN_CMDS = [c.command for c in COMMAND_MENU]

# ─────────────── helpers ───────────────
async def _set_menu(app: Application):
    """Runs once, right after PTB is up."""
    await app.bot.set_my_commands(COMMAND_MENU)

def build_app() -> Application:
    # PTB builder
    builder = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_set_menu)         # ← async callback, will be awaited
    )
    app = builder.build()

    # /start & /help
    async def _start(u, c):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help for commands."
        )

    async def _help(u, c):
        await u.message.reply_markdown(
            "*Quick guide*\n"
            "• `/doubt` – raise a study doubt\n"
            "• `/task_start Maths` – stopwatch task\n"
            "• `/timer` – Pomodoro presets\n"
            "• `/countdown 2025-12-31 23:59:59 New Year`\n"
            "• `/checkin`, `/mystreak` – streak tools\n"
            "Tap the command menu (⬇️) for everything."
        )

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # plug-in feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)          # starts hourly checker via job-queue
    study_tasks.register_handlers(app)
    doubts.register_handlers(app, 803299591)   # ← pass admin id here

    # unknown command fallback
    unknown_filter = filters.COMMAND & (~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})"))
    async def _unknown(u, c):
        await u.message.reply_text("❓ Unknown command – type /help.")
    app.add_handler(MessageHandler(unknown_filter, _unknown))

    return app

# ─────────────── main ───────────────
if __name__ == "__main__":
    database.init_db()

    application = build_app()
    webhook_url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook ▶ %s  (port %s)", webhook_url, PORT)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        stop_signals=None,        # Render stops the container itself
    )
