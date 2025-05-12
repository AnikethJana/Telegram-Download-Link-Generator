import sys
import asyncio
import logging
import datetime 
from aiohttp import web
from dotenv import load_dotenv

# --- Load .env file BEFORE importing config ---
load_dotenv()
logger = logging.getLogger(__name__) 
logger.info(".env file loaded (if found).")

from .config import Var 
from .bot import TgDlBot 
from .web.web import setup_webapp 

# --- Logging Setup ---
# Ensure logging is configured after potential .env load and Var import if needed
# Basic config might be okay here, or move it after Var if log levels depend on config
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("tgdlbot.log"), 
        logging.StreamHandler(sys.stdout)   
    ]
)

logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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
     runner_ref = None # To hold runner for shutdown
     try:
         # Run the main asynchronous function
         # asyncio.run(main()) # asyncio.run() handles loop creation/closing
         # Need to manage runner for shutdown when using asyncio.run, which isn't straightforward
         # A more manual loop management allows cleaner shutdown access to runner

         loop = asyncio.get_event_loop()
         main_task = loop.create_task(main()) # main() now implicitly sets up runner

         # Need access to runner created inside main() for shutdown
         # A better approach might be for main() to return the runner

         # Temporary workaround: Access runner via web_app if needed, but ideally main returns it
         # Or pass a reference object to main that it can populate

         loop.run_until_complete(main_task) # This will run until main_task completes or is cancelled


     except KeyboardInterrupt:
         # Handle Ctrl+C gracefully
         logger.info("Ctrl+C pressed. Initiating shutdown...")
         # Find the runner - this is a bit hacky, relies on runner being setup in main
         # A cleaner way is needed if main doesn't return runner
         # Assuming runner is accessible somehow or shutdown logic is moved inside main's finally block
         # For now, we call a conceptual shutdown assuming runner is available in scope
         # This part needs refinement based on how runner is managed.
         # Let's assume main handles its own shutdown on cancel/exception for now.
         # The asyncio.Event().wait() inside main will raise CancelledError on Ctrl+C with asyncio.run
         # If using manual loop, need to cancel the task
         if 'main_task' in locals() and not main_task.done():
             main_task.cancel()
             try:
                 loop.run_until_complete(main_task)
             except asyncio.CancelledError:
                 logger.info("Main task cancelled.")
             except Exception as e:
                 logger.error(f"Error during task cancellation: {e}")

         logger.info("Shutdown process completed from KeyboardInterrupt.")
         sys.exit(0) 

     except Exception as e:
         
         logger.critical(f"CRITICAL: Unhandled exception in main execution block: {e}", exc_info=True)
         logger.critical("Exiting due to unhandled runtime error.")
         sys.exit(1) 
     finally:
         # Ensure loop is closed if using manual loop management
         if 'loop' in locals() and loop.is_running():
              loop.close()
              logger.info("Asyncio event loop closed.")