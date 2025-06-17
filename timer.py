# timer.py

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
    /timer <name> <study_minutes> <break_minutes>
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
        "work_duration":  work * 60,
        "break_duration": brk  * 60,
        "remaining":      work * 60,
        "start":          time.time(),
    }

    await update.message.reply_text(
        f"🟢 Started '{session_name}': {work}m study → {brk}m break."
    )
    _launch_task(chat_id, context)

async def timer_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pauses the active session."""
    chat_id = update.effective_chat.id
    meta    = timer_info.get(chat_id)
    task    = active_timers.pop(chat_id, None)

    if not meta or not task:
        return await update.message.reply_text("ℹ️ No active session to pause.")

    # Calculate remaining from start
    elapsed       = time.time() - meta["start"]
    remaining     = max(0, meta["remaining"] - elapsed)
    meta["remaining"] = remaining
    task.cancel()

    await update.message.reply_text(
        f"⏸️ Paused '{meta['session']}' with {int(remaining//60)}m {int(remaining%60)}s left."
    )

async def timer_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumes a paused session."""
    chat_id = update.effective_chat.id
    meta    = timer_info.get(chat_id)

    if not meta or chat_id in active_timers:
        return await update.message.reply_text("ℹ️ No paused session to resume.")

    meta["start"]   = time.time()
    # phase & remaining already in meta
    await update.message.reply_text(
        f"▶️ Resumed '{meta['session']}' with "
        f"{int(meta['remaining']//60)}m {int(meta['remaining']%60)}s left."
    )
    _launch_task(chat_id, context)

async def timer_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active or paused session."""
    chat_id = update.effective_chat.id
    task    = active_timers.pop(chat_id, None)
    meta    = timer_info.pop(chat_id, None)

    if task:
        task.cancel()
        await update.message.reply_text("🚫 Session canceled.")
    else:
        await update.message.reply_text("ℹ️ No active session to cancel.")

async def timer_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows remaining time."""
    chat_id = update.effective_chat.id
    meta    = timer_info.get(chat_id)
    task    = active_timers.get(chat_id)

    if not meta:
        return await update.message.reply_text("ℹ️ No session in progress.")

    if task:
        elapsed   = time.time() - meta["start"]
        remaining = max(0, meta["remaining"] - elapsed)
    else:
        remaining = meta["remaining"]

    m, s    = divmod(int(remaining), 60)
    icon    = "📚" if meta["phase"] == "study" else "☕"
    phase   = "Study" if meta["phase"] == "study" else "Break"
    session = meta["session"]

    await update.message.reply_text(
        f"{icon} {phase} '{session}': {m}m {s}s remaining."
    )

def _launch_task(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Internal: start countdown for current phase and auto-transition."""
    meta = timer_info[chat_id]

    async def run_phase():
        try:
            # countdown loop
            end_time = time.time() + meta["remaining"]
            while True:
                remain = end_time - time.time()
                if remain <= 0:
                    break
                m, s = divmod(int(remain), 60)
                icon = "📚" if meta["phase"] == "study" else "☕"
                text = (
                    f"{icon} {meta['phase'].capitalize()} '{meta['session']}': "
                    f"{m}m {s}s remaining."
                )
                try:
                    # edit last message
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=context.bot_data.get(f"msg_{chat_id}", None),
                        text=text
                    )
                except:
                    pass
                await asyncio.sleep(5)

            # phase-end
            if meta["phase"] == "study":
                # move to break
                await context.bot.send_message(
                    chat_id,
                    f"⏰ Study '{meta['session']}' over! "
                    f"Break for {meta['break_duration']//60}m begins."
                )
                meta["phase"]     = "break"
                meta["remaining"] = meta["break_duration"]
                meta["start"]     = time.time()
                _launch_task(chat_id, context)

            else:
                # break over
                await context.bot.send_message(
                    chat_id,
                    f"✅ Break over! '{meta['session']}' complete."
                )
                active_timers.pop(chat_id, None)
                timer_info.pop(chat_id, None)

        except asyncio.CancelledError:
            # exit cleanly on pause/stop
            pass

    # send or reuse a single message to edit
    initial = await context.bot.send_message(
        chat_id, "⏳ Starting countdown..."
    )
    context.bot_data[f"msg_{chat_id}"] = initial.message_id

    task = asyncio.create_task(run_phase())
    active_timers[chat_id] = task

def register_handlers(app):
    app.add_handler(CommandHandler("timer",         timer_start))
    app.add_handler(CommandHandler("timer_pause",   timer_pause))
    app.add_handler(CommandHandler("timer_resume",  timer_resume))
    app.add_handler(CommandHandler("timer_status",  timer_status))
    app.add_handler(CommandHandler("timer_stop",    timer_stop))
