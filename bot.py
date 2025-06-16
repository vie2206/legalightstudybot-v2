import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import asyncio
import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")

# === Command Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to LegalightStudyBot!\n\n"
        "🧠 Use this bot for study timers, countdowns, quiz celebrations, and more.\n"
        "🎯 Motto: *We can do hard things.*",
        parse_mode="Markdown"
    )

async def pomodoro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(context.args[0]) if context.args else 25
        await update.message.reply_text(f"🍅 Starting Pomodoro for {minutes} minutes!\n*We can do hard things.*", parse_mode="Markdown")
        await asyncio.sleep(minutes * 60)
        await update.message.reply_text("✅ Pomodoro complete! Take a break.\n*We can do hard things.*", parse_mode="Markdown")
    except:
        await update.message.reply_text("Usage: /pomodoro 25")

async def countdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_str = " ".join(context.args)
        target = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        now = datetime.datetime.now()
        delta = target - now
        if delta.total_seconds() <= 0:
            await update.message.reply_text("⏳ That time is in the past!")
        else:
            await update.message.reply_text(f"🕒 Countdown started to {time_str}!\n*We can do hard things.*", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("Usage: /countdown YYYY-MM-DD HH:MM")

async def announcewinner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in [123456789]:  # Replace with your Telegram user ID
        if context.args:
            winner = context.args[0]
            await update.message.reply_text(
                f"🎉 Congrats {winner}! You nailed the quiz! 💯\n"
                "🏆 You’re today’s winner!\n"
                "*We can do hard things.*\n"
                "🎊🎊🎊",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("Usage: /announcewinner @username")
    else:
        await update.message.reply_text("❌ You are not authorized to announce winners.")

# === Bot Setup ===

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("pomodoro", pomodoro))
app.add_handler(CommandHandler("countdown", countdown))
app.add_handler(CommandHandler("announcewinner", announcewinner))

if __name__ == "__main__":
    print("🤖 Bot is starting... Listening for commands.")
    app.run_polling()
