# bot.py
import logging, os
from dotenv import load_dotenv

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,              # keep this
)

# ────────── constants ──────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")             # e.g. https://your-app.onrender.com
WEBHOOK_PATH = "webhook"                            # relative path for PTB
PORT         = int(os.getenv("PORT", 10000))
ADMIN_ID     = 803299591                           # your Telegram numeric-ID

# ────────── local feature modules ──────────
import database
import timer
import countdown
import streak
import study_tasks
import doubts

# ────────── logging ──────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ────────── Telegram command menu ──────────
COMMAND_MENU = [
    BotCommand("start",    "Restart the bot"),
    BotCommand("help",     "Show help message"),
    BotCommand("doubt",    "Ask a study doubt"),        # NEW
    BotCommand("task_start",  "Start stopwatch task"),
    BotCommand("task_status", "Show task timer"),
    BotCommand("task_pause",  "Pause task"),
    BotCommand("task_resume", "Resume task"),
    BotCommand("task_stop",   "Stop & log task"),
    BotCommand("timer",        "Start Pomodoro"),
    BotCommand("timer_status", "Pomodoro status"),
    BotCommand("timer_pause",  "Pause Pomodoro"),
    BotCommand("timer_resume", "Resume Pomodoro"),
    BotCommand("timer_stop",   "Stop Pomodoro"),
    BotCommand("countdown",       "Start live countdown"),
    BotCommand("countdownstatus", "Countdown status"),
    BotCommand("countdownstop",   "Cancel countdown"),
    BotCommand("checkin",       "Record today’s check-in"),
    BotCommand("mystreak",      "Show study streak"),
    BotCommand("streak_alerts", "Toggle streak alerts"),
]
KNOWN_CMDS = [c.command for c in COMMAND_MENU]

# ────────── helpers ──────────
async def _set_bot_menu(app: Application):
    await app.bot.set_my_commands(COMMAND_MENU)

# ────────── build PTB application ──────────
def build_app() -> Application:
    builder = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_set_bot_menu)
    )
    app: Application = builder.build()

    # ——— basic /start  /help ———
    async def _start(u, c):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see everything I can do."
        )

    async def _help(u, c):
        await u.message.reply_markdown(
            "*Quick guide*\n"
            "• `/doubt` – submit any question/doubt\n"
            "• `/task_start MATHS` – begin a stopwatch study task\n"
            "• `/timer` – choose a Pomodoro preset\n"
            "• `/countdown 2025-12-31 23:59:59 New Year`\n"
            "• `/checkin`, `/mystreak`, `/streak_alerts on`\n"
            "Tap the Telegram *Menu* (≡ / ⌨) for the full list."
        )

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # ——— plug-in feature modules ———
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)
    doubts.register_handlers(app)          # ← no ADMIN_ID arg

    # ——— fallback for unknown commands ———
    unknown_filter = filters.COMMAND & (~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})"))
    async def _unknown(u, c):
        await u.message.reply_text("❓ Unknown command – type /help.")
    app.add_handler(MessageHandler(unknown_filter, _unknown))

    return app

# ────────── main entry ──────────
if __name__ == "__main__":
    database.init_db()

    application = build_app()

    webhook_url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook → %s  (port %s)", webhook_url, PORT)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        stop_signals=None,   # Render stops the container itself
    )
