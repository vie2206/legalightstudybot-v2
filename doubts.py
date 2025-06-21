# doubts.py – /doubt ask  with quotas (2 public + 3 private per day)
import enum, datetime as dt, asyncio, itertools
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto, InputMediaDocument
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from database import session_scope, Doubt, DoubtQuota

# ── Enums ─────────────────────────────────────────────────────
class Subject(enum.Enum):
    ENGLISH="English", "📖 English"
    LEGAL="Legal Reasoning", "⚖️ Legal"
    LOGICAL="Logical Reasoning", "🧩 Logical"
    MATHS="Maths", "➗ Maths"
    GK="GK / CA", "🌎 GK/CA"
    MOCK="Mock Test", "📝 Mock"
    SECTIONAL="Sectional Test", "📊 Sectional"
    STRATEGY="Strategy / Time-Mgmt", "⏱ Strategy"
    COLLEGE="Application / College", "🏛 College"
    OTHER="Other", "🔖 Other"
    def __new__(cls,key,label):
        obj=str.__new__(cls,key);obj._value_=key;obj.label=label;return obj

class Nature(enum.Enum):
    NSOL="Can’t solve", "❓ Can't solve"
    NANS="Don’t get answer", "🤔 Answer?"
    WRONG="Explain wrong answer", "📉 Wrong ans"
    CONCEPT="Concept clarif.", "💡 Concept"
    ALT="Alt. method", "🔄 Alternate"
    SOURCE="Source/ref", "🔗 Source"
    TIME="Time-mgmt", "⏱ Time"
    STRAT="Test strategy", "🎯 Strategy"
    OTHER="Other", "🔖 Other"
    def __new__(cls,key,label):
        obj=str.__new__(cls,key);obj._value_=key;obj.label=label;return obj

# ── States ───────────────────────────────────────────────────
S_SUBJ,S_NAT,S_Q,S_FILE = range(4)

DAILY_PUB=2; DAILY_PRI=3

# ── quota helper ─────────────────────────────────────────────
async def _check_quota(uid:int, public:bool)->str|None:
    today=dt.date.today()
    with session_scope() as s:
        q=s.query(DoubtQuota).filter_by(user_id=uid, date=today).first()
        if not q:
            q=DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            s.add(q); s.commit()
        if public and q.public_count>=DAILY_PUB:
            return f"Daily public-doubt limit ({DAILY_PUB}) reached."
        if not public and q.private_count>=DAILY_PRI:
            return f"Daily private-doubt limit ({DAILY_PRI}) reached."
        if public: q.public_count+=1
        else:      q.private_count+=1
        s.commit()

# ── conversation ────────────────────────────────────────────
async def cmd_doubt(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    err=await _check_quota(update.effective_user.id, public=False)
    if err: return await update.message.reply_text(err)
    # Subject keyboard
    rows=list(itertools.zip_longest(*[iter(list(Subject))]*2, fillvalue=None))
    kb=[[InlineKeyboardButton(s.label,callback_data=f"S|{s.value}") for s in row if s]
        for row in rows]
    await update.message.reply_text("Subject?",reply_markup=InlineKeyboardMarkup(kb))
    return S_SUBJ

async def subj_cb(update:Update, ctx):
    q=update.callback_query;await q.answer()
    ctx.user_data["subj"]=q.data.split("|",1)[1]
    # nature kb
    rows=list(itertools.zip_longest(*[iter(list(Nature))]*2, fillvalue=None))
    kb=[[InlineKeyboardButton(n.label,callback_data=f"N|{n.value}") for n in row if n]
        for row in rows]
    await q.edit_message_text("Nature of doubt:",reply_markup=InlineKeyboardMarkup(kb))
    return S_NAT

async def nat_cb(update:Update, ctx):
    q=update.callback_query;await q.answer()
    ctx.user_data["nature"]=q.data.split("|",1)[1]
    await q.edit_message_text("Describe your doubt (or attach a photo/doc, then /done):")
    return S_Q

async def text_q(update:Update, ctx):
    ctx.user_data["text"]="\n".join([ctx.user_data.get("text",""), update.message.text.strip()])

async def file_q(update:Update, ctx):
    if photo:=update.message.photo:
        ctx.user_data["file"]=photo[-1].file_id
    elif doc:=update.message.document:
        ctx.user_data["file"]=doc.file_id

async def done(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    d=Doubt(
        user_id=update.effective_user.id,
        subject=ctx.user_data["subj"],
        nature=ctx.user_data["nature"],
        question=ctx.user_data.get("text","(no text)"),
        file_id=ctx.user_data.get("file")
    )
    with session_scope() as s: s.add(d)
    await update.message.reply_text("🎫 Doubt recorded. Tutor will respond soon.")
    return ConversationHandler.END

async def cancel(update:Update,_): await update.message.reply_text("Cancelled."); return ConversationHandler.END

def register_handlers(app:Application):
    conv=ConversationHandler(
        entry_points=[CommandHandler("doubt",cmd_doubt)],
        states={
            S_SUBJ:[CallbackQueryHandler(subj_cb,pattern="^S\|")],
            S_NAT: [CallbackQueryHandler(nat_cb, pattern="^N\|")],
            S_Q:   [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_q),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, file_q),
                CommandHandler("done", done)
            ],
        }, fallbacks=[CommandHandler("cancel", cancel)], per_user=True
    )
    app.add_handler(conv)
