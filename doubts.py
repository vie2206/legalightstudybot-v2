# doubts.py
"""
‘/doubt’ conversation:
  1.  Subject  ➜  inline keyboard (or custom free-text)
  2.  Nature   ➜  inline keyboard (or custom free-text)
  3.  Question ➜  text or single photo (caption optional)

After submission the bot:
  • stores the record (Subject, Nature, text/photo_id, public/private flag)
  • decrements the user’s daily quota
  • forwards the material to the teacher (admin_id) with inline-buttons:
        🔒 Private reply | 📢 Public reply
  • shows the student a confirmation

Command:
  /doubt – start the wizard
"""

import asyncio, enum, io, datetime as dt
from typing import Optional

from telegram import (
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as MK,
    Update, InputFile
)
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes, Application
)
from database import session_scope, Doubt, DoubtQuota

# ──────────────────────────────────────────────────────────
# ENUMS
class Subject(enum.Enum):
    ENGLISH          = "English & RC"
    LEGAL            = "Legal Reasoning"
    LOGICAL          = "Logical Reasoning"
    MATHS            = "Maths"
    GK_CA            = "GK / CA"
    MOCK_TEST        = "Mock Test"
    SECTIONAL_TEST   = "Sectional Test"
    STRATEGY         = "Strategy / Time-Mgmt"
    APPLICATION      = "Application / College"
    OTHER            = "Custom"

class Nature(enum.Enum):
    CANT_SOLVE       = "Can’t solve"
    DONT_UNDERSTAND  = "Don’t understand answer"
    EXPLAIN_WRONG    = "Explain wrong answer"
    CONCEPT          = "Concept clarification"
    ALT_METHOD       = "Alternative method"
    SOURCE_REQ       = "Source / reference"
    TIME_MGMT        = "Time-management advice"
    STRATEGY         = "Test-taking strategy"
    OTHER            = "Custom"

# ──────────────────────────────────────────────────────────
# Conversation states
ASK_SUBJ, ASK_SUBJ_FREE, ASK_NATURE, ASK_NATURE_FREE, ASK_Q_TEXT, ASK_MEDIA, DONE = range(7)

# ──────────────────────────────────────────────────────────
# Quota helper
QUOTA_PUB  = 2
QUOTA_PRIV = 3
def _today():
    return dt.date.today()

async def _check_quota(uid: int, public: bool) -> Optional[str]:
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, _today()))
        if not q:                     # first record today
            q = DoubtQuota(user_id=uid, date=_today(),
                           public_count=0, private_count=0,
                           last_reset=dt.datetime.utcnow())
            s.add(q)
        if public and q.public_count >= QUOTA_PUB:
            return ("You reached today’s *public*-answer quota "
                    f"({QUOTA_PUB}). Try private or wait till tomorrow.")
        if not public and q.private_count >= QUOTA_PRIV:
            return ("You reached today’s *private*-answer quota "
                    f"({QUOTA_PRIV}). Wait till tomorrow.")
        # all good → increment
        if public:
            q.public_count += 1
        else:
            q.private_count += 1
    return None           # ok

# ──────────────────────────────────────────────────────────
# Step handlers
async def cmd_doubt(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(upd.effective_user.id, public=False)
    if err:
        return await upd.message.reply_markdown(err)
    kb = [[Btn(v.value, callback_data=f"s|{k.name}")]
          for k, v in Subject.__members__.items() if k != "OTHER"]
    kb.append([Btn("Other / Custom", callback_data="s|OTHER")])
    await upd.message.reply_text("Choose *subject*:", parse_mode="Markdown",
                                 reply_markup=MK(kb))
    return ASK_SUBJ

async def subj_chosen(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = upd.callback_query; await q.answer()
    code = q.data.split("|")[1]
    if code == "OTHER":
        await q.edit_message_text("Type custom subject (≤ 30 chars):")
        return ASK_SUBJ_FREE
    ctx.user_data["subject"] = Subject[code].value
    return await _ask_nature(q)

async def subj_free(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"] = upd.message.text[:30]
    return await _ask_nature(upd.message)

async def _ask_nature(msglike):
    kb = [[Btn(v.value, callback_data=f"n|{k.name}")]
          for k, v in Nature.__members__.items() if k != "OTHER"]
    kb.append([Btn("Other / Custom", callback_data="n|OTHER")])
    await msglike.reply_text("Choose *nature* of doubt:", parse_mode="Markdown",
                             reply_markup=MK(kb))
    return ASK_NATURE

async def nature_chosen(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = upd.callback_query; await q.answer()
    code = q.data.split("|")[1]
    if code == "OTHER":
        await q.edit_message_text("Type custom nature (≤ 30 chars):")
        return ASK_NATURE_FREE
    ctx.user_data["nature"] = Nature[code].value
    await q.edit_message_text("Send your *question* (text or 1 photo):",
                              parse_mode="Markdown")
    return ASK_Q_TEXT

async def nature_free(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"] = upd.message.text[:30]
    await upd.message.reply_text("Send your *question* (text or 1 photo):",
                                 parse_mode="Markdown")
    return ASK_Q_TEXT

async def receive_question(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = upd.message
    ctx.user_data["question_text"] = msg.caption or msg.text or ""
    ctx.user_data["photo_id"] = (msg.photo[-1].file_id
                                 if msg.photo else None)
    # store DB
    with session_scope() as s:
        d = Doubt(
            user_id=upd.effective_user.id,
            subject=ctx.user_data["subject"],
            nature=ctx.user_data["nature"],
            text=ctx.user_data["question_text"],
            photo_id=ctx.user_data["photo_id"],
            is_public=False,
            created_at=dt.datetime.utcnow(),
        )
        s.add(d); s.flush()   # get id
        doubt_id = d.id
    # forward to admin with buttons
    admin_id = ctx.application.bot_data["ADMIN_ID"]
    inline = MK([[
        Btn("🔒 Private reply", callback_data=f"ans|{doubt_id}|0"),
        Btn("📢 Public reply",  callback_data=f"ans|{doubt_id}|1"),
    ]])
    caption = (f"*New doubt #{doubt_id}*\n"
               f"*Subject:* {d.subject}\n*Nature:* {d.nature}\n"
               f"*From:* {upd.effective_user.full_name} `{upd.effective_user.id}`\n\n"
               f"{d.text}")
    if d.photo_id:
        await ctx.bot.send_photo(admin_id, d.photo_id,
                                 caption=caption, parse_mode="Markdown",
                                 reply_markup=inline)
    else:
        await ctx.bot.send_message(admin_id, caption,
                                   parse_mode="Markdown",
                                   reply_markup=inline)
    await msg.reply_markdown(
        "✅ Doubt received! The teacher will get back to you soon."
    )
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────
# Admin answer handler
async def admin_answer_cb(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = upd.callback_query; await q.answer()
    _, did, pub = q.data.split("|")
    ctx.user_data.update({"doubt_id": int(did), "public": pub == "1"})
    await q.edit_message_reply_markup(None)
    await q.message.reply_text("Send your answer (text, photo, voice…):")
    return ASK_MEDIA          # reuse media/text state

async def receive_answer(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did   = ctx.user_data["doubt_id"]
    pub   = ctx.user_data["public"]
    msg   = upd.message
    text  = msg.caption or msg.text or ""
    photo = msg.photo[-1].file_id if msg.photo else None

    with session_scope() as s:
        d = s.get(Doubt, did)
        if not d: return
        d.answer_text  = text
        d.answer_photo = photo
        d.answered_at  = dt.datetime.utcnow()
        d.is_public    = pub

    # destination
    if pub:
        chat_id = ctx.application.bot_data["ANNOUNCE_CHAT"]
        if photo:
            await ctx.bot.send_photo(chat_id, photo, caption=text)
        else:
            await ctx.bot.send_message(chat_id, text)
    else:
        if photo:
            await ctx.bot.send_photo(d.user_id, photo, caption=text)
        else:
            await ctx.bot.send_message(d.user_id, text)
    await msg.reply_text("✅ Sent!")
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────
def register_handlers(app: Application, admin_id: int):
    # store admin & (optionally) public channel/group id
    app.bot_data["ADMIN_ID"] = admin_id
    app.bot_data["ANNOUNCE_CHAT"] = admin_id   # reuse personal chat for now

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:    [CallbackQueryHandler(subj_chosen,  pattern=r"^s\|")],
            ASK_SUBJ_FREE:[MessageHandler(filters.TEXT & ~filters.COMMAND, subj_free)],
            ASK_NATURE:  [CallbackQueryHandler(nature_chosen, pattern=r"^n\|")],
            ASK_NATURE_FREE:[MessageHandler(filters.TEXT & ~filters.COMMAND, nature_free)],
            ASK_Q_TEXT:  [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, receive_question)],
            ASK_MEDIA:   [MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE) & ~filters.COMMAND, receive_answer)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: u.message.reply_text("Cancelled") or ConversationHandler.END)],
        per_user=True,
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$"))
