# streak.py  ────────────────────────────────────────────────────────────
"""
Daily study-streak tracker.

Commands
--------
/checkin        – record “I studied today!”
/mystreak       – show consecutive-day streak
/streak_alerts  – toggle DM alert if the streak breaks
"""

import datetime as dt
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ──────────────────────────────────────────────────────────────
class _Streak:
    __slots__ = ("days", "last_date", "alerts_on")

    def __init__(self):
        self.days: int = 0
        self.last_date: dt.date | None = None
        self.alerts_on: bool = True


streaks: Dict[int, _Streak] = {}   # user_id → _Streak

# ──────────────────────────────────────────────────────────────
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    today = dt.date.today()

    s = streaks.setdefault(uid, _Streak())

    if s.last_date == today:
        return await update.message.reply_text("✅ Already checked in for today!")

    s.days = s.days + 1 if s.last_date and (today - s.last_date).days == 1 else 1
    s.last_date = today

    await update.message.reply_text(
        f"📅 Check-in recorded! 🔥 Current streak: *{s.days}* day(s).",
        parse_mode="Markdown",
    )


async def mystreak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s   = streaks.get(uid)

    if not s or not s.last_date:
        return await update.message.reply_text("No streak yet. Use /checkin!")

    await update.message.reply_text(
        f"🔥 You’re on a *{s.days}-day* streak (last check-in: {s.last_date}).",
        parse_mode="Markdown",
    )


async def streak_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    arg = (context.args[0].lower() if context.args else "")

    if arg not in ("on", "off"):
        return await update.message.reply_text("Usage: /streak_alerts on|off")

    s = streaks.setdefault(uid, _Streak())
    s.alerts_on = arg == "on"

    await update.message.reply_text(
        f"🔔 Break-streak alerts are now *{'ON' if s.alerts_on else 'OFF'}*.",
        parse_mode="Markdown",
    )

# ──────────────────────────────────────────────────────────────
async def _hourly_checker(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue task – DM users whose streak just broke."""
    today = dt.date.today()

    for uid, s in list(streaks.items()):
        if not s.alerts_on or not s.last_date:
            continue
        if (today - s.last_date).days >= 2:
            with contextlib.suppress(Exception):
                await context.bot.send_message(
                    uid,
                    "⚠️ You missed a day and your study streak reset. "
                    "Jump back in with /checkin!",
                )
            s.alerts_on = False  # stop further alerts

# ──────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    app.add_handler(CommandHandler("checkin",        checkin))
    app.add_handler(CommandHandler("mystreak",       mystreak))
    app.add_handler(CommandHandler("streak_alerts",  streak_alerts))

    # run the broken-streak checker every hour (first run immediately)
    app.job_queue.run_repeating(_hourly_checker, interval=3600, first=0)
