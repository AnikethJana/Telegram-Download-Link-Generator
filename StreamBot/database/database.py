# StreamBot/database.py
import pymongo
import logging
from ..config import Var # Import Var from your config
logger = logging.getLogger(__name__)

# Establish MongoDB connection
try:
    dbclient = pymongo.MongoClient(Var.DB_URI)
    database = dbclient[Var.DB_NAME]
    # Create a unique index on user ID if it doesn't exist
    # Note: This runs on startup. In larger applications, manage indexes separately.
    logger.info(f"Successfully connected to MongoDB database: {Var.DB_NAME}")
except pymongo.errors.ConfigurationError as e:
     logger.critical(f"MongoDB Configuration Error: {e}. Please check DB_URI and DB_NAME in config.", exc_info=True)
     # Depending on your app's needs, you might exit or handle this differently
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
    """Checks if a user exists in the database."""
    try:
        found = user_data.find_one({'_id': user_id})
        return bool(found)
    except Exception as e:
        logger.error(f"Error checking user presence for {user_id}: {e}", exc_info=True)
        return False # Assume not present on error to potentially allow retry/add

async def add_user(user_id: int):
    """Adds a new user to the database."""
    if await present_user(user_id):
        # logger.debug(f"User {user_id} already exists in the database.")
        return # Don't add if already present

    try:
        user_data.insert_one({'_id': user_id})
        logger.info(f"Added new user {user_id} to the database.")
    except pymongo.errors.DuplicateKeyError:
        # logger.warning(f"Attempted to add duplicate user {user_id}. Already exists.")
        pass # User likely added between check and insert, ignore
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}", exc_info=True)


async def full_userbase() -> list[int]:
    """Returns a list of all user IDs in the database."""
    try:
        user_docs = user_data.find({}, {'_id': 1}) # Only fetch the _id field
        user_ids = [doc['_id'] for doc in user_docs]
        return user_ids
    except Exception as e:
        logger.error(f"Error retrieving full userbase: {e}", exc_info=True)
        return []

async def total_users_count() -> int:
    """Returns the total number of users in the database."""
    try:
        count = user_data.count_documents({})
        return count
    except Exception as e:
        logger.error(f"Error getting total users count: {e}", exc_info=True)
        return 0 # Return 0 on error


async def del_user(user_id: int):
    """Deletes a user from the database."""
    try:
        result = user_data.delete_one({'_id': user_id})
        if result.deleted_count > 0:
             logger.info(f"Deleted user {user_id} from the database.")
        else:
             logger.warning(f"Attempted to delete non-existent user {user_id}.")

    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}", exc_info=True)
