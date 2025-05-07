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
            await asyncio.sleep(e.retry_after)  # Use asyncio.sleep instead of time.sleep

    # Start the webhook
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=webhook_url,
        secret_token=os.getenv('SECRET_TOKEN')  
    )

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        if loop.is_running():
            # If the loop is already running, schedule the main coroutine
            loop.create_task(main())
        else:
            # Run the main coroutine in a new event loop
            loop.run_until_complete(main())
    except RuntimeError as e:
        print(f"RuntimeError: {e}")
    finally:
        # Ensure the loop is not closed if it's already running
        if not loop.is_running():
            loop.close()
