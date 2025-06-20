# doubts.py  ───────────────────────────────────────────────────────────
"""
Private ➜ public doubt-handling module.

Commands
--------
/doubt         – open inline wizard, submit text or a single photo + caption
/mydoubts      – list your last N doubts with their status
Admins will see an “Answer” button to publish or PM a reply.

Environment
-----------
ADMIN_ID   – telegram user-id of the bot owner (default: 803299591)
"""

import asyncio, os, time
from contextlib import suppress
from enum import Enum, auto
from typing import Dict, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    InputMediaPhoto,
    Message,
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

# read admin (owner) id here – no more circular import
ADMIN_ID = int(os.getenv("ADMIN_ID", "803299591"))

# DB stuff
from database import session_scope, Doubt, DoubtQuota

# ────────── conversation states ──────────
ASK_CAT, ASK_CONTENT = range(2)

# available categories + custom option
CATEGORIES = (
    "Concept", "Question-solving", "Wrong answer", "Resource request",
    "Strategy", "Other ❓",
)

# text & photo are stored in memory only until saved
_pending_media: Dict[int, dict] = {}  # chat_id → {"cat": str, "text": str, "photo": file_id}


# ──────────────────────────────────────────────────────────────────────
async def doubt_start(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """/doubt entry point – show category keyboard."""
    kb = [[InlineKeyboardButton(c, callback_data=f"C|{c}")] for c in CATEGORIES]
    await upd.message.reply_text(
        "Pick a category for your doubt:",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ASK_CAT


async def cat_chosen(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = upd.callback_query
    await q.answer()
    cat = q.data.split("|", 1)[1]
    _pending_media[q.message.chat.id] = {"cat": cat}
    await q.edit_message_text(
        "Great! Now send **either** a text description *or* one photo with an "
        "optional caption (max 1).",
        parse_mode="Markdown",
    )
    return ASK_CONTENT


async def receive_content(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = upd.effective_chat.id
    pend = _pending_media.get(chat_id)
    if not pend:
        return ConversationHandler.END  # should not happen

    # enforce 1 piece of media
    if upd.message.photo:
        if "photo" in pend or "text" in pend:
            await upd.message.reply_text("You already sent something – use /cancel first.")
            return ASK_CONTENT
        pend["photo"] = upd.message.photo[-1].file_id
        pend["caption"] = upd.message.caption or ""
    else:
        if "text" in pend or "photo" in pend:
            await upd.message.reply_text("You already sent something – use /cancel first.")
            return ASK_CONTENT
        pend["text"] = upd.message.text_html or upd.message.text_markdown or upd.message.text

    # validate quota
    uid = upd.effective_user.id
    with session_scope() as db:
        quota = DoubtQuota.get_or_create(db, uid)
        if not quota.consume():
            await upd.message.reply_text(
                "🚫 You’ve reached today’s free-doubt limit. "
                "Upgrade your plan to ask more."
            )
            _pending_media.pop(chat_id, None)
            return ConversationHandler.END
        db.add(quota)

        # persist doubt
        d = Doubt(
            user_id=uid,
            category=pend["cat"],
            text=pend.get("text", ""),
            photo_id=pend.get("photo"),
            created=int(time.time()),
        )
        db.add(d)

    # notify admin privately
    await ctx.bot.send_message(
        ADMIN_ID,
        f"📩 *New doubt* from [{upd.effective_user.first_name}](tg://user?id={uid})\n"
        f"*Category:* {pend['cat']}\n"
        f"ID: {d.id}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Answer ✔️", callback_data=f"A|{d.id}")]]
        ),
    )

    # confirm to student
    await upd.message.reply_text("✅ Doubt received! I’ll get back to you soon.")
    _pending_media.pop(chat_id, None)
    return ConversationHandler.END


async def cancel(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    _pending_media.pop(upd.effective_chat.id, None)
    await upd.message.reply_text("❌ Doubt cancelled.")
    return ConversationHandler.END


# ────────── admin flow ──────────
async def answer_button(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = upd.callback_query
    await q.answer()
    _, did = q.data.split("|", 1)

    with session_scope() as db:
        d: Optional[Doubt] = db.get(Doubt, int(did))
        if not d or d.answered_ts:
            await q.edit_message_text("This doubt was already answered.")
            return
        ctx.user_data["answering"] = d.id
        await q.edit_message_text(
            f"Reply to this message with your *answer* for doubt #{d.id}.",
            parse_mode="Markdown",
        )


async def save_answer(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "answering" not in ctx.user_data:
        return
    did = ctx.user_data.pop("answering")

    with session_scope() as db:
        d: Optional[Doubt] = db.get(Doubt, did)
        if not d:
            return
        d.answer_text = upd.message.text_html or upd.message.text_markdown or upd.message.text
        d.answered_ts = int(time.time())
        db.add(d)

        # send to student (private)
        await ctx.bot.send_message(
            d.user_id,
            f"📝 *Answer to your doubt* #{d.id}\n\n{d.answer_text}",
            parse_mode="Markdown",
            reply_to_message_id=None,
        )

        # post publicly in the group/channel
        target_chat = os.getenv("PUBLIC_ANSWER_CHAT")
        if target_chat:
            if d.photo_id:
                await ctx.bot.send_photo(
                    target_chat,
                    d.photo_id,
                    caption=f"❓ {d.text}\n\n📝 {d.answer_text}",
                    parse_mode="Markdown",
                )
            else:
                await ctx.bot.send_message(
                    target_chat,
                    f"❓ {d.text}\n\n📝 {d.answer_text}",
                    parse_mode="Markdown",
                )

    await upd.message.reply_text("✅ Posted!")
    return


# ────────── list my doubts ──────────
async def mydoubts(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = upd.effective_user.id
    with session_scope() as db:
        rows = (
            db.query(Doubt)
            .filter(Doubt.user_id == uid)
            .order_by(Doubt.created.desc())
            .limit(10)
            .all()
        )
    if not rows:
        return await upd.message.reply_text("No doubts yet.")
    txt = "\n\n".join(
        f"*#{d.id}* — {d.category}\n"
        f"{'✅ Answered' if d.answered_ts else '⏳ Pending'}"
        for d in rows
    )
    await upd.message.reply_text(txt, parse_mode="Markdown")


# ────────── registration helper ──────────
def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("doubt", doubt_start)],
        states={
            ASK_CAT:   [CallbackQueryHandler(cat_chosen, pattern=r"^C\|")],
            ASK_CONTENT: [
                MessageHandler(filters.PHOTO, receive_content),
                MessageHandler(filters.TEXT & (~filters.COMMAND), receive_content),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
    app.add_handler(conv)

    # admin answer flow
    app.add_handler(CallbackQueryHandler(answer_button, pattern=r"^A\|\d+$"))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_ID) & (~filters.COMMAND), save_answer
    ))

    # misc
    app.add_handler(CommandHandler("mydoubts", mydoubts))
