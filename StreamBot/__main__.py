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
from .bot import attach_handlers 
from .web.web import setup_webapp 
from .client_manager import ClientManager 
from .utils.cleanup_scheduler import cleanup_scheduler
from .utils.memory_manager import memory_manager

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
CLIENT_MANAGER_INSTANCE: ClientManager = None 

# --- Main Application --- 
async def main():
    """Initializes and runs the bot and web server."""
    global BOT_START_TIME 
    BOT_START_TIME = datetime.datetime.now(datetime.timezone.utc) 

    global CLIENT_MANAGER_INSTANCE # Allow assignment to global

    logger.info(f"Using Base URL: {Var.BASE_URL}") 
    logger.info(f"Log Channel ID: {Var.LOG_CHANNEL}")
    logger.info("Starting Telegram Download Link Generator Bot...")
    
    # Log initial memory usage
    memory_manager.log_memory_usage("startup")
    
    web_runner = None # Renamed runner to web_runner to avoid conflict

    # --- Initialize and Start ClientManager ---
    try:
        additional_tokens = Var.ADDITIONAL_BOT_TOKENS
        logger.info(f"Primary Bot Token: ...{Var.BOT_TOKEN[-4:]}")
        logger.info(f"Additional Bot Tokens: {len(additional_tokens)} found.")
        if additional_tokens:
             for i, token in enumerate(additional_tokens):
                  logger.info(f"  Worker {i+1}: ...{token[-4:]}")

        CLIENT_MANAGER_INSTANCE = ClientManager(
            primary_api_id=Var.API_ID,
            primary_api_hash=Var.API_HASH,
            primary_bot_token=Var.BOT_TOKEN,
            primary_session_name=Var.SESSION_NAME,
            primary_workers_count=Var.WORKERS,
            additional_tokens_list=additional_tokens,
            worker_pyrogram_workers=Var.WORKER_CLIENT_PYROGRAM_WORKERS,
            worker_sessions_in_memory=Var.WORKER_SESSIONS_IN_MEMORY
        )
        await CLIENT_MANAGER_INSTANCE.start_clients()
        
        primary_bot_client = CLIENT_MANAGER_INSTANCE.get_primary_client()
        if not primary_bot_client:
            logger.critical("CRITICAL: Primary bot client could not be obtained from ClientManager. Exiting.")
            sys.exit(1)

        # Attach handlers to the primary client
        attach_handlers(primary_bot_client)
        
        # Store bot info on the primary client instance if needed (e.g., for /api/info)
        me = await primary_bot_client.get_me()
        primary_bot_client.me = me # type: ignore # pyright: ignore [reportGeneralTypeIssues]
        logger.info(f"Primary bot client operational as @{me.username} (ID: {me.id})")
        
        # Log memory usage after client setup
        memory_manager.log_memory_usage("clients started")

    except Exception as e:
        logger.critical(f"CRITICAL: Failed during ClientManager setup or primary client start: {e}", exc_info=True)
        sys.exit(1) 

    # --- Start Web Server ---
    try:
        logger.info("Setting up web server...")
        web_app = await setup_webapp(
            bot_instance=CLIENT_MANAGER_INSTANCE.get_primary_client(), # Pass primary client for general bot info
            client_manager=CLIENT_MANAGER_INSTANCE, # Pass the whole manager for streaming clients
            start_time=BOT_START_TIME
        )
        web_runner = web.AppRunner(web_app) # Use web_runner
        await web_runner.setup()
        
        site = web.TCPSite(web_runner, Var.BIND_ADDRESS, Var.PORT) # Use web_runner
        await site.start()
        logger.info(f"Web server started successfully on http://{Var.BIND_ADDRESS}:{Var.PORT}")
        
        # Log memory usage after web server setup
        memory_manager.log_memory_usage("web server started")
        
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to start web server: {e}", exc_info=True)
        if CLIENT_MANAGER_INSTANCE:
            await CLIENT_MANAGER_INSTANCE.stop_clients() # Ensure clients are stopped if web fails
        sys.exit(1)

    # --- Start Cleanup Scheduler ---
    try:
        await cleanup_scheduler.start()
        logger.info("Cleanup scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start cleanup scheduler: {e}", exc_info=True)
        # Continue running even if cleanup scheduler fails

    # --- Keep Running ---
    logger.info("Bot and web server are running. Press Ctrl+C to stop.")
    # Pass web_runner to the main_task context or make it accessible for shutdown if needed by shutdown func
    main_task.web_runner_ref = web_runner # type: ignore
    main_task.cleanup_scheduler_ref = cleanup_scheduler # type: ignore
    await asyncio.Event().wait() 

# --- Shutdown Logic 
async def perform_shutdown(web_runner_to_stop, client_manager_to_stop, cleanup_scheduler_to_stop=None):
     logger.info("Shutdown signal received. Stopping services...")
     
     # Stop cleanup scheduler first
     if cleanup_scheduler_to_stop:
         try:
             await cleanup_scheduler_to_stop.stop()
             logger.info("Cleanup scheduler stopped.")
         except Exception as e:
             logger.error(f"Error stopping cleanup scheduler: {e}")
     
     # Stop streaming operations
     try:
         from .utils.stream_cleanup import stream_tracker
         await stream_tracker.cancel_all_streams()
         logger.info("All streaming operations cancelled.")
     except Exception as e:
         logger.error(f"Error cancelling streams: {e}")
     
     if client_manager_to_stop:
         await client_manager_to_stop.stop_clients()
         logger.info("All Telegram clients stopped.")
     else:
         logger.info("ClientManager was not initialized.")

     if web_runner_to_stop:
         await web_runner_to_stop.cleanup()
         logger.info("Web server stopped.")
     else:
          logger.info("Web server runner was not initialized.")
          
     # Final memory usage log
     memory_manager.log_memory_usage("shutdown")
     logger.info("Bot stopped gracefully.")


if __name__ == "__main__":
     loop = asyncio.get_event_loop()
     main_task = None
     try:
         main_task = loop.create_task(main())
         loop.run_until_complete(main_task)

     except KeyboardInterrupt:
         logger.info("Ctrl+C pressed. Initiating shutdown...")
         if main_task and not main_task.done():
             main_task.cancel()
             try:
                 loop.run_until_complete(main_task)
             except asyncio.CancelledError:
                 logger.info("Main task cancelled.")
        
     except Exception as e:
         logger.critical(f"CRITICAL: Unhandled exception in main execution block: {e}", exc_info=True)
     
     finally:
         logger.info("Entering finally block for shutdown...")
         current_web_runner = None
         current_cleanup_scheduler = None
         if main_task and hasattr(main_task, 'web_runner_ref'):
             current_web_runner = main_task.web_runner_ref # type: ignore
         if main_task and hasattr(main_task, 'cleanup_scheduler_ref'):
             current_cleanup_scheduler = main_task.cleanup_scheduler_ref # type: ignore
         
         # Perform cleanup of client manager and web server
         # This ensures that perform_shutdown is called even if main() exits early due to an error
         # after CLIENT_MANAGER_INSTANCE or web_runner might have been initialized.
         if loop.is_running():
             loop.run_until_complete(perform_shutdown(current_web_runner, CLIENT_MANAGER_INSTANCE, current_cleanup_scheduler))
         else: # If loop already closed or never started properly, try a simplified shutdown
             asyncio.run(perform_shutdown(current_web_runner, CLIENT_MANAGER_INSTANCE, current_cleanup_scheduler))

         if loop.is_running(): # Close loop if it's still running (it should be if run_until_complete was used)
              loop.close()
              logger.info("Asyncio event loop closed.")
         logger.info("Shutdown process completed.")
         sys.exit(0) # Exit cleanly after shutdown