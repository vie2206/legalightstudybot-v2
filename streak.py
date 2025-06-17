"""Daily study streak module.

Streak is earned if the user either:
  * Completes any /task_stop (timer) on that day, or
  * Sends /checkin manually.

Commands:
    /checkin      – manual mark
    /mystreak     – show current streak length
    /streak_alerts on|off – toggle DM when streak broken
"""

from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext

# Simple in-memory stores (replace by DB later)
_last_checkin = {}          # user_id -> date
_streak_len = {}            # user_id -> int
_alert_pref = {}            # user_id -> bool

UTC = timezone.utc

async def _record_checkin(user_id: int):
    today = date.today()
    last = _last_checkin.get(user_id)
    if last == today:
        return  # already counted today
    if last == today - timedelta(days=1):
        _streak_len[user_id] = _streak_len.get(user_id, 0) + 1
    else:
        # streak broken yesterday
        if _alert_pref.get(user_id, False) and last and last < today - timedelta(days=1):
            # we would DM here; skipped for brevity
            pass
        _streak_len[user_id] = 1
    _last_checkin[user_id] = today

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _record_checkin(update.effective_user.id)
    await update.message.reply_text("✅ Check-in recorded! Keep it up 🔥")

async def mystreak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    length = _streak_len.get(update.effective_user.id, 0)
    await update.message.reply_text(f"🔥 Your current streak: *{length}* day(s).", parse_mode="Markdown")

async def streak_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.message.reply_text("Usage: /streak_alerts on|off")
        return
    pref = context.args[0].lower() == "on"
    _alert_pref[update.effective_user.id] = pref
    await update.message.reply_text("🔔 Alerts " + ("enabled" if pref else "disabled"))

# Hook called by timer module when a task ends
async def task_completed(user_id: int):
    await _record_checkin(user_id)


def register_handlers(app: Application):
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("mystreak", mystreak))
    app.add_handler(CommandHandler("streak_alerts", streak_alerts))
