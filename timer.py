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
    m, s = divmod(int(meta["remaining"]), 60)
    await update.message.reply_text(
        f"⏸️ Paused '{meta['session']}': {m}m {s}s left."
    )

async def timer_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumes a paused session."""
    chat_id = update.effective_chat.id
    meta    = timer_info.get(chat_id)

    if not meta or chat_id in active_timers:
        return await update.message.reply_text("ℹ️ No paused session to resume.")

    meta["start"] = time.time()
    remaining      = meta["remaining"]
    m, s = divmod(int(remaining), 60)
    await update.message.reply_text(
        f"▶️ Resumed '{meta['session']}' ({meta['phase'].capitalize()}): {m}m {s}s left."
    )
    asyncio.create_task(_run_phase(chat_id, context))

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
    """Shows remaining time and phase."""
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

    m, s = divmod(int(remaining), 60)
    icon       = "📚" if meta["phase"] == "study" else "☕"
    phase_name = "Study" if meta["phase"] == "study" else "Break"
    await update.message.reply_text(
        f"{icon} {phase_name} '{meta['session']}': {m}m {s}s remaining."
    )

async def _run_phase(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Internal: countdown loop for current phase, then auto-transition."""
    meta = timer_info.get(chat_id)
    if not meta:
        return
    task = asyncio.current_task()
    active_timers[chat_id] = task

    try:
        end_time = time.time() + meta["remaining"]
        # send initial or reuse
        msg = await context.bot.send_message(
            chat_id,
            f"{('📚' if meta['phase']=='study' else '☕')} "
            f"{meta['phase'].capitalize()} '{meta['session']}': {int(meta['remaining']//60)}m {int(meta['remaining']%60)}s remaining."
        )
        msg_id = msg.message_id

        while True:
            remain = end_time - time.time()
            if remain <= 0:
                break
            m, s = divmod(int(remain), 60)
            text = (
                f"{('📚' if meta['phase']=='study' else '☕')} "
                f"{meta['phase'].capitalize()} '{meta['session']}': {m}m {s}s remaining."
            )
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text
                )
            except Exception:
                pass
            await asyncio.sleep(5)

        # Phase ends
        if meta["phase"] == "study":
            await context.bot.send_message(
                chat_id,
                f"⏰ Study '{meta['session']}' over! Break for {meta['break_duration']//60}m starts."
            )
            meta["phase"]    = "break"
            meta["remaining"] = meta["break_duration"]
            meta["start"]     = time.time()
            await _run_phase(chat_id, context)
        else:
            await context.bot.send_message(
                chat_id,
                f"✅ Break over! '{meta['session']}' complete."
            )
            timer_info.pop(chat_id, None)
            active_timers.pop(chat_id, None)

    except asyncio.CancelledError:
        pass


def register_handlers(app):
    app.add_handler(CommandHandler("timer",        timer_start))
    app.add_handler(CommandHandler("timer_pause",  timer_pause))
    app.add_handler(CommandHandler("timer_resume", timer_resume))
    app.add_handler(CommandHandler("timer_status", timer_status))
    app.add_handler(CommandHandler("timer_stop",   timer_stop))
