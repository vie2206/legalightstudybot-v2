# study_tasks.py
"""
Stop-watch study tasks with inline-keyboard presets.

Commands
--------
/task_start           – choose a task type & start timer
/task_status          – show elapsed time
/task_pause           – pause
/task_resume          – resume
/task_stop            – stop & log
"""
import asyncio, time
from enum import Enum
from typing import Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ─────────────────────────── task types ────────────────────────────
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

# ───────────────────────── in-memory state ─────────────────────────
_active: Dict[int, dict] = {}          # chat_id → {type,start_time,paused_at}

# ──────────────────────────── helpers ──────────────────────────────
def _elapsed(meta: dict) -> int:
    """Seconds elapsed (even when paused)."""
    if "paused_at" in meta:
        return int(meta["paused_at"] - meta["start_time"])
    return int(time.time() - meta["start_time"])


def _fmt(secs: int) -> str:
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

# ─────────────────────────── handlers ──────────────────────────────
async def task_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/task_start – show preset keyboard."""
    kb = [
        [InlineKeyboardButton("Mock",      callback_data=f"t|{TaskType.CLAT_MOCK}"),
         InlineKeyboardButton("Sectional", callback_data=f"t|{TaskType.SECTIONAL}")],
        [InlineKeyboardButton("Newspaper", callback_data=f"t|{TaskType.NEWSPAPER}"),
         InlineKeyboardButton("Editorial", callback_data=f"t|{TaskType.EDITORIAL}")],
        [InlineKeyboardButton("GK/CA",     callback_data=f"t|{TaskType.GK_CA}"),
         InlineKeyboardButton("Maths",     callback_data=f"t|{TaskType.MATHS}")],
        [InlineKeyboardButton("Legal 🏛️",  callback_data=f"t|{TaskType.LEGAL_REASONING}"),
         InlineKeyboardButton("Logical 🔎",callback_data=f"t|{TaskType.LOGICAL_REASONING}")],
        [InlineKeyboardButton("CLATOPEDIA",callback_data=f"t|{TaskType.CLATOPEDIA}"),
         InlineKeyboardButton("English",   callback_data=f"t|{TaskType.ENGLISH}")],
        [InlineKeyboardButton("Custom ⌨️", callback_data=f"t|{TaskType.STUDY_TASK}")],
    ]
    await update.message.reply_text(
        "Select a study task type:",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def preset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Button tap → begin stopwatch."""
    q = update.callback_query
    await q.answer()

    ttype = TaskType(q.data.split("|", 1)[1])
    await _begin(q.message.chat.id, ctx.bot, ttype)


async def _begin(chat_id: int, bot, ttype: TaskType):
    _active[chat_id] = {"type": ttype, "start_time": time.time()}
    await bot.send_message(
        chat_id,
        f"🟢 *{ttype.replace('_',' ').title()}* started.\n"
        "Stopwatch running…\nUse /task_pause or /task_stop.",
        parse_mode="Markdown",
    )


async def task_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    meta = _active.get(update.effective_chat.id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active study task.")
    await update.message.reply_text(
        f"⏱️ {_fmt(_elapsed(meta))} elapsed on "
        f"*{meta['type'].replace('_',' ').title()}*.",
        parse_mode="Markdown",
    )


async def task_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    meta = _active.get(update.effective_chat.id)
    if not meta or "paused_at" in meta:
        return await update.message.reply_text("ℹ️ Nothing to pause.")
    meta["paused_at"] = time.time()
    await update.message.reply_text("⏸️ Paused.")


async def task_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    meta = _active.get(update.effective_chat.id)
    if not meta or "paused_at" not in meta:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    meta["start_time"] += time.time() - meta.pop("paused_at")
    await update.message.reply_text("▶️ Resumed.")


async def task_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    meta = _active.pop(update.effective_chat.id, None)
    if not meta:
        return await update.message.reply_text("ℹ️ No active task.")
    await update.message.reply_text(
        f"✅ Logged *{_fmt(_elapsed(meta))}* of "
        f"{meta['type'].replace('_',' ').title()}.",
        parse_mode="Markdown",
    )
    # TODO: save to database

# ───────────────────── registration helper ────────────────────────
def register_handlers(app: Application):
    app.add_handler(CommandHandler("task_start",  task_start))
    app.add_handler(CallbackQueryHandler(preset, pattern=r"^t\|"))
    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
