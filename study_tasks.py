# study_tasks.py  –  v2 (safe CallbackQuery handling)
# ----------------------------------------------------
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

# ───── preset task names ─────
TASK_TYPES = [
    "CLAT_MOCK", "SECTIONAL", "NEWSPAPER", "EDITORIAL", "GK_CA", "MATHS",
    "LEGAL_REASONING", "LOGICAL_REASONING", "CLATOPEDIA", "SELF_STUDY",
    "ENGLISH", "STUDY_TASK",
]

# ───── conversation states ─────
class S(Enum):
    CHOOSE = auto()

# ───── in-memory bookkeeping ─────
active_tasks: Dict[int, asyncio.Task]   = {}  # chat_id → asyncio.Task
task_meta:    Dict[int, Dict[str, any]] = {}  # chat_id → metadata

# ──────────────────────────────────────────────────────────────────────────
# internal helpers
# ──────────────────────────────────────────────────────────────────────────
async def _ticker(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    meta = task_meta[chat_id]
    while True:
        try:
            elapsed = int(time.time() - meta["start"]) + meta["elapsed"]
            h, r1   = divmod(elapsed, 3600)
            m, s    = divmod(r1, 60)
            txt     = f"⏱️ {meta['type']} • {h:02d}:{m:02d}:{s:02d}"

            try:
                await context.bot.edit_message_text(
                    chat_id, meta["msg_id"], txt
                )
            except:  # ignore edit failures (rate-limit, etc.)
                pass
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break

async def _begin(u_or_q, ctx, ttype: str):
    """Starts or restarts a stopwatch task."""
    # ── safe chat/message extraction ──
    if isinstance(u_or_q, CallbackQuery):
        chat_id   = u_or_q.message.chat_id
        send_func = u_or_q.message.reply_text
    else:
        chat_id   = u_or_q.effective_chat.id
        send_func = u_or_q.message.reply_text
    # ----------------------------------

    # cancel previous ticker (if any)
    old = active_tasks.pop(chat_id, None)
    if old:
        old.cancel()

    msg = await send_func(
        f"🟢 *{ttype.replace('_', ' ').title()}* started.\n"
        "Stopwatch running…\n"
        "Use /task_pause or /task_stop.",
        parse_mode="Markdown"
    )

    task_meta[chat_id] = {
        "type":    ttype,
        "start":   time.time(),
        "elapsed": 0,            # seconds accumulated before a pause
        "paused":  False,
        "msg_id":  msg.message_id,
    }
    ticker = asyncio.create_task(_ticker(chat_id, ctx))
    active_tasks[chat_id] = ticker
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────────────────
# command /task_start  (inline menu)
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[Btn(t, callback_data=f"TASK:{t}")] for t in TASK_TYPES]
    await update.message.reply_text(
        "Pick a study task:",
        reply_markup=Mk(kb)
    )
    return S.CHOOSE

async def _preset_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, ttype = q.data.split(":")
    return await _begin(q, ctx, ttype)

# ────────────────────────────────
# pause / resume / stop / status
async def task_pause(update: Update, ctx):
    chat_id = update.effective_chat.id
    ticker  = active_tasks.pop(chat_id, None)
    meta    = task_meta.get(chat_id)
    if not ticker or not meta or meta["paused"]:
        return await update.message.reply_text("ℹ️ No active task to pause.")
    ticker.cancel()
    meta["elapsed"] += int(time.time() - meta["start"])
    meta["paused"]   = True
    await update.message.reply_text("⏸️ Task paused – /task_resume to continue.")

async def task_resume(update: Update, ctx):
    chat_id = update.effective_chat.id
    meta    = task_meta.get(chat_id)
    if not meta or not meta["paused"]:
        return await update.message.reply_text("ℹ️ No paused task to resume.")
    meta["paused"] = False
    meta["start"]  = time.time()
    ticker         = asyncio.create_task(_ticker(chat_id, ctx))
    active_tasks[chat_id] = ticker
    await update.message.reply_text("▶️ Task resumed.")

async def task_stop(update: Update, ctx):
    chat_id = update.effective_chat.id
    ticker  = active_tasks.pop(chat_id, None)
    meta    = task_meta.pop(chat_id, None)
    if ticker:
        ticker.cancel()
    if not meta:
        return await update.message.reply_text("ℹ️ No active task.")
    total = meta["elapsed"]
    if not meta["paused"]:
        total += int(time.time() - meta["start"])
    h, r1  = divmod(total, 3600)
    m, s   = divmod(r1, 60)
    await update.message.reply_text(
        f"✅ Logged *{meta['type']}* – {h:02d}:{m:02d}:{s:02d}",
        parse_mode="Markdown"
    )

async def task_status(update: Update, ctx):
    chat_id = update.effective_chat.id
    meta    = task_meta.get(chat_id)
    if not meta:
        return await update.message.reply_text("ℹ️ No task running.")
    total = meta["elapsed"]
    if not meta["paused"]:
        total += int(time.time() - meta["start"])
    h, r1 = divmod(total, 3600)
    m, s  = divmod(r1, 60)
    await update.message.reply_text(
        f"⏱️ {meta['type']} – {h:02d}:{m:02d}:{s:02d}"
    )

# ──────────────────────────────────────────────────────────────────────────
def register_handlers(app):
    # Conversation + extra direct command handler
    wizard = ConversationHandler(
        entry_points=[
            CommandHandler("task_start", task_start),
        ],
        states={S.CHOOSE: [CallbackQueryHandler(_preset_chosen, r"^TASK:")]},
        fallbacks=[],
        per_message=True,
    )
    app.add_handler(wizard)
    # ensure /task_start always caught (even if convo somehow skipped)
    app.add_handler(CommandHandler("task_start", task_start), group=1)

    # stand-alone commands
    app.add_handler(CommandHandler("task_pause",  task_pause))
    app.add_handler(CommandHandler("task_resume", task_resume))
    app.add_handler(CommandHandler("task_stop",   task_stop))
    app.add_handler(CommandHandler("task_status", task_status))
