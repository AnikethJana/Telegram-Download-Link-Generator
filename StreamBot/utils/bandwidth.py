# StreamBot/utils/bandwidth.py
import logging
import datetime
from typing import Optional
from StreamBot.config import Var

logger = logging.getLogger(__name__)

# Global variable to cache database connection
_bandwidth_collection = None

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
    """Add bandwidth usage for current month. Returns True if successful."""
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
    """Check if current bandwidth usage exceeds the configured limit."""
    if Var.BANDWIDTH_LIMIT_GB <= 0:
        return False  # No limit configured
    
    usage = await get_current_bandwidth_usage()
    limit_exceeded = usage["gb_used"] >= Var.BANDWIDTH_LIMIT_GB
    
    if limit_exceeded:
        logger.warning(f"Bandwidth limit exceeded: {usage['gb_used']:.3f} GB >= {Var.BANDWIDTH_LIMIT_GB} GB")
    
    return limit_exceeded

async def cleanup_old_bandwidth_records(keep_months: int = 3) -> int:
    """Clean up old bandwidth records, keeping only the specified number of months."""
    collection = get_bandwidth_collection()
    if collection is None:
        return 0
    
    try:
        # Calculate cutoff date
        now = datetime.datetime.now()
        cutoff_date = (now - datetime.timedelta(days=30 * keep_months))
        cutoff_month = cutoff_date.strftime("%Y-%m")
        
        # Delete old records
        result = collection.delete_many({"_id": {"$lt": cutoff_month}})
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
    except Exception as e:
        logger.error(f"Error in monthly cleanup task: {e}")

# Helper function to check if current month has changed (for auto-reset detection)
def get_current_month_key() -> str:
    """Get current month key in YYYY-MM format."""
    return datetime.datetime.now().strftime("%Y-%m") 