"""
doubts.py  –  Raise-a-Doubt module
──────────────────────────────────
Commands
  /doubt               → interactive wizard
  /my_doubts           → list your own pending & resolved doubts
Admin-only
  /doubt_list [open|all]      → show IDs waiting for answer
  /doubt_answer <id>          → begin reply flow (public or private)
  /doubt_resolved <id>        → mark resolved without answer

Quota
  •  2 PUBLIC answers / 24 h
  •  3 PRIVATE answers / 24 h
"""

import asyncio, datetime as dt, io, os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ConversationHandler,
    MessageHandler, ContextTypes, filters
)

from database import session_scope, Doubt, DoubtQuota
from bot import ADMIN_ID           # import constant from main module

# ────────────────────────────────────────────────────────────────────
# Wizard states
ASK_SUBJECT, ASK_NATURE, ASK_TEXT, ASK_MEDIA, CONFIRM_SUBMIT = range(5)

# preset lists
SUBJECTS = [
    "English", "Maths", "GK / Current-Affairs", "Legal Reasoning",
    "Logical Reasoning", "Sectional-Test", "Full-Mock", "CLATOPEDIA",
    "Other (custom)",
]
NATURES = [
    "Can't solve", "Can't understand explanation", "Wrong answer?",
    "Concept clarification", "General guidance"
]

# ────────────────────────────────────────────────────────────────────
# Utility helpers
def _today() -> dt.date:
    return dt.datetime.utcnow().date()


def _check_quota(user_id: int, public: bool) -> bool:
    """Return True if user still has quota left *after* this submission."""
    with session_scope() as s:
        q: DoubtQuota = (
            s.query(DoubtQuota)
            .filter(DoubtQuota.user_id == user_id,
                    DoubtQuota.date == _today())
            .first()
        )
        if not q:
            q = DoubtQuota(
                user_id=user_id, date=_today(),
                public_count=0, private_count=0
            )
            s.add(q)
            s.flush()

        if public:
            allowed = q.public_count < 2
            if allowed:
                q.public_count += 1
            return allowed
        allowed = q.private_count < 3
        if allowed:
            q.private_count += 1
        return allowed


async def _send_admin_notification(app: Application, doubt: Doubt):
    txt = (f"🆕 *New doubt* #{doubt.id}\n"
           f"*From*: [{doubt.user_id}](tg://user?id={doubt.user_id})\n"
           f"*Subject*: {doubt.subject}\n"
           f"*Nature*: {doubt.nature}")
    await app.bot.send_message(
        ADMIN_ID, txt, parse_mode="Markdown"
    )
    if doubt.photo_file_id:
        await app.bot.send_photo(ADMIN_ID, doubt.photo_file_id)
    if doubt.text:
        await app.bot.send_message(ADMIN_ID, f"```{doubt.text}```",
                                   parse_mode="Markdown")


# ────────────────────────────────────────────────────────────────────
# Wizard entry
async def doubt_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    kb = [[InlineKeyboardButton(s, callback_data=f"subj|{s}")]
          for s in SUBJECTS]
    await update.message.reply_text(
        "📌 *Raise a doubt* – pick the subject category:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return ASK_SUBJECT


async def pick_subject(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    subj = q.data.split("|", 1)[1]
    ctx.user_data["subject"] = subj
    # nature
    kb = [[InlineKeyboardButton(n, callback_data=f"nat|{n}")]
          for n in NATURES]
    await q.edit_message_text(
        "🔍 Pick the *nature* of the doubt:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return ASK_NATURE


async def pick_nature(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    ctx.user_data["nature"] = q.data.split("|", 1)[1]
    await q.edit_message_text(
        "✍️ Send your doubt text (or type `skip`):", parse_mode="Markdown"
    )
    return ASK_TEXT


async def text_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt.lower().strip() != "skip":
        ctx.user_data["text"] = txt[:4096]
    await update.message.reply_text(
        "📷 Now send 1 photo *or* 1 PDF (<=20 MB), or type `skip`.",
        parse_mode="Markdown"
    )
    return ASK_MEDIA


async def media_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text and update.message.text.lower().strip() == "skip":
        # no media
        return await _confirm(update, ctx)

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        ctx.user_data["photo"] = file_id
    elif update.message.document and update.message.document.mime_type == "application/pdf":
        ctx.user_data["pdf"] = update.message.document.file_id
    else:
        return await update.message.reply_text("❌ Send photo or PDF only, or `skip`.") or ASK_MEDIA

    return await _confirm(update, ctx)


async def _confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    kb = [
        [InlineKeyboardButton("Submit ✅", callback_data="cfm|yes"),
         InlineKeyboardButton("Cancel ❌", callback_data="cfm|no")]
    ]
    await update.message.reply_text(
        "Submit this doubt?", reply_markup=InlineKeyboardMarkup(kb)
    )
    return CONFIRM_SUBMIT


async def confirm_submit(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data.endswith("|no"):
        await q.edit_message_text("🚫 Doubt cancelled.")
        return ConversationHandler.END

    # build DB row
    data = ctx.user_data
    is_public = True   # default public
    if not _check_quota(q.from_user.id, is_public):
        await q.edit_message_text(
            "⚠️ Daily public quota reached (2). Try private, or upgrade."
        )
        return ConversationHandler.END

    with session_scope() as s:
        d = Doubt(
            user_id=q.from_user.id,
            subject=data.get("subject"),
            nature=data.get("nature"),
            text=data.get("text"),
            photo_file_id=data.get("photo"),
            pdf_file_id=data.get("pdf"),
            public=is_public,
        )
        s.add(d)
        s.flush()

    await q.edit_message_text("✅ Doubt submitted!")
    # ping admin
    await _send_admin_notification(ctx.application, d)
    ctx.user_data.clear()
    return ConversationHandler.END


# ────────────────────────────────────────────────────────────────────
async def my_doubts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with session_scope() as s:
        rows: List[Doubt] = (
            s.query(Doubt)
            .filter(Doubt.user_id == update.effective_user.id)
            .order_by(Doubt.id.desc())
            .limit(10)
            .all()
        )
    if not rows:
        return await update.message.reply_text("No doubts logged yet.")
    msg = "\n".join(
        f"#{d.id} – *{d.subject}* ({'✅' if d.answered_at else '⏳'})"
        for d in rows
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ────────────────────────────────────────────────────────────────────
# admin helpers (minimal)
async def doubt_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    filter_open = (ctx.args and ctx.args[0] == "open")
    with session_scope() as s:
        q = s.query(Doubt)
        if filter_open:
            q = q.filter(Doubt.answered_at.is_(None))
        rows = q.order_by(Doubt.id).all()
    if not rows:
        await update.message.reply_text("No doubts.")
    txt = "\n".join(f"#{d.id} – {d.subject} ({'✅' if d.answered_at else '⏳'})"
                    for d in rows)
    await update.message.reply_text(txt or "No doubts.")

# (Answering flow intentionally omitted for brevity)

# ────────────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    wizard = ConversationHandler(
        entry_points=[CommandHandler("doubt", doubt_entry)],
        states={
            ASK_SUBJECT: [CallbackQueryHandler(pick_subject, pattern=r"^subj\|")],
            ASK_NATURE:  [CallbackQueryHandler(pick_nature,  pattern=r"^nat\|")],
            ASK_TEXT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, text_received)],
            ASK_MEDIA: [
                MessageHandler(filters.PHOTO | filters.Document.PDF | filters.Regex("^skip$"),
                               media_received)
            ],
            CONFIRM_SUBMIT: [CallbackQueryHandler(confirm_submit, pattern=r"^cfm\|")],
        },
        fallbacks=[],
        per_user=True,
        per_message=False,
    )
    app.add_handler(wizard)
    app.add_handler(CommandHandler("my_doubts", my_doubts))

    # admin
    app.add_handler(CommandHandler("doubt_list", doubt_list))
