# countdown.py – live edit every 2 s, optional pin
import asyncio, datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)
meta={}, tasks={}

def _parse_date(s):      # YYYY-MM-DD
    try: return dt.date.fromisoformat(s)
    except ValueError:   return None
def _parse_time(s):      # HH:MM:SS or now
    if s.lower()=="now": return dt.time()
    try: return dt.time.fromisoformat(s)
    except ValueError:   return None

async def start(update:Update, _): await update.message.reply_text("📅 Date (YYYY-MM-DD)?"); return ASK_DATE
async def got_date(update:Update, ctx):
    d=_parse_date(update.message.text.strip())
    if not d: return await update.message.reply_text("Bad date.") or ASK_DATE
    ctx.user_data["d"]=d; await update.message.reply_text("⏰ Time (HH:MM:SS or now)"); return ASK_TIME
async def got_time(update:Update, ctx):
    t=_parse_time(update.message.text.strip())
    if t is None: return await update.message.reply_text("Bad time.") or ASK_TIME
    ctx.user_data["t"]=t; await update.message.reply_text("🏷 Label?"); return ASK_LABEL
async def got_label(update:Update, ctx):
    ctx.user_data["label"]=update.message.text.strip()[:60]
    kb=[[InlineKeyboardButton("Pin",callback_data="Y"),
         InlineKeyboardButton("Skip",callback_data="N")]]
    await update.message.reply_text("Pin countdown message?",reply_markup=InlineKeyboardMarkup(kb))
    return ASK_PIN

async def pin_choice(update:Update, ctx):
    q=update.callback_query; await q.answer()
    pin=(q.data=="Y"); cid=q.message.chat.id
    target=dt.datetime.combine(ctx.user_data["d"], ctx.user_data["t"])
    m=await q.edit_message_text("⏳ Starting…")
    if pin: await q.bot.pin_chat_message(cid,m.message_id,disable_notification=True)
    meta[cid]={"target":target,"msg":m.message_id,"label":ctx.user_data["label"]}
    if cid in tasks: tasks[cid].cancel()
    tasks[cid]=asyncio.create_task(_loop(cid,q.bot))
    return ConversationHandler.END

async def status(update:Update, ctx):
    if update.effective_chat.id not in meta: return await update.message.reply_text("No countdown.")
    await _edit(update.effective_chat.id, ctx.bot)

async def stop(update:Update, _):
    cid=update.effective_chat.id
    if cid in tasks: tasks[cid].cancel(); tasks.pop(cid,None)
    meta.pop(cid,None)
    await update.message.reply_text("🚫 Countdown cancelled.")

async def _edit(cid, bot):
    m=meta[cid]; now=dt.datetime.utcnow()
    rem=m["target"]-now
    if rem.total_seconds()<=0:
        await bot.edit_message_text(cid,m["msg"],text=f"🎉 {m['label']}!")
        return False
    d=rem.days; h,rem2=divmod(rem.seconds,3600); mins,sec=divmod(rem2,60)
    txt=f"⏳ *{m['label']}*\n{d}d {h:02d}:{mins:02d}:{sec:02d} left."
    await bot.edit_message_text(cid,m["msg"],text=txt,parse_mode="Markdown")
    return True
async def _loop(cid,bot):
    try:
        while await _edit(cid,bot):
            await asyncio.sleep(2)
    except asyncio.CancelledError: pass

def register_handlers(app:Application):
    conv=ConversationHandler(
        entry_points=[CommandHandler("countdown",start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT &~filters.COMMAND,got_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT &~filters.COMMAND,got_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT &~filters.COMMAND,got_label)],
            ASK_PIN:   [CallbackQueryHandler(pin_choice,pattern="^[YN]$")],
        }, fallbacks=[CommandHandler("cancel",stop)], per_chat=True)
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus",status))
    app.add_handler(CommandHandler("countdownstop",stop))
