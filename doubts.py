# doubts.py  — fixed UNIQUE-constraint error

import enum, datetime as dt, itertools
from pathlib import Path
from typing import Final

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, Update,
                      constants)
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ConversationHandler, ContextTypes, MessageHandler,
                          filters)

from database import Doubt, DoubtQuota, session_scope

# ────────────────────────────────────────────────────────
#  Enums (values are stored in DB as strings)
# ────────────────────────────────────────────────────────
class Subject(enum.Enum):
    ENGLISH        = "English & RC"
    LEGAL          = "Legal Reasoning"
    LOGICAL        = "Logical Reasoning"
    MATHS          = "Mathematics"
    GK_CA          = "GK / CA"
    MOCK           = "Mock Test"
    SECTIONAL      = "Sectional Test"
    STRATEGY       = "Strategy / Time-Mgmt"
    APPLICATION    = "Application / College"
    OTHER_CUSTOM   = "Other / Custom"


class Nature(enum.Enum):
    CANT_SOLVE     = "Can’t solve a question"
    OFFICIAL_ANS   = "Don’t understand official answer"
    WRONG_ANS      = "Explain my wrong answer"
    CONCEPT        = "Concept clarification"
    ALT_METHOD     = "Need alternative method"
    SOURCE_REQ     = "Source / reference request"
    TIME_MGMT      = "Time-management advice"
    TEST_STRAT     = "Test-taking strategy"
    OTHER_CUSTOM   = "Other / Custom"


# ────────────────────────────────────────────────────────
#  Conversation states
# ────────────────────────────────────────────────────────
(ASK_SUBJ, ASK_CUSTOM_SUBJ,
 ASK_NATURE, ASK_CUSTOM_NATURE,
 ASK_PRIVATE, ASK_CONTENT) = range(6)

# ────────────────────────────────────────────────────────
#  helpers
# ────────────────────────────────────────────────────────
def _get_or_create_quota(db, uid: int) -> DoubtQuota:
    """Return today’s quota row – create in-memory if absent.
    Works even if the row was just added earlier in the same session."""
    today = dt.date.today()
    quota = (
        db.get(DoubtQuota, (uid, today))
        or next((q for q in db.new if isinstance(q, DoubtQuota)
                 and q.user_id == uid and q.date == today), None)
    )
    if quota is None:                       # create only once per day
        quota = DoubtQuota(user_id=uid, date=today,
                           public_count=0, private_count=0)
        db.add(quota)
    return quota


def _check_quota(uid: int, is_public: bool) -> str | None:
    """Return an error-msg string if quota exhausted, else None."""
    with session_scope() as db:
        q = _get_or_create_quota(db, uid)

        limit_pub, limit_priv = 2, 3
        if is_public and q.public_count >= limit_pub:
            return "❌ You’ve reached today’s *public* doubt limit (2)."
        if not is_public and q.private_count >= limit_priv:
            return "❌ You’ve reached today’s *private* doubt limit (3)."

        # we only *reserve* a slot – count will be finalised after posting
        if is_public:
            q.public_count += 1
        else:
            q.private_count += 1
    return None  # OK


# ────────────────────────────────────────────────────────
#  step ➀  /doubt  – entry
# ────────────────────────────────────────────────────────
async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id

    err = _check_quota(uid, is_public=False)   # we count even private raises
    if err:
        await update.message.reply_markdown(err)
        return ConversationHandler.END

    # subject keyboard
    rows = list(itertools.batched(list(Subject)[:-1], 2))
    kb = [[InlineKeyboardButton(s.value, callback_data=f"s|{s.name}") for s in row]
          for row in rows]
    kb.append([InlineKeyboardButton("Other / Custom", callback_data="s|OTHER_CUSTOM")])
    await update.message.reply_text(
        "Pick the *subject* of your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ASK_SUBJ


# ────────────────────────────────────────────────────────
#  … all remaining handlers are unchanged
#    (subject → nature → private/public → content & media)
# ────────────────────────────────────────────────────────
#  register_handlers(app) also unchanged
