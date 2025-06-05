# StreamBot/security/rate_limiter.py
import time
import logging
import asyncio
from typing import Dict, Optional, Tuple, Deque
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class WebRateLimiter:
    """
    Lightweight IP-based rate limiter for web endpoints,
    enhanced to handle download managers by coalescing range requests.
    """
    
    def __init__(self, 
                 max_download_sessions: int = 15, 
                 main_window_seconds: int = 600,
                 download_session_window_seconds: int = 60): # 1 minute for all parts of a single file download to start
        self.max_download_sessions = max_download_sessions  # Max new files an IP can start in main_window_seconds
        self.main_window_seconds = main_window_seconds
        self.download_session_window_seconds = download_session_window_seconds
        
        # Tracks the start times of new download sessions (new files)
        self.download_starts: Dict[str, Deque[float]] = defaultdict(lambda: deque())
        
        # Tracks active individual download sessions (IP, encoded_id) -> expiry_time
        self.active_download_parts: Dict[Tuple[str, str], float] = {}
        
        self.last_cleanup_time = time.time()
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, ip: str, encoded_id: Optional[str] = None) -> bool:
        """Check if IP is allowed to make a request.
        If encoded_id is provided, it attempts to coalesce range requests.
        """
        async with self._lock:
            current_time = time.time()
            
            # Auto-cleanup periodically (e.g., every 10 minutes)
            if current_time - self.last_cleanup_time > self.main_window_seconds: # Use main_window for cleanup frequency
                await self._cleanup_internal(current_time)
                self.last_cleanup_time = current_time
            
            if encoded_id:
                session_key = (ip, encoded_id)
                
                # Check if this is part of an already approved download session (e.g., a range request)
                if session_key in self.active_download_parts:
                    if self.active_download_parts[session_key] > current_time:
                        # Part of an active, ongoing download. Refresh its window slightly.
                        self.active_download_parts[session_key] = current_time + self.download_session_window_seconds
                        logger.debug(f"Allowing coalesced request for IP {ip}, file {encoded_id}")
                        return True
                    else:
                        # Session part expired, remove it
                        del self.active_download_parts[session_key]
                        # Fall through to treat as a new download start

                # This is a request for a new file (or first part of a file)
                # Check against the main download session limit for the IP
                ip_downloads = self.download_starts[ip]
                
                # Remove old download start timestamps outside the main window
                while ip_downloads and ip_downloads[0] < (current_time - self.main_window_seconds):
                    ip_downloads.popleft()
                
                # Check if under the main limit for new download sessions
                if len(ip_downloads) < self.max_download_sessions:
                    ip_downloads.append(current_time) # Record this new download start
                    # Register this specific file part as active
                    self.active_download_parts[session_key] = current_time + self.download_session_window_seconds
                    logger.debug(f"Allowing new download session for IP {ip}, file {encoded_id}. Count: {len(ip_downloads)}/{self.max_download_sessions}")
                    return True
                else:
                    # IP has reached its limit for starting new file downloads
                    logger.warning(f"Rate limit (new files) exceeded for IP {ip}. File {encoded_id} denied. Current: {len(ip_downloads)}/{self.max_download_sessions}")
                    return False
            else:
                # Fallback for requests without encoded_id (e.g. other endpoints, though middleware should only call for /dl/)
                # This part uses the old logic based on max_download_sessions as raw request counter
                # This might be too restrictive if other /dl/ endpoints don't pass encoded_id.
                # For now, we assume /dl/ always comes with an encoded_id from middleware.
                # If not, this part needs careful review.
                logger.warning(f"Rate limiter called for IP {ip} without encoded_id. Applying general limit.")
                ip_general_requests = self.download_starts[ip] # Re-use download_starts for simplicity, or use a separate dict
                while ip_general_requests and ip_general_requests[0] < (current_time - self.main_window_seconds):
                    ip_general_requests.popleft()
                if len(ip_general_requests) < self.max_download_sessions:
                    ip_general_requests.append(current_time)
                    return True
                return False
                
    async def _cleanup_internal(self, current_time: Optional[float] = None):
        """Internal cleanup method for expired sessions and old IPs."""
        if current_time is None:
            current_time = time.time()

        # Cleanup expired download_starts
        ips_to_remove_from_starts = []
        for ip, deq in list(self.download_starts.items()):
            while deq and deq[0] < (current_time - self.main_window_seconds * 2): # More aggressive cleanup for old IPs
                deq.popleft()
            if not deq:
                ips_to_remove_from_starts.append(ip)
        for ip in ips_to_remove_from_starts:
            if ip in self.download_starts: # Check again due to potential concurrent modification
                 del self.download_starts[ip]

        # Cleanup expired active_download_parts
        keys_to_remove_from_parts = [
            key for key, expiry in list(self.active_download_parts.items())
            if expiry < current_time
        ]
        for key in keys_to_remove_from_parts:
            if key in self.active_download_parts: # Check again
                del self.active_download_parts[key]
        
        # Limit total tracked IPs/sessions to prevent memory leaks (optional, but good practice)
        if len(self.download_starts) > 2000: # Example limit
            # Simple strategy: remove oldest IPs if too many are tracked
            sorted_ips = sorted(self.download_starts.items(), key=lambda x: x[1][0] if x[1] else 0)
            for ip, _ in sorted_ips[:len(self.download_starts) - 1000]: # Keep 1000 freshest
                del self.download_starts[ip]
        
        if len(self.active_download_parts) > 5000: # Example limit for active file parts
             # Simple strategy: remove oldest expiring parts
            sorted_parts = sorted(self.active_download_parts.items(), key=lambda x: x[1])
            for key, _ in sorted_parts[:len(self.active_download_parts) - 2500]: # Keep 2500 freshest
                 del self.active_download_parts[key]

        logger.debug(f"Rate limiter cleanup: {len(self.download_starts)} IPs, {len(self.active_download_parts)} active file parts.")
    
    async def cleanup_old_entries(self):
        """Explicit public cleanup method for scheduled tasks."""
        async with self._lock: # Ensure thread-safety for explicit calls too
            await self._cleanup_internal()


class BotRateLimiter:
    """Rate limiter for bot operations (link generation)."""
    
    def __init__(self, max_links_per_day: int = 5):
        self.max_links_per_day = max_links_per_day
        self.user_timestamps: Dict[int, Deque[float]] = defaultdict(lambda: deque())
        self._lock = asyncio.Lock()
        self.twenty_four_hours = 24 * 60 * 60
    
    async def check_and_record_link_generation(self, user_id: int) -> bool:
        """Check if user can generate a new link and record it if allowed."""
        async with self._lock:
            current_time = time.time()

            # No need to check if user_id not in self.user_timestamps, defaultdict handles it
            timestamps_deque = self.user_timestamps[user_id]

            # Remove timestamps older than 24 hours
            while timestamps_deque and timestamps_deque[0] < (current_time - self.twenty_four_hours):
                timestamps_deque.popleft()

            # If max_links_per_day is 0, consider it unlimited
            if self.max_links_per_day <= 0:
                timestamps_deque.append(current_time)
                return True
            elif len(timestamps_deque) < self.max_links_per_day:
                timestamps_deque.append(current_time)
                logger.debug(f"User {user_id} allowed. Links in last 24h: {len(timestamps_deque)}/{self.max_links_per_day}")
                return True
            else:
                logger.info(f"User {user_id} rate-limited for link generation. Links in last 24h: {len(timestamps_deque)}/{self.max_links_per_day}.")
                return False

    async def get_user_link_count_and_wait_time(self, user_id: int) -> tuple[int, float]:
        """Get current link count and approximate wait time until next allowed link."""
        async with self._lock:
            current_time = time.time()
            if user_id not in self.user_timestamps: # Check here as we are not modifying
                return 0, 0.0

            timestamps_deque = self.user_timestamps[user_id]
            
            # Clean old timestamps (important for accurate count)
            while timestamps_deque and timestamps_deque[0] < (current_time - self.twenty_four_hours):
                timestamps_deque.popleft()

            count = len(timestamps_deque)
            wait_time_seconds = 0.0
            if count >= self.max_links_per_day and self.max_links_per_day > 0 and timestamps_deque:
                oldest_link_expiry_time = timestamps_deque[0] + self.twenty_four_hours
                wait_time_seconds = max(0, oldest_link_expiry_time - current_time)

            return count, wait_time_seconds


# Global instances - initialized with default values from config
web_rate_limiter = WebRateLimiter() # Uses new default parameters
bot_rate_limiter = BotRateLimiter()

# Function to initialize with config values (only BotRateLimiter uses this now)
def initialize_rate_limiters(max_links_per_day: int):
    """Initialize rate limiters with config values."""
    global bot_rate_limiter # WebRateLimiter uses hardcoded defaults now
    bot_rate_limiter = BotRateLimiter(max_links_per_day)
    logger.info(f"BotRateLimiter initialized with max_links_per_day={max_links_per_day}")
    logger.info(f"WebRateLimiter initialized with defaults: max_download_sessions={web_rate_limiter.max_download_sessions}, main_window={web_rate_limiter.main_window_seconds}s, session_part_window={web_rate_limiter.download_session_window_seconds}s")

# Cleanup function for scheduler
async def cleanup_rate_limiters():
    """Periodic cleanup of rate limiter data."""
    try:
        await web_rate_limiter.cleanup_old_entries()
        # BotRateLimiter cleans itself up during checks, but an explicit periodic cleanup can be added if many inactive users.
        # For now, its own mechanism is likely sufficient.
        logger.debug("WebRateLimiter cleanup completed via scheduler")
    except Exception as e:
        logger.error(f"Error in scheduled rate limiter cleanup: {e}") 