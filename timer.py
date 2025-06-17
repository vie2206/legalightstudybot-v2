# timer.py  – interactive Pomodoro wizard
import asyncio, time
from datetime import timedelta
from typing import Dict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

# ───────────────────────── conversation states
PRESET, CUSTOM_WORK, CUSTOM_BREAK = range(3)

# ───────────────────────── in-memory tracking
active_tasks: Dict[int, asyncio.Task]   = {}
meta_info:    Dict[int, Dict]           = {}   # chat_id → dict

# ───────────────────────── presets
PRESETS = [
    ("Pomodoro 25 | 5", 25, 5),
    ("Long 50 | 10",    50, 10),
    ("Sprint 15 | 3",   15, 3),
]

# ───────────────────────── entry point
async def timer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = [[InlineKeyboardButton(txt, callback_data=f"PRESET|{w}|{b}")]
            for txt, w, b in PRESETS]
    rows.append([InlineKeyboardButton("Custom ➕", callback_data="CUSTOM")])
    await update.message.reply_text(
        "⏲️ *Choose a Pomodoro preset* (work | break):",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown",
    )
    return PRESET

# ───────────────────────── preset picked
async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    data = query.data

    if data == "CUSTOM":
        await query.edit_message_text("✏️ Send *work minutes* (e.g. `30`):", parse_mode="Markdown")
        return CUSTOM_WORK

    _, work, brk = data.split("|")
    return await _begin_timer(query, context, int(work), int(brk))

# ───────────────────────── receive custom work
async def custom_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(update.text.strip())
        if not 1 <= minutes <= 240:
            raise ValueError
        context.user_data["work"] = minutes
        await update.reply_text("✏️ Now send *break minutes* (e.g. `5`):", parse_mode="Markdown")
        return CUSTOM_BREAK
    except ValueError:
        return await update.reply_text("❌ Whole minutes 1-240, please.")

# ───────────────────────── receive custom break
async def custom_break(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        brk = int(update.text.strip())
        if not 1 <= brk <= 120:
            raise ValueError
        work = context.user_data["work"]
        return await _begin_timer(update, context, work, brk)
    except ValueError:
        return await update.reply_text("❌ Whole minutes 1-120, please.")

# ───────────────────────── helper to start task
async def _begin_timer(msg_or_query, context, work, brk):
    chat_id = msg_or_query.effective_chat.id

    # cancel previous
    if t := active_tasks.pop(chat_id, None):
        t.cancel()

    meta_info[chat_id] = {
        "phase":  "work",
        "remain": work * 60,
        "work":   work * 60,
        "break":  brk  * 60,
        "start":  time.time(),
    }

    text = f"🟢 *Work phase* started – {work} min → {brk} min break."
    if isinstance(msg_or_query, Update):
        m = await msg_or_query.reply_text(text, parse_mode="Markdown")
    else:
        m = await msg_or_query.edit_message_text(text, parse_mode="Markdown")
    context.bot_data[f"timer_msg_{chat_id}"] = m.message_id

    async def loop():
        try:
            while True:
                meta = meta_info[chat_id]
                remaining = meta["remain"] - (time.time() - meta["start"])
                if remaining <= 0:
                    # phase switch
                    if meta["phase"] == "work":
                        meta.update(phase="break", remain=meta["break"], start=time.time())
                        await context.bot.send_message(chat_id, f"☕ Break time! {brk} min.")
                    else:
                        await context.bot.send_message(chat_id, "✅ Pomodoro finished!")
                        break
                    continue

                mm, ss = divmod(int(remaining), 60)
                icon   = "📚" if meta["phase"] == "work" else "☕"
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=m.message_id,
                    text=f"{icon} {meta['phase'].capitalize()}: {mm:02d}:{ss:02d} remaining.",
                )
                await asyncio.sleep(10)
        finally:
            active_tasks.pop(chat_id, None)
            meta_info.pop(chat_id, None)

    task = asyncio.create_task(loop())
    active_tasks[chat_id] = task
    return ConversationHandler.END

# ───────────────────────── status / pause / resume / stop
async def timer_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta    = meta_info.get(chat_id)
    if not meta:
        return await update.message.reply_text("ℹ️ No active Pomodoro.")
    remain  = meta["remain"] - (time.time() - meta["start"])
    mm, ss  = divmod(int(remain), 60)
    icon    = "📚" if meta["phase"] == "work" else "☕"
    await update.message.reply_text(f"{icon} {meta['phase'].capitalize()}: {mm:02d}:{ss:02d} remaining.")

async def timer_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task    = active_tasks.get(chat_id)
    meta    = meta_info.get(chat_id)
    if not task: return await update.message.reply_text("ℹ️ Nothing to pause.")
    task.cancel(); active_tasks.pop(chat_id, None)
    meta["remain"] -= time.time() - meta["start"]
    await update.message.reply_text("⏸️ Timer paused.")

async def timer_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_tasks or chat_id not in meta_info:
        return await update.message.reply_text("ℹ️ Nothing to resume.")
    meta = meta_info[chat_id]; meta["start"] = time.time()
    async def dummy(): pass   # quick restart
    meta_info[chat_id] = meta
    active_tasks[chat_id] = asyncio.create_task(dummy())
    await update.message.reply_text("▶️ Resumed.")
    await _begin_timer(update, context, meta["work"]//60, meta["break"]//60)  # reuse wizard helper

async def timer_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if t := active_tasks.pop(chat_id, None):
        t.cancel()
    meta_info.pop(chat_id, None)
    await update.message.reply_text("🚫 Pomodoro canceled.")

# ───────────────────────── wiring to bot.py
def register_handlers(app):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("timer", timer_entry)],
        states={
            PRESET: [
                CallbackQueryHandler(preset_chosen, pattern=r"^(PRESET|CUSTOM)"),
            ],
            CUSTOM_WORK: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_work)],
            CUSTOM_BREAK:[MessageHandler(filters.TEXT & ~filters.COMMAND, custom_break)],
        },
        fallbacks=[CommandHandler("cancel", timer_stop)],
        allow_reentry=True,
    )
    app.add_handler(wizard)

    app.add_handler(CommandHandler("timer_status", timer_status))
    app.add_handler(CommandHandler("timer_pause",  timer_pause))
    app.add_handler(CommandHandler("timer_resume", timer_resume))
    app.add_handler(CommandHandler("timer_stop",   timer_stop))
