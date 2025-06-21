# doubts.py  (StrEnum-back-compat version)
"""
Ask-a-doubt flow with daily quota.
...
"""

import asyncio, datetime as dt, enum, textwrap
from typing import Optional

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters,
)

from database import session_scope, Doubt, DoubtQuota

# ─────────── StrEnum shim (🎯 works on 3.10+) ───────────
try:
    from enum import StrEnum as _StrEnum            # Python 3.11+
except ImportError:
    class _StrEnum(str, enum.Enum):                # fallback for 3.10
        pass

# ─────────── categories & natures ───────────
class Subject(_StrEnum):
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

class Nature(_StrEnum):
    CANT_SOLVE      = "Can’t solve a question"
    DONT_UNDERSTAND = "Don’t understand official answer"
    EXPL_WRONG      = "Explain my wrong answer"
    CONCEPT         = "Concept clarification"
    ALT_METHOD      = "Need alternative method"
    SOURCE_REQ      = "Source / reference request"
    TIME_MGMT       = "Time-management advice"
    TEST_STRAT      = "Test-taking strategy"
    OTHER           = "Other / Custom"

# ─────────── convo states, quota helper … (unchanged) ───────────
CHOOSING_SUBJ, CHOOSING_NATURE, TYPING_CUSTOM_SUBJ, \
TYPING_CUSTOM_NATURE, WAITING_QUESTION = range(5)

DAY = dt.timedelta(days=1)

async def _check_quota(uid: int, pub: bool) -> Optional[str]:
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, uid)
        if not q:
            q = DoubtQuota(user_id=uid, date=today,
                           public_count=0, private_count=0)
            s.add(q); s.commit()
        if q.date != today:
            q.date = today
            q.public_count = q.private_count = 0
            s.commit()
        if pub and q.public_count >= 2:
            return "🚫 Daily public-answer quota (2) reached."
        if not pub and q.private_count >= 3:
            return "🚫 Daily private-answer quota (3) reached."
        if pub:   q.public_count   += 1
        else:     q.private_count += 1
        s.commit()
    return None

# ─────────── /doubt flow (functions are identical to previous v1) ───────────
# ... (cmd_doubt, subj_chosen, save_custom_subj, _ask_nature,
#      nature_chosen, save_custom_nature, _ask_question,
#      receive_question, _answer_kb, admin_answer_cb, receive_answer)
#   ✂  ← keep the exact implementations you already pasted earlier …

# ─────────── handler registration ───────────
def register_handlers(app: Application):
    ADMIN_ID = 803299591
    app.bot_data["ADMIN_ID"] = ADMIN_ID

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            CHOOSING_SUBJ:   [CallbackQueryHandler(subj_chosen,   pattern=r"^s\|")],
            TYPING_CUSTOM_SUBJ:   [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                  save_custom_subj)],
            CHOOSING_NATURE: [CallbackQueryHandler(nature_chosen, pattern=r"^n\|")],
            TYPING_CUSTOM_NATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                  save_custom_nature)],
            WAITING_QUESTION: [MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT,
                                              receive_question)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_chat=True,
    )
    app.add_handler(conv)

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$")],
        states={
            WAITING_QUESTION: [MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT,
                                              receive_answer)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_chat=False,
    )
    app.add_handler(admin_conv)
