# timer.py ─────────────────────────────────────────────────────
"""
Interactive Pomodoro timer with inline presets + classic commands.
"""

import asyncio, time
from typing import Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters,
)

CHOOSING, ASK_WORK, ASK_BREAK = range(3)

active: Dict[int, asyncio.Task]  = {}
meta:   Dict[int, dict]          = {}

# ─── helpers
def _secs(m: int) -> int: return max(1, m) * 60

# ─── wizard
async def wizard_entry(u: Update, _):
    kb = [
        [InlineKeyboardButton("Pomodoro 25 | 5", callback_data="25|5"),
         InlineKeyboardButton("Focus 50 | 10",   callback_data="50|10")],
        [InlineKeyboardButton("Custom ➕", callback_data="custom")],
    ]
    await u.message.reply_text(
        "Choose a preset or tap *Custom ➕*:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return CHOOSING

async def preset_chosen(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer()
    w, b = map(int, q.data.split("|"))
    return await _begin(q, ctx, w, b)

async def custom_chosen(u: Update, _):
    q = u.callback_query; await q.answer()
    await q.edit_message_text("Work minutes?")
    return ASK_WORK

async def ask_break(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["work"] = int(u.message.text)
    await u.message.reply_text("Break minutes?")
    return ASK_BREAK

async def custom_finish(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    w = ctx.user_data["work"]; b = int(u.message.text)
    return await _begin(u, ctx, w, b)

# ─── core
async def _begin(origin, ctx: ContextTypes.DEFAULT_TYPE, work, brk):
    chat = origin.message.chat if hasattr(origin, "message") else origin.effective_chat
    cid  = chat.id

    if (t := active.pop(cid, None)): t.cancel()
    meta[cid] = m = {
        "phase":"work","rem":_secs(work),
        "work":_secs(work),"break":_secs(brk),"start":time.time()
    }

    await ctx.bot.send_message(
        cid,
        f"🟢 *Study* started • {work}-min focus → {brk}-min break.\n"
        "Use /timer_pause /timer_resume /timer_stop.",
        parse_mode="Markdown"
    )
    _launch(cid, ctx.bot)
    return ConversationHandler.END

def _launch(cid: int, bot):
    m = meta[cid]
    async def loop():
        try:
            end = time.time() + m["rem"]
            while True:
                rem = int(end - time.time())
                if rem <= 0: break
                await asyncio.sleep(5)
            # switch
            if m["phase"] == "work":
                m["phase"] = "break"; m["rem"] = m["break"]; m["start"]=time.time()
                await bot.send_message(cid, f"⏰ Break {m['break']//60}-min!")
                _launch(cid, bot)
            else:
                await bot.send_message(cid, "✅ Session complete!")
                active.pop(cid, None); meta.pop(cid,None)
        except asyncio.CancelledError: pass
    active[cid] = asyncio.create_task(loop())

# ─── classic controls
async def _pause_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE, pause: bool):
    cid = update.effective_chat.id
    m   = meta.get(cid); t = active.get(cid)
    if not m: return await update.message.reply_text("ℹ️ No active timer.")
    if pause and t:
        m["rem"] = max(0, m["rem"] - (time.time()-m["start"]))
        t.cancel(); active.pop(cid,None)
        await update.message.reply_text("⏸️ Paused.")
    elif not pause and not t:
        m["start"] = time.time(); _launch(cid, ctx.bot)
        await update.message.reply_text("▶️ Resumed.")

async def pause(u,c):  await _pause_resume(u,c,True)
async def resume(u,c): await _pause_resume(u,c,False)

async def stop(update: Update, _):
    cid = update.effective_chat.id
    if (t:=active.pop(cid,None)): t.cancel()
    meta.pop(cid,None)
    await update.message.reply_text("🚫 Timer cancelled.")

async def status(update: Update, _):
    m = meta.get(update.effective_chat.id)
    if not m: return await update.message.reply_text("ℹ️ No active timer.")
    rem = m["rem"] - (time.time()-m["start"])
    mins, sec = divmod(int(rem), 60)
    await update.message.reply_text(f"⏱ {mins}m {sec}s remaining.")

# ─── registration
def register_handlers(app: Application):
    wizard = ConversationHandler(
        [CommandHandler("timer", wizard_entry)],
        states={
            CHOOSING:[CallbackQueryHandler(preset_chosen, r"^\d+\|\d+$"),
                      CallbackQueryHandler(custom_chosen,  r"^custom$")],
            ASK_WORK:[MessageHandler(filters.Regex(r"^\d+$"), ask_break)],
            ASK_BREAK:[MessageHandler(filters.Regex(r"^\d+$"), custom_finish)],
        },
        per_chat=True,
    )
    app.add_handler(wizard)
    app.add_handler(CommandHandler("timer_status", status))
    app.add_handler(CommandHandler("timer_pause",  pause))
    app.add_handler(CommandHandler("timer_resume", resume))
    app.add_handler(CommandHandler("timer_stop",   stop))
