# StreamBot/database.py
import pymongo
import logging
from ..config import Var

logger = logging.getLogger(__name__)

# Establish MongoDB connection with security settings
try:
    # Optimized connection settings for low-resource deployment with 2-hour streams
    dbclient = pymongo.MongoClient(
        Var.DB_URI,
        serverSelectionTimeoutMS=8000,   # 8 second timeout (reduced from 10)
        connectTimeoutMS=8000,           # 8 second timeout (reduced from 10)
        socketTimeoutMS=30000,           # 30 second timeout (for long operations)
        maxPoolSize=12,                  # Reduced from 15 to save memory
        minPoolSize=1,                   # Reduced from 2 to save resources
        maxIdleTimeMS=300000             # 5 minutes idle timeout to free unused connections
    )
    
    # Test connection
    dbclient.admin.command('ping')
    
    database = dbclient[Var.DB_NAME]
    logger.info(f"Successfully connected to MongoDB database: {Var.DB_NAME}")
    
    # Create index for better performance (if not exists)
    try:
        # _id index is automatically created by MongoDB and cannot be background.
        # We ensure other potential custom indexes can be background if needed.
        # For now, only the default _id index is implicitly managed.
        # If you add other indexes, you can specify background=True for them.
        # Example: database['users'].create_index([("some_other_field", 1)], background=True)
        logger.debug("Database indexes ensured (MongoDB auto-manages _id index)")
    except Exception as e:
        logger.warning(f"Could not create database indexes: {e}")
        
except pymongo.errors.ConfigurationError as e:
     logger.critical(f"MongoDB Configuration Error: {e}. Please check DB_URI and DB_NAME in config.", exc_info=True)
     exit(f"MongoDB Configuration Error: {e}")
except pymongo.errors.ConnectionFailure as e:
     logger.critical(f"MongoDB Connection Error: {e}. Check if MongoDB server is running and accessible.", exc_info=True)
     exit(f"MongoDB Connection Error: {e}")
except pymongo.errors.ServerSelectionTimeoutError as e:
     logger.critical(f"MongoDB Server Selection Timeout: {e}. Database server unreachable.", exc_info=True)
     exit(f"MongoDB Server Selection Timeout: {e}")
except Exception as e:
    logger.critical(f"Failed to connect to MongoDB: {e}", exc_info=True)
    exit(f"Failed to connect to MongoDB: {e}")


# User collection
user_data = database['users']

async def present_user(user_id: int) -> bool:
    """Check if a user exists in the database."""
    try:
        # Input validation
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id provided: {user_id}")
            return False
            
        found = user_data.find_one({'_id': user_id})
        return bool(found)
    except Exception as e:
        logger.error(f"Error checking user presence for {user_id}: {e}", exc_info=True)
        return False

async def add_user(user_id: int):
    """Add a new user to the database."""
    # Input validation
    if not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"Invalid user_id provided for addition: {user_id}")
        return
        
    if await present_user(user_id):
        return

    try:
        user_data.insert_one({'_id': user_id})
        logger.info(f"Added new user {user_id} to the database.")
    except pymongo.errors.DuplicateKeyError:
        pass
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}", exc_info=True)


async def full_userbase() -> list[dict]:
    """Return a list of all user documents in the database."""
    try:
        # Limit result size to prevent memory issues
        user_docs = list(user_data.find({}, {'_id': 1}).limit(100000))
        return [{'user_id': doc['_id']} for doc in user_docs]
    except Exception as e:
        logger.error(f"Error retrieving full userbase: {e}", exc_info=True)
        return []

async def total_users_count() -> int:
    """Return the total number of users in the database."""
    try:
        count = user_data.count_documents({})
        return count
    except Exception as e:
        logger.error(f"Error getting total users count: {e}", exc_info=True)
        return 0


async def del_user(user_id: int):
    """Delete a user from the database."""
    try:
        # Input validation
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id provided for deletion: {user_id}")
            return
            
        result = user_data.delete_one({'_id': user_id})
        if result.deleted_count > 0:
             logger.info(f"Deleted user {user_id} from the database.")
        else:
             logger.warning(f"Attempted to delete non-existent user {user_id}.")
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}", exc_info=True)
