# bot.py  – main entry-point
import asyncio, os, logging
from dotenv import load_dotenv
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters
)

# ───────────────────────── local modules
from database      import init_db
import study_tasks, timer, countdown, streak  # each has register_handlers(app)

load_dotenv()
TOKEN        = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")           # e.g. https://legalightstudybot-docker.onrender.com
WEBHOOK_PATH = "webhook"                          # trailing part
PORT         = int(os.getenv("PORT", 10000))

logging.basicConfig(
    format="%(levelname)s:%(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

# ───────────────────────── general commands
HELP_TXT = (
    "*Available commands*\n\n"
    "• `/task_start <type>` – start a stopwatch study task\n"
    "• `/task_status`, `/task_pause`, `/task_resume`, `/task_stop`\n\n"
    "• `/timer` – pick a Pomodoro preset or custom length\n"
    "• `/timer_status`, `/timer_pause`, `/timer_resume`, `/timer_stop`\n\n"
    "• `/countdown YYYY-MM-DD HH:MM:SS <event>` – live event countdown\n"
    "• `/checkin`, `/mystreak` – streak tracking\n"
    "• `/help` – this message\n\n"
    "_Task types_: `CLAT_MOCK`, `SECTIONAL`, `NEWSPAPER`, `EDITORIAL`, "
    "`GK_CA`, `MATHS`, `LEGAL_REASONING`, `LOGICAL_REASONING`, "
    "`CLATOPEDIA`, `SELF_STUDY`, `ENGLISH`, `STUDY_TASK`"
)

async def start(update, context):
    await update.message.reply_text(
        "👋 *Welcome to Legalight Study Bot!*\n"
        "Use /help to see everything I can do.",
        parse_mode="Markdown",
    )

async def help_cmd(update, context):
    await update.message.reply_markdown(HELP_TXT)

async def unknown_cmd(update, context):           # fallback for typos
    await update.message.reply_text(
        "❓ Sorry, I didn't recognize that command. Use /help to see what I can do."
    )

# ───────────────────────── assemble application
def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()

    # core commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    # feature modules
    study_tasks.register_handlers(app)
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)

    return app

# ───────────────────────── main entry
def main():
    init_db()                                     # ensure tables exist
    app = build_app()

    webhook_url = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Starting webhook on port %s with path '/%s' → %s",
             PORT, WEBHOOK_PATH, webhook_url)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        stop_signals=None,        # Render kills the process; no SIGINT
    )

# ─────────────────────────
if __name__ == "__main__":
    asyncio.run(asyncio.to_thread(main))
