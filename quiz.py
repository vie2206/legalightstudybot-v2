# quiz.py

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

async def quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args) if context.args else "General"
    # TODO: actually forward QuizBot’s quiz here
    await update.message.reply_text(f"🎲 Quiz “{topic}” imported! Answers will be tracked for 24 h.")

async def quiz_winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: fetch leaderboard from QuizBot after 24 h
    await update.message.reply_text(
        "🏆 Quiz winners:\n"
        "1. @first_place\n"
        "2. @second_place\n"
        "3. @third_place\n\n"
        "🎉🎉🎉"
    )

def register_handlers(app):
    app.add_handler(CommandHandler("quiz_start", quiz_start))
    app.add_handler(CommandHandler("quiz_winner", quiz_winner))
