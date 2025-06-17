# bot.py
import logging
import os
from dotenv import load_dotenv

from telegram.ext import (
    Application,
    CommandHandler,
)

# --- local modules ---
import database               # database.py → init_db()
import timer                  # timer.py → register_handlers(app)
import countdown              # countdown.py → register_handlers(app)
import streak                 # streak.py → register_handlers(app)
import study_tasks            # study_tasks.py → register_handlers(app)

# ─────────── env / logging ───────────
load_dotenv()
BOT_TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT    = os.getenv("WEBHOOK_URL")                # e.g. https://your-site.onrender.com
WEBHOOK_PATH    = "webhook"                               # a relative path
PORT            = int(os.getenv("PORT", 10000))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)
log = logging.getLogger(__name__)

# ─────────── build PTB application ───────────
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # Simple /start & /help
    async def start(update, context):
        await update.message.reply_markdown(
            "*Welcome to Legalight Study Bot!*  Use /help to see commands."
        )

    async def help_cmd(update, context):
        await update.message.reply_markdown(
            "*Available commands*\n"
            "• /task_start `<type>` – stopwatch study task\n"
            "• /task_status, /task_pause, /task_resume, /task_stop\n"
            "• /timer – classic Pomodoro (inline presets)\n"
            "• /countdown – live event timer\n"
            "• /checkin, /mystreak – streak tracking\n"
            "• /help – this message"
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # plug-in feature modules
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    study_tasks.register_handlers(app)

    # fallback for unknown commands
    async def unknown_cmd(update, context):
        await update.message.reply_text(
            "❓ Sorry, I didn't recognize that command. Use /help for a list."
        )
    app.add_handler(CommandHandler([], unknown_cmd))       # matches nothing specific

    return app

# ─────────── main entry ───────────
if __name__ == "__main__":
    # create DB tables if they don't exist
    database.init_db()

    app = build_app()

    full_webhook = f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}"
    log.info(
        "Starting webhook on port %s with path '/%s' → %s",
        PORT, WEBHOOK_PATH, full_webhook
    )

    # PTB spins up its own asyncio loop internally – no extra asyncio.run()!
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=full_webhook,
        # Render kills the process itself, so we disable graceful stop signals
        stop_signals=None,
    )
