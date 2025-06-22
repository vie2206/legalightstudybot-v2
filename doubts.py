# doubts.py

import enum
import datetime as dt
from contextlib import contextmanager

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from database import session_scope, Doubt, DoubtQuota

# ────────── Conversation states ──────────
(
    STATE_SUBJ,
    STATE_SUBJ_CUSTOM,
    STATE_NATURE,
    STATE_NATURE_CUSTOM,
    STATE_CONTENT,
) = range(5)

# ────────── Enums ──────────
class Subject(str, enum.Enum):
    ENGLISH       = "English"
    RC            = "Reading Comprehension"
    LEGAL         = "Legal Reasoning"
    LOGICAL       = "Logical Reasoning"
    MATHS         = "Maths"
    GK_CA         = "GK & CA"
    MOCK          = "Mock Test"
    SECTIONAL     = "Sectional Test"
    STRATEGY      = "Strategy / Time Management"
    APPLICATION   = "Application / College"
    OTHER         = "Other / Custom"

class Nature(str, enum.Enum):
    CANT_SOLVE       = "Can’t solve"
    DONT_UNDERSTAND  = "Don’t understand official answer"
    EXPLAIN_WRONG    = "Explain my wrong answer"
    CONCEPT          = "Concept clarification"
    ALT_METHOD       = "Need alternative method"
    SOURCE           = "Source / reference request"
    TIME_MGMT        = "Time-management advice"
    TEST_STRATEGY    = "Test-taking strategy"
    OTHER            = "Other / Custom"

# ────────── Handlers ──────────
async def cmd_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start /doubt: check quota, then ask subject."""
    user_id = update.effective_user.id
    err = await _check_quota(user_id, public=False)
    if err:
        return await update.message.reply_text(err)

    # build subject keyboard
    kb = [
        InlineKeyboardButton(s.value, callback_data=f"subj|{s.name}")
        for s in Subject
    ]
    # arrange 2 per row
    keyboard = [kb[i : i + 2] for i in range(0, len(kb), 2)]
    await update.message.reply_text(
        "📚 *Select the subject of your doubt:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return STATE_SUBJ

async def subj_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Subject button tapped."""
    q = update.callback_query
    await q.answer()
    _, raw = q.data.split("|", 1)
    if raw == Subject.OTHER.name:
        await q.edit_message_text("✏️ Please type your custom subject (≤30 chars):")
        return STATE_SUBJ_CUSTOM

    context.user_data["subject"] = Subject[raw].value
    return await _ask_nature(q, context)

async def subj_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed a custom subject."""
    text = update.message.text.strip()[:30]
    context.user_data["subject"] = text
    await update.message.reply_text(f"✅ Subject set to *{text}*.", parse_mode="Markdown")
    return await _ask_nature(update, context)

async def _ask_nature(msg_or_q, context):
    """Helper to show nature-of-doubt keyboard."""
    kb = [
        InlineKeyboardButton(n.value, callback_data=f"nat|{n.name}")
        for n in Nature
    ]
    keyboard = [kb[i : i + 2] for i in range(0, len(kb), 2)]
    if hasattr(msg_or_q, "edit_message_text"):
        await msg_or_q.edit_message_text(
            "❓ *Select the nature of your doubt:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await msg_or_q.message.reply_text(
            "❓ *Select the nature of your doubt:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    return STATE_NATURE

async def nat_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nature button tapped."""
    q = update.callback_query
    await q.answer()
    _, raw = q.data.split("|", 1)
    if raw == Nature.OTHER.name:
        await q.edit_message_text("✏️ Please type your custom nature (≤30 chars):")
        return STATE_NATURE_CUSTOM

    context.user_data["nature"] = Nature[raw].value
    await q.edit_message_text(
        f"✅ Nature set to *{Nature[raw].value}*.\n\n"
        "📩 Now send your doubt as text or as a photo (caption is the doubt).",
        parse_mode="Markdown",
    )
    return STATE_CONTENT

async def nat_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed custom nature."""
    text = update.message.text.strip()[:30]
    context.user_data["nature"] = text
    await update.message.reply_text(
        f"✅ Nature set to *{text}*.\n\n"
        "📩 Now send your doubt as text or as a photo (caption is the doubt).",
        parse_mode="Markdown",
    )
    return STATE_CONTENT

async def receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive final doubt (text or photo+caption), store & notify admin."""
    user_id = update.effective_user.id
    subject = context.user_data["subject"]
    nature  = context.user_data["nature"]

    # extract content
    photo_id = None
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        content = update.message.caption or ""
    else:
        content = update.message.text or ""

    timestamp = dt.datetime.utcnow()

    # persist
    with session_scope() as db:
        # save doubt
        d = Doubt(
            user_id=user_id,
            subject=subject,
            nature=nature,
            content=content,
            photo_id=photo_id,
            timestamp=timestamp,
        )
        db.add(d)
        # update quota
        today = dt.date.today()
        pk = (user_id, today)
        quota = db.get(DoubtQuota, pk)
        quota.private_count += 1
        db.commit()

    await update.message.reply_text("✅ Your doubt has been submitted. Thanks!")

    # notify admin
    admin_id = context.bot_data.get("admin_id")
    text = (
        f"🆕 *New Doubt*\n"
        f"• From: `{update.effective_user.id}`\n"
        f"• Subject: *{subject}*\n"
        f"• Nature: *{nature}*\n"
        f"• Content: {content}"
    )
    if photo_id:
        await context.bot.send_photo(
            chat_id=admin_id,
            photo=photo_id,
            caption=text,
            parse_mode="Markdown",
        )
    else:
        await context.bot.send_message(
            chat_id=admin_id,
            text=text,
            parse_mode="Markdown",
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Doubt submission canceled.")
    return ConversationHandler.END

# ────────── Quota check helper ──────────
async def _check_quota(user_id: int, public: bool) -> str | None:
    """
    Ensure user hasn't exceeded daily limit (3 private / 2 public).
    Returns an error message if over limit, else None.
    """
    today = dt.date.today()
    with session_scope() as db:
        pk = (user_id, today)
        quota = db.get(DoubtQuota, pk)
        if not quota:
            # create new for today
            quota = DoubtQuota(
                user_id=user_id,
                date=today,
                public_count=0,
                private_count=0,
                last_reset=dt.datetime.utcnow(),
            )
            db.add(quota)
            db.commit()
        count = quota.public_count if public else quota.private_count
        limit = 2 if public else 3
        if count >= limit:
            return (
                f"❌ You’ve reached your daily {'public' if public else 'private'} "
                f"doubt limit of {limit}. Please try again tomorrow."
            )
    return None

# ────────── Registration ──────────
def register_handlers(app: Application, admin_id: int):
    # make admin_id available
    app.bot_data["admin_id"] = admin_id

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            STATE_SUBJ:            [CallbackQueryHandler(subj_chosen, pattern=r"^subj\|")],
            STATE_SUBJ_CUSTOM:     [MessageHandler(filters.TEXT & ~filters.COMMAND, subj_custom)],
            STATE_NATURE:          [CallbackQueryHandler(nat_chosen, pattern=r"^nat\|")],
            STATE_NATURE_CUSTOM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, nat_custom)],
            STATE_CONTENT:         [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, receive_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=False,
    )
    app.add_handler(conv)
