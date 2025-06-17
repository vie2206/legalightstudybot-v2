# study_tasks.py  – stopwatch study sessions
import asyncio, time
from typing import Dict, Literal, Tuple

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# -----------------------------------------------------------
TYPES = (
    "CLAT_MOCK", "SECTIONAL", "NEWSPAPER", "EDITORIAL", "GK_CA",
    "MATHS", "LEGAL_REASONING", "LOGICAL_REASONING", "CLATOPEDIA",
    "SELF_STUDY", "ENGLISH", "STUDY_TASK",
)

# in-memory; replace with DB writes later
_active: Dict[int, dict] = {}  # chat_id → {type, start, paused, elapsed}

# ─────────────────────────────────────────────────────────────
def _format_elapsed(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h:02}:{m:02}:{s:02}"
    return f"{m:02}:{s:02}"

# core starter ------------------------------------------------
async def _begin(update_or_q: Update | CallbackQuery,
                 ctx: ContextTypes.DEFAULT_TYPE,
                 ttype: str):

    chat_id = update_or_q.effective_chat.id
    # finish any running task
    if chat_id in _active:
        _active.pop(chat_id)

    _active[chat_id] = {
        "type":   ttype,
        "start":  time.time(),
        "paused": False,
        "elapsed": 0.0,
    }

    # detect whether called via command or button
    send_func = (
        update_or_q.message.reply_markdown
        if isinstance(update_or_q, Update)
        else update_or_q.edit_message_text
    )

    msg = await send_func(
        f"🟢 *{ttype.replace('_', ' ').title()}* started.\n"
        "Stopwatch running…\n"
        "Use /task_pause or /task_stop.",
        parse_mode="Markdown"
    )
    ctx.chat_data["task_msg_id"] = msg.message_id

# command entry ----------------------------------------------
async def task_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if args and args[0].upper() in TYPES:
        return await _begin(update, ctx, args[0].upper())

    # show inline buttons
    rows = [
        [
            InlineKeyboardButton(t.replace('_', ' ').title(), callback_data=f"task:{t}")
            for t in TYPES[i:i+2]
        ] for i in range(0, len(TYPES), 2)
    ]
    kb = InlineKeyboardMarkup(rows)
    await update.message.reply_text("Select a study task type:", reply_markup=kb)

async def preset_chosen(query: CallbackQuery, ctx: ContextTypes.DEFAULT_TYPE):
    await query.answer()
    _, ttype = query.data.split(":")
    return await _begin(query, ctx, ttype)

# pause / resume / status / stop -----------------------------
def _get_active(chat_id: int) -> Tuple[dict | None, str]:
    meta = _active.get(chat_id)
    if not meta:
        return None, "ℹ️ No active task."

    if meta["paused"]:
        elapsed = meta["elapsed"]
    else:
        elapsed = meta["elapsed"] + (time.time() - meta["start"])
    return meta, _format_elapsed(elapsed)

async def task_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    meta, txt = _get_active(update.effective_chat.id)
    if not meta:
        await update.message.reply_text(txt)
        return
    await update.message.reply_text(
        f"⏱️ {meta['type'].replace('_',' ').title()} – {txt}"
    )

async def task_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = _active.get(chat_id)
    if not meta or meta["paused"]:
        return await update.message.reply_text("ℹ️ Nothing running to pause.")
    meta["elapsed"] += time.time() - meta["start"]
    meta["paused"]  = True
    await update.message.reply_text("⏸️ Paused.")

async def task_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta = _active.get(chat_id)
    if not meta or not meta["paused"]:
        return await update.message.reply_text("ℹ️ No paused task to resume.")
    meta["start"]  = time.time()
    meta["paused"] = False
    await update.message.reply_text("▶️ Resumed.")

async def task_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta, txt = _get_active(chat_id)
    if not meta:
        return await update.message.reply_text(txt)
    _active.pop(chat_id, None)
    await update.message.reply_markdown(
        f"✅ *{meta['type'].replace('_',' ').title()}* finished.\nTotal time: {txt}"
    )

# ─────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    app.add_handler(CommandHandler("task_start",  task_start))
    app.add_handler(CallbackQueryHandler(preset_chosen, pattern=r"^task:"))
    app.add_handler(CommandHandler("task_status", task_status))
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
