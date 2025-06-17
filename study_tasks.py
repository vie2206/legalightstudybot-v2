# study_tasks.py  ───────────────────────────────────────────────
"""
Stop-watch study tasks with inline-keyboard presets.

Commands
--------
/task_start            – choose a task type & start timer
/task_status           – show elapsed time
/task_pause | /taskpause    – pause      (both spellings work)
/task_resume | /taskresume  – resume
/task_stop | /taskstop      – stop & log
"""
import asyncio, time
from enum import Enum
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
)

# ────────── task types ──────────
class TaskType(str, Enum):
    CLAT_MOCK         = "CLAT_MOCK"
    SECTIONAL         = "SECTIONAL"
    NEWSPAPER         = "NEWSPAPER"
    EDITORIAL         = "EDITORIAL"
    GK_CA             = "GK_CA"
    MATHS             = "MATHS"
    LEGAL_REASONING   = "LEGAL_REASONING"
    LOGICAL_REASONING = "LOGICAL_REASONING"
    CLATOPEDIA        = "CLATOPEDIA"
    SELF_STUDY        = "SELF_STUDY"
    ENGLISH           = "ENGLISH"
    STUDY_TASK        = "STUDY_TASK"

_active: Dict[int, dict] = {}   # chat_id → {type,start_time,paused_at}

# ────────── helpers ──────────
def _elapsed(meta: dict) -> int:
    end = meta.get("paused_at", time.time())
    return int(end - meta["start_time"])

def _fmt(sec: int) -> str:
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h} h {m} m {s} s"
    return f"{m} m {s} s"

# ────────── handlers ──────────
async def task_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Inline keyboard of task presets."""
    kb = [
        [
            InlineKeyboardButton("Mock",      callback_data="T|CLAT_MOCK"),
            InlineKeyboardButton("Sectional", callback_data="T|SECTIONAL"),
        ],[
            InlineKeyboardButton("Newspaper", callback_data="T|NEWSPAPER"),
            InlineKeyboardButton("Editorial", callback_data="T|EDITORIAL"),
        ],[
            InlineKeyboardButton("GK/CA",     callback_data="T|GK_CA"),
            InlineKeyboardButton("Maths",     callback_data="T|MATHS"),
        ],[
            InlineKeyboardButton("Legal 🏛️",  callback_data="T|LEGAL_REASONING"),
            InlineKeyboardButton("Logical 🔎",callback_data="T|LOGICAL_REASONING"),
        ],[
            InlineKeyboardButton("CLATOPEDIA",callback_data="T|CLATOPEDIA"),
            InlineKeyboardButton("English",   callback_data="T|ENGLISH"),
        ],[
            InlineKeyboardButton("Custom ⌨️", callback_data="T|STUDY_TASK"),
        ],
    ]
    await update.message.reply_text(
        "Select a study-task type:",
        reply_markup=InlineKeyboardMarkup(kb),
    )

async def preset_chosen(update: Update, _: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, raw = q.data.split("|", 1)
    ttype  = TaskType(raw)

    chat_id = q.message.chat.id
    _active[chat_id] = {"type": ttype, "start_time": time.time()}
    await q.edit_message_text(
        f"🟢 *{ttype.replace('_',' ').title()}* started.\n"
        "Stop-watch running…\nUse /task_pause or /task_stop.",
        parse_mode="Markdown",
    )

async def task_status(update: Update, _: ContextTypes.DEFAULT_TYPE):
    meta = _active.get(update.effective_chat.id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active study task.")
    await update.message.reply_text(
        f"⏱ {_fmt(_elapsed(meta))} elapsed on *{meta['type'].replace('_',' ').title()}*.",
        parse_mode="Markdown",
    )

async def _pause_resume(update: Update, pause: bool):
    chat_id = update.effective_chat.id
    meta = _active.get(chat_id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active study task.")
    if pause:
        if "paused_at" in meta:
            return await update.message.reply_text("Already paused.")
        meta["paused_at"] = time.time()
        await update.message.reply_text("⏸️ Paused.")
    else:
        if "paused_at" not in meta:
            return await update.message.reply_text("Not paused.")
        meta["start_time"] += time.time() - meta.pop("paused_at")
        await update.message.reply_text("▶️ Resumed.")

async def task_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pause_resume(update, True)

async def task_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pause_resume(update, False)

async def task_stop(update: Update, _: ContextTypes.DEFAULT_TYPE):
    meta = _active.pop(update.effective_chat.id, None)
    if not meta:
        return await update.message.reply_text("ℹ️ No active study task.")
    await update.message.reply_text(
        f"✅ Logged *{_fmt(_elapsed(meta))}* of {meta['type'].replace('_',' ').title()}.",
        parse_mode="Markdown",
    )

# ────────── registration helper ──────────
def register_handlers(app: Application):
    app.add_handler(CommandHandler("task_start",   task_start))
    app.add_handler(CallbackQueryHandler(preset_chosen, pattern=r"^T\|"))
    # support both spellings so users aren’t stuck
    for cmd, fn in [
        ("task_status", task_status),
        ("task_pause",  task_pause),  ("taskpause",  task_pause),
        ("task_resume", task_resume), ("taskresume", task_resume),
        ("task_stop",   task_stop),   ("taskstop",   task_stop),
    ]:
        app.add_handler(CommandHandler(cmd, fn))
