import asyncio
import logging
import time
from typing import Set, Dict
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class StreamTracker:
    """Track and cleanup active streaming connections."""
    
    def __init__(self):
        self.active_streams: Dict[str, float] = {}  # request_id -> start_time
        self.cleanup_lock = asyncio.Lock()
        self.max_stream_age = 8400  # 2.3 hours max stream age (allowing some buffer beyond 2-hour timeout)
    
    def add_stream(self, request_id: str):
        """Add a streaming request to tracking."""
        self.active_streams[request_id] = time.time()
        logger.debug(f"Added stream {request_id}, total active: {len(self.active_streams)}")
    
    def remove_stream(self, request_id: str):
        """Remove completed stream from tracking."""
        if request_id in self.active_streams:
            del self.active_streams[request_id]
            logger.debug(f"Removed stream {request_id}, total active: {len(self.active_streams)}")
    
    async def cleanup_completed_streams(self):
        """Clean up old/stale streams."""
        async with self.cleanup_lock:
            current_time = time.time()
            stale_streams = [
                request_id for request_id, start_time in self.active_streams.items()
                if current_time - start_time > self.max_stream_age
            ]
            
            for request_id in stale_streams:
                start_time = self.active_streams.get(request_id, current_time)
                del self.active_streams[request_id]
                logger.warning(f"Cleaned up stale stream {request_id} (age: {(current_time - start_time)/3600:.1f} hours)")
            
            if stale_streams:
                logger.info(f"Cleaned up {len(stale_streams)} stale streams, {len(self.active_streams)} remaining")
    
    def get_active_count(self) -> int:
        """Get number of active streams."""
        return len(self.active_streams)
    
    async def cancel_all_streams(self):
        """Clear all tracked streams (for shutdown)."""
        async with self.cleanup_lock:
            count = len(self.active_streams)
            self.active_streams.clear()
            logger.info(f"Cleared {count} tracked streams during shutdown")

@asynccontextmanager
async def tracked_stream_response(response, stream_tracker: 'StreamTracker', request_id: str):
    """Context manager for tracked streaming responses with cleanup."""
    stream_tracker.add_stream(request_id)
    
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
        # Always remove stream regardless of success/failure/bytes transferred
        try:
            stream_tracker.remove_stream(request_id)
            logger.debug(f"Cleaned up stream for request {request_id}")
        except Exception as cleanup_error:
            logger.error(f"Error removing stream {request_id}: {cleanup_error}")
        
        # Ensure response is properly closed
        if hasattr(response, '_eof') and not response._eof:
            try:
                await response.write_eof()
            except Exception as e:
                logger.debug(f"Error closing response for {request_id}: {e}")

# Global instance
stream_tracker = StreamTracker() 