import os
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Legalight Study Bot.\nWe can do hard things 💪")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Use /start to begin and /help to get assistance.")

async def echo_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔁 You said: " + update.message.text)

# Create the bot application
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Add handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo_text))

# aiohttp webhook handler
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return web.Response(status=500)

# aiohttp app setup
async def on_startup(app):
    webhook_url = "https://legalightstudybot-docker.onrender.com/webhook"
    await telegram_app.bot.set_webhook(webhook_url)
    print(f"🚀 Webhook set to {webhook_url}")

def main():
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    app.on_startup.append(on_startup)
    web.run_app(app, port=10000)

if __name__ == "__main__":
    main()
