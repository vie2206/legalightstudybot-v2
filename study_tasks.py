"""
study_tasks.py  – stop-watch style study sessions

Usage
─────
/task_start <TYPE>     → starts immediately (if TYPE supplied)
/task_start            → shows inline keyboard of types
/task_status           → show elapsed / paused
/task_pause            → pause
/task_resume           → resume
/task_stop             → finish & log

The module uses context.user_data to keep per-user state.
"""

from __future__ import annotations

import time
from enum import Enum, auto
from typing import Final, Dict

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
    ConversationHandler,
)

# ────────────────────────────────────────────────────────────
class TaskType(str, Enum):
    CLAT_MOCK        = "CLAT_MOCK"
    SECTIONAL        = "SECTIONAL"
    NEWSPAPER        = "NEWSPAPER"
    EDITORIAL        = "EDITORIAL"
    GK_CA            = "GK_CA"
    MATHS            = "MATHS"
    LEGAL_REASONING  = "LEGAL_REASONING"
    LOGICAL_REASONING= "LOGICAL_REASONING"
    CLATOPEDIA       = "CLATOPEDIA"
    SELF_STUDY       = "SELF_STUDY"
    ENGLISH          = "ENGLISH"
    STUDY_TASK       = "STUDY_TASK"

PRESETS: Final[list[TaskType]] = [
    TaskType.CLAT_MOCK, TaskType.SECTIONAL, TaskType.NEWSPAPER,
    TaskType.EDITORIAL, TaskType.GK_CA,     TaskType.MATHS,
    TaskType.LEGAL_REASONING, TaskType.LOGICAL_REASONING,
    TaskType.CLATOPEDIA,      TaskType.SELF_STUDY,
    TaskType.ENGLISH,         TaskType.STUDY_TASK,
]

# Conversation state
CHOOSING = 1

# ────────────────────────────────────────────────────────────
def _keyboard() -> InlineKeyboardMarkup:
    # 3-buttons per row for readability
    rows, row = [], []
    for i, t in enumerate(PRESETS, 1):
        row.append(InlineKeyboardButton(t.replace("_", " ").title(), callback_data=t))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

# helpers
def _now() -> float:
    return time.time()

def _human(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

# ────────────────────────────────────────────────────────────
async def _begin(update_or_q, context: ContextTypes.DEFAULT_TYPE, ttype: TaskType):
    """Start a task timer; works for /task_start <type> or callback."""
    chat_id = update_or_q.effective_chat.id
    context.user_data["task"] = {
        "type":       ttype,
        "start":      _now(),
        "elapsed":    0.0,
        "is_paused":  False,
    }
    msg = await context.bot.send_message(
        chat_id,
        f"🟢 *{ttype.replace('_', ' ').title()}* started.\n"
        "Stop-watch running…\n"
        "Use /task_pause or /task_stop.",
        parse_mode="Markdown",
    )
    # End the conversation (so keyboard disappears)
    return ConversationHandler.END

# ────────────────── command callbacks ───────────────────────
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """`/task_start [TYPE]` – with type = start, else show chooser."""
    if context.args:
        try:
            ttype = TaskType(context.args[0].upper())
        except ValueError:
            return await update.message.reply_text("❌ Invalid type. Use /task_start to pick from the list.")
        return await _begin(update, context, ttype)

    # No arg → show inline keyboard
    await update.message.reply_text(
        "Select a study task:",
        reply_markup=_keyboard(),
    )
    return CHOOSING

async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ttype  = TaskType(query.data)
    return await _begin(query, context, ttype)

async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = context.user_data.get("task")
    if not task:
        return await update.message.reply_text("ℹ️ No active task.")
    elapsed = task["elapsed"]
    if not task["is_paused"]:
        elapsed += _now() - task["start"]
    await update.message.reply_text(
        f"⏱️ {_human(elapsed)} elapsed on {task['type'].replace('_', ' ').title()}"
        + (" (paused)" if task["is_paused"] else "")
    )

async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = context.user_data.get("task")
    if not task or task["is_paused"]:
        return await update.message.reply_text("ℹ️ No running task to pause.")
    task["elapsed"] += _now() - task["start"]
    task["is_paused"] = True
    await update.message.reply_text("⏸️ Paused.")

async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = context.user_data.get("task")
    if not task or not task["is_paused"]:
        return await update.message.reply_text("ℹ️ No paused task to resume.")
    task["start"] = _now()
    task["is_paused"] = False
    await update.message.reply_text("▶️ Resumed.")

async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = context.user_data.pop("task", None)
    if not task:
        return await update.message.reply_text("ℹ️ No task to stop.")
    total = task["elapsed"]
    if not task["is_paused"]:
        total += _now() - task["start"]
    await update.message.reply_text(
        f"✅ Logged {_human(total)} on {task['type'].replace('_', ' ').title()}."
    )
    # TODO: store to DB for streaks / summaries

# ────────────────── registration helper ─────────────────────
def register_handlers(app: Application):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("task_start", task_start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(preset_chosen),
                # allow these even while keyboard is open
                CommandHandler("task_start",  task_start),
                CommandHandler("task_pause",  task_pause),
                CommandHandler("task_resume", task_resume),
                CommandHandler("task_stop",   task_stop),
                CommandHandler("task_status", task_status),
            ],
        },
        fallbacks=[],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,           # re-issue /task_start any time
    )

    app.add_handler(wizard)
    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
