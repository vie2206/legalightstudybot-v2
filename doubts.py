# doubts.py  – full module
import enum, asyncio, textwrap, datetime as dt
from typing import Dict, Literal

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery,
    Message, Chat
)
from telegram.ext import (
    Application, ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)

from database import session_scope, Doubt, DoubtQuota

# ───────────────────────── enums ─────────────────────────
class Subject(enum.Enum):
    ENGLISH       = "English & RC"
    LEGAL         = "Legal Reasoning"
    LOGICAL       = "Logical Reasoning"
    MATHS         = "Maths"
    GK            = "GK / CA"
    MOCK          = "Mock Test"
    SECTIONAL     = "Sectional Test"
    STRATEGY      = "Strategy / Time-Mgmt"
    APPLICATION   = "Application / College"
    OTHER         = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE    = "Can’t solve"
    DONT_GET_ANS  = "Don’t get answer"
    EXPLAIN_WRONG = "Explain wrong answer"
    CONCEPT       = "Concept clarification"
    ALT_METHOD    = "Need alt. method"
    SOURCE_REQ    = "Source / ref. request"
    TIME_MGMT     = "Time-mgmt advice"
    STRATEGY      = "Test-taking strategy"
    OTHER         = "Other / Custom"

# ────────────────────────── states ───────────────────────
(
    ASK_SUBJ, ASK_SUBJ_CUSTOM,
    ASK_NATURE, ASK_NATURE_CUSTOM,
    ASK_PHOTO_OR_TEXT, ASK_TEXT, ASK_PHOTO,
    CONFIRM_PUBLIC,
) = range(8)

# ────────────────────────── quota helpers ────────────────
DAILY_PUB = 2
DAILY_PRI = 3

async def _check_quota(uid: int, public: bool) -> str|None:
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, today))
        if not q:
            q = DoubtQuota(user_id=uid, date=today,
                           public_count=0, private_count=0)
            s.add(q)
            s.commit()
        if public  and q.public_count >= DAILY_PUB:
            return "You reached today’s *public*-answer quota."
        if not public and q.private_count >= DAILY_PRI:
            return "You reached today’s *private*-answer quota."
        # reserve one slot
        if public:   q.public_count  += 1
        else:        q.private_count += 1
        s.commit()
    return None

# ────────────────────────── handlers ─────────────────────
async def cmd_doubt(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(upd.effective_user.id, public=False)  # private by default
    if err:
        return await upd.message.reply_markdown(f"❌ {err}")
    ctx.user_data.clear()
    kb = [[InlineKeyboardButton(v.value, callback_data=f"s|{k.name}")]
          for k,v in Subject.__members__.items()]
    await upd.message.reply_text("Pick *subject*:", parse_mode="Markdown",
                                 reply_markup=InlineKeyboardMarkup(kb))
    return ASK_SUBJ

async def subj_chosen(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = upd.callback_query; await q.answer()
    _, key = q.data.split("|",1)
    if key=="OTHER":
        await q.edit_message_text("Type custom subject (≤30 chars):")
        return ASK_SUBJ_CUSTOM
    ctx.user_data["subject"]=Subject[key].value
    return await _ask_nature(q)

async def subj_custom(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"]=upd.message.text[:30]
    return await _ask_nature(upd.message)

async def _ask_nature(msg_or_q: Message|CallbackQuery):
    kb = [[InlineKeyboardButton(v.value,callback_data=f"n|{k.name}")]
          for k,v in Nature.__members__.items()]
    if isinstance(msg_or_q, CallbackQuery):
        await msg_or_q.edit_message_text("Pick *nature*:",parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(kb))
    else:
        await msg_or_q.reply_text("Pick *nature*:",parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(kb))
    return ASK_NATURE

async def nature_chosen(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = upd.callback_query; await q.answer()
    _, key=q.data.split("|",1)
    if key=="OTHER":
        await q.edit_message_text("Type custom nature (≤30 chars):")
        return ASK_NATURE_CUSTOM
    ctx.user_data["nature"]=Nature[key].value
    return await _ask_qtype(q)

async def nature_custom(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"]=upd.message.text[:30]
    return await _ask_qtype(upd.message)

async def _ask_qtype(msg_or_q):
    kb=[
        [InlineKeyboardButton("📝 Text",  callback_data="q|text"),
         InlineKeyboardButton("📷 Photo", callback_data="q|photo")]
    ]
    if isinstance(msg_or_q, CallbackQuery):
        await msg_or_q.edit_message_text("Send your doubt as *text* or *photo*?",
                                         parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(kb))
    else:
        await msg_or_q.reply_text("Send your doubt as *text* or *photo*?",
                                  parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(kb))
    return ASK_PHOTO_OR_TEXT

async def choose_qtype(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q:CallbackQuery=upd.callback_query; await q.answer()
    _,mode=q.data.split("|",1)
    if mode=="text":
        await q.edit_message_text("📨 Send the question text:")
        return ASK_TEXT
    else:
        await q.edit_message_text("📷 Send the photo (one image):")
        return ASK_PHOTO

async def receive_text(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["q_type"]="text"
    ctx.user_data["q_text"]=upd.message.text.strip()[:2000]
    return await _ask_public(upd.message, ctx)

async def receive_photo(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photo=upd.message.photo[-1]
    ctx.user_data["q_type"]="photo"
    ctx.user_data["q_photo"]=photo.file_id
    return await _ask_public(upd.message, ctx)

async def _ask_public(msg, ctx):
    err=await _check_quota(msg.from_user.id, public=True)
    kb=[
        [InlineKeyboardButton("👥 Public (group)",callback_data="pub|1" if not err else "X")],
        [InlineKeyboardButton("🔒 Private (DM)",   callback_data="pub|0")]
    ]
    if err: kb[0][0].text+=" – quota full"
    await msg.reply_text("Where should I answer?",reply_markup=InlineKeyboardMarkup(kb))
    return CONFIRM_PUBLIC

async def confirm(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q:CallbackQuery=upd.callback_query;await q.answer()
    allow=q.data.endswith("|1")
    ctx.user_data["public"]=allow
    # persist
    with session_scope() as s:
        d=Doubt(
            user_id=q.from_user.id,
            subject=ctx.user_data["subject"],
            nature=ctx.user_data["nature"],
            q_type=ctx.user_data["q_type"],
            q_text=ctx.user_data.get("q_text"),
            q_photo=ctx.user_data.get("q_photo"),
            public_answer=allow
        )
        s.add(d); s.commit()
        did=d.id
    await q.edit_message_text("✅ Your doubt has been recorded. You’ll receive an answer soon.")
    # notify admin
    txt=textwrap.dedent(f"""\
        #Doubt {did}
        👤 User: [{q.from_user.first_name}](tg://user?id={q.from_user.id})
        🏷 *{ctx.user_data['subject']}* – {ctx.user_data['nature']}
        """)
    if ctx.user_data["q_type"]=="text":
        txt+="\n"+ctx.user_data["q_text"]
        await ctx.bot.send_message(ctx.bot_data["admin_id"],txt,parse_mode="Markdown")
    else:
        await ctx.bot.send_photo(ctx.bot_data["admin_id"],
                                ctx.user_data["q_photo"],
                                caption=txt,parse_mode="Markdown")
    return ConversationHandler.END

# ───────────────────────── registration ──────────────────
def register_handlers(app: Application, admin_id: int):
    app.bot_data["admin_id"]=admin_id
    conv=ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:          [CallbackQueryHandler(subj_chosen, pattern=r"^s\|")],
            ASK_SUBJ_CUSTOM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, subj_custom)],
            ASK_NATURE:        [CallbackQueryHandler(nature_chosen, pattern=r"^n\|")],
            ASK_NATURE_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, nature_custom)],
            ASK_PHOTO_OR_TEXT: [CallbackQueryHandler(choose_qtype, pattern=r"^q\|")],
            ASK_TEXT:          [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
            ASK_PHOTO:         [MessageHandler(filters.PHOTO, receive_photo)],
            CONFIRM_PUBLIC:    [CallbackQueryHandler(confirm,pattern=r"^pub\|[01]$")],
        },
        fallbacks=[],
        per_user=True,
    )
    app.add_handler(conv)
