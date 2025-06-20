# bot.py  – full module
import logging, os, asyncio
from dotenv import load_dotenv

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

# ────────── local modules ──────────
import database
import timer
import countdown
import streak
import study_tasks
import doubts

# ────────── env / logging ──────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")       # e.g. https://legalight…render.com
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ────────── Telegram command-menu ──────────
COMMAND_MENU = [
    BotCommand("start",           "Restart the bot"),
    BotCommand("help",            "Show help message"),

    # study task
    BotCommand("task_start",      "Start stopwatch study task"),
    BotCommand("task_status",     "Show task timer"),
    BotCommand("task_pause",      "Pause task"),
    BotCommand("task_resume",     "Resume task"),
    BotCommand("task_stop",       "Stop & log task"),

    # Pomodoro
    BotCommand("timer",           "Start Pomodoro"),
    BotCommand("timer_status",    "Pomodoro status"),
    BotCommand("timer_pause",     "Pause Pomodoro"),
    BotCommand("timer_resume",    "Resume Pomodoro"),
    BotCommand("timer_stop",      "Stop Pomodoro"),

    # Countdown
    BotCommand("countdown",       "Start live countdown"),
    BotCommand("countdownstatus", "Countdown status"),
    BotCommand("countdownstop",   "Cancel countdown"),

    # Streaks
    BotCommand("checkin",         "Record today’s check-in"),
    BotCommand("mystreak",        "Show study streak"),
    BotCommand("streak_alerts",   "Toggle streak alerts"),

    # Doubts  ← NEW
    BotCommand("doubt",           "Ask a doubt"),
    BotCommand("mydoubts",        "List my doubts"),
]
KNOWN_CMDS = [c.command for c in COMMAND_MENU]

# ────────── helpers ──────────
async def _push_menu(app):
    """(Re)send the command list to Telegram."""
    try:
        await app.bot.set_my_commands(COMMAND_MENU)
    except Exception as e:
        log.warning("Could not set command menu: %s", e)

# ────────── build PTB application ──────────
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # /start & /help ---------------------------------------------------
    async def start(u, c):
        # ensure menu is present for every user who presses /start
        asyncio.create_task(_push_menu(c.application))

        await u.message.reply_markdown(
            "👋 *Welcome to Legalight Study Bot!*\n"
            "Use /help to see everything I can do."
        )

    async def help_cmd(u, c):
        await u.message.reply_markdown(
            "*Quick guide*\n"
            "• `/task_start MATHS` – begin stopwatch\n"
            "• `/timer` – pick a Pomodoro preset\n"
            "• `/countdown 2025-12-31 23:59:59 New Year`\n"
            "• `/checkin`, `/mystreak`, `/streak_alerts on`\n"
            "• `/doubt` – ask a study doubt\n"
            "Tap the *Menu* (📋) for the full list."
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))

    # feature modules --------------------------------------------------
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)
    doubts.register_handlers(app)

    # unknown commands -------------------------------------------------
    bad = filters.COMMAND & (~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})"))
    async def unknown(u, c):
        await u.message.reply_text("❓ Unknown command – type /help.")
    app.add_handler(MessageHandler(bad, unknown))

    # push menu once when bot starts
    app.post_init(_push_menu)

    return app

# ────────── main entry ──────────
if __name__ == "__main__":
    database.init_db()

    application = build_app()
    full_hook = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook → %s  (port %s)", full_hook, PORT)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=full_hook,
        stop_signals=None,     # Render stops container itself
    )
