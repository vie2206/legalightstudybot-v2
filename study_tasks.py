# study_tasks.py  – stopwatch that shows elapsed every 2 s
import asyncio, time
from enum import Enum
from typing import Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

class TaskType(str, Enum):
    MOCK = "Mock", "📝 Mock"
    SECTIONAL = "Sectional", "📊 Sectional"
    NEWSPAPER = "Newspaper", "🗞 Newspaper"
    EDITORIAL = "Editorial", "✍️ Editorial"
    GK_CA = "GK_CA", "🌎 GK/CA"
    MATHS = "Maths", "➗ Maths"
    LEGAL = "Legal Reasoning", "⚖️ Legal"
    LOGICAL = "Logical Reasoning", "🧩 Logical"
    CLATOPEDIA = "CLATOPEDIA", "📚 Clatopedia"
    ENGLISH = "English", "📖 English"
    SELF = "Self-Study", "👤 Self-study"
    CUSTOM = "Custom", "🔖 Custom"

    def __new__(cls, key, label):
        obj = str.__new__(cls, key); obj._value_ = key; obj.label = label; return obj

_active: Dict[int, dict] = {}
_loops:  Dict[int, asyncio.Task] = {}

def _elapsed(meta): return int(time.time() - meta["start"])
def _fmt(s): h, rem = divmod(s,3600); m, s = divmod(rem,60); return f"{h:02d}:{m:02d}:{s:02d}"

# ── handlers ─────────────────────────────────────────────────
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    kb = []
    row = []
    for t in TaskType:
        row.append(InlineKeyboardButton(t.label, callback_data=f"T|{t.value}"))
        if len(row) == 2:
            kb.append(row); row=[]
    if row: kb.append(row)
    await update.message.reply_text("Pick a task:", reply_markup=InlineKeyboardMarkup(kb))

async def chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, raw = q.data.split("|",1)
    cid = q.message.chat.id
    if cid in _loops:
        _loops[cid].cancel()
    _active[cid] = {"type": raw, "start": time.time()}
    await q.edit_message_text(f"🟢 *{raw}* started.\nUse /task_pause or /task_stop.", parse_mode="Markdown")
    _loops[cid]=asyncio.create_task(_tick_loop(cid, ctx.bot))

async def _tick_loop(cid, bot):
    try:
        while cid in _active:
            await bot.send_message(cid, f"⏱ {_fmt(_elapsed(_active[cid]))} elapsed.", disable_notification=True)
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass

async def pause(update: Update, _):
    cid=update.effective_chat.id
    if cid not in _active or cid in _active and _active[cid].get("paused"):
        return await update.message.reply_text("Nothing to pause.")
    _active[cid]["paused"]=time.time()
    _loops[cid].cancel(); _loops.pop(cid,None)
    await update.message.reply_text("⏸ Paused.")

async def resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid=update.effective_chat.id
    meta=_active.get(cid)
    if not meta or "paused" not in meta:
        return await update.message.reply_text("Nothing to resume.")
    meta["start"] += time.time()-meta.pop("paused")
    _loops[cid]=asyncio.create_task(_tick_loop(cid, ctx.bot))
    await update.message.reply_text("▶️ Resumed.")

async def stop(update: Update, _):
    cid=update.effective_chat.id
    if cid in _loops: _loops[cid].cancel(); _loops.pop(cid,None)
    meta=_active.pop(cid,None)
    if not meta: return await update.message.reply_text("Nothing to stop.")
    await update.message.reply_text(f"✅ Logged {_fmt(_elapsed(meta))} on {meta['type']}.")

async def status(update: Update, _):
    cid=update.effective_chat.id
    meta=_active.get(cid)
    if not meta: return await update.message.reply_text("No active task.")
    await update.message.reply_text(f"⏱ {_fmt(_elapsed(meta))} elapsed on {meta['type']}.")

def register_handlers(app: Application):
    app.add_handler(CommandHandler("task_start", cmd_start))
    app.add_handler(CallbackQueryHandler(chosen, pattern=r"^T\|"))
    app.add_handler(CommandHandler("task_pause",  pause))
    app.add_handler(CommandHandler("task_resume", resume))
    app.add_handler(CommandHandler("task_stop",   stop))
    app.add_handler(CommandHandler("task_status", status))
