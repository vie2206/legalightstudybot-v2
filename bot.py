import logging, os
from dotenv import load_dotenv

from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters
)

# ── local feature modules ──
import database
import timer, countdown, streak, study_tasks

# ── env / logging ──
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")  # e.g. https://legalightstudybot-docker.onrender.com
PORT         = int(os.getenv("PORT", 10000))
WEBHOOK_PATH = "webhook"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger(__name__)

# ── build app ──
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    async def start(update, ctx):
        await update.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see commands."
        )

    async def help_cmd(update, ctx):
        await update.message.reply_markdown(
            "*Available commands*\n"
            "• `/task_start <type>` – stopwatch study task\n"
            "• `/task_status`, `/task_pause`, `/task_resume`, `/task_stop`\n"
            "• `/timer` – Pomodoro presets\n"
            "• `/countdown` – live event timer\n"
            "• `/checkin`, `/mystreak` – streak tracking\n"
            "• `/help` – this message",
            disable_web_page_preview=True,
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))

    # feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)

    # fallback for any *unknown* slash command
    async def unknown_cmd(update, ctx):
        await update.message.reply_text("❓ Unknown command. Use /help for a list.")
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    return app

# ── main ──
if __name__ == "__main__":
    database.init_db()

    app = build_app()
    full_webhook = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info("Starting webhook: %s → %s", WEBHOOK_PATH, full_webhook)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=full_webhook,
        stop_signals=None,     # Render handles SIGTERM itself
    )
