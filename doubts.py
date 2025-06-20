# doubts.py
"""
Ask-a-Doubt system.

Flow
====
/doubt  ─►  SUBJECT menu  ─►  Nature menu  ─►  ask for text *or* 1 photo
          (custom subject)    (custom nature)

Tables (see database.py)
------------------------
•  doubts        – full record of every doubt (subject, nature, text, photo_id …)
•  doubt_quotas  – per-user daily quota (2 public + 3 private answers default)

Quota rules
-----------
•  max 3 private   + 2 public doubts per rolling 24 h
"""

import asyncio, datetime as dt, io
from enum import Enum
from typing import Dict, Tuple, Optional

from telegram import (
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup,
    Update,
    InputFile,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from sqlalchemy import select, func

from database import session_scope, Doubt, DoubtQuota

# ────────────────────────────────────────────────────────────
# Conversation states
(CHOOSE_SUBJ, CUSTOM_SUBJ,
 CHOOSE_NAT,  CUSTOM_NAT,
 AWAIT_CONTENT) = range(5)

# ────────────────────────────────────────────────────────────
# Enumerations
class Subject(str, Enum):
    ENGLISH      = "English & RC"
    LEGAL        = "Legal Reasoning"
    LOGICAL      = "Logical Reasoning"
    MATHS        = "Maths"
    GK_CA        = "GK / CA"
    MOCK         = "Mock Test"
    SECTIONAL    = "Sectional Test"
    STRATEGY     = "Strategy / Time-Mgmt"
    APPLICATION  = "Application / College"
    OTHER        = "Other / Custom"

class Nature(str, Enum):
    CANT_SOLVE      = "Can’t solve a question"
    NO_ANS          = "Don’t understand the official answer"
    EXPLAIN_WRONG   = "Explain my wrong answer"
    CONCEPT         = "Concept clarification"
    ALT_METHOD      = "Need alternative method"
    SOURCE_REQ      = "Source / reference request"
    TIME_ADVICE     = "Time-management advice"
    STRAT_ADVICE    = "Test-taking strategy"
    OTHER           = "Other / Custom"

SUBJECT_ORDER = list(Subject)
NATURE_ORDER  = list(Nature)

# ────────────────────────────────────────────────────────────
#  Helpers
def _kb_from_enum(enum_list, prefix):
    """Return inline-keyboard rows of ≤ 2 buttons each."""
    rows, row = [], []
    for i, item in enumerate(enum_list, 1):
        row.append(Btn(item.value, callback_data=f"{prefix}|{item.name}"))
        if len(row) == 2 or i == len(enum_list):
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(rows)

def _today():
    return dt.datetime.utcnow()

async def _check_quota(user_id: int) -> Optional[str]:
    """Return None if okay, else error string."""
    now  = _today()
    day_ago = now - dt.timedelta(days=1)
    with session_scope() as s:
        quota = s.get(DoubtQuota, user_id) or DoubtQuota(user_id=user_id)
        # reset window if older than 24 h
        if quota.last_reset is None or quota.last_reset < day_ago:
            quota.pub_used = quota.priv_used = 0
            quota.last_reset = now
            s.add(quota); s.commit()
        if quota.pub_used >= quota.pub_limit and quota.priv_used >= quota.priv_limit:
            return "❌ Daily doubt quota exhausted. Upgrade to submit more."
    return None

# ────────────────────────────────────────────────────────────
#  Conversation handlers
async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(update.effective_user.id)
    if err:
        return await update.message.reply_text(err)

    await update.message.reply_text(
        "📚 Select *subject* of your doubt:",
        reply_markup=_kb_from_enum(SUBJECT_ORDER, "S"),
        parse_mode="Markdown",
    )
    return CHOOSE_SUBJ

async def subject_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, subj_raw = q.data.split("|")
    if subj_raw == Subject.OTHER.name:
        await q.edit_message_text("Custom subject (≤ 30 chars):")
        return CUSTOM_SUBJ
    ctx.user_data["subject"] = Subject[subj_raw].value
    await q.edit_message_text(
        "📌 Select *nature* of the doubt:",
        reply_markup=_kb_from_enum(NATURE_ORDER, "N"),
        parse_mode="Markdown",
    )
    return CHOOSE_NAT

async def custom_subject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"] = update.message.text.strip()[:30]
    await update.message.reply_text(
        "📌 Select *nature* of the doubt:",
        reply_markup=_kb_from_enum(NATURE_ORDER, "N"),
        parse_mode="Markdown",
    )
    return CHOOSE_NAT

async def nature_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, raw = q.data.split("|")
    if raw == Nature.OTHER.name:
        await q.edit_message_text("Custom nature (≤ 30 chars):")
        return CUSTOM_NAT
    ctx.user_data["nature"] = Nature[raw].value
    await q.edit_message_text("✏️ Send your question (text *or* 1 photo):")
    return AWAIT_CONTENT

async def custom_nature(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"] = update.message.text.strip()[:30]
    await update.message.reply_text("✏️ Send your question (text *or* 1 photo):")
    return AWAIT_CONTENT

async def receive_content(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Accept either text or exactly 1 photo."""
    uid   = update.effective_user.id
    cid   = update.effective_chat.id
    media = None
    text  = None

    if update.message.photo:
        media = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        text = caption.strip() or None
    else:
        text = update.message.text_markdown_urled

    if not media and not text:
        return await update.message.reply_text("❌ Need text or a single photo.")

    # check quota again (edge case)
    err = await _check_quota(uid)
    if err: return await update.message.reply_text(err)

    # store in DB
    with session_scope() as s:
        dq = s.get(DoubtQuota, uid)
        is_public = True   # default for now – you could add /doubt_private later
        if is_public:
            dq.pub_used += 1
        else:
            dq.priv_used += 1
        d = Doubt(
            user_id=uid,
            created=_today(),
            subject=ctx.user_data["subject"],
            nature=ctx.user_data["nature"],
            text=text,
            photo_id=media,
            public=is_public,
        )
        s.add_all([dq, d]); s.commit()
        doubt_id = d.id

    await update.message.reply_text("✅ Doubt received! You’ll get a reply soon.")
    # notify admin
    admin_msg = (
        f"🆕 *Doubt #{doubt_id}*\n"
        f"👤 {uid}\n"
        f"🏷 *{d.subject}*  |  *{d.nature}*\n"
        f"—" * 10
    )
    if media:
        await ctx.bot.send_photo(
            ctx.bot_data["ADMIN_ID"],
            media,
            caption=f"{admin_msg}\n{text or '_no caption_'}",
            parse_mode="Markdown",
        )
    else:
        await ctx.bot.send_message(
            ctx.bot_data["ADMIN_ID"],
            f"{admin_msg}\n{text}",
            parse_mode="Markdown",
        )
    return ConversationHandler.END

async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# ────────────────────────────────────────────────────────────
def register_handlers(app: Application, admin_id: int):
    # keep admin_id in bot_data for quick access
    app.bot_data["ADMIN_ID"] = admin_id

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            CHOOSE_SUBJ:  [CallbackQueryHandler(subject_chosen,  pattern=r"^S\|")],
            CUSTOM_SUBJ:  [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subject)],
            CHOOSE_NAT:   [CallbackQueryHandler(nature_chosen,   pattern=r"^N\|")],
            CUSTOM_NAT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nature)],
            AWAIT_CONTENT:[MessageHandler(~filters.COMMAND, receive_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)
