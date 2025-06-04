import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from pyrogram import Client
from pyrogram.errors import FloodWait

from StreamBot.client_manager import ClientManager
from StreamBot.utils.exceptions import NoClientsAvailableError

logger = logging.getLogger(__name__)

class FileSize(Enum):
    """File size categories for intelligent allocation."""
    SMALL = "small"  # < 300MB
    LARGE = "large"  # >= 300MB

class ClientStatus(Enum):
    """Client status for tracking availability."""
    IDLE = "idle"
    BUSY = "busy"
    FLOOD_WAIT = "flood_wait"

class IntelligentClientAllocator:
    """
    Intelligent client allocation system that segregates download tasks by file size.
    
    This system builds on top of the existing ClientManager to provide:
    - Size-based client allocation (small vs large files)
    - Intelligent overflow handling
    - FloodWait retry with alternative clients
    - Resource efficiency through smart client selection
    """
    
    def __init__(self, client_manager: ClientManager, small_file_threshold_mb: int = 300):
        self.client_manager = client_manager
        self.small_file_threshold_bytes = small_file_threshold_mb * 1024 * 1024
        
        # Track client states
        self.client_states: Dict[int, ClientStatus] = {}  # client_id -> status
        self.client_tasks: Dict[int, str] = {}  # client_id -> task_id for tracking
        self.flood_wait_until: Dict[int, float] = {}  # client_id -> timestamp when flood wait ends
        
        # Round-robin indices for each group
        self.small_preferred_index = 0
        self.large_preferred_index = 0
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        logger.info(f"IntelligentClientAllocator initialized with {small_file_threshold_mb}MB threshold")
    
    def _calculate_client_groups(self) -> Tuple[List[Client], List[Client]]:
        """
        Calculate small-preferred and large-preferred client groups.
        Formula for small group: floor(((N - 2) + (N % 2)) / 2)
        """
        all_clients = [c for c in self.client_manager.all_clients if c and c.is_connected]
        total_clients = len(all_clients)
        
        if total_clients <= 2:
            # With 2 or fewer clients, assign based on simple rules
            if total_clients == 1:
                small_preferred = all_clients.copy()
                large_preferred = all_clients.copy()
            else:  # total_clients == 2
                small_preferred = [all_clients[0]]
                large_preferred = [all_clients[1]]
        else:
            # Apply the formula: floor(((N - 2) + (N % 2)) / 2)
            small_group_size = ((total_clients - 2) + (total_clients % 2)) // 2
            small_preferred = all_clients[:small_group_size]
            large_preferred = all_clients[small_group_size:]
        
        logger.debug(f"Client groups calculated: {len(small_preferred)} small-preferred, {len(large_preferred)} large-preferred from {total_clients} total")
        return small_preferred, large_preferred
    
    def _is_client_available(self, client: Client) -> bool:
        """Check if a client is available for new tasks."""
        client_id = client.me.id
        
        # Check if client is in flood wait
        if client_id in self.flood_wait_until:
            if time.time() < self.flood_wait_until[client_id]:
                return False
            else:
                # Flood wait period ended, remove from tracking
                del self.flood_wait_until[client_id]
                self.client_states[client_id] = ClientStatus.IDLE
        
        # Check current status
        status = self.client_states.get(client_id, ClientStatus.IDLE)
        return status == ClientStatus.IDLE and client.is_connected
    
    def _get_available_clients_from_group(self, client_group: List[Client]) -> List[Client]:
        """Get available clients from a specific group."""
        return [client for client in client_group if self._is_client_available(client)]
    
    def _select_client_round_robin(self, available_clients: List[Client], is_small_group: bool) -> Optional[Client]:
        """Select a client using round-robin from available clients."""
        if not available_clients:
            return None
        
        if is_small_group:
            self.small_preferred_index = (self.small_preferred_index + 1) % len(available_clients)
            selected = available_clients[self.small_preferred_index]
        else:
            self.large_preferred_index = (self.large_preferred_index + 1) % len(available_clients)
            selected = available_clients[self.large_preferred_index]
        
        return selected
    
    async def acquire_client_for_download(self, file_size: int, task_id: str) -> Client:
        """
        Acquire an optimal client for a download task based on file size.
        
        Args:
            file_size: Size of the file to download in bytes
            task_id: Unique identifier for this download task
            
        Returns:
            Client instance allocated for the download
            
        Raises:
            NoClientsAvailableError: When no clients are available
        """
        async with self._lock:
            file_category = FileSize.SMALL if file_size < self.small_file_threshold_bytes else FileSize.LARGE
            small_preferred, large_preferred = self._calculate_client_groups()
            
            selected_client = None
            
            if file_category == FileSize.SMALL:
                # Try small-preferred group first
                available_small = self._get_available_clients_from_group(small_preferred)
                if available_small:
                    selected_client = self._select_client_round_robin(available_small, is_small_group=True)
                    logger.debug(f"Allocated small-preferred client @{selected_client.me.username} for {file_size/1024/1024:.1f}MB task {task_id}")
                else:
                    # Overflow to large-preferred group
                    available_large = self._get_available_clients_from_group(large_preferred)
                    if available_large:
                        selected_client = self._select_client_round_robin(available_large, is_small_group=False)
                        logger.debug(f"Overflowed to large-preferred client @{selected_client.me.username} for {file_size/1024/1024:.1f}MB task {task_id}")
            
            else:  # FileSize.LARGE
                # Use large-preferred group
                available_large = self._get_available_clients_from_group(large_preferred)
                if available_large:
                    selected_client = self._select_client_round_robin(available_large, is_small_group=False)
                    logger.debug(f"Allocated large-preferred client @{selected_client.me.username} for {file_size/1024/1024:.1f}MB task {task_id}")
            
            if selected_client:
                # Mark client as busy
                client_id = selected_client.me.id
                self.client_states[client_id] = ClientStatus.BUSY
                self.client_tasks[client_id] = task_id
                
                logger.info(f"Client @{selected_client.me.username} allocated for {file_category.value} file ({file_size/1024/1024:.1f}MB) task {task_id}")
                return selected_client
            
            # No clients available
            total_clients = len(self.client_manager.all_clients)
            busy_count = sum(1 for status in self.client_states.values() if status == ClientStatus.BUSY)
            flood_wait_count = len(self.flood_wait_until)
            
            logger.warning(f"No clients available for {file_category.value} file task {task_id}. "
                         f"Total: {total_clients}, Busy: {busy_count}, FloodWait: {flood_wait_count}")
            
            raise NoClientsAvailableError(f"No clients available for {file_category.value} file download")
    
    async def handle_flood_wait_retry(self, failed_client: Client, flood_wait_seconds: int, 
                                    file_size: int, task_id: str) -> Optional[Client]:
        """
        Handle FloodWait error by marking client as unavailable and finding alternative.
        
        Args:
            failed_client: Client that encountered FloodWait
            flood_wait_seconds: Duration of flood wait in seconds
            file_size: Size of file being downloaded
            task_id: Task identifier
            
        Returns:
            Alternative client if available, None otherwise
        """
        async with self._lock:
            client_id = failed_client.me.id
            
            # Mark client as in flood wait
            self.client_states[client_id] = ClientStatus.FLOOD_WAIT
            self.flood_wait_until[client_id] = time.time() + flood_wait_seconds
            
            # Remove task assignment since we're retrying
            if client_id in self.client_tasks:
                del self.client_tasks[client_id]
            
            logger.warning(f"Client @{failed_client.me.username} in FloodWait for {flood_wait_seconds}s. "
                         f"Seeking alternative for task {task_id}")
            
            # Try to find alternative client (excluding the failed one)
            file_category = FileSize.SMALL if file_size < self.small_file_threshold_bytes else FileSize.LARGE
            small_preferred, large_preferred = self._calculate_client_groups()
            
            # Remove failed client from consideration
            small_preferred = [c for c in small_preferred if c.me.id != client_id]
            large_preferred = [c for c in large_preferred if c.me.id != client_id]
            
            alternative_client = None
            
            if file_category == FileSize.SMALL:
                # Try small-preferred first, then large-preferred
                available_small = self._get_available_clients_from_group(small_preferred)
                if available_small:
                    alternative_client = self._select_client_round_robin(available_small, is_small_group=True)
                else:
                    available_large = self._get_available_clients_from_group(large_preferred)
                    if available_large:
                        alternative_client = self._select_client_round_robin(available_large, is_small_group=False)
            else:
                # Large files use large-preferred group
                available_large = self._get_available_clients_from_group(large_preferred)
                if available_large:
                    alternative_client = self._select_client_round_robin(available_large, is_small_group=False)
            
            if alternative_client:
                # Mark new client as busy
                alt_client_id = alternative_client.me.id
                self.client_states[alt_client_id] = ClientStatus.BUSY
                self.client_tasks[alt_client_id] = task_id
                
                logger.info(f"FloodWait retry: Using alternative client @{alternative_client.me.username} "
                          f"for task {task_id} (was @{failed_client.me.username})")
                return alternative_client
            
            logger.warning(f"No alternative client available for FloodWait retry of task {task_id}")
            return None
    
    async def release_client(self, client: Client, task_id: str):
        """
        Release a client back to the available pool after task completion.
        
        Args:
            client: Client to release
            task_id: Task identifier for verification
        """
        async with self._lock:
            client_id = client.me.id
            
            # Verify task assignment
            assigned_task = self.client_tasks.get(client_id)
            if assigned_task != task_id:
                logger.warning(f"Task ID mismatch when releasing client @{client.me.username}. "
                             f"Expected: {task_id}, Found: {assigned_task}")
            
            # Release client
            self.client_states[client_id] = ClientStatus.IDLE
            if client_id in self.client_tasks:
                del self.client_tasks[client_id]
            
            logger.debug(f"Released client @{client.me.username} from task {task_id}")
    
    async def get_allocation_stats(self) -> Dict:
        """Get current allocation statistics for monitoring."""
        async with self._lock:
            small_preferred, large_preferred = self._calculate_client_groups()
            
            total_clients = len(self.client_manager.all_clients)
            connected_clients = len([c for c in self.client_manager.all_clients if c and c.is_connected])
            
            idle_count = sum(1 for status in self.client_states.values() if status == ClientStatus.IDLE)
            busy_count = sum(1 for status in self.client_states.values() if status == ClientStatus.BUSY)
            flood_wait_count = len(self.flood_wait_until)
            
            return {
                "total_clients": total_clients,
                "connected_clients": connected_clients,
                "small_preferred_count": len(small_preferred),
                "large_preferred_count": len(large_preferred),
                "client_states": {
                    "idle": idle_count,
                    "busy": busy_count,
                    "flood_wait": flood_wait_count
                },
                "small_file_threshold_mb": self.small_file_threshold_bytes / 1024 / 1024,
                "active_tasks": len(self.client_tasks)
            } 