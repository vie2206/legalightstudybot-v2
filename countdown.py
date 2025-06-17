# countdown.py
"""
Interactive live-countdown feature.

Flow
====
  /countdown ➜ wizard:
      1️⃣  date  (YYYY-MM-DD)
      2️⃣  time  (HH:MM:SS or “now” = 00:00:00)
      3️⃣  label (≤ 60 chars)
      4️⃣  Pin?  Yes / No   ← NEW
  ✅  Bot starts a background task that edits the message every second.

Extra commands
--------------
  /countdownstatus  – show remaining once
  /countdownstop    – cancel the live countdown
"""

import asyncio
import datetime as dt
from typing import Dict

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────── states
ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

# per-chat runtime storage
_meta:  Dict[int, dict]   = {}  # chat_id ➜ {target, label, msg_id}
_tasks: Dict[int, asyncio.Task] = {}

# ─────────────────────────────── parsers
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


# ─────────────────────────────── wizard handlers
async def cd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("📅 Target *date*? (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE


async def cd_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    d = _parse_date(update.message.text.strip())
    if not d:
        await update.message.reply_text("❌ Invalid date – try again (YYYY-MM-DD).")
        return ASK_DATE
    ctx.user_data["date"] = d
    await update.message.reply_text(
        "⏰ Target *time*? (HH:MM:SS or `now` = 00:00:00)",
        parse_mode="Markdown",
    )
    return ASK_TIME


async def cd_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    t = _parse_time(update.message.text.strip())
    if t is None:
        await update.message.reply_text("❌ Invalid time – try HH:MM:SS or `now`.")
        return ASK_TIME
    ctx.user_data["time"] = t
    await update.message.reply_text("🏷  Event *label*? (e.g. *Exam Day*)", parse_mode="Markdown")
    return ASK_LABEL


async def cd_label(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["label"] = update.message.text.strip()[:60]
    # ask whether to pin
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📌 Yes", callback_data="pin_yes"),
                InlineKeyboardButton("🚫 No",  callback_data="pin_no"),
            ]
        ]
    )
    await update.message.reply_text("Pin this countdown message?", reply_markup=kb)
    return ASK_PIN


async def pin_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pin_it = (query.data == "pin_yes")

    # assemble target dt
    target_dt = dt.datetime.combine(ctx.user_data["date"], ctx.user_data["time"])
    label = ctx.user_data["label"]
    chat_id = query.message.chat.id

    # cancel any previous countdown
    old_task = _tasks.pop(chat_id, None)
    if old_task:
        old_task.cancel()

    # send initial placeholder
    placeholder = await ctx.bot.send_message(chat_id, "⏳ Starting countdown…")
    if pin_it:
        try:
            await ctx.bot.pin_chat_message(
                chat_id=chat_id,
                message_id=placeholder.message_id,
                disable_notification=True,
            )
        except Exception:
            # no permission? silently ignore
            pass

    # store metadata & launch loop
    _meta[chat_id] = {"target": target_dt, "label": label, "msg_id": placeholder.message_id}
    _tasks[chat_id] = ctx.application.create_task(_loop(chat_id, ctx))
    await query.edit_message_text("✅ Countdown started!")
    return ConversationHandler.END


# ─────────────────────────────── support functions
async def _edit(chat_id: int, bot) -> bool:
    meta = _meta[chat_id]
    now  = dt.datetime.utcnow()
    remaining = meta["target"] - now
    if remaining.total_seconds() <= 0:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=meta["msg_id"],
            text=f"🎉 {meta['label']} reached!",
        )
        return False
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


async def _loop(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        while await _edit(chat_id, ctx.bot):
            await asyncio.sleep(1)      # update every *second*
    except asyncio.CancelledError:
        pass


# ─────────────────────────────── extra commands
async def cd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    meta = _meta.get(update.effective_chat.id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active countdown.")
    await _edit(update.effective_chat.id, ctx.bot)


async def cd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = _tasks.pop(chat_id, None)
    if task:
        task.cancel()
    _meta.pop(chat_id, None)
    await update.message.reply_text("🚫 Countdown cancelled.")


# ─────────────────────────────── registration helper
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", cd_start)],
        states={
            ASK_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cd_date)
            ],
            ASK_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cd_time)
            ],
            ASK_LABEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cd_label)
            ],
            ASK_PIN: [
                CallbackQueryHandler(pin_choice, pattern=r"^pin_(yes|no)$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cd_stop)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", cd_status))
    app.add_handler(CommandHandler("countdownstop",   cd_stop))
