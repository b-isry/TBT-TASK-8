import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import RetryAfter
import asyncio
import nest_asyncio
import logging

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PORT = int(os.environ.get('PORT', '8443'))

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! Bot is running with webhooks!')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Error occurred: {context.error}')

async def main():
    # Initialize bot application
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)

    # Start webhook with retry logic
    webhook_url = os.getenv('WEBHOOK_URL')
    if not webhook_url:
        raise ValueError("WEBHOOK_URL environment variable is not set!")

    logger.info(f"Setting webhook to {webhook_url}")
    while True:
        try:
            await application.bot.set_webhook(webhook_url)
            break
        except RetryAfter as e:
            logger.warning(f"Flood control exceeded. Retrying in {e.retry_after} seconds...")
            await asyncio.sleep(e.retry_after)

    # Start the webhook
    logger.info(f"Starting webhook server on port {PORT}")
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=webhook_url,
        secret_token=os.getenv('SECRET_TOKEN')
    )

if __name__ == '__main__':
    # Apply nest_asyncio to allow nested event loops
    nest_asyncio.apply()
    
    # Get the event loop
    loop = asyncio.get_event_loop()
    
    try:
        logger.info(f"Starting bot on port {PORT}")
        # Run the main function
        loop.run_until_complete(main())
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        raise
    finally:
        logger.info(f"Application is running on port {PORT}")
        # Keep the event loop running
        loop.run_forever()
