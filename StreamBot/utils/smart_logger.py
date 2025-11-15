import logging
import asyncio
from typing import Dict
from datetime import datetime, timedelta

class SmartRateLimitedLogger:
    """Rate-limited logger with memory-safe cache management."""
    
    def __init__(self, logger, rate_limit_seconds=5, max_cache_size=1000):
        self.logger = logger
        self.rate_limit_seconds = rate_limit_seconds
        self.max_cache_size = max_cache_size
        self.last_logged: Dict[str, float] = {}
        self.last_cleanup = datetime.now()
        self.cleanup_interval = timedelta(minutes=30)  # Cleanup every 30 minutes

    def _cleanup_cache(self):
        """Remove old entries from cache to prevent memory leaks."""
        now = datetime.now()
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        current_time = asyncio.get_event_loop().time()
        # Remove entries older than 2x the rate limit
        cutoff_time = current_time - (self.rate_limit_seconds * 2)
        
        # Clean old entries
        old_keys = [key for key, timestamp in self.last_logged.items() 
                   if timestamp < cutoff_time]
        for key in old_keys:
            del self.last_logged[key]
        
        # If still too large, keep only the most recent entries
        if len(self.last_logged) > self.max_cache_size:
            sorted_items = sorted(self.last_logged.items(), key=lambda x: x[1], reverse=True)
            self.last_logged = dict(sorted_items[:self.max_cache_size])
        
        self.last_cleanup = now
        if old_keys:
            self.logger.debug(f"Cleaned {len(old_keys)} old log cache entries")

    def log(self, level, message, **kwargs):
        """Log a message with rate limiting and memory-safe cache management."""
        # Periodic cache cleanup
        self._cleanup_cache()
        
        current_time = asyncio.get_event_loop().time()
        
        # Check rate limit
        if message in self.last_logged:
            time_diff = current_time - self.last_logged[message]
            if time_diff < self.rate_limit_seconds:
                return  # Skip logging if within rate limit period
        
        # Update timestamp and log
        self.last_logged[message] = current_time
        
        # Log the message
        if level == 'debug':
            self.logger.debug(message, **kwargs)
        elif level == 'info':
            self.logger.info(message, **kwargs)
        elif level == 'warning':
            self.logger.warning(message, **kwargs)
        elif level == 'error':
            self.logger.error(message, **kwargs)
        elif level == 'critical':
            self.logger.critical(message, **kwargs)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get current cache statistics."""
        return {
            "cache_size": len(self.last_logged),
            "max_cache_size": self.max_cache_size
        } 