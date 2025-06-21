# timer.py
"""
Pomodoro-style timer with inline-keyboard presets **and** classic
commands (/task_pause, /task_resume, /task_stop, /task_status).

Usage
-----
/timer               → choose preset (25|5, 50|10, Custom …)
/task_pause          → pause
/task_resume         → resume
/task_stop           → cancel
/task_status         → remaining time
"""

from __future__ import annotations
import asyncio, time
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

CHOOSING, ASK_WORK, ASK_BREAK = range(3)

active: Dict[int, asyncio.Task] = {}        # chat_id → asyncio.Task
info:   Dict[int, dict]          = {}        # chat_id → meta dict


# ───────────────────────── helpers
def _m2s(m: int) -> int:        # minutes → seconds
    return max(1, m) * 60


# ───────────────────────── wizard entry
async def timer_wizard(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    kb = [
        [
            InlineKeyboardButton("Pomodoro 25 | 5", callback_data="25|5"),
            InlineKeyboardButton("Focus 50 | 10",   callback_data="50|10"),
        ],
        [InlineKeyboardButton("Custom  ➕", callback_data="custom")],
    ]
    await upd.message.reply_text(
        "Choose a preset or tap *Custom ➕*:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return CHOOSING


# ───────────────────────── preset flow
async def preset_chosen(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = upd.callback_query
    await q.answer()
    work, brk = map(int, q.data.split("|"))
    return await _begin(q, ctx, work, brk)


async def custom_chosen(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await upd.callback_query.answer()
    await upd.callback_query.edit_message_text("Enter *work* minutes (e.g. 30):",
                                               parse_mode="Markdown")
    return ASK_WORK


async def work_minutes(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["work"] = int(upd.message.text)
    await upd.message.reply_text("Break minutes?")
    return ASK_BREAK


async def break_minutes(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    w = ctx.user_data["work"]
    b = int(upd.message.text)
    return await _begin(upd, ctx, w, b)


async def cancel(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await upd.message.reply_text("⏹️ Timer setup cancelled.")
    return ConversationHandler.END


# ───────────────────────── core begin / loop
async def _begin(src, ctx: ContextTypes.DEFAULT_TYPE, work_m: int, brk_m: int) -> int:
    chat = src.message.chat if hasattr(src, "message") and src.message else src.effective_chat
    cid  = chat.id

    # cancel existing
    t = active.pop(cid, None)
    if t: t.cancel()

    info[cid] = meta = {
        "phase": "work",
        "work":  _m2s(work_m),
        "break": _m2s(brk_m),
        "remain": _m2s(work_m),
        "start":  time.time(),
    }

    await ctx.bot.send_message(
        cid,
        f"🟢 Study started • {work_m}-min focus → {brk_m}-min break.\n"
        "Use /task_pause or /task_stop.",
    )
    _launch(cid, ctx)
    return ConversationHandler.END


def _launch(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    meta = info[cid]

    async def loop():
        try:
            end = time.time() + meta["remain"]
            while True:
                remain = int(end - time.time())
                if remain <= 0: break
                await asyncio.sleep(2)

            # phase switch
            if meta["phase"] == "work":
                meta["phase"]  = "break"
                meta["remain"] = meta["break"]
                meta["start"]  = time.time()
                await ctx.bot.send_message(cid, f"⏰ Break started ({meta['break']//60}-min).")
                _launch(cid, ctx)
            else:
                await ctx.bot.send_message(cid, "✅ Session complete!")
                active.pop(cid, None); info.pop(cid, None)
        except asyncio.CancelledError:
            pass

    active[cid] = asyncio.create_task(loop())


# ───────────────────────── classic commands
async def task_pause(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = upd.effective_chat.id
    t   = active.pop(cid, None)
    m   = info.get(cid)
    if not m or not t:
        return await upd.message.reply_text("ℹ️ No active session.")
    m["remain"] -= time.time() - m["start"]
    t.cancel()
    await upd.message.reply_text("⏸️ Paused.  /task_resume to continue.")


async def task_resume(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = upd.effective_chat.id
    if cid in active or cid not in info:
        return await upd.message.reply_text("ℹ️ Nothing to resume.")
    info[cid]["start"] = time.time()
    _launch(cid, ctx)
    await upd.message.reply_text("▶️ Resumed.")


async def task_stop(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = upd.effective_chat.id
    t   = active.pop(cid, None)
    info.pop(cid, None)
    if t: t.cancel()
    await upd.message.reply_text("🚫 Session cancelled.")


async def task_status(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = upd.effective_chat.id
    m   = info.get(cid)
    if not m:
        return await upd.message.reply_text("ℹ️ No active session.")
    rem = max(0, int(m["remain"] - (time.time() - m["start"])))
    mm, ss = divmod(rem, 60)
    phase  = "Study" if m["phase"] == "work" else "Break"
    await upd.message.reply_text(f"⏱ {phase}: {mm}m {ss}s left.")


# ───────────────────────── registration
def register_handlers(app: Application):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("timer", timer_wizard)],
        states={
            CHOOSING: [
                CallbackQueryHandler(preset_chosen, pattern=r"^\d+\|\d+$"),
                CallbackQueryHandler(custom_chosen,  pattern="^custom$"),
            ],
            ASK_WORK:  [MessageHandler(filters.Regex(r"^\d+$"), work_minutes)],
            ASK_BREAK: [MessageHandler(filters.Regex(r"^\d+$"), break_minutes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(wizard)

    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
    app.add_handler(CommandHandler("task_status", task_status))
    
