# doubts.py  – full module, drop-in replacement
"""
/doubt  →  Subject 🔽  →  Nature 🔽  →  ask for text/photo  →
          choose Public / Private  →  stored & forwarded to ADMIN

Daily limits per user
---------------------
• Public doubts   : 2 / day
• Private doubts  : 3 / day
"""

import datetime as dt
from enum import Enum, auto

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ConversationHandler,
    MessageHandler, filters, ContextTypes
)

from database import session_scope, Doubt, DoubtQuota

# ──────────────────────────────────────────────────────────────
ADMIN_ID = 803299591          #  ← your Telegram ID

# Conversation states
SUBJECT, SUBJECT_CUSTOM, NATURE, NATURE_CUSTOM, QUESTION, PUBLICITY = range(6)

# ------------------------------------------------------------------
class Subject(str, Enum):
    ENGLISH   = "English & RC"
    LEGAL     = "Legal Reasoning"
    LOGICAL   = "Logical Reasoning"
    MATHS     = "Maths"
    GK_CA     = "GK / CA"
    MOCK      = "Mock Test"
    SECTIONAL = "Sectional Test"
    STRATEGY  = "Strategy / Time-Mgmt"
    COLLEGE   = "Application / College"
    OTHER     = "Other / Custom"

class Nature(str, Enum):
    CANT_SOLVE     = "Can’t solve a question"
    DONT_UNDERST   = "Don’t understand the official answer"
    EXPLAIN_WRONG  = "Explain my wrong answer"
    CONCEPT        = "Concept clarification"
    ALT_METHOD     = "Need alternative method"
    SOURCE_REQ     = "Source / reference request"
    TIME_MGMT      = "Time-management advice"
    STRATEGY       = "Test-taking strategy"
    OTHER          = "Other / Custom"

# ------------------------------------------------------------------
QUOTA_PUBLIC  = 2
QUOTA_PRIVATE = 3

async def _check_quota(uid: int, want_public: bool) -> str | None:
    """Return err-msg or None if quota available; also increments counter."""
    today = dt.date.today()
    with session_scope() as s:
        quota = (
            s.query(DoubtQuota)
            .filter_by(user_id=uid, date=today)
            .one_or_none()
        )
        if quota is None:
            quota = DoubtQuota(user_id=uid, date=today)   # counts = 0
            s.add(quota)

        if want_public and quota.public_count >= QUOTA_PUBLIC:
            return f"You’ve reached today’s *public* doubt limit ({QUOTA_PUBLIC})."
        if (not want_public) and quota.private_count >= QUOTA_PRIVATE:
            return f"You’ve reached today’s *private* doubt limit ({QUOTA_PRIVATE})."

        if want_public:
            quota.public_count += 1
        else:
            quota.private_count += 1
        s.add(quota)
    return None

# ──────────────────────────────────────────────────────────────
# Helpers to build keyboards
def _subject_kb() -> InlineKeyboardMarkup:
    btns = [
        [InlineKeyboardButton(Subject.ENGLISH,   callback_data=f"s|{Subject.ENGLISH}")],
        [InlineKeyboardButton(Subject.LEGAL,     callback_data=f"s|{Subject.LEGAL}")],
        [InlineKeyboardButton(Subject.LOGICAL,   callback_data=f"s|{Subject.LOGICAL}")],
        [InlineKeyboardButton(Subject.MATHS,     callback_data=f"s|{Subject.MATHS}")],
        [InlineKeyboardButton(Subject.GK_CA,     callback_data=f"s|{Subject.GK_CA}")],
        [InlineKeyboardButton(Subject.MOCK,      callback_data=f"s|{Subject.MOCK}")],
        [InlineKeyboardButton(Subject.SECTIONAL, callback_data=f"s|{Subject.SECTIONAL}")],
        [InlineKeyboardButton(Subject.STRATEGY,  callback_data=f"s|{Subject.STRATEGY}")],
        [InlineKeyboardButton(Subject.COLLEGE,   callback_data=f"s|{Subject.COLLEGE}")],
        [InlineKeyboardButton("Other / Custom ✏️", callback_data=f"s|{Subject.OTHER}")],
    ]
    return InlineKeyboardMarkup(btns)

def _nature_kb() -> InlineKeyboardMarkup:
    btns = [
        [InlineKeyboardButton(Nature.CANT_SOLVE,    callback_data=f"n|{Nature.CANT_SOLVE}")],
        [InlineKeyboardButton(Nature.DONT_UNDERST,  callback_data=f"n|{Nature.DONT_UNDERST}")],
        [InlineKeyboardButton(Nature.EXPLAIN_WRONG, callback_data=f"n|{Nature.EXPLAIN_WRONG}")],
        [InlineKeyboardButton(Nature.CONCEPT,       callback_data=f"n|{Nature.CONCEPT}")],
        [InlineKeyboardButton(Nature.ALT_METHOD,    callback_data=f"n|{Nature.ALT_METHOD}")],
        [InlineKeyboardButton(Nature.SOURCE_REQ,    callback_data=f"n|{Nature.SOURCE_REQ}")],
        [InlineKeyboardButton(Nature.TIME_MGMT,     callback_data=f"n|{Nature.TIME_MGMT}")],
        [InlineKeyboardButton(Nature.STRATEGY,      callback_data=f"n|{Nature.STRATEGY}")],
        [InlineKeyboardButton("Other / Custom ✏️",  callback_data=f"n|{Nature.OTHER}")],
    ]
    return InlineKeyboardMarkup(btns)

# =================================================================
# Conversation callbacks
async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose a *subject*:", parse_mode="Markdown",
                                    reply_markup=_subject_kb())
    return SUBJECT

async def subject_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    subj = q.data.split("|", 1)[1]
    if subj == Subject.OTHER:
        await q.edit_message_text("Enter a short custom *subject* (≤ 30 chars):",
                                  parse_mode="Markdown")
        return SUBJECT_CUSTOM
    ctx.user_data["subject"] = subj
    await q.edit_message_text("Now pick the *nature* of your doubt:",
                              parse_mode="Markdown", reply_markup=_nature_kb())
    return NATURE

async def custom_subject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"] = update.message.text.strip()[:30]
    await update.message.reply_text("Now pick the *nature* of your doubt:",
                                    parse_mode="Markdown", reply_markup=_nature_kb())
    return NATURE

async def nature_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    nat = q.data.split("|", 1)[1]
    if nat == Nature.OTHER:
        await q.edit_message_text("Enter a short custom *nature* (≤ 30 chars):",
                                  parse_mode="Markdown")
        return NATURE_CUSTOM
    ctx.user_data["nature"] = nat
    await q.edit_message_text(
        "Send your question *text* or *ONE photo* now.",
        parse_mode="Markdown"
    )
    return QUESTION

async def custom_nature(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"] = update.message.text.strip()[:30]
    await update.message.reply_text(
        "Send your question *text* or *ONE photo* now.",
        parse_mode="Markdown"
    )
    return QUESTION

async def received_question(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # store text or photo file_id
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        ctx.user_data["media_id"] = file_id
        ctx.user_data["question"] = "[photo]"   # placeholder text
    elif update.message.text:
        ctx.user_data["question"] = update.message.text.strip()
        ctx.user_data["media_id"] = None
    else:
        return await update.message.reply_text("Please send text or ONE photo.")

    # ask Public / Private
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Public 👥",  callback_data="pub|yes"),
         InlineKeyboardButton("Private 🔒", callback_data="pub|no")]
    ])
    await update.message.reply_text("How should I answer?", reply_markup=kb)
    return PUBLICITY

async def publicity_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    public = q.data.endswith("yes")

    # enforce quota
    err = await _check_quota(q.from_user.id, public)
    if err:
        await q.edit_message_text(err, parse_mode="Markdown")
        return ConversationHandler.END

    # store in DB
    with session_scope() as s:
        dbrow = Doubt(
            user_id   = q.from_user.id,
            subject   = ctx.user_data["subject"],
            nature    = ctx.user_data["nature"],
            question  = ctx.user_data["question"],
            media_id  = ctx.user_data["media_id"],
            public    = public,
        )
        s.add(dbrow)
        s.flush()               # get ID
        db_id = dbrow.id

    # notify user
    await q.edit_message_text("✅ Your doubt has been sent to the instructor!")

    # forward to ADMIN with inline buttons
    answer_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Answered ✅", callback_data=f"ans|{db_id}|{int(public)}"),
        InlineKeyboardButton("Private ↩️",  callback_data=f"ans|{db_id}|0"),
    ]])
    header = (f"*New doubt #{db_id}*  from [{q.from_user.first_name}](tg://user?id={q.from_user.id})\n"
              f"*Subject*: {ctx.user_data['subject']}\n"
              f"*Nature* : {ctx.user_data['nature']}")
    if ctx.user_data["media_id"]:
        await q.bot.send_photo(
            ADMIN_ID, ctx.user_data["media_id"], caption=header,
            parse_mode="Markdown", reply_markup=answer_kb
        )
    else:
        await q.bot.send_message(
            ADMIN_ID, f"{header}\n\n{ctx.user_data['question']}",
            parse_mode="Markdown", reply_markup=answer_kb
        )

    return ConversationHandler.END

# ------------------------------------------------------------------
async def admin_answer_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin pressed 'Answered' / 'Private' – next message he sends becomes the answer."""
    q = update.callback_query; await q.answer()
    db_id, want_public = q.data.split("|")[1:]
    ctx.user_data["ans_for"] = int(db_id)
    ctx.user_data["ans_public"] = bool(int(want_public))
    await q.edit_message_text("Send your answer *now* (text or one photo).",
                              parse_mode="Markdown")
    return

async def admin_answer_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "ans_for" not in ctx.user_data:
        return
    db_id  = ctx.user_data.pop("ans_for")
    public = ctx.user_data.pop("ans_public")

    with session_scope() as s:
        dbrow: Doubt = s.query(Doubt).get(db_id)
        if not dbrow:
            return
        dbrow.answered   = True
        dbrow.answer_ts  = dt.datetime.utcnow()
        dbrow.answer_text = "[photo]" if update.message.photo else (update.message.text or "")
        s.add(dbrow)
        tgt_user = dbrow.user_id

    # deliver answer
    if update.message.photo:
        mid = update.message.photo[-1].file_id
        if public:
            sent = await update.message.copy(ADMIN_ID)   # ensure bot has photo
            await ctx.bot.copy_message(
                tgt_user, ADMIN_ID, sent.message_id,
                caption=update.message.caption or "",
                parse_mode=ParseMode.MARKDOWN
            )
            await ctx.bot.send_message(tgt_user, "📝 Your doubt was answered (see above).")
        else:
            await ctx.bot.copy_message(
                tgt_user, ADMIN_ID, update.message.message_id,
                caption=update.message.caption or "",
                parse_mode=ParseMode.MARKDOWN
            )
            await ctx.bot.send_message(tgt_user, "📝 Your doubt was answered privately.")
    else:
        txt = update.message.text or ""
        if public:
            await ctx.bot.send_message(tgt_user, f"📝 Answer:\n{txt}")
        else:
            await ctx.bot.send_message(tgt_user, f"📝 Private answer:\n{txt}")

# =================================================================
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            SUBJECT:         [CallbackQueryHandler(subject_chosen, pattern=r"^s\|")],
            SUBJECT_CUSTOM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subject)],
            NATURE:          [CallbackQueryHandler(nature_chosen,  pattern=r"^n\|")],
            NATURE_CUSTOM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nature)],
            QUESTION:        [MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND),
                                             received_question)],
            PUBLICITY:       [CallbackQueryHandler(publicity_chosen, pattern=r"^pub\|")],
        },
        fallbacks=[],
        per_chat=True,
    )
    app.add_handler(conv)

    # Admin answer flow
    app.add_handler(CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$",
                                         block=False, chat_id=ADMIN_ID))
    app.add_handler(MessageHandler(filters.ALL & filters.User(ADMIN_ID), admin_answer_msg))
