# timer.py
"""
Interactive Pomodoro timer:
  • /timer         – inline wizard with presets + custom
  • /timer_pause   /timer_resume /timer_stop /timer_status
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

# ────────────────────────────── state constants
CHOOSING, ASK_WORK, ASK_BREAK = range(3)

# in-memory per-chat storage
active: Dict[int, asyncio.Task] = {}      # chat_id → asyncio.Task
meta:   Dict[int, dict]          = {}      # chat_id → session metadata


# ────────────────────────────── helpers
def _mins(m: int) -> int: return max(1, m) * 60


def _remaining(m: dict) -> int:
    """seconds left in current phase"""
    return max(0, int(m["end_time"] - time.time()))


def _fmt(sec: int) -> Tuple[int, int]:
    m, s = divmod(sec, 60)
    return m, s


# ────────────────────────────── wizard entry
async def wizard_entry(update: Update, _ctx):
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


# ────────────────────────────── preset flow
async def preset_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    work, brk = map(int, q.data.split("|"))
    await _begin_session(q.message.chat.id, ctx, work, brk)
    await q.edit_message_text("✅ Preset started!")
    return ConversationHandler.END


# ────────────────────────────── custom flow
async def custom_chosen(update: Update, _ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Work minutes?")
    return ASK_WORK


async def ask_break(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["work"] = int(update.message.text)
    await update.message.reply_text("Break minutes?")
    return ASK_BREAK


async def custom_finish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    work = ctx.user_data["work"]
    brk  = int(update.message.text)
    await _begin_session(update.effective_chat.id, ctx, work, brk)
    return ConversationHandler.END


# ────────────────────────────── core session logic
async def _begin_session(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE,
                         work_min: int, break_min: int):
    # cancel previous
    if task := active.pop(chat_id, None):
        task.cancel()

    meta[chat_id] = m = {
        "phase": "work",
        "work_dur":  _mins(work_min),
        "break_dur": _mins(break_min),
        "end_time":  time.time() + _mins(work_min),
    }

    await ctx.bot.send_message(
        chat_id,
        f"🟢 Study started • {work_min}-min focus → {break_min}-min break.\n"
        "Use /timer_pause or /timer_stop."
    )

    async def loop():
        try:
            while True:
                if _remaining(m) == 0:
                    # phase switch
                    if m["phase"] == "work":
                        m["phase"] = "break"
                        m["end_time"] = time.time() + m["break_dur"]
                        await ctx.bot.send_message(chat_id, "⏰ Break time!")
                    else:
                        await ctx.bot.send_message(chat_id, "✅ Session complete!")
                        break
                await asyncio.sleep(5)
        finally:
            active.pop(chat_id, None)
            meta.pop(chat_id, None)

    active[chat_id] = asyncio.create_task(loop())


# ────────────────────────────── pause / resume / stop / status
async def pause(update: Update, _ctx):
    cid = update.effective_chat.id
    if cid not in meta or cid not in active:
        return await update.message.reply_text("ℹ️ Nothing to pause.")
    remaining = _remaining(meta[cid])
    active[cid].cancel()
    meta[cid]["pause_left"] = remaining
    await update.message.reply_text("⏸️ Paused.")


async def resume(update: Update, ctx):
    cid = update.effective_chat.id
    m = meta.get(cid)
    if not m or cid in active:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    m["end_time"] = time.time() + m.pop("pause_left")
    async def loop_wrap(): await _begin_session(cid, ctx, m["work_dur"]//60, m["break_dur"]//60)
    # reuse the same loop logic
    active[cid] = asyncio.create_task(loop_wrap())
    await update.message.reply_text("▶️ Resumed.")


async def stop(update: Update, _ctx):
    cid = update.effective_chat.id
    if task := active.pop(cid, None):
        task.cancel()
    meta.pop(cid, None)
    await update.message.reply_text("🚫 Timer cancelled.")


async def status(update: Update, _ctx):
    cid = update.effective_chat.id
    m = meta.get(cid)
    if not m:
        return await update.message.reply_text("ℹ️ No active timer.")
    mins, secs = _fmt(_remaining(m))
    phase = "Focus" if m["phase"] == "work" else "Break"
    await update.message.reply_text(f"⏱ {phase}: {mins} m {secs} s remaining.")


# ────────────────────────────── registration
def register_handlers(app: Application):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("timer", wizard_entry)],
        states={
            CHOOSING: [
                CallbackQueryHandler(preset_chosen, pattern=r"^\d+\|\d+$"),
                CallbackQueryHandler(custom_chosen,  pattern="^custom$"),
            ],
            ASK_WORK:  [MessageHandler(filters.Regex(r"^\d+$"), ask_break)],
            ASK_BREAK: [MessageHandler(filters.Regex(r"^\d+$"), custom_finish)],
        },
        fallbacks=[CommandHandler("cancel", stop)],   # required
        per_chat=True,
    )
    app.add_handler(wizard)

    app.add_handler(CommandHandler("timer_status", status))
    app.add_handler(CommandHandler("timer_pause",  pause))
    app.add_handler(CommandHandler("timer_resume", resume))
    app.add_handler(CommandHandler("timer_stop",   stop))
