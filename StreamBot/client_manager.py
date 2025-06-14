# StreamBot/client_manager.py
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
    """Manages primary and worker Telegram clients for the bot."""
    
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

        self.primary_api_id = primary_api_id
        self.primary_api_hash = primary_api_hash
        self.primary_bot_token = primary_bot_token
        self.primary_session_name = primary_session_name
        self.primary_workers_count = primary_workers_count

        self.additional_tokens = additional_tokens_list
        self.worker_session_prefix = worker_session_prefix
        self.worker_pyrogram_workers = worker_pyrogram_workers
        self.worker_sessions_in_memory = worker_sessions_in_memory

        self.primary_client: Optional[Client] = None
        self.worker_clients: List[Client] = []
        self.all_clients: List[Client] = []
        
        # ByteStreamer instances for each client
        self.streamers: Dict[str, ByteStreamer] = {}

        self._round_robin_index = 0
        self._lock = asyncio.Lock()
        logger.info("ClientManager initialized.")
        logger.info(f"Primary bot token: ***{primary_bot_token[-4:]}")
        logger.info(f"Found {len(additional_tokens_list)} additional bot tokens.")

    async def start_clients(self):
        """Start all Telegram clients (primary and workers)."""
        logger.info("Starting Telegram clients...")

        # Start primary client
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
            
            # Create ByteStreamer for primary client
            self.streamers[f"primary_{me.username}"] = ByteStreamer(self.primary_client)
            logger.info(f"Primary client started as @{me.username} (ID: {me.id})")
        except (ApiIdInvalid, AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan, SessionPasswordNeeded) as e:
            logger.critical(f"CRITICAL: Failed to start primary Telegram client: {e.__class__.__name__} - {e}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"CRITICAL: An unexpected error occurred while starting primary client: {e}", exc_info=True)
            raise

        # Start worker clients
        if self.additional_tokens:
            logger.info(f"Starting {len(self.additional_tokens)} worker clients...")
            worker_tasks = []
            for i, token in enumerate(self.additional_tokens):
                session_name = f"{self.worker_session_prefix}_{i}"
                worker_tasks.append(self._start_single_worker(token, session_name, i))

            results = await asyncio.gather(*worker_tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Client) and result.is_connected:
                    self.worker_clients.append(result)
                    self.all_clients.append(result)
                    
                    # Create ByteStreamer for worker client
                    self.streamers[f"worker_{i}_{result.me.username}"] = ByteStreamer(result)
                    logger.info(f"Worker client {i} (@{result.me.username}) started successfully with session: {result.name}.")
                elif isinstance(result, Exception):
                    logger.error(f"Failed to start worker client {i} with token ending in ...{self.additional_tokens[i][-4:]}: {result.__class__.__name__} - {result}", exc_info=False)
                else:
                    logger.error(f"Worker client {i} with token ...{self.additional_tokens[i][-4:]} did not start correctly and did not raise an exception. Result: {result}")
            logger.info(f"Successfully started {len(self.worker_clients)} worker clients out of {len(self.additional_tokens)}.")
        else:
            logger.info("No additional worker tokens configured.")

        if not self.primary_client and not self.worker_clients:
            logger.critical("CRITICAL: No clients (neither primary nor worker) could be started. The bot cannot function.")
        elif not self.all_clients:
            logger.critical("CRITICAL: self.all_clients is empty after startup attempts.")

    async def _start_single_worker(self, token: str, session_name: str, worker_index: int) -> Client:
        """Start a single worker client."""
        logger.info(f"Attempting to start worker client {worker_index} with session: {session_name} (Token: ...{token[-4:]})")
        try:
            worker = Client(
                name=session_name,
                api_id=self.primary_api_id,
                api_hash=self.primary_api_hash,
                bot_token=token,
                no_updates=True,
                workers=self.worker_pyrogram_workers,
                in_memory=self.worker_sessions_in_memory
            )
            await worker.start()
            return worker
        except Exception as e:
            logger.error(f"Error starting worker client {worker_index} ({session_name}): {e.__class__.__name__}", exc_info=True)
            raise

    async def stop_clients(self):
        """Stop all Telegram clients."""
        logger.info("Stopping all Telegram clients...")
        stop_tasks = []
        for client_instance in self.all_clients:
            if client_instance and client_instance.is_connected:
                stop_tasks.append(client_instance.stop())
            elif client_instance:
                logger.info(f"Client {client_instance.name} was not connected, no stop needed.")
            else:
                logger.warning("Found a None entry in all_clients during stop.")

        if stop_tasks:
            results = await asyncio.gather(*stop_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                client_name = self.all_clients[i].name if i < len(self.all_clients) and self.all_clients[i] else f"Client {i}"
                if isinstance(result, Exception):
                    logger.error(f"Error stopping client {client_name}: {result}")
                else:
                    logger.info(f"Client {client_name} stopped successfully.")
        else:
            logger.info("No connected clients to stop.")
        self.all_clients.clear()
        self.worker_clients.clear()
        self.streamers.clear()
        self.primary_client = None

    def get_primary_client(self) -> Optional[Client]:
        """Get the primary client if available and connected."""
        if self.primary_client and self.primary_client.is_connected:
            return self.primary_client
        logger.warning("Primary client requested but is not available or not connected.")
        return None

    async def get_streaming_client(self) -> Client:
        """Get an available client for streaming operations using round-robin selection."""
        async with self._lock:
            active_workers = [client for client in self.worker_clients if client.is_connected]

            if active_workers:
                self._round_robin_index = (self._round_robin_index + 1) % len(active_workers)
                selected_client = active_workers[self._round_robin_index]
                logger.debug(f"Selected worker client @{selected_client.me.username} via round-robin for streaming.")
                return selected_client

            if self.primary_client and self.primary_client.is_connected:
                logger.warning("No active worker clients available. Falling back to primary client for streaming.")
                return self.primary_client

            logger.critical("CRITICAL: No connected Telegram clients available for streaming operation!")
            raise NoClientsAvailableError("All Telegram clients are currently disconnected or no clients were started.")

    async def get_alternative_streaming_client(self, exclude_client: Client) -> Optional[Client]:
        """Get an alternative streaming client, excluding the specified problematic client."""
        async with self._lock:
            active_workers = [client for client in self.worker_clients 
                            if client.is_connected and client.me.id != exclude_client.me.id]

            if active_workers:
                # Select the next available worker that's not the excluded one
                self._round_robin_index = (self._round_robin_index + 1) % len(active_workers)
                selected_client = active_workers[self._round_robin_index]
                logger.debug(f"Selected alternative worker client @{selected_client.me.username} excluding @{exclude_client.me.username}")
                return selected_client

            # If no alternative workers, check if primary is available and different
            if (self.primary_client and self.primary_client.is_connected and 
                self.primary_client.me.id != exclude_client.me.id):
                logger.debug(f"Using primary client @{self.primary_client.me.username} as alternative to @{exclude_client.me.username}")
                return self.primary_client

            logger.warning(f"No alternative clients available excluding @{exclude_client.me.username}")
            return None

    def get_streamer_for_client(self, client: Client) -> Optional[ByteStreamer]:
        """Get the ByteStreamer instance for a given client."""
        for key, streamer in self.streamers.items():
            if streamer.client.me.id == client.me.id:
                return streamer
        logger.warning(f"No ByteStreamer found for client @{client.me.username}")
        return None