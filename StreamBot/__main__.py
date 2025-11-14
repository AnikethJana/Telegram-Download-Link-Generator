"""
Main application entry point for the Telegram Download Link Generator Bot.

This module initializes and orchestrates the core components of the application:
- Bot client management with multi-client support
- Web server for streaming and session generation
- Background cleanup and memory management
- Security middleware and rate limiting

The application provides secure download links for Telegram files with features like
session-based private channel access, bandwidth monitoring, and comprehensive logging.
"""

import sys
import asyncio
import logging
import datetime
from aiohttp import web
from dotenv import load_dotenv

# Load environment variables before importing configuration
load_dotenv()
logger = logging.getLogger(__name__)
logger.info("Environment configuration loaded.")

from .config import Var
from .bot import attach_handlers
from .web.web import setup_webapp
from .client_manager import ClientManager
from .utils.cleanup_scheduler import cleanup_scheduler
from .utils.memory_manager import memory_manager
from .security.rate_limiter import initialize_rate_limiters

# Configure logging with file and console handlers
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("tgdlbot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Reduce log noise from third-party libraries
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("StreamBot.session_generator").setLevel(logging.ERROR)
logging.getLogger("StreamBot.session_generator.session_manager").setLevel(logging.ERROR)
logging.getLogger("StreamBot.session_generator.telegram_auth").setLevel(logging.ERROR)
logging.getLogger("StreamBot.web.web").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Global state variables for application lifecycle management
BOT_START_TIME: datetime.datetime | None = None
CLIENT_MANAGER_INSTANCE: ClientManager | None = None


async def main() -> None:
    """
    Initialize and orchestrate the main application components.

    This function performs the following initialization sequence:
    1. Records application start time
    2. Initializes security rate limiters
    3. Sets up ClientManager with primary and additional bot tokens
    4. Configures bot handlers and web server
    5. Starts background services (cleanup scheduler)
    6. Maintains application runtime until shutdown

    Raises:
        SystemExit: On critical initialization failures
    """
    global BOT_START_TIME
    BOT_START_TIME = datetime.datetime.now(datetime.timezone.utc)

    global CLIENT_MANAGER_INSTANCE

    logger.info(f"Base URL: {Var.BASE_URL}")
    logger.info(f"Log Channel ID: {Var.LOG_CHANNEL}")
    logger.info("Initializing Telegram Download Link Generator Bot...")

    # Initialize security components with configured limits
    initialize_rate_limiters(Var.MAX_LINKS_PER_DAY)

    # Log initial memory usage for monitoring
    memory_manager.log_memory_usage("startup")

    web_runner = None

    # Initialize and start Telegram client management
    try:
        additional_tokens = Var.ADDITIONAL_BOT_TOKENS
        logger.info(f"Primary Bot Token: ...{Var.BOT_TOKEN[-4:]}")
        logger.info(f"Additional Bot Tokens: {len(additional_tokens)} configured.")

        # Log worker token details for debugging
        if additional_tokens:
            for i, token in enumerate(additional_tokens):
                logger.info(f"Worker {i+1}: ...{token[-4:]}")

        # Initialize ClientManager with all configured bot tokens
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

        # Start all configured clients (primary + workers)
        await CLIENT_MANAGER_INSTANCE.start_clients()

        # Verify primary client is operational
        primary_bot_client = CLIENT_MANAGER_INSTANCE.get_primary_client()
        if not primary_bot_client:
            logger.critical("Primary bot client initialization failed. Exiting.")
            sys.exit(1)

        # Configure bot command and message handlers
        attach_handlers(primary_bot_client)

        # Cache bot information for API endpoints
        me = await primary_bot_client.get_me()
        primary_bot_client.me = me  # type: ignore
        logger.info(f"Primary bot client operational as @{me.username} (ID: {me.id})")

        # Test notification system functionality
        logger.info("Testing notification system...")
        try:
            from .session_generator.session_manager import session_manager
            notification_test_passed = await session_manager.test_notification_system()
            if notification_test_passed:
                logger.info("Notification system test passed.")
            else:
                logger.warning("Notification system test had issues, but system will continue.")
        except Exception as test_error:
            logger.warning(f"Notification system test failed: {test_error}")
            logger.warning("System will continue, but login notifications may not work.")

        # Log memory usage after client initialization
        memory_manager.log_memory_usage("clients started")

    except Exception as e:
        logger.critical(f"ClientManager setup or primary client start failed: {e}", exc_info=True)
        sys.exit(1)

    # Initialize web server
    try:
        logger.info("Setting up web server...")
        web_app = await setup_webapp(
            bot_instance=CLIENT_MANAGER_INSTANCE.get_primary_client(),
            client_manager=CLIENT_MANAGER_INSTANCE,
            start_time=BOT_START_TIME
        )

        web_runner = web.AppRunner(web_app)
        await web_runner.setup()

        site = web.TCPSite(web_runner, Var.BIND_ADDRESS, Var.PORT)
        await site.start()
        logger.info(f"Web server started successfully on http://{Var.BIND_ADDRESS}:{Var.PORT}")

        # Log memory usage after web server initialization
        memory_manager.log_memory_usage("web server started")

    except Exception as e:
        logger.critical(f"Web server startup failed: {e}", exc_info=True)
        if CLIENT_MANAGER_INSTANCE:
            await CLIENT_MANAGER_INSTANCE.stop_clients()
        sys.exit(1)

    # Start background cleanup scheduler
    try:
        await cleanup_scheduler.start()
        logger.info("Cleanup scheduler started successfully.")
    except Exception as e:
        logger.error(f"Cleanup scheduler startup failed: {e}", exc_info=True)
        # Continue running even if cleanup scheduler fails

    # Application runtime - wait for shutdown signal
    logger.info("Bot and web server are running. Press Ctrl+C to stop.")
    main_task.web_runner_ref = web_runner  # type: ignore
    main_task.cleanup_scheduler_ref = cleanup_scheduler  # type: ignore
    await asyncio.Event().wait()

async def perform_shutdown(
    web_runner_to_stop,
    client_manager_to_stop,
    cleanup_scheduler_to_stop=None
) -> None:
    """
    Perform graceful shutdown of all application components.

    Shutdown sequence ensures clean resource cleanup in reverse order of initialization:
    1. Cleanup scheduler (stops background tasks)
    2. Active streams (cancels ongoing file transfers)
    3. Telegram clients (disconnects from Telegram API)
    4. Web server (stops HTTP endpoints)
    5. Memory usage logging

    Args:
        web_runner_to_stop: Web application runner instance
        client_manager_to_stop: ClientManager instance to stop clients
        cleanup_scheduler_to_stop: Optional cleanup scheduler instance
    """
    logger.info("Shutdown signal received. Stopping services...")

    # Stop background cleanup tasks first
    if cleanup_scheduler_to_stop:
        try:
            await cleanup_scheduler_to_stop.stop()
            logger.info("Cleanup scheduler stopped.")
        except Exception as e:
            logger.error(f"Error stopping cleanup scheduler: {e}")

    # Cancel any active streaming operations
    try:
        from .utils.stream_cleanup import stream_tracker
        await stream_tracker.cancel_all_streams()
        logger.info("All streaming operations cancelled.")
    except Exception as e:
        logger.error(f"Error cancelling streams: {e}")

    # Stop all Telegram clients
    if client_manager_to_stop:
        await client_manager_to_stop.stop_clients()
        logger.info("All Telegram clients stopped.")
    else:
        logger.info("ClientManager was not initialized.")

    # Stop web server
    if web_runner_to_stop:
        await web_runner_to_stop.cleanup()
        logger.info("Web server stopped.")
    else:
        logger.info("Web server runner was not initialized.")

    # Log final memory usage
    memory_manager.log_memory_usage("shutdown")
    logger.info("Bot stopped gracefully.")


if __name__ == "__main__":
    """
    Application entry point with signal handling and graceful shutdown.

    Handles KeyboardInterrupt for clean shutdown and ensures all resources
    are properly cleaned up even on unexpected errors.
    """
    loop = asyncio.get_event_loop()
    main_task = None

    try:
        # Start the main application task
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
        logger.critical(f"Unhandled exception in main execution block: {e}", exc_info=True)

    finally:
        logger.info("Entering finally block for shutdown...")
        current_web_runner = None
        current_cleanup_scheduler = None

        # Retrieve shutdown references from main task
        if main_task and hasattr(main_task, 'web_runner_ref'):
            current_web_runner = main_task.web_runner_ref  # type: ignore
        if main_task and hasattr(main_task, 'cleanup_scheduler_ref'):
            current_cleanup_scheduler = main_task.cleanup_scheduler_ref  # type: ignore

        # Ensure shutdown is called even if main() exited early due to error
        # This guarantees cleanup of any partially initialized resources
        if loop.is_running():
            loop.run_until_complete(perform_shutdown(
                current_web_runner,
                CLIENT_MANAGER_INSTANCE,
                current_cleanup_scheduler
            ))
        else:
            # Fallback for cases where event loop is not running
            asyncio.run(perform_shutdown(
                current_web_runner,
                CLIENT_MANAGER_INSTANCE,
                current_cleanup_scheduler
            ))

        # Clean up event loop if still running
        if loop.is_running():
            loop.close()
            logger.info("Asyncio event loop closed.")

        logger.info("Shutdown process completed.")
        sys.exit(0)