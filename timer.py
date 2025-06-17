# timer.py
"""
Interactive Pomodoro timer with inline-keyboard presets **and** classic
/ commands for pause / resume / stop / status.
"""

import asyncio
import time
from typing import Dict, Tuple

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ──────────────────────────────────────────────────────────────────────
# STATE KEYS for ConversationHandler
CHOOSING, ASK_WORK, ASK_BREAK = range(3)

# in-memory per-chat storage
active_timers: Dict[int, asyncio.Task] = {}
timer_info: Dict[int, Dict[str, float]] = {}

# ──────────────────────────────────────────────────────────────────────
# Helpers
def _mins_to_seconds(m: int) -> int:
    return max(1, m) * 60


# ──────────────────────────────────────────────────────────────────────
# Inline-keyboard wizard
async def timer_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry-point: /timer → show preset choices."""
    kb = [
        [
            InlineKeyboardButton("Pomodoro 25 | 5", callback_data="25|5"),
            InlineKeyboardButton("Focus 50 | 10",   callback_data="50|10"),
        ],
        [InlineKeyboardButton("Custom  ➕", callback_data="custom")],
    ]
    await update.message.reply_text(
        "Choose a preset or tap *Custom ➕*:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return CHOOSING


async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped a preset button → start immediately."""
    query = update.callback_query
    await query.answer()
    work, brk = map(int, query.data.split("|"))
    return await _begin_timer(query, context, work, brk)


async def custom_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for custom work minutes."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter work minutes (e.g. 30):")
    return ASK_WORK


async def work_minutes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["work"] = int(update.message.text)
    await update.message.reply_text("Break minutes?")
    return ASK_BREAK


async def break_minutes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    work = context.user_data["work"]
    brk = int(update.message.text)
    return await _begin_timer(update, context, work, brk)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Timer setup cancelled.")
    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────
# Core logic
async def _begin_timer(
    msg_or_query, context: ContextTypes.DEFAULT_TYPE, work_min: int, break_min: int
) -> int:
    """Create metadata & launch stopwatch loop (for preset OR custom)."""
    # works for Update.message **or** CallbackQuery
    if hasattr(msg_or_query, "message") and msg_or_query.message:  # CallbackQuery
        chat = msg_or_query.message.chat
    else:  # Update with message
        chat = msg_or_query.effective_chat
    chat_id = chat.id

    # cancel existing
    task = active_timers.pop(chat_id, None)
    if task:
        task.cancel()

    timer_info[chat_id] = meta = {
        "session": "Study",
        "phase": "work",
        "work_duration": _mins_to_seconds(work_min),
        "break_duration": _mins_to_seconds(break_min),
        "remaining": _mins_to_seconds(work_min),
        "start": time.time(),
    }

    await context.bot.send_message(
        chat_id,
        f"🟢 *{meta['session']}* started.  Stopwatch running…\n"
        "Use /task_pause or /task_stop.",
        parse_mode="Markdown",
    )
    _launch_task(chat_id, context)

    return ConversationHandler.END


def _launch_task(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    meta = timer_info[chat_id]

    async def run_phase():
        try:
            end_time = time.time() + meta["remaining"]
            while True:
                remain = int(end_time - time.time())
                if remain <= 0:
                    break
                m, s = divmod(remain, 60)
                icon = "📚" if meta["phase"] == "work" else "☕"
                await asyncio.sleep(5)

            # switch phases
            if meta["phase"] == "work":
                meta["phase"] = "break"
                meta["remaining"] = meta["break_duration"]
                meta["start"] = time.time()
                await context.bot.send_message(
                    chat_id, f"⏰ Time for a {meta['break_duration']//60}-min break!"
                )
                _launch_task(chat_id, context)
            else:
                await context.bot.send_message(chat_id, "✅ Session complete!")
                active_timers.pop(chat_id, None)
                timer_info.pop(chat_id, None)

        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(run_phase())
    active_timers[chat_id] = task


# ──────────────────────────────────────────────────────────────────────
# Classic /commands (pause / resume / stop / status)
async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _do_pause_resume(update.effective_chat.id, pause=True, bot=context.bot)


async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _do_pause_resume(update.effective_chat.id, pause=False, bot=context.bot)


def _do_pause_resume(chat_id: int, pause: bool, bot):
    task = active_timers.get(chat_id)
    meta = timer_info.get(chat_id)
    if not meta:
        return
    if pause and task:
        elapsed = time.time() - meta["start"]
        meta["remaining"] = max(0, meta["remaining"] - elapsed)
        task.cancel()
        active_timers.pop(chat_id, None)
        asyncio.create_task(
            bot.send_message(chat_id, "⏸️ Paused.  Use /task_resume to continue.")
        )
    elif not pause and not task:
        meta["start"] = time.time()
        _launch_task(chat_id, bot._application)
        asyncio.create_task(bot.send_message(chat_id, "▶️ Resumed."))


async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = active_timers.pop(chat_id, None)
    timer_info.pop(chat_id, None)
    if task:
        task.cancel()
    await update.message.reply_text("🚫 Task cancelled.")


async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meta = timer_info.get(update.effective_chat.id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active task.")
    elapsed = time.time() - meta["start"]
    remaining = max(0, meta["remaining"] - elapsed)
    m, s = divmod(int(remaining), 60)
    await update.message.reply_text(f"⏱ {m} m {s} s remaining.")


# ──────────────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    # Conversation wizard for /timer
    wizard = ConversationHandler(
        entry_points=[CommandHandler("timer", timer_wizard)],
        states={
            CHOOSING: [
                CallbackQueryHandler(preset_chosen, pattern=r"^\d+\|\d+$"),
                CallbackQueryHandler(custom_chosen, pattern="^custom$"),
            ],
            ASK_WORK:  [MessageHandler(filters.Regex(r"^\d+$"), work_minutes)],
            ASK_BREAK: [MessageHandler(filters.Regex(r"^\d+$"), break_minutes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(wizard)

    # Classic task-style commands
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
    app.add_handler(CommandHandler("task_status", task_status))
