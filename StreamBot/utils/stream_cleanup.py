import asyncio
import logging
import weakref
from typing import Set, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class StreamTracker:
    """Track and cleanup active streaming connections."""
    
    def __init__(self):
        self.active_streams: Set[asyncio.Task] = set()
        self.cleanup_lock = asyncio.Lock()
    
    def add_stream(self, task: asyncio.Task):
        """Add a streaming task to tracking."""
        self.active_streams.add(task)
        # Use weak reference callback to auto-cleanup when task completes
        weakref.finalize(task, self._remove_stream, task)
    
    def _remove_stream(self, task: asyncio.Task):
        """Remove completed stream from tracking."""
        self.active_streams.discard(task)
    
    async def cleanup_completed_streams(self):
        """Clean up completed or cancelled streams."""
        async with self.cleanup_lock:
            completed = {task for task in self.active_streams if task.done()}
            for task in completed:
                self.active_streams.discard(task)
                if task.cancelled():
                    logger.debug("Cleaned up cancelled stream task")
                elif task.exception():
                    logger.debug(f"Cleaned up failed stream task: {task.exception()}")
    
    def get_active_count(self) -> int:
        """Get number of active streams."""
        return len(self.active_streams)
    
    async def cancel_all_streams(self):
        """Cancel all active streams (for shutdown)."""
        async with self.cleanup_lock:
            for task in self.active_streams.copy():
                if not task.done():
                    task.cancel()
            # Wait a bit for cancellation to complete
            await asyncio.sleep(0.1)
            await self.cleanup_completed_streams()

@asynccontextmanager
async def tracked_stream_response(response, stream_tracker: 'StreamTracker', request_id: str):
    """Context manager for tracked streaming responses with cleanup."""
    task = asyncio.current_task()
    if task:
        stream_tracker.add_stream(task)
    
    try:
        logger.debug(f"Starting tracked stream for request {request_id}")
        yield response
    except asyncio.CancelledError:
        logger.debug(f"Stream cancelled for request {request_id}")
        raise
    except Exception as e:
        logger.error(f"Stream error for request {request_id}: {e}")
        raise
    finally:
        logger.debug(f"Cleaning up stream for request {request_id}")
        # Ensure response is properly closed
        if hasattr(response, '_eof') and not response._eof:
            try:
                await response.write_eof()
            except Exception as e:
                logger.debug(f"Error closing response for {request_id}: {e}")

# Global instance
stream_tracker = StreamTracker() 