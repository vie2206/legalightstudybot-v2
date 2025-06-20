# bot.py
import logging, os
from dotenv import load_dotenv

from telegram import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllGroupChats,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

# ── local feature modules ──
import database, timer, countdown, streak, study_tasks, doubts

# ── env / constants ──
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))

ADMIN_ID     = 803299591            # ← your Telegram numeric ID

# ── logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ── command menu ──
COMMAND_MENU = [
    BotCommand("start",          "Restart the bot"),
    BotCommand("help",           "Show help"),
    BotCommand("task_start",     "Start stopwatch study task"),
    BotCommand("task_status",    "Show task timer"),
    BotCommand("task_pause",     "Pause task"),
    BotCommand("task_resume",    "Resume task"),
    BotCommand("task_stop",      "Stop & log task"),
    BotCommand("timer",          "Pomodoro wizard"),
    BotCommand("timer_status",   "Pomodoro status"),
    BotCommand("timer_pause",    "Pause Pomodoro"),
    BotCommand("timer_resume",   "Resume Pomodoro"),
    BotCommand("timer_stop",     "Stop Pomodoro"),
    BotCommand("countdown",        "Start live countdown"),
    BotCommand("countdownstatus",  "Countdown status"),
    BotCommand("countdownstop",    "Cancel countdown"),
    BotCommand("checkin",        "Daily check-in"),
    BotCommand("mystreak",       "Show streak"),
    BotCommand("streak_alerts",  "Toggle streak alerts"),
    BotCommand("doubt",          "Ask a doubt (quota)"),
    BotCommand("mydoubts",       "List / withdraw my doubts"),
]
KNOWN_CMDS = [c.command for c in COMMAND_MENU]

# ── helper: push menu after bot starts ──
async def _set_bot_menu(app: Application):
    # private chats
    await app.bot.set_my_commands(COMMAND_MENU, scope=BotCommandScopeDefault())
    # all group chats
    await app.bot.set_my_commands(COMMAND_MENU, scope=BotCommandScopeAllGroupChats())
    log.info("✅ setMyCommands pushed to all scopes")

# ── build PTB application ──
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
            "*Welcome to Legalight Study Bot!*\nUse /help to see commands."
        )

    async def _help(u, c):
        await u.message.reply_markdown(
            "*Quick guide*\n"
            "• `/task_start MATHS` – begin stopwatch\n"
            "• `/timer` – Pomodoro presets\n"
            "• `/countdown 2025-12-31 23:59:59 New Year`\n"
            "• `/doubt` – ask a doubt (quota applies)\n"
            "Tap the menu ↓ for everything."
        )

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)
    doubts.register_handlers(app)      # no ADMIN_ID arg needed

    # unknown commands → gentle reply
    unknown_f = filters.COMMAND & ~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})")
    async def _unknown(u, c): await u.message.reply_text("❓ Unknown command – try /help.")
    app.add_handler(MessageHandler(unknown_f, _unknown))

    return app

# ── main ──
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
        stop_signals=None,  # Render stops the container itself
    )
