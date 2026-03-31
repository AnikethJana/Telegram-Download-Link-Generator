import asyncio
import logging
from typing import List, Callable, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CleanupScheduler:
    """Lightweight scheduler for periodic cleanup tasks with consolidated intervals."""
    
    def __init__(self):
        self.tasks: List[asyncio.Task] = []
        self.running = False
    
    async def start(self):
        """Start all scheduled cleanup tasks."""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting cleanup scheduler...")
        
        # Schedule memory cleanup (every 2 hours - consolidated interval)
        self.tasks.append(asyncio.create_task(self._memory_cleanup()))
        
        # Schedule stream cleanup (every 30 minutes - standard interval)
        self.tasks.append(asyncio.create_task(self._stream_cleanup()))
        
        # Schedule security cleanup (every 10 minutes - consolidated with rate limiters)
        self.tasks.append(asyncio.create_task(self._security_cleanup()))

        # Schedule premium subscription cleanup (every 10 minutes)
        self.tasks.append(asyncio.create_task(self._subscription_cleanup()))
        
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
    
    async def _memory_cleanup(self):
        """Run memory cleanup every 2 hours (consolidated interval)."""
        while self.running:
            try:
                await asyncio.sleep(7200)  # 2 hours (consolidated from 3 hours)
                if not self.running:
                    break
                
                logger.debug("Running 2-hourly memory cleanup...")
                from .memory_manager import memory_manager
                await memory_manager.periodic_cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory cleanup: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes before retry
    
    async def _stream_cleanup(self):
        """Clean up completed streams every 30 minutes (standard interval)."""
        while self.running:
            try:
                await asyncio.sleep(1800)  # 30 minutes (standard interval)
                if not self.running:
                    break
                
                logger.debug("Running stream cleanup...")
                from .stream_cleanup import stream_tracker
                await stream_tracker.cleanup_completed_streams()
                
                active_count = stream_tracker.get_active_count()
                if active_count > 3:  # Log if more than 3 active streams
                    logger.info(f"Active streams after cleanup: {active_count}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stream cleanup: {e}")
                await asyncio.sleep(900)  # Wait 15 minutes before retry

    async def _security_cleanup(self):
        """Clean up security data every 10 minutes (consolidated with rate limiters)."""
        while self.running:
            try:
                await asyncio.sleep(600)  # 10 minutes (consolidated with rate limiter cleanup)
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

    async def _subscription_cleanup(self):
        """Revoke expired premium access periodically."""
        while self.running:
            try:
                await asyncio.sleep(600)  # 10 minutes
                if not self.running:
                    break
                from StreamBot.database.user_access import revoke_expired_users
                deleted_count = await revoke_expired_users()
                if deleted_count:
                    logger.info(f"Subscription cleanup revoked {deleted_count} expired users")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in subscription cleanup: {e}")
                await asyncio.sleep(900)

    

# Global instance
cleanup_scheduler = CleanupScheduler() 