import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import RetryAfter
import asyncio

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PORT = int(os.environ.get('PORT', '8443'))

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! Bot is running with webhooks!')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Error occurred: {context.error}')

async def main():
    # Initialize bot application
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)

    # Start webhook with retry logic
    webhook_url = os.getenv('WEBHOOK_URL')
    while True:
        try:
            await application.bot.set_webhook(webhook_url)
            break
        except RetryAfter as e:
            print(f"Flood control exceeded. Retrying in {e.retry_after} seconds...")
            await asyncio.sleep(e.retry_after)

    # Start the webhook
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=webhook_url,
        secret_token=os.getenv('SECRET_TOKEN')  
    )

if __name__ == '__main__':
    import sys

    try:
        # Try the standard way first
        asyncio.run(main())
    except RuntimeError as e:
        print(f"RuntimeError: {e}")
        # If the event loop is already running (common in some platforms)
        if "already running" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            # Properly schedule and run the coroutine
            task = loop.create_task(main())
            # Await the task if possible
            try:
                loop.run_until_complete(task)
            except RuntimeError as e2:
                print(f"RuntimeError during run_until_complete: {e2}")
    finally:
        print(f"Application is running on port {PORT}")
