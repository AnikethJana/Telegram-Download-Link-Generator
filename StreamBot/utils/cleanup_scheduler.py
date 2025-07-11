import asyncio
import logging
from typing import List, Callable, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CleanupScheduler:
    """Lightweight scheduler for periodic cleanup tasks."""
    
    def __init__(self):
        self.tasks: List[asyncio.Task] = []
        self.running = False
    
    async def start(self):
        """Start all scheduled cleanup tasks."""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting cleanup scheduler...")
        
        # Schedule bandwidth cleanup (daily)
        self.tasks.append(asyncio.create_task(self._daily_bandwidth_cleanup()))
        
        # Schedule memory cleanup (every 3 hours - reduced frequency for low resources)
        self.tasks.append(asyncio.create_task(self._memory_cleanup()))
        
        # Schedule stream cleanup (every 45 minutes - less frequent on low resources)
        self.tasks.append(asyncio.create_task(self._stream_cleanup()))
        
        # Schedule security cleanup (every hour - rate limiter cleanup)
        self.tasks.append(asyncio.create_task(self._security_cleanup()))
        
        # Schedule session cleanup (every 6 hours - for session generator)
        self.tasks.append(asyncio.create_task(self._session_cleanup()))
        
        logger.info(f"Started {len(self.tasks)} cleanup tasks")
    
    async def stop(self):
        """Stop all cleanup tasks."""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping cleanup scheduler...")
        
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        logger.info("Cleanup scheduler stopped")
    
    async def _daily_bandwidth_cleanup(self):
        """Run bandwidth cleanup daily."""
        while self.running:
            try:
                await asyncio.sleep(24 * 3600)  # 24 hours
                if not self.running:
                    break
                
                logger.info("Running daily bandwidth cleanup...")
                from .bandwidth import cleanup_old_bandwidth_records
                deleted_count = await cleanup_old_bandwidth_records(keep_months=3)
                logger.info(f"Daily cleanup: removed {deleted_count} old bandwidth records")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily bandwidth cleanup: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retry
    
    async def _memory_cleanup(self):
        """Run memory cleanup every 3 hours (reduced frequency for low resources)."""
        while self.running:
            try:
                await asyncio.sleep(10800)  # 3 hours (was 2 hours)
                if not self.running:
                    break
                
                logger.debug("Running 3-hourly memory cleanup...")
                from .memory_manager import memory_manager
                await memory_manager.periodic_cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory cleanup: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes before retry
    
    async def _stream_cleanup(self):
        """Clean up completed streams every 45 minutes (reduced frequency)."""
        while self.running:
            try:
                await asyncio.sleep(2700)  # 45 minutes (was 30 minutes)
                if not self.running:
                    break
                
                logger.debug("Running stream cleanup...")
                from .stream_cleanup import stream_tracker
                await stream_tracker.cleanup_completed_streams()
                
                active_count = stream_tracker.get_active_count()
                if active_count > 3:  # Log if more than 3 active streams (reduced threshold)
                    logger.info(f"Active streams after cleanup: {active_count}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stream cleanup: {e}")
                await asyncio.sleep(900)  # Wait 15 minutes before retry

    async def _security_cleanup(self):
        """Clean up security data every hour (rate limiter cleanup)."""
        while self.running:
            try:
                await asyncio.sleep(3600)  # 1 hour
                if not self.running:
                    break
                
                logger.debug("Running security cleanup...")
                from StreamBot.security.rate_limiter import cleanup_rate_limiters
                await cleanup_rate_limiters()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in security cleanup: {e}")
                await asyncio.sleep(900)  # Wait 15 minutes before retry

    async def _session_cleanup(self):
        """Clean up inactive sessions every 6 hours."""
        while self.running:
            try:
                await asyncio.sleep(21600)  # 6 hours
                if not self.running:
                    break
                
                logger.debug("Running session cleanup...")
                from StreamBot.database.user_sessions import cleanup_old_sessions
                deleted_count = await cleanup_old_sessions(days_old=7)  # Keep sessions for 7 days
                
                if deleted_count > 0:
                    logger.info(f"Session cleanup: removed {deleted_count} old sessions")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes before retry

# Global instance
cleanup_scheduler = CleanupScheduler() 