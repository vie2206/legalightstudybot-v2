# study_tasks.py
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from database import SessionLocal
from models import TaskLog
import datetime

# In‐memory map of user_id → active TaskLog.id
ACTIVE = {}

VALID_TYPES = TaskLog.TYPES  # pull in the preset list

async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    chat = update.effective_chat.id
    if user in ACTIVE:
        return await update.message.reply_text("🚫 You already have an active task. Use /task_status or /task_stop first.")
    
    if not context.args:
        types = ", ".join(VALID_TYPES)
        return await update.message.reply_text(
            "Usage: /task_start <type>\n"
            f"Valid types: {types}"
        )
    ttype = context.args[0].upper()
    if ttype not in VALID_TYPES:
        types = ", ".join(VALID_TYPES)
        return await update.message.reply_text(
            f"❌ “{ttype}” isn’t in the preset list.\nValid types: {types}"
        )
    
    db = SessionLocal()
    now = datetime.datetime.utcnow()
    log = TaskLog(
        user_id=user,
        chat_id=chat,
        task_type=ttype,
        start_ts=now,
        elapsed=0,
        paused_at=None,
        end_ts=None
    )
    db.add(log)
    db.commit()
    ACTIVE[user] = log.id
    await update.message.reply_text(f"▶️ Started **{ttype}**. Use /task_pause, /task_resume, /task_stop or /task_status.")

async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    log_id = ACTIVE.get(user)
    if not log_id:
        return await update.message.reply_text("❌ No active task to pause.")
    db = SessionLocal()
    log = db.get(TaskLog, log_id)
    if log.paused_at is None:
        now = datetime.datetime.utcnow()
        log.elapsed += int((now - log.start_ts).total_seconds())
        log.paused_at = now
        db.commit()
        await update.message.reply_text(f"⏸ Paused **{log.task_type}**. Elapsed: {log.elapsed_str()}")
    else:
        await update.message.reply_text("⚠️ Already paused.")

async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    log_id = ACTIVE.get(user)
    if not log_id:
        return await update.message.reply_text("❌ No paused task to resume.")
    db = SessionLocal()
    log = db.get(TaskLog, log_id)
    if log.paused_at:
        now = datetime.datetime.utcnow()
        log.start_ts = now
        log.paused_at = None
        db.commit()
        await update.message.reply_text(f"▶️ Resumed **{log.task_type}**. Elapsed so far: {log.elapsed_str()}")
    else:
        await update.message.reply_text("⚠️ It isn’t paused right now.")

async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    log_id = ACTIVE.pop(user, None)
    if not log_id:
        return await update.message.reply_text("❌ No active task to stop.")
    db = SessionLocal()
    log = db.get(TaskLog, log_id)
    now = datetime.datetime.utcnow()
    if log.paused_at is None:
        log.elapsed += int((now - log.start_ts).total_seconds())
    log.end_ts = now
    db.commit()
    await update.message.reply_text(f"✅ Completed **{log.task_type}**: {log.elapsed_str()}")
    
async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    log_id = ACTIVE.get(user)
    if not log_id:
        return await update.message.reply_text("ℹ️ No active task right now.")
    db = SessionLocal()
    log = db.get(TaskLog, log_id)
    await update.message.reply_text(f"⏳ **{log.task_type}**: {log.elapsed_str()} (running)")

def register_handlers(app):
    app.add_handler(CommandHandler("task_start", task_start))
    app.add_handler(CommandHandler("task_pause", task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop", task_stop))
    app.add_handler(CommandHandler("task_status", task_status))
