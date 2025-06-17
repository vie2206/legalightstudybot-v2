# ───── unknown-command fallback  (place this *after* all feature modules) ─────
KNOWN_CMDS = {
    "start", "help",
    # study-task
    "task_start", "task_status", "task_pause", "task_resume", "task_stop",
    # timer
    "timer", "timer_status", "timer_pause", "timer_resume", "timer_stop",
    # countdown
    "countdown", "countdownstatus", "countdownstop",
    # streak
    "checkin", "mystreak", "streak_alerts",
}

async def unknown(update, context):
    await update.message.reply_text("❓ Unknown command – try /help.")

#  ▸ filters.COMMAND catches *any* slash-command;
#    we exclude the ones we already know so only real
#    typos fall through to this handler.
unknown_filter = filters.COMMAND & (~filters.Regex(rf"^/({'|'.join(KNOWN_CMDS)})"))

# use a *high* group number so it’s consulted last
app.add_handler(MessageHandler(unknown_filter, unknown), group=99)
