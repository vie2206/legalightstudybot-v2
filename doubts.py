# doubts.py  – 2025-06-21 fix “single-tick” bug

import enum, datetime as dt
from io import BytesIO
from typing import Final

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    Update, InputFile, constants,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters,
)

from database import session_scope, Doubt, DoubtQuota   # re-exports
ADMIN_ID: Final = 803299591            # your Telegram numeric user-id

# ─────────────────────────  ENUMS  ──────────────────────────
class Subject(enum.Enum):
    ENGLISH   = "English & RC"
    LEGAL     = "Legal Reasoning"
    LOGICAL   = "Logical Reasoning"
    MATHS     = "Maths"
    GKCA      = "GK / CA"
    MOCK      = "Mock Test"
    SECTIONAL = "Sectional Test"
    STRAT     = "Strategy / Time-Mgmt"
    APPL      = "Application / College"
    OTHER     = "Other / Custom"

class Nature(enum.Enum):
    CANT_SOLVE   = "Can’t solve"
    OFFICIAL_ANS = "Don’t understand official answer"
    WRONG_ANS    = "Explain my wrong answer"
    CONCEPT      = "Concept clarification"
    ALT_METHOD   = "Need alternative method"
    SOURCE       = "Source / reference"
    TIME_MGMT    = "Time-management advice"
    TEST_STRAT   = "Test-taking strategy"
    OTHER        = "Other / Custom"

# ───────────── conversation states ─────────────
ASK_SUBJ, ASK_NATURE, ASK_CUSTOM_SUBJ, ASK_CUSTOM_NATURE, ASK_QUESTION = range(5)

# ───────────── helpers ─────────────
DAILY_PUB, DAILY_PRI = 2, 3

async def _check_quota(uid: int, publ: bool) -> str|None:
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, today))
        if not q:
            q = DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            s.add(q)
        if publ and q.public_count >= DAILY_PUB:
            return f"You’ve reached the daily *public* quota ({DAILY_PUB})."
        if not publ and q.private_count >= DAILY_PRI:
            return f"You’ve reached the daily *private* quota ({DAILY_PRI})."
        if publ:
            q.public_count += 1
        else:
            q.private_count += 1
    return None

def _kb_from_enum(EnumCls, prefix: str):
    rows, row = [], []
    for e in EnumCls:
        row.append(InlineKeyboardButton(e.value, callback_data=f"{prefix}|{e.name}"))
        if len(row) == 2:
            rows.append(row); row=[]
    if row: rows.append(row)
    return InlineKeyboardMarkup(rows)

# ───────────── handlers ─────────────
async def cmd_doubt(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(u.effective_user.id, publ=False)
    if err: return await u.message.reply_markdown(f"❌ {err}")
    ctx.user_data.clear()
    await u.message.reply_text("Select *Subject*:", parse_mode="Markdown",
                               reply_markup=_kb_from_enum(Subject, "SUBJ"))
    return ASK_SUBJ

async def subj_chosen(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer()
    key = q.data.split("|",1)[1]
    if key=="OTHER":
        await q.edit_message_text("Enter custom subject (≤30 chars):")
        return ASK_CUSTOM_SUBJ
    ctx.user_data["subject"]=key
    await q.edit_message_text("Select *Nature* of doubt:",
                              parse_mode="Markdown",
                              reply_markup=_kb_from_enum(Nature,"NAT"))
    return ASK_NATURE

async def custom_subj(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subject"]="CUSTOM:"+u.message.text[:30]
    await u.message.reply_text("Select *Nature* of doubt:",
                               parse_mode="Markdown",
                               reply_markup=_kb_from_enum(Nature,"NAT"))
    return ASK_NATURE

async def nature_chosen(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=u.callback_query;await q.answer()
    key=q.data.split("|",1)[1]
    if key=="OTHER":
        await q.edit_message_text("Enter custom nature (≤30 chars):")
        return ASK_CUSTOM_NATURE
    ctx.user_data["nature"]=key
    await q.edit_message_text("Send your question (text or a single photo).")
    return ASK_QUESTION

async def custom_nat(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"]="CUSTOM:"+u.message.text[:30]
    await u.message.reply_text("Send your question (text or a single photo).")
    return ASK_QUESTION

async def receive_q(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    err = await _check_quota(uid, publ=False)
    if err: return await u.message.reply_markdown(f"❌ {err}")
    sd  = ctx.user_data
    subj = sd["subject"]; nature=sd["nature"]
    # save in DB
    with session_scope() as s:
        d=Doubt(user_id=uid, subject=subj, nature=nature,
                question_text=u.message.text or "",
                question_file_id=u.message.photo[-1].file_id if u.message.photo else None,
                timestamp=dt.datetime.utcnow())
        s.add(d)
        s.flush()           # obtain id
        doubt_id=d.id
    # confirmation to student
    await u.message.reply_markdown(
        "✅ *Doubt received!* I’ll get back to you soon.")
    # forward to admin
    caption = (f"*#{doubt_id}* • *{Subject[subj.split(':',1)[0]].value if subj.startswith('CUSTOM')==False else subj[7:]}*\n"
               f"_{Nature[nature.split(':',1)[0]].value if nature.startswith('CUSTOM')==False else nature[7:]}_\n"
               f"from [{u.effective_user.full_name}](tg://user?id={uid})")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Answer Privately", callback_data=f"ANS|{doubt_id}|0"),
        InlineKeyboardButton("Answer Publicly", callback_data=f"ANS|{doubt_id}|1")
    ]])
    if u.message.photo:
        fid=u.message.photo[-1].file_id
        await ctx.bot.send_photo(ADMIN_ID, fid, caption=caption,
                                 parse_mode="Markdown", reply_markup=kb)
    else:
        await ctx.bot.send_message(ADMIN_ID, caption, parse_mode="Markdown",
                                   reply_markup=kb)
    return ConversationHandler.END

# admin answer
async def admin_cb(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=u.callback_query; await q.answer()
    doubt_id, public=int(q.data.split("|")[1]), int(q.data[-1])
    ctx.user_data["ans_public"]=bool(public)
    ctx.user_data["ans_did"]=doubt_id
    await q.message.reply_text("Send your answer (text / photo).")

async def admin_answer(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did=ctx.user_data.get("ans_did"); publ=ctx.user_data.get("ans_public")
    if not did: return
    with session_scope() as s:
        d=s.get(Doubt,did)
        if not d: return await u.message.reply_text("Record missing.")
        d.answer_text=u.message.text or ""
        d.answer_file_id=u.message.photo[-1].file_id if u.message.photo else None
        d.answered_at=dt.datetime.utcnow()
        s.flush()
    # send to student
    target_id=d.user_id
    if u.message.photo:
        fid=u.message.photo[-1].file_id
        await ctx.bot.send_photo(target_id,fid,caption=d.answer_text or "",
                                 parse_mode="Markdown")
    else:
        await ctx.bot.send_message(target_id,d.answer_text or "_Answered_",parse_mode="Markdown")
    # optionally public
    if publ:
        out=f"*Q*: {d.question_text or ''}\n*A*: {d.answer_text or ''}"
        await ctx.bot.send_message(target_id, "Your doubt was also answered publicly:")
        await ctx.bot.send_message(u.effective_chat.id, out, parse_mode="Markdown")
    await u.message.reply_text("✅ Sent.")
    ctx.user_data.clear()

# cancel
async def cancel(u: Update, _): await u.message.reply_text("❌ Cancelled."); return ConversationHandler.END

# ─────────────  register  ─────────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states = {
            ASK_SUBJ:           [CallbackQueryHandler(subj_chosen, pattern=r"^SUBJ\|")],
            ASK_CUSTOM_SUBJ:    [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_subj)],
            ASK_NATURE:         [CallbackQueryHandler(nature_chosen, pattern=r"^NAT\|")],
            ASK_CUSTOM_NATURE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_nat)],
            ASK_QUESTION: [
                MessageHandler(filters.PHOTO, receive_q),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_q)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_cb, pattern=r"^ANS\|\d+\|[01]$"))
    app.add_handler(MessageHandler(filters.Chat(user_id=ADMIN_ID), admin_answer))
