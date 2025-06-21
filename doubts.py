# doubts.py
"""
Doubt-asking system
• /doubt  – student wizard  (subject → nature → text/photo)
• admin inline buttons let you answer private / public
"""

from __future__ import annotations
import enum, asyncio, datetime as dt, mimetypes

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
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


# conversation states
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
            return f"🚫 Daily limit reached ({limit} {'public' if public else 'private'} doubts)."

        # increment now
        if public:
            quota.public_count += 1
        else:
            quota.private_count += 1
        s.commit()
    return None


# ─────────────────────────────────────────────
async def cmd_doubt(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    err = await _check_quota(u.effective_user.id, public=False)
    if err:
        await u.message.reply_text(err)
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(s.label, callback_data=f"s|{s.name}")]
          for s in Subject if s != Subject.CUSTOM]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="s|CUSTOM")])
    await u.message.reply_text("Choose *subject*:",
                               reply_markup=InlineKeyboardMarkup(kb),
                               parse_mode="Markdown")
    return ASK_SUBJ


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


async def _ask_nature(msg):
    kb = [[InlineKeyboardButton(n.label, callback_data=f"n|{n.name}")]
          for n in Nature if n != Nature.OTHER]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="n|OTHER")])
    await msg.reply_text("Choose *nature* of doubt:",
                         reply_markup=InlineKeyboardMarkup(kb),
                         parse_mode="Markdown")
    return ASK_NATURE


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
    await msg.reply_text("Send your *question* (text or single photo).",
                         parse_mode="Markdown")
    return GET_Q


async def save_question(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # ... (unchanged – keep your existing implementation) ...
    pass   # <-- keep rest of your function here


# Admin-side answer callbacks – also unchanged from previous version …
# (make sure you keep admin_answer_cb, admin_answer, etc.)

# ─────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:        [CallbackQueryHandler(subj_chosen, pattern=r"^s\|")],
            ASK_CUSTOM_SUBJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subj)],
            ASK_NATURE:      [CallbackQueryHandler(nature_chosen, pattern=r"^n\|")],
            ASK_CUSTOM_NAT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nat)],
            GET_Q:           [MessageHandler(filters.ALL & ~filters.COMMAND, save_question)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_user=True,
    )
    app.add_handler(conv)

    # admin flow (keep your existing admin_conv if already present)
