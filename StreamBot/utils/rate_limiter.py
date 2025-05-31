# StreamBot/rate_limiter.py
import time
from collections import deque
from ..config import Var 
import logging
import asyncio # Import asyncio

logger = logging.getLogger(__name__)

# In-memory store for user link generation timestamps
# { user_id: deque([timestamp1, timestamp2, ...]), ... }
# Timestamps are floats (from time.time())
user_link_timestamps: dict[int, deque[float]] = {}

# Add an asyncio lock to protect the shared state
_rate_limit_lock = asyncio.Lock()

TWENTY_FOUR_HOURS_IN_SECONDS = 24 * 60 * 60

async def check_and_record_link_generation(user_id: int) -> bool:
    """Check if user can generate a new link and record it if allowed."""
    async with _rate_limit_lock:
        current_time = time.time()

        if user_id not in user_link_timestamps:
            user_link_timestamps[user_id] = deque()

        timestamps_deque = user_link_timestamps[user_id]

        # Remove timestamps older than 24 hours
        while timestamps_deque and timestamps_deque[0] < (current_time - TWENTY_FOUR_HOURS_IN_SECONDS):
            timestamps_deque.popleft()

        if len(timestamps_deque) < Var.MAX_LINKS_PER_DAY:
            timestamps_deque.append(current_time)
            logger.debug(f"User {user_id} allowed. Links in last 24h: {len(timestamps_deque)}/{Var.MAX_LINKS_PER_DAY}")
            return True
        else:
            time_until_next_link = 0
            if timestamps_deque:
                oldest_link_expiry_time = timestamps_deque[0] + TWENTY_FOUR_HOURS_IN_SECONDS
                time_until_next_link = oldest_link_expiry_time - current_time

            logger.info(f"User {user_id} rate-limited. Links in last 24h: {len(timestamps_deque)}/{Var.MAX_LINKS_PER_DAY}.")
            return False

async def get_user_link_count_and_wait_time(user_id: int) -> tuple[int, float]:
    """Get current link count and approximate wait time until next allowed link."""
    async with _rate_limit_lock:
        current_time = time.time()
        if user_id not in user_link_timestamps:
            return 0, 0.0

        timestamps_deque = user_link_timestamps[user_id]
        
        # Clean old timestamps
        while timestamps_deque and timestamps_deque[0] < (current_time - TWENTY_FOUR_HOURS_IN_SECONDS):
            timestamps_deque.popleft()

        count = len(timestamps_deque)
        wait_time_seconds = 0.0
        if count >= Var.MAX_LINKS_PER_DAY and timestamps_deque:
            oldest_link_expiry_time = timestamps_deque[0] + TWENTY_FOUR_HOURS_IN_SECONDS
            wait_time_seconds = max(0, oldest_link_expiry_time - current_time)

        return count, wait_time_seconds