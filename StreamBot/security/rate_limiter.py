# StreamBot/security/rate_limiter.py
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class InvalidRequestGuard:
    """Lightweight guard against repeated invalid requests from the same IP.
    
    Consolidated with rate limiting system to reduce redundancy.
    """
    
    def __init__(self, max_invalid_per_minute: int = 20, block_duration_seconds: int = 120):
        self.max_invalid_per_minute = max_invalid_per_minute
        self.block_duration_seconds = block_duration_seconds
        self._ip_stats: Dict[str, Dict[str, float | int]] = {}
        self._last_cleanup = 0.0
        # Periodic cleanup interval (10 minutes)
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

invalid_request_guard = InvalidRequestGuard()


async def cleanup_rate_limiters():
    """Periodic hook for scheduler compatibility (InvalidRequestGuard self-cleans on use)."""
    pass