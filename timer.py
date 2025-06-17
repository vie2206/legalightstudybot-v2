import asyncio
import time
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# In-memory storage
active_timers: Dict[int, asyncio.Task] = {}
timer_info:   Dict[int, Dict[str, float]] = {}

async def timer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /timer <name> <study_min> <break_min>
    Starts a named study session with live countdown.
    """
    chat_id = update.effective_chat.id
    args    = context.args or []

    if len(args) < 3:
        return await update.message.reply_text(
            "❌ Usage: /timer <session_name> <study_min> <break_min>\n"
            "Example: /timer Math 25 5"
        )

    session_name = args[0]
    try:
        work = int(args[1])
        brk  = int(args[2])
    except ValueError:
        return await update.message.reply_text(
            "❌ Minutes must be whole numbers.\nExample: /timer Math 25 5"
        )

    # Cancel existing
    if chat_id in active_timers:
        active_timers[chat_id].cancel()

    # Store metadata
    timer_info[chat_id] = {
        "session":        session_name,
        "phase":          "study",
        "study_duration": work * 60,
        "break_duration": brk  * 60,
        "remaining":      work * 60,
        "start":          time.time(),
    }

    await update.message.reply_text(
        f"🟢 Started '{session_name}': {work}m study → {brk}m break."
    )
    # Launch countdown task
    asyncio.create_task(_run_phase(chat_id, context))

async def timer_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pauses the active session."""
    chat_id = update.effective_chat.id
    meta    = timer_info.get(chat_id)
    task    = active_timers.pop(chat_id, None)

    if not meta or not task:
        return await update.message.reply_text("ℹ️ No active session to pause.")

    # Update remaining and cancel
    elapsed           = time.time() - meta["start"]
    meta["remaining"] = max(0, meta["remaining"] - elapsed)
    task.cancel()
    await update.message.reply_text(
        f"⏸️ Paused '{meta['session']}': {int(meta['remaining']//60)}m {int(meta['remaining']%60)}s left."
    )

async def timer_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumes a paused session."""
    chat_id = update.effective_chat.id
    meta    = timer_info.get(chat_id)

    if not meta or chat_id in active_timers:
        return await update.message.reply_text("ℹ️ No paused session to resume.")

    meta["start"] = time.time()
    phase          = meta["phase"].capitalize()
    await update.message.reply_text(
        f"▶️ Resumed '{meta['session']}' ({phase}): 
