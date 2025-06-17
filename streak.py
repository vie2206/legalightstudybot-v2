"""
streak.py  –  Simple daily study-streak tracker
Compatible with python-telegram-bot v20.x
"""

import datetime as dt
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------------------------#
# simple in-memory store
#   user_id → {"last_day": date, "streak": int, "alerts": bool}
# ---------------------------------------------------------------------------#
user_streaks: Dict[int, Dict[str, object]] = {}


# ---------------------------------------------------------------------------#
# /checkin  – “I studied today!”
# ---------------------------------------------------------------------------#
async def checkin(update: Update, _: ContextTypes.DEFAULT_TYPE):
    uid       = update.effective_user.id
    today     = dt.date.today()
    record    = user_streaks.get(uid, {"streak": 0, "last_day": None, "alerts": False})

    # Same day? nothing to do
    if record["last_day"] == today:
        return await update.message.reply_text("✅ Already checked-in today!")

    # compute new streak
    if record["last_day"] == today - dt.timedelta(days=1):
        record["streak"] += 1                          # continue streak
    else:
        record["streak"] = 1                           # reset

    record["last_day"] = today
    user_streaks[uid]  = record

    await update.message.reply_text(
        f"📅 Check-in recorded!  🔥 Current streak: *{record['streak']}* day(s).",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------#
# /mystreak  – show current streak
# ---------------------------------------------------------------------------#
async def mystreak(update: Update, _: ContextTypes.DEFAULT_TYPE):
    uid    = update.effective_user.id
    record = user_streaks.get(uid)

    if not record:
        return await update.message.reply_text("ℹ️ No streak yet — send /checkin to start!")

    streak = record["streak"]
    last   = record["last_day"].strftime("%Y-%m-%d")
    await update.message.reply_text(
        f"🔥 You’re on a *{streak}-day* streak (last check-in: {last}).",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------#
# /streak_alerts on|off  – toggle DM alert if streak breaks
# ---------------------------------------------------------------------------#
async def streak_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    args  = (context.args or [])[:1]
    if not args or args[0].lower() not in {"on", "off"}:
        return await update.message.reply_text("Usage: /streak_alerts on|off")

    record = user_streaks.setdefault(uid, {"streak": 0, "last_day": None, "alerts": False})
    record["alerts"] = args[0].lower() == "on"
    await update.message.reply_text(
        f"🔔 Streak alerts *{'enabled' if record['alerts'] else 'disabled'}*.",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------#
# register with main bot
# ---------------------------------------------------------------------------#
def register_handlers(app: Application):
    app.add_handler(CommandHandler("checkin",       checkin))
    app.add_handler(CommandHandler("mystreak",      mystreak))
    app.add_handler(CommandHandler("streak_alerts", streak_alerts))
