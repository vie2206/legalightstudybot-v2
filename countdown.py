# countdown.py  ─ live second-by-second event countdown
import asyncio, datetime as dt
from typing import Dict

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ────── conversation states
ASK_DATE, ASK_TIME, ASK_LABEL, ASK_PIN = range(4)

# per-chat storage
count_meta: Dict[int, dict] = {}      # chat_id → {target, label, msg_id}
count_tasks: Dict[int, asyncio.Task] = {}

# ───────────────────────── helpers
def _parse_date(s: str):
    try:
        return dt.date.fromisoformat(s.strip())
    except ValueError:
        return None


def _parse_time(s: str):
    s = s.strip().lower()
    if s == "now":
        return dt.time(0, 0, 0)
    try:
        return dt.time.fromisoformat(s)
    except ValueError:
        return None


# ───────────────────────── wizard entry
async def cd_start(update: Update, _):
    await update.message.reply_text("📅 Target *date*?  (YYYY-MM-DD)", parse_mode="Markdown")
    return ASK_DATE


async def cd_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = _parse_date(update.message.text)
    if not d:
        await update.message.reply_text("❌ Invalid date. Try again (YYYY-MM-DD).")
        return ASK_DATE
    context.user_data["cd_date"] = d
    await update.message.reply_text(
        "⏰ Target *time*?  (HH:MM:SS or `now`)", parse_mode="Markdown"
    )
    return ASK_TIME


async def cd_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = _parse_time(update.message.text)
    if t is None:
        await update.message.reply_text("❌ Invalid time. Try again.")
        return ASK_TIME
    context.user_data["cd_time"] = t
    await update.message.reply_text("🏷  Event label? (max 60 chars)")
    return ASK_LABEL


async def cd_label(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cd_label"] = update.message.text.strip()[:60]
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📌 Pin", callback_data="pin_yes"),
          InlineKeyboardButton("Skip",  callback_data="pin_no")]]
    )
    await update.message.reply_text("Pin this countdown message?", reply_markup=kb)
    return ASK_PIN


async def pin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    pin   = q.data == "pin_yes"
    chat  = q.message.chat
    cid   = chat.id

    # build target datetime
    date  = context.user_data["cd_date"]
    time_ = context.user_data["cd_time"]
    target = dt.datetime.combine(date, time_)

    # cancel any existing timer for this chat
    old = count_tasks.pop(cid, None)
    if old:
        old.cancel()

    # initial placeholder message
    msg = await q.edit_message_text("⏳ Starting countdown…")

    if pin:
        try:
            await q.bot.pin_chat_message(cid, msg.message_id, disable_notification=True)
        except Exception:
            pass  # ignore pin failures (e.g., no permission)

    # store meta & launch loop
    count_meta[cid] = {"target": target, "label": context.user_data["cd_label"], "msg_id": msg.message_id}
    _launch_countdown(cid, context)

    return ConversationHandler.END


# ───────────────────────── command helpers
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in count_meta:
        await update.message.reply_text("ℹ️ No active countdown.")
        return
    await _edit(cid, context.bot)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    task = count_tasks.pop(cid, None)
    if task:
        task.cancel()
    count_meta.pop(cid, None)
    await update.message.reply_text("🚫 Countdown cancelled.")


# ───────────────────────── internal loop
async def _edit(cid: int, bot) -> bool:
    m = count_meta[cid]
    left = m["target"] - dt.datetime.utcnow()

    if left.total_seconds() <= 0:
        try:
            await bot.edit_message_text(
                chat_id=cid,
                message_id=m["msg_id"],
                text=f"🎉 {m['label']} reached!"
            )
        except Exception:
            pass
        return False

    days = left.days
    hrs, rem = divmod(left.seconds, 3600)
    mins, secs = divmod(rem, 60)
    txt = (
        f"⏳ *{m['label']}*\n"
        f"{days} d {hrs:02} h {mins:02} m {secs:02} s remaining."
    )
    try:
        await bot.edit_message_text(
            chat_id=cid,
            message_id=m["msg_id"],
            text=txt,
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            raise
    return True


def _launch_countdown(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    async def loop():
        try:
            while await _edit(cid, ctx.bot):
                await asyncio.sleep(1)          # update every second
        except asyncio.CancelledError:
            pass

    count_tasks[cid] = ctx.application.create_task(loop())


# ───────────────────────── registration
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", cd_start)],
        states={
            ASK_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_date)],
            ASK_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_time)],
            ASK_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_label)],
            ASK_PIN:   [CallbackQueryHandler(pin_choice, pattern="^pin_")],
        },
        fallbacks=[CommandHandler("cancel", stop)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("countdownstatus", status))
    app.add_handler(CommandHandler("countdownstop",   stop))
