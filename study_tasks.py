# study_tasks.py
"""
Stop-watch style study timer for preset tasks.

Commands
--------
/task_start <type>   – Start a task or tap inline buttons
/task_status         – Time elapsed so far
/task_pause          – Pause
/task_resume         – Resume
/task_stop           – Stop and log
"""

import asyncio, time
from typing import Dict, Literal

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler,
)

TASK_TYPES: tuple[str, ...] = (
    "CLAT_MOCK", "SECTIONAL", "NEWSPAPER", "EDITORIAL",
    "GK_CA", "MATHS", "LEGAL_REASONING", "LOGICAL_REASONING",
    "CLATOPEDIA", "SELF_STUDY", "ENGLISH", "STUDY_TASK",
)

# ------------------------------------------------------------------
class _Task:
    __slots__ = ("task", "start", "elapsed", "running")

    def __init__(self, task: str):
        self.task      : str   = task
        self.start     : float = time.time()
        self.elapsed   : float = 0.0      # paused time accumulated
        self.running   : bool  = True


active: Dict[int, _Task] = {}   # chat_id → _Task

# ------------------------------------------------------------------
# ───── helpers ─────────────────────────────────────────────────────
def _keyboard() -> InlineKeyboardMarkup:
    # show 3 columns of buttons
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, t in enumerate(TASK_TYPES, 1):
        row.append(InlineKeyboardButton(t.replace("_", " "), callback_data=t))
        if idx % 3 == 0:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def _elapsed_text(task: _Task) -> str:
    total = task.elapsed + (time.time() - task.start if task.running else 0)
    m, s  = divmod(int(total), 60)
    h, m  = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# ------------------------------------------------------------------
# ───── command handlers ────────────────────────────────────────────
SELECTING = 1     # conv-state for inline keyboard

async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/task_start <type> or launch keyboard."""
    chat_id = update.effective_chat.id
    if chat_id in active:
        await update.message.reply_text("⚠️ A task is already running. Use /task_stop first.")
        return ConversationHandler.END

    if context.args:
        task = context.args[0].upper()
        if task not in TASK_TYPES:
            await update.message.reply_text(f"❌ Invalid type. Choose one of: {', '.join(TASK_TYPES)}")
            return ConversationHandler.END
        return await _begin_task(update, context, task)

    # show inline keyboard
    await update.message.reply_text(
        "Pick a study task:", reply_markup=_keyboard()
    )
    return SELECTING

async def _preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task  = query.data
    return await _begin_task(query, context, task)

async def _begin_task(msg_or_query, context, task: str):
    chat_id                = msg_or_query.message.chat_id
    active[chat_id]        = _Task(task)
    await msg_or_query.message.reply_markdown(
        f"🟢 *{task.replace('_', ' ').title()}* started.  Stopwatch running…\n"
        "Use /task_pause or /task_stop."
    )
    return ConversationHandler.END

# ------------------------------------------------------------------
async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = active.get(update.effective_chat.id)
    if not task:
        return await update.message.reply_text("ℹ️ No active task.")
    state = "⏱️ Paused" if not task.running else "⏱️ Running"
    await update.message.reply_text(f"{state}: {task.task}  { _elapsed_text(task) }")

async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = active.get(chat_id)
    if not task or not task.running:
        return await update.message.reply_text("ℹ️ Nothing to pause.")
    task.elapsed += time.time() - task.start
    task.running  = False
    await update.message.reply_text(f"⏸️ Paused at { _elapsed_text(task) }")

async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = active.get(chat_id)
    if not task or task.running:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    task.start   = time.time()
    task.running = True
    await update.message.reply_text("▶️ Resumed.")

async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = active.pop(chat_id, None)
    if not task:
        return await update.message.reply_text("ℹ️ Nothing to stop.")
    # final elapsed
    if task.running:
        task.elapsed += time.time() - task.start
    total = _elapsed_text(task)
    await update.message.reply_text(f"✅ Finished *{task.task}*: _{total}_", parse_mode="Markdown")


# ------------------------------------------------------------------
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("task_start", task_start)],
        states={
            SELECTING: [CallbackQueryHandler(_preset_chosen)],
        },
        fallbacks=[],
        per_message=True,
    )
    app.add_handler(conv)

    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
