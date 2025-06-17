# bot.py  – Legalight Study Bot (command-menu fix)
import logging, os, asyncio
from functools import partial
from dotenv import load_dotenv
from telegram import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import database, timer, countdown, streak, study_tasks

# ─── env / logging ───────────────────────────────────────────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")          # e.g. https://…render.com
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger(__name__)

# ─── command menu we want Telegram to show ───────────────────────
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

# ─── helpers to push the menu after the bot is ready ─────────────
async def _do_set_menu(app: Application):
    """Actually call set_my_commands for all scopes."""
    await app.bot.set_my_commands(COMMAND_MENU)  # default scope
    # ensure users in private & group chats also see it:
    await app.bot.set_my_commands(COMMAND_MENU, scope=BotCommandScopeAllPrivateChats())
    await app.bot.set_my_commands(COMMAND_MENU, scope=BotCommandScopeAllGroupChats())
    log.info("✅ Command menu set")

def _post_init_sync(app: Application):
    """Non-async wrapper that schedules the async _do_set_menu."""
    asyncio.create_task(_do_set_menu(app))

# ─── build PTB application ───────────────────────────────────────
def build_app() -> Application:
    builder = (Application.builder()
               .token(BOT_TOKEN)
               .post_init(_post_init_sync))     # <-- sync wrapper
    app = builder.build()

    # /start and /help
    async def start(u, c):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*\nUse /help to see commands."
        )
    async def help_(u, c):
        await u.message.reply_markdown(
            "*How to use the bot*\n"
            "• `/task_start MATHS` – begin stopwatch\n"
            "• `/timer` – pick a Pomodoro preset\n"
            "• `/countdown 2025-12-31 23:59:59 New Year`  \n"
            "• `/checkin`, `/mystreak`, `/streak_alerts on`\n"
            "Tap the menu button (📋) for the full list."
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_))

    # feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)

    # fallback for unknown commands
    async def unknown(u, c):
        await u.message.reply_text("❓ Unknown command – try /help.")
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    return app

# ─── main ────────────────────────────────────────────────────────
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
