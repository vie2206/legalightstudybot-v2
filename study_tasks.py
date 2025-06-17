"""
study_tasks.py  –  Stopwatch-style study task tracker
Compatible with python-telegram-bot v20.x
"""

import asyncio
import time
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

# ────────────────────────────────────────────────────────────────────────────
class TaskType(str, Enum):
    CLAT_MOCK          = "CLAT_MOCK"
    SECTIONAL          = "SECTIONAL"
    NEWSPAPER          = "NEWSPAPER"
    EDITORIAL          = "EDITORIAL"
    GK_CA              = "GK_CA"
    MATHS              = "MATHS"
    LEGAL_REASONING    = "LEGAL_REASONING"
    LOGICAL_REASONING  = "LOGICAL_REASONING"
    CLATOPEDIA         = "CLATOPEDIA"
    SELF_STUDY         = "SELF_STUDY"
    ENGLISH            = "ENGLISH"
    STUDY_TASK         = "STUDY_TASK"

# ordered list for the picker
TASK_ORDER = [
    TaskType.CLAT_MOCK, TaskType.SECTIONAL, TaskType.NEWSPAPER,
    TaskType.EDITORIAL, TaskType.GK_CA, TaskType.MATHS,
    TaskType.LEGAL_REASONING, TaskType.LOGICAL_REASONING, TaskType.CLATOPEDIA,
    TaskType.SELF_STUDY, TaskType.ENGLISH, TaskType.STUDY_TASK,
]

# ────────────────────────────────────────────────────────────────────────────
# in-memory:  chat_id → {"type": TaskType, "start": epoch, "elapsed": secs, "paused": bool}
tasks: Dict[int, Dict[str, object]] = {}


# ─────────────────────────────── helpers ───────────────────────────────────
def _format_elapsed(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# ─────────────────────────────── UI pickers ────────────────────────────────
def _task_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(t.replace("_", " ").title(), callback_data=f"task:{t}")
        for t in TASK_ORDER
    ]
    # 3 buttons per row
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(rows)


# ─────────────────────────────── Handlers ──────────────────────────────────
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/task_start or /task_start <TYPE>"""
    chat_id = update.effective_chat.id

    # If user provided a type directly
    if context.args:
        arg = context.args[0].upper()
        if arg not in TaskType.__members__:
            return await update.message.reply_text(
                "❌ Unknown type. Send /task_start and choose from the list."
            )
        task_type = TaskType[arg]
        return await _begin_task(chat_id, update.message, task_type)

    # Otherwise show inline keyboard
    await update.message.reply_text(
        "Choose your study task:", reply_markup=_task_keyboard()
    )


async def _task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CallbackQuery: user clicked a task type"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("task:"):
        return
    task_type = TaskType[data.split(":", 1)[1]]
    await _begin_task(query.message.chat_id, query, task_type)


async def _begin_task(chat_id: int, msg_or_query, task_type: TaskType):
    # Cancel any existing task
    tasks.pop(chat_id, None)

    tasks[chat_id] = {
        "type":    task_type,
        "start":   time.time(),
        "elapsed": 0.0,
        "paused":  False,
    }

    name = task_type.replace("_", " ").title()
    text = f"🟢 *{name}* started.  Stopwatch running…\nUse /task_pause or /task_stop."
    if isinstance(msg_or_query, Update):  # message
        await msg_or_query.reply_text(text, parse_mode="Markdown")
    else:                                 # CallbackQuery
        await msg_or_query.edit_message_text(text, parse_mode="Markdown")


async def task_status(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rec     = tasks.get(chat_id)
    if not rec:
        return await update.message.reply_text("ℹ️ No task running.")

    if rec["paused"]:
        elapsed = rec["elapsed"]
        state   = "⏸ Paused"
    else:
        elapsed = rec["elapsed"] + (time.time() - rec["start"])
        state   = "🟢 Running"

    name = rec["type"].replace("_", " ").title()
    await update.message.reply_text(
        f"{state} *{name}* — _{_format_elapsed(elapsed)}_",
        parse_mode="Markdown",
    )


async def task_pause(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rec     = tasks.get(chat_id)
    if not rec or rec["paused"]:
        return await update.message.reply_text("ℹ️ Nothing to pause.")
    rec["elapsed"] += time.time() - rec["start"]
    rec["paused"]   = True
    await update.message.reply_text(
        f"⏸ Paused at {_format_elapsed(rec['elapsed'])}."
    )


async def task_resume(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rec     = tasks.get(chat_id)
    if not rec or not rec["paused"]:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    rec["start"]  = time.time()
    rec["paused"] = False
    await update.message.reply_text("▶️ Resumed.")


async def task_stop(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rec     = tasks.pop(chat_id, None)
    if not rec:
        return await update.message.reply_text("ℹ️ No task to stop.")

    # Final elapsed
    if not rec["paused"]:
        rec["elapsed"] += time.time() - rec["start"]

    name    = rec["type"].replace("_", " ").title()
    elapsed = _format_elapsed(rec["elapsed"])
    await update.message.reply_text(
        f"✅ *{name}* completed — _{elapsed}_.",
        parse_mode="Markdown",
    )
    # TODO: persist to DB


# ───────────────────────── register with main bot ─────────────────────────
def register_handlers(app: Application):
    app.add_handler(CommandHandler("task_start",  task_start))
    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))

    # callback buttons
    app.add_handler(CallbackQueryHandler(_task_button, pattern=r"^task:"))
