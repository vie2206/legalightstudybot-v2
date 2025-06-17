# countdown.py ────────────────────────────────────────────────
"""
Live countdown with per-second updates and optional pin.

Commands
--------
/countdown          – interactive wizard
/countdownstatus    – show remaining once
/countdownstop      – cancel countdown
"""

import asyncio, datetime as dt
from typing import Dict

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters,
)

# ─── Conversation states
ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

# ─── per-chat storage
_meta:  Dict[int, dict]   = {}    # chat_id → {tgt,label,msg_id}
_tasks: Dict[int, asyncio.Task] = {}

# ─── tiny helpers
def _date(s: str):
    try: return dt.date.fromisoformat(s)
    except: return None
def _time(s: str):
    if s.lower() == "now": return dt.time()
    try: return dt.time.fromisoformat(s)
    except: return None

# ─── wizard handlers
async def start(update: Update, _):
    await update.message.reply_text("📅 Target *date*? (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE

async def got_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d = _date(update.message.text.strip())
    if not d:
        await update.message.reply_text("❌ Try format YYYY-MM-DD.")
        return ASK_DATE
    ctx.user_data["d"] = d
    await update.message.reply_text(
        "⏰ Target *time*? (HH:MM:SS or `now`)", parse_mode="Markdown"
    )
    return ASK_TIME

async def got_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = _time(update.message.text.strip())
    if t is None:
        await update.message.reply_text("❌ Invalid time.")
        return ASK_TIME
    ctx.user_data["t"] = t
    await update.message.reply_text(
        "🏷  Event label? (max 60 characters)", parse_mode="Markdown"
    )
    return ASK_LABEL

async def got_label(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["label"] = update.message.text.strip()[:60]
    kb = [[InlineKeyboardButton("📌 Pin", callback_data="pin_yes"),
           InlineKeyboardButton("No",     callback_data="pin_no")]]
    await update.message.reply_text(
        "Pin countdown in chat?", reply_markup=InlineKeyboardMarkup(kb)
    )
    return ASK_PIN

async def pin_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    cid = q.message.chat.id
    await q.answer()

    pin  = q.data.endswith("yes")
    tgt  = dt.datetime.combine(ctx.user_data["d"], ctx.user_data["t"])
    label = ctx.user_data["label"]

    # cancel old task if any
    if (old := _tasks.pop(cid, None)): old.cancel()

    msg = await q.edit_message_text("⏳ Starting countdown…")
    if pin:
        await ctx.bot.pin_chat_message(cid, msg.message_id, disable_notification=True)

    _meta[cid] = {"tgt": tgt, "label": label, "msg_id": msg.message_id}
    _launch(cid, ctx.bot)
    return ConversationHandler.END

# ─── helper commands
async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in _meta:
        return await update.message.reply_text("ℹ️ No active countdown.")
    await _edit(cid, ctx.bot)

async def stop(update: Update, _):
    cid = update.effective_chat.id
    if (t := _tasks.pop(cid, None)): t.cancel()
    _meta.pop(cid, None)
    await update.message.reply_text("🚫 Countdown cancelled.")

# ─── internal loop
async def _edit(cid: int, bot):
    m   = _meta[cid]
    now = dt.datetime.utcnow()
    rem = m["tgt"] - now
    if rem.total_seconds() <= 0:
        await bot.edit_message_text(cid, m["msg_id"], f"🎉 {m['label']} reached!")
        return False
    d = rem.days
    h, r = divmod(rem.seconds, 3600)
    mn, s = divmod(r, 60)
    await bot.edit_message_text(
        cid, m["msg_id"],
        f"⏳ *{m['label']}*\n{d}d {h}h {mn}m {s}s remaining.",
        parse_mode="Markdown"
    )
    return True

def _launch(cid: int, bot):
    async def loop():
        try:
            while await _edit(cid, bot):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    _tasks[cid] = asyncio.create_task(loop())

# ─── registration helper
def register_handlers(app: Application):
    conv = ConversationHandler(
        [CommandHandler("countdown", start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_label)],
            ASK_PIN:   [CallbackQueryHandler(pin_choice, pattern="^pin_")],
        },
        fallbacks=[CommandHandler("cancel", stop)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", status))
    app.add_handler(CommandHandler("countdownstop",   stop))
