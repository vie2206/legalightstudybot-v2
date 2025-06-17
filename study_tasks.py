# study_tasks.py
#
# Stopwatch-style study task tracker with inline-keyboard presets
# Commands: /task_start, /task_status, /task_pause, /task_resume, /task_stop
# ──────────────────────────────────────────────────────────────────────────────
import asyncio, time
from enum import Enum, auto
from typing import Dict, Optional

from telegram import (
    Update,
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as Mk,
    CallbackQuery,
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ────────────── preset task types ──────────────
TASK_TYPES = [
    "CLAT_MOCK", "SECTIONAL", "NEWSPAPER", "EDITORIAL", "GK_CA", "MATHS",
    "LEGAL_REASONING", "LOGICAL_REASONING", "CLATOPEDIA", "SELF_STUDY",
    "ENGLISH", "STUDY_TASK",
]

# ────────────── conversation states ──────────────
class S(Enum):
    CHOOSE = auto()
    CUSTOM = auto()

# ────────────── in-memory timers ──────────────
active_tasks: Dict[int, asyncio.Task]   = {}  # chat_id → asyncio task
task_meta:    Dict[int, Dict[str, any]] = {}  # chat_id → metadata

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
async def _count_loop(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Background coroutine that ticks every second and live-edits the message."""
    meta = task_meta[chat_id]
    msg_id: Optional[int] = meta.get("msg_id")

    try:
        while True:
            elapsed = int(time.time() - meta["start"])
            h, rem  = divmod(elapsed, 3600)
            m, s    = divmod(rem, 60)
            txt     = f"⏱️ {meta['type']} • {h:02d}:{m:02d}:{s:02d}"

            if msg_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id, msg_id, txt
                    )
                except:  # message might be out of date – ignore
                    pass
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass  # graceful cancel

async def _begin(update_or_q, context: ContextTypes.DEFAULT_TYPE, ttype: str):
    """Starts (or restarts) a task."""
    # ── fix: robust chat_id detection for both /task_start and callbacks ──
    if isinstance(update_or_q, CallbackQuery):
        chat_id = update_or_q.message.chat_id
        reply   = update_or_q.message.reply_text
    else:
        chat_id = update_or_q.effective_chat.id
        reply   = update_or_q.message.reply_text
    # ----------------------------------------------------------------------

    # Cancel existing task if any
    old = active_tasks.pop(chat_id, None)
    if old:
        old.cancel()

    # Send initial message
    msg = await reply(f"🟢 *{ttype.replace('_', ' ').title()}* started.\n"
                      "Stopwatch running…\nUse /task_pause or /task_stop.",
                      parse_mode="Markdown")

    # Track metadata & launch ticker
    task_meta[chat_id] = {
        "type":  ttype,
        "start": time.time(),
        "msg_id": msg.message_id,
        "paused": False,
        "elapsed_before_pause": 0,
    }
    ticker = asyncio.create_task(_count_loop(chat_id, context))
    active_tasks[chat_id] = ticker
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────────────────────
# Conversation entry: /task_start
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kbd = [
        [Btn(t, callback_data=f"TASK:{t}")]
        for t in TASK_TYPES[:6]
    ] + [
        [Btn(t, callback_data=f"TASK:{t}")]
        for t in TASK_TYPES[6:]
    ]
    await update.message.reply_text(
        "Pick a study task:",
        reply_markup=Mk(kbd)
    )
    return S.CHOOSE

async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("TASK:"):
        return ConversationHandler.END
    _, ttype = query.data.split(":", maxsplit=1)
    return await _begin(query, context, ttype)

# ──────────────────────────────────────────────────────────────────────────────
# Pause / resume / stop / status
async def task_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ticker  = active_tasks.pop(chat_id, None)
    meta    = task_meta.get(chat_id)

    if not ticker or not meta or meta["paused"]:
        return await update.message.reply_text("ℹ️ No active task to pause.")

    ticker.cancel()
    meta["paused"] = True
    meta["elapsed_before_pause"] += time.time() - meta["start"]
    await update.message.reply_text("⏸️ Task paused. Use /task_resume.")

async def task_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta    = task_meta.get(chat_id)

    if not meta or not meta.get("paused"):
        return await update.message.reply_text("ℹ️ No paused task to resume.")

    meta["paused"] = False
    meta["start"]  = time.time()
    ticker         = asyncio.create_task(_count_loop(chat_id, context))
    active_tasks[chat_id] = ticker
    await update.message.reply_text("▶️ Task resumed.")

async def task_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ticker  = active_tasks.pop(chat_id, None)
    meta    = task_meta.pop(chat_id, None)

    if ticker:
        ticker.cancel()

    if not meta:
        return await update.message.reply_text("ℹ️ No active task.")

    elapsed = int(time.time() - meta["start"]) + int(meta["elapsed_before_pause"])
    h, rem  = divmod(elapsed, 3600)
    m, s    = divmod(rem, 60)
    await update.message.reply_text(
        f"✅ Logged *{meta['type']}* – {h:02d}:{m:02d}:{s:02d}",
        parse_mode="Markdown"
    )

async def task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meta    = task_meta.get(chat_id)

    if not meta:
        return await update.message.reply_text("ℹ️ No task running.")

    if meta["paused"]:
        elapsed = int(meta["elapsed_before_pause"])
    else:
        elapsed = int(time.time() - meta["start"]) + int(meta["elapsed_before_pause"])

    h, rem = divmod(elapsed, 3600)
    m, s   = divmod(rem, 60)
    await update.message.reply_text(
        f"⏱️ {meta['type']} – {h:02d}:{m:02d}:{s:02d}"
    )

# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app):
    # Conversation for picking preset
    wizard = ConversationHandler(
        entry_points=[CommandHandler("task_start", task_start)],
        states={
            S.CHOOSE: [CallbackQueryHandler(preset_chosen, pattern=r"^TASK:")],
        },
        fallbacks=[MessageHandler(filters.Regex("/cancel"), lambda u, c: ConversationHandler.END)],
        per_message=True,
    )
    app.add_handler(wizard)

    # Stand-alone commands
    app.add_handler(CommandHandler("task_pause",   task_pause))
    app.add_handler(CommandHandler("task_resume",  task_resume))
    app.add_handler(CommandHandler("task_stop",    task_stop))
    app.add_handler(CommandHandler("task_status",  task_status))
