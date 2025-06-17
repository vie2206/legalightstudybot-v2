"""
countdown.py  –  Interactive date-&-time countdown with live edits
Compatible with python-telegram-bot v20.x
"""

import asyncio, datetime as dt, time
from typing import Dict, Tuple

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

DATE, TIME, LABEL = range(3)

# ----------------- active countdown state -----------------
active_cd: Dict[int, asyncio.Task]    = {}  # chat_id → asyncio.Task
meta_cd:   Dict[int, Dict[str, str]]  = {}  # chat_id → {"label", "end_ts", "msg_id"}


# ---------------------------------------------------------------------------#
# WIZARD STEP 1  (/countdown)  – ask for date
# ---------------------------------------------------------------------------#
async def start_wizard(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🗓  *Countdown* – send a date in `YYYY-MM-DD` format:",
        parse_mode="Markdown",
    )
    return DATE


async def date_received(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    try:
        date_obj = dt.datetime.strptime(txt, "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text("❌ Invalid date. Please send `YYYY-MM-DD`.")
        return DATE

    update.user_data["cd_date"] = date_obj
    await update.message.reply_text(
        "⏰ Send a *time* in `HH:MM[:SS]` 24-h format "
        "(or send `skip` for 00:00:00):",
        parse_mode="Markdown",
    )
    return TIME


# ---------------------------------------------------------------------------#
# WIZARD STEP 2  – ask for time
# ---------------------------------------------------------------------------#
async def time_received(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt.lower() == "skip":
        time_obj = dt.time(0, 0, 0)
    else:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                time_obj = dt.datetime.strptime(txt, fmt).time()
                break
            except ValueError:
                time_obj = None
        if not time_obj:
            await update.message.reply_text("❌ Invalid time. `HH:MM` or `HH:MM:SS`.")
            return TIME

    update.user_data["cd_time"] = time_obj
    await update.message.reply_text("📝 Finally, send a short *label* for the event:")
    return LABEL


# ---------------------------------------------------------------------------#
# WIZARD STEP 3  – get label → begin countdown
# ---------------------------------------------------------------------------#
async def label_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    cid         = update.effective_chat.id
    label       = update.message.text.strip()[:60] or "Event"
    date_obj    = update.user_data["cd_date"]
    time_obj    = update.user_data["cd_time"]

    end_dt      = dt.datetime.combine(date_obj, time_obj)
    end_ts      = end_dt.timestamp()

    # cancel any existing countdown in this chat
    if cid in active_cd:
        active_cd[cid].cancel()

    # first message
    m = await update.message.reply_text("⏳ Starting countdown…")
    meta_cd[cid] = {"label": label, "end_ts": end_ts, "msg_id": m.message_id}

    # async loop task
    task = asyncio.create_task(_run_cd_loop(cid, ctx))
    active_cd[cid] = task

    return ConversationHandler.END


async def _run_cd_loop(cid: int, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        while True:
            meta = meta_cd[cid]
            remain = int(meta["end_ts"] - time.time())
            if remain <= 0:
                break

            days, rem = divmod(remain, 86400)
            hrs, rem  = divmod(rem, 3600)
            mins, sec = divmod(rem, 60)

            text = (
                f"⏳ *{meta['label']}*\n"
                f"{days} d {hrs:02d} h {mins:02d} m {sec:02d} s remaining."
            )
            try:
                await ctx.bot.edit_message_text(
                    chat_id=cid,
                    message_id=meta["msg_id"],
                    text=text,
                    parse_mode="Markdown",
                )
            except Exception:
                pass

            await asyncio.sleep(5)

        # finished
        await ctx.bot.send_message(cid, f"🎉 *{meta_cd[cid]['label']}* is here!", parse_mode="Markdown")
    except asyncio.CancelledError:
        pass
    finally:
        active_cd.pop(cid, None)
        meta_cd.pop(cid, None)


# ---------------------------------------------------------------------------#
# STATUS / STOP
# ---------------------------------------------------------------------------#
async def countdown_status(update: Update, _: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    meta = meta_cd.get(cid)
    if not meta:
        return await update.message.reply_text("ℹ️ No active countdown.")

    remain = int(meta["end_ts"] - time.time())
    days, rem = divmod(remain, 86400)
    hrs, rem  = divmod(rem, 3600)
    mins, sec = divmod(rem, 60)
    await update.message.reply_text(
        f"⏳ *{meta['label']}*\n"
        f"{days} d {hrs:02d} h {mins:02d} m {sec:02d} s remaining.",
        parse_mode="Markdown",
    )


async def countdown_stop(update: Update, _: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    task = active_cd.pop(cid, None)
    if task:
        task.cancel()
        meta_cd.pop(cid, None)
        await update.message.reply_text("🚫 Countdown cancelled.")
    else:
        await update.message.reply_text("ℹ️ No active countdown.")


# ---------------------------------------------------------------------------#
# cancel wizard mid-flow
# ---------------------------------------------------------------------------#
async def wizard_cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------#
# register with main bot
# ---------------------------------------------------------------------------#
def register_handlers(app: Application):
    # interactive wizard
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", start_wizard)],
        states={
            DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, date_received)],
            TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, time_received)],
            LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, label_received)],
        },
        fallbacks=[CommandHandler("cancel", wizard_cancel)],
        per_message=True,
    )
    app.add_handler(conv)

    # utility commands
    app.add_handler(CommandHandler("countdownstatus", countdown_status))
    app.add_handler(CommandHandler("countdownstop",   countdown_stop))
