# study_tasks.py  – interactive task picker
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

TASK_TYPES = [
    "CLAT_MOCK", "SECTIONAL", "NEWSPAPER", "EDITORIAL",
    "GK_CA", "MATHS", "LEGAL_REASONING", "LOGICAL_REASONING",
    "CLATOPEDIA", "SELF_STUDY", "ENGLISH", "STUDY_TASK",
]

# ───────────────────────────────────────────────
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin asking user which task type they want."""
    if context.args:
        # Old behaviour still works for power-users
        return await _begin_task(update, context, " ".join(context.args).upper())

    # Show a reply-keyboard with 12 buttons (2 rows × 6)
    rows = [TASK_TYPES[i:i+3] for i in range(0, len(TASK_TYPES), 3)]
    kb   = ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "📝 Select the task you’re about to start:", reply_markup=kb
    )
    return 1  # go to "choice" state


async def task_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.upper().strip()
    if choice not in TASK_TYPES:
        return await update.message.reply_text("❌ Please tap one of the buttons.")

    # Remove keyboard, start task
    await update.message.reply_text("✅ Got it!", reply_markup=ReplyKeyboardRemove())
    return await _begin_task(update, context, choice)


async def _begin_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_type: str):
    # <existing stopwatch code you already have>
    from datetime import datetime
    context.chat_data["task"] = {
        "type":   task_type,
        "start":  datetime.utcnow(),
        "paused": False,
        "elapsed": 0,
    }
    await update.message.reply_text(f"⏱ Stopwatch started for *{task_type}*.", parse_mode="Markdown")

# ────────────────────── conversation wiring
from telegram.ext import ConversationHandler

def register_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("task_start", task_start)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_choice)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # keep your existing /task_status /task_pause … handlers
