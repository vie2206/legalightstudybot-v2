# study_tasks.py
# Module to handle the /task_* commands for stopwatch-style study tasks

import time
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# In-memory store for user tasks: {user_id: meta_dict}
tasks: dict[int, dict] = {}

# Valid types (should mirror bot.py)
VALID_TASK_TYPES = [
    'CLAT_MOCK', 'SECTIONAL', 'NEWSPAPER', 'EDITORIAL', 'GK_CA', 'MATHS',
    'LEGAL_REASONING', 'LOGICAL_REASONING', 'CLATOPEDIA', 'SELF_STUDY',
    'ENGLISH', 'STUDY_TASK'
]

# Helper to format seconds into H:M:S
def format_duration(seconds: float) -> str:
    secs = int(seconds)
    hrs, secs = divmod(secs, 3600)
    mins, secs = divmod(secs, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /task_start <type>\n" +
            "Valid types: " + ", ".join(VALID_TASK_TYPES)
        )
        return
    task_type = context.args[0].upper()
    if task_type not in VALID_TASK_TYPES:
        await update.message.reply_text(
            f"❌ '{task_type}' is not a valid task.\n" +
            "Use /help to see valid types."
        )
        return
    # Start or restart the task
    tasks[user_id] = {
        'type': task_type,
        'start': time.time(),
        'elapsed': 0.0,
        'paused': False
    }
    await update.message.reply_text(f"▶️ Started '{task_type}'. Good luck! (00:00:00)")

async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    meta = tasks.get(user_id)
    if not meta:
        await update.message.reply_text("ℹ️ No active task. Use /task_start to begin.")
        return
    if meta['paused']:
        elapsed = meta['elapsed']
    else:
        elapsed = meta['elapsed'] + (time.time() - meta['start'])
    await update.message.reply_text(
        f"⏱️ '{meta['type']}' elapsed: {format_duration(elapsed)}"
    )

async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    meta = tasks.get(user_id)
    if not meta:
        await update.message.reply_text("ℹ️ No active task to pause.")
        return
    if meta['paused']:
        await update.message.reply_text("ℹ️ Task is already paused.")
        return
    # Pause it
    now = time.time()
    meta['elapsed'] += (now - meta['start'])
    meta['paused'] = True
    await update.message.reply_text(
        f"⏸️ Paused '{meta['type']}' at {format_duration(meta['elapsed'])}."
    )

async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    meta = tasks.get(user_id)
    if not meta:
        await update.message.reply_text("ℹ️ No paused task to resume.")
        return
    if not meta['paused']:
        await update.message.reply_text("ℹ️ Task is already running.")
        return
    # Resume
    meta['start'] = time.time()
    meta['paused'] = False
    await update.message.reply_text(f"▶️ Resumed '{meta['type']}' ({format_duration(meta['elapsed'])}).")

async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    meta = tasks.pop(user_id, None)
    if not meta:
        await update.message.reply_text("ℹ️ No active task to stop.")
        return
    if not meta['paused']:
        # finish running segment
        meta['elapsed'] += (time.time() - meta['start'])
    duration = format_duration(meta['elapsed'])
    # TODO: log to database here
    await update.message.reply_text(
        f"✅ Completed '{meta['type']}' — Duration: {duration}. Well done!"
    )

# Register all handlers on the Application

def register_handlers(app):
    app.add_handler(CommandHandler("task_start", task_start))
    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause", task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop", task_stop))
