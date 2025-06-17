import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# In-memory storage for live countdowns
active_countdowns: Dict[int, asyncio.Task] = {}
countdown_info:     Dict[int, Dict]         = {}

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M:%S"

async def countdown_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /countdown <YYYY-MM-DD> [HH:MM:SS] <label> [--pin]
    Starts a live countdown to the given date/time with optional label.
    Add --pin to pin the message in chat.
    """
    chat_id = update.effective_chat.id
    args    = context.args or []

    # Handle --pin flag
    pin = False
    if "--pin" in args:
        pin = True
        args.remove("--pin")

    if len(args) < 2:
        return await update.message.reply_text(
            "❌ Usage: /countdown <YYYY-MM-DD> [HH:MM:SS] <label> [--pin]\n"
            "Examples:\n"
            "/countdown 2025-12-31 NewYear --pin\n"
            "/countdown 2025-12-31 23:59:59 YearEnd"
        )

    # Parse date
    date_str = args[0]
    try:
        base_date = datetime.strptime(date_str, DATE_FMT)
    except ValueError:
        return await update.message.reply_text("❌ Date must be YYYY-MM-DD")

    # See if next arg is time
    time_part: Optional[str]
    label_parts = []
    if len(args) >= 2 and ":" in args[1]:
        time_part   = args[1]
        label_parts = args[2:]
    else:
        time_part   = None
        label_parts = args[1:]

    # Build target datetime
    if time_part:
        try:
            t = datetime.strptime(time_part, TIME_FMT).time()
            target = datetime.combine(base_date.date(), t)
        except ValueError:
            return await update.message.reply_text("❌ Time must be HH:MM:SS")
    else:
        target = datetime.combine(base_date.date(), datetime.min.time())

    label = " ".join(label_parts).strip() or "Event"

    # Cancel previous
    if chat_id in active_countdowns:
        active_countdowns[chat_id].cancel()

    countdown_info[chat_id] = {
        "target": target,
        "label":  label,
        "msg_id": None,
        "pin":    pin,
    }

    # Acknowledge
    await update.message.reply_text(
        f"⏳ Countdown to '{label}' set for {target:%Y-%m-%d %H:%M:%S}."
    )
    # Start live updates
    active_countdowns[chat_id] = asyncio.create_task(_run_countdown(chat_id, context))

async def countdown_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """One-off remaining time without live updates."""
    chat_id = update.effective_chat.id
    info    = countdown_info.get(chat_id)
    if not info:
        return await update.message.reply_text("ℹ️ No active countdown.")

    remain = info["target"] - datetime.now()
    if remain <= timedelta(0):
        return await update.message.reply_text(f"🎉 '{info['label']}' has arrived!")

    d = remain.days
    h, rem = divmod(remain.seconds, 3600)
    m, s    = divmod(rem, 60)
    await update.message.reply_text(
        f"📅 {d}d {h:02d}h {m:02d}m {s:02d}s until '{info['label']}'."
    )

async def countdown_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stops the live countdown."""
    chat_id = update.effective_chat.id
    task    = active_countdowns.pop(chat_id, None)
    info    = countdown_info.pop(chat_id, None)

    if task:
        task.cancel()
        return await update.message.reply_text("🛑 Countdown canceled.")

    await update.message.reply_text("ℹ️ No active countdown to cancel.")

async def _run_countdown(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Background task: updates the message every second."""
    info = countdown_info.get(chat_id)
    if not info:
        return

    try:
        # Send initial message
        msg = await context.bot.send_message(chat_id, "⏳ Starting countdown...")
        if info["pin"]:
            try:
                await context.bot.pin_chat_message(chat_id, msg.message_id)
            except:
                pass
        info["msg_id"] = msg.message_id

        while True:
            now    = datetime.now()
            remain = info["target"] - now
            if remain <= timedelta(0):
                text = f"🎉 '{info['label']}' is happening now!"
                await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=text)
                break

            d = remain.days
            h, rem = divmod(remain.seconds, 3600)
            m, s    = divmod(rem, 60)
            text = f"📅 {d}d {h:02d}h {m:02d}m {s:02d}s until '{info['label']}'."
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=text,
                )
            except:
                pass

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    finally:
        countdown_info.pop(chat_id, None)
        active_countdowns.pop(chat_id, None)

def register_handlers(app):
    app.add_handler(CommandHandler("countdown",        countdown_start))
    app.add_handler(CommandHandler("countdown_status", countdown_status))
    app.add_handler(CommandHandler("countdown_stop",   countdown_stop))
