import datetime
import secrets
from typing import Dict, Optional


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


_ONE_TIME_TOKENS: Dict[str, dict] = {}
_DASHBOARD_SESSIONS: Dict[str, dict] = {}


def _cleanup_expired() -> None:
    now = _now()
    expired_tokens = [k for k, v in _ONE_TIME_TOKENS.items() if v.get("expires_at") <= now]
    for key in expired_tokens:
        _ONE_TIME_TOKENS.pop(key, None)

    expired_sessions = [k for k, v in _DASHBOARD_SESSIONS.items() if v.get("expires_at") <= now]
    for key in expired_sessions:
        _DASHBOARD_SESSIONS.pop(key, None)


def create_owner_one_time_token(owner_id: int, expires_minutes: int = 30) -> str:
    """Create a one-time owner dashboard token."""
    _cleanup_expired()
    token = secrets.token_urlsafe(24)
    _ONE_TIME_TOKENS[token] = {
        "owner_id": owner_id,
        "expires_at": _now() + datetime.timedelta(minutes=expires_minutes),
    }
    return token


def consume_owner_one_time_token(token: str) -> Optional[int]:
    """Consume one-time token and return owner_id if valid."""
    _cleanup_expired()
    data = _ONE_TIME_TOKENS.pop(token, None)
    if not data:
        return None
    if data.get("expires_at") <= _now():
        return None
    return data.get("owner_id")


def create_dashboard_session(owner_id: int, expires_minutes: int = 30) -> str:
    """Create a short-lived dashboard session after one-time token verification."""
    _cleanup_expired()
    sid = secrets.token_urlsafe(24)
    _DASHBOARD_SESSIONS[sid] = {
        "owner_id": owner_id,
        "expires_at": _now() + datetime.timedelta(minutes=expires_minutes),
    }
    return sid


def get_dashboard_session_owner(session_id: str) -> Optional[int]:
    """Validate dashboard session and return owner_id."""
    _cleanup_expired()
    data = _DASHBOARD_SESSIONS.get(session_id)
    if not data:
        return None
    if data.get("expires_at") <= _now():
        _DASHBOARD_SESSIONS.pop(session_id, None)
        return None
    return data.get("owner_id")
