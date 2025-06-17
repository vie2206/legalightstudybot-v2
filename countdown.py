# countdown.py
"""
Interactive live-countdown feature.

Workflow
========
  /countdown  →  wizard asks:
      1️⃣  Target date  (YYYY-MM-DD)    ⤵
      2️⃣  Target time  (HH:MM:SS) or “now” for 00:00:00
      3️⃣  Event label  (max 60 chars)
  ✅  Bot starts a background task that edits the message every minute.
  /countdownstatus – show remaining once
  /countdownstop   – cancel live countdown
"""

import asyncio
import datetime as dt
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ──────────────────────────────────────────────────────────────
ASK_DATE, ASK_TIME, ASK_LABEL = range(3)

# per-chat storage
count_meta: Dict[int, dict] = {}
count_tasks: Dict[int, asyncio.Task] = {}

# ──────────────────────────────────────────────────────────────
def _parse_date(s: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def _parse_time(s: str) -> dt.time | None:
    if s.lower() == "now":
        return dt.time(0, 0, 0)
    try:
        return dt.time.fromisoformat(s)
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────
async def cd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/countdown entry-point."""
    await update.message.reply_text("📅 Target *date*?  (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE


async def cd_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    d = _parse_date(update.message.text.strip())
    if not d:
        return await update.message.reply_text("❌ Invalid date. Try again (YYYY-MM-DD).") or ASK_DATE
    context.user_data["cd_date"] = d
    await update.message.reply_text("⏰ Target *time*?  (HH:MM:SS or `now` for 00:00:00)",
                                    parse_mode="Markdown")
    return ASK_TIME


async def cd_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    t = _parse_time(update.message.text.strip())
    if t is None:
        return await update.message.reply_text("❌ Invalid time. Try HH:MM:SS or `now`.") or ASK_TIME
    context.user_data["cd_time"] = t
    await update.message.reply_text("🏷  Event label? (e.g. *Exam day*)", parse_mode="Markdown")
    return ASK_LABEL


async def cd_label(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    label = update.message.text.strip()[:60]
    date = context.user_data["cd_date"]
    time_ = context.user_data["cd_time"]
    target = dt.datetime.combine(date, time_)
    chat_id = update.effective_chat.id

    # cancel previous
    task = count_tasks.pop(chat_id, None)
    if task:
        task.cancel()

    count_meta[chat_id] = meta = {
        "target": target,
        "label": label,
        "msg_id": None,
    }

    msg = await update.message.reply_text("⏳ Starting countdown…")
    meta["msg_id"] = msg.message_id
    _launch_countdown(chat_id, context)

    return ConversationHandler.END


async def cd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meta = count_meta.get(update.effective_chat.id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active countdown.")
    await _edit_countdown(update.effective_chat.id, context.bot)


async def cd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = count_tasks.pop(chat_id, None)
    if task:
        task.cancel()
    count_meta.pop(chat_id, None)
    await update.message.reply_text("🚫 Countdown cancelled.")


# ──────────────────────────────────────────────────────────────
async def _edit_countdown(chat_id: int, bot):
    meta = count_meta[chat_id]
    now = dt.datetime.utcnow()
    remaining = meta["target"] - now
    if remaining.total_seconds() <= 0:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=meta["msg_id"],
            text=f"🎉 {meta['label']} reached!",
        )
        return False  # done
    days = remaining.days
    hrs, rem = divmod(remaining.seconds, 3600)
    mins, secs = divmod(rem, 60)
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=meta["msg_id"],
        text=(
            f"⏳ *{meta['label']}*\n"
            f"{days}d {hrs}h {mins}m {secs}s remaining."
        ),
        parse_mode="Markdown",
    )
    return True


def _launch_countdown(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    async def loop():
        try:
            while await _edit_countdown(chat_id, context.bot):
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

    count_tasks[chat_id] = asyncio.create_task(loop())


# ──────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", cd_start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_label)],
        },
        fallbacks=[CommandHandler("cancel", cd_stop)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", cd_status))
    app.add_handler(CommandHandler("countdownstop",   cd_stop))
