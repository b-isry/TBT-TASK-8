import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import RetryAfter, NetworkError, TelegramError
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from aiohttp import web
import json
from datetime import datetime

# Set up logging
def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Set up file handler with rotation
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=1024 * 1024,  # 1MB
        backupCount=5
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG)

    # Set up root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Initialize logging
logger = setup_logging()

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PORT = int(os.environ.get('PORT', '8443'))

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    try:
        await update.message.reply_text('Hello! Bot is running with webhooks!')
        logger.info(f"Start message sent to user {user.id}")
    except Exception as e:
        logger.error(f"Error sending start message: {e}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    logger.info(f"User {user.id} ({user.username}) sent message: {message_text}")
    try:
        await update.message.reply_text(update.message.text)
        logger.info(f"Echo message sent to user {user.id}")
    except Exception as e:
        logger.error(f"Error sending echo message: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message to the user."""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Log detailed error information
    error_info = {
        'timestamp': datetime.now().isoformat(),
        'update_id': update.update_id if update else None,
        'error_type': type(context.error).__name__,
        'error_message': str(context.error),
        'user_id': update.effective_user.id if update and update.effective_user else None,
        'chat_id': update.effective_chat.id if update and update.effective_chat else None
    }
    
    logger.error(f"Detailed error info: {json.dumps(error_info, indent=2)}")
    
    # Send error message to user if possible
    if update and update.effective_chat:
        error_message = "Sorry, something went wrong. Please try again later."
        if isinstance(context.error, NetworkError):
            error_message = "Network error occurred. Please check your connection."
        elif isinstance(context.error, RetryAfter):
            error_message = f"Too many requests. Please try again in {context.error.retry_after} seconds."
        
        try:
            await update.effective_chat.send_message(error_message)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

async def main():
    logger.info("Starting bot...")
    
    # Initialize bot application
    application = Application.builder().token(TOKEN).build()
    
    # Initialize the application
    await application.initialize()
    logger.info("Bot application initialized")

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)
    logger.info("Handlers registered")

    # Create web application
    app = web.Application()
    
    # Add root route handler
    async def root_handler(request):
        logger.info("Root endpoint accessed")
        return web.Response(text="Bot is running!", status=200)
    
    # Add webhook handler
    async def webhook_handler(request):
        try:
            logger.debug("Received webhook request")
            if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != os.getenv('SECRET_TOKEN'):
                logger.warning("Invalid secret token in webhook request")
                return web.Response(status=403)
            
            update = await request.json()
            logger.debug(f"Received webhook update: {json.dumps(update, indent=2)}")
            
            # Process the update
            await application.process_update(Update.de_json(update, application.bot))
            logger.debug("Update processed successfully")
            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return web.Response(status=500)

    # Add routes
    app.router.add_get('/', root_handler)
    app.router.add_post('/webhook', webhook_handler)
    logger.info("Routes configured")
    
    # Start web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Webhook server started on port {PORT}")
    
    # Set webhook after server is running
    webhook_url = os.getenv('WEBHOOK_URL')
    if not webhook_url:
        logger.error("WEBHOOK_URL environment variable is not set!")
        raise ValueError("WEBHOOK_URL environment variable is not set!")

    # Make sure webhook URL ends with /webhook
    if not webhook_url.endswith('/webhook'):
        webhook_url = f"{webhook_url.rstrip('/')}/webhook"

    logger.info(f"Setting webhook to {webhook_url}")
    while True:
        try:
            await application.bot.set_webhook(
                webhook_url,
                secret_token=os.getenv('SECRET_TOKEN')
            )
            logger.info("Webhook set successfully")
            break
        except RetryAfter as e:
            logger.warning(f"Flood control exceeded. Retrying in {e.retry_after} seconds...")
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            raise
    
    # Keep the server running
    logger.info("Bot is now running and ready to handle updates")
    while True:
        await asyncio.sleep(3600)  # Sleep for an hour

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error occurred: {e}")
        raise
