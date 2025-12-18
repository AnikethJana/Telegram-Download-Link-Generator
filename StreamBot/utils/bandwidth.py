# StreamBot/utils/bandwidth.py
import logging
import datetime
from typing import Optional
from StreamBot.config import Var

logger = logging.getLogger(__name__)

# Global variable to cache database connection
_bandwidth_collection = None

# Global flag to track bandwidth limit status 
_bandwidth_limit_reached = False
_last_bandwidth_check = 0  # Timestamp of last check

def reset_bandwidth_status_cache():
    """Reset cached bandwidth status (e.g., after monthly reset)."""
    global _bandwidth_limit_reached, _last_bandwidth_check
    _bandwidth_limit_reached = False
    _last_bandwidth_check = 0

def get_bandwidth_collection():
    """Get or create the bandwidth collection reference."""
    global _bandwidth_collection
    if _bandwidth_collection is None:
        try:
            from StreamBot.database.database import database
            _bandwidth_collection = database['bandwidth_usage']
            logger.info("Bandwidth collection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize bandwidth collection: {e}")
            return None
    return _bandwidth_collection

async def get_current_bandwidth_usage() -> dict:
    """Get current month's bandwidth usage and metadata."""
    collection = get_bandwidth_collection()
    if collection is None:
        return {"bytes_used": 0, "gb_used": 0.0, "month_key": "", "last_reset": None}
    
    try:
        current_month = datetime.datetime.now().strftime("%Y-%m")
        
        # Get or create current month record
        record = collection.find_one({"_id": current_month})
        if not record:
            # Create new month record
            new_record = {
                "_id": current_month,
                "bytes_used": 0,
                "created_at": datetime.datetime.utcnow(),
                "last_reset": datetime.datetime.utcnow()
            }
            collection.insert_one(new_record)
            record = new_record
            # Reset cached bandwidth status because a new month has started
            reset_bandwidth_status_cache()
        
        gb_used = record["bytes_used"] / (1024**3)  # Convert bytes to GB
        
        return {
            "bytes_used": record["bytes_used"],
            "gb_used": round(gb_used, 3),
            "month_key": current_month,
            "last_reset": record.get("last_reset"),
            "created_at": record.get("created_at")
        }
    except Exception as e:
        logger.error(f"Error getting bandwidth usage: {e}")
        return {"bytes_used": 0, "gb_used": 0.0, "month_key": "", "last_reset": None}

async def add_bandwidth_usage(bytes_count: int) -> bool:
    """Add bandwidth usage for current month."""
    if bytes_count <= 0:
        return True
    
    collection = get_bandwidth_collection()
    if collection is None:
        logger.warning("Bandwidth collection not available, skipping tracking")
        return True
    
    try:
        current_month = datetime.datetime.now().strftime("%Y-%m")
        
        # Update or create record
        result = collection.update_one(
            {"_id": current_month},
            {
                "$inc": {"bytes_used": bytes_count},
                "$setOnInsert": {
                    "created_at": datetime.datetime.utcnow(),
                    "last_reset": datetime.datetime.utcnow()
                },
                "$set": {"last_updated": datetime.datetime.utcnow()}
            },
            upsert=True
        )
        
        logger.debug(f"Added {bytes_count} bytes to bandwidth usage for {current_month}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding bandwidth usage: {e}")
        return False

async def is_bandwidth_limit_exceeded() -> bool:
    """
    Check if current bandwidth usage exceeds the configured limit.
    
    This function uses a cached global flag to avoid repeated database queries.
    Once the bandwidth limit has been reached, the flag stays True until the cache
    is reset (e.g., on monthly reset). While the limit has not been reached, the
    cache is refreshed periodically (every 60 seconds) to balance performance and
    accuracy.
    
    Returns:
        bool: True if bandwidth limit has been reached, False otherwise
    """
    global _bandwidth_limit_reached, _last_bandwidth_check
    
    if Var.BANDWIDTH_LIMIT_GB <= 0:
        _bandwidth_limit_reached = False
        return False  # No limit configured

    # If limit already reached, no need to query the database again
    if _bandwidth_limit_reached:
        return True
    
    # Check cache validity (refresh every 60 seconds)
    current_time = datetime.datetime.now().timestamp()
    cache_age = current_time - _last_bandwidth_check
    
    # Use cached value if recent (within 60 seconds)
    if cache_age < 60 and _last_bandwidth_check > 0:
        return _bandwidth_limit_reached
    
    # Refresh cache by checking database
    usage = await get_current_bandwidth_usage()
    limit_exceeded = usage["gb_used"] >= Var.BANDWIDTH_LIMIT_GB
    
    # Update global flag and timestamp
    _bandwidth_limit_reached = limit_exceeded
    _last_bandwidth_check = current_time
    
    if limit_exceeded:
        logger.warning(f"Bandwidth limit exceeded: {usage['gb_used']:.3f} GB >= {Var.BANDWIDTH_LIMIT_GB} GB")
    
    return limit_exceeded


def get_bandwidth_limit_status() -> bool:
    """
    Get the current cached bandwidth limit status without database query.
    
    This is a synchronous function that returns the cached status for use in
    command handlers and endpoints where async checks are not needed.
    
    Returns:
        bool: Current cached bandwidth limit status
    """
    global _bandwidth_limit_reached
    return _bandwidth_limit_reached

async def cleanup_old_bandwidth_records(keep_months: int = 3) -> int:
    """Clean up old bandwidth records, keeping only the specified number of months."""
    collection = get_bandwidth_collection()
    if collection is None:
        return 0
    
    try:
        # Get current month for safety
        current_month = datetime.datetime.now().strftime("%Y-%m")
        
        # Calculate cutoff date
        now = datetime.datetime.now()
        cutoff_date = (now - datetime.timedelta(days=30 * keep_months))
        cutoff_month = cutoff_date.strftime("%Y-%m")
        
        # Delete old records but NEVER delete current month
        result = collection.delete_many({
            "_id": {
                "$lt": cutoff_month,
                "$ne": current_month
            }
        })
        deleted_count = result.deleted_count
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old bandwidth records (older than {cutoff_month})")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old bandwidth records: {e}")
        return 0

async def monthly_cleanup_task():
    """Perform monthly cleanup of old bandwidth records."""
    try:
        logger.info("Starting monthly bandwidth cleanup task")
        deleted_count = await cleanup_old_bandwidth_records(keep_months=3)
        logger.info(f"Monthly cleanup completed, deleted {deleted_count} old records")
        # After cleanup, reset cached bandwidth status to ensure accurate readings
        reset_bandwidth_status_cache()
    except Exception as e:
        logger.error(f"Error in monthly cleanup task: {e}")

# Helper function to check if current month has changed (for auto-reset detection)
def get_current_month_key() -> str:
    """Get current month key in YYYY-MM format."""
    return datetime.datetime.now().strftime("%Y-%m") 