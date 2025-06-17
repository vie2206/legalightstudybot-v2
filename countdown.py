# countdown.py
"""
Live event-countdown with optional pin:

  /countdown  → wizard asks
      1) Date  (YYYY-MM-DD)
      2) Time  (HH:MM:SS or 'now')
      3) Label (max 60 chars)
      4) Pin?  ✅/❌
  The bot then posts (and maybe pins) a message that updates every second.

Extra commands
--------------
/countdownstatus   – show remaining once
/countdownstop     – cancel the live countdown
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
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

# per-chat state
meta:  Dict[int, dict]     = {}        # chat_id → {target, label, msg_id, pinned}
tasks: Dict[int, asyncio.Task] = {}    # chat_id → asyncio task


# ───────────────────────── helpers
def _parse_date(s: str):
    try: return dt.date.fromisoformat(s)
    except ValueError: return None


def _parse_time(s: str):
    if s.lower() == "now":
        return dt.time(0, 0, 0)
    try: return dt.time.fromisoformat(s)
    except ValueError: return None


async def _edit(chat_id: int, bot):
    """Return True while still counting down; False when finished."""
    m = meta[chat_id]
    remaining = m["target"] - dt.datetime.utcnow()
    if remaining.total_seconds() <= 0:
        txt = f"🎉 *{m['label']}* reached!"
        try:
            await bot.edit_message_text(
                chat_id, m["msg_id"], text=txt, parse_mode="Markdown"
            )
        except: pass
        return False

    days = remaining.days
    hrs, rem = divmod(remaining.seconds, 3600)
    mins, secs = divmod(rem, 60)
    txt = (
        f"⏳ *{m['label']}*\n"
        f"{days}d {hrs}h {mins}m {secs}s remaining."
    )
    try:
        await bot.edit_message_text(
            chat_id, m["msg_id"], text=txt, parse_mode="Markdown"
        )
    except:  # message might have been deleted/unpinned
        return False
    return True


def _launch(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    async def loop():
        try:
            while await _edit(chat_id, ctx.bot):
                await asyncio.sleep(1)          # update every second
        finally:
            tasks.pop(chat_id, None)
            meta.pop(chat_id,  None)

    tasks[chat_id] = asyncio.create_task(loop())


# ───────────────────────── wizard handlers
async def w_start(update: Update, _):
    await update.message.reply_text("📅 Target *date*? (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE


async def w_date(update: Update, ctx):
    d = _parse_date(update.message.text.strip())
    if not d:
        return await update.message.reply_text("❌ Invalid date. Try again.") or ASK_DATE
    ctx.user_data["d"] = d
    await update.message.reply_text("⏰ Target *time*? (HH:MM:SS or `now`)", parse_mode="Markdown")
    return ASK_TIME


async def w_time(update: Update, ctx):
    t = _parse_time(update.message.text.strip())
    if t is None:
        return await update.message.reply_text("❌ Invalid time. Try again.") or ASK_TIME
    ctx.user_data["t"] = t
    await update.message.reply_text("🏷  Event label?")
    return ASK_LABEL


async def w_label(update: Update, ctx):
    ctx.user_data["label"] = update.message.text.strip()[:60]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 Pin", callback_data="pin_yes"),
         InlineKeyboardButton("Skip",  callback_data="pin_no")]
    ])
    await update.message.reply_text("Pin the live countdown message?", reply_markup=kb)
    return ASK_PIN


async def w_pin(update: Update, ctx):
    q   = update.callback_query
    cid = q.message.chat.id
    await q.answer()
    pin = (q.data == "pin_yes")

    # build target datetime
    d, t = ctx.user_data["d"], ctx.user_data["t"]
    target = dt.datetime.combine(d, t)

    # cancel previous
    if tsk := tasks.pop(cid, None):
        tsk.cancel()

    # post initial message
    msg = await q.message.reply_text("⏳ Starting countdown…")
    if pin:
        try: await q.bot.pin_chat_message(cid, msg.message_id, disable_notification=True)
        except: pass

    meta[cid] = {
        "target": target,
        "label":  ctx.user_data["label"],
        "msg_id": msg.message_id,
        "pinned": pin,
    }
    _launch(cid, ctx)
    await q.message.delete()   # remove the wizard’s “Pin?” question
    return ConversationHandler.END


async def cancel(update: Update, _):
    await update.message.reply_text("Countdown wizard cancelled.")
    return ConversationHandler.END


# ───────────────────────── standalone cmds
async def status(update: Update, ctx):
    cid = update.effective_chat.id
    if cid not in meta:
        return await update.message.reply_text("ℹ️ No active countdown.")
    await _edit(cid, ctx.bot)


async def stop(update: Update, _):
    cid = update.effective_chat.id
    if t := tasks.pop(cid, None):
        t.cancel()
    if m := meta.pop(cid, None):
        try: await _.bot.unpin_chat_message(cid, m["msg_id"])
        except: pass
    await update.message.reply_text("🚫 Countdown cancelled.")


# ───────────────────────── registration
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", w_start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, w_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, w_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, w_label)],
            ASK_PIN:   [CallbackQueryHandler(w_pin, pattern="^pin_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", status))
    app.add_handler(CommandHandler("countdownstop",   stop))
