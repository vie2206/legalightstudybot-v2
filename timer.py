# timer.py  – Pomodoro with 2-second live refresh
import asyncio, time
from typing import Dict
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters
)

CHOOSING, ASK_WORK, ASK_BREAK = range(3)

active: Dict[int, asyncio.Task]      = {}
meta:   Dict[int, dict]              = {}

def _sec(mins: int) -> int: return max(1, mins) * 60

# ── wizard entry ─────────────────────────────────────────────
async def wizard(update: Update, _: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("25 - 5", callback_data="25|5"),
         InlineKeyboardButton("50 - 10", callback_data="50|10")],
        [InlineKeyboardButton("Custom ➕", callback_data="CUST")]
    ]
    await update.message.reply_text("Pick a preset:", reply_markup=InlineKeyboardMarkup(kb))
    return CHOOSING

async def preset_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    work, brk = map(int, q.data.split("|"))
    await _start_timer(q.message.chat.id, ctx, work, brk)
    await q.edit_message_text(f"🟢 Study started • {work}-min focus → {brk}-min break.")
    return ConversationHandler.END

async def custom_cb(update: Update, _: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("Work minutes?")
    return ASK_WORK

async def ask_work(update: Update, _: ContextTypes.DEFAULT_TYPE):
    ctx = _.user_data
    ctx["work"] = int(update.message.text)
    await update.message.reply_text("Break minutes?")
    return ASK_BREAK

async def ask_break(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    work = ctx.user_data["work"]
    brk  = int(update.message.text)
    await _start_timer(update.effective_chat.id, ctx, work, brk)
    return ConversationHandler.END

async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# ── core timer ───────────────────────────────────────────────
async def _start_timer(cid: int, ctx: ContextTypes.DEFAULT_TYPE, work: int, brk: int):
    if t := active.pop(cid, None): t.cancel()
    meta[cid] = {
        "phase": "work", "work": _sec(work), "break": _sec(brk),
        "remaining": _sec(work), "start": time.time()
    }
    _run_loop(cid, ctx)

def _run_loop(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    async def loop():
        try:
            while True:
                m = meta[cid]
                now = time.time()
                left = m["remaining"] - (now - m["start"])
                if left <= 0:
                    if m["phase"] == "work":
                        await ctx.bot.send_message(cid, "⏰ Break time!")
                        m["phase"], m["remaining"], m["start"] = "break", m["break"], time.time()
                    else:
                        await ctx.bot.send_message(cid, "✅ Session complete!")
                        meta.pop(cid, None); active.pop(cid, None); break
                    left = m["remaining"]
                mins, sec = divmod(int(left), 60)
                icon = "📚" if m["phase"] == "work" else "☕"
                await ctx.bot.send_message(cid, f"{icon} {mins:02d}:{sec:02d} remaining.", disable_notification=True)
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
    active[cid] = asyncio.create_task(loop())

# ── simple commands ──────────────────────────────────────────
async def timer_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if (t := active.pop(cid, None)):
        t.cancel()
        m  = meta[cid]; m["remaining"] -= time.time() - m["start"]
        await update.message.reply_text("⏸ Paused. /timer_resume to continue.")

async def timer_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid in meta and cid not in active:
        meta[cid]["start"] = time.time()
        _run_loop(cid, ctx)
        await update.message.reply_text("▶️ Resumed.")

async def timer_stop(update: Update, _):
    cid = update.effective_chat.id
    if (t := active.pop(cid, None)): t.cancel()
    meta.pop(cid, None)
    await update.message.reply_text("🚫 Timer stopped.")

async def timer_status(update: Update, _):
    cid = update.effective_chat.id
    if cid not in meta:
        return await update.message.reply_text("ℹ️ No active timer.")
    m = meta[cid]; left = m["remaining"] - (time.time() - m["start"])
    mins, sec = divmod(int(max(0,left)), 60)
    await update.message.reply_text(f"{'📚' if m['phase']=='work' else '☕'} {mins:02d}:{sec:02d} left.")

# ── registration ─────────────────────────────────────────────
def register_handlers(app: Application):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("timer", wizard)],
        states={
            CHOOSING: [
                CallbackQueryHandler(preset_cb, pattern=r"^\d+\|\d+$"),
                CallbackQueryHandler(custom_cb, pattern="^CUST$")
            ],
            ASK_WORK:  [MessageHandler(filters.Regex(r"^\d+$"), ask_work)],
            ASK_BREAK: [MessageHandler(filters.Regex(r"^\d+$"), ask_break)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(wizard)
    app.add_handler(CommandHandler("timer_pause",  timer_pause))
    app.add_handler(CommandHandler("timer_resume", timer_resume))
    app.add_handler(CommandHandler("timer_stop",   timer_stop))
    app.add_handler(CommandHandler("timer_status", timer_status))
