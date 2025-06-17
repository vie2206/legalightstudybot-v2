# countdown.py  ────────────────────────────────────────────────
"""
Live event countdown with per-second updates & optional pin.
"""

import asyncio, datetime as dt
from typing import Dict

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters, ContextTypes
)

ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)
_meta: Dict[int, dict]  = {}
_tasks: Dict[int, asyncio.Task] = {}

def _dt(d: str) -> dt.date|None:
    try: return dt.date.fromisoformat(d)
    except: return None
def _tm(t: str) -> dt.time|None:
    if t.lower()=="now": return dt.time()
    try: return dt.time.fromisoformat(t)
    except: return None

async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Target *date*? (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE

async def got_date(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d = _dt(u.message.text.strip())
    if not d:
        return await u.message.reply_text("❌ Try YYYY-MM-DD") or ASK_DATE
    ctx.user_data["d"]=d
    await u.message.reply_text("⏰ Target *time*? (HH:MM:SS or `now`)", parse_mode="Markdown")
    return ASK_TIME

async def got_time(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t=_tm(u.message.text.strip())
    if t is None:
        return await u.message.reply_text("❌ Invalid time.") or ASK_TIME
    ctx.user_data["t"]=t
    await u.message.reply_text("🏷  Event label? (≤60 chars)", parse_mode="Markdown")
    return ASK_LABEL

async def got_label(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["label"]=u.message.text.strip()[:60]
    kb=[[InlineKeyboardButton("📌 Pin",callback_data="pin_yes"),
         InlineKeyboardButton("No",callback_data="pin_no")]]
    await u.message.reply_text("Pin countdown in chat?",reply_markup=InlineKeyboardMarkup(kb))
    return ASK_PIN

async def pin_choice(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=u.callback_query; await q.answer()
    pin=(q.data=="pin_yes")
    chat=q.message.chat; cid=chat.id
    tgt=dt.datetime.combine(ctx.user_data["d"],ctx.user_data["t"])
    _tasks.get(cid, asyncio.Task).cancel() if cid in _tasks else None
    _meta[cid]={"tgt":tgt,"label":ctx.user_data["label"],"msg":None,"pin":pin}
    m=await q.edit_message_text("⏳ Starting…")
    _meta[cid]["msg"]=m.message_id
    if pin: await q.bot.pin_chat_message(cid,m.message_id,disable_notification=True)
    _launch(cid,q.bot)
    return ConversationHandler.END

async def status(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if cid:=u.effective_chat.id in _meta:
        await _update(u.effective_chat.id, ctx.bot)
    else:
        await u.message.reply_text("ℹ️ No active countdown.")

async def stop(u: Update, _: ContextTypes.DEFAULT_TYPE):
    cid=u.effective_chat.id
    if task:=_tasks.pop(cid,None): task.cancel()
    if cid in _meta: _meta.pop(cid)
    await u.message.reply_text("🚫 Countdown cancelled.")

# ── helpers ──────────────────────────────────────────────────
async def _update(cid:int, bot):
    m=_meta[cid]; now=dt.datetime.utcnow(); rem=m["tgt"]-now
    if rem.total_seconds()<=0:
        await bot.edit_message_text(cid,m["msg"],text=f"🎉 {m['label']} reached!")
        return False
    d, r = rem.days, rem.seconds
    h, r = divmod(r,3600); mn, s = divmod(r,60)
    await bot.edit_message_text(
        cid, m["msg"],
        text=f"⏳ *{m['label']}*\n{d}d {h}h {mn}m {s}s remaining.",
        parse_mode="Markdown")
    return True

def _launch(cid:int, bot):
    async def loop():
        try:
            while await _update(cid, bot):
                await asyncio.sleep(1)
        except asyncio.CancelledError: pass
    _tasks[cid]=asyncio.create_task(loop())

def register_handlers(app: Application):
    conv=ConversationHandler(
        [CommandHandler("countdown",start)],
        states={
            ASK_DATE:[MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
            ASK_TIME:[MessageHandler(filters.TEXT & ~filters.COMMAND, got_time)],
            ASK_LABEL:[MessageHandler(filters.TEXT & ~filters.COMMAND, got_label)],
            ASK_PIN:[CallbackQueryHandler(pin_choice,pattern="^pin_")],
        },
        fallbacks=[CommandHandler("cancel",stop)], per_chat=True)
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus",status))
    app.add_handler(CommandHandler("countdownstop",stop))
