import sys
import asyncio
import logging  # Add this back for logging.INFO reference
import datetime 
from aiohttp import web
from dotenv import load_dotenv

# --- Load .env file BEFORE importing config ---
load_dotenv()

# Import our new logger module
from logger import setup_logger, get_logger

# Configure logging
setup_logger(
    level=logging.INFO,
    log_file="tgdlbot.log",
    add_stdout=True
)

# Get logger for this module
logger = get_logger(__name__)
logger.info(".env file loaded (if found).")

from config import Var 
from bot import TgDlBot 
from web import setup_webapp 
import exceptions

# --- Global variable for start time ---
BOT_START_TIME = None

# --- Main Application --- 
async def main():
    """Initializes and runs the bot and web server."""
    global BOT_START_TIME 
    BOT_START_TIME = datetime.datetime.now(datetime.timezone.utc) 

    logger.info(f"Using Base URL: {Var.BASE_URL}") 
    logger.info(f"Log Channel ID: {Var.LOG_CHANNEL}")
    logger.info("Starting Telegram Download Link Generator Bot...")
    runner = None 

    # --- Start Bot Client ---
    try:
        logger.info("Starting Telegram client...")
        await TgDlBot.start()
        me = await TgDlBot.get_me()
        # Store bot info globally if needed by API endpoint directly from client instance later
        TgDlBot.me = me 
        logger.info(f"Bot client started as @{me.username} (ID: {me.id})")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to start Telegram client: {e}", exc_info=True)
        sys.exit(1) 

    # --- Start Web Server ---
    try:
        logger.info("Setting up web server...")
        web_app = await setup_webapp(bot_instance=TgDlBot, start_time=BOT_START_TIME)
        runner = web.AppRunner(web_app)
        await runner.setup()
        
        site = web.TCPSite(runner, Var.BIND_ADDRESS, Var.PORT)
        await site.start()
        logger.info(f"Web server started successfully on http://{Var.BIND_ADDRESS}:{Var.PORT}")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to start web server: {e}", exc_info=True)
        
        if TgDlBot.is_connected:
            await TgDlBot.stop()
        sys.exit(1)

    # --- Keep Running ---
    logger.info("Bot and web server are running. Press Ctrl+C to stop.")
    # Keep the main task running indefinitely
    await asyncio.Event().wait() 

# --- Shutdown Logic 
async def shutdown(runner):
     logger.info("Shutdown signal received. Stopping services...")
     if TgDlBot.is_connected:
         await TgDlBot.stop()
         logger.info("Telegram client stopped.")
     else:
         logger.info("Telegram client was not connected.")

     if runner:
         await runner.cleanup()
         logger.info("Web server stopped.")
     else:
          logger.info("Web server runner was not initialized.")
     logger.info("Bot stopped gracefully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Ctrl+C pressed. Initiating shutdown...")
        # No need for manual loop management; asyncio.run handles cleanup
        logger.info("Shutdown process completed from KeyboardInterrupt.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"CRITICAL: Unhandled exception in main execution block: {e}", exc_info=True)
        logger.critical("Exiting due to unhandled runtime error.")
        sys.exit(1)