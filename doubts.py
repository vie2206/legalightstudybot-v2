# doubts.py
import enum, time, contextlib
from typing import Optional
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from database import session_scope, Doubt, DoubtQuota

# ─── States ─────────────────────────
SUBJECT, SUBJECT_CUSTOM, NATURE, NATURE_CUSTOM, DETAILS = range(5)

# ─── Admin to notify ─────────────────
_admin_id: int

# ─── Helpers ─────────────────────────
class Subject(enum.Enum):
    ENGLISH = "English & RC"
    LEGAL   = "Legal Reasoning"
    LOGICAL = "Logical Reasoning"
    MATHS   = "Maths"
    GK_CA   = "GK / CA"
    MOCK    = "Mock Test"
    SECTION = "Sectional Test"
    STRAT   = "Strategy / Time-Mgmt"
    APP     = "Application / College"
    OTHER   = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE      = "Can’t solve"
    DONT_UNDERSTAND = "Don’t understand answer"
    EXPLAIN_WRONG   = "Explain my wrong answer"
    CONCEPT         = "Concept clarification"
    ALT_METHOD      = "Need alternative method"
    REFERENCE       = "Source / reference request"
    TIME_MGMT       = "Time-management advice"
    TEST_STRAT      = "Test-taking strategy"
    OTHER           = "Other / Custom"

def _make_keyboard(enums: enum.EnumMeta, custom_state: int) -> InlineKeyboardMarkup:
    kb = [
        InlineKeyboardButton(e.value, callback_data=f"{enums.__name__}|{e.name}")
        for e in enums
    ]
    # chunk into rows of 2
    buttons = [kb[i : i + 2] for i in range(0, len(kb), 2)]
    return InlineKeyboardMarkup(buttons)

async def cmd_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # quota check
    uid = update.effective_user.id
    err = await _check_quota(uid)
    if err:
        return await update.message.reply_text(err)  # quota hit

    await update.message.reply_text(
        "📚 *Select subject:*",
        parse_mode="Markdown",
        reply_markup=_make_keyboard(Subject, SUBJECT_CUSTOM),
    )
    return SUBJECT

async def _check_quota(uid: int) -> Optional[str]:
    today = time.strftime("%Y-%m-%d")
    with session_scope() as db:
        quota = db.get(DoubtQuota, (uid, today))
        if not quota:
            quota = DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            db.add(quota)
            db.commit()
        if quota.private_count >= 3:
            return "⚠️ You’ve reached your 3 private doubts today."
    return None

async def subject_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    kind, sel = query.data.split("|", 1)
    if kind != "Subject":
        return ConversationHandler.END
    if sel == "OTHER":
        await query.edit_message_text("✏️ Enter custom subject (≤30 chars):")
        return SUBJECT_CUSTOM
    context.user_data["subject"] = Subject[sel].value
    await query.edit_message_text(f"*Subject:* {Subject[sel].value}\n\nNow select *nature*:",
        parse_mode="Markdown",
        reply_markup=_make_keyboard(Nature, NATURE_CUSTOM),
    )
    return NATURE

async def subject_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()[:30]
    context.user_data["subject"] = txt
    await update.message.reply_text(
        f"*Subject:* {txt}\n\nNow select *nature*:",
        parse_mode="Markdown",
        reply_markup=_make_keyboard(Nature, NATURE_CUSTOM),
    )
    return NATURE

async def nature_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    kind, sel = query.data.split("|", 1)
    if sel == "OTHER":
        await query.edit_message_text("✏️ Enter custom nature (≤30 chars):")
        return NATURE_CUSTOM
    context.user_data["nature"] = Nature[sel].value
    await query.edit_message_text(
        f"*{context.user_data['subject']}* → *{Nature[sel].value}*\n\n"
        "Now send your *doubt detail* (text or one photo):",
        parse_mode="Markdown"
    )
    return DETAILS

async def nature_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()[:30]
    context.user_data["nature"] = txt
    await update.message.reply_text(
        f"*{context.user_data['subject']}* → *{txt}*\n\n"
        "Now send your *doubt detail* (text or one photo):",
        parse_mode="Markdown"
    )
    return DETAILS

async def details_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    chat = update.effective_chat.id
    # store in DB
    with session_scope() as db:
        d = Doubt(
            user_id=uid,
            subject=context.user_data["subject"],
            nature=context.user_data["nature"],
            detail_text=update.message.text or "",
            detail_photo=update.message.photo[-1].file_id if update.message.photo else None,
            timestamp=int(time.time()),
        )
        db.add(d)
        q = db.get(DoubtQuota, (uid, time.strftime("%Y-%m-%d")))
        q.private_count += 1
        db.commit()

    # notify admin privately
    await context.bot.send_message(
        _admin_id,
        f"❓ *New Doubt* from {update.effective_user.full_name}:\n"
        f"• Subject: {d.subject}\n"
        f"• Nature: {d.nature}\n"
        f"• Detail: {d.detail_text or '(photo)'}",
        parse_mode="Markdown",
    )
    await update.message.reply_text("✅ Your doubt has been sent to the admin.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Doubt cancelled.")
    return ConversationHandler.END

def register_handlers(app: Application, admin_id: int):
    global _admin_id
    _admin_id = admin_id

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            SUBJECT:        [CallbackQueryHandler(subject_chosen, pattern="^Subject\\|")],
            SUBJECT_CUSTOM:[MessageHandler(filters.TEXT & ~filters.COMMAND, subject_custom)],
            NATURE:         [CallbackQueryHandler(nature_chosen, pattern="^Nature\\|")],
            NATURE_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, nature_custom)],
            DETAILS:       [MessageHandler(filters.TEXT | filters.PHOTO, details_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)
