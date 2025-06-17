import asyncio
from datetime import datetime, timedelta
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# In‐memory stores for active countdowns
active_tasks: Dict[int, asyncio.Task] = {}
info_store:   Dict[int, Dict]         = {}

# Date/time formats
DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M:%S"


async def countdown_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args    = context.args or []

    # pin flag?
    pin = False
    if "--pin" in args:
        pin = True
        args.remove("--pin")

    # need at least date + label
    if len(args) < 2:
        return await update.message.reply_text(
            "❌ Usage: /countdown <YYYY-MM-DD> [HH:MM:SS] <label> [--pin]"
        )

    # parse date
    try:
        base = datetime.strptime(args[0], DATE_FMT)
    except ValueError:
        return await update.message.reply_text("❌ Date must be YYYY-MM-DD")

    # parse optional time
    if ":" in args[1]:
        try:
            t = datetime.strptime(args[1], TIME_FMT).time()
            target = datetime.combine(base.date(), t)
            label  = " ".join(args[2:]).strip() or "Event"
        except ValueError:
            return await update.message.reply_text("❌ Time must be HH:MM:SS")
    else:
        target = datetime.combine(base.date(), datetime.min.time())
        label  = " ".join(args[1:]).strip() or "Event"

    # cancel any existing countdown in this chat
    if chat_id in active_tasks:
        active_tasks[chat_id].cancel()

    # store meta
    info_store[chat_id] = {
        "target": target,
        "label":  label,
        "pin":    pin,
        "msg_id": None,
    }

    # 1️⃣ Immediate acknowledgement (becomes our live ticker)
    msg = await update.message.reply_text(
        f"⏳ Countdown to '{label}' at {target:%Y-%m-%d %H:%M:%S} started."
    )
    if pin:
        try:
            await context.bot.pin_chat_message(chat_id, msg.message_id)
        except:
            pass

    info_store[chat_id]["msg_id"] = msg.message_id

    # fire off the per-second ticker
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
    m, s   = divmod(rem, 60)
    await update.message.reply_text(
        f"📅 {d}d {h:02d}h {m:02d}m {s:02d}s until '{info['label']}'."
    )


async def countdown_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task    = active_tasks.pop(chat_id, None)
    info_store.pop(chat_id, None)
    if task:
        task.cancel()
        return await update.message.reply_text("🛑 Countdown canceled.")
    return await update.message.reply_text("ℹ️ No active countdown to stop.")


async def _ticker(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    info   = info_store.get(chat_id)
    msg_id = info["msg_id"]
    try:
        while True:
            remain = info["target"] - datetime.now()
            if remain <= timedelta(0):
                # 3️⃣ Final edit
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=f"🎉 '{info['label']}' is now!"
                )
                # 3️⃣ Broadcast celebration
                await context.bot.send_message(
                    chat_id,
                    f"🎉 '{info['label']}' has arrived! 🎊"
                )
                break

            d = remain.days
            h, rem = divmod(remain.seconds, 3600)
            m, s   = divmod(rem, 60)
            text = f"📅 {d}d {h:02d}h {m:02d}m {s:02d}s until '{info['label']}'."
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text
                )
            except:
                pass

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        # user hit /countdown_stop
        pass
    finally:
        info_store.pop(chat_id, None)
        active_tasks.pop(chat_id, None)


def register_handlers(app):
    app.add_handler(CommandHandler("countdown",        countdown_start))
    app.add_handler(CommandHandler("countdown_status", countdown_status))
    app.add_handler(CommandHandler("countdown_stop",   countdown_stop))
