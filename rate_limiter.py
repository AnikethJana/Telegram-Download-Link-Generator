# StreamBot/rate_limiter.py
import time
from collections import deque
from config import Var # To access MAX_LINKS_PER_DAY
from logger import get_logger
from exceptions import handle_async_exceptions, RateLimitError

# Get logger for this module
logger = get_logger(__name__)

# In-memory store for user link generation timestamps
# { user_id: deque([timestamp1, timestamp2, ...]), ... }
# Timestamps are floats (from time.time())
user_link_timestamps: dict[int, deque[float]] = {}


TWENTY_FOUR_HOURS_IN_SECONDS = 24 * 60 * 60

@handle_async_exceptions(fallback_return=False)
async def check_and_record_link_generation(user_id: int) -> bool:
    """
    Checks if a user can generate a new link and records it if allowed.

    Returns:
        True if the user is allowed to generate a link, False otherwise.
    """
    # async with _rate_limit_lock: # If using asyncio lock
    current_time = time.time()

    # Get or initialize the deque for the user
    if user_id not in user_link_timestamps:
        user_link_timestamps[user_id] = deque()

    timestamps_deque = user_link_timestamps[user_id]

    # Remove timestamps older than 24 hours
    # Iterate from the left (oldest timestamps)
    while timestamps_deque and timestamps_deque[0] < (current_time - TWENTY_FOUR_HOURS_IN_SECONDS):
        timestamps_deque.popleft()

    # Check if the user is under the limit
    if len(timestamps_deque) < Var.MAX_LINKS_PER_DAY:
        timestamps_deque.append(current_time)
        logger.debug(f"User {user_id} allowed. Links in last 24h: {len(timestamps_deque)}/{Var.MAX_LINKS_PER_DAY}")
        return True
    else:
        # User has reached the limit
        # Calculate remaining time until the oldest link expires
        time_until_next_link = 0
        if timestamps_deque: # Should always be true if limit is reached
            oldest_link_expiry_time = timestamps_deque[0] + TWENTY_FOUR_HOURS_IN_SECONDS
            time_until_next_link = oldest_link_expiry_time - current_time

        logger.info(f"User {user_id} rate-limited. Links in last 24h: {len(timestamps_deque)}/{Var.MAX_LINKS_PER_DAY}.")
        # Optionally, you can return the time_until_next_link if you want to inform the user.
        # For now, just returning False is sufficient.
        return False

@handle_async_exceptions(fallback_return=(0, 0.0))
async def get_user_link_count_and_wait_time(user_id: int) -> tuple[int, float]:
    """
    Gets the current link count for the user in the last 24 hours and
    the approximate wait time in seconds until their oldest link expires if they are at the limit.
    """
    current_time = time.time()
    if user_id not in user_link_timestamps:
        return 0, 0.0

    timestamps_deque = user_link_timestamps[user_id]
    # Clean old timestamps (important to do this before counting)
    while timestamps_deque and timestamps_deque[0] < (current_time - TWENTY_FOUR_HOURS_IN_SECONDS):
        timestamps_deque.popleft()

    count = len(timestamps_deque)
    wait_time_seconds = 0.0
    if count >= Var.MAX_LINKS_PER_DAY and timestamps_deque:
        oldest_link_expiry_time = timestamps_deque[0] + TWENTY_FOUR_HOURS_IN_SECONDS
        wait_time_seconds = max(0, oldest_link_expiry_time - current_time) # ensure non-negative

    return count, wait_time_seconds