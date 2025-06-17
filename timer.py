"""
timer.py  –  Inline-keyboard Pomodoro with pause / resume / stop / status
Compatible with python-telegram-bot v20.x
"""

import asyncio, time
from typing import Dict, Union, Tuple

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ----------------- in-memory session state -----------------
active_tasks: Dict[int, asyncio.Task]    = {}   # chat_id  → asyncio.Task
meta:         Dict[int, Dict[str, float]] = {}   # chat_id  → {phase, start, remaining,…}

# ----------------- helpers -----------------
def _cid(src: Union[Update, CallbackQuery]) -> int:
    """Chat-ID from Update or CallbackQuery."""
    if isinstance(src, CallbackQuery):
        return src.message.chat.id
    return src.effective_chat.id


def _format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m} m {s:02d} s"


async def _edit_progress(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, text: str):
    msg_id = ctx.bot_data.get(f"timer_msg_{chat_id}")
    if msg_id:
        try:
            await ctx.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
        except Exception:
            pass


# ----------------- command entry (/timer) -----------------
async def timer_entry(update: Update, _: ContextTypes.DEFAULT_TYPE):
    kb = [
        [
            InlineKeyboardButton("Pomodoro 25 | 5", callback_data="preset|25|5"),
            InlineKeyboardButton("Focus 50 | 10",   callback_data="preset|50|10"),
        ],
        [InlineKeyboardButton("Custom ➕", callback_data="custom")],
    ]
    await update.message.reply_text(
        "Choose a preset or tap *Custom ➕*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ----------------- preset chosen -----------------
async def preset_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, work, brk = q.data.split("|")
    await _begin_timer(q, ctx, int(work), int(brk))


# ----------------- core: begin timer -----------------
async def _begin_timer(
    src: Union[Update, CallbackQuery],
    ctx: ContextTypes.DEFAULT_TYPE,
    work_min: int,
    break_min: int,
):
    cid          = _cid(src)
    work_sec     = work_min * 60
    break_sec    = break_min * 60

    # cancel existing
    if cid in active_tasks:
        active_tasks[cid].cancel()

    meta[cid] = {
        "phase":      "study",
        "work_sec":   work_sec,
        "break_sec":  break_sec,
        "remaining":  work_sec,
        "start":      time.time(),
    }

    # initial message (and store its id for edits)
    start_msg = (
        f"🟢 *Pomodoro* started – {work_min} m study → {break_min} m break."
    )
    if isinstance(src, CallbackQuery):
        sent = await ctx.bot.send_message(cid, start_msg, parse_mode="Markdown")
    else:
        sent = await src.message.reply_markdown(start_msg)
    ctx.bot_data[f"timer_msg_{cid}"] = sent.message_id

    # launch async loop
    task = asyncio.create_task(_run_timer_loop(cid, ctx))
    active_tasks[cid] = task


async def _run_timer_loop(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        while True:
            m = meta[cid]
            end = m["start"] + m["remaining"]
            remain = end - time.time()
            if remain <= 0:
                break

            icon  = "📚" if m["phase"] == "study" else "☕"
            phase = "Study" if m["phase"] == "study" else "Break"
            await _edit_progress(
                cid,
                ctx,
                f"{icon} *{phase}* – {_format_time(remain)} left.",
            )
            await asyncio.sleep(5)

        # phase finished
        m = meta[cid]
        if m["phase"] == "study":
            await ctx.bot.send_message(cid, "⏰ Study over – break starts!")
            m["phase"]     = "break"
            m["remaining"] = m["break_sec"]
            m["start"]     = time.time()
            await _run_timer_loop(cid, ctx)      # recurse to break phase
        else:
            await ctx.bot.send_message(cid, "✅ Break finished – session complete.")
            active_tasks.pop(cid, None)
            meta.pop(cid, None)

    except asyncio.CancelledError:
        pass  # paused / stopped


# ----------------- pause / resume / stop / status -----------------
async def timer_pause(update: Update, _: ContextTypes.DEFAULT_TYPE):
    cid = _cid(update)
    t   = active_tasks.pop(cid, None)
    m   = meta.get(cid)
    if not t:
        return await update.message.reply_text("ℹ️ No active timer.")
    t.cancel()
    m["remaining"] = max(0, m["remaining"] - (time.time() - m["start"]))
    await update.message.reply_text(f"⏸️ Paused with {_format_time(m['remaining'])} left.")


async def timer_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = _cid(update)
    if cid in active_tasks or cid not in meta:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    meta[cid]["start"] = time.time()
    task = asyncio.create_task(_run_timer_loop(cid, ctx))
    active_tasks[cid] = task
    await update.message.reply_text("▶️ Resumed.")


async def timer_stop(update: Update, _: ContextTypes.DEFAULT_TYPE):
    cid = _cid(update)
    t   = active_tasks.pop(cid, None)
    meta.pop(cid, None)
    if t:
        t.cancel()
        await update.message.reply_text("🚫 Timer cancelled.")
    else:
        await update.message.reply_text("ℹ️ No timer running.")


async def timer_status(update: Update, _: ContextTypes.DEFAULT_TYPE):
    cid = _cid(update)
    m   = meta.get(cid)
    if not m:
        return await update.message.reply_text("ℹ️ No timer running.")
    remaining = (
        max(0, m["remaining"] - (time.time() - m["start"]))
        if cid in active_tasks
        else m["remaining"]
    )
    icon  = "📚" if m["phase"] == "study" else "☕"
    phase = "Study" if m["phase"] == "study" else "Break"
    await update.message.reply_text(
        f"{icon} *{phase}* – {_format_time(remaining)} left.",
        parse_mode="Markdown",
    )


# ----------------- wire into the app -----------------
def register_handlers(app: Application):
    # inline-keyboard entry
    app.add_handler(CommandHandler("timer", timer_entry))

    # preset buttons  (pattern ^preset|)
    app.add_handler(CallbackQueryHandler(preset_chosen, pattern=r"^preset\|"))

    # classic commands
    app.add_handler(CommandHandler("timer_pause",  timer_pause))
    app.add_handler(CommandHandler("timer_resume", timer_resume))
    app.add_handler(CommandHandler("timer_stop",   timer_stop))
    app.add_handler(CommandHandler("timer_status", timer_status))
