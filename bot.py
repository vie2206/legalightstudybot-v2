# bot.py  ── main entry for Legalight Study Bot
# Requires: python-telegram-bot[webhooks] 20.x

import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ────────────────────────────────────────────────────────────────
# Environment / logging
# ────────────────────────────────────────────────────────────────
load_dotenv()
TOKEN        = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")        # e.g. https://legalightstudybot-docker.onrender.com
PORT         = int(os.getenv("PORT", "10000")) # Render exposes 10000

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────
# Import feature-modules
# ────────────────────────────────────────────────────────────────
import study_tasks    # /task_*
import timer          # /timer …
import countdown      # /countdown …
import streak         # /checkin …


# ────────────────────────────────────────────────────────────────
# Core commands
# ────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *Legalight Study Bot*!\nUse /help to see everything I can do.",
        parse_mode="Markdown",
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        """
*Available commands*

• `/task_start <type>` – start a stopwatch study task  
• `/task_status`, `/task_pause`, `/task_resume`, `/task_stop`  
• `/timer <name> <study> <break>` – classic Pomodoro  
• `/timer_status`, `/timer_pause`, `/timer_resume`, `/timer_stop`  
• `/countdown YYYY-MM-DD HH:MM:SS <event>` – live event countdown  
• `/checkin`, `/mystreak` – streak tracking  
• `/help` – this message
""",
        disable_web_page_preview=True,
    )


async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback for any unrecognised /command."""
    await update.message.reply_text("❓ Unknown command – use /help for the menu.")


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────
def main() -> None:
    app = Application.builder().token(TOKEN).build()

    # core handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))

    # feature-modules
    study_tasks.register_handlers(app)
    timer.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)

    # unknown commands last
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    # run via PTB’s built-in webhook server
    webhook_url = f"{WEBHOOK_ROOT}/webhook"
    log.info("Starting webhook on port %s as %s", PORT, webhook_url)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",         # relative path Telegram will hit
        webhook_url=webhook_url,    # full public HTTPS URL
    )


if __name__ == "__main__":
    main()
