# doubts.py
"""
Student doubt-submission feature.

Flow
----
/doubt
  → choose Subject   (inline keyboard)
  → choose Nature    (inline keyboard)
  → send text / photo
  → "✓ Done" button (optional photo attach)
Admin receives a private copy with “Answer Public / Private” buttons.
"""

import enum, datetime as dt
from pathlib import Path
from telegram import (
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as Markup,
    Update,
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
from database import session_scope, Doubt, DoubtQuota

# ──────────────────────────────────────────────────────────────
# Enumerations -------------------------------------------------
class Subject(enum.Enum):
    ENGLISH    = "English & RC"
    LEGAL      = "Legal Reasoning"
    LOGICAL    = "Logical Reasoning"
    MATHS      = "Mathematics"
    GKCA       = "GK / CA"
    MOCK       = "Mock Test"
    SECTIONAL  = "Sectional Test"
    STRATEGY   = "Strategy / Time-Mgmt"
    APPLN      = "Application / College"
    OTHER      = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE       = "Can’t solve a question"
    DONT_UNDERSTAND  = "Don’t understand official answer"
    EXPLAIN_WRONG    = "Explain my wrong answer"
    CONCEPT          = "Concept clarification"
    ALT_METHOD       = "Need alternative method"
    SOURCE_REQ       = "Source / reference request"
    TIME_MGMT        = "Time-management advice"
    STRATEGY         = "Test-taking strategy"
    OTHER            = "Other / Custom"

# ──────────────────────────────────────────────────────────────
# Conversation states -----------------------------------------
CHO_SUBJ, CHO_NATURE, ASK_TEXT, ASK_PHOTO, CONFIRM = range(5)

# ──────────────────────────────────────────────────────────────
# Helpers ------------------------------------------------------
def _kb_from_enum(enum_cls, prefix: str):
    """Return 2-column inline-keyboard from an Enum."""
    buttons = [Btn(m.value, callback_data=f"{prefix}|{m.name}") for m in enum_cls]
    # split into rows of 2
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return Markup(rows)

async def _check_quota(uid: int, public: bool):
    """Return None if quota ok, else err-msg string."""
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, today))
        if not q:
            q = DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            s.add(q)
            s.commit()
        limit = 2 if public else 3
        used  = q.public_count if public else q.private_count
        if used >= limit:
            return f"You’ve reached today’s quota of {limit} {'public' if public else 'private'} doubts."
        # reserve a slot now to avoid race
        if public:   q.public_count  += 1
        else:        q.private_count += 1
        s.commit()

# ──────────────────────────────────────────────────────────────
# Conversation step funcs -------------------------------------
async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(update.effective_user.id, public=False)
    if err:
        return await update.message.reply_text(err)
    await update.message.reply_text(
        "Choose *subject*:", parse_mode="Markdown",
        reply_markup=_kb_from_enum(Subject, "subj")
    )
    return CHO_SUBJ

async def subj_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, key = q.data.split("|")
    ctx.user_data["subj"] = Subject[key]
    await q.edit_message_text(
        "Choose *nature* of doubt:", parse_mode="Markdown",
        reply_markup=_kb_from_enum(Nature, "nat")
    )
    return CHO_NATURE

async def nature_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, key = q.data.split("|")
    ctx.user_data["nature"] = Nature[key]
    await q.edit_message_text("Describe your *doubt* (text or photo).", parse_mode="Markdown")
    return ASK_TEXT

async def got_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["text"] = update.message.text_html or ""
    await update.message.reply_text(
        "You may now *attach one photo* or tap ✓ Done.", parse_mode="Markdown",
        reply_markup=Markup([[Btn("✓ Done", callback_data="done")]])
    )
    return ASK_PHOTO

async def got_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("✓ Photo saved. Tap *Done* to submit.", parse_mode="Markdown",
                                    reply_markup=Markup([[Btn("✓ Done", callback_data="done")]]))
    return CONFIRM

async def confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query              # <-- FIXED LINE
    await q.answer()
    user = q.from_user
    data = ctx.user_data
    # store in DB -------------------------------------------------
    with session_scope() as s:
        d = Doubt(
            user_id=user.id,
            subject=data["subj"].value,
            nature=data["nature"].value,
            text=data.get("text", ""),
            photo_file_id=data.get("photo"),
            timestamp=dt.datetime.utcnow(),
        )
        s.add(d); s.commit()
        doubt_id = d.id
    # send admin copy --------------------------------------------
    msg_lines = [
        f"🆕 *Doubt #{doubt_id}*",
        f"👤 {user.mention_html()}",
        f"📚 <b>{data['subj'].value}</b> – {data['nature'].value}",
        f"〰️ {data.get('text','(photo only)')}",
    ]
    admin_kb = Markup([
        [Btn("Public 📢", callback_data=f"ans|{doubt_id}|1"),
         Btn("Private 🔒",callback_data=f"ans|{doubt_id}|0")]
    ])
    sent = await ctx.bot.send_message(ctx.application.bot_data["ADMIN_ID"],
                                      "\n".join(msg_lines), parse_mode="HTML",
                                      reply_markup=admin_kb)
    if fid := data.get("photo"):
        await ctx.bot.send_photo(ctx.application.bot_data["ADMIN_ID"], fid,
                                 reply_to_message_id=sent.message_id)
    # user confirmation ------------------------------------------
    await q.edit_message_text("✅ Doubt submitted! You’ll get a reply soon.")
    ctx.user_data.clear()
    return ConversationHandler.END

# Admin answer callback ----------------------------------------
async def admin_answer_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, did, is_pub = q.data.split("|")
    await q.message.reply_text("Send your answer (text / voice / photo).")
    ctx.user_data["ans_for"] = (int(did), bool(int(is_pub)))

async def admin_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did, is_pub = ctx.user_data.get("ans_for", (None, None))
    if did is None:
        return
    # fetch original question
    with session_scope() as s:
        d = s.get(Doubt, did)
    # build answer
    header = f"📝 *Answer to doubt #{did}*\n" \
             f"📚 <b>{d.subject}</b> – {d.nature}"
    if is_pub:
        chat = ctx.application.bot_data["PUBLIC_CHAT_ID"]
    else:
        chat = d.user_id
    if update.message.text:
        await ctx.bot.send_message(chat, header + "\n\n" + update.message.text_html,
                                   parse_mode="HTML")
    elif update.message.photo:
        fid = update.message.photo[-1].file_id
        await ctx.bot.send_photo(chat, fid, caption=header, parse_mode="HTML")
    ctx.user_data.clear()

# ──────────────────────────────────────────────────────────────
def register_handlers(app: Application):
    app.bot_data["ADMIN_ID"]      = int(app.bot_data.get("ADMIN_ID", 0))
    app.bot_data["PUBLIC_CHAT_ID"] = int(app.bot_data.get("PUBLIC_CHAT_ID", 0))

    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            CHO_SUBJ:      [CallbackQueryHandler(subj_chosen,   r"^subj\|")],
            CHO_NATURE:    [CallbackQueryHandler(nature_chosen, r"^nat\|")],
            ASK_TEXT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, got_text)],
            ASK_PHOTO: [
                MessageHandler(filters.PHOTO, got_photo),
                CallbackQueryHandler(confirm, pattern="^done$")
            ],
            CONFIRM:       [CallbackQueryHandler(confirm, pattern="^done$")]
        },
        fallbacks=[],
        per_chat=True,
    )
    app.add_handler(conv)

    # Admin handlers
    app.add_handler(CallbackQueryHandler(admin_answer_cb, pattern=r"^ans\|\d+\|[01]$"))
    app.add_handler(MessageHandler(filters.ALL & filters.User(app.bot_data["ADMIN_ID"]),
                                   admin_media))
