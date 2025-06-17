# streak.py
"""
Daily study-streak tracker.

Features
--------
/checkin        – record “I studied today!”
/mystreak       – show consecutive-day streak
/streak_alerts  – toggle DM alert if the streak breaks

Implementation
--------------
•  Streak data kept in a simple in-memory dict  {user_id: {...}}.
   (You can later swap this out for a DB; the interface is isolated.)
•  A background task runs every hour to detect broken streaks and
   DM users who enabled alerts.
"""

import asyncio
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


streaks: Dict[int, _Streak] = {}   # key = telegram user_id


# ──────────────────────────────────────────────────────────────
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User manually records study for today."""
    uid = update.effective_user.id
    today = dt.date.today()

    s = streaks.setdefault(uid, _Streak())

    # same day?
    if s.last_date == today:
        return await update.message.reply_text("✅ Already checked in for today!")

    # consecutive?
    if s.last_date and (today - s.last_date).days == 1:
        s.days += 1
    else:
        s.days = 1  # reset

    s.last_date = today
    await update.message.reply_text(
        f"📅 Check-in recorded! 🔥 Current streak: *{s.days}* day(s).",
        parse_mode="Markdown",
    )


async def mystreak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the user’s current streak."""
    uid = update.effective_user.id
    s = streaks.get(uid)
    if not s or not s.last_date:
        return await update.message.reply_text("You haven’t checked in yet. Use /checkin!")

    days = s.days
    last = s.last_date.strftime("%Y-%m-%d")
    await update.message.reply_text(
        f"🔥 You’re on a *{days}-day* streak (last check-in: {last}).",
        parse_mode="Markdown",
    )


async def streak_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/streak_alerts on|off  – toggle DM alert."""
    uid = update.effective_user.id
    arg = (context.args[0].lower() if context.args else "")
    if arg not in ("on", "off"):
        return await update.message.reply_text("Usage: /streak_alerts on|off")

    s = streaks.setdefault(uid, _Streak())
    s.alerts_on = (arg == "on")
    await update.message.reply_text(
        f"🔔 Break-streak alerts are now *{'ON' if s.alerts_on else 'OFF'}*.",
        parse_mode="Markdown",
    )


# ──────────────────────────────────────────────────────────────
async def _hourly_checker(bot):
    """Background loop: DM users whose streak just broke."""
    while True:
        now = dt.datetime.now()
        today = now.date()

        for uid, s in list(streaks.items()):
            if not s.alerts_on or not s.last_date:
                continue
            # missed yesterday?
            if (today - s.last_date).days >= 2:
                try:
                    await bot.send_message(
                        uid,
                        "⚠️ You missed a day and your study streak reset. "
                        "Jump back in with /checkin!",
                    )
                except Exception:
                    pass   # user may have blocked bot
                s.alerts_on = False  # stop spamming until they re-enable

        # wait 1 h
        await asyncio.sleep(3600)


# ──────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    app.add_handler(CommandHandler("checkin",        checkin))
    app.add_handler(CommandHandler("mystreak",       mystreak))
    app.add_handler(CommandHandler("streak_alerts",  streak_alerts))

    # Launch background checker once the bot is up
    async def _post_init(app: Application):
        app.create_task(_hourly_checker(app.bot))

    app.post_init(_post_init)
