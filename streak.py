# streak.py  ────────────────────────────────────────────────────────────
"""
Daily study-streak tracker.

Commands
--------
/checkin        – record “I studied today!”
/mystreak       – show consecutive-day streak
/streak_alerts  – toggle DM alert if the streak breaks
"""

import asyncio, datetime as dt
from typing import Dict

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ──────────────────────────────────────────────────────────────
class _Streak:
    __slots__ = ("days", "last_date", "alerts_on")

    def __init__(self):
        self.days: int                = 0
        self.last_date: dt.date | None = None
        self.alerts_on: bool          = True


_streaks: Dict[int, _Streak] = {}        # user_id → _Streak

# ──────────────────────────────────────────────────────────────
async def checkin(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid, today = upd.effective_user.id, dt.date.today()
    s = _streaks.setdefault(uid, _Streak())

    if s.last_date == today:
        return await upd.message.reply_text("✅ Already checked-in today!")

    s.days = s.days + 1 if s.last_date and (today - s.last_date).days == 1 else 1
    s.last_date = today

    await upd.message.reply_text(
        f"📅 Check-in recorded! 🔥 Current streak: *{s.days}* day(s).",
        parse_mode="Markdown",
    )


async def mystreak(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = _streaks.get(upd.effective_user.id)
    if not s or not s.last_date:
        return await upd.message.reply_text("No streak yet. Use /checkin!")

    await upd.message.reply_text(
        f"🔥 You’re on a *{s.days}-day* streak (last: {s.last_date}).",
        parse_mode="Markdown",
    )


async def streak_alerts(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return await upd.message.reply_text("Usage: /streak_alerts on|off")

    uid, toggle = upd.effective_user.id, ctx.args[0].lower() == "on"
    _streaks.setdefault(uid, _Streak()).alerts_on = toggle

    await upd.message.reply_text(
        f"🔔 Break-streak alerts *{'enabled' if toggle else 'disabled'}*.",
        parse_mode="Markdown",
    )

# ──────────────────────────────────────────────────────────────
async def _hourly_loop(bot):
    """Background task: DM users whose streak broke."""
    while True:
        today = dt.date.today()

        for uid, s in list(_streaks.items()):
            if s.alerts_on and s.last_date and (today - s.last_date).days >= 2:
                try:
                    await bot.send_message(
                        uid,
                        "⚠️ You missed a day and your streak reset. "
                        "Jump back in with /checkin!",
                    )
                except Exception:
                    pass            # user may have blocked the bot
                s.alerts_on = False  # mute further alerts until they re-enable

        await asyncio.sleep(3600)    # run every hour

# ──────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    app.add_handler(CommandHandler("checkin",        checkin))
    app.add_handler(CommandHandler("mystreak",       mystreak))
    app.add_handler(CommandHandler("streak_alerts",  streak_alerts))

    # launch the background checker once the app is up
    app.create_task(_hourly_loop(app.bot))
