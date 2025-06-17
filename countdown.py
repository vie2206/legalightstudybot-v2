# countdown.py  – interactive live-countdown wizard
from datetime import datetime, timedelta, timezone
import asyncio

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

DATE, TIME, LABEL, CONFIRM = range(4)
COUNTDOWNS = {}          # chat_id → asyncio.Task
PINNED_MSG = {}          # chat_id → message_id


# ───────────────────────────────────────────── entry
async def countdown_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Offer buttons for today … +6 days
    today = datetime.now(timezone.utc).date()
    rows = []
    for i in range(7):
        d = today + timedelta(days=i)
        rows.append(
            [InlineKeyboardButton(d.strftime("%a %d %b"), callback_data=f"DATE|{d.isoformat()}")]
        )
    rows.append([InlineKeyboardButton("Other 📅", callback_data="DATE|manual")])
    await update.message.reply_text(
        "📅 *Pick the event date*:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )
    return DATE


# ───────────────────────────────────────────── date chosen
async def date_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    _, payload = query.data.split("|", 1)

    if payload == "manual":
        await query.edit_message_text("📅 Send the date as *YYYY-MM-DD*:")
        return DATE     # wait for text
    else:
        context.user_data["date"] = payload
        return await ask_time(query)


async def receive_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.text.strip()
    try:
        datetime.fromisoformat(txt)
        context.user_data["date"] = txt
        return await ask_time(update)
    except ValueError:
        return await update.reply_text("❌ Please send the date in YYYY-MM-DD format.")


# ───────────────────────────────────────────── time
async def ask_time(msg_or_query):
    rows = [[
        InlineKeyboardButton("00:00", callback_data="TIME|00:00:00"),
        InlineKeyboardButton("06:00", callback_data="TIME|06:00:00"),
        InlineKeyboardButton("12:00", callback_data="TIME|12:00:00"),
        InlineKeyboardButton("18:00", callback_data="TIME|18:00:00"),
    ], [InlineKeyboardButton("Other ⌨️", callback_data="TIME|manual")]]
    text = "⏰ *Select event time (UTC)*:"
    if isinstance(msg_or_query, Update):          # came from text handler
        await msg_or_query.reply_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
    else:                                         # came from callback query
        await msg_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
    return TIME


async def time_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    _, payload = query.data.split("|", 1)

    if payload == "manual":
        await query.edit_message_text("⏰ Send the time as *HH:MM:SS* (24 h UTC):")
        return TIME
    else:
        context.user_data["time"] = payload
        await query.edit_message_text("📝 *Now send a short label for this event:*", parse_mode="Markdown")
        return LABEL


async def receive_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.text.strip()
    try:
        datetime.strptime(txt, "%H:%M:%S")
        context.user_data["time"] = txt
        await update.reply_text("📝 *Now send a short label for this event:*", parse_mode="Markdown")
        return LABEL
    except ValueError:
        return await update.reply_text("❌ Time must be HH:MM:SS (24 h).")


# ───────────────────────────────────────────── label
async def label_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["label"] = update.text[:60]
    # Ask whether to pin
    rows = [[
        InlineKeyboardButton("Start & pin 📌", callback_data="GO|pin"),
        InlineKeyboardButton("Start (no pin)", callback_data="GO|nopin"),
    ]]
    await update.reply_text(
        "✅ Ready to start!\nPin this message?", reply_markup=InlineKeyboardMarkup(rows)
    )
    return CONFIRM


# ───────────────────────────────────────────── go
async def countdown_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    _, pin_choice = query.data.split("|", 1)

    # build target datetime (in UTC)
    target = datetime.fromisoformat(context.user_data["date"] + "T" + context.user_data["time"]).replace(tzinfo=timezone.utc)
    label  = context.user_data["label"]
    chat_id = query.message.chat_id

    async def updater(msg_id: int):
        try:
            while True:
                remaining = target - datetime.now(timezone.utc)
                if remaining.total_seconds() <= 0:
                    break
                days, rem = divmod(int(remaining.total_seconds()), 86400)
                hrs, rem  = divmod(rem, 3600)
                mins, secs = divmod(rem, 60)
                text = (
                    f"⏳ *{label}*\n"
                    f"`{days:02d}d {hrs:02d}:{mins:02d}:{secs:02d}` remaining."
                )
                await context.bot.edit_message_text(
                    text=text, chat_id=chat_id, message_id=msg_id,
                    parse_mode="Markdown"
                )
                await asyncio.sleep(10)
        finally:
            await context.bot.edit_message_text(
                f"🎉 *{label} is happening now!*", chat_id=chat_id, message_id=msg_id, parse_mode="Markdown"
            )
            if pin_choice == "pin":
                await context.bot.unpin_chat_message(chat_id, msg_id)
            COUNTDOWNS.pop(chat_id, None)

    # initial message
    m = await query.edit_message_text("⏳ Preparing countdown…")
    if pin_choice == "pin":
        try:
            await context.bot.pin_chat_message(chat_id, m.message_id, disable_notification=True)
            PINNED_MSG[chat_id] = m.message_id
        except:
            pass

    task = asyncio.create_task(updater(m.message_id))
    # kill any previous
    if old := COUNTDOWNS.get(chat_id):
        old.cancel()
    COUNTDOWNS[chat_id] = task
    return ConversationHandler.END


# ───────────────────────────────────────────── cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Countdown wizard canceled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ────────────────────────────────────────────── wiring
def register_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("countdown", countdown_start)],
        states={
            DATE:   [
                CallbackQueryHandler(date_chosen,  pattern=r"^DATE\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date_text),
            ],
            TIME:   [
                CallbackQueryHandler(time_chosen,  pattern=r"^TIME\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time_text),
            ],
            LABEL:  [MessageHandler(filters.TEXT & ~filters.COMMAND, label_received)],
            CONFIRM:[CallbackQueryHandler(countdown_go, pattern=r"^GO\|")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
