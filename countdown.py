"""
Live event countdown with optional pin.

Workflow
========
  /countdown  → wizard asks
      1️⃣  Date  (YYYY-MM-DD)
      2️⃣  Time  (HH:MM:SS or “now” = 00:00:00)
      3️⃣  Label (≤ 60 chars)
      4️⃣  Pin?  (Yes / No)

The bot edits a single message every second until the deadline.
Commands
--------
/countdownstatus   – show remaining once
/countdownstop     – cancel the active countdown
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

# ──────────────────────────────────────────────────────────────
ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

meta:  Dict[int, dict]      = {}     # chat_id → {target,label,msg_id}
tasks: Dict[int, asyncio.Task] = {}  # chat_id → background asyncio.Task

# ──────────────────────────────────────────────────────────────
def _parse_date(txt: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(txt)
    except ValueError:
        return None


def _parse_time(txt: str) -> dt.time | None:
    if txt.lower() == "now":
        return dt.time(0, 0, 0)
    try:
        return dt.time.fromisoformat(txt)
    except ValueError:
        return None


# ─────────────────── wizard steps ─────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📅 Target *date*? (YYYY-MM-DD)", parse_mode="Markdown"
    )
    return ASK_DATE


async def got_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    d = _parse_date(update.message.text.strip())
    if not d:
        await update.message.reply_text("❌ Invalid date. Try again (YYYY-MM-DD).")
        return ASK_DATE
    ctx.user_data["date"] = d
    await update.message.reply_text(
        "⏰ Target *time*? (HH:MM:SS or `now` = 00:00:00)", parse_mode="Markdown"
    )
    return ASK_TIME


async def got_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    t = _parse_time(update.message.text.strip())
    if t is None:
        await update.message.reply_text("❌ Invalid time. Try again.")
        return ASK_TIME
    ctx.user_data["time"] = t
    await update.message.reply_text(
        "🏷  Label this event (e.g. *Exam Day*):", parse_mode="Markdown"
    )
    return ASK_LABEL


async def got_label(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["label"] = update.message.text.strip()[:60]
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📌 Pin", callback_data="pin_yes"),
          InlineKeyboardButton("Skip",  callback_data="pin_no")]]
    )
    await update.message.reply_text("Pin countdown message?", reply_markup=kb)
    return ASK_PIN


async def pin_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q      = update.callback_query
    await q.answer()
    pin_it = q.data == "pin_yes"

    date   = ctx.user_data["date"]
    time_  = ctx.user_data["time"]
    label  = ctx.user_data["label"]
    target = dt.datetime.combine(date, time_)

    cid = q.message.chat.id
    # cancel old task if present
    old = tasks.pop(cid, None)
    if old:
        old.cancel()

    msg = await q.edit_message_text("⏳ Starting countdown…")
    if pin_it:
        try:
            await q.message.chat.pin_message(msg.message_id, disable_notification=True)
        except Exception:
            pass  # ignore pin errors (no rights etc.)

    meta[cid] = {"target": target, "label": label, "msg_id": msg.message_id}
    _launch(cid, ctx)
    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Countdown cancelled.")
    return ConversationHandler.END


# ─────────────────── live-update helpers ──────────────────────
async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in meta:
        return await update.message.reply_text("ℹ️ No active countdown.")
    await _edit(cid, ctx.bot)


async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    t   = tasks.pop(cid, None)
    if t:
        t.cancel()
    meta.pop(cid, None)
    await update.message.reply_text("🚫 Countdown cancelled.")


async def _edit(cid: int, bot) -> bool:
    m = meta[cid]
    now = dt.datetime.utcnow()
    left = m["target"] - now
    if left.total_seconds() <= 0:
        txt = f"🎉 {m['label']} reached!"
        try:
            await bot.edit_message_text(cid, m["msg_id"], text=txt)
        except Exception:
            pass
        return False

    days  = left.days
    hrs, rem = divmod(left.seconds, 3600)
    mins, secs = divmod(rem, 60)
    txt = (
        f"⏳ *{m['label']}*\n"
        f"{days} d {hrs:02} h {mins:02} m {secs:02} s remaining."
    )
    try:
        await bot.edit_message_text(cid, m["msg_id"], text=txt, parse_mode="Markdown")
    except Exception as e:
        # ignore harmless “message is not modified” errors
        if "message is not modified" not in str(e).lower():
            raise
    return True


def _launch(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    async def loop():
        try:
            # immediate first tick
            while await _edit(cid, ctx.bot):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            tasks.pop(cid, None)
            meta.pop(cid,  None)

    tasks[cid] = ctx.application.create_task(loop())


# ─────────────────── wiring into the bot ──────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_label)],
            ASK_PIN:   [CallbackQueryHandler(pin_choice, pattern="^pin_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", status))
    app.add_handler(CommandHandler("countdownstop",   stop))
