# doubts.py

import os
import enum
import datetime as dt
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from database import session_scope, Doubt, DoubtQuota

# ─────────────────────────────────────────────────────────────────────────────
# Admin ID (set this env var in your Render dashboard)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# daily quota limits
PUBLIC_LIMIT  = 2
PRIVATE_LIMIT = 3

# ──────────────────────────────────────────────────────────
class Subject(str, enum.Enum):
    ENGLISH           = "English"
    LEGAL_REASONING   = "Legal Reasoning"
    LOGICAL_REASONING = "Logical Reasoning"
    MATHS             = "Maths"
    GK_CA             = "GK/CA"
    MOCK_TEST         = "Mock Test"
    SECTIONAL         = "Sectional Test"
    STRATEGY          = "Strategy / Time-Mgmt"
    APPLICATION       = "Application / College"
    OTHER             = "Other / Custom"

class Nature(str, enum.Enum):
    CANT_SOLVE          = "Can’t solve a question"
    DONT_UNDERSTAND     = "Don’t understand the official answer"
    EXPLAIN_WRONG       = "Explain my wrong answer"
    CONCEPT             = "Concept clarification"
    ALTERNATIVE         = "Need alternative method"
    SOURCE              = "Source / reference request"
    TIME_MANAGEMENT     = "Time-management advice"
    TEST_STRATEGY       = "Test-taking strategy"
    OTHER               = "Other / Custom"

# Conversation states
ASK_SUBJ, ASK_SUBJ_CUSTOM, ASK_NAT, ASK_NAT_CUSTOM, ASK_TEXT, ASK_PHOTO = range(6)

# ──────────────────────────────────────────────────────────
async def cmd_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /doubt"""
    user_id = update.effective_user.id
    err = _check_quota(user_id, public=False)  # raising a doubt counts as *private*
    if err:
        return await update.message.reply_text(err)

    # build subject keyboard
    kb = [
        [InlineKeyboardButton(s.value, callback_data=s.name)]
        for s in Subject
        if s is not Subject.OTHER
    ]
    # add custom
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="OTHER")])
    await update.message.reply_text(
        "📝 *Select the subject*: ",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return ASK_SUBJ

async def subject_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data == "OTHER":
        await q.edit_message_text("✏️ Enter custom subject (≤ 30 chars):")
        return ASK_SUBJ_CUSTOM

    subj = Subject[q.data].value
    context.user_data["subject"] = subj
    return await _ask_nature(q)

async def subject_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()[:30]
    context.user_data["subject"] = text
    await update.message.reply_text("🔍 Now select nature of your doubt:")
    return ASK_NAT

async def _ask_nature(q_or_msg):
    kb = [
        [InlineKeyboardButton(n.value, callback_data=n.name)]
        for n in Nature
        if n is not Nature.OTHER
    ]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="OTHER_N")])
    return await q_or_msg.edit_message_text(
        "🔍 *Select the nature* of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    ) if isinstance(q_or_msg, type(update := None)) else None  # fallback

async def nature_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data == "OTHER_N":
        await q.edit_message_text("✏️ Enter custom nature (≤ 30 chars):")
        return ASK_NAT_CUSTOM

    nat = Nature[q.data].value
    context.user_data["nature"] = nat
    # ask for text or photo
    await q.edit_message_text(
        "📄 Now send your question as text or send *one* photo (no other file types).",
        parse_mode="Markdown"
    )
    return ASK_TEXT

async def nature_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()[:30]
    context.user_data["nature"] = text
    await update.message.reply_text(
        "📄 Send your question as text or attach *one* photo (no videos).",
        parse_mode="Markdown"
    )
    return ASK_TEXT

async def text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["text"] = update.message.text[:500]
    return await _save_and_notify(update, context)

async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # take only the last photo
    photo = update.message.photo[-1]
    context.user_data["photo_file_id"] = photo.file_id
    return await _save_and_notify(update, context)

async def _save_and_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save to DB and notify the admin privately."""
    user_id = update.effective_user.id
    data    = context.user_data
    subj    = data["subject"]
    nat     = data["nature"]
    txt     = data.get("text")
    photo   = data.get("photo_file_id")
    is_public = False  # always private until admin publishes

    # persist
    with session_scope() as db:
        d = Doubt(
            user_id=user_id,
            subject=subj,
            nature=nat,
            text=txt,
            photo_file_id=photo,
            is_public=is_public,
        )
        db.add(d)

    # notify user
    await update.message.reply_text("✅ Your doubt has been recorded. We'll get back soon!")

    # forward to admin
    if ADMIN_ID:
        bot = context.bot
        msg = f"🆕 *New Doubt* from `{update.effective_user.username or user_id}`\n" \
              f"*Subject:* {subj}\n*Nature:* {nat}"
        await bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
        if txt:
            await bot.send_message(ADMIN_ID, txt)
        if photo:
            await bot.send_photo(ADMIN_ID, photo)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Doubt submission cancelled.")
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────
def _check_quota(user_id: int, public: bool) -> str|None:
    """Enforce daily quotas."""
    today = dt.date.today()
    with session_scope() as db:
        # composite PK get via tuple
        quota = db.get(DoubtQuota, (user_id, today))
        if not quota:
            quota = DoubtQuota(user_id=user_id, date=today, public_count=0, private_count=0)
            db.add(quota)
            db.commit()
        cnt = quota.public_count if public else quota.private_count
        limit = PUBLIC_LIMIT if public else PRIVATE_LIMIT
        if cnt >= limit:
            return f"⚠️ You’ve reached your daily {'public' if public else 'private'} quota ({limit})."
        # increment
        if public:
            quota.public_count += 1
        else:
            quota.private_count += 1
        db.commit()
    return None

# ──────────────────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:            [CallbackQueryHandler(subject_chosen)],
            ASK_SUBJ_CUSTOM:     [MessageHandler(filters.TEXT & ~filters.COMMAND, subject_custom)],
            ASK_NAT:             [CallbackQueryHandler(nature_chosen)],
            ASK_NAT_CUSTOM:      [MessageHandler(filters.TEXT & ~filters.COMMAND, nature_custom)],
            ASK_TEXT:            [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_received),
                MessageHandler(filters.PHOTO,              photo_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)
