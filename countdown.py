# countdown.py
"""
Live event-countdown wizard
  /countdown                → date → time → label → pin? → starts live edit
  /countdownstatus          → show remaining once
  /countdownstop            → cancel
"""

from __future__ import annotations
import asyncio, datetime as dt
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

ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

meta:  Dict[int, dict] = {}   # chat_id → {target,label,msg_id,pin}
tasks: Dict[int, asyncio.Task] = {}

# ───────────────────────── helpers
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


# ───────────────────────── wizard steps
async def start(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await u.message.reply_text("📅 Target *date*? (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE


async def got_date(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    d = _parse_date(u.message.text.strip())
    if not d:
        await u.message.reply_text("❌ Invalid date – use YYYY-MM-DD.")
        return ASK_DATE
    ctx.user_data["date"] = d
    await u.message.reply_text(
        "⏰ Target *time*? (HH:MM:SS or `now` for 00:00:00)",
        parse_mode="Markdown",
    )
    return ASK_TIME


async def got_time(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    t = _parse_time(u.message.text.strip())
    if t is None:
        await u.message.reply_text("❌ Invalid time – use HH:MM:SS or `now`.")
        return ASK_TIME
    ctx.user_data["time"] = t
    await u.message.reply_text("🏷  Event label? (max 60 chars)")
    return ASK_LABEL


async def got_label(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["label"] = u.message.text.strip()[:60]
    kb = [
        [
            InlineKeyboardButton("📌 Pin countdown", callback_data="pin|yes"),
            InlineKeyboardButton("No pin",          callback_data="pin|no"),
        ]
    ]
    await u.message.reply_text(
        "Pin the live countdown message?", reply_markup=InlineKeyboardMarkup(kb)
    )
    return ASK_PIN


async def pin_choice(q_upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = q_upd.callback_query
    await q.answer()
    _, yn = q.data.split("|", 1)
    pin = yn == "yes"

    d, t, label = (
        ctx.user_data["date"],
        ctx.user_data["time"],
        ctx.user_data["label"],
    )
    target = dt.datetime.combine(d, t)
    cid = q.message.chat.id

    # cancel previous
    if cid in tasks:
        tasks[cid].cancel()
        tasks.pop(cid, None)
        meta.pop(cid, None)

    m = await q.message.reply_text("⏳ Starting countdown…")
    if pin:
        await q.bot.pin_chat_message(cid, m.message_id, disable_notification=True)

    meta[cid] = {"target": target, "label": label, "msg_id": m.message_id}
    _launch(cid, ctx)
    return ConversationHandler.END


# ───────────────────────── live edit
async def _edit(cid: int, bot) -> bool:
    m = meta[cid]
    now = dt.datetime.utcnow()
    rem = m["target"] - now
    if rem.total_seconds() <= 0:
        await bot.edit_message_text(
            chat_id=cid, message_id=m["msg_id"], text=f"🎉 {m['label']} reached!"
        )
        return False
    days = rem.days
    hrs, r = divmod(rem.seconds, 3600)
    mins, secs = divmod(r, 60)
    txt = (
        f"⏳ *{m['label']}*\n"
        f"{days}d {hrs}h {mins}m {secs}s remaining."
    )
    await bot.edit_message_text(
        cid, m["msg_id"], text=txt, parse_mode="Markdown"
    )
    return True


def _launch(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    async def loop():
        try:
            while await _edit(cid, ctx.bot):
                await asyncio.sleep(2)   # live update every 2 s
        except asyncio.CancelledError:
            pass

    tasks[cid] = asyncio.create_task(loop())


# ───────────────────────── simple commands
async def status(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id not in meta:
        await u.message.reply_text("ℹ️ No active countdown.")
    else:
        await _edit(u.effective_chat.id, ctx.bot)


async def stop(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = u.effective_chat.id
    t = tasks.pop(cid, None)
    meta.pop(cid, None)
    if t:
        t.cancel()
    await u.message.reply_text("🚫 Countdown cancelled.")


# ───────────────────────── registration
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_label)],
            ASK_PIN:   [CallbackQueryHandler(pin_choice, pattern=r"^pin\|")],
        },
        fallbacks=[CommandHandler("cancel", stop)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", status))
    app.add_handler(CommandHandler("countdownstop",   stop))
