# bot.py  – main entry
import logging, os
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import database, timer, countdown, streak, study_tasks, doubts

# ────────── config ──────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))
ADMIN_ID     = 803299591                       # ← your Telegram user-ID

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger(__name__)

# ────────── Telegram command-menu ──────────
COMMAND_MENU = [
    BotCommand("start",            "Restart the bot"),
    BotCommand("help",             "Show help message"),

    # ⏱  Study-task stopwatch
    BotCommand("task_start",       "Start stopwatch study task"),
    BotCommand("task_status",      "Show task timer"),
    BotCommand("task_pause",       "Pause task"),
    BotCommand("task_resume",      "Resume task"),
    BotCommand("task_stop",        "Stop & log task"),

    # 🍅  Pomodoro
    BotCommand("timer",            "Start Pomodoro"),
    BotCommand("timer_status",     "Pomodoro status"),
    BotCommand("timer_pause",      "Pause Pomodoro"),
    BotCommand("timer_resume",     "Resume Pomodoro"),
    BotCommand("timer_stop",       "Stop Pomodoro"),

    # 📆  Countdown
    BotCommand("countdown",        "Start live countdown"),
    BotCommand("countdownstatus",  "Countdown status"),
    BotCommand("countdownstop",    "Cancel countdown"),

    # 🔥  Streaks
    BotCommand("checkin",          "Record today’s check-in"),
    BotCommand("mystreak",         "Show study streak"),
    BotCommand("streak_alerts",    "Toggle streak alerts"),

    # ❓  Doubts
    BotCommand("doubt",            "Ask a doubt"),        # NEW
    BotCommand("mydoubts",         "List my doubts"),     # NEW
]
KNOWN_CMDS = [c.command for c in COMMAND_MENU]

async def _set_menu(app): await app.bot.set_my_commands(COMMAND_MENU)

# ────────── build app ──────────
def build_app():
    builder = Application.builder().token(BOT_TOKEN).post_init(_set_menu)
    app = builder.build()

    # basic help
    async def _start(u,c): await u.message.reply_text("Hi – /help to start!")
    async def _help(u,c):  await u.message.reply_text("Use the slash-menu ⬇")
    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)
    doubts.register_handlers(app)

    async def _unk(u,c): await u.message.reply_text("❓ Unknown command.")
    app.add_handler(MessageHandler(filters.COMMAND & ~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})"),
                                   _unk))
    return app

# ────────── run ──────────
if __name__ == "__main__":
    database.init_db()
    app = build_app()
    app.run_webhook(
        listen="0.0.0.0", port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}",
        stop_signals=None,
    )
