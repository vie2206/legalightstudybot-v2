# doubts.py
"""
Ask-a-doubt flow with daily quota
────────────────────────────────
/doubt  → category → nature → (text or 1 photo/pdf)   → stored & forwarded
Admin answers via inline-buttons (public or private).

Quota: 2 public + 3 private answers per user per day.
"""

import asyncio, datetime as dt, enum, io, os, textwrap
from typing import Dict, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    InputFile,
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

# ─────────── categories & nature enums ───────────
class Subject(enum.StrEnum):
    ENGLISH       = "English & RC"
    LEGAL         = "Legal Reasoning"
    LOGICAL       = "Logical Reasoning"
    MATHS         = "Maths"
    GK_CA         = "GK / CA"
    MOCK          = "Mock Test"
    SECTIONAL     = "Sectional Test"
    STRATEGY      = "Strategy / Time-Mgmt"
    COLLEGE_APP   = "Application / College"
    OTHER         = "Other / Custom"

class Nature(enum.StrEnum):
    CANT_SOLVE        = "Can’t solve a question"
    DONT_UNDERSTAND   = "Don’t understand official answer"
    EXPL_WRONG        = "Explain my wrong answer"
    CONCEPT           = "Concept clarification"
    ALT_METHOD        = "Need alternative method"
    SOURCE_REQ        = "Source / reference request"
    TIME_MGMT         = "Time-management advice"
    TEST_STRAT        = "Test-taking strategy"
    OTHER             = "Other / Custom"

# ─────────── conversation states ───────────
CHOOSING_SUBJ, CHOOSING_NATURE, TYPING_CUSTOM_SUBJ, TYPING_CUSTOM_NATURE, \
WAITING_QUESTION = range(5)

# ─────────── quota helper ───────────
DAY = dt.timedelta(days=1)

async def _check_quota(user_id: int, public: bool = False) -> Optional[str]:
    today = dt.date.today()
    with session_scope() as s:
        quota = s.get(DoubtQuota, user_id)
        if not quota:
            quota = DoubtQuota(user_id=user_id, date=today, public_count=0,
                               private_count=0, last_reset=today)
            s.add(quota)
            s.commit()

        # reset at new day
        if quota.date != today:
            quota.date = today
            quota.public_count = quota.private_count = 0
            s.commit()

        if public and quota.public_count >= 2:
            return "🚫 Daily public-answer quota (2) reached."
        if not public and quota.private_count >= 3:
            return "🚫 Daily private-answer quota (3) reached."

        # increment
        if public:
            quota.public_count += 1
        else:
            quota.private_count += 1
        s.commit()
    return None

# ─────────── /doubt entry ───────────
async def cmd_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    err = await _check_quota(update.effective_user.id, public=False)
    if err:
        return await update.message.reply_text(err) or ConversationHandler.END

    kb = [[InlineKeyboardButton(v, callback_data=f"s|{k.name}")]
          for k, v in Subject.__members__.items()]
    await update.message.reply_text(
        "Select *subject* of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return CHOOSING_SUBJ

# subject chosen → nature
async def subj_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    _, subj_key = q.data.split("|")
    if subj_key == Subject.OTHER.name:
        await q.edit_message_text("Type custom *subject* (≤30 chars):",
                                  parse_mode="Markdown")
        return TYPING_CUSTOM_SUBJ
    context.user_data["subj"] = Subject[subj_key].value
    return await _ask_nature(q)

async def save_custom_subj(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subj"] = update.message.text.strip()[:30]
    return await _ask_nature(update.message)

async def _ask_nature(msg_or_q):
    kb = [[InlineKeyboardButton(v.value, callback_data=f"n|{v.name}")]
          for v in Nature]
    await msg_or_q.edit_message_text(
        "Select *nature* of doubt:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb))
    return CHOOSING_NATURE

# nature chosen
async def nature_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    _, n_key = q.data.split("|")
    if n_key == Nature.OTHER.name:
        await q.edit_message_text("Type custom *nature* (≤30 chars):",
                                  parse_mode="Markdown")
        return TYPING_CUSTOM_NATURE
    context.user_data["nature"] = Nature[n_key].value
    return await _ask_question(q)

async def save_custom_nature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nature"] = update.message.text.strip()[:30]
    return await _ask_question(update.message)

async def _ask_question(msg_or_q):
    txt = ("Send your *question* now (text **or** 1 photo/PDF).\n"
           "When you’re done, I’ll forward it to the mentor.")
    await msg_or_q.edit_message_text(txt, parse_mode="Markdown")
    return WAITING_QUESTION

# capture question
async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user  = update.effective_user
    chat  = update.effective_chat

    subj   = context.user_data["subj"]
    nature = context.user_data["nature"]

    # build display text
    header = f"🆕 *Doubt from* [{user.full_name}](tg://user?id={user.id})\n" \
             f"*Subject:* {subj}\n*Nature:* {nature}"
    if update.message.text:
        text = f"{header}\n\n{update.message.text}"
        media = None
    else:
        text = header
        media = update.message.photo[-1] if update.message.photo else update.message.document

    # store DB
    with session_scope() as s:
        d = Doubt(
            user_id=user.id,
            subject=subj,
            nature=nature,
            text=update.message.text_html if update.message.text else "",
            file_id=media.file_id if media else None,
            file_unique_id=media.file_unique_id if media else None,
            date=dt.datetime.utcnow(),
        )
        s.add(d); s.commit()
        doubt_id = d.id

    # forward to admin
    admin_txt = textwrap.dedent(f"""
        {text}
        
        ID: `{doubt_id}`
    """)
    if media:
        await context.bot.send_photo(
            chat_id=context.bot_data["ADMIN_ID"],
            photo=media.file_id,
            caption=admin_txt,
            parse_mode="Markdown",
            reply_markup=_answer_kb(doubt_id),
        )
    else:
        await context.bot.send_message(
            chat_id=context.bot_data["ADMIN_ID"],
            text=admin_txt,
            parse_mode="Markdown",
            reply_markup=_answer_kb(doubt_id),
        )

    await update.message.reply_text(
        "✅ Your doubt was sent!  You’ll receive the answer soon."
    )
    return ConversationHandler.END

def _answer_kb(did: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Reply privately",   callback_data=f"ans|{did}|0"),
            InlineKeyboardButton("Reply publicly",    callback_data=f"ans|{did}|1"),
        ]
    ])

# admin presses answer button
async def admin_answer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, did, is_public = q.data.split("|")
    context.user_data["ans_did"] = int(did)
    context.user_data["ans_pub"] = bool(int(is_public))
    await q.edit_message_text("Send your answer (text *or* 1 photo/PDF):",
                              parse_mode="Markdown")
    return WAITING_QUESTION  # reuse same state to capture answer

# capture admin answer
async def receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    did   = context.user_data.pop("ans_did")
    pub   = context.user_data.pop("ans_pub")
    with session_scope() as s:
        d: Doubt = s.get(Doubt, did)
        if not d:  # should not happen
            await update.message.reply_text("Doubt not found.")
            return ConversationHandler.END
        # send to the student
        txt = f"📝 *Answer to your doubt*\n\n{update.message.text or ''}"
        media = update.message.photo[-1] if update.message.photo else update.message.document
        if media:
            await update.message.bot.send_photo(d.user_id, media.file_id,
                                                caption=txt, parse_mode="Markdown")
        else:
            await update.message.bot.send_message(d.user_id, txt,
                                                  parse_mode="Markdown")

        if pub:
            # post publicly (same format)
            pub_txt = f"❓ *Q:* {d.text}\n\n💡 *A:* {update.message.text or ''}"
            await update.message.bot.send_message(
                update.effective_chat.id, pub_txt, parse_mode="Markdown"
            )

    await update.message.reply_text("Answer delivered ✔")
    return ConversationHandler.END

# ─────────── registration ───────────
def register_handlers(app: Application):
    # store admin id in bot_data so we can reuse inside functions
    app.bot_data["ADMIN_ID"] = ADMIN_ID = 803299591

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            CHOOSING_SUBJ: [
                CallbackQueryHandler(subj_chosen, pattern=r"^s\|"),
            ],
            TYPING_CUSTOM_SUBJ: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                               save_custom_subj)],
            CHOOSING_NATURE: [
                CallbackQueryHandler(nature_chosen, pattern=r"^n\|"),
            ],
            TYPING_CUSTOM_NATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                  save_custom_nature)],
            WAITING_QUESTION: [
                MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT,
                               receive_question)
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_chat=True,
    )
    app.add_handler(conv)

    # admin answer flow
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$")],
        states={
            WAITING_QUESTION: [
                MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT,
                               receive_answer)
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_chat=False,
    )
    app.add_handler(admin_conv)
