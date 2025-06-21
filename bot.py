# bot.py  – central launcher
import logging, os
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import database, timer, countdown, streak, study_tasks, doubts

load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
WEBHOOK_ROOT = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "webhook"
PORT         = int(os.getenv("PORT", 10000))
ADMIN_ID     = int(os.getenv("ADMIN_ID", "803299591"))

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")
log=logging.getLogger(__name__)

COMMAND_MENU=[BotCommand("start","Restart"),BotCommand("help","Help"),
              BotCommand("timer","Pomodoro"),BotCommand("task_start","Stopwatch"),
              BotCommand("countdown","Live countdown"),BotCommand("doubt","Ask doubt")]
KNOWN=[c.command for c in COMMAND_MENU]

async def _set_menu(app): await app.bot.set_my_commands(COMMAND_MENU)

def build_app():
    app=(Application.builder().token(BOT_TOKEN).post_init(_set_menu).build())
    async def _start(u,c): await u.message.reply_text("Welcome to *Legalight Study Bot* 🎓",
                                                     parse_mode="Markdown")
    async def _help(u,c): await u.message.reply_text("Use the menu commands below.")
    app.add_handler(CommandHandler("start",_start))
    app.add_handler(CommandHandler("help", _help))

    timer.register_handlers(app)
    study_tasks.register_handlers(app)
    countdown.register_handlers(app)
    streak.register_handlers(app)
    doubts.register_handlers(app)

    async def _unknown(u,c): await u.message.reply_text("❓ Unknown command.")
    app.add_handler(MessageHandler(filters.COMMAND & ~filters.Regex(rf"^/({'|'.join(KNOWN)})"), _unknown))
    return app

if __name__=="__main__":
    database.init_db()
    app=build_app()
    app.run_webhook(listen="0.0.0.0", port=PORT,
                    url_path=WEBHOOK_PATH,
                    webhook_url=f"{WEBHOOK_ROOT}/{WEBHOOK_PATH}",
                    stop_signals=None)
