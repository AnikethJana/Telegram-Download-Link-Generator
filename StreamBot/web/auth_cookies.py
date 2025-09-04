import datetime
from aiohttp import web


def set_auth_cookies(response: web.StreamResponse, session_token: str, user_id: int, max_age_seconds: int = 3600) -> None:
    """Set authentication cookies on the response.

    Cookies:
    - session_token: opaque token used by server to validate session
    - is_authenticated: string 'true' for client-side checks
    - user_id: user identifier for UI display (non-sensitive)
    """
    is_secure = False
    try:
        from StreamBot.config import Var
        is_secure = str(Var.BASE_URL).lower().startswith('https://')
    except Exception:
        is_secure = False

    cookie_kwargs = {
        'httponly': True,
        'secure': is_secure,
        'max_age': max_age_seconds,
        'samesite': 'Lax'
    }

    response.set_cookie('session_token', session_token, **cookie_kwargs)

    # is_authenticated and user_id are for convenience; not marked httponly to allow UI access
    # Keep same expiry and security attributes except httponly
    response.set_cookie('is_authenticated', 'true', secure=is_secure, max_age=max_age_seconds, samesite='Lax')
    response.set_cookie('user_id', str(user_id), secure=is_secure, max_age=max_age_seconds, samesite='Lax')


def clear_auth_cookies(response: web.StreamResponse) -> None:
    """Clear authentication cookies on the response."""
    # Expire cookies by setting max_age=0
    for name in ('session_token', 'is_authenticated', 'user_id'):
        response.del_cookie(name)


def get_session_token(request: web.Request) -> str | None:
    """Fetch session token from cookies or headers."""
    return request.cookies.get('session_token') or request.headers.get('X-Session-Token')


