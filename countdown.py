import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# In-memory
active_tasks: Dict[int, asyncio.Task] = {}
info_store:  Dict[int, Dict]         = {}

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M:%S"

async def countdown_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args    = context.args or []

    # parse --pin
    pin = False
    if "--pin" in args:
        pin = True
        args.remove("--pin")

    if len(args) < 2:
        return await update.message.reply_text(
            "❌ Usage: /countdown <YYYY-MM-DD> [HH:MM:SS] <label> [--pin]"
        )

    # date
    date_str = args[0]
    try:
        base_date = datetime.strptime(date_str, DATE_FMT)
    except ValueError:
        return await update.message.reply_text("❌ Date must be YYYY-MM-DD")

    # optional time
    if ":" in args[1]:
        time_str   = args[1]
        label_parts = args[2:]
        try:
            t = datetime.strptime(time_str, TIME_FMT).time()
            target = datetime.combine(base_date.date(), t)
        except ValueError:
            return await update.message.reply_text("❌ Time must be HH:MM:SS")
    else:
        target      = datetime.combine(base_date.date(), datetime.min.time())
        label_parts = args[1:]

    label = " ".join(label_parts).strip() or "Event"

    # cancel existing
    if chat_id in active_tasks:
        active_tasks[chat_id].cancel()

    info_store[chat_id] = {
        "target": target,
        "label":  label,
        "msg_id": None,
        "pin":    pin,
    }

    await update.message.reply_text(
        f"⏳ Countdown to '{label}' at {target:%Y-%m-%d %H:%M:%S} started."
    )
    active_tasks[chat_id] = asyncio.create_task(_ticker(chat_id, context))

async def countdown_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    info    = info_store.get(chat_id)
    if not info:
        return await update.message.reply_text("ℹ️ No active countdown.")

    remain = info["target"] - datetime.now()
    if remain <= timedelta(0):
        return await update.message.reply_text(f"🎉 '{info['label']}' is now!")
    d = remain.days
    h, rem = divmod(remain.seconds, 3600)
    m, s    = divmod(rem, 60)
    await update.message.reply_text(
        f"📅 {d}d {h:02d}h {m:02d}m {s:02d}s until '{info['label']}'."
    )

async def countdown_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task    = active_tasks.pop(chat_id, None)
    info    = info_store.pop(chat_id, None)
    if task:
        task.cancel()
        return await update.message.reply_text("🛑 Countdown canceled.")
    await update.message.reply_text("ℹ️ No active countdown to stop.")

async def _ticker(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    info = info_store.get(chat_id)
    if not info:
        return

    try:
        msg = await context.bot.send_message(chat_id, "⏳ Starting…")
        if info["pin"]:
            try:
                await context.bot.pin_chat_message(chat_id, msg.message_id)
            except:
                pass
        info["msg_id"] = msg.message_id

        while True:
            remain = info["target"] - datetime.now()
            if remain <= timedelta(0):
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=f"🎉 '{info['label']}' is now!"
                )
                break

            d = remain.days
            h, rem = divmod(remain.seconds, 3600)
            m, s    = divmod(rem, 60)
            text = f"📅 {d}d {h:02d}h {m:02d}m {s:02d}s until '{info['label']}'."
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=text
                )
            except:
                pass

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    finally:
        info_store.pop(chat_id, None)
        active_tasks.pop(chat_id, None)

def register_handlers(app):
    app.add_handler(CommandHandler("countdown",        countdown_start))
    app.add_handler(CommandHandler("countdown_status", countdown_status))
    app.add_handler(CommandHandler("countdown_stop",   countdown_stop))
