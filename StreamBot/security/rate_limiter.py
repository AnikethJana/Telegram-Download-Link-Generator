# StreamBot/security/rate_limiter.py
import time
import logging
import asyncio
from typing import Dict, Optional
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class WebRateLimiter:
    """Lightweight IP-based rate limiter for web endpoints."""
    
    def __init__(self, max_requests: int = 15, window_seconds: int = 600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(lambda: deque())
        self.last_cleanup = time.time()
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed to make request."""
        async with self._lock:
            current_time = time.time()
            
            # Auto-cleanup every 10 minutes (consolidated interval)
            if current_time - self.last_cleanup > 600:
                await self._cleanup()
                self.last_cleanup = current_time
            
            requests = self.requests[ip]
            
            # Remove old requests outside window
            while requests and requests[0] < (current_time - self.window_seconds):
                requests.popleft()
            
            # Check if under limit
            if len(requests) < self.max_requests:
                requests.append(current_time)
                return True
            
            return False
    
    async def _cleanup(self):
        """Auto cleanup to prevent memory leaks."""
        current_time = time.time()
        ips_to_remove = []
        
        for ip, requests in list(self.requests.items()):
            # Remove old requests
            while requests and requests[0] < (current_time - self.window_seconds * 2):
                requests.popleft()
            # Remove IPs with no recent requests
            if not requests:
                ips_to_remove.append(ip)
        
        for ip in ips_to_remove:
            del self.requests[ip]
        
        # Limit total tracked IPs to prevent memory issues
        if len(self.requests) > 1000:
            oldest_ips = sorted(
                self.requests.items(), 
                key=lambda x: x[1][0] if x[1] else 0
            )[:len(self.requests) - 500]
            for ip, _ in oldest_ips:
                del self.requests[ip]
    
    async def cleanup_old_entries(self):
        """Explicit cleanup method for scheduled tasks."""
        await self._cleanup()


class InvalidRequestGuard:
    """Lightweight guard against repeated invalid requests from the same IP.
    
    Consolidated with rate limiting system to reduce redundancy.
    """
    
    def __init__(self, max_invalid_per_minute: int = 20, block_duration_seconds: int = 120):
        self.max_invalid_per_minute = max_invalid_per_minute
        self.block_duration_seconds = block_duration_seconds
        self._ip_stats: Dict[str, Dict[str, float | int]] = {}
        self._last_cleanup = 0.0
        # Use same cleanup interval as WebRateLimiter (10 minutes)
        self._cleanup_interval = 600

    def _now(self) -> float:
        return time.time()

    def _cleanup(self) -> None:
        # Periodic cleanup to keep memory bounded - consolidated interval
        now = self._now()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        to_delete = []
        for ip, stats in self._ip_stats.items():
            blocked_until = stats.get('blocked_until', 0) or 0
            window_start = stats.get('window_start', 0) or 0
            # Drop entries that are long past any relevance
            if now - max(blocked_until, window_start) > 900:  # 15 minutes idle
                to_delete.append(ip)
        for ip in to_delete:
            self._ip_stats.pop(ip, None)

    def is_blocked(self, ip: str) -> bool:
        if not ip:
            return False
        self._cleanup()
        now = self._now()
        stats = self._ip_stats.get(ip)
        if not stats:
            return False
        blocked_until = stats.get('blocked_until', 0) or 0
        return now < float(blocked_until)

    def record_invalid(self, ip: str) -> None:
        if not ip:
            return
        self._cleanup()
        now = self._now()
        stats = self._ip_stats.get(ip)
        if not stats:
            stats = {'count': 0, 'window_start': now, 'blocked_until': 0}
            self._ip_stats[ip] = stats

        window_start = float(stats.get('window_start', now))
        if now - window_start > 60:
            # Reset window
            stats['count'] = 0
            stats['window_start'] = now

        stats['count'] = int(stats.get('count', 0)) + 1

        if stats['count'] >= self.max_invalid_per_minute:
            stats['blocked_until'] = now + self.block_duration_seconds
            # Reset counter to avoid repeated logging
            stats['count'] = 0
            stats['window_start'] = now
            try:
                logger.warning(f"InvalidRequestGuard: Blocking IP {ip} for {self.block_duration_seconds}s due to repeated invalid requests")
            except Exception:
                pass


class BotRateLimiter:
    """Rate limiter for bot operations (link generation)."""
    
    def __init__(self, max_links_per_day: int = 5):
        self.max_links_per_day = max_links_per_day
        self.user_timestamps: Dict[int, deque] = {}
        self._lock = asyncio.Lock()
        self.twenty_four_hours = 24 * 60 * 60
    
    async def check_and_record_link_generation(self, user_id: int) -> bool:
        """Check if user can generate a new link and record it if allowed."""
        async with self._lock:
            current_time = time.time()

            if user_id not in self.user_timestamps:
                self.user_timestamps[user_id] = deque()

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
                logger.info(f"User {user_id} rate-limited. Links in last 24h: {len(timestamps_deque)}/{self.max_links_per_day}.")
                return False

    async def get_user_link_count_and_wait_time(self, user_id: int) -> tuple[int, float]:
        """Get current link count and approximate wait time until next allowed link."""
        async with self._lock:
            current_time = time.time()
            if user_id not in self.user_timestamps:
                return 0, 0.0

            timestamps_deque = self.user_timestamps[user_id]
            
            # Clean old timestamps
            while timestamps_deque and timestamps_deque[0] < (current_time - self.twenty_four_hours):
                timestamps_deque.popleft()

            count = len(timestamps_deque)
            wait_time_seconds = 0.0
            if count >= self.max_links_per_day and self.max_links_per_day > 0 and timestamps_deque:
                oldest_link_expiry_time = timestamps_deque[0] + self.twenty_four_hours
                wait_time_seconds = max(0, oldest_link_expiry_time - current_time)

            return count, wait_time_seconds


# Global instances - initialized with default values from config
web_rate_limiter = WebRateLimiter()
bot_rate_limiter = BotRateLimiter()
invalid_request_guard = InvalidRequestGuard()

# Function to initialize with config values
def initialize_rate_limiters(max_links_per_day: int):
    """Initialize rate limiters with config values."""
    global bot_rate_limiter
    bot_rate_limiter = BotRateLimiter(max_links_per_day)
    logger.info(f"Rate limiters initialized with max_links_per_day={max_links_per_day}")

# Cleanup function for scheduler - consolidated cleanup
async def cleanup_rate_limiters():
    """Periodic cleanup of all rate limiter data."""
    try:
        await web_rate_limiter.cleanup_old_entries()
        # InvalidRequestGuard cleanup is automatic, no need to call explicitly
        logger.debug("Rate limiter cleanup completed")
    except Exception as e:
        logger.error(f"Error in rate limiter cleanup: {e}") 