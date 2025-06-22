# doubts.py
"""
Student-doubt intake + admin-answer workflow.

Flow
----
/doubt → choose Subject   → choose Nature → (optional custom text) →
         send question (text/photo)       → bot forwards to admin.

Admin receives inline-buttons:
    ✅ Public (reply in group)   |   🔒 Private (reply in DM)

Quotas
------
Free users: 2 public + 3 private answers per rolling day.

DB tables: Doubt, DoubtQuota  – see models.py
"""

import os               # ←–––––– added
import enum
import io
import datetime as dt
from typing import Dict, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from database import session_scope, Doubt, DoubtQuota

# ──────────────────────────────────────────────────────────────
#  constants & enums
class Subject(enum.Enum):
    ENGLISH      = ("English & RC",          "ENG")
    LEGAL        = ("Legal Reasoning",       "LEG")
    LOGICAL      = ("Logical Reasoning",     "LOG")
    MATHS        = ("Maths",                 "MAT")
    GK           = ("GK / CA",               "GK")
    MOCK         = ("Mock Test",             "MCK")
    SECTIONAL    = ("Sectional Test",        "SEC")
    STRATEGY     = ("Strategy / Time-Mgmt",  "STR")
    APPLICATION  = ("Application / College", "APP")
    OTHER        = ("Other / Custom",        "OTH")

    def __new__(cls, label: str, code: str):
        obj = object.__new__(cls)
        obj._value_ = code
        obj.label = label
        return obj


class Nature(enum.Enum):
    CANT_SOLVE       = "Can’t solve the question"
    ANSWER_UNCLEAR   = "Don’t understand the official answer"
    WRONG_EXPLAIN    = "Explain my wrong answer"
    CONCEPT          = "Concept clarification"
    ALT_METHOD       = "Need alternative method"
    SOURCE_REQUEST   = "Source / reference request"
    TIME_MGMT        = "Time-management advice"
    STRATEGY         = "Test-taking strategy"
    OTHER            = "Other / Custom"

#  conversation steps
ASK_SUBJ, ASK_CUSTOM_SUBJ, ASK_NATURE, ASK_CUSTOM_NAT, ASK_CONTENT = range(5)

#  daily quota
PUBLIC_LIMIT  = 2
PRIVATE_LIMIT = 3

#  admin id
ADMIN_ID = int(os.getenv("ADMIN_ID", "803299591"))

# ──────────────────────────────────────────────────────────────
#  helpers
def _quota_key(user_id: int) -> str:
    return f"quota:{user_id}:{dt.date.today().isoformat()}"


async def _check_quota(user_id: int, public: bool) -> Optional[str]:
    """Return error string if over-quota, else None."""
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, {"user_id": user_id, "date": today})
        if not q:
            q = DoubtQuota(user_id=user_id, date=today,
                           public_count=0, private_count=0)
            s.add(q); s.commit()
        if public and q.public_count >= PUBLIC_LIMIT:
            return f"❌ Daily limit reached ({PUBLIC_LIMIT} public doubts)."
        if (not public) and q.private_count >= PRIVATE_LIMIT:
            return f"❌ Daily limit reached ({PRIVATE_LIMIT} private doubts)."
        # ok – pre-increment so concurrency is safe
        if public:
            q.public_count += 1
        else:
            q.private_count += 1
        s.commit()
    return None

# ──────────────────────────────────────────────────────────────
#  conversation callbacks
async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(update.effective_user.id, public=False)
    if err:
        return await update.message.reply_text(err)
    # subject keyboard
    kb = [[InlineKeyboardButton(s.label, callback_data=f"subj|{s.name}")]
          for s in Subject]
    await update.message.reply_text(
        "Choose *subject* of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ASK_SUBJ


async def subj_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    name = query.data.split("|", 1)[1]
    subj = Subject[name]
    if subj == Subject.OTHER:
        await query.edit_message_text("Enter custom *subject* (≤30 chars):",
                                      parse_mode="Markdown")
        return ASK_CUSTOM_SUBJ
    ctx.user_data["subj"] = subj
    return await _ask_nature(query, ctx)


async def custom_subj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()[:30]
    ctx.user_data["subj"] = txt
    return await _ask_nature(update, ctx)


async def _ask_nature(msg, ctx):
    kb = [[InlineKeyboardButton(n.value, callback_data=f"nat|{n.name}")]
          for n in Nature]
    if hasattr(msg, "edit_message_text"):
        await msg.edit_message_text(
            "Choose *nature* of your doubt:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )
    else:
        await msg.message.reply_text(
            "Choose *nature* of your doubt:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )
    return ASK_NATURE


async def nat_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    name = q.data.split("|", 1)[1]
    nat = Nature[name]
    if nat == Nature.OTHER:
        await q.edit_message_text("Enter custom *nature* (≤30 chars):",
                                  parse_mode="Markdown")
        return ASK_CUSTOM_NAT
    ctx.user_data["nat"] = nat.value
    return await _ask_content(q, ctx)


async def custom_nat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()[:30]
    ctx.user_data["nat"] = txt
    return await _ask_content(update, ctx)


async def _ask_content(msg, ctx):
    await msg.edit_message_text if hasattr(msg, "edit_message_text") else \
        msg.message.reply_text
    await msg.message.reply_text(
        "Send your doubt (text *or* ONE photo).\n"
        "_/cancel to abort_",
        parse_mode="Markdown",
    )
    return ASK_CONTENT


async def receive_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subj = ctx.user_data["subj"]
    nat  = ctx.user_data["nat"]

    text = update.message.text or ""
    photo = update.message.photo[-1] if update.message.photo else None

    if not text and not photo:
        return await update.message.reply_text("❌ send text or a photo.")
    if text and len(text) > 1000:
        return await update.message.reply_text("❌ Text too long (max 1000).")

    # persist
    with session_scope() as s:
        d = Doubt(
            user_id=user.id,
            subject=subj if isinstance(subj, str) else subj.label,
            nature=nat,
            content=text,
            status="open",
            created_at=dt.datetime.utcnow(),
        )
        s.add(d); s.flush()           # get auto-id

        # forward to admin
        caption = (f"📚 *Doubt #{d.id}*\n"
                   f"*Subject:* {d.subject}\n"
                   f"*Nature:*  {d.nature}\n"
                   f"*From:* @{user.username or user.first_name}")
        if text:
            caption += f"\n\n{text}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Answer Publicly",
                                  callback_data=f"ans|{d.id}|1"),
             InlineKeyboardButton("🔒 Answer Privately",
                                  callback_data=f"ans|{d.id}|0")]
        ])
        if photo:
            file = await photo.get_file()
            bio = io.BytesIO(await file.download_as_bytearray())
            bio.name = "question.jpg"
            await ctx.bot.send_photo(
                ADMIN_ID, bio, caption=caption, reply_markup=kb,
                parse_mode="Markdown"
            )
        else:
            await ctx.bot.send_message(
                ADMIN_ID, caption, reply_markup=kb, parse_mode="Markdown"
            )
        s.commit()

    await update.message.reply_text("✅ Doubt received! I’ll get back to you soon.")
    return ConversationHandler.END


async def admin_answer_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, did, public = q.data.split("|")
    did   = int(did)
    pub   = bool(int(public))
    ctx.user_data["ans_public"] = pub
    ctx.user_data["ans_did"] = did
    await q.message.reply_text("Send your answer (text or ONE photo).")
    return ASK_CONTENT  # reuse


async def admin_answer_recv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pub = ctx.user_data["ans_public"]
    did = ctx.user_data["ans_did"]
    txt = update.message.text or ""
    photo = update.message.photo[-1] if update.message.photo else None

    with session_scope() as s:
        d: Doubt = s.get(Doubt, did)
        if not d:
            return await update.message.reply_text("Doubt not found.")
        d.answer   = txt if txt else "<photo>"
        d.answered = dt.datetime.utcnow()
        d.status   = "resolved"
        s.commit()

    dest_chat = update.message.chat_id if pub else d.user_id
    caption = f"*Answer to doubt #{did}:*\n\n{txt or ''}"
    if photo:
        file = await photo.get_file()
        bio  = io.BytesIO(await file.download_as_bytearray()); bio.name="answer.jpg"
        await ctx.bot.send_photo(dest_chat, bio, caption=caption, parse_mode="Markdown")
    else:
        await ctx.bot.send_message(dest_chat, caption, parse_mode="Markdown")

    await update.message.reply_text("✅ Sent!")
    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:         [CallbackQueryHandler(subj_chosen, pattern=r"^subj\|")],
            ASK_CUSTOM_SUBJ:  [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subj)],
            ASK_NATURE:       [CallbackQueryHandler(nat_chosen,   pattern=r"^nat\|")],
            ASK_CUSTOM_NAT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nat)],
            ASK_CONTENT:      [MessageHandler(filters.TEXT | filters.PHOTO, receive_doubt)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$")],
        states={
            ASK_CONTENT: [MessageHandler(filters.TEXT | filters.PHOTO, admin_answer_recv)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    )
    app.add_handler(conv)
    app.add_handler(admin_conv)
