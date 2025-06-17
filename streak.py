# streak.py
"""
Daily study-streak tracker.

Commands
--------
/checkin         – record “I studied today!”
/mystreak        – show consecutive-day streak
/streak_alerts   – toggle DM alert if the streak breaks
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

# ────────────────────────── internal data model
class _Streak:
    __slots__ = ("days", "last_date", "alerts_on")

    def __init__(self):
        self.days: int = 0
        self.last_date: dt.date | None = None
        self.alerts_on: bool = True


_streaks: Dict[int, _Streak] = {}  # user_id ➜ _Streak

# ────────────────────────── helpers
def _today() -> dt.date:
    """Return today’s date (UTC)."""
    return dt.datetime.utcnow().date()

# ────────────────────────── command handlers
async def checkin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    today = _today()

    s = _streaks.setdefault(uid, _Streak())

    if s.last_date == today:
        return await update.message.reply_text("✅ Already checked-in today!")

    if s.last_date and (today - s.last_date).days == 1:
        s.days += 1          # consecutive
    else:
        s.days = 1           # reset

    s.last_date = today
    await update.message.reply_text(
        f"📅 Check-in recorded! 🔥 Current streak: *{s.days}* day(s).",
        parse_mode="Markdown",
    )


async def mystreak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s   = _streaks.get(uid)

    if not s or not s.last_date:
        return await update.message.reply_text("No streak yet – use /checkin!")

    await update.message.reply_text(
        f"🔥 You’re on a *{s.days}-day* streak "
        f"(last check-in: {s.last_date.isoformat()}).",
        parse_mode="Markdown",
    )


async def streak_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return await update.message.reply_text("Usage: /streak_alerts on|off")

    enable = ctx.args[0].lower() == "on"
    _streaks.setdefault(uid, _Streak()).alerts_on = enable
    await update.message.reply_text(
        f"🔔 Break-streak alerts are now *{'ON' if enable else 'OFF'}*.",
        parse_mode="Markdown",
    )

# ────────────────────────── background loop
async def _hourly_checker(bot):
    while True:
        today = _today()
        for uid, s in list(_streaks.items()):
            if s.alerts_on and s.last_date and (today - s.last_date).days >= 2:
                try:
                    await bot.send_message(
                        uid,
                        "⚠️ You missed a day – your streak reset. "
                        "Get back on track with /checkin!",
                    )
                except Exception:
                    pass          # user blocked bot / cannot DM
                s.alerts_on = False
        await asyncio.sleep(3600)

# ────────────────────────── registration helper
def register_handlers(app: Application):
    app.add_handler(CommandHandler("checkin",        checkin))
    app.add_handler(CommandHandler("mystreak",       mystreak))
    app.add_handler(CommandHandler("streak_alerts",  streak_alerts))

    async def _post_init(app: Application):
        app.create_task(_hourly_checker(app.bot))

    app.post_init(_post_init)
