# bot.py  – final (2025-06-18)
import logging, os
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

# ─────────────── local feature modules ───────────────
import database
import timer
import countdown
import streak
import study_tasks

# ─────────────── env & logging ───────────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")          # e.g. https://legalightstudybot-docker.onrender.com
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────── Telegram menu (long list) ───────────────
COMMAND_MENU = [
    BotCommand("start",          "Restart the bot"),
    BotCommand("help",           "Show help message"),
    BotCommand("task_start",     "Stop-watch study task"),
    BotCommand("task_status",    "Show task timer"),
    BotCommand("task_pause",     "Pause task"),
    BotCommand("task_resume",    "Resume task"),
    BotCommand("task_stop",      "Stop & log task"),
    BotCommand("timer",          "Start Pomodoro"),
    BotCommand("timer_status",   "Pomodoro status"),
    BotCommand("timer_pause",    "Pause Pomodoro"),
    BotCommand("timer_resume",   "Resume Pomodoro"),
    BotCommand("timer_stop",     "Stop Pomodoro"),
    BotCommand("countdown",        "Start live countdown"),
    BotCommand("countdownstatus",  "Countdown status"),
    BotCommand("countdownstop",    "Cancel countdown"),
    BotCommand("checkin",        "Record today’s check-in"),
    BotCommand("mystreak",       "Show study streak"),
    BotCommand("streak_alerts",  "Toggle streak alerts"),
]

# ───────────────── build PTB application ─────────────────
def build_app() -> Application:
    # coroutine that sets the slash-command menu
    async def _set_bot_menu(app: Application):
        await app.bot.set_my_commands(COMMAND_MENU)

    builder = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_set_bot_menu)      # ← hand the coroutine itself
    )
    app = builder.build()

    # ── simple /start & /help ──
    async def start(u, c):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see commands."
        )

    async def help_(u, c):
        await u.message.reply_markdown(
            "*How to use the bot*\n"
            "• `/task_start MATHS` – begin stopwatch\n"
            "• `/timer` – pick a Pomodoro preset\n"
            "• `/countdown 2025-12-31 23:59:59 New Year`\n"
            "• `/checkin`, `/mystreak`, `/streak_alerts on`\n"
            "_Tap the command menu (▼) for everything else._"
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_))

    # ── register feature modules ──
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)

    # fallback: any unknown /command
    async def unknown(u, c):
        await u.message.reply_text("❓ Unknown command – try /help.")
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    return app

# ───────────────── main ─────────────────
if __name__ == "__main__":
    database.init_db()                       # ensure tables

    application = build_app()
    webhook_url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook → %s (port %s)", webhook_url, PORT)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        stop_signals=None,                  # Render stops the container itself
    )
