# doubts.py
"""
Full ‘Ask-a-Doubt’ module – quota check, subject & nature menus,
media capture, admin answer flow.
"""

# doubts.py   (top-of-file imports ONLY)

import enum, datetime as dt
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaDocument
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

from database import session_scope                     # session helper
from models   import Doubt, DoubtQuota                  # ← import models directly
...
# (rest of your latest doubts.py remains exactly as you pasted)

# ───────────── SQLAlchemy models & helpers ─────────────
from database import session_scope
from models    import Doubt, DoubtQuota                       # <- models import, NOT database

# ───────────── enums for menu building ─────────────
class Subject(enum.Enum):
    ENG        = "English & RC"
    LEGAL      = "Legal Reasoning"
    LOGICAL    = "Logical Reasoning"
    MATHS      = "Maths"
    GK         = "GK / CA"
    MOCK       = "Mock Test"
    SECTIONAL  = "Sectional Test"
    STRAT      = "Strategy / Time-Mgmt"
    COLLEGE    = "Application / College"
    OTHER      = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE         = "Can’t solve a question"
    DONT_UNDERSTAND    = "Don’t understand official answer"
    EXPLAIN_WRONG      = "Explain my wrong answer"
    CONCEPT            = "Concept clarification"
    ALT_METHOD         = "Need alternative method"
    SOURCE_REQUEST     = "Source / reference request"
    TIME_MGMT          = "Time-management advice"
    TEST_STRAT         = "Test-taking strategy"
    OTHER              = "Other / Custom"

# ───────────── Conversation states ─────────────
ASK_SUBJ, ASK_CUSTOM_SUBJ, ASK_NATURE, ASK_CUSTOM_NATURE, \
ASK_TEXT, ASK_PHOTO = range(6)

# ───────────── quota limits ─────────────
MAX_PUB   : Final = 2     # /day
MAX_PRIV  : Final = 3     # /day

# ───────────── internal helpers ─────────────
async def _check_quota(uid: int, *, public: bool) -> str | None:
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, {"user_id": uid, "date": today})
        if not q:
            q = DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            s.add(q)

        used = q.public_count if public else q.private_count
        limit = MAX_PUB      if public else MAX_PRIV
        if used >= limit:
            return f"❌ You reached today’s {limit}-{ 'public' if public else 'private'} doubt quota."

        # increment but _don’t_ commit yet – will commit on session exit
        if public:
            q.public_count  += 1
        else:
            q.private_count += 1
    return None

def _kb_from_enum(enum_cls):
    rows = []
    cur  = []
    for i, m in enumerate(enum_cls):
        cur.append(InlineKeyboardButton(m.value, callback_data=m.name))
        if len(cur) == 2:
            rows.append(cur); cur=[]
    if cur: rows.append(cur)
    return InlineKeyboardMarkup(rows)

# ───────────── conversation callbacks ─────────────
async def cmd_doubt(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(u.effective_user.id, public=False)   # private quota check first
    if err: return await u.message.reply_text(err)

    await u.message.reply_text("Choose *subject*:", parse_mode="Markdown",
                               reply_markup=_kb_from_enum(Subject))
    return ASK_SUBJ

async def subj_chosen(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q  = u.callback_query; await q.answer()
    key = q.data
    if key == Subject.OTHER.name:
        await q.edit_message_text("Enter custom subject (≤ 30 chars):")
        return ASK_CUSTOM_SUBJ
    ctx.user_data["subject"] = Subject[key].value
    await q.edit_message_text("Nature of doubt:",
                              reply_markup=_kb_from_enum(Nature))
    return ASK_NATURE

async def custom_subject(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"] = u.message.text[:30]
    await u.message.reply_text("Nature of doubt:",
                               reply_markup=_kb_from_enum(Nature))
    return ASK_NATURE

async def nature_chosen(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q= u.callback_query; await q.answer()
    key=q.data
    if key == Nature.OTHER.name:
        await q.edit_message_text("Enter custom nature (≤ 30 chars):")
        return ASK_CUSTOM_NATURE
    ctx.user_data["nature"] = Nature[key].value
    await q.edit_message_text("Send your question as text (or attach ONE photo).")
    return ASK_TEXT

async def custom_nature(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"] = u.message.text[:30]
    await u.message.reply_text("Send your question as text (or attach ONE photo).")
    return ASK_TEXT

async def text_received(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["text"] = u.message.text
    await u.message.reply_text("Now send ONE photo *or* /skip.", parse_mode="Markdown")
    return ASK_PHOTO

async def photo_received(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["photo_file_id"] = u.message.photo[-1].file_id
    return await _store_and_notify(u, ctx)

async def skip_photo(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _store_and_notify(u, ctx)

async def _store_and_notify(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = ctx.user_data
    with session_scope() as s:
        doubt = Doubt(
            user_id = u.effective_user.id,
            subject = data["subject"],
            nature  = data["nature"],
            text    = data.get("text"),
            photo_file_id = data.get("photo_file_id"),
            is_public     = False
        )
        s.add(doubt)
        s.flush()          # so we get the id

        # inform student
        await u.message.reply_text("✅ Doubt submitted! You’ll receive an answer soon.")

        # DM admin
        admin_msg = textwrap.dedent(f"""
            📥 *New doubt #{doubt.id}*  
            👤 `{u.effective_user.id}` – {u.effective_user.full_name}
            🗂 *{doubt.subject}*  |  _{doubt.nature}_
            💬 {doubt.text or '_<photo only>_'}
        """)
        if doubt.photo_file_id:
            await ctx.bot.send_photo(
                chat_id=ctx.bot_data["ADMIN_ID"],
                photo=doubt.photo_file_id,
                caption=admin_msg,
                parse_mode="Markdown",
                reply_markup=_answer_kb(doubt.id)
            )
        else:
            await ctx.bot.send_message(
                chat_id=ctx.bot_data["ADMIN_ID"],
                text=admin_msg,
                parse_mode="Markdown",
                reply_markup=_answer_kb(doubt.id)
            )
    return ConversationHandler.END

def _answer_kb(did: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Reply Privately 🗝", callback_data=f"ans|{did}|0"),
         InlineKeyboardButton("Reply Publicly 📣",  callback_data=f"ans|{did}|1")]
    ])

# ───────────── admin answer flow ─────────────
async def admin_answer_cb(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=u.callback_query; await q.answer()
    did, pub = map(int, q.data.split("|")[1:])
    ctx.user_data["did"] = did
    ctx.user_data["is_public"] = bool(pub)
    await q.edit_message_text("Send answer (text or photo).")
    return ASK_TEXT

async def admin_answer_media(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did      : int  = ctx.user_data["did"]
    is_pub   : bool = ctx.user_data["is_public"]
    text = u.message.caption or u.message.text
    photo_id = u.message.photo[-1].file_id if u.message.photo else None

    with session_scope() as s:
        d: Doubt = s.get(Doubt, did)
        if not d: return await u.message.reply_text("⛔ Doubt not found.")
        d.answer_text  = text
        d.answer_photo = photo_id
        d.answered_at  = dt.datetime.utcnow()
        d.is_public    = is_pub

    # send to student
    dest = d.user_id if not is_pub else ctx.bot_data["GROUP_ID"]
    if d.answer_photo:
        await ctx.bot.send_photo(dest, d.answer_photo, caption=text)
    else:
        await ctx.bot.send_message(dest, text)

    await u.message.reply_text("✅ Sent.")
    return ConversationHandler.END

# ───────────── registration ─────────────
def register_handlers(app: Application):
    # store admin/group ids for callbacks
    app.bot_data["ADMIN_ID"] = int(os.getenv("ADMIN_ID", "803299591"))
    app.bot_data["GROUP_ID"] = int(os.getenv("GROUP_ID", "0"))       # 0 ⇒ skip posting

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:          [CallbackQueryHandler(subj_chosen)],
            ASK_CUSTOM_SUBJ:   [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subject)],
            ASK_NATURE:        [CallbackQueryHandler(nature_chosen)],
            ASK_CUSTOM_NATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nature)],
            ASK_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_received),
                MessageHandler(filters.PHOTO, photo_received)
            ],
            ASK_PHOTO: [
                MessageHandler(filters.PHOTO, photo_received),
                CommandHandler("skip", skip_photo)
            ],
        },
        fallbacks=[CommandHandler("cancel", skip_photo)],
        per_chat=True,
    )
    app.add_handler(conv)

    # admin answer conversation
    ans_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$")],
        states={
            ASK_TEXT: [MessageHandler(filters.TEXT | filters.PHOTO, admin_answer_media)],
        },
        fallbacks=[CommandHandler("cancel", skip_photo)],
        per_chat=False,
    )
    app.add_handler(ans_conv)
