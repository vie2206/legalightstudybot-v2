"""
Interactive Pomodoro timer.

• /timer   → inline-keyboard presets (25-5, 50-10, Custom ➕)
• /task_pause   /task_resume   /task_stop   /task_status
"""

import asyncio, time
from typing import Dict

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters
)

# ───────── conversation states ─────────
CHOOSING, ASK_WORK, ASK_BREAK = range(3)

# ───────── per-chat runtime storage ─────────
active_timers: Dict[int, asyncio.Task] = {}
timer_meta:    Dict[int, Dict]         = {}

# ────────────────────────────────────────────
def _mins_to_sec(m: int) -> int:
    """Clamp to ≥1 sec so tiny inputs don’t explode."""
    return max(1, m) * 60


# ╭──────────────────────────────────────╮
# │  Inline-keyboard wizard entry point  │
# ╰──────────────────────────────────────╯
async def timer_entry(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    kb = [
        [
            InlineKeyboardButton("Pomodoro 25 | 5", callback_data="25|5"),
            InlineKeyboardButton("Focus 50 | 10",   callback_data="50|10"),
        ],
        [InlineKeyboardButton("Custom  ➕", callback_data="custom")]
    ]
    await update.message.reply_text(
        "Choose a preset or tap *Custom ➕*:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return CHOOSING


# ───────── preset chosen ─────────
async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    work, brk = map(int, q.data.split("|"))
    return await _begin_timer(q, context, work, brk)


# ───────── custom path ─────────
async def preset_custom(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Enter *work* minutes (e.g. 30):", parse_mode="Markdown")
    return ASK_WORK


async def custom_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.text.isdigit():
        await update.message.reply_text("Numbers only – try again:")
        return ASK_WORK
    context.user_data["work"] = int(update.message.text)
    await update.message.reply_text("Break minutes?")
    return ASK_BREAK


async def custom_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.text.isdigit():
        await update.message.reply_text("Numbers only – try again:")
        return ASK_BREAK
    work = context.user_data["work"]
    brk  = int(update.message.text)
    return await _begin_timer(update, context, work, brk)


async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Timer setup cancelled.")
    return ConversationHandler.END


# ╭──────────────────────────────────────────────╮
# │  Core: create metadata & launch async loop   │
# ╰──────────────────────────────────────────────╯
async def _begin_timer(origin, context: ContextTypes.DEFAULT_TYPE,
                       work_min: int, break_min: int) -> int:
    """Works for Update *or* CallbackQuery."""
    if hasattr(origin, "effective_chat") and origin.effective_chat:
        chat = origin.effective_chat
    else:                                   # CallbackQuery.message.chat fallback
        chat = origin.message.chat
    chat_id = chat.id

    # cancel existing
    old = active_timers.pop(chat_id, None)
    if old:
        old.cancel()

    timer_meta[chat_id] = meta = {
        "phase": "work",
        "work_dur":   _mins_to_sec(work_min),
        "break_dur":  _mins_to_sec(break_min),
        "remaining":  _mins_to_sec(work_min),
        "start":      time.time(),
    }

    await context.bot.send_message(
        chat_id,
        f"🟢 *Study* started • {work_min}-min focus → {break_min}-min break.\n"
        "Use /task_pause or /task_stop.",
        parse_mode="Markdown",
    )
    _launch_loop(chat_id, context)
    return ConversationHandler.END


def _launch_loop(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    meta = timer_meta[chat_id]

    async def phase_loop():
        try:
            end = time.time() + meta["remaining"]
            while True:
                remain = int(end - time.time())
                if remain <= 0:
                    break
                await asyncio.sleep(5)

            if meta["phase"] == "work":
                # switch to break
                meta["phase"]     = "break"
                meta["remaining"] = meta["break_dur"]
                meta["start"]     = time.time()
                await context.bot.send_message(
                    chat_id, f"⏰ Focus done! Break {meta['break_dur']//60} min."
                )
                _launch_loop(chat_id, context)
            else:
                await context.bot.send_message(chat_id, "✅ Session complete!")
                active_timers.pop(chat_id, None)
                timer_meta.pop(chat_id, None)

        except asyncio.CancelledError:
            pass

    active_timers[chat_id] = asyncio.create_task(phase_loop())


# ╭────────────────────────────────────────────╮
# │  Pause / Resume / Stop / Status commands   │
# ╰────────────────────────────────────────────╯
async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task    = active_timers.pop(chat_id, None)
    meta    = timer_meta.get(chat_id)
    if not task or not meta:
        return await update.message.reply_text("ℹ️ No active task.")
    elapsed = time.time() - meta["start"]
    meta["remaining"] = max(0, meta["remaining"] - elapsed)
    task.cancel()
    await update.message.reply_text("⏸️ Paused – /task_resume to continue.")


async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_timers:
        return await update.message.reply_text("⚠️ Already running.")
    meta = timer_meta.get(chat_id)
    if not meta:
        return await update.message.reply_text("ℹ️ No paused task.")
    meta["start"] = time.time()
    _launch_loop(chat_id, context)
    await update.message.reply_text("▶️ Resumed.")


async def task_stop(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = active_timers.pop(chat_id, None)
    timer_meta.pop(chat_id, None)
    if task:
        task.cancel()
    await update.message.reply_text("🚫 Task cancelled.")


async def task_status(update: Update, _: ContextTypes.DEFAULT_TYPE):
    meta = timer_meta.get(update.effective_chat.id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active task.")
    elapsed   = time.time() - meta["start"]
    remaining = max(0, meta["remaining"] - elapsed)
    m, s      = divmod(int(remaining), 60)
    phase     = "Study" if meta["phase"] == "work" else "Break"
    await update.message.reply_text(f"⏱ {phase}: {m} m {s} s remaining.")


# ────────────────────────────────────────────
def register_handlers(app: Application):
    # wizard
    wizard = ConversationHandler(
        entry_points=[CommandHandler("timer", timer_entry)],
        states={
            CHOOSING: [
                CallbackQueryHandler(preset_chosen, pattern=r"^\d+\|\d+$"),
                CallbackQueryHandler(preset_custom,  pattern="^custom$"),
            ],
            ASK_WORK:  [MessageHandler(filters.Regex(r"^\d+$"), custom_work)],
            ASK_BREAK: [MessageHandler(filters.Regex(r"^\d+$"), custom_break)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(wizard)

    # classic commands
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
    app.add_handler(CommandHandler("task_status", task_status))
