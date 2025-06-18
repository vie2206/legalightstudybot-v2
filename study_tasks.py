# study_tasks.py  ✨ 2-Jun-2025
"""
Stop-watch study tasks with a live elapsed-time ticker.
"""
from __future__ import annotations
import asyncio, time
from enum import Enum
from typing import Dict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

class TaskType(str, Enum):
    CLAT_MOCK="CLAT_MOCK"; SECTIONAL="SECTIONAL"; NEWSPAPER="NEWSPAPER"; EDITORIAL="EDITORIAL"
    GK_CA="GK_CA"; MATHS="MATHS"; LEGAL_REASONING="LEGAL_REASONING"; LOGICAL_REASONING="LOGICAL_REASONING"
    CLATOPEDIA="CLATOPEDIA"; SELF_STUDY="SELF_STUDY"; ENGLISH="ENGLISH"; STUDY_TASK="STUDY_TASK"

_active: Dict[int, dict] = {}   # chat → {type,start,msg_id,paused}

# ───────── helpers ─────────
def _fmt(secs:int)->str:
    m,s = divmod(secs,60); h,m = divmod(m,60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

async def _ticker(chat_id:int, bot):
    try:
        while True:
            meta=_active.get(chat_id); 
            if not meta: break
            if meta.get("paused"): await asyncio.sleep(2); continue
            elapsed=int(time.time()-meta["start"])
            txt=f"🟢 *{meta['type'].replace('_',' ').title()}*\nElapsed: *_{_fmt(elapsed)}_*.\nUse /task_pause or /task_stop."
            try: await bot.edit_message_text(chat_id,meta["msg_id"],txt,parse_mode="Markdown")
            except Exception: pass
            await asyncio.sleep(20)
    finally:
        _active.pop(chat_id,None)

# ───────── command handlers ─────────
async def task_start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    kb=[
      [InlineKeyboardButton("Mock",callback_data=f"t|{TaskType.CLAT_MOCK}"),
       InlineKeyboardButton("Sectional",callback_data=f"t|{TaskType.SECTIONAL}")],
      [InlineKeyboardButton("Newspaper",callback_data=f"t|{TaskType.NEWSPAPER}"),
       InlineKeyboardButton("Editorial",callback_data=f"t|{TaskType.EDITORIAL}")],
      [InlineKeyboardButton("GK/CA",callback_data=f"t|{TaskType.GK_CA}"),
       InlineKeyboardButton("Maths",callback_data=f"t|{TaskType.MATHS}")],
      [InlineKeyboardButton("Legal 🏛️",callback_data=f"t|{TaskType.LEGAL_REASONING}"),
       InlineKeyboardButton("Logical 🔎",callback_data=f"t|{TaskType.LOGICAL_REASONING}")],
      [InlineKeyboardButton("CLATOPEDIA",callback_data=f"t|{TaskType.CLATOPEDIA}"),
       InlineKeyboardButton("English",callback_data=f"t|{TaskType.ENGLISH}")],
      [InlineKeyboardButton("Custom ⌨️",callback_data=f"t|{TaskType.STUDY_TASK}")]
    ]
    await update.message.reply_text("Select a study task:",reply_markup=InlineKeyboardMarkup(kb))

async def _begin(chat_id:int,bot,ttype:TaskType):
    # cancel old
    if (old:=_active.pop(chat_id,None)) and (tid:=old.get("ticker")): tid.cancel()
    sent=await bot.send_message(chat_id,"Starting…")
    _active[chat_id]={
        "type":ttype,"start":time.time(),"msg_id":sent.message_id,
        "paused":False
    }
    _active[chat_id]["ticker"]=asyncio.create_task(_ticker(chat_id,bot))

async def preset(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    ttype=TaskType(q.data.split("|")[1])
    await _begin(q.message.chat.id,q.bot,ttype)
    await q.edit_message_text("🟢 Stopwatch running…\nUse /task_pause or /task_stop.")

async def _status_msg(chat_id:int)->str:
    meta=_active[chat_id]; elapsed=int(time.time()-meta["start"])
    return f"⏱ {_fmt(elapsed)} on {meta['type'].replace('_',' ').title()}."

async def task_status(update:Update,ctx): 
    cid=update.effective_chat.id
    if cid not in _active: return await update.message.reply_text("ℹ️ No active task.")
    await update.message.reply_text(await _status_msg(cid),parse_mode="Markdown")

async def task_pause(update:Update,ctx):
    cid=update.effective_chat.id; meta=_active.get(cid)
    if not meta or meta["paused"]: return await update.message.reply_text("Nothing to pause.")
    meta["paused"]=True; meta["pause_at"]=time.time()
    await update.message.reply_text("⏸️ Paused.")

async def task_resume(update:Update,ctx):
    cid=update.effective_chat.id; meta=_active.get(cid)
    if not meta or not meta["paused"]: return await update.message.reply_text("Nothing to resume.")
    meta["paused"]=False
    meta["start"] += time.time()-meta.pop("pause_at")
    await update.message.reply_text("▶️ Resumed.")

async def task_stop(update:Update,ctx):
    cid=update.effective_chat.id; meta=_active.pop(cid,None)
    if not meta: return await update.message.reply_text("No active task.")
    if (t:=meta.get("ticker")): t.cancel()
    elapsed=int((time.time()-meta["start"]) if not meta.get("paused") else meta["pause_at"]-meta["start"])
    await update.message.reply_text(f"✅ Logged *_{_fmt(elapsed)}_* of {meta['type'].replace('_',' ').title()}.",parse_mode="Markdown")

# ───────── registrar ─────────
def register_handlers(app:Application):
    app.add_handler(CommandHandler("task_start",task_start))
    app.add_handler(CallbackQueryHandler(preset,pattern=r"^t\|"))
    app.add_handler(CommandHandler("task_status",task_status))
    app.add_handler(CommandHandler("task_pause",task_pause))
    app.add_handler(CommandHandler("task_resume",task_resume))
    app.add_handler(CommandHandler("task_stop",task_stop))
