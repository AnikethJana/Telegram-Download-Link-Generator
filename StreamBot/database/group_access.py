import datetime
import logging
from typing import Any, Dict, List
from .database import database
from ..config import Var

logger = logging.getLogger(__name__)

# Authorized groups collection in MongoDB
# Schema:
# - _id: int (chat_id)
# - title: str
# - added_by: int
# - created_at: datetime
authorized_groups = database["authorized_groups"]


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def is_group_authorized(chat_id: int) -> bool:
    """
    Check if a group chat ID is authorized to generate links.
    Returns True if chat_id is in Var.AUTHORIZED_GROUPS or stored in the database.
    """
    if not isinstance(chat_id, int):
        return False

    # Check environment variable config first
    if Var.AUTHORIZED_GROUPS and chat_id in Var.AUTHORIZED_GROUPS:
        return True

    # Check database records
    try:
        doc = authorized_groups.find_one({"_id": chat_id})
        return doc is not None
    except Exception as e:
        logger.error(f"Error checking group authorization for {chat_id}: {e}", exc_info=True)
        return False


async def add_authorized_group(chat_id: int, title: str = "", added_by: int = 0) -> bool:
    """Add a group chat ID to the authorized groups database collection."""
    if not isinstance(chat_id, int):
        return False
    try:
        authorized_groups.update_one(
            {"_id": chat_id},
            {
                "$set": {
                    "title": title or "",
                    "added_by": added_by,
                    "updated_at": _utc_now(),
                },
                "$setOnInsert": {
                    "created_at": _utc_now(),
                }
            },
            upsert=True,
        )
        logger.info(f"Authorized group {chat_id} ('{title}') added by user {added_by}.")
        return True
    except Exception as e:
        logger.error(f"Failed to add authorized group {chat_id}: {e}", exc_info=True)
        return False


async def remove_authorized_group(chat_id: int) -> bool:
    """Remove a group chat ID from the authorized groups database collection."""
    if not isinstance(chat_id, int):
        return False
    try:
        res = authorized_groups.delete_one({"_id": chat_id})
        success = getattr(res, "deleted_count", 0) > 0
        if success:
            logger.info(f"Removed group {chat_id} from authorized groups database.")
        return success
    except Exception as e:
        logger.error(f"Failed to remove authorized group {chat_id}: {e}", exc_info=True)
        return False


async def get_all_authorized_groups() -> List[Dict[str, Any]]:
    """Get list of all authorized group documents from DB and environment config."""
    groups: List[Dict[str, Any]] = []
    seen_ids = set()

    # Load from DB
    try:
        docs = list(authorized_groups.find({}))
        for doc in docs:
            groups.append(doc)
            seen_ids.add(doc["_id"])
    except Exception as e:
        logger.error(f"Failed to fetch authorized groups from DB: {e}", exc_info=True)

    # Load from config environment variable if not already in DB list
    if Var.AUTHORIZED_GROUPS:
        for gid in Var.AUTHORIZED_GROUPS:
            if gid not in seen_ids:
                groups.append({
                    "_id": gid,
                    "title": "Env Config Group",
                    "source": "env",
                    "created_at": None,
                })
                seen_ids.add(gid)

    return groups
