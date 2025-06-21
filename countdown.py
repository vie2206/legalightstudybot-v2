# countdown.py
"""
Interactive live-countdown feature.

Workflow
========
  /countdown  →  wizard asks:
      1️⃣  Target date  (YYYY-MM-DD)    ⤵
      2️⃣  Target time  (HH:MM:SS or now)
      3️⃣  Event label  (max 60 chars)
      4️⃣  Pin?  Yes / No
  ✅  Bot edits the message every 2 s to act like a live clock.
  /countdownstatus – show remaining once
  /countdownstop   – cancel
"""
from __future__ import annotations

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
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────
ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

meta:  Dict[int, dict]       = {}   # chat_id → {target, label, msg_id}
tasks: Dict[int, asyncio.Task] = {}  # chat_id → asyncio.Task

# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# Conversation steps
async def cd_start(u: Update, _) -> int:
    await u.message.reply_text("📅 Enter *date* (YYYY-MM-DD):", parse_mode="Markdown")
    return ASK_DATE


async def cd_date(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    d = _parse_date(u.message.text.strip())
    if not d:
        await u.message.reply_text("❌ Invalid date. Try again.")
        return ASK_DATE
    ctx.user_data["date"] = d
    await u.message.reply_text("⏰ Enter *time* (HH:MM:SS or `now`):", parse_mode="Markdown")
    return ASK_TIME


async def cd_time(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    t = _parse_time(u.message.text.strip())
    if t is None:
        await u.message.reply_text("❌ Invalid time. Try again.")
        return ASK_TIME
    ctx.user_data["time"] = t
    await u.message.reply_text("🏷  Enter a short *label* (≤ 60 chars):", parse_mode="Markdown")
    return ASK_LABEL


async def cd_label(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["label"] = u.message.text.strip()[:60]
    kb = InlineKeyboardMarkup.from_row(
        [InlineKeyboardButton("📌 Pin", callback_data="pin"),
         InlineKeyboardButton("Skip",  callback_data="nopin")]
    )
    await u.message.reply_text("Do you want me to pin the countdown message?", reply_markup=kb)
    return ASK_PIN


async def pin_choice(q_upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = q_upd.callback_query
    await q.answer()
    pin = q.data == "pin"

    # Assemble metadata
    date:  dt.date = ctx.user_data["date"]
    time_: dt.time = ctx.user_data["time"]
    label: str     = ctx.user_data["label"]
    target = dt.datetime.combine(date, time_)

    cid = q.message.chat.id

    # cancel any previous
    old = tasks.pop(cid, None)
    if old:
        old.cancel()

    # send initial message
    msg = await q.message.reply_text("⏳ Starting countdown…")
    if pin:
        try:
            await q.message.bot.pin_chat_message(
                cid, msg.message_id, disable_notification=True
            )
        except Exception:
            pass  # ignore pin errors (e.g. no rights)

    meta[cid] = {"target": target, "label": label, "msg_id": msg.message_id}
    _launch(cid, ctx)

    return ConversationHandler.END


async def cd_status(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id not in meta:
        return await u.message.reply_text("ℹ️ No active countdown.")
    await _edit(u.effective_chat.id, ctx.bot)


async def cd_stop(u: Update, _):
    cid = u.effective_chat.id
    t = tasks.pop(cid, None)
    if t:
        t.cancel()
    meta.pop(cid, None)
    await u.message.reply_text("🚫 Countdown cancelled.")


# ─────────────────────────────────────────────
# Live-update helpers
async def _edit(cid: int, bot) -> bool:
    m = meta[cid]
    rem = m["target"] - dt.datetime.utcnow()
    if rem.total_seconds() <= 0:
        txt = f"🎉 {m['label']} reached!"
        await bot.edit_message_text(cid, m["msg_id"], text=txt)
        return False

    days = rem.days
    hrs, rems = divmod(rem.seconds, 3600)
    mins, secs = divmod(rems, 60)
    txt = (
        f"⏳ *{m['label']}*\n"
        f"{days}d {hrs}h {mins}m {secs}s remaining."
    )
    await bot.edit_message_text(cid, m["msg_id"], text=txt, parse_mode="Markdown")
    return True


def _launch(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    async def loop():
        try:
            while await _edit(cid, ctx.bot):
                await asyncio.sleep(2)   # ← 2-second refresh
        except asyncio.CancelledError:
            pass

    tasks[cid] = asyncio.create_task(loop())


# ─────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", cd_start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_label)],
            ASK_PIN:   [CallbackQueryHandler(pin_choice, pattern="^(pin|nopin)$")],
        },
        fallbacks=[CommandHandler("cancel", cd_stop)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", cd_status))
    app.add_handler(CommandHandler("countdownstop", cd_stop))
