# StreamBot/database.py
import pymongo
import logging
from ..config import Var

logger = logging.getLogger(__name__)

# Establish MongoDB connection
try:
    dbclient = pymongo.MongoClient(Var.DB_URI)
    database = dbclient[Var.DB_NAME]
    logger.info(f"Successfully connected to MongoDB database: {Var.DB_NAME}")
except pymongo.errors.ConfigurationError as e:
     logger.critical(f"MongoDB Configuration Error: {e}. Please check DB_URI and DB_NAME in config.", exc_info=True)
     exit(f"MongoDB Configuration Error: {e}")
except pymongo.errors.ConnectionFailure as e:
     logger.critical(f"MongoDB Connection Error: {e}. Check if MongoDB server is running and accessible.", exc_info=True)
     exit(f"MongoDB Connection Error: {e}")
except Exception as e:
    logger.critical(f"Failed to connect to MongoDB: {e}", exc_info=True)
    exit(f"Failed to connect to MongoDB: {e}")


# User collection
user_data = database['users']

async def present_user(user_id: int) -> bool:
    """Check if a user exists in the database."""
    try:
        found = user_data.find_one({'_id': user_id})
        return bool(found)
    except Exception as e:
        logger.error(f"Error checking user presence for {user_id}: {e}", exc_info=True)
        return False

async def add_user(user_id: int):
    """Add a new user to the database."""
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
        user_docs = list(user_data.find({}, {'_id': 1}))
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
        result = user_data.delete_one({'_id': user_id})
        if result.deleted_count > 0:
             logger.info(f"Deleted user {user_id} from the database.")
        else:
             logger.warning(f"Attempted to delete non-existent user {user_id}.")
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}", exc_info=True)
