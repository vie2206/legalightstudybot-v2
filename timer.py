"""
timer.py  – Named Pomodoro with pause / resume
Compatible with python-telegram-bot 20.x async
"""

import datetime as dt
from typing import Dict, Optional

from telegram import Update, Message
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ContextTypes,
)

# --------------------------------------------------------------------- #
# In-memory state
# --------------------------------------------------------------------- #
class Session:
    def __init__(
        self,
        session: str,
        work_sec: int,
        break_sec: int,
        chat_id: int,
        msg_id: Optional[int] = None,
    ):
        self.session = session
        self.work_sec = work_sec
        self.break_sec = break_sec
        self.chat_id = chat_id
        self.msg_id = msg_id
        self.phase = "study"          # or "break"
        self.end_at = dt.datetime.utcnow() + dt.timedelta(seconds=work_sec)
        self.paused_remaining = None  # seconds

    def remaining(self) -> int:
        return max(0, int((self.end_at - dt.datetime.utcnow()).total_seconds()))


ACTIVE: Dict[int, Session] = {}  # keyed by chat_id

TICK = 5  # seconds between status edits


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #
def _format(sec: int) -> str:
    m, s = divmod(sec, 60)
    return f"{m}m {s}s"


async def _tick(context: CallbackContext) -> None:
    chat_id = context.job.chat_id
    ses = ACTIVE.get(chat_id)
    if not ses:
        return

    # Finished?
    if ses.remaining() == 0:
        if ses.phase == "study":
            # switch to break
            ses.phase = "break"
            ses.end_at = dt.datetime.utcnow() + dt.timedelta(seconds=ses.break_sec)
            await context.bot.send_message(
                chat_id, f"⏰ Study phase done! Break starts for {ses.break_sec//60}m"
            )
        else:
            await context.bot.send_message(
                chat_id,
                f"✅ Break over – '{ses.session}' Pomodoro complete!",
            )
            ACTIVE.pop(chat_id, None)
            return  # no re-queue

    # Still running – update or send message
    txt = (
        ("📚" if ses.phase == "study" else "☕")
        + f" {ses.phase.capitalize()} '{ses.session}': { _format(ses.remaining()) }"
    )
    try:
        if ses.msg_id:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=ses.msg_id, text=txt
            )
        else:
            m: Message = await context.bot.send_message(chat_id, txt)
            ses.msg_id = m.message_id
    except Exception:
        # message might be gone – send new
        m: Message = await context.bot.send_message(chat_id, txt)
        ses.msg_id = m.message_id

    # re-schedule
    context.job_queue.run_once(_tick, TICK, chat_id=chat_id)


# --------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------- #
async def timer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    if len(args) < 3:
        await update.message.reply_text(
            "❌ Usage: /timer <name> <study_min> <break_min>\n"
            "Example: /timer Maths 25 5"
        )
        return

    name = args[0]
    try:
        work = int(args[1])
        brk = int(args[2])
    except ValueError:
        await update.message.reply_text("Minutes must be whole numbers.")
        return

    # Clear any existing session
    ACTIVE.pop(chat_id, None)

    ses = Session(name, work * 60, brk * 60, chat_id)
    ACTIVE[chat_id] = ses

    await update.message.reply_text(
        f"🟢 Started '{name}': {work}m study → {brk}m break."
    )
    context.job_queue.run_once(_tick, 0, chat_id=chat_id)


async def timer_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ses = ACTIVE.get(chat_id)
    if not ses or ses.paused_remaining is not None:
        await update.message.reply_text("ℹ️ No running session to pause.")
        return

    ses.paused_remaining = ses.remaining()
    await update.message.reply_text(
        f"⏸️ Paused '{ses.session}' with {_format(ses.paused_remaining)} left."
    )


async def timer_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ses = ACTIVE.get(chat_id)
    if not ses or ses.paused_remaining is None:
        await update.message.reply_text("ℹ️ No paused session to resume.")
        return

    ses.end_at = dt.datetime.utcnow() + dt.timedelta(seconds=ses.paused_remaining)
    ses.paused_remaining = None
    await update.message.reply_text(
        f"▶️ Resumed '{ses.session}' – {_format(ses.remaining())} left."
    )
    context.job_queue.run_once(_tick, 0, chat_id=chat_id)


async def timer_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ACTIVE.pop(update.effective_chat.id, None):
        await update.message.reply_text("🚫 Session canceled.")
    else:
        await update.message.reply_text("ℹ️ No active session to cancel.")


async def timer_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ses = ACTIVE.get(update.effective_chat.id)
    if not ses:
        await update.message.reply_text("ℹ️ No session running.")
    else:
        await update.message.reply_text(
            ("📚" if ses.phase == "study" else "☕")
            + f" {ses.phase.capitalize()} '{ses.session}': {_format(ses.remaining())}"
        )


# --------------------------------------------------------------------- #
# Registration helper
# --------------------------------------------------------------------- #
def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("timer", timer_start))
    app.add_handler(CommandHandler("timer_pause", timer_pause))
    app.add_handler(CommandHandler("timer_resume", timer_resume))
    app.add_handler(CommandHandler("timer_status", timer_status))
    app.add_handler(CommandHandler("timer_stop", timer_stop))
