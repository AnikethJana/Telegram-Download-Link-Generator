import gc
import asyncio
import logging
import psutil
import os
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MemoryManager:
    """Lightweight memory management utility for cleanup and monitoring."""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.last_cleanup = datetime.now()
        self.cleanup_interval = timedelta(hours=1)  # Cleanup every hour
        
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
                "percent": round(memory_percent, 2),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {"error": str(e)}
    
    def should_cleanup(self) -> bool:
        """Check if it's time for periodic cleanup."""
        return datetime.now() - self.last_cleanup > self.cleanup_interval
    
    async def periodic_cleanup(self):
        """Perform periodic memory cleanup tasks."""
        if not self.should_cleanup():
            return
        
        try:
            # Force garbage collection
            collected = gc.collect()
            
            # Update cleanup timestamp
            self.last_cleanup = datetime.now()
            
            memory_before = self.get_memory_usage()
            logger.info(f"Memory cleanup completed. Collected {collected} objects. "
                       f"Memory usage: {memory_before.get('rss_mb', 'N/A')} MB")
            
        except Exception as e:
            logger.error(f"Error during periodic cleanup: {e}")
    
    def log_memory_usage(self, context: str = ""):
        """Log current memory usage with context."""
        usage = self.get_memory_usage()
        if "error" not in usage:
            logger.info(f"Memory usage{' (' + context + ')' if context else ''}: "
                       f"{usage['rss_mb']} MB RSS, {usage['percent']}%")

# Global instance
memory_manager = MemoryManager() 