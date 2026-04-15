import datetime
import logging
from typing import Any, Dict, Optional

from .database import database

logger = logging.getLogger(__name__)

# Active subscriptions / access grants (non-admin users).
#
# Schema (flexible; older docs may not have all fields):
# - _id: int (user_id)
# - created_at: datetime
# - start_at: datetime | None
# - expires_at: datetime | None (None => unlimited)
allowed_users = database["allowed_users"]

# Pending premium payment submissions.
#
# Schema:
# - _id: str (txn_id)
# - user_id: int
# - method: "crypto" | "upi"
# - selected_days: int
# - priced_days: int (subscription length; same as selected button unless logic changes)
# - amount_usd: float | None
# - amount_inr: float | None
# - status: "awaiting_paid" | "awaiting_screenshot" | "awaiting_admin" | "approved" | "rejected" | "cancelled"
# - user_snapshot: dict
# - screenshot_file_id: str | None
# - screenshot_file_unique_id: str | None
# - created_at: datetime
pending_txns = database["pending_txns"]

# Dynamic admins (users granted admin privileges via /add).
dynamic_admins = database["dynamic_admins"]


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def is_user_allowed(user_id: int) -> bool:
    """Return True if user currently has active subscription access."""
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    try:
        doc = allowed_users.find_one({"_id": user_id}, {"expires_at": 1, "start_at": 1})
        if not doc:
            return False

        expires_at = doc.get("expires_at")
        if expires_at is None:
            # Unlimited access (manual / legacy grants)
            return True

        # Mongo may store naive or aware datetimes depending on deployment.
        now = _utc_now()
        try:
            # If expires_at is naive, treat it as UTC.
            if getattr(expires_at, "tzinfo", None) is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            # If something strange happens, deny to be safe.
            return False

        return expires_at > now
    except Exception as e:
        logger.error(f"Failed checking allowed user {user_id}: {e}", exc_info=True)
        return False


async def add_allowed_user(
    user_id: int,
    *,
    start_at: Optional[datetime.datetime] = None,
    expires_at: Optional[datetime.datetime] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    """Grant access to a user, optionally with subscription expiry."""
    if not isinstance(user_id, int) or user_id <= 0:
        return False

    if start_at is not None and getattr(start_at, "tzinfo", None) is None:
        start_at = start_at.replace(tzinfo=datetime.timezone.utc)
    if expires_at is not None and getattr(expires_at, "tzinfo", None) is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

    try:
        update_doc: Dict[str, Any] = {"created_at": _utc_now()}
        if start_at is not None:
            update_doc["start_at"] = start_at
        update_doc["expires_at"] = expires_at
        if extra:
            update_doc.update(extra)

        allowed_users.update_one({"_id": user_id}, {"$set": update_doc}, upsert=True)
        return True
    except Exception as e:
        logger.error(f"Failed adding allowed user {user_id}: {e}", exc_info=True)
        return False


async def remove_allowed_user(user_id: int) -> bool:
    """Revoke access for a user."""
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    try:
        result = allowed_users.delete_one({"_id": user_id})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Failed removing allowed user {user_id}: {e}", exc_info=True)
        return False


async def revoke_expired_users() -> int:
    """Remove expired subscription users."""
    try:
        now = _utc_now()
        # Delete expired docs (expires_at <= now). Unset/None expires_at are unlimited.
        result = allowed_users.delete_many({"expires_at": {"$lte": now}})
        return int(getattr(result, "deleted_count", 0) or 0)
    except Exception as e:
        logger.error(f"Failed revoking expired users: {e}", exc_info=True)
        return 0


async def is_user_admin(user_id: int) -> bool:
    """Return True if user has been granted admin privileges via /add."""
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    try:
        return dynamic_admins.find_one({"_id": user_id}) is not None
    except Exception as e:
        logger.error(f"Failed checking admin user {user_id}: {e}", exc_info=True)
        return False


async def add_admin_user(user_id: int) -> bool:
    """Upsert user into dynamic admins."""
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    try:
        dynamic_admins.update_one(
            {"_id": user_id},
            {"$set": {"created_at": _utc_now()}},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"Failed adding admin user {user_id}: {e}", exc_info=True)
        return False


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and value > 0


async def create_pending_txn(
    *,
    txn_id: str,
    user_id: int,
    method: str,
    selected_days: int,
    priced_days: int,
    amount_usd: Optional[float],
    amount_inr: Optional[float],
    user_snapshot: Dict[str, Any],
) -> bool:
    """Create a pending transaction record."""
    if not txn_id or not isinstance(txn_id, str):
        return False
    if not _is_positive_int(user_id):
        return False
    if method not in ("crypto", "upi"):
        return False

    try:
        # Clear any existing pending records for this user that are not final.
        pending_txns.delete_many(
            {"user_id": user_id, "status": {"$in": ["awaiting_paid", "awaiting_screenshot", "awaiting_admin"]}}
        )

        pending_txns.update_one(
            {"_id": txn_id},
            {
                "$set": {
                    "user_id": user_id,
                    "method": method,
                    "selected_days": int(selected_days),
                    "priced_days": int(priced_days),
                    "amount_usd": amount_usd,
                    "amount_inr": amount_inr,
                    "status": "awaiting_paid",
                    "paid_at": None,
                    "user_snapshot": user_snapshot,
                    "screenshot_file_id": None,
                    "screenshot_file_unique_id": None,
                    "screenshot_is_photo": None,
                    "created_at": _utc_now(),
                }
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"Failed creating pending txn {txn_id}: {e}", exc_info=True)
        return False


async def set_pending_txn_paid(txn_id: str) -> bool:
    """Mark pending txn as user has paid; now we wait for screenshot."""
    try:
        res = pending_txns.update_one(
            {"_id": txn_id, "status": {"$in": ["awaiting_paid"]}},
            {"$set": {"status": "awaiting_screenshot", "paid_at": _utc_now()}},
        )
        return getattr(res, "matched_count", 0) > 0
    except Exception as e:
        logger.error(f"Failed setting txn paid {txn_id}: {e}", exc_info=True)
        return False


async def set_pending_txn_screenshot(
    txn_id: str,
    *,
    screenshot_file_id: str,
    screenshot_file_unique_id: Optional[str] = None,
    screenshot_is_photo: Optional[bool] = None,
) -> bool:
    """Store screenshot file ids for a txn."""
    try:
        res = pending_txns.update_one(
            {"_id": txn_id, "status": {"$in": ["awaiting_screenshot"]}},
            {
                "$set": {
                    "screenshot_file_id": screenshot_file_id,
                    "screenshot_file_unique_id": screenshot_file_unique_id,
                    "screenshot_is_photo": screenshot_is_photo,
                    "status": "awaiting_admin",
                }
            },
        )
        return getattr(res, "matched_count", 0) > 0
    except Exception as e:
        logger.error(f"Failed setting screenshot for txn {txn_id}: {e}", exc_info=True)
        return False


async def cancel_pending_txn(txn_id: str) -> bool:
    """Cancel a pending transaction."""
    try:
        res = pending_txns.update_one(
            {"_id": txn_id, "status": {"$in": ["awaiting_paid", "awaiting_screenshot", "awaiting_admin", "submitted_to_admin"]}},
            {"$set": {"status": "cancelled"}},
        )
        return getattr(res, "matched_count", 0) > 0
    except Exception as e:
        logger.error(f"Failed cancelling txn {txn_id}: {e}", exc_info=True)
        return False


async def get_pending_txn(txn_id: str) -> Optional[Dict[str, Any]]:
    """Get pending txn document by id."""
    try:
        return pending_txns.find_one({"_id": txn_id})
    except Exception as e:
        logger.error(f"Failed loading pending txn {txn_id}: {e}", exc_info=True)
        return None


async def get_latest_pending_txn_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get latest non-final pending txn for user."""
    try:
        return pending_txns.find_one(
            {"user_id": user_id, "status": {"$in": ["awaiting_paid", "awaiting_screenshot", "awaiting_admin", "submitted_to_admin"]}},
            sort=[("created_at", -1)],
        )
    except Exception as e:
        logger.error(f"Failed loading latest pending txn for user {user_id}: {e}", exc_info=True)
        return None


async def approve_pending_txn(txn_id: str, *, admin_id: int) -> Optional[Dict[str, Any]]:
    """Approve a pending txn and grant subscription access."""
    txn = await get_pending_txn(txn_id)
    if not txn:
        return None
    if txn.get("status") not in ("awaiting_admin", "submitted_to_admin"):
        return None

    user_id = txn.get("user_id")
    priced_days = txn.get("priced_days")
    if not _is_positive_int(user_id) or not _is_positive_int(priced_days):
        return None

    # Subscription must start only after admin/owner confirms in txn channel.
    start_at = _utc_now()
    expires_at = start_at + datetime.timedelta(days=int(priced_days))

    ok = await add_allowed_user(
        int(user_id),
        start_at=start_at,
        expires_at=expires_at,
        extra={"approved_by": admin_id, "approved_txn_id": txn_id},
    )
    if not ok:
        return None

    pending_txns.update_one({"_id": txn_id}, {"$set": {"status": "approved", "approved_at": start_at}})
    return {"user_id": user_id, "start_at": start_at, "expires_at": expires_at, "priced_days": priced_days}


async def reject_pending_txn(txn_id: str, *, admin_id: int) -> bool:
    """Reject pending txn."""
    try:
        res = pending_txns.update_one(
            {"_id": txn_id, "status": {"$in": ["awaiting_admin", "submitted_to_admin"]}},
            {"$set": {"status": "rejected", "rejected_by": admin_id, "rejected_at": _utc_now()}},
        )
        return getattr(res, "matched_count", 0) > 0
    except Exception as e:
        logger.error(f"Failed rejecting txn {txn_id}: {e}", exc_info=True)
        return False


async def mark_pending_txn_submitted(txn_id: str) -> bool:
    """Mark txn submitted to admin for review."""
    try:
        res = pending_txns.update_one(
            {"_id": txn_id, "status": {"$in": ["awaiting_admin"]}},
            {"$set": {"status": "submitted_to_admin", "submitted_at": _utc_now()}},
        )
        return getattr(res, "matched_count", 0) > 0
    except Exception as e:
        logger.error(f"Failed marking txn submitted {txn_id}: {e}", exc_info=True)
        return False

