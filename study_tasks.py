# study_tasks.py
"""
Stop-watch style study tasks with pause / resume / stop.
Commands
    /task_start <TYPE?>         – choose or supply one of the TASK_TYPES
    /task_status                – show elapsed time
    /task_pause                 – pause
    /task_resume                – resume
    /task_stop                  – stop & log
"""

import time
from typing import Dict, Literal

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
)

TASK_TYPES = [
    "CLAT_MOCK", "SECTIONAL", "NEWSPAPER", "EDITORIAL", "GK_CA", "MATHS",
    "LEGAL_REASONING", "LOGICAL_REASONING", "CLATOPEDIA",
    "SELF_STUDY", "ENGLISH", "STUDY_TASK",
]

# ──────────────────────────────────────────────────────────────────────────
# Simple in-memory store:  chat_id -> task-dict
active_tasks: Dict[int, Dict[str, float | str | bool]] = {}

CHOOSING = 1  # Conversation state

# ────────────────── helpers ──────────────────
def _fmt_hms(seconds: int) -> str:
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

def _keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, t in enumerate(TASK_TYPES, 1):
        row.append(InlineKeyboardButton(t, callback_data=t))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

# ────────────────── command handlers ──────────────────
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /task_start or /task_start <TYPE>
    """
    chat_id = update.effective_chat.id
    # If a task is already running – reject
    if chat_id in active_tasks and active_tasks[chat_id]["running"]:
        return await update.message.reply_text(
            "⚠️ A task is already running. Use /task_stop first."
        )

    # Immediate start when type arg supplied
    if context.args:
        task_type = context.args[0].upper()
        if task_type not in TASK_TYPES:
            return await update.message.reply_text(
                "❌ Unknown type. Valid types:\n" + ", ".join(TASK_TYPES)
            )
        await _begin_task(update, context, task_type)
        return ConversationHandler.END

    # Otherwise show chooser
    await update.message.reply_text(
        "Select your study task:", reply_markup=_keyboard()
    )
    return CHOOSING

async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_type = query.data
    # Use the CallbackQuery’s message instead of update.message
    await _begin_task(query, context, task_type)
    return ConversationHandler.END

async def _begin_task(msg_or_query, context: ContextTypes.DEFAULT_TYPE, task_type: str):
    chat_id = msg_or_query.message.chat.id
    start_ts = time.time()
    active_tasks[chat_id] = {
        "type": task_type,
        "start": start_ts,
        "elapsed": 0.0,
        "running": True,
        "paused_at": None,
    }
    await msg_or_query.message.reply_text(
        f"🟢 {task_type.replace('_', ' ').title()} started.\n"
        f"Stop-watch running…\n"
        "Use /task_pause or /task_stop."
    )

async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = active_tasks.get(chat_id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active or paused task.")
    elapsed = meta["elapsed"]
    if meta["running"]:
        elapsed += time.time() - meta["start"]
    await update.message.reply_text(
        f"⏱️ {meta['type']}: {_fmt_hms(int(elapsed))} elapsed."
    )

async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = active_tasks.get(chat_id)
    if not meta or not meta["running"]:
        return await update.message.reply_text("ℹ️ Nothing to pause.")
    meta["elapsed"] += time.time() - meta["start"]
    meta["running"] = False
    await update.message.reply_text(
        f"⏸️ Paused at {_fmt_hms(int(meta['elapsed']))}. Use /task_resume."
    )

async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = active_tasks.get(chat_id)
    if not meta or meta["running"]:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    meta["start"] = time.time()
    meta["running"] = True
    await update.message.reply_text("▶️ Resumed! Use /task_stop when done.")

async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = active_tasks.pop(chat_id, None)
    if not meta:
        return await update.message.reply_text("ℹ️ No active task to stop.")
    total = meta["elapsed"]
    if meta["running"]:
        total += time.time() - meta["start"]
    await update.message.reply_text(
        f"✅ {meta['type']} completed. Total { _fmt_hms(int(total)) }.\n"
        "Great work! 🎉"
    )
    # TODO: persist to DB if desired

# ────────────────── registration helper ──────────────────
def register_handlers(app: Application):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("task_start", task_start)],
        states={
            CHOOSING: [CallbackQueryHandler(preset_chosen)],
        },
        fallbacks=[],
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    app.add_handler(wizard)
    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
