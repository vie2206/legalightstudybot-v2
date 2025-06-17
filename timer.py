import asyncio
import time
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# In‐memory storage for active timers and metadata
active_timers: Dict[int, asyncio.Task] = {}
timer_info:   Dict[int, Dict[str, float]] = {}

async def timer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /timer [work_min] [break_min]
    Starts a Pomodoro with an in-place live countdown.
    """
    chat_id = update.effective_chat.id
    args    = context.args or []

    try:
        work = int(args[0]) if len(args) >= 1 else 25
        brk  = int(args[1]) if len(args) >= 2 else 5
    except ValueError:
        return await update.message.reply_text(
            "❌ Usage: /timer [work_minutes] [break_minutes]"
        )

    # Cancel any existing timer
    if chat_id in active_timers:
        active_timers[chat_id].cancel()

    # Work phase metadata
    timer_info[chat_id] = {"phase": "work", "start": time.time(), "duration": work * 60}

    # Send initial countdown message
    countdown_msg = await context.bot.send_message(
        chat_id,
        f"🟢 Work phase: {work}m 0s remaining."
    )

    async def run_pomodoro():
        try:
            # Work countdown loop
            end_time = time.time() + work * 60
            while True:
                remain = end_time - time.time()
                if remain <= 0:
                    break
                m, s = divmod(int(remain), 60)
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=countdown_msg.message_id,
                        text=f"🟢 Work phase: {m}m {s}s remaining."
                    )
                except Exception:
                    pass
                await asyncio.sleep(5)

            # Transition to break
            await context.bot.delete_message(chat_id, countdown_msg.message_id)
            await context.bot.send_message(
                chat_id,
                f"⏰ Work session over! Time for a {brk}-min break."
            )

            # Break phase metadata
            timer_info[chat_id] = {"phase": "break", "start": time.time(), "duration": brk * 60}
            break_msg = await context.bot.send_message(
                chat_id,
                f"🔵 Break phase: {brk}m 0s remaining."
            )
            end_break = time.time() + brk * 60

            # Break countdown loop
            while True:
                remain2 = end_break - time.time()
                if remain2 <= 0:
                    break
                m2, s2 = divmod(int(remain2), 60)
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=break_msg.message_id,
                        text=f"🔵 Break phase: {m2}m {s2}s remaining."
                    )
                except Exception:
                    pass
                await asyncio.sleep(5)

            # Finish
            await context.bot.delete_message(chat_id, break_msg.message_id)
            await context.bot.send_message(
                chat_id,
                "✅ Break’s over! Ready for the next session? Use /timer again."
            )

        except asyncio.CancelledError:
            # Cleanup if canceled mid-phase
            try:
                await context.bot.delete_message(chat_id, countdown_msg.message_id)
            except Exception:
                pass
        finally:
            active_timers.pop(chat_id, None)
            timer_info.pop(chat_id, None)

    task = asyncio.create_task(run_pomodoro())
    active_timers[chat_id] = task

    await update.message.reply_text(
        f"🟢 Pomodoro started: {work} min work → {brk} min break."
    )

async def timer_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stops and cancels the active Pomodoro timer."""
    chat_id = update.effective_chat.id
    task    = active_timers.pop(chat_id, None)
    timer_info.pop(chat_id, None)
    if task:
        task.cancel()
        await update.message.reply_text("🚫 Pomodoro canceled.")
    else:
        await update.message.reply_text("ℹ️ No active Pomodoro to cancel.")

async def timer_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reports remaining time for the active Pomodoro phase."""
    chat_id = update.effective_chat.id
    info    = timer_info.get(chat_id)
    if not info:
        return await update.message.reply_text("ℹ️ No active Pomodoro.")

    elapsed = time.time() - info["start"]
    remain  = max(0, info["duration"] - elapsed)
    m, s     = divmod(int(remain), 60)
    phase    = info.get("phase", "work").capitalize()
    await update.message.reply_text(f"⏱️ {phase} phase: {m}m {s}s remaining.")

def register_handlers(app):
    app.add_handler(CommandHandler("timer",        timer_start))
    app.add_handler(CommandHandler("timer_stop",   timer_stop))
    app.add_handler(CommandHandler("timer_status", timer_status))
