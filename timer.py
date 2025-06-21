# timer.py
"""
Interactive Pomodoro timer with inline-keyboard presets
plus classic /task_* stopwatch commands.

Refresh policy
--------------
• Default edit cadence: 2  seconds  (looks “live”)
• If > 25 timers are running at once, new timers fall back to 5 s
  to stay well under Telegram’s global-edit limit.
"""

import asyncio
import time
from typing import Dict

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

# ─────────────────────────────────────────────────────────────
# Conversation state keys
CHOOSING, ASK_WORK, ASK_BREAK = range(3)

# Per-chat runtime state
active_timers: Dict[int, asyncio.Task] = {}
timer_info: Dict[int, Dict[str, float]] = {}

# Configurable refresh interval (seconds)
REFRESH_DEFAULT = 2
REFRESH_FALLBACK = 5          # used when we have “too many” live timers
FALLBACK_THRESHOLD = 25       # # timers at which to switch to fallback

# ─────────────────────────────────────────────────────────────
def _mins(m: int) -> int:
    return max(1, m) * 60

# ─────────────────────────────────────────────────────────────
# 1) Inline-keyboard wizard ( /timer )
async def timer_wizard(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    kb = [
        [
            InlineKeyboardButton("Pomodoro 25 | 5", callback_data="25|5"),
            InlineKeyboardButton("Focus 50 | 10",   callback_data="50|10"),
        ],
        [InlineKeyboardButton("Custom ➕", callback_data="custom")],
    ]
    await update.message.reply_text(
        "Choose a preset or tap *Custom ➕*:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return CHOOSING


async def preset_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    work, brk = map(int, q.data.split("|"))
    return await _begin_timer(q.message.chat.id, ctx.bot, work, brk)


async def custom_chosen(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Enter *work* minutes (e.g. 30):", parse_mode="Markdown")
    return ASK_WORK


async def ask_work(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.text.isdigit():
        await update.message.reply_text("Numbers only – try again:")
        return ASK_WORK
    update.user_data["work_min"] = int(update.message.text)
    await update.message.reply_text("Now enter *break* minutes:", parse_mode="Markdown")
    return ASK_BREAK


async def ask_break(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.text.isdigit():
        await update.message.reply_text("Numbers only – try again:")
        return ASK_BREAK
    work = update.user_data.pop("work_min")
    brk = int(update.message.text)
    return await _begin_timer(update.effective_chat.id, ctx.bot, work, brk)


async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Timer setup cancelled.")
    return ConversationHandler.END

# ─────────────────────────────────────────────────────────────
# 2) Core logic
async def _begin_timer(chat_id: int, bot, work_min: int, break_min: int) -> int:
    # cancel existing for this chat
    old = active_timers.pop(chat_id, None)
    if old:
        old.cancel()

    timer_info[chat_id] = meta = {
        "phase": "work",
        "work_duration": _mins(work_min),
        "break_duration": _mins(break_min),
        "remaining": _mins(work_min),
        "start": time.time(),
    }

    await bot.send_message(
        chat_id,
        f"🟢 Study started • {work_min}-min focus → {break_min}-min break.\n"
        "Use /task_pause, /task_resume or /task_stop.",
    )
    _launch_task(chat_id, bot)
    return ConversationHandler.END


def _launch_task(chat_id: int, bot):
    """Spawn/respawn the per-chat countdown coroutine."""
    meta = timer_info[chat_id]

    # decide refresh interval
    refresh = (
        REFRESH_FALLBACK if len(active_timers) >= FALLBACK_THRESHOLD else REFRESH_DEFAULT
    )

    async def loop():
        try:
            end_at = time.time() + meta["remaining"]
            while True:
                left = int(end_at - time.time())
                if left <= 0:
                    break
                m, s = divmod(left, 60)
                icon = "📚" if meta["phase"] == "work" else "☕"
                await bot.send_chat_action(chat_id, "typing")
                await asyncio.sleep(refresh)

            # phase switch
            if meta["phase"] == "work":
                meta["phase"] = "break"
                meta["remaining"] = meta["break_duration"]
                meta["start"] = time.time()
                await bot.send_message(
                    chat_id, f"⏰ Focus over! Take a {meta['break_duration']//60}-min break."
                )
                _launch_task(chat_id, bot)
            else:
                await bot.send_message(chat_id, "✅ Session complete!")
                active_timers.pop(chat_id, None)
                timer_info.pop(chat_id, None)
        except asyncio.CancelledError:
            pass

    active_timers[chat_id] = asyncio.create_task(loop())

# ─────────────────────────────────────────────────────────────
# 3) Classic /task_* commands
async def _pause_resume(chat_id: int, bot, pause: bool):
    task = active_timers.get(chat_id)
    meta = timer_info.get(chat_id)
    if not meta:
        return
    if pause and task:
        elapsed = time.time() - meta["start"]
        meta["remaining"] = max(0, meta["remaining"] - elapsed)
        task.cancel(); active_timers.pop(chat_id, None)
        await bot.send_message(chat_id, "⏸️ Paused. /task_resume to continue.")
    elif not pause and not task:
        meta["start"] = time.time()
        _launch_task(chat_id, bot)
        await bot.send_message(chat_id, "▶️ Resumed.")


async def task_pause(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await _pause_resume(u.effective_chat.id, c.bot, True)


async def task_resume(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await _pause_resume(u.effective_chat.id, c.bot, False)


async def task_stop(u: Update, c: ContextTypes.DEFAULT_TYPE):
    cid = u.effective_chat.id
    t = active_timers.pop(cid, None)
    if t: t.cancel()
    timer_info.pop(cid, None)
    await u.message.reply_text("🚫 Timer cancelled.")


async def task_status(u: Update, _: ContextTypes.DEFAULT_TYPE):
    meta = timer_info.get(u.effective_chat.id)
    if not meta:
        return await u.message.reply_text("ℹ️ No active timer.")
    elapsed = time.time() - meta["start"]
    left = max(0, meta["remaining"] - elapsed)
    m, s = divmod(int(left), 60)
    await u.message.reply_text(f"⏱ {m} m {s} s left ({meta['phase']}).")

# ─────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    # wizard for /timer
    wizard = ConversationHandler(
        entry_points=[CommandHandler("timer", timer_wizard)],
        states={
            CHOOSING: [
                CallbackQueryHandler(preset_chosen, pattern=r"^\d+\|\d+$"),
                CallbackQueryHandler(custom_chosen,  pattern="^custom$"),
            ],
            ASK_WORK:  [MessageHandler(filters.Regex(r"^\d+$"), ask_work)],
            ASK_BREAK: [MessageHandler(filters.Regex(r"^\d+$"), ask_break)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(wizard)

    # classic commands
    app.add_handler(CommandHandler("task_pause",   task_pause))
    app.add_handler(CommandHandler("task_resume",  task_resume))
    app.add_handler(CommandHandler("task_stop",    task_stop))
    app.add_handler(CommandHandler("task_status",  task_status))
