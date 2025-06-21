# doubts.py
"""
Doubt-asking system
• /doubt – student wizard (subject → nature → text|photo)
• Admin inline buttons to answer public/private
"""

from __future__ import annotations
import enum, asyncio, datetime as dt, mimetypes, pathlib

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    InputFile,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from database import session_scope, Doubt, DoubtQuota

# ─────────────────────────────────────────────
# 1. Enums  (inherit from *str* AND Enum)
class Subject(str, enum.Enum):
    ENG_RC   = ("ENG_RC",   "English & RC")
    LEGAL    = ("LEGAL",    "Legal Reasoning")
    LOGIC    = ("LOGIC",    "Logical Reasoning")
    MATHS    = ("MATHS",    "Mathematics")
    GK_CA    = ("GK_CA",    "GK / CA")
    MOCK     = ("MOCK",     "Mock Test")
    SEC_TEST = ("SEC_TEST", "Sectional Test")
    STRAT    = ("STRAT",    "Strategy / Time-Mgmt")
    APPLY    = ("APPLY",    "Application / College")
    CUSTOM   = ("CUSTOM",   "Other / Custom")

    def __new__(cls, value: str, label: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label   = label
        return obj


class Nature(str, enum.Enum):
    CANT_SOLVE   = ("CANT_SOLVE",   "Can’t solve a question")
    DONT_GET_ANS = ("DONT_GET_ANS", "Don’t understand official answer")
    EXPLAIN_WRNG = ("EXPLAIN_WRNG", "Explain my wrong answer")
    CONCEPT      = ("CONCEPT",      "Concept clarification")
    ALT_METHOD   = ("ALT_METHOD",   "Need alternative method")
    SOURCE       = ("SOURCE",       "Source / reference request")
    TIME_MGMT    = ("TIME_MGMT",    "Time-management advice")
    STRATEGY     = ("STRATEGY",     "Test-taking strategy")
    OTHER        = ("OTHER",        "Other / Custom")

    def __new__(cls, value: str, label: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label   = label
        return obj


# ─────────────────────────────────────────────
ASK_SUBJ, ASK_NATURE, ASK_CUSTOM_SUBJ, ASK_CUSTOM_NAT, GET_Q = range(5)

DAILY_PUB  = 2
DAILY_PRIV = 3

# ─────────────────────────────────────────────
async def _check_quota(uid: int, public: bool) -> str | None:
    today = dt.date.today()
    with session_scope() as s:
        quota = (
            s.query(DoubtQuota)
            .filter_by(user_id=uid, date=today)
            .one_or_none()
        )
        if not quota:
            quota = DoubtQuota(
                user_id=uid,
                date=today,
                public_count=0,
                private_count=0,
            )
            s.add(quota)
            s.commit()

        count = quota.public_count if public else quota.private_count
        limit = DAILY_PUB if public else DAILY_PRIV
        if count >= limit:
            return (
                f"🚫 Daily limit reached "
                f"({limit} {'public' if public else 'private'} doubts)."
            )
        # increment
        if public:
            quota.public_count += 1
        else:
            quota.private_count += 1
        s.commit()
    return None


# ─────────────────────────────────────────────
# 1️⃣  /doubt entry
async def cmd_doubt(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    err = await _check_quota(u.effective_user.id, public=False)  # private raise
    if err:
        await u.message.reply_text(err)
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(s.label, callback_data=f"s|{s.name}")]
        for s in Subject if s != Subject.CUSTOM
    ]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="s|CUSTOM")])
    await u.message.reply_text(
        "Choose *subject*:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return ASK_SUBJ


# 2️⃣ subject chosen
async def subj_chosen(q_upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = q_upd.callback_query
    await q.answer()
    _, raw = q.data.split("|", 1)
    if raw == "CUSTOM":
        await q.message.reply_text("Enter custom subject (≤ 30 chars):")
        return ASK_CUSTOM_SUBJ

    ctx.user_data["subject"] = Subject[raw]
    return await _ask_nature(q.message)


async def custom_subj(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["subject"] = u.message.text.strip()[:30]
    return await _ask_nature(u.message)


# helper to show nature keyboard
async def _ask_nature(msg):
    kb = [
        [InlineKeyboardButton(n.label, callback_data=f"n|{n.name}")]
        for n in Nature if n != Nature.OTHER
    ]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="n|OTHER")])
    await msg.reply_text(
        "Choose *nature* of doubt:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return ASK_NATURE


# 3️⃣ nature chosen
async def nature_chosen(q_upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = q_upd.callback_query
    await q.answer()
    _, raw = q.data.split("|", 1)
    if raw == "OTHER":
        await q.message.reply_text("Enter custom nature (≤ 30 chars):")
        return ASK_CUSTOM_NAT

    ctx.user_data["nature"] = Nature[raw]
    return await _ask_question(q.message)


async def custom_nat(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["nature"] = u.message.text.strip()[:30]
    return await _ask_question(u.message)


async def _ask_question(msg):
    await msg.reply_text("Send your *question* (text or single photo).", parse_mode="Markdown")
    return GET_Q


# 4️⃣ receive question
async def save_question(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = u.effective_user
    cid  = u.effective_chat.id

    content: str | None = None
    file_id: str | None = None
    mime: str | None    = None

    if u.message.photo:
        ph = u.message.photo[-1]
        file_id = ph.file_id
        mime = "image/jpeg"
    elif u.message.document:
        doc = u.message.document
        file_id = doc.file_id
        mime, _ = mimetypes.guess_type(doc.file_name or "")  # may be None
    elif u.message.text:
        content = u.message.text_html
    else:
        await u.message.reply_text("❌ Please send text or a photo.")
        return GET_Q

    # DB insert
    with session_scope() as s:
        d = Doubt(
            user_id=user.id,
            user_name=user.full_name,
            subject=str(ctx.user_data["subject"]),
            nature=str(ctx.user_data["nature"]),
            content=content,
            file_id=file_id,
            file_mime=mime,
            ts=dt.datetime.utcnow(),
        )
        s.add(d); s.flush()   # get id

        doubt_id = d.id

    await u.message.reply_text("✅ Doubt recorded! You’ll get a reply soon.")

    # notify admin
    admin_text = (
        f"❓ <b>New doubt #{doubt_id}</b>\n"
        f"<b>User:</b> {user.full_name} ({user.id})\n"
        f"<b>Subject:</b> {ctx.user_data['subject']}\n"
        f"<b>Nature:</b>  {ctx.user_data['nature']}"
    )
    kb = InlineKeyboardMarkup.from_row([
        InlineKeyboardButton("Answer 🔒 Private", callback_data=f"ans|{doubt_id}|0"),
        InlineKeyboardButton("Answer 📢 Public", callback_data=f"ans|{doubt_id}|1"),
    ])
    await u.get_bot().send_message(cid=ADMIN_ID, text=admin_text,
                                   parse_mode="HTML", reply_markup=kb)

    return ConversationHandler.END


# ─────────────────────────────────────────────
# Admin answer callback
async def admin_answer_cb(q_upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = q_upd.callback_query
    await q.answer()
    _, did, pub = q.data.split("|")
    did  = int(did)
    pub  = bool(int(pub))

    await q.message.reply_text("Send your answer (text / photo / doc).")

    ctx.user_data["doubt_id"] = did
    ctx.user_data["public"]   = pub

    return GET_Q  # reuse same state


async def admin_answer(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did   = ctx.user_data["doubt_id"]
    pub   = ctx.user_data["public"]

    content: str | None = None
    file_id: str | None = None
    mime: str | None    = None

    if u.message.photo:
        ph = u.message.photo[-1]
        file_id = ph.file_id
        mime = "image/jpeg"
    elif u.message.document:
        doc = u.message.document
        file_id = doc.file_id
        mime, _ = mimetypes.guess_type(doc.file_name or "")
    elif u.message.text:
        content = u.message.text_html
    else:
        await u.message.reply_text("❌ Please send text or a photo.")
        return GET_Q

    with session_scope() as s:
        d = s.get(Doubt, did)
        if not d:
            await u.message.reply_text("Doubt not found.")
            return ConversationHandler.END
        d.answer_content = content
        d.answer_file_id = file_id
        d.answer_file_mime = mime
        d.answered_at = dt.datetime.utcnow()
        d.answered_public = pub
        s.commit()

        # send to student
        try:
            if content:
                await u.get_bot().send_message(d.user_id, content, parse_mode="HTML")
            if file_id:
                await u.get_bot().send_document(d.user_id, file_id) if mime else \
                     await u.get_bot().send_photo(d.user_id, file_id)
        except Exception:
            pass  # ignore blocked bot

        # if public, post to originating chat
        if pub:
            txt = f"❓ <b>Doubt #{did}</b>\n" \
                  f"<b>Q:</b> {d.content or '📎'}\n\n" \
                  f"💬 <b>Answer</b>:\n" \
                  f"{content or '📎'}"
            await u.get_bot().send_message(chat_id=d.user_id, text=txt, parse_mode="HTML")

    await u.message.reply_text("✅ Answer saved & sent.")
    return ConversationHandler.END


# ─────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ: [CallbackQueryHandler(subj_chosen, pattern=r"^s\|")],
            ASK_CUSTOM_SUBJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom субj)],
            ASK_NATURE: [CallbackQueryHandler(nature_chosen, pattern=r"^n\|")],
            ASK_CUSTOM_NAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nat)],
            GET_Q: [MessageHandler(filters.ALL & ~filters.COMMAND, save_question)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_user=True,
    )
    app.add_handler(conv)

    # admin answer flow
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$")],
        states={
            GET_Q: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_answer)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_user=True,
    )
    app.add_handler(admin_conv)
