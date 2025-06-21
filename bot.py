# bot.py  – hub-style interface
import logging, os
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters
)

# ── local feature modules ───────────────────────────────────
import database
import timer, study_tasks, countdown, streak, doubts

# ── env / logging ───────────────────────────────────────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))
ADMIN_ID     = 803299591                       # ← your Telegram id

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger(__name__)

# ── visible command menu (≤ 12) ────────────────────────────
COMMAND_MENU = [
    BotCommand("start",      "Restart the bot"),
    BotCommand("help",       "How to use the bot"),
    BotCommand("doubt",      "Submit a doubt"),
    BotCommand("task",       "Start stopwatch task"),
    BotCommand("timer",      "Pomodoro timer"),
    BotCommand("countdown",  "Live event countdown"),
    BotCommand("checkin",    "Log today’s study"),
    BotCommand("mystreak",   "Show your streak"),
]

KNOWN = {c.command for c in COMMAND_MENU}

async def _set_menu(app: Application):      # runs post-init
    await app.bot.set_my_commands(COMMAND_MENU)

# ── build PTB application ──────────────────────────────────
def build_app() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_set_menu)
        .build()
    )

    # /start  /help
    async def _start(u, c):
        await u.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see commands."
        )

    async def _help(u, c):
        await u.message.reply_markdown(
            "*Quick guide*\n"
            "• `/task` – pick a subject & stopwatch starts (buttons to pause/stop)\n"
            "• `/timer` – choose a Pomodoro preset (buttons to pause/resume)\n"
            "• `/countdown` – 3-step wizard, then live pinned timer\n"
            "• `/doubt` – send a doubt with subject & nature\n"
            "• `/checkin` – mark today studied, `/mystreak` to view streak."
        )

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help",  _help))

    # plug-in modules
    timer.register_handlers(app)
    study_tasks.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    doubts.register_handlers(app, ADMIN_ID)

    # fallback – any unknown /
    unknown = filters.COMMAND & (~filters.Regex(rf"^/({'|'.join(KNOWN)})"))
    async def _unk(u, c):
        await u.message.reply_text("❓ Unknown command – try /help.")
    app.add_handler(MessageHandler(unknown, _unk))

    return app

# ── main ───────────────────────────────────────────────────
if __name__ == "__main__":
    database.init_db()
    application = build_app()

    url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Webhook → %s  (port %s)", url, PORT)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=url,
        stop_signals=None,     # Render stops container itself
    )
