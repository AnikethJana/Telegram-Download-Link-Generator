"""
Client management system for the Telegram Download Link Generator.

This module provides centralized management of Telegram bot clients including:
- Primary bot client for command handling and messaging
- Multiple worker clients for load distribution and streaming operations
- Round-robin client selection for optimal resource utilization
- Automatic failover and client health monitoring
- Memory-efficient ByteStreamer integration for each client

The ClientManager ensures high availability and performance by distributing
streaming operations across multiple bot tokens while maintaining session
integrity and proper resource cleanup.
"""

import asyncio
import logging
from typing import List, Optional, Dict

from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan, SessionPasswordNeeded

from StreamBot.config import Var
from StreamBot.utils.exceptions import NoClientsAvailableError
from StreamBot.utils.custom_dl import ByteStreamer

logger = logging.getLogger(__name__)


class ClientManager:
    """
    Centralized management of Telegram bot clients with load balancing capabilities.

    This class handles the lifecycle of multiple Pyrogram clients, providing:
    - Primary client for bot operations and user interactions
    - Worker clients for distributed streaming operations
    - Round-robin load balancing for optimal resource utilization
    - Automatic client health monitoring and failover
    - Integrated ByteStreamer management for each client instance
    """
    
    def __init__(self,
                 primary_api_id: int,
                 primary_api_hash: str,
                 primary_bot_token: str,
                 primary_session_name: str,
                 primary_workers_count: int,
                 additional_tokens_list: List[str],
                 worker_session_prefix: str = "worker_client",
                 worker_pyrogram_workers: int = 1,
                 worker_sessions_in_memory: bool = False):
        """
        Initialize the ClientManager with primary and worker client configurations.

        Args:
            primary_api_id (int): Telegram API ID for all clients
            primary_api_hash (str): Telegram API hash for all clients
            primary_bot_token (str): Bot token for the primary client
            primary_session_name (str): Session name for the primary client
            primary_workers_count (int): Number of workers for the primary client
            additional_tokens_list (List[str]): List of additional bot tokens for worker clients
            worker_session_prefix (str): Prefix for worker client session names
            worker_pyrogram_workers (int): Number of Pyrogram workers per worker client
            worker_sessions_in_memory (bool): Whether to store worker sessions in memory only
        """
        # Primary client configuration
        self.primary_api_id = primary_api_id
        self.primary_api_hash = primary_api_hash
        self.primary_bot_token = primary_bot_token
        self.primary_session_name = primary_session_name
        self.primary_workers_count = primary_workers_count

        # Worker client configuration
        self.additional_tokens = additional_tokens_list
        self.worker_session_prefix = worker_session_prefix
        self.worker_pyrogram_workers = worker_pyrogram_workers
        self.worker_sessions_in_memory = worker_sessions_in_memory

        # Client instance storage
        self.primary_client: Optional[Client] = None
        self.worker_clients: List[Client] = []
        self.all_clients: List[Client] = []

        # ByteStreamer instances mapped by client identifier for streaming operations
        self.streamers: Dict[str, ByteStreamer] = {}

        # Load balancing state
        self._round_robin_index = 0
        self._lock = asyncio.Lock()

        logger.info("ClientManager initialized successfully.")
        logger.info(f"Primary bot token: ***{primary_bot_token[-4:]}")
        logger.info(f"Configured {len(additional_tokens_list)} additional worker tokens.")

    async def start_clients(self) -> None:
        """
        Initialize and start all configured Telegram clients.

        This method performs the complete client startup sequence:
        1. Starts the primary bot client for user interactions
        2. Initializes worker clients for distributed streaming operations
        3. Creates ByteStreamer instances for each client
        4. Validates client connectivity and authentication

        Raises:
            Exception: If primary client fails to start (critical error)
            Various Pyrogram exceptions for authentication or network issues
        """
        logger.info("Initializing Telegram client infrastructure...")

        # Initialize primary client for bot operations and user messaging
        try:
            logger.info(f"Starting primary client with session name: {self.primary_session_name}")
            self.primary_client = Client(
                name=self.primary_session_name,
                api_id=self.primary_api_id,
                api_hash=self.primary_api_hash,
                bot_token=self.primary_bot_token,
                workers=self.primary_workers_count
            )
            await self.primary_client.start()
            self.all_clients.append(self.primary_client)
            me = await self.primary_client.get_me()

            # Create ByteStreamer instance for primary client's streaming operations
            self.streamers[f"primary_{me.username}"] = ByteStreamer(self.primary_client)
            logger.info(f"Primary client operational as @{me.username} (ID: {me.id})")
        except (ApiIdInvalid, AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan, SessionPasswordNeeded) as e:
            logger.critical(f"Primary client authentication failed: {e.__class__.__name__} - {e}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"Unexpected error during primary client initialization: {e}", exc_info=True)
            raise

        # Initialize worker clients for load distribution and streaming operations
        if self.additional_tokens:
            logger.info(f"Initializing {len(self.additional_tokens)} worker clients for load balancing...")
            worker_tasks = []

            # Create concurrent startup tasks for all worker clients
            for i, token in enumerate(self.additional_tokens):
                session_name = f"{self.worker_session_prefix}_{i}"
                worker_tasks.append(self._start_single_worker(token, session_name, i))

            # Execute worker initialization concurrently for faster startup
            results = await asyncio.gather(*worker_tasks, return_exceptions=True)

            # Process results and create ByteStreamer instances for successful workers
            for i, result in enumerate(results):
                if isinstance(result, Client) and result.is_connected:
                    self.worker_clients.append(result)
                    self.all_clients.append(result)

                    # Create ByteStreamer instance for worker client's streaming operations
                    self.streamers[f"worker_{i}_{result.me.username}"] = ByteStreamer(result)
                    logger.info(f"Worker client {i} (@{result.me.username}) operational with session: {result.name}.")
                elif isinstance(result, Exception):
                    logger.error(f"Worker client {i} initialization failed (token: ...{self.additional_tokens[i][-4:]}): {result.__class__.__name__}", exc_info=False)
                else:
                    logger.error(f"Worker client {i} initialization incomplete (token: ...{self.additional_tokens[i][-4:]}): {result}")

            logger.info(f"Worker client initialization complete: {len(self.worker_clients)}/{len(self.additional_tokens)} successful.")
        else:
            logger.info("No additional worker tokens configured - operating with primary client only.")

        # Validate that at least one client is operational
        if not self.primary_client and not self.worker_clients:
            logger.critical("No clients available - bot functionality compromised.")
        elif not self.all_clients:
            logger.critical("Client initialization validation failed - all_clients collection is empty.")

    async def _start_single_worker(self, token: str, session_name: str, worker_index: int) -> Client:
        """
        Initialize and start a single worker client instance.

        Worker clients are optimized for streaming operations with:
        - No updates handling (no_updates=True) to reduce overhead
        - Configurable worker count for concurrent operations
        - Optional in-memory session storage for performance

        Args:
            token (str): Bot token for the worker client
            session_name (str): Unique session identifier for the client
            worker_index (int): Index number for logging and identification

        Returns:
            Client: Successfully initialized and connected Pyrogram client

        Raises:
            Exception: If client initialization or authentication fails
        """
        logger.info(f"Initializing worker client {worker_index} with session: {session_name} (Token: ...{token[-4:]})")
        try:
            worker = Client(
                name=session_name,
                api_id=self.primary_api_id,
                api_hash=self.primary_api_hash,
                bot_token=token,
                no_updates=True,  # Optimize for streaming operations only
                workers=self.worker_pyrogram_workers,
                in_memory=self.worker_sessions_in_memory
            )
            await worker.start()
            return worker
        except Exception as e:
            logger.error(f"Worker client {worker_index} initialization failed ({session_name}): {e.__class__.__name__}", exc_info=True)
            raise

    async def stop_clients(self) -> None:
        """
        Perform graceful shutdown of all Telegram clients and clean up resources.

        This method ensures proper resource cleanup by:
        1. Stopping all connected clients concurrently
        2. Handling partial shutdown scenarios gracefully
        3. Clearing all client references and ByteStreamer instances
        4. Logging shutdown status for monitoring and debugging

        The method is designed to be safe to call multiple times and handles
        various edge cases such as partially initialized clients or network issues.
        """
        logger.info("Initiating graceful shutdown of all Telegram clients...")
        stop_tasks = []

        # Create stop tasks for all connected clients
        for client_instance in self.all_clients:
            if client_instance and client_instance.is_connected:
                stop_tasks.append(client_instance.stop())
            elif client_instance:
                logger.debug(f"Client {client_instance.name} already disconnected.")
            else:
                logger.warning("Encountered invalid client reference during shutdown.")

        # Execute shutdown tasks concurrently
        if stop_tasks:
            results = await asyncio.gather(*stop_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                client_name = self.all_clients[i].name if i < len(self.all_clients) and self.all_clients[i] else f"Client {i}"
                if isinstance(result, Exception):
                    logger.error(f"Error during shutdown of client {client_name}: {result}")
                else:
                    logger.info(f"Client {client_name} shut down successfully.")
        else:
            logger.info("No connected clients found during shutdown.")

        # Clean up all client references and associated resources
        self.all_clients.clear()
        self.worker_clients.clear()
        self.streamers.clear()
        self.primary_client = None

    def get_primary_client(self) -> Optional[Client]:
        """
        Retrieve the primary client instance if available and operational.

        The primary client is used for bot command handling and user messaging.
        This method performs a connectivity check before returning the client.

        Returns:
            Optional[Client]: The primary client if connected, None otherwise
        """
        if self.primary_client and self.primary_client.is_connected:
            return self.primary_client
        logger.warning("Primary client unavailable or disconnected.")
        return None

    async def get_streaming_client(self) -> Client:
        """
        Select an optimal client for streaming operations using load balancing.

        This method implements round-robin load balancing across worker clients
        with automatic fallback to the primary client. Worker clients are preferred
        for streaming operations to distribute load and avoid rate limiting.

        Returns:
            Client: An available and connected client for streaming operations

        Raises:
            NoClientsAvailableError: If no clients are currently operational
        """
        async with self._lock:
            # Identify currently active worker clients
            active_workers = [client for client in self.worker_clients if client.is_connected]

            if active_workers:
                # Select next worker using round-robin algorithm
                self._round_robin_index = (self._round_robin_index + 1) % len(active_workers)
                selected_client = active_workers[self._round_robin_index]
                logger.debug(f"Selected worker client @{selected_client.me.username} for streaming operation.")
                return selected_client

            # Fallback to primary client if no workers available
            if self.primary_client and self.primary_client.is_connected:
                logger.warning("No worker clients available. Using primary client for streaming.")
                return self.primary_client

            logger.critical("No operational clients available for streaming operations.")
            raise NoClientsAvailableError("All Telegram clients are currently disconnected or unavailable.")

    async def get_alternative_streaming_client(self, exclude_client: Client) -> Optional[Client]:
        """
        Select an alternative client for streaming operations, excluding a problematic client.

        This method is used for automatic failover when a client encounters issues
        during streaming operations. It maintains load balancing while avoiding
        the problematic client.

        Args:
            exclude_client (Client): The client to exclude from selection

        Returns:
            Optional[Client]: An alternative operational client, or None if none available
        """
        async with self._lock:
            # Find active workers excluding the problematic client
            active_workers = [client for client in self.worker_clients
                            if client.is_connected and client.me.id != exclude_client.me.id]

            if active_workers:
                # Select alternative worker using round-robin
                self._round_robin_index = (self._round_robin_index + 1) % len(active_workers)
                selected_client = active_workers[self._round_robin_index]
                logger.debug(f"Selected alternative worker client @{selected_client.me.username} (excluding @{exclude_client.me.username})")
                return selected_client

            # Fallback to primary client if available and not excluded
            if (self.primary_client and self.primary_client.is_connected and
                self.primary_client.me.id != exclude_client.me.id):
                logger.debug(f"Using primary client @{self.primary_client.me.username} as alternative to @{exclude_client.me.username}")
                return self.primary_client

            logger.warning(f"No alternative clients available (excluding @{exclude_client.me.username})")
            return None

    def get_streamer_for_client(self, client: Client) -> Optional[ByteStreamer]:
        """
        Retrieve the ByteStreamer instance associated with a specific client.

        Each client has a corresponding ByteStreamer for efficient file streaming
        operations. This method provides access to the appropriate streamer
        based on the client instance.

        Args:
            client (Client): The Pyrogram client instance

        Returns:
            Optional[ByteStreamer]: The associated ByteStreamer instance, or None if not found
        """
        # Search through streamer mappings to find the correct instance
        for key, streamer in self.streamers.items():
            if streamer.client.me.id == client.me.id:
                return streamer

        logger.warning(f"No ByteStreamer instance found for client @{client.me.username}")
        return None