import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import RetryAfter
import asyncio
import logging
from aiohttp import web

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

    # Create web application
    app = web.Application()
    
    # Add webhook handler
    async def webhook_handler(request):
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != os.getenv('SECRET_TOKEN'):
            return web.Response(status=403)
        
        update = await request.json()
        await application.process_update(Update.de_json(update, application.bot))
        return web.Response(status=200)

    # Add route for webhook
    app.router.add_post('/webhook', webhook_handler)
    
    # Start web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Webhook server started on port {PORT}")
    
    # Keep the server running
    while True:
        await asyncio.sleep(3600)  # Sleep for an hour

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        raise
