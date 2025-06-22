# doubts.py
import enum
import datetime as dt
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from database import session_scope, Doubt, DoubtQuota

# ENUMS for subject and nature
class Subject(enum.Enum):
    ENGLISH = "English & RC"
    LEGAL = "Legal Reasoning"
    LOGICAL = "Logical Reasoning"
    MATHS = "Maths"
    GKCA = "GK / CA"
    MOCK = "Mock Test"
    SECTIONAL = "Sectional Test"
    STRATEGY = "Strategy / Time-Mgmt"
    COLLEGE = "Application / College"
    OTHER = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE = "Can’t solve a question"
    NO_ANSWER = "Don’t understand the official answer"
    EXPLAIN_WRONG = "Explain my wrong answer"
    CONCEPT = "Concept clarification"
    ALT_METHOD = "Need alternative method"
    SOURCE = "Source / reference request"
    TIME = "Time-management advice"
    STRATEGY = "Test-taking strategy"
    OTHER = "Other / Custom"

# States for conversation
(ASK_SUBJECT, ASK_CUSTOM_SUBJECT, ASK_NATURE, ASK_CUSTOM_NATURE, ASK_DOUBT, ASK_PHOTO, CONFIRM) = range(7)

# Keyboard helpers
def subject_keyboard():
    kb = [[InlineKeyboardButton(subj.value, callback_data=f"subj|{subj.name}")]
          for subj in Subject if subj != Subject.OTHER]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="subj|OTHER")])
    return InlineKeyboardMarkup(kb)

def nature_keyboard():
    kb = [[InlineKeyboardButton(nat.value, callback_data=f"nature|{nat.name}")]
          for nat in Nature if nat != Nature.OTHER]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="nature|OTHER")])
    return InlineKeyboardMarkup(kb)

# Quota checker
async def _check_quota(uid, public=False):
    today = dt.date.today()
    with session_scope() as s:
        quota = s.query(DoubtQuota).filter_by(user_id=uid, date=today).first()
        if not quota:
            quota = DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            s.add(quota)
            s.commit()
        if public and quota.public_count >= 2:
            return "Daily public doubt quota reached. Upgrade to ask more."
        if not public and quota.private_count >= 3:
            return "Daily private doubt quota reached. Upgrade to ask more."
        return None

async def cmd_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(update.effective_user.id, public=False)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return ConversationHandler.END
    await update.message.reply_text(
        "Choose the *subject* of your doubt:",
        reply_markup=subject_keyboard(),
        parse_mode="Markdown"
    )
    return ASK_SUBJECT

async def pick_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    key = q.data.split("|", 1)[1]
    if key == "OTHER":
        await q.edit_message_text("Type your custom subject (≤30 chars):")
        return ASK_CUSTOM_SUBJECT
    context.user_data["subject"] = getattr(Subject, key).value
    await q.edit_message_text("Choose the *nature* of your doubt:",
                              reply_markup=nature_keyboard(),
                              parse_mode="Markdown")
    return ASK_NATURE

async def custom_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subject"] = update.message.text.strip()[:30]
    await update.message.reply_text(
        "Choose the *nature* of your doubt:",
        reply_markup=nature_keyboard(),
        parse_mode="Markdown")
    return ASK_NATURE

async def pick_nature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    key = q.data.split("|", 1)[1]
    if key == "OTHER":
        await q.edit_message_text("Type your custom nature (≤30 chars):")
        return ASK_CUSTOM_NATURE
    context.user_data["nature"] = getattr(Nature, key).value
    await q.edit_message_text("Describe your doubt. You can also attach a photo (PDF/photo only, *no video/audio*):",
                              parse_mode="Markdown")
    return ASK_DOUBT

async def custom_nature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nature"] = update.message.text.strip()[:30]
    await update.message.reply_text(
        "Describe your doubt. You can also attach a photo (PDF/photo only, *no video/audio*):",
        parse_mode="Markdown")
    return ASK_DOUBT

async def save_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Accepts text or photo
    user = update.effective_user
    photo = None
    file_id = None
    file_type = None
    text = update.message.text or ""
    if update.message.photo:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        file_type = "photo"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
    context.user_data["doubt_text"] = text
    context.user_data["file_id"] = file_id
    context.user_data["file_type"] = file_type
    # Save to DB
    with session_scope() as s:
        d = Doubt(
            user_id=user.id,
            username=user.username or "",
            subject=context.user_data["subject"],
            nature=context.user_data["nature"],
            question=text,
            file_id=file_id,
            file_type=file_type,
            asked_at=dt.datetime.now(),
            resolved=False,
            public=False,
        )
        s.add(d)
        # Increment quota
        q = s.query(DoubtQuota).filter_by(user_id=user.id, date=dt.date.today()).first()
        if q:
            q.private_count += 1
        s.commit()
        doubt_id = d.id
    await update.message.reply_text(
        "✅ Doubt submitted! Our team will review and reply soon."
    )
    # Notify admin
    context.bot_data['admin_id'] = context.bot_data.get('admin_id', None)
    if not context.bot_data['admin_id']:
        return ConversationHandler.END
    try:
        msg = f"🆕 Doubt #{doubt_id} from @{user.username or user.id}\n*Subject*: {context.user_data['subject']}\n*Nature*: {context.user_data['nature']}\n{ text[:4096] }"
        await context.bot.send_message(context.bot_data['admin_id'], msg, parse_mode="Markdown")
        # send photo/file if available
        if file_id and file_type == "photo":
            await context.bot.send_photo(context.bot_data['admin_id'], file_id)
        elif file_id and file_type == "document":
            await context.bot.send_document(context.bot_data['admin_id'], file_id)
    except Exception:
        pass
    return ConversationHandler.END

def register_handlers(app, admin_id):
    app.bot_data['admin_id'] = admin_id
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJECT: [CallbackQueryHandler(pick_subject, pattern=r"^subj\|")],
            ASK_CUSTOM_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subject)],
            ASK_NATURE: [CallbackQueryHandler(pick_nature, pattern=r"^nature\|")],
            ASK_CUSTOM_NATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nature)],
            ASK_DOUBT: [MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, save_doubt)],
        },
        fallbacks=[],
        per_chat=True,
    )
    app.add_handler(conv)
