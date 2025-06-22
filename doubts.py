# doubts.py
"""
Student-doubt intake & admin-answer module.
"""

from __future__ import annotations

import enum, datetime as dt
from pathlib import Path
from typing import Final, Optional  # ← added Final

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from database import session_scope, Doubt, DoubtQuota
# -----------------------------------------------------------

# ─── Configuration ─────────────────────────────────────────
MAX_PUB:   Final = 2   # free public answers per user / 24 h
MAX_PRIV:  Final = 3   # free private answers per user / 24 h

# ─── Enums for subject & nature ────────────────────────────
class Subject(enum.Enum):
    ENGLISH = "English & RC"
    LEGAL   = "Legal Reasoning"
    LOGICAL = "Logical Reasoning"
    MATHS   = "Maths"
    GK      = "GK / CA"
    MOCK    = "Mock Test"
    SECT    = "Sectional Test"
    STRATEGY= "Strategy / Time-Mgmt"
    COLLEGE = "Application / College"
    OTHER   = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE     = "Can’t solve a question"
    DONT_GET_ANS   = "Don’t understand the answer"
    EXPLAIN_WRONG  = "Explain my wrong answer"
    CLARIFY_CONCEPT= "Concept clarification"
    ALT_METHOD     = "Need alternative method"
    SOURCE_REQ     = "Source / reference request"
    TIME_ADVICE    = "Time-management advice"
    TEST_STRAT     = "Test-taking strategy"
    OTHER          = "Other / Custom"

# ─── Conversation states ───────────────────────────────────
(
    ASK_SUBJ, ASK_CUSTOM_SUBJ,
    ASK_NATURE, ASK_CUSTOM_NATURE,
    ASK_TEXT, ASK_MEDIA, CONFIRM,
) = range(7)

# ─── Helpers ───────────────────────────────────────────────
def _today() -> dt.date: return dt.date.today()

async def _check_quota(uid: int, public: bool) -> Optional[str]:
    """Return error-text if quota exceeded, else None."""
    with session_scope() as s:
        quota = s.get(DoubtQuota, (uid, _today()))
        if quota is None:
            quota = DoubtQuota(user_id=uid, date=_today(),
                               public_count=0, private_count=0)
            s.add(quota)

        if public and quota.public_count >= MAX_PUB:
            return f"❌ You used your {MAX_PUB} free *public* doubts today."
        if not public and quota.private_count >= MAX_PRIV:
            return f"❌ You used your {MAX_PRIV} free *private* doubts today."
    return None

def _inc_quota(uid: int, public: bool):
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, _today()))
        if public:  q.public_count  += 1
        else:       q.private_count += 1

async def _store_doubt(d: Doubt) -> int:
    with session_scope() as s:
        s.add(d)
        s.flush()
        return d.id

# ─── Command entry - /doubt ────────────────────────────────
async def cmd_doubt(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    err = await _check_quota(upd.effective_user.id, public=False)
    if err:
        await upd.message.reply_markdown(err + "\nUpgrade plan coming soon 🙂")
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(v.value, callback_data=f"subj|{v.name}")]
        for v in Subject if v != Subject.OTHER
    ] + [[InlineKeyboardButton("Other / Custom", callback_data="subj|OTHER")]]
    await upd.message.reply_text(
        "Choose *subject* of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ASK_SUBJ

# Subject chosen
async def subj_chosen(q: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await q.callback_query.answer()
    key = q.callback_query.data.split("|",1)[1]
    if key == "OTHER":
        await q.callback_query.edit_message_text("Type custom subject (≤ 30 chars):")
        return ASK_CUSTOM_SUBJ
    ctx.user_data["subj"] = Subject[key].value
    return await _ask_nature(q.callback_query)

async def custom_subj(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["subj"] = upd.message.text[:30]
    return await _ask_nature(upd)

async def _ask_nature(sender):
    kb = [
        [InlineKeyboardButton(v.value, callback_data=f"nat|{v.name}")]
        for v in Nature if v != Nature.OTHER
    ] + [[InlineKeyboardButton("Other / Custom", callback_data="nat|OTHER")]]
    await sender.edit_message_text(
        "Specify *nature* of doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ASK_NATURE

# Nature chosen
async def nat_chosen(q: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await q.callback_query.answer()
    key = q.callback_query.data.split("|",1)[1]
    if key == "OTHER":
        await q.callback_query.edit_message_text("Type custom nature (≤ 40 chars):")
        return ASK_CUSTOM_NATURE
    ctx.user_data["nature"] = Nature[key].value
    await q.callback_query.edit_message_text("Describe your doubt (text or photo).")
    return ASK_TEXT

async def custom_nature(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["nature"] = upd.message.text[:40]
    await upd.message.reply_text("Describe your doubt (text or photo).")
    return ASK_TEXT

# Receive text / media
async def receive_text(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["text"] = upd.message.text_markdown_v2 or ""
    await upd.message.reply_text("You may now *attach one photo* or tap ✓ Done.",
                                 reply_markup=InlineKeyboardMarkup(
                                     [[InlineKeyboardButton("✓ Done", callback_data="confirm")]]),
                                 parse_mode="Markdown")
    return ASK_MEDIA

async def receive_photo(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["photo"] = upd.message.photo[-1].file_id
    await upd.message.reply_text("Photo received.\nTap ✓ Done.",
                                 reply_markup=InlineKeyboardMarkup(
                                     [[InlineKeyboardButton("✓ Done", callback_data="confirm")]]))
    return ASK_MEDIA

async def confirm(q: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await q.callback_query.answer()
    data   = ctx.user_data
    doubt  = Doubt(
        user_id=q.from_user.id,
        subject=data["subj"],
        nature=data["nature"],
        text=data.get("text",""),
        photo_file_id=data.get("photo"),
        is_public=False,
        created_at=dt.datetime.utcnow()
    )
    did = await _store_doubt(doubt)
    _inc_quota(q.from_user.id, public=False)

    await q.callback_query.edit_message_text(
        f"✅ Doubt saved (ID #{did}). You’ll receive a reply soon!"
    )
    # notify admin
    await ctx.application.bot.send_message(
        chat_id=ctx.bot_data["ADMIN_ID"],
        text=(
            f"🆕 *Private doubt* #{did} from [{q.from_user.first_name}](tg://user?id={q.from_user.id})\n"
            f"*Subject:* {doubt.subject}\n*Nature:* {doubt.nature}\n"
            f"{doubt.text or '_no text_'}"
        ),
        parse_mode="Markdown",
    )
    if doubt.photo_file_id:
        await ctx.application.bot.send_photo(
            chat_id=ctx.bot_data["ADMIN_ID"],
            photo=doubt.photo_file_id,
            caption=f"(photo for doubt #{did})"
        )
    ctx.user_data.clear()
    return ConversationHandler.END

# ─── Registration helper ───────────────────────────────────
def register_handlers(app: Application):
    app.bot_data["ADMIN_ID"] = int(app.bot_data.get("ADMIN_ID", 0))  # ensure present

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:         [CallbackQueryHandler(subj_chosen,  pattern=r"^subj\|")],
            ASK_CUSTOM_SUBJ:  [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subj)],
            ASK_NATURE:       [CallbackQueryHandler(nat_chosen,   pattern=r"^nat\|")],
            ASK_CUSTOM_NATURE:[MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nature)],
            ASK_TEXT:         [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text),
                               MessageHandler(filters.PHOTO, receive_photo)],
            ASK_MEDIA:        [CallbackQueryHandler(confirm, pattern="^confirm$"),
                               MessageHandler(filters.PHOTO, receive_photo)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)],
        per_user=True,
        allow_reentry=True,
    )
    app.add_handler(conv)
