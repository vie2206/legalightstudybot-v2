# doubts.py
"""
Ask-a-doubt module.

Student flow
------------
/doubt  →
[ Subject ⌨️ ]  →
[ Nature ⌨️ ]   →
 text | photo →
✅ confirmation

Admin flow
----------
Every doubt is immediately forwarded to ADMIN_ID
with the student’s handle + metadata so you can
reply manually (public or private) for now.
"""

from __future__ import annotations
import enum, datetime as dt
from typing import Final

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    Update, InputFile
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters
)

from database import session_scope, Doubt, DoubtQuota   # models & helper

# ─────────────── config ───────────────
ADMIN_ID: Final[int] = 803299591           #  ← your Telegram ID
MAX_PRIVATE = 3
MAX_PUBLIC  = 2

# ─────────────── enum helpers ─────────
class _Choice(enum.Enum):
    def __new__(cls, key: str, label: str):
        obj = object.__new__(cls)
        obj._value_ = key
        obj.label   = label
        return obj
    def __str__(self):     # human-readable
        return self.label

class Subject(_Choice):
    ENGLISH      = ("EN", "English & RC")
    LEGAL        = ("LE", "Legal Reasoning")
    LOGIC        = ("LO", "Logical Reasoning")
    MATHS        = ("MA", "Maths")
    GKCA         = ("GK", "GK / CA")
    MOCK         = ("MO", "Mock Test")
    SECTIONAL    = ("SE", "Sectional Test")
    STRATEGY     = ("ST", "Strategy / Time Mgmt")
    APPLICATION  = ("AP", "College / Application")
    OTHER        = ("OT", "Other / Custom")

class Nature(_Choice):
    CANT_SOLVE   = ("NS1", "Can’t solve a question")
    DONT_GET_ANS = ("NS2", "Don’t understand answer")
    WRONG_ANS    = ("NS3", "Explain my wrong answer")
    CONCEPT      = ("NS4", "Concept clarification")
    ALT_METHOD   = ("NS5", "Need alternative method")
    SOURCE_REQ   = ("NS6", "Source / reference")
    TIME_MGMT    = ("NS7", "Time-management advice")
    STRATEGY     = ("NS8", "Test-taking strategy")
    OTHER        = ("NS9", "Other / Custom")

# ─────────────── states ───────────────
CHOOSING_SUBJ, ASK_SUBJ_CUSTOM, CHOOSING_NAT, ASK_NAT_CUSTOM, WAIT_CONTENT = range(5)

# ─────────────── quota helper ─────────
def _today() -> dt.date:
    return dt.date.today()

def _check_quota(uid: int, private: bool) -> str | None:
    with session_scope() as s:
        quota = s.get(DoubtQuota, uid)
        today = _today()
        if not quota:
            quota = DoubtQuota(user_id=uid, date=today,
                               public_count=0, private_count=0)
            s.add(quota)
            s.flush()

        # reset if a new day
        if quota.date != today:
            quota.date = today
            quota.public_count = 0
            quota.private_count = 0

        used = quota.private_count if private else quota.public_count
        limit = MAX_PRIVATE if private else MAX_PUBLIC
        if used >= limit:
            return (
                f"⚠️ You’ve reached your daily "
                f"{'private' if private else 'public'}-doubt quota "
                f"({limit}). Try again tomorrow."
            )
        # reserve a slot (roll back on failure later)
        if private: quota.private_count += 1
        else:       quota.public_count  += 1
    return None

# ─────────────── keyboards ────────────
def _subj_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(str(s), callback_data=f"subj|{s.name}")]
         for s in Subject]
    )

def _nat_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(str(n), callback_data=f"nat|{n.name}")]
         for n in Nature]
    )

# ─────────────── conversation ─────────
async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = _check_quota(update.effective_user.id, private=True)  # quota counted only when fully stored
    if err:
        return await update.message.reply_text(err)

    ctx.user_data.clear()
    await update.message.reply_text(
        "What subject is your doubt about?",
        reply_markup=_subj_kb(),
    )
    return CHOOSING_SUBJ

# ---- subject chosen
async def subj_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    name = q.data.split("|")[1]
    if name == Subject.OTHER.name:
        await q.message.reply_text("Enter custom subject (≤ 30 chars):")
        return ASK_SUBJ_CUSTOM
    ctx.user_data["subject"] = name
    await q.message.reply_text(
        "What’s the nature of your doubt?",
        reply_markup=_nat_kb()
    )
    return CHOOSING_NAT

async def subj_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()[:30]
    ctx.user_data["subject"] = txt
    await update.message.reply_text(
        "Nature of doubt?",
        reply_markup=_nat_kb()
    )
    return CHOOSING_NAT

# ---- nature chosen
async def nat_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    name = q.data.split("|")[1]
    if name == Nature.OTHER.name:
        await q.message.reply_text("Enter custom nature (≤ 30 chars):")
        return ASK_NAT_CUSTOM
    ctx.user_data["nature"] = name
    await q.message.reply_text("Send the doubt as text *or* a photo.",
                               parse_mode="Markdown")
    return WAIT_CONTENT

async def nat_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()[:30]
    ctx.user_data["nature"] = txt
    await update.message.reply_text("Now send the doubt text or photo:")
    return WAIT_CONTENT

# ---- content
async def content_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    private = True  # all current doubts are private; you decide later
    err = _check_quota(uid, private)
    if err:
        return await update.message.reply_text(err) or ConversationHandler.END

    subj = ctx.user_data["subject"]
    nat  = ctx.user_data["nature"]

    text = update.message.text_html or ""
    photo_id: str | None = None
    if update.message.photo:
        # get largest resolution
        photo_id = update.message.photo[-1].file_id
    elif not text:
        return await update.message.reply_text("Need text or a photo.") or WAIT_CONTENT

    # DB record
    with session_scope() as s:
        d = Doubt(
            user_id=uid,
            subject=subj,
            nature=nat,
            text=text,
            photo_file_id=photo_id,
            created_at=dt.datetime.utcnow(),
            is_public=False
        )
        s.add(d)
        s.flush()      # to get PK

    # student confirmation
    await update.message.reply_text("✅ Your doubt has been sent to the mentor!")

    # forward to admin
    sub_lbl = subj if not hasattr(Subject, subj) else Subject[subj].label
    nat_lbl = nat  if not hasattr(Nature,  nat ) else Nature[nat ].label
    header = (
        f"🆕 *New doubt*\n"
        f"From: [{update.effective_user.full_name}](tg://user?id={uid})\n"
        f"Subject: _{sub_lbl}_\n"
        f"Nature:  _{nat_lbl}_\n"
        f"ID: #{d.id}"
    )
    if photo_id:
        await ctx.bot.send_photo(
            ADMIN_ID, photo_id, caption=f"{header}\n\n{text}",
            parse_mode="Markdown"
        )
    else:
        await ctx.bot.send_message(
            ADMIN_ID, f"{header}\n\n{text}", parse_mode="Markdown"
        )
    return ConversationHandler.END

# ---- cancel
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Doubt submission cancelled.")
    return ConversationHandler.END

# ─────────────── registration ────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            CHOOSING_SUBJ: [
                CallbackQueryHandler(subj_cb, pattern=r"^subj\|"),
            ],
            ASK_SUBJ_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, subj_custom)
            ],
            CHOOSING_NAT: [
                CallbackQueryHandler(nat_cb,  pattern=r"^nat\|"),
            ],
            ASK_NAT_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nat_custom)
            ],
            WAIT_CONTENT: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO, content_msg
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=False,
    )
    app.add_handler(conv)
