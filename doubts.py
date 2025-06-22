# doubts.py  – ask/answer workflow with daily public & private quotas
import enum, datetime as dt, asyncio
from typing import Final

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    Update, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

from database import session_scope, Doubt, DoubtQuota

# ────────────────────────────────────────────────────────────
# Enums with human-readable labels
class Subject(enum.Enum):
    ENGLISH =        ("English & RC",)
    LEGAL   =        ("Legal Reasoning",)
    LOGICAL =        ("Logical Reasoning",)
    MATHS   =        ("Maths",)
    GKCA    =        ("GK / CA",)
    MOCK    =        ("Mock Test",)
    SECTION =        ("Sectional Test",)
    STRAT   =        ("Strategy / Time-Mgmt",)
    APPL    =        ("Application / College",)
    OTHER   =        ("Other / Custom",)

    def __init__(self, label: str):
        self.label: str = label


class Nature(enum.Enum):
    CANT_SOLVE   = ("Can’t solve a question",)
    DONT_UNDERST = ("Don’t understand answer",)
    WRONG_ANS    = ("Explain my wrong answer",)
    CONCEPT      = ("Concept clarification",)
    ALT_METHOD   = ("Need alternative method",)
    SOURCE_REQ   = ("Source / reference request",)
    TIME_MGMT    = ("Time-management advice",)
    STRATEGY     = ("Test-taking strategy",)
    OTHER        = ("Other / Custom",)

    def __init__(self, label: str):
        self.label: str = label


# ────────────────────────────────────────────────────────────
# Conversation states
ASK_SUBJ, ASK_SUBJ_CUSTOM, ASK_NATURE, ASK_NATURE_CUSTOM, ASK_TEXT, ASK_MEDIA = range(6)

# Daily quota limits
MAX_PRIV: Final[int] = 3
MAX_PUB:  Final[int] = 2

def _today() -> dt.date:
    return dt.date.today()


# ────────────────────────────────────────────────────────────
async def _check_quota(uid: int, *, public: bool) -> str | None:
    """Return error-msg string if quota exceeded, else None."""
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, _today()))
        if q is None:
            q = DoubtQuota(
                user_id=uid,
                date=_today(),
                public_count=0,
                private_count=0,
            )
            s.add(q)

        if public and q.public_count >= MAX_PUB:
            return f"Daily public-doubt limit ({MAX_PUB}) reached."
        if not public and q.private_count >= MAX_PRIV:
            return f"Daily private-doubt limit ({MAX_PRIV}) reached."

        # reserve a slot
        if public:
            q.public_count += 1
        else:
            q.private_count += 1
    return None


# ────────────────────────────────────────────────────────────
# Step-1 command
async def cmd_doubt(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    err = await _check_quota(upd.effective_user.id, public=False)  # only counts if completed
    if err:
        return await upd.message.reply_text(err) or ConversationHandler.END

    ctx.user_data.clear()        # fresh run
    kb = [
        [InlineKeyboardButton(sub.label, callback_data=f"s|{sub.name}")]
        for sub in Subject if sub != Subject.OTHER
    ]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="s|OTHER")])
    await upd.message.reply_text(
        "📚 *Choose the doubt’s subject:*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ASK_SUBJ


async def subj_chosen(q: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = q.callback_query; await q.answer()
    _, key = q.data.split("|", 1)
    if key == "OTHER":
        await q.edit_message_text("Enter custom subject (≤ 30 chars):")
        return ASK_SUBJ_CUSTOM
    ctx.user_data["subject"] = Subject[key]
    return await _ask_nature(q, ctx)


async def subj_custom(msg: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["subject"] = msg.message.text[:30]
    return await _ask_nature(msg, ctx)


async def _ask_nature(src, ctx):
    kb = [
        [InlineKeyboardButton(n.label, callback_data=f"n|{n.name}")]
        for n in Nature if n != Nature.OTHER
    ]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="n|OTHER")])
    txt = "📎 *Nature of doubt?*"
    if isinstance(src, Update) and src.message:
        await src.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb),
                                     parse_mode="Markdown")
    else:
        await src.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb),
                                    parse_mode="Markdown")
    return ASK_NATURE


async def nature_chosen(q: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = q.callback_query; await q.answer()
    _, key = q.data.split("|", 1)
    if key == "OTHER":
        await q.edit_message_text("Enter custom nature (≤ 40 chars):")
        return ASK_NATURE_CUSTOM
    ctx.user_data["nature"] = Nature[key]
    await q.edit_message_text("✏️ Send your question text (or `skip`):", parse_mode="Markdown")
    return ASK_TEXT


async def nature_custom(msg: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["nature"] = msg.message.text[:40]
    await msg.message.reply_text("✏️ Send your question text (or `skip`):")
    return ASK_TEXT


async def ask_text(msg: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if msg.message.text.lower() != "skip":
        ctx.user_data["text"] = msg.message.text[:400]
    await msg.message.reply_text("📷 Optionally send ONE photo (or `skip`).")
    return ASK_MEDIA


async def ask_media(msg: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if msg.message.photo:
        ctx.user_data["photo"] = msg.message.photo[-1].file_id
    # -------- persist ----------
    data = ctx.user_data
    with session_scope() as s:
        doubt = Doubt(
            user_id=msg.effective_user.id,
            subject=str(data["subject"]),
            nature=str(data["nature"]),
            text=data.get("text"),
            photo=data.get("photo"),
        )
        s.add(doubt)
    await msg.message.reply_text("✅ Your doubt has been queued. You’ll receive an answer soon.")
    return ConversationHandler.END


async def cancel(upd: Update, _):  # fallback
    await upd.message.reply_text("❌ Doubt cancelled.")
    return ConversationHandler.END


# ────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:          [CallbackQueryHandler(subj_chosen, pattern=r"^s\|")],
            ASK_SUBJ_CUSTOM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, subj_custom)],
            ASK_NATURE:        [CallbackQueryHandler(nature_chosen, pattern=r"^n\|")],
            ASK_NATURE_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, nature_custom)],
            ASK_TEXT:          [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_text)],
            ASK_MEDIA: [
                MessageHandler(filters.PHOTO, ask_media),
                MessageHandler(filters.Regex(r"^(skip|SKIP)$"), ask_media),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="doubt_wizard",
        persistent=False,
    )
    app.add_handler(conv)
