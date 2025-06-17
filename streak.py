# streak.py
# Module: Streak Tracking (commands: /checkin, /mystreak, /streak_alerts)

from datetime import date, timedelta
from database import SessionLocal
from models import Checkin, StreakAlert  # Ensure StreakAlert is defined in models.py
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application


def register_handlers(app: Application):
    """Register all streak-tracking handlers on the Application."""
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("mystreak", mystreak))
    app.add_handler(CommandHandler("streak_alerts", streak_alerts))


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Record today's check-in for the user."""
    user_id = update.effective_user.id
    today = date.today()

    db = SessionLocal()
    entry = Checkin(user_id=user_id, date=today)
    db.merge(entry)
    db.commit()
    db.close()

    await update.message.reply_text("✅ Check-in recorded for today!")


async def mystreak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculate and display the user's current consecutive-day streak."""
    user_id = update.effective_user.id
    db = SessionLocal()
    # Fetch all dates user has checked in
    rows = (
        db.query(Checkin)
          .filter_by(user_id=user_id)
          .order_by(Checkin.date.desc())
          .all()
    )
    db.close()

    dates = {r.date for r in rows}
    streak = 0
    current = date.today()
    # Count backwards until a day is missing
    while current in dates:
        streak += 1
        current -= timedelta(days=1)

    await update.message.reply_text(f"🔥 Your current study streak is {streak} days!")


async def streak_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle DM notifications when a streak is broken."""
    user_id = update.effective_user.id
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.message.reply_text("Usage: /streak_alerts [on|off]")
        return

    enable = context.args[0].lower() == "on"
    db = SessionLocal()
    entry = StreakAlert(user_id=user_id, is_enabled=enable)
    db.merge(entry)
    db.commit()
    db.close()

    status = "enabled" if enable else "disabled"
    await update.message.reply_text(f"🔔 Streak alerts {status}!")
