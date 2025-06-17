# study_tasks.py  – UPDATED
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

PRESET, RUNNING = range(2)

PRESETS = [
    ("CLAT_MOCK",           "CLAT mock"),
    ("SECTIONAL",           "Sectional test"),
    ("NEWSPAPER",           "Read newspaper"),
    ("EDITORIAL",           "Editorial Express"),
    ("GK_CA",               "GK & CA"),
    ("MATHS",               "Maths"),
    ("LEGAL_REASONING",     "Legal Reasoning"),
    ("LOGICAL_REASONING",   "Logical Reasoning"),
    ("CLATOPEDIA",          "CLATopedia"),
    ("SELF_STUDY",          "Self-study"),
    ("ENGLISH",             "English"),
    ("STUDY_TASK",          "Other task"),
]

# ──────────────────────────────────────────────────────────────
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb = [
        [InlineKeyboardButton(lbl, callback_data=code)]
        for code, lbl in PRESETS
    ]
    await update.message.reply_text(
        "Select a study task:",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return PRESET


async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    task_code = query.data
    context.user_data["task_code"] = task_code
    context.user_data["start_time"] = context.application.time()
    await query.edit_message_text(f"🟢 *{task_code}* stopwatch started!", parse_mode="Markdown")
    return RUNNING


async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = context.user_data.get("start_time")
    if not start:
        return await update.message.reply_text("No active task.")
    elapsed = int(context.application.time() - start)
    mins, secs = divmod(elapsed, 60)
    await update.message.reply_text(f"⏱ {mins}m {secs}s elapsed.")

async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "start_time" not in context.user_data:
        return await update.message.reply_text("No active task.")
    context.user_data["paused_at"] = context.application.time()
    await update.message.reply_text("⏸ Paused.")

async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    paused = context.user_data.pop("paused_at", None)
    if not paused:
        return await update.message.reply_text("Not paused.")
    # shift the start_time forward by pause duration
    context.user_data["start_time"] += context.application.time() - paused
    await update.message.reply_text("▶️ Resumed.")

async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = context.user_data.pop("start_time", None)
    if not start:
        return await update.message.reply_text("No active task.")
    elapsed = int(context.application.time() - start)
    mins, secs = divmod(elapsed, 60)
    code = context.user_data.pop("task_code", "TASK")
    await update.message.reply_text(f"✅ *{code}* finished — {mins}m {secs}s logged.", parse_mode="Markdown")
    return ConversationHandler.END


def register_handlers(app):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("task_start", task_start)],
        states={
            PRESET:  [CallbackQueryHandler(preset_chosen)],
            RUNNING: [
                CommandHandler("task_status", task_status),
                CommandHandler("task_pause",  task_pause),
                CommandHandler("task_resume", task_resume),
                CommandHandler("task_stop",   task_stop),
            ],
        },
        fallbacks=[CommandHandler("task_stop", task_stop)],
        per_user=True,
    )
    app.add_handler(wizard)
