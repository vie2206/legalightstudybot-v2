# streak.py – simple, async loop every hour (no JobQueue)
import asyncio, datetime as dt
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

class Streak: __slots__=("days","last","alerts"); 
streaks={}

async def checkin(u:Update,_):
    uid=u.effective_user.id; today=dt.date.today()
    s=streaks.setdefault(uid,Streak()); 
    if not hasattr(s,"days"): s.days=0;s.last=None;s.alerts=True
    if s.last==today: return await u.message.reply_text("Already checked-in!")
    s.days = s.days+1 if s.last and (today-s.last).days==1 else 1
    s.last=today
    await u.message.reply_text(f"🔥 Streak {s.days} day(s)")

async def mystreak(u:Update,_):
    s=streaks.get(u.effective_user.id)
    if not s: return await u.message.reply_text("No streak yet.")
    await u.message.reply_text(f"Current streak: {s.days} days (last {s.last})")

async def toggle(u:Update,ctx):
    arg=(ctx.args[0].lower() if ctx.args else "")
    if arg not in ("on","off"): return await u.message.reply_text("Use on/off")
    s=streaks.setdefault(u.effective_user.id,Streak()); s.alerts=(arg=="on")
    await u.message.reply_text(f"Alerts {'ON' if s.alerts else 'OFF'}")

async def _hourly(bot):
    while True:
        today=dt.date.today()
        for uid,s in streaks.items():
            if s.alerts and s.last and (today-s.last).days>=2:
                try: await bot.send_message(uid,"⚠️ You broke your streak.")
                except: pass
                s.alerts=False
        await asyncio.sleep(3600)

def register_handlers(app:Application):
    app.add_handler(CommandHandler("checkin",checkin))
    app.add_handler(CommandHandler("mystreak",mystreak))
    app.add_handler(CommandHandler("streak_alerts",toggle))
    async def _post_init(a): a.create_task(_hourly(a.bot))
    app.post_init(_post_init)
