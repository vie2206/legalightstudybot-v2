# doubts.py  – v2.2  (remove “username” arg)
import enum, datetime as dt, os, uuid
from pathlib import Path
from telegram import (
    InlineKeyboardMarkup, InlineKeyboardButton, Update, InputFile
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from database import session_scope, Doubt, DoubtQuota

MEDIA_DIR = Path("doubt_media")
MEDIA_DIR.mkdir(exist_ok=True)

class Subject(enum.Enum):
    ENG  = "English & RC"
    LEG  = "Legal Reasoning"
    LOG  = "Logical Reasoning"
    MAT  = "Maths"
    GK   = "GK / CA"
    MOCK = "Mock Test"
    SECT = "Sectional Test"
    STR  = "Strategy / Time-Mgmt"
    APPL = "Application / College"
    OTH  = "Other / Custom"

class Nature(enum.Enum):
    Q_SOLVE    = "Can’t solve a question"
    WRONG_ANS  = "Don’t understand the official answer"
    EXPLAIN    = "Explain my wrong answer"
    CONCEPT    = "Concept clarification"
    ALT_METH   = "Need alternative method"
    SOURCE     = "Source / reference request"
    TIME_MGMT  = "Time-management advice"
    STRATEGY   = "Test-taking strategy"
    OTHER      = "Other / Custom"

(ASK_SUBJ, ASK_NATURE, ASK_TEXT, ASK_MEDIA, CONFIRM) = range(5)

async def _check_quota(uid: int, public: bool) -> str | None:
    today = dt.date.today()
    with session_scope() as s:
        q = s.get(DoubtQuota, (uid, today))
        if not q:
            q = DoubtQuota(user_id=uid, date=today, public_count=0, private_count=0)
            s.add(q)
        if public and q.public_count >= 2:
            return "Daily public-doubt quota (2) reached."
        if not public and q.private_count >= 3:
            return "Daily private-doubt quota (3) reached."
    return None

async def cmd_doubt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = await _check_quota(update.effective_user.id, public=False)   # we only check quota later again
    if err:
        return await update.message.reply_text(err)
    kb = [[InlineKeyboardButton(subj.value, callback_data=f"S|{subj.name}")]
          for subj in Subject]
    await update.message.reply_text("Select *subject*:", parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))
    return ASK_SUBJ

async def chose_subj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["subj"] = Subject[update.callback_query.data.split("|")[1]]
    await update.callback_query.answer()
    kb = [[InlineKeyboardButton(nat.value, callback_data=f"N|{nat.name}")]
          for nat in Nature]
    await update.callback_query.edit_message_text("Select *nature of doubt*:",
                                                  parse_mode="Markdown",
                                                  reply_markup=InlineKeyboardMarkup(kb))
    return ASK_NATURE

async def chose_nature(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nature"] = Nature[update.callback_query.data.split("|")[1]]
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Send the doubt text (you can add *one* image afterwards).",
        parse_mode="Markdown")
    return ASK_TEXT

async def receive_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["text"] = update.message.text.strip()[:1024]
    await update.message.reply_text("Optional: send *one* photo, or /skip.",
                                    parse_mode="Markdown")
    return ASK_MEDIA

async def receive_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    fid = photo.file_id
    fname = MEDIA_DIR / f"{uuid.uuid4()}.jpg"
    await photo.get_file().download_to_drive(str(fname))
    ctx.user_data["photo"] = fname
    return await _save_and_confirm(update, ctx)

async def skip_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_confirm(update, ctx)

async def _save_and_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    subj = ctx.user_data["subj"]
    nat  = ctx.user_data["nature"]
    txt  = ctx.user_data["text"]
    img  = ctx.user_data.get("photo")

    with session_scope() as s:
        d = Doubt(
            user_id=uid,
            subject=subj.name,
            nature=nat.name,
            text=txt,
            image_path=str(img) if img else None,
            ts_submitted=dt.datetime.utcnow(),
        )
        s.add(d)
        q = s.get(DoubtQuota, (uid, dt.date.today()))
        q.private_count += 1   # always private for now
    await update.message.reply_text("✅ Your doubt was submitted. I’ll get back to you soon.")
    # notify admin
    await ctx.bot.send_message(
        ctx.bot_data["ADMIN_ID"],
        f"🆕 *{subj.value}* – {nat.value}\n\n{txt}",
        parse_mode="Markdown",
    )
    if img:
        await ctx.bot.send_photo(ctx.bot_data["ADMIN_ID"], InputFile(img))
    return ConversationHandler.END

def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", cmd_doubt)],
        states={
            ASK_SUBJ:   [CallbackQueryHandler(chose_subj,   pattern=r"^S\|")],
            ASK_NATURE: [CallbackQueryHandler(chose_nature, pattern=r"^N\|")],
            ASK_TEXT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
            ASK_MEDIA: [
                MessageHandler(filters.PHOTO, receive_photo),
                CommandHandler("skip", skip_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", skip_photo)],
        per_user=True,
    )
    app.add_handler(conv)
