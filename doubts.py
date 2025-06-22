# doubts.py
import datetime as dt
import enum
from contextlib import suppress

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import session_scope, Doubt, DoubtQuota

# ────────── Conversation states ──────────
(
    ASK_SUBJECT, ASK_CUSTOM_SUBJ,
    ASK_NATURE,  ASK_CUSTOM_NAT,
    ASK_TEXT,    ASK_MEDIA,
    ADMIN_CHOICE, ADMIN_REPLY
) = range(8)

# ────────── Doubt categories ──────────
class Subject(enum.Enum):
    ENGLISH_RC   = "English & RC"
    LEGAL        = "Legal Reasoning"
    LOGICAL      = "Logical Reasoning"
    MATHS        = "Maths"
    GK_CA        = "GK / CA"
    MOCK         = "Mock Test"
    SECTIONAL    = "Sectional Test"
    TIME_MGMT    = "Strategy / Time-Mgmt"
    COLLEGE_APP  = "Application / College"
    OTHER        = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE      = "Can’t solve"
    DONT_UNDERSTAND = "Don’t understand solution"
    EXPLAIN_WRONG   = "Explain my wrong answer"
    CONCEPT_CLARIFY = "Concept clarification"
    ALT_METHOD      = "Need alternative method"
    SOURCE_REQUEST  = "Source / reference"
    TIME_ADVICE     = "Time-management advice"
    STRAT_ADVICE    = "Test-taking strategy"
    OTHER           = "Other / Custom"

# ────────── Helpers ──────────
async def _check_quota(user_id: int, public: bool = False) -> str | None:
    """Ensure user hasn’t exceeded daily quotas."""
    today = dt.date.today()
    with session_scope() as db:
        quota = db.get(DoubtQuota, (user_id, today))
        if not quota:
            quota = DoubtQuota(
                user_id=user_id,
                date=today,
                public_count=0,
                private_count=0,
            )
            db.add(quota)
            db.commit()
        cnt = quota.public_count if public else quota.private_count
        limit = 2 if public else 3
        if cnt >= limit:
            return (
                f"🚫 You’ve reached your {'public' if public else 'private'}-doubt limit "
                f"({limit}/day). Upgrade for more!"
            )
    return None

# ────────── Handlers ──────────
async def cmd_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /doubt."""
    err = await _check_quota(update.effective_user.id, public=False)
    if err:
        return await update.message.reply_text(err) or ConversationHandler.END

    # build subject keyboard
    kb = [
        [InlineKeyboardButton(subj.value, callback_data=f"S|{subj.name}")]
        for subj in Subject
    ]
    await update.message.reply_text(
        "📚 Select subject of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ASK_SUBJECT

async def subject_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    _, name = q.data.split("|", 1)
    if name == Subject.OTHER.name:
        await q.edit_message_text("✏️ Enter custom subject (≤30 chars):")
        return ASK_CUSTOM_SUBJ

    context.user_data["subject"] = Subject[name].value
    return await _ask_nature(q, context)

async def custom_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subject"] = update.message.text.strip()[:30]
    return await _ask_nature(update, context)

async def _ask_nature(orig, context) -> int:
    kb = [
        [InlineKeyboardButton(nat.value, callback_data=f"N|{nat.name}")]
        for nat in Nature
    ]
    await orig.edit_message_text(
        "❓ Select nature of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ASK_NATURE

async def nature_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    _, name = q.data.split("|", 1)
    if name == Nature.OTHER.name:
        await q.edit_message_text("✏️ Enter custom nature (≤30 chars):")
        return ASK_CUSTOM_NAT

    context.user_data["nature"] = Nature[name].value
    await q.edit_message_text("📝 Describe your doubt in text (or send /skip):")
    return ASK_TEXT

async def custom_nature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nature"] = update.message.text.strip()[:30]
    await update.message.reply_text("📝 Describe your doubt in text (or send /skip):")
    return ASK_TEXT

async def text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["text"] = update.message.text
    await update.message.reply_text("📸 You may attach a photo (or send /skip):")
    return ASK_MEDIA

async def skip_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["text"] = None
    await update.message.reply_text("📸 You may attach a photo (or send /skip):")
    return ASK_MEDIA

async def media_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    f = update.message.photo[-1].file_id if update.message.photo else None
    context.user_data["media"] = f
    return await _save_and_notify(update, context)

async def skip_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["media"] = None
    return await _save_and_notify(update, context)

async def _save_and_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = {
        "user_id": update.effective_user.id,
        "subject": context.user_data["subject"],
        "nature":  context.user_data["nature"],
        "text":    context.user_data.get("text"),
        "media":   context.user_data.get("media"),
        "date":    dt.datetime.utcnow(),
    }
    with session_scope() as db:
        doubt = Doubt(**data)
        db.add(doubt)
        # increment private quota
        today = dt.date.today()
        quota = db.get(DoubtQuota, (doubt.user_id, today))
        quota.private_count += 1
        db.commit()

    await update.message.reply_text("✅ Your doubt has been recorded! We’ll get back soon.")
    return ConversationHandler.END

# ────────── Admin answer flow (simplified) ──────────
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: list pending doubts."""
    with session_scope() as db:
        pending = db.query(Doubt).filter_by(answered=False).all()
    if not pending:
        return await update.message.reply_text("✅ No pending doubts.")
    text = "\n".join(f"{d.id}: {d.subject} – {d.nature}" for d in pending)
    await update.message.reply_text(text)

async def pick_for_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, dud_id = q.data.split("|", 1)
    context.user_data["answering"] = int(dud_id)
    await q.edit_message_text("📝 Send your answer text (or /skip to attach media):")
    return ADMIN_REPLY

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dud_id = context.user_data["answering"]
    media = None
    text = None
    if update.message.photo:
        media = update.message.photo[-1].file_id
    else:
        text = update.message.text

    with session_scope() as db:
        d = db.get(Doubt, dud_id)
        d.answered = True
        d.answer_text = text
        d.answer_media = media
        db.commit()

    # post both question & answer publicly
    await update.message.reply_text(
        f"❓ {d.subject} – {d.nature}\n\n📝 Q: {d.text or '(no text)'}"
    )
    if media:
        await update.message.reply_photo(media, caption="🗒️ Answer:")
    elif text:
        await update.message.reply_text(f"🗒️ Answer: {text}")

    return ConversationHandler.END

# ────────── Registration ──────────
def register_handlers(app: Application):
    # student doubt flow
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJECT:    [CallbackQueryHandler(subject_chosen, pattern="^S\\|")],
            ASK_CUSTOM_SUBJ:[MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subject)],
            ASK_NATURE:     [CallbackQueryHandler(nature_chosen, pattern="^N\\|")],
            ASK_CUSTOM_NAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nature)],
            ASK_TEXT:       [
                              MessageHandler(filters.TEXT & ~filters.COMMAND, text_received),
                              CommandHandler("skip", skip_text),
                            ],
            ASK_MEDIA:      [
                              MessageHandler(filters.PHOTO, media_received),
                              CommandHandler("skip", skip_media),
                            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_chat=True,
    )
    app.add_handler(conv)

    # admin flow
    app.add_handler(CommandHandler("doubt_list", cmd_list))
    app.add_handler(
        CallbackQueryHandler(pick_for_answer, pattern=r"^ANS\\|\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(admin_reply, pattern=r"^REPLY$")
    )
