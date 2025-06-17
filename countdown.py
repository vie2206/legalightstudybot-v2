"""
Date-time countdown module.

Commands
--------
/countdown_set <YYYY-MM-DD HH:MM> <event>
/countdown_show
/countdown_clear
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional
from telegram import Update
from telegram.ext import ContextTypes, Application, CommandHandler

# chat_id → (deadline (UTC dt), title)
_countdowns: Dict[int, Tuple[datetime, str]] = {}


def _parse_dt(text: str) -> Optional[datetime]:
    m = re.match(r"(\\d{4}-\\d{2}-\\d{2})(?:\\s+(\\d{2}:\\d{2}))?", text)
    if not m:
        return None
    date_part, time_part = m.groups()
    time_part = time_part or "00:00"
    try:
        dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fmt(dt: datetime) -> str:
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    delta = dt - now
    if delta.total_seconds() < 0:
        return "0d 0h 0m 0s"
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


async def countdown_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /countdown_set <YYYY-MM-DD HH:MM> <event>"
        )
        return
    dt = _parse_dt(" ".join(context.args[:2]))
    if dt is None:
        await update.message.reply_text("❌ Invalid date/time format.")
        return
    title = " ".join(context.args[2:]).strip()
    if not title:
        await update.message.reply_text("❌ Please provide an event name.")
        return
    _countdowns[update.effective_chat.id] = (dt, title)
    await update.message.reply_text(
        f"✅ Countdown set for *{title}* – {_fmt(dt)} left.",
        parse_mode="Markdown",
    )


async def countdown_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = _countdowns.get(update.effective_chat.id)
    if not data:
        await update.message.reply_text("ℹ️ No countdown set.")
        return
    dt, title = data
    await update.message.reply_text(
        f"⏳ *{title}* – {_fmt(dt)} left.", parse_mode="Markdown"
    )


async def countdown_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _countdowns.pop(update.effective_chat.id, None):
        await update.message.reply_text("✅ Countdown cleared.")
    else:
        await update.message.reply_text("ℹ️ No countdown to clear.")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("countdown_set", countdown_set))
    app.add_handler(CommandHandler("countdown_show", countdown_show))
    app.add_handler(CommandHandler("countdown_clear", countdown_clear))
