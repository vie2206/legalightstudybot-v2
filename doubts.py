# doubts.py
"""
/doubt wizard ─ students raise doubts with Subject ▸ Nature ▸ question (text/photo/doc).
Admin receives each doubt with an inline keyboard:
   [Answer 🔓Public]   [Answer 🔒Private]

Quotas: 2 public + 3 private answers per user per day.
"""

import asyncio, datetime as dt, enum, textwrap, uuid
from typing import Optional

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, InputFile
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters,
)

from database import session_scope, Doubt, DoubtQuota


# ───────────────────────────── StrEnum shim (Py-3.10) ─────────────────────────
try:
    from enum import StrEnum            # Py-3.11+
except ImportError:                     # fallback
    class StrEnum(str, enum.Enum):
        pass


# ───────────────────────────── categories / natures ───────────────────────────
class Subject(StrEnum):
    ENGLISH       = "English & RC"
    LEGAL         = "Legal Reasoning"
    LOGICAL       = "Logical Reasoning"
    MATHS         = "Maths"
    GK_CA         = "GK / CA"
    MOCK          = "Mock Test"
    SECTIONAL     = "Sectional Test"
    STRATEGY      = "Strategy / Time-Mgmt"
    COLLEGE_APP   = "Application / College"
    OTHER         = "Other / Custom"

class Nature(StrEnum):
    CANT_SOLVE      = "Can’t solve a question"
    DONT_UNDERSTAND = "Don’t understand official answer"
    EXPL_WRONG      = "Explain my wrong answer"
    CONCEPT         = "Concept clarification"
    ALT_METHOD      = "Need alternative method"
    SOURCE_REQ      = "Source / reference request"
    TIME_MGMT       = "Time-management advice"
    TEST_STRAT      = "Test-taking strategy"
    OTHER           = "Other / Custom"


# ───────────────────────── conversation states ────────────────────────────────
CHOOSING_SUBJ, TYPING_CUSTOM_SUBJ, \
CHOOSING_NATURE, TYPING_CUSTOM_NATURE, \
WAITING_QUESTION, WAITING_ADMIN_ANS = range(6)

DAY = dt.timedelta(days=1)
ADMIN_ID = 803299591   # ← your Telegram numeric ID


# ───────────────────────── quota helper ───────────────────────────────────────
async def _check_quota(uid: int, public: bool) -> Optional[str]:
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, uid)
        if not q:
            q = DoubtQuota(user_id=uid, date=today,
                           public_count=0, private_count=0)
            s.add(q); s.commit()
        if q.date != today:                    # new day → reset
            q.date = today
            q.public_count = q.private_count = 0
            s.commit()

        if public and q.public_count >= 2:
            return "🚫 Daily *public* quota (2) reached – ask again tomorrow."
        if not public and q.private_count >= 3:
            return "🚫 Daily *private* quota (3) reached – ask again tomorrow."

        if public:   q.public_count   += 1
        else:        q.private_count += 1
        s.commit()
    return None


# ───────────────────────── /doubt entry point ────────────────────────────────
async def cmd_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(update.effective_user.id, public=False)   # quota counts *private* raise
    if err:
        return await update.message.reply_markdown(err)

    kb = [
        [InlineKeyboardButton(Subject.ENGLISH,       callback_data=f"s|{Subject.ENGLISH}")],
        [InlineKeyboardButton(Subject.LEGAL,         callback_data=f"s|{Subject.LEGAL}")],
        [InlineKeyboardButton(Subject.LOGICAL,       callback_data=f"s|{Subject.LOGICAL}")],
        [InlineKeyboardButton(Subject.MATHS,         callback_data=f"s|{Subject.MATHS}")],
        [InlineKeyboardButton(Subject.GK_CA,         callback_data=f"s|{Subject.GK_CA}")],
        [InlineKeyboardButton(Subject.MOCK,          callback_data=f"s|{Subject.MOCK}")],
        [InlineKeyboardButton(Subject.SECTIONAL,     callback_data=f"s|{Subject.SECTIONAL}")],
        [InlineKeyboardButton(Subject.STRATEGY,      callback_data=f"s|{Subject.STRATEGY}")],
        [InlineKeyboardButton(Subject.COLLEGE_APP,   callback_data=f"s|{Subject.COLLEGE_APP}")],
        [InlineKeyboardButton("➕ Other / Custom",    callback_data=f"s|{Subject.OTHER}")],
    ]
    await update.message.reply_text(
        "Choose the *subject* of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return CHOOSING_SUBJ


# ───────────────────────── Subject → Nature ──────────────────────────────────
async def subj_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    raw = q.data.split("|", 1)[1]
    if raw == Subject.OTHER:
        await q.edit_message_text("Type a *custom subject* (max 30 chars):", parse_mode="Markdown")
        return TYPING_CUSTOM_SUBJ
    context.user_data["subject"] = raw
    return await _ask_nature(q)

async def save_custom_subj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subject"] = update.message.text[:30]
    return await _ask_nature(update.message)

async def _ask_nature(msg_or_q):
    kb = [
        [InlineKeyboardButton("1️⃣ Can’t solve",          callback_data=f"n|{Nature.CANT_SOLVE}")],
        [InlineKeyboardButton("2️⃣ Don’t understand",     callback_data=f"n|{Nature.DONT_UNDERSTAND}")],
        [InlineKeyboardButton("3️⃣ Explain wrong answer", callback_data=f"n|{Nature.EXPL_WRONG}")],
        [InlineKeyboardButton("4️⃣ Concept clarification",callback_data=f"n|{Nature.CONCEPT}")],
        [InlineKeyboardButton("5️⃣ Alternative method",   callback_data=f"n|{Nature.ALT_METHOD}")],
        [InlineKeyboardButton("6️⃣ Source / reference",   callback_data=f"n|{Nature.SOURCE_REQ}")],
        [InlineKeyboardButton("7️⃣ Time-mgmt advice",     callback_data=f"n|{Nature.TIME_MGMT}")],
        [InlineKeyboardButton("8️⃣ Test-taking strategy", callback_data=f"n|{Nature.TEST_STRAT}")],
        [InlineKeyboardButton("➕ Other / Custom",        callback_data=f"n|{Nature.OTHER}")],
    ]
    await msg_or_q.edit_message_text(
        "Select the *nature* of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return CHOOSING_NATURE


async def nature_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    raw = q.data.split("|", 1)[1]
    if raw == Nature.OTHER:
        await q.edit_message_text("Type a *custom nature* (max 30 chars):", parse_mode="Markdown")
        return TYPING_CUSTOM_NATURE
    context.user_data["nature"] = raw
    return await _ask_question(q)

async def save_custom_nature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nature"] = update.message.text[:30]
    return await _ask_question(update.message)

async def _ask_question(msg_or_q):
    await msg_or_q.edit_message_text(
        textwrap.dedent(
            "*Send your doubt now*\n"
            "• Text (up to 400 chars) *or*\n"
            "• 1 photo *or* 1 PDF document.\n\n"
            "Use /cancel to abort."
        ),
        parse_mode="Markdown"
    )
    return WAITING_QUESTION


# ───────────────────────── capture question ──────────────────────────────────
async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = user.id
    subj   = context.user_data.get("subject", "Unknown")
    nature = context.user_data.get("nature", "Unknown")

    # extract payload
    text  = update.message.text_html or ""
    file_id = None
    file_type = None
    if update.message.photo:
        file_id   = update.message.photo[-1].file_id
        file_type = "photo"
    elif update.message.document:
        file_id   = update.message.document.file_id
        file_type = "document"

    # store DB
    with session_scope() as s:
        d = Doubt(
            id=str(uuid.uuid4()),
            user_id=chat_id,
            subject=subj,
            nature=nature,
            text=text[:400],
            file_id=file_id,
            file_type=file_type,
            answered=False,
            public=False,         # default; admin chooses later
        )
        s.add(d)

    # notify student
    await update.message.reply_markdown(
        "📨 Your doubt has been sent to the mentor.\n"
        "_You’ll get a reply shortly._"
    )

    # send to admin
    kb = [
        [
            InlineKeyboardButton("Answer 🔓Public",  callback_data=f"ans|{d.id}|1"),
            InlineKeyboardButton("Answer 🔒Private", callback_data=f"ans|{d.id}|0"),
        ]
    ]
    caption = (
        f"*New doubt*\n"
        f"• User: {user.mention_html()}\n"
        f"• Subject: {subj}\n"
        f"• Nature: {nature}\n"
        f"• Text: {text or '_<no text>_'}"
    )
    if file_id and file_type == "photo":
        await context.bot.send_photo(
            ADMIN_ID, photo=file_id, caption=caption, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )
    elif file_id and file_type == "document":
        await context.bot.send_document(
            ADMIN_ID, document=file_id, caption=caption, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )
    else:
        await context.bot.send_message(
            ADMIN_ID, caption, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    return ConversationHandler.END


# ───────────────────────── admin answer flow ─────────────────────────────────
async def admin_answer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.callback_query.answer("Not for you!", show_alert=True)

    q = update.callback_query; await q.answer()
    _, doubt_id, pub_flag = q.data.split("|")
    context.user_data["answer_for"] = (doubt_id, bool(int(pub_flag)))

    await q.edit_message_reply_markup(reply_markup=None)
    await q.message.reply_text("✏️ Send your answer (text/photo/doc).")
    return WAITING_ADMIN_ANS


async def receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "answer_for" not in context.user_data:
        return  # ignore stray message
    doubt_id, is_public = context.user_data.pop("answer_for")

    # fetch stored doubt
    with session_scope() as s:
        d: Doubt = s.get(Doubt, doubt_id)
        if not d:
            return await update.message.reply_text("Original doubt not found.")
        d.answered = True
        d.public   = is_public
        s.commit()

    # forward answer
    target = d.user_id
    if update.message.photo:
        await context.bot.send_photo(target, update.message.photo[-1].file_id,
                                     caption=update.message.caption_html or "",
                                     parse_mode="HTML")
    elif update.message.document:
        await context.bot.send_document(target, update.message.document.file_id,
                                        caption=update.message.caption_html or "",
                                        parse_mode="HTML")
    else:
        await context.bot.send_message(target, update.message.text_html or "",
                                       parse_mode="HTML")

    # if public, also post to admin chat (thread)
    if is_public:
        await context.bot.send_message(
            ADMIN_ID,
            f"📣 *Public answer sent* to {target}.\n"
            f"Subject: {d.subject}\nNature: {d.nature}",
            parse_mode="Markdown"
        )
    await update.message.reply_text("✅ Answer delivered.")
    return ConversationHandler.END


# ───────────────────────── registration ──────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            CHOOSING_SUBJ:           [CallbackQueryHandler(subj_chosen,   pattern=r"^s\|")],
            TYPING_CUSTOM_SUBJ:      [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                     save_custom_subj)],
            CHOOSING_NATURE:         [CallbackQueryHandler(nature_chosen, pattern=r"^n\|")],
            TYPING_CUSTOM_NATURE:    [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                     save_custom_nature)],
            WAITING_QUESTION:        [MessageHandler(filters.Document.ALL |
                                                     filters.PHOTO |
                                                     filters.TEXT, receive_question)],
            WAITING_ADMIN_ANS:       [MessageHandler(filters.Document.ALL |
                                                     filters.PHOTO |
                                                     filters.TEXT, receive_answer)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_chat=True,
    )
    app.add_handler(conv)
    # admin entry for answer buttons
    app.add_handler(CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|"))
