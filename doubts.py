# doubts.py
"""
Private doubt-asking system

•  /doubt  → pick *subject*  → pick *nature*  → send text/photo
•  Quotas: 2 public + 3 private answers /-day (per user)
•  Admin receives inline buttons to answer privately or publicly
"""

import asyncio, enum, io
import datetime as dt
from typing import Dict, Tuple

from telegram import (
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as Mk,
    InputMediaPhoto,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import session_scope, Doubt, DoubtQuota

# ───────────────────────────────────────────────────────────────
ADMIN_ID = 803299591  # <— your Telegram numeric id

class Subject(enum.Enum):
    ENGLISH           = "English & RC"
    LEGAL_REASONING   = "Legal Reasoning"
    LOGICAL_REASONING = "Logical Reasoning"
    MATHS             = "Maths"
    GK_CA             = "GK / CA"
    MOCK_TEST         = "Mock Test"
    SECTIONAL_TEST    = "Sectional Test"
    STRATEGY          = "Strategy / Time-Mgmt"
    APPLICATION       = "Application / College"
    OTHER             = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE        = "Can’t solve a question"
    DONT_GET_ANS      = "Don’t understand the answer"
    EXPLAIN_WRONG     = "Explain my wrong answer"
    CONCEPT           = "Concept clarification"
    ALT_METHOD        = "Need alternative method"
    SOURCE_REQ        = "Source / reference request"
    TIME_MGMT         = "Time-management advice"
    TEST_STRATEGY     = "Test-taking strategy"
    OTHER             = "Other / Custom"

# ─── convo states
ASK_SUBJ, ASK_NATURE, ASK_CUSTOM_SUBJ, ASK_CUSTOM_NATURE, WAIT_TEXT = range(5)

# ───────────────────────────────────────────────────────────────
# Quota helpers ─ 2 public + 3 private / day
DAILY_PUB   = 2
DAILY_PRIV  = 3

async def _check_quota(uid: int, private: bool) -> Tuple[bool, str]:
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, today))
        if not q:
            q = DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            s.add(q); s.commit()
        if private and q.private_count >= DAILY_PRIV:
            return False, "🛑 You’ve reached today’s private-doubt limit."
        if (not private) and q.public_count >= DAILY_PUB:
            return False, "🛑 You’ve reached today’s public-doubt limit."
        # increment
        if private: q.private_count += 1
        else:       q.public_count  += 1
        s.commit()
    return True, ""

# ───────────────────────────────────────────────────────────────
async def cmd_doubt(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ok, err = await _check_quota(upd.effective_user.id, private=True)  # we count now
    if not ok:
        return await upd.message.reply_text(err)

    kb = [
        [Btn(subj.value, callback_data=f"subj|{subj.name}")]
        for subj in Subject
    ]
    await upd.message.reply_text(
        "📝 *Pick subject category:*",
        reply_markup=Mk(kb), parse_mode="Markdown"
    )
    return ASK_SUBJ

async def choose_subject(q: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = q.callback_query; await q.answer()
    subj_name = q.data.split("|", 1)[1]
    ctx.user_data["subject"] = subj_name
    if subj_name == "OTHER":
        await q.edit_message_text("Type custom *subject* label (≤30 chars):", parse_mode="Markdown")
        return ASK_CUSTOM_SUBJ

    return await _next_nature(q)

async def _next_nature(q):
    kb = [
        [Btn(nat.value, callback_data=f"nat|{nat.name}")]
        for nat in Nature
    ]
    await q.edit_message_text(
        "📌 *Nature of doubt?*",
        reply_markup=Mk(kb), parse_mode="Markdown"
    )
    return ASK_NATURE

async def custom_subj(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"] = upd.message.text[:30]
    return await _next_nature(upd)

async def choose_nature(q: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = q.callback_query; await q.answer()
    nat_name = q.data.split("|", 1)[1]
    ctx.user_data["nature"] = nat_name
    if nat_name == "OTHER":
        await q.edit_message_text("Type custom *nature* label (≤30 chars):", parse_mode="Markdown")
        return ASK_CUSTOM_NATURE

    await q.edit_message_text("✍️ Send your text *or* 1 photo (no video/audio).", parse_mode="Markdown")
    return WAIT_TEXT

async def custom_nat(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"] = upd.message.text[:30]
    await upd.message.reply_text("✍️ Send your text *or* 1 photo (no video/audio).", parse_mode="Markdown")
    return WAIT_TEXT

# ───────────────────────────────────────────────────────────────
async def receive_doubt(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = upd.effective_user.id
    subj = ctx.user_data["subject"]
    nature = ctx.user_data["nature"]
    text = upd.message.text or "(see attached)"
    photo_id = None
    if upd.message.photo:
        photo_id = upd.message.photo[-1].file_id

    # save row
    with session_scope() as s:
        d = Doubt(
            user_id=uid, subject=subj, nature=nature,
            text=text, photo_id=photo_id, created=dt.datetime.utcnow()
        )
        s.add(d); s.commit(); s.refresh(d)
        did = d.id

    # DM admin
    msg_admin = (
        f"📥 *New doubt* #{did}\n"
        f"*User:* `{uid}`\n"
        f"*Subject:* {subj}\n"
        f"*Nature:* {nature}\n"
        f"*Text:* {text}"
    )
    buttons = [
        [
            Btn("Answer Privately", callback_data=f"ans|{did}|1"),
            Btn("Answer Publicly",  callback_data=f"ans|{did}|0"),
        ]
    ]
    if photo_id:
        await ctx.bot.send_photo(
            ADMIN_ID, photo_id, caption=msg_admin, parse_mode="Markdown",
            reply_markup=Mk(buttons)
        )
    else:
        await ctx.bot.send_message(
            ADMIN_ID, msg_admin, parse_mode="Markdown",
            reply_markup=Mk(buttons)
        )

    await upd.message.reply_text("✅ Your doubt has been sent to the mentor. You’ll be answered soon 🙂")
    return ConversationHandler.END

# ───────────────────────────────────────────────────────────────
async def admin_answer_cb(q: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = q.callback_query; await q.answer()
    _, did, priv = q.data.split("|")
    priv = bool(int(priv))

    await q.message.reply_text("✏️ Send your answer now (text/photo).")
    ctx.user_data["answer_for"] = (int(did), priv)
    return WAIT_TEXT  # reuse state for admin answer

async def admin_answer_msg(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did, priv = ctx.user_data.pop("answer_for")
    with session_scope() as s:
        d = s.get(Doubt, did)
        if not d:
            return await upd.message.reply_text("Doubt not found (maybe already answered).")

        target = d.user_id if priv else ADMIN_ID  # public -> admin posts & can forward
        caption = (
            f"❓ *Doubt #{d.id}* by `{d.user_id}`\n"
            f"*Subject:* {d.subject}\n"
            f"*Nature:* {d.nature}\n"
            f"*Text:* {d.text}\n\n"
            f"💡 *Answer:*"
        )
        if upd.message.photo:
            pid = upd.message.photo[-1].file_id
            await ctx.bot.send_photo(target, pid, caption=caption, parse_mode="Markdown")
        else:
            await ctx.bot.send_message(target, caption, parse_mode="Markdown")
            await ctx.bot.send_message(target, upd.message.text)

        d.answered = True
        s.commit()

    await upd.message.reply_text("✅ Sent!")
    return ConversationHandler.END

# ───────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ: [CallbackQueryHandler(choose_subject, pattern=r"^subj\|")],
            ASK_CUSTOM_SUBJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subj)],
            ASK_NATURE: [CallbackQueryHandler(choose_nature, pattern=r"^nat\|")],
            ASK_CUSTOM_NATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nat)],
            WAIT_TEXT: [
                MessageHandler(filters.TEXT | filters.PHOTO, receive_doubt)
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)],
        per_user=True,
    )
    app.add_handler(conv)

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$")],
        states={
            WAIT_TEXT: [MessageHandler(filters.TEXT | filters.PHOTO, admin_answer_msg)],
        },
        fallbacks=[],
        per_user=False,  # admin only
    )
    app.add_handler(admin_conv)
