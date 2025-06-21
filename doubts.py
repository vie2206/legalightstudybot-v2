# doubts.py
"""
Ask-a-doubt module.

Flow
====
/doubt                 → choose Subject → choose Nature → user sends text/photo
Bot stores row in DB   → forwards to ADMIN_ID with inline buttons
Admin taps ✅/❌        → bot posts public answer or private DM
Quotas:
  • 2 public + 3 private per user per UTC day
"""

import enum, asyncio, datetime as dt, logging
from typing import Optional

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, constants, Message
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)

from database import session_scope, Doubt, DoubtQuota   # our helpers

# ─────────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ≤────────────────  Enums  ────────────────≥
try:
    _Base = enum.StrEnum          # Py 3.11+
except AttributeError:
    class _Base(str, enum.Enum):  # fallback for 3.10
        pass

class Subject(_Base):
    ENGLISH = "English & RC"
    LEGAL   = "Legal Reasoning"
    LOGICAL = "Logical Reasoning"
    MATHS   = "Maths"
    GKCA    = "GK / CA"
    MOCK    = "Mock Test"
    SECTION = "Sectional Test"
    STRAT   = "Strategy / Time-Mgmt"
    APP     = "Application / College"
    OTHER   = "Other / Custom"

class Nature(_Base):
    CANT_SOLVE   = "Can’t solve"
    DONT_UNDERST = "Don’t understand answer"
    WRONG_EXP    = "Explain my wrong answer"
    CONCEPT      = "Concept clarification"
    ALT_METHOD   = "Need alternative method"
    SOURCE_REQ   = "Source / reference"
    TIME_MGMT    = "Time-mgmt advice"
    STRATEGY     = "Test strategy"
    OTHER        = "Other / Custom"

# ─────────────────────────────────────────────────────────────
(
    ASK_SUBJ, ASK_NATURE,
    ASK_CUSTOM_SUBJ, ASK_CUSTOM_NATURE,
    WAIT_CONTENT
) = range(5)

PUBLIC_DAILY  = 2
PRIVATE_DAILY = 3

ADMIN_ID = int(os.getenv("ADMIN_ID", "803299591"))

# ─────────────────────────────────────────────────────────────
def _today() -> dt.date:
    return dt.datetime.utcnow().date()

def _check_quota(uid: int, wants_public: bool) -> Optional[str]:
    with session_scope() as s:
        q = s.get(DoubtQuota, uid)
        if not q:
            q = DoubtQuota(user_id=uid, last_reset=_today(),
                           public_count=0, private_count=0)
            s.add(q)

        # daily reset
        if q.last_reset < _today():
            q.public_count = q.private_count = 0
            q.last_reset   = _today()

        # check limits
        if wants_public and q.public_count >= PUBLIC_DAILY:
            return "⚠️ You reached today’s *public* doubt limit."
        if (not wants_public) and q.private_count >= PRIVATE_DAILY:
            return "⚠️ You reached today’s *private* doubt limit."

        # pre-reserve the slot so users can’t double-spam
        if wants_public:
            q.public_count += 1
        else:
            q.private_count += 1
    return None

# ─────────────────────────────────────────────────────────────
async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # first, choose PUBLIC / PRIVATE
    kb = [
        [InlineKeyboardButton("🌐 Public (2/day)",  callback_data="mode|pub")],
        [InlineKeyboardButton("🔒 Private (3/day)", callback_data="mode|priv")],
    ]
    await update.message.reply_text("Ask publicly or privately?",
                                    reply_markup=InlineKeyboardMarkup(kb))
    return ASK_SUBJ

async def mode_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["public"] = (q.data == "mode|pub")

    # quota check
    err = _check_quota(update.effective_user.id, ctx.user_data["public"])
    if err:
        await q.edit_message_text(err, parse_mode=constants.ParseMode.MARKDOWN)
        return ConversationHandler.END

    # pick subject
    buttons = [[InlineKeyboardButton(subj.value, callback_data=f"subj|{subj.name}")]
               for subj in list(Subject)[:-1]]    # exclude OTHER
    buttons.append([InlineKeyboardButton("Other / Custom ✍️", callback_data="subj|OTHER")])
    await q.edit_message_text("Select *subject*:", parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup(buttons))
    return ASK_NATURE

async def subj_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    _, key = q.data.split("|",1)
    if key=="OTHER":
        await q.edit_message_text("Type a custom subject (≤30 chars):")
        return ASK_CUSTOM_SUBJ
    ctx.user_data["subject"]=Subject[key].value
    return await _ask_nature(q)

async def save_custom_subj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"]=update.message.text[:30]
    return await _ask_nature(update.message)

async def _ask_nature(msg_or_q):
    buttons=[[InlineKeyboardButton(n.value,callback_data=f"nat|{n.name}")]
             for n in list(Nature)[:-1]]
    buttons.append([InlineKeyboardButton("Other / Custom ✍️",callback_data="nat|OTHER")])
    txt="Select *nature* of doubt:"
    if isinstance(msg_or_q,Message):
        await msg_or_q.reply_text(txt,parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await msg_or_q.edit_message_text(txt,parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(buttons))
    return WAIT_CONTENT if isinstance(msg_or_q,Message) else ASK_NATURE

async def nature_chosen(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;await q.answer()
    _,key=q.data.split("|",1)
    if key=="OTHER":
        await q.edit_message_text("Type a custom nature (≤30 chars):")
        return ASK_CUSTOM_NATURE
    ctx.user_data["nature"]=Nature[key].value
    await q.edit_message_text("Now send your question (text or *one* photo).",
                              parse_mode="Markdown")
    return WAIT_CONTENT

async def save_custom_nature(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"]=update.message.text[:30]
    await update.message.reply_text("Now send your question (text or *one* photo).",
                                    parse_mode="Markdown")
    return WAIT_CONTENT

# ---------- receive doubt content ----------
async def receive_content(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    pub   = ctx.user_data["public"]
    subj  = ctx.user_data["subject"]
    nature= ctx.user_data["nature"]

    # save row
    with session_scope() as s:
        d = Doubt(user_id=uid, subject=subj, nature=nature,
                  text=update.message.text_html or "",
                  photo_file_id=(update.message.photo[-1].file_id
                                 if update.message.photo else None),
                  public=pub)
        s.add(d)
        s.flush()          # get id
        doubt_id = d.id

    # forward to admin
    preview = f"#{doubt_id} | {subj} | {nature}\n"
    if update.message.text:
        preview += update.message.text_html
    elif update.message.caption_html:
        preview += update.message.caption_html

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Answer Public", callback_data=f"ans|{doubt_id}|1"),
         InlineKeyboardButton("❌ Answer Private",callback_data=f"ans|{doubt_id}|0")]
    ])
    if update.message.photo:
        await ctx.bot.send_photo(ADMIN_ID,
                                 photo=update.message.photo[-1].file_id,
                                 caption=preview,
                                 parse_mode="HTML",
                                 reply_markup=kb)
    else:
        await ctx.bot.send_message(ADMIN_ID, preview,
                                   parse_mode="HTML", reply_markup=kb)

    await update.message.reply_text(
        "📝 Your doubt is recorded. "
        "You’ll receive the answer soon!"
    )
    return ConversationHandler.END

# ---------- admin answer ----------
async def admin_answer_cb(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _,did,pub = q.data.split("|"); did=int(did); pub=bool(int(pub))

    await q.edit_message_reply_markup(None)   # remove buttons
    await q.message.reply_text("Send your answer *now* (text, photo, or audio).",
                               parse_mode="Markdown")
    ctx.user_data["ans_for"] = (did, pub)

async def admin_receive_answer(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if "ans_for" not in ctx.user_data: return
    did, pub = ctx.user_data.pop("ans_for")
    with session_scope() as s:
        d = s.get(Doubt, did); d.answered=True
    # fetch original asker
    target_uid = d.user_id

    if pub:
        # post in same chat where doubt was asked? here: send to ADMIN then forward
        msg:Message
        if update.message.photo:
            msg=await update.message.copy(chat_id=ADMIN_ID,caption=None)
        else:
            msg=await update.message.copy(chat_id=ADMIN_ID)
        await ctx.bot.send_message(ADMIN_ID,
            f"📢 *Answer to #{did}* ({d.subject})\n{msg.caption_html or msg.text_html}",
            parse_mode="HTML")
    else:
        await update.message.copy(chat_id=target_uid)
        await ctx.bot.send_message(target_uid,
            f"✅ Your doubt #{did} has been answered privately.")

    await update.message.reply_text("✅ Answer sent.")

# ─────────────────────────────────────────────────────────────
def register_handlers(app:Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ: [CallbackQueryHandler(mode_chosen, pattern=r"^mode\|")],
            ASK_NATURE: [CallbackQueryHandler(subj_chosen, pattern=r"^subj\|"),
                         MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_subj)],
            ASK_CUSTOM_SUBJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_subj)],
            ASK_CUSTOM_NATURE:[MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_nature)],
            WAIT_CONTENT: [MessageHandler(filters.TEXT | filters.PHOTO, receive_content)],
        },
        fallbacks=[],
        per_chat=True,
        per_user=True,
    )
    app.add_handler(conv)
    # admin answer
    app.add_handler(CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$"))
    app.add_handler(MessageHandler(filters.ALL, admin_receive_answer),
                    group=1)   # group=1 ensures this runs after others
