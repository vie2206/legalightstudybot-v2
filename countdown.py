# countdown.py  ✨ 2-Jun-2025
"""
Live, pinned countdown that updates every second until the target moment.

Workflow
--------
/countdown   → wizard asks date, time, label, pin? (yes/no)
/countdownstatus → show remaining once
/countdownstop   → cancel
"""
from __future__ import annotations
import asyncio, datetime as dt
from typing import Dict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

_meta: Dict[int, dict] = {}     # chat → {target, label, msg_id, pin}
_tasks: Dict[int, asyncio.Task] = {}

# ──────────────────────────────────────────────────────────────
def _parse_date(text: str) -> dt.date | None:
    try: return dt.date.fromisoformat(text)
    except ValueError: return None

def _parse_time(text: str) -> dt.time | None:
    if text.lower() == "now":  return dt.time(0, 0, 0)
    try: return dt.time.fromisoformat(text)
    except ValueError: return None

# ───────────────────── conversation steps ─────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE)->int:
    await update.message.reply_text("📅 Target *date*? (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE

async def step_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE)->int:
    d = _parse_date(update.message.text.strip())
    if not d:
        await update.message.reply_text("❌ Invalid date. Try YYYY-MM-DD.")
        return ASK_DATE
    ctx.user_data["date"] = d
    await update.message.reply_text(
        "⏰ Target *time*? (HH:MM:SS or `now`)", parse_mode="Markdown"
    )
    return ASK_TIME

async def step_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE)->int:
    t = _parse_time(update.message.text.strip())
    if t is None:
        await update.message.reply_text("❌ Invalid time. Try HH:MM:SS or `now`.")
        return ASK_TIME
    ctx.user_data["time"] = t
    await update.message.reply_text("🏷  Event label? (≤60 chars)", parse_mode="Markdown")
    return ASK_LABEL

async def step_label(update: Update, ctx: ContextTypes.DEFAULT_TYPE)->int:
    ctx.user_data["label"] = update.message.text.strip()[:60]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 Pin", callback_data="pin_yes"),
         InlineKeyboardButton("No thanks", callback_data="pin_no")]
    ])
    await update.message.reply_text("Pin this countdown at the top?", reply_markup=kb)
    return ASK_PIN

async def pin_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE)->int:
    q = update.callback_query
    await q.answer()
    pin = (q.data == "pin_yes")
    cid = q.message.chat.id

    # build target datetime (UTC-aware to avoid offsets)
    date: dt.date = ctx.user_data["date"]
    time_: dt.time = ctx.user_data["time"]
    target = dt.datetime.combine(date, time_).replace(tzinfo=dt.timezone.utc)

    # cancel older countdown in this chat
    if (t := _tasks.pop(cid, None)): t.cancel()

    _meta[cid] = meta = {
        "target": target,
        "label":  ctx.user_data["label"],
        "msg_id": None,
        "pin":    pin,
    }

    sent = await q.message.reply_text("⏳ Starting countdown…")
    meta["msg_id"] = sent.message_id
    if pin:
        try: await q.bot.pin_chat_message(cid, sent.message_id, disable_notification=True)
        except Exception: pass   # ignore “not enough rights”

    _tasks[cid] = asyncio.create_task(_ticker(cid, q.bot))
    return ConversationHandler.END

async def cancel(update: Update, ctx):   # fallback /cancel
    await update.message.reply_text("Countdown cancelled.")
    return ConversationHandler.END

# ───────────────────── helpers ─────────────────────
async def _edit(cid: int, bot) -> bool:
    meta = _meta[cid]
    remaining = meta["target"] - dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    if remaining.total_seconds() <= 0:
        await bot.edit_message_text(
            cid, meta["msg_id"], text=f"🎉 {meta['label']} reached!"
        )
        return False
    days = remaining.days
    hrs, rem = divmod(remaining.seconds, 3600)
    mins, secs = divmod(rem, 60)
    txt = (
        f"⏳ *{meta['label']}*\n"
        f"{days}d {hrs}h {mins}m {secs}s remaining."
    )
    try:
        await bot.edit_message_text(cid, meta["msg_id"], txt, parse_mode="Markdown")
    except Exception:   # network glitch, chat moved, etc.
        return True     # keep trying
    return True

async def _ticker(cid: int, bot):
    """Background loop that refreshes every second, resilient to errors."""
    try:
        while True:
            ok = await _edit(cid, bot)
            if not ok: break
            await asyncio.sleep(1)
    finally:
        _tasks.pop(cid, None)
        _meta.pop(cid,  None)

# ───────────────────── public cmd handlers ─────────────────────
async def status(update: Update, ctx):
    meta = _meta.get(update.effective_chat.id)
    if not meta: return await update.message.reply_text("ℹ️ No active countdown.")
    await _edit(update.effective_chat.id, ctx.bot)

async def stop(update: Update, ctx):
    cid = update.effective_chat.id
    if (t := _tasks.pop(cid, None)): t.cancel()
    _meta.pop(cid, None)
    await update.message.reply_text("🚫 Countdown cancelled.")

# ───────────────────── registrar ─────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, step_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, step_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_label)],
            ASK_PIN:   [CallbackQueryHandler(pin_choice, pattern="^pin_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", status))
    app.add_handler(CommandHandler("countdownstop",   stop))
