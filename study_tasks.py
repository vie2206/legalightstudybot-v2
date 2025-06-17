# study_tasks.py
"""
Stop-watch study tasks with inline-keyboard presets.
Commands:
    /task_start           – choose a task type & start timer
    /task_status          – show elapsed time
    /task_pause           – pause
    /task_resume          – resume
    /task_stop            – stop & log
"""
import asyncio, time
from enum import Enum, auto
from typing import Dict

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
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

# ────────── in-memory state (per-chat) ──────────
_active: Dict[int, dict] = {}     # chat_id → {type, start_time, paused_at}

# ────────── helpers ──────────
def _elapsed(meta: dict) -> int:
    """Return seconds elapsed (even when paused)."""
    if "paused_at" in meta:
        return int(meta["paused_at"] - meta["start_time"])
    return int(time.time() - meta["start_time"])


def _format_secs(s: int) -> str:
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"

# ────────── handlers ──────────
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point – show inline keyboard of task presets."""
    kb = [
        [
            InlineKeyboardButton("Mock",      callback_data=f"t|{TaskType.CLAT_MOCK}"),
            InlineKeyboardButton("Sectional", callback_data=f"t|{TaskType.SECTIONAL}"),
        ],
        [
            InlineKeyboardButton("Newspaper", callback_data=f"t|{TaskType.NEWSPAPER}"),
            InlineKeyboardButton("Editorial", callback_data=f"t|{TaskType.EDITORIAL}"),
        ],
        [
            InlineKeyboardButton("GK/CA",     callback_data=f"t|{TaskType.GK_CA}"),
            InlineKeyboardButton("Maths",     callback_data=f"t|{TaskType.MATHS}"),
        ],
        [
            InlineKeyboardButton("Legal 🏛️", callback_data=f"t|{TaskType.LEGAL_REASONING}"),
            InlineKeyboardButton("Logical 🔎",callback_data=f"t|{TaskType.LOGICAL_REASONING}"),
        ],
        [
            InlineKeyboardButton("CLATOPEDIA",callback_data=f"t|{TaskType.CLATOPEDIA}"),
            InlineKeyboardButton("English",   callback_data=f"t|{TaskType.ENGLISH}"),
        ],
        [InlineKeyboardButton("Custom ⌨️", callback_data=f"t|{TaskType.STUDY_TASK}")],
    ]
    await update.message.reply_text(
        "Select a study task type:",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button tap, begin the stopwatch."""
    query = update.callback_query           # ← FIX: pull the CallbackQuery
    await query.answer()

    _, raw_type = query.data.split("|", 1)
    ttype = TaskType(raw_type)

    chat_id = query.message.chat.id
    _active[chat_id] = {
        "type":       ttype,
        "start_time": time.time(),
    }
    await query.edit_message_text(
        f"🟢 *{ttype.replace('_', ' ').title()}* started.\n"
        f"Stopwatch running…\nUse /task_pause or /task_stop.",
        parse_mode="Markdown"
    )


async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = _active.get(chat_id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active study task.")

    secs = _elapsed(meta)
    await update.message.reply_text(
        f"⏱️ {_format_secs(secs)} elapsed on *{meta['type'].replace('_',' ').title()}*.",
        parse_mode="Markdown",
    )


async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = _active.get(chat_id)
    if not meta or "paused_at" in meta:
        return await update.message.reply_text("ℹ️ Nothing to pause.")
    meta["paused_at"] = time.time()
    await update.message.reply_text("⏸️ Paused.")


async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = _active.get(chat_id)
    if not meta or "paused_at" not in meta:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    # shift start_time forward by pause duration
    paused_dur = time.time() - meta.pop("paused_at")
    meta["start_time"] += paused_dur
    await update.message.reply_text("▶️ Resumed.")


async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = _active.pop(chat_id, None)
    if not meta:
        return await update.message.reply_text("ℹ️ No active task.")
    secs = _elapsed(meta)
    await update.message.reply_text(
        f"✅ Logged *{_format_secs(secs)}* of {meta['type'].replace('_',' ').title()}.",
        parse_mode="Markdown",
    )
    # TODO: persist into DB (meta, secs)


# ────────── registration helper ──────────
def register_handlers(app):
    app.add_handler(CommandHandler("task_start",  task_start))
    app.add_handler(CallbackQueryHandler(preset_chosen, pattern=r"^t\|"))
    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
