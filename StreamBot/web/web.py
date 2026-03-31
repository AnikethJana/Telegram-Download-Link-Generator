# StreamBot/web.py
import re
import logging
import asyncio
import datetime
import os
import math
from aiohttp import web
import aiohttp_cors
import jinja2
from pyrogram import Client
from pyrogram.errors import FloodWait, FileIdInvalid, RPCError
from pyrogram.types import Message, User
import aiohttp_jinja2
from StreamBot.config import Var
# Ensure decode_message_id is imported from utils
from StreamBot.utils.utils import get_file_attr, humanbytes, decode_message_id, get_media_message
from StreamBot.utils.file_properties import parse_file_id
from StreamBot.utils.exceptions import NoClientsAvailableError # Import custom exception
from StreamBot.utils.stream_cleanup import stream_tracker, tracked_stream_response
from StreamBot.security.middleware import SecurityMiddleware
from StreamBot.security.validator import validate_range_header, sanitize_filename, get_client_ip
from StreamBot.utils.custom_dl import ByteStreamer
from StreamBot.utils.exceptions import NoClientsAvailableError
from .streaming import stream_video_route
from StreamBot.database.user_access import is_user_allowed, is_user_admin
from StreamBot.database.analytics import record_link_access, get_dashboard_data, get_link_owner_user_id, get_user_detail, get_link_events
from ..session_generator.interactive_login import interactive_login_manager
from .auth_cookies import set_auth_cookies, get_session_token
from ..security.rate_limiter import invalid_request_guard
from .dashboard_auth import consume_owner_one_time_token, create_dashboard_session, get_dashboard_session_owner

import hashlib
from typing import Optional, Dict, Any
from StreamBot.utils.smart_logger import SmartRateLimitedLogger

logger = logging.getLogger(__name__)
stream_rate_limited_logger = SmartRateLimitedLogger(logger)

routes = web.RouteTableDef()

# Favicon route to prevent 404 errors
@routes.get("/favicon.ico")
async def favicon_route(request: web.Request):
    """Serve a simple favicon to prevent 404 errors."""
    # Return a simple transparent 1x1 PNG as ICO
    favicon_data = b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x00\x00\x00\x00(\x00\x00\x00\x16\x00\x00\x00(\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00'
    return web.Response(body=favicon_data, content_type='image/x-icon')

# User session streaming is now integrated into the main download route

# Helper function to check session generator access permissions
def generate_session_token(user_id: int) -> str:
    """Generate a secure session token for user authentication."""
    import secrets
    import hashlib
    import time

    # Create a unique token with timestamp and random data
    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(16)
    token_data = f"{user_id}:{timestamp}:{random_data}"

    # Hash the token for security
    token_hash = hashlib.sha256(token_data.encode()).hexdigest()

    # Store token mapping (in production, use Redis or database)
    # For now, we'll store in a simple in-memory dict
    if not hasattr(generate_session_token, '_token_store'):
        generate_session_token._token_store = {}
        # Start cleanup task for expired tokens
        asyncio.create_task(cleanup_expired_tokens())

    # Clean up expired tokens before adding new one
    current_time = int(time.time())
    expired_tokens = [
        token for token, data in generate_session_token._token_store.items()
        if current_time > int(data['expires_at'])
    ]
    for token in expired_tokens:
        del generate_session_token._token_store[token]

    generate_session_token._token_store[token_hash] = {
        'user_id': user_id,
        'created_at': timestamp,
        'expires_at': str(int(time.time()) + 3600),  # 1 hour expiry
    }

    return token_hash

async def cleanup_expired_tokens():
    """Periodically clean up expired session tokens."""
    while True:
        try:
            await asyncio.sleep(300)  # Clean up every 5 minutes

            if hasattr(generate_session_token, '_token_store'):
                current_time = int(datetime.datetime.now().timestamp())
                expired_tokens = [
                    token for token, data in generate_session_token._token_store.items()
                    if current_time > int(data['expires_at'])
                ]
                for token in expired_tokens:
                    del generate_session_token._token_store[token]

                if expired_tokens:
                    logger.debug(f"Cleaned up {len(expired_tokens)} expired session tokens")

        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying

async def validate_session_token(token: str) -> int | None:
    """Validate session token and return user_id if valid."""
    import time

    if not hasattr(generate_session_token, '_token_store'):
        return None

    token_data = generate_session_token._token_store.get(token)
    if not token_data:
        return None

    # Check if token has expired
    current_time = int(time.time())
    if current_time > int(token_data['expires_at']):
        # Remove expired token
        del generate_session_token._token_store[token]
        return None

    return token_data['user_id']

async def check_session_generator_access(user_id: int) -> bool:
    """Return True if the user can access session generator (premium access)."""
    if not Var.ALLOW_USER_LOGIN:
        return False
    if user_id == Var.OWNER_ID:
        return True
    if Var.ADMINS and user_id in Var.ADMINS:
        return True
    if await is_user_admin(user_id):
        return True
    return await is_user_allowed(user_id)


# Request timeout for streaming operations (2 hours max)
STREAM_TIMEOUT = 7200  # 2 hours

# --- Helper: Format Uptime 
def format_uptime(start_time_dt: datetime.datetime) -> str:
    """Format the uptime into a human-readable string."""
    if start_time_dt is None:
        return "N/A"
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - start_time_dt
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    uptime_str = ""
    if days > 0:
        uptime_str += f"{days}d "
    if hours > 0:
        uptime_str += f"{hours}h "
    if minutes > 0:
        uptime_str += f"{minutes}m "
    uptime_str += f"{seconds}s"
    return uptime_str.strip() if uptime_str else "0s"


def should_render_download_landing(request: web.Request) -> bool:
    """Return True when browser users should see a landing page before download."""
    if request.query.get("download") == "1":
        return False
    if request.headers.get("Range"):
        return False

    sec_fetch_dest = (request.headers.get("Sec-Fetch-Dest") or "").lower()
    sec_fetch_mode = (request.headers.get("Sec-Fetch-Mode") or "").lower()
    accept = (request.headers.get("Accept") or "").lower()

    return (
        sec_fetch_dest == "document"
        or sec_fetch_mode == "navigate"
        or "text/html" in accept
    )


async def _user_has_download_access(user_id: int) -> bool:
    """Check if a user is privileged or has active subscription."""
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    if user_id == Var.OWNER_ID:
        return True
    if Var.ADMINS and user_id in Var.ADMINS:
        return True
    if await is_user_admin(user_id):
        return True
    return await is_user_allowed(user_id)


def _detect_file_category(file_name: str) -> str:
    """Detect file category from extension for icon display."""
    ext = (file_name.rsplit('.', 1)[-1] if '.' in file_name else '').lower()
    if ext in ('mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'wmv', 'm4v', 'ts', '3gp'):
        return 'video'
    if ext in ('mp3', 'flac', 'wav', 'aac', 'ogg', 'wma', 'm4a', 'opus'):
        return 'audio'
    if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tiff'):
        return 'image'
    if ext in ('zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'zst'):
        return 'archive'
    if ext in ('pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'rtf', 'odt'):
        return 'document'
    if ext in ('py', 'js', 'ts', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'sh', 'bat', 'c', 'cpp', 'java', 'go', 'rs'):
        return 'code'
    if ext in ('exe', 'msi', 'dmg', 'deb', 'rpm', 'apk', 'appimage'):
        return 'executable'
    return 'file'


def render_download_landing_page(*, file_name: str, file_size: int, direct_url: str) -> str:
    """Premium download landing page with animated UI."""
    safe_name = sanitize_filename(file_name or "file")
    size_text = humanbytes(file_size or 0)
    escaped_url = direct_url.replace("&", "&amp;")
    category = _detect_file_category(safe_name)
    ext = (safe_name.rsplit('.', 1)[-1] if '.' in safe_name else '').upper()

    # SVG icons per category
    icons = {
        'video': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>',
        'audio': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
        'image': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
        'archive': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg>',
        'document': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
        'code': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
        'executable': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>',
        'file': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>',
    }
    icon_svg = icons.get(category, icons['file'])

    # Accent colors per category
    accent_map = {
        'video': ('#a78bfa', '#7c3aed', 'rgba(167,139,250,0.15)'),
        'audio': ('#f472b6', '#db2777', 'rgba(244,114,182,0.15)'),
        'image': ('#34d399', '#059669', 'rgba(52,211,153,0.15)'),
        'archive': ('#fbbf24', '#d97706', 'rgba(251,191,36,0.15)'),
        'document': ('#60a5fa', '#2563eb', 'rgba(96,165,250,0.15)'),
        'code': ('#a3e635', '#65a30d', 'rgba(163,230,53,0.15)'),
        'executable': ('#fb923c', '#ea580c', 'rgba(251,146,60,0.15)'),
        'file': ('#94a3b8', '#64748b', 'rgba(148,163,184,0.15)'),
    }
    accent1, accent2, accent_bg = accent_map.get(category, accent_map['file'])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Download — {safe_name}</title>
  <meta name="description" content="Download {safe_name} ({size_text}) — secure direct download link."/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
    :root {{
      --bg: #06080f;
      --surface: rgba(255,255,255,0.04);
      --surface-hover: rgba(255,255,255,0.07);
      --border: rgba(255,255,255,0.08);
      --border-accent: rgba(255,255,255,0.12);
      --text: #f1f5f9;
      --text-secondary: #94a3b8;
      --text-tertiary: #64748b;
      --accent1: {accent1};
      --accent2: {accent2};
      --accent-bg: {accent_bg};
      --radius-lg: 24px;
      --radius-md: 16px;
      --radius-sm: 12px;
    }}
    html {{ scroll-behavior:smooth; }}
    body {{
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      padding: 20px;
      overflow: hidden;
      background: var(--bg);
    }}
    /* Animated gradient background */
    .bg-gradient {{
      position: fixed;
      inset: 0;
      z-index: 0;
      background:
        radial-gradient(ellipse 80% 60% at 20% 10%, {accent_bg}, transparent),
        radial-gradient(ellipse 60% 50% at 80% 80%, rgba(99,102,241,0.08), transparent),
        radial-gradient(ellipse 50% 40% at 50% 50%, rgba(15,23,42,0.5), transparent);
      animation: bgPulse 8s ease-in-out infinite alternate;
    }}
    @keyframes bgPulse {{
      0% {{ opacity:0.7; transform:scale(1); }}
      100% {{ opacity:1; transform:scale(1.05); }}
    }}
    /* Floating particles */
    .particles {{
      position:fixed; inset:0; z-index:0; overflow:hidden; pointer-events:none;
    }}
    .particles span {{
      position:absolute; display:block; width:2px; height:2px;
      background: var(--accent1); border-radius:50%; opacity:0;
      animation: floatUp linear infinite;
    }}
    @keyframes floatUp {{
      0% {{ opacity:0; transform:translateY(100vh) scale(0); }}
      10% {{ opacity:0.6; }}
      90% {{ opacity:0.3; }}
      100% {{ opacity:0; transform:translateY(-10vh) scale(1); }}
    }}
    .container {{
      position: relative;
      z-index: 1;
      width: min(520px, 100%);
      animation: slideUp 0.6s cubic-bezier(0.16,1,0.3,1) forwards;
      opacity: 0;
      transform: translateY(30px);
    }}
    @keyframes slideUp {{
      to {{ opacity:1; transform:translateY(0); }}
    }}
    /* Main card with glassmorphism */
    .card {{
      background: linear-gradient(165deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 36px 32px 32px;
      backdrop-filter: blur(40px) saturate(1.4);
      -webkit-backdrop-filter: blur(40px) saturate(1.4);
      box-shadow:
        0 32px 64px -12px rgba(0,0,0,0.5),
        0 0 0 1px rgba(255,255,255,0.05),
        inset 0 1px 0 rgba(255,255,255,0.06);
      position: relative;
      overflow: hidden;
    }}
    .card::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
    }}
    /* File icon area */
    .file-icon-wrapper {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 28px;
    }}
    .file-icon {{
      width: 56px; height: 56px;
      border-radius: var(--radius-md);
      background: var(--accent-bg);
      border: 1px solid rgba(255,255,255,0.06);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--accent1);
      flex-shrink: 0;
      position: relative;
      animation: iconPulse 3s ease-in-out infinite;
    }}
    .file-icon svg {{ width: 26px; height: 26px; }}
    @keyframes iconPulse {{
      0%,100% {{ box-shadow: 0 0 0 0 var(--accent-bg); }}
      50% {{ box-shadow: 0 0 20px 4px var(--accent-bg); }}
    }}
    .file-badge {{
      position: absolute;
      bottom: -4px; right: -4px;
      background: var(--accent2);
      color: white;
      font-size: 8px;
      font-weight: 700;
      padding: 2px 5px;
      border-radius: 6px;
      letter-spacing: 0.04em;
      line-height: 1;
    }}
    .file-icon-info {{ flex: 1; min-width: 0; }}
    .file-category {{
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--accent1);
      margin-bottom: 4px;
    }}
    .file-size-tag {{
      font-size: 13px;
      color: var(--text-secondary);
      font-weight: 500;
    }}
    /* File name */
    .file-name {{
      font-size: clamp(20px, 3.5vw, 28px);
      font-weight: 700;
      line-height: 1.25;
      word-break: break-word;
      margin-bottom: 24px;
      letter-spacing: -0.02em;
    }}
    /* Meta grid */
    .meta-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 28px;
    }}
    .meta-item {{
      padding: 14px 16px;
      border-radius: var(--radius-sm);
      background: var(--surface);
      border: 1px solid var(--border);
      transition: all 0.2s ease;
    }}
    .meta-item:hover {{
      background: var(--surface-hover);
      border-color: var(--border-accent);
    }}
    .meta-label {{
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--text-tertiary);
      margin-bottom: 6px;
    }}
    .meta-value {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
      word-break: break-all;
    }}
    /* Download button */
    .dl-btn {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      height: 54px;
      border: none;
      border-radius: var(--radius-md);
      font-family: inherit;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      color: #fff;
      background: linear-gradient(135deg, var(--accent2) 0%, var(--accent1) 100%);
      position: relative;
      overflow: hidden;
      transition: transform 0.15s ease, box-shadow 0.2s ease;
      box-shadow: 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.15);
    }}
    .dl-btn:hover {{
      transform: translateY(-2px);
      box-shadow: 0 8px 30px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.2);
    }}
    .dl-btn:active {{ transform: translateY(0); }}
    .dl-btn svg {{ width:18px; height:18px; flex-shrink:0; }}
    /* Ripple effect */
    .dl-btn::after {{
      content: '';
      position: absolute;
      inset: 0;
      background: radial-gradient(circle at var(--x,50%) var(--y,50%), rgba(255,255,255,0.25), transparent 60%);
      opacity: 0;
      transition: opacity 0.3s;
    }}
    .dl-btn:hover::after {{ opacity:1; }}
    /* Secondary button */
    .back-btn {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      height: 46px;
      margin-top: 10px;
      border-radius: var(--radius-sm);
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      color: var(--text-secondary);
      background: var(--surface);
      border: 1px solid var(--border);
      transition: all 0.2s ease;
    }}
    .back-btn:hover {{
      background: var(--surface-hover);
      color: var(--text);
      border-color: var(--border-accent);
    }}
    .back-btn svg {{ width:14px; height:14px; }}
    /* Footer hint */
    .hint {{
      margin-top: 20px;
      text-align: center;
      font-size: 12px;
      color: var(--text-tertiary);
      line-height: 1.6;
    }}
    .hint svg {{ width:12px; height:12px; vertical-align:-2px; margin-right:4px; opacity:0.6; }}
    /* Responsive */
    @media (max-width: 480px) {{
      .card {{ padding: 24px 20px 20px; border-radius: 20px; }}
      .meta-grid {{ grid-template-columns: 1fr; }}
      .file-icon {{ width: 48px; height: 48px; }}
      .file-icon svg {{ width: 22px; height: 22px; }}
    }}
  </style>
</head>
<body>
  <div class="bg-gradient"></div>
  <div class="particles" id="particles"></div>
  <div class="container">
    <div class="card">
      <div class="file-icon-wrapper">
        <div class="file-icon">
          {icon_svg}
          <span class="file-badge">{ext}</span>
        </div>
        <div class="file-icon-info">
          <div class="file-category">{category} file</div>
          <div class="file-size-tag">{size_text}</div>
        </div>
      </div>
      <h1 class="file-name">{safe_name}</h1>
      <div class="meta-grid">
        <div class="meta-item">
          <div class="meta-label">File Name</div>
          <div class="meta-value">{safe_name}</div>
        </div>
        <div class="meta-item">
          <div class="meta-label">File Size</div>
          <div class="meta-value">{size_text}</div>
        </div>
        <div class="meta-item">
          <div class="meta-label">Format</div>
          <div class="meta-value">{ext if ext else 'Unknown'}</div>
        </div>
        <div class="meta-item">
          <div class="meta-label">Category</div>
          <div class="meta-value" style="text-transform:capitalize">{category}</div>
        </div>
      </div>
      <a id="dlBtn" class="dl-btn" href="{escaped_url}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Download Now
      </a>
      <a class="back-btn" href="javascript:history.back()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        Go Back
      </a>
      <div class="hint">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
        Click the button above to begin your download. This is a preview page.
      </div>
    </div>
  </div>
  <script>
    // Particles
    (function(){{
      const c=document.getElementById('particles');
      for(let i=0;i<20;i++){{
        const s=document.createElement('span');
        s.style.left=Math.random()*100+'%';
        s.style.animationDuration=(6+Math.random()*8)+'s';
        s.style.animationDelay=Math.random()*6+'s';
        s.style.width=s.style.height=(1+Math.random()*2)+'px';
        c.appendChild(s);
      }}
    }})();
    // Ripple follow
    const btn=document.getElementById('dlBtn');
    btn.addEventListener('mousemove',e=>{{
      const r=btn.getBoundingClientRect();
      btn.style.setProperty('--x',((e.clientX-r.left)/r.width*100)+'%');
      btn.style.setProperty('--y',((e.clientY-r.top)/r.height*100)+'%');
    }});
  </script>
</body>
</html>"""

# get_media_message function moved to utils.py to avoid circular imports

# --- Download Route (Fixed streaming error) ---
@routes.get("/dl/{encoded_id_str}")
async def download_route(request: web.Request):
    """Handle file download requests with range support."""
    client_manager = request.app.get('client_manager')
    if not client_manager:
        logger.error("ClientManager not found in web app state.")
        raise web.HTTPServiceUnavailable(text="Service configuration error.")

    start_time_request = asyncio.get_event_loop().time()

    encoded_id = request.match_info['encoded_id_str']
    
    # Fast path: guard against abusive invalid requests by IP
    client_ip = get_client_ip(request)
    if invalid_request_guard.is_blocked(client_ip):
        raise web.HTTPTooManyRequests(text="Too many invalid requests. Try again later.")

    # Enhanced input validation
    if not encoded_id or len(encoded_id) > 100:  # Reasonable length limit
        logger.warning(f"Invalid encoded ID format from {client_ip}: {encoded_id[:50]}...")
        invalid_request_guard.record_invalid(client_ip)
        raise web.HTTPBadRequest(text="Invalid download link format.")
    
    message_id = decode_message_id(encoded_id)

    if message_id is None:
        logger.warning(f"Download request with invalid or undecodable ID: {encoded_id[:50]} from {client_ip}")
        invalid_request_guard.record_invalid(client_ip)
        raise web.HTTPBadRequest(text="Invalid or malformed download link.")

    logger.info(f"Download request for decoded message_id: {message_id} (encoded: {encoded_id[:20]}...) from {get_client_ip(request)}")

    try:
        # Check if this is a user session file (virtual message ID)
        is_user_session = isinstance(message_id, str) and message_id.startswith('user_')
        if is_user_session:
            # Handle user session file - anyone with the link can download
            # This is intentional: users can share their generated links with others
            bot_client = request.app['bot_client']
            if not hasattr(bot_client, 'user_session_files') or message_id not in bot_client.user_session_files:
                invalid_request_guard.record_invalid(client_ip)
                raise web.HTTPNotFound(text="File not found or expired.")
            
            session_info = bot_client.user_session_files[message_id]

            # Subscription/admin gating for streamed private content
            if not await _user_has_download_access(int(session_info["user_id"])):
                raise web.HTTPUnauthorized(text="Premium required. Please renew your subscription.")

            # Get user's client for streaming
            from StreamBot.link_handler import user_session_streamer
            user_client = await user_session_streamer.get_user_client(session_info['user_id'])
            if not user_client:
                raise web.HTTPUnauthorized(text="User session expired. Please login again.")
            
            # Get the actual message from user's session
            media_msg = await user_client.get_messages(
                chat_id=session_info['chat_id'], 
                message_ids=session_info['message_id']
            )
            if not media_msg or not media_msg.media:
                invalid_request_guard.record_invalid(client_ip)
                raise web.HTTPNotFound(text="File not found or no longer available.")
            
            # Use user's client for streaming
            streamer_client = user_client
            logger.debug(f"Using user session client for streaming user file: {message_id}")
            # Create a ByteStreamer for the user's client (not managed by ClientManager)
            byte_streamer = ByteStreamer(streamer_client)
            
        else:
            # For regular generated links, enforce owner subscription/admin status if owner is known.
            link_owner_id = await get_link_owner_user_id(encoded_id)
            if link_owner_id is not None and not await _user_has_download_access(link_owner_id):
                raise web.HTTPUnauthorized(text="This link is no longer active.")

            # Handle regular forwarded file
            # Add timeout to prevent hanging requests - increased for large file support
            streamer_client = await asyncio.wait_for(
                client_manager.get_streaming_client(),
                timeout=60  # Increased from 30 to 60 seconds for large file handling
            )
            if not streamer_client or not getattr(streamer_client, "is_connected", False):
                logger.error(f"Failed to obtain a connected streaming client for message_id {message_id}")
                raise web.HTTPServiceUnavailable(text="Service temporarily overloaded. Please try again shortly.")
            logger.debug(f"Using client @{streamer_client.me.username} for streaming message_id {message_id}")
            # Fetch the media message from the log channel using bot/worker client
            media_msg = await get_media_message(streamer_client, message_id)
            # Get ByteStreamer instance for the client from ClientManager
            byte_streamer = client_manager.get_streamer_for_client(streamer_client)
            if not byte_streamer:
                logger.error(f"No ByteStreamer found for client @{streamer_client.me.username}")
                raise web.HTTPInternalServerError(text="Streaming service not available.")
    except asyncio.TimeoutError:
        logger.error(f"Timeout getting streaming client for message_id {message_id}")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable.")
    except (web.HTTPNotFound, web.HTTPServiceUnavailable, web.HTTPTooManyRequests, web.HTTPGone, web.HTTPInternalServerError) as e:
        logger.warning(f"Error during get_media_message for {message_id}: {type(e).__name__}")
        raise e
    except NoClientsAvailableError as e:
        logger.error(f"No clients available for streaming message_id {message_id}: {e}")
        raise web.HTTPServiceUnavailable(text="Service temporarily overloaded. Please try again later.")
    except Exception as e: # Catch any other unexpected error from get_media_message
        logger.error(f"Unexpected error from get_media_message for {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Internal server error occurred.")

    # Use ByteStreamer to get file properties (similar to WebStreamer approach)
    try:
        if is_user_session:
            # For user session files, derive FileId directly from the fetched message
            file_id = await parse_file_id(media_msg)
            if not file_id:
                raise FileNotFoundError("Unable to parse file id from user session message")
        else:
            # For regular files in log channel, get properties by message_id
            file_id = await byte_streamer.get_file_properties(message_id)
    except FileNotFoundError:
        logger.error(f"File properties not found for message {message_id}")
        raise web.HTTPNotFound(text="File not found or has been deleted.")
    except Exception as e:
        logger.error(f"Error getting file properties for message {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Failed to get file details.")

    # Extract file information using get_file_attr (proper filename handling)
    file_id_str, file_name, file_size, file_mime_type, file_unique_id = get_file_attr(media_msg)

    if not file_name:
        logger.warning(f"No filename could be determined for message {message_id}")
        file_name = f"file_{message_id}"

    # Sanitize filename for security
    safe_filename = sanitize_filename(file_name)

    if should_render_download_landing(request):
        landing_url = f"{request.path}?download=1"
        return web.Response(
            text=render_download_landing_page(
                file_name=safe_filename,
                file_size=file_size,
                direct_url=landing_url,
            ),
            content_type="text/html",
        )

    # Validate file size
    if file_size == 0:
        logger.warning(f"File size is 0 for message {message_id}")
        # Don't raise error, let it proceed for 0-byte files


    headers = {
        'Content-Type': file_mime_type or 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{safe_filename}"',
        'Accept-Ranges': 'bytes'
    }

    range_header = request.headers.get('Range')
    status_code = 200
    start_offset = 0
    end_offset = file_size - 1 if file_size > 0 else 0 # Handle 0-byte files for end_offset
    is_range_request = False

    if range_header:
        logger.info(f"Range header for {message_id}: '{range_header}', File size: {humanbytes(file_size)}")
        
        # Use secure range validation
        range_result = validate_range_header(range_header, file_size)
        if range_result is None:
            logger.error(f"Invalid Range header '{range_header}' for file size {file_size}")
            raise web.HTTPRequestRangeNotSatisfiable(headers={'Content-Range': f'bytes */{file_size}'})
        
        start_offset, end_offset = range_result
        headers['Content-Range'] = f'bytes {start_offset}-{end_offset}/{file_size}'
        headers['Content-Length'] = str(end_offset - start_offset + 1)
        status_code = 206
        is_range_request = True
        logger.info(f"Serving range request for {message_id}: bytes {start_offset}-{end_offset}/{file_size}. Content-Length: {headers['Content-Length']}")

    else:
        headers['Content-Length'] = str(file_size)
        logger.info(f"Serving full download for {message_id}. File size: {humanbytes(file_size)}. Content-Length: {headers['Content-Length']}")

    response = web.StreamResponse(status=status_code, headers=headers)
    await response.prepare(request)

    bytes_streamed = 0
    stream_start_time = asyncio.get_event_loop().time()
    max_retries_stream = 2
    current_retry_stream = 0



    # Handle 0-byte file case: if length is 0, don't try to stream.
    if (end_offset - start_offset + 1) == 0 and file_size == 0 and status_code in [200, 206]:
        logger.info(f"Serving 0-byte file {message_id}. No data to stream.")
        # Response already prepared with Content-Length: 0. Just return.
        return response

    # Calculate streaming parameters based on WebStreamer approach
    chunk_size = 1024 * 1024  # 1MB chunks
    until_bytes = min(end_offset, file_size - 1)
    offset = start_offset - (start_offset % chunk_size)
    first_part_cut = start_offset - offset
    last_part_cut = until_bytes % chunk_size + 1
    part_count = math.ceil((until_bytes + 1) / chunk_size) - math.floor(offset / chunk_size)

    logger.debug(f"Preparing WebStreamer-style streaming for {message_id}. Range: {start_offset}-{end_offset}, Offset: {offset}, Parts: {part_count}")

    # Use stream tracking context manager for proper cleanup
    request_id = f"{message_id}_{encoded_id[:10]}"
    async with tracked_stream_response(response, stream_tracker, request_id):
        while current_retry_stream <= max_retries_stream:
            try:
                # Use WebStreamer-style streaming with ByteStreamer
                try:
                    # CRITICAL: Calculate remaining bytes to stream based on what we've already sent
                    # This ensures proper resumption after client switches
                    remaining_start_offset = start_offset + bytes_streamed
                    remaining_bytes = (end_offset - remaining_start_offset + 1)
                    
                    if remaining_bytes <= 0:
                        # Already streamed everything
                        logger.info(f"All bytes already streamed for {message_id}. Total: {humanbytes(bytes_streamed)}")
                        break
                    
                    # Recalculate streaming parameters for remaining data (memory-efficient)
                    remaining_offset = remaining_start_offset - (remaining_start_offset % chunk_size)
                    remaining_first_part_cut = remaining_start_offset - remaining_offset
                    remaining_until_bytes = min(end_offset, file_size - 1)
                    remaining_last_part_cut = remaining_until_bytes % chunk_size + 1
                    remaining_part_count = math.ceil((remaining_until_bytes + 1) / chunk_size) - math.floor(remaining_offset / chunk_size)
                    
                    if bytes_streamed > 0:
                        logger.debug(f"Resuming stream for {message_id}. Already sent: {humanbytes(bytes_streamed)}, Remaining: {humanbytes(remaining_bytes)}")
                    
                    # Create the streaming coroutine using ByteStreamer
                    async def stream_data():
                        async for chunk in byte_streamer.yield_file(
                            file_id,
                            remaining_offset,
                            remaining_first_part_cut,
                            remaining_last_part_cut,
                            remaining_part_count,
                            chunk_size
                        ):
                            try:
                                await response.write(chunk)
                                nonlocal bytes_streamed
                                bytes_streamed += len(chunk)
                            except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError) as client_e:
                                stream_rate_limited_logger.log(
                                    'warning',
                                    f"Client connection issue during write for {message_id}: {type(client_e).__name__}. Streamed {humanbytes(bytes_streamed)}.",
                                    key="download.client_connection_issue"
                                )
                                return
                            except Exception as write_e:
                                stream_rate_limited_logger.log(
                                    'error',
                                    f"Error writing chunk for {message_id}: {write_e}",
                                    key="download.chunk_write_error",
                                    exc_info=True
                                )
                                return
                    
                    # Apply timeout to the entire streaming operation
                    await asyncio.wait_for(stream_data(), timeout=STREAM_TIMEOUT)
                    
                except asyncio.TimeoutError:
                    logger.error(f"Stream timeout for {message_id} after {STREAM_TIMEOUT}s")
                    if bytes_streamed == 0:
                        raise web.HTTPGatewayTimeout(text="Request timeout. Please try again.")
                    break

                logger.info(f"Successfully finished WebStreamer-style streaming for {message_id}.")
                break # Exit retry loop on successful completion

            except FloodWait as e:
                 logger.warning(f"FloodWait during stream for {message_id} on client @{streamer_client.me.username}. FloodWait: {e.value}s. Already streamed: {humanbytes(bytes_streamed)}. Attempting to get alternative client...")
                 
                 # Try to get a different client instead of waiting
                 try:
                     alternative_client = await client_manager.get_alternative_streaming_client(streamer_client)
                     if alternative_client:
                         logger.info(f"Switching from @{streamer_client.me.username} to @{alternative_client.me.username} for {message_id} due to FloodWait. Will resume from byte {bytes_streamed}")
                         streamer_client = alternative_client
                         # Update ByteStreamer instance for new client
                         byte_streamer = client_manager.get_streamer_for_client(streamer_client)
                         if not byte_streamer:
                             logger.error(f"No ByteStreamer found for alternative client @{streamer_client.me.username}")
                             break
                         
                         # IMPORTANT: file_id remains the same (same file from LOG_CHANNEL)
                         # Just continue the loop to resume streaming with new client from where we left off
                         await asyncio.sleep(1)
                         continue  # Resume with new client
                     else:
                         logger.warning(f"No alternative clients available for {message_id}. Waiting {e.value}s for FloodWait on @{streamer_client.me.username}")
                         await asyncio.sleep(min(e.value + 2, 60))  # Cap wait time at 60s
                         continue  # Retry with same client after waiting
                 except Exception as client_e:
                     logger.warning(f"Error getting alternative client for {message_id}: {client_e}. Falling back to waiting.")
                     await asyncio.sleep(min(e.value + 2, 60))  # Cap wait time at 60s
                     continue  # Retry after waiting
                 
                 # Continue to the next iteration of the while loop (retry with potentially different client)

            except (ConnectionError, TimeoutError, RPCError) as e: # Catches other RPC errors
                 current_retry_stream += 1
                 logger.warning(f"Stream interrupted for {message_id} (Attempt {current_retry_stream}/{max_retries_stream+1}): {type(e).__name__}")
                 if current_retry_stream > max_retries_stream:
                      logger.error(f"Max retries reached for stream error. Aborting stream for {message_id} after {humanbytes(bytes_streamed)} bytes.")
                      break
                 await asyncio.sleep(2 * current_retry_stream)
                 logger.info(f"Retrying stream for {message_id} from offset {start_offset}.")
            except Exception as e:
                 logger.error(f"Unexpected error during WebStreamer-style streaming for {message_id}: {e}", exc_info=True)
                 return response

    stream_duration = asyncio.get_event_loop().time() - stream_start_time
    expected_bytes_to_serve = (end_offset - start_offset + 1)

    if bytes_streamed == expected_bytes_to_serve:
        logger.info(f"Finished streaming {humanbytes(bytes_streamed)} for {message_id} in {stream_duration:.2f}s. Expected: {humanbytes(expected_bytes_to_serve)}.")
    else:
        stream_rate_limited_logger.log(
            'warning',
            f"Stream for {message_id} ended. Expected to serve {humanbytes(expected_bytes_to_serve)}, actually sent {humanbytes(bytes_streamed)} in {stream_duration:.2f}s.",
            key="download.stream_ended_unexpected_bytes"
        )

    total_request_duration = asyncio.get_event_loop().time() - start_time_request
    logger.info(f"Download request for {message_id} completed. Total duration: {total_request_duration:.2f}s")
    try:
        await record_link_access(
            encoded_id=encoded_id,
            request_path=request.path,
            ip=client_ip,
            user_agent=request.headers.get("User-Agent", ""),
            bytes_served=bytes_streamed,
        )
    except Exception as analytics_e:
        logger.warning(f"Failed to record analytics for {encoded_id}: {analytics_e}")
    return response



# --- Setup Web App ---
async def setup_webapp(bot_instance: Client, client_manager, start_time: datetime.datetime):
    # Create app with security middleware
    app = web.Application(middlewares=SecurityMiddleware.get_middlewares())

    # Store bot instance and client manager
    app['bot_client'] = bot_instance
    app['client_manager'] = client_manager
    # Store both keys for compatibility with existing code paths
    app['bot_start_time'] = start_time
    app['start_time'] = start_time
    
    # Cache bot metadata for redirects
    bot_username = None
    try:
        bot_me = getattr(bot_instance, "me", None) or await bot_instance.get_me()
        bot_username = getattr(bot_me, "username", None)
    except Exception as e:
        logger.warning(f"Unable to fetch bot username for redirects: {e}")
    app["bot_username"] = bot_username

    # Add routes
    app.add_routes(routes)
    
    # Configure CORS
    if Var.CORS_ALLOWED_ORIGINS:
        logger.info(f"CORS enabled for origins: {Var.CORS_ALLOWED_ORIGINS}")
        cors = aiohttp_cors.setup(app, defaults={
            origin: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS"],
            ) for origin in Var.CORS_ALLOWED_ORIGINS
        })
        for route in list(app.router.routes()):
            try:
                cors.add(route)
            except ValueError as exc:
                route_name = getattr(route, "name", None) or getattr(route.resource, "canonical", None) or str(route.resource)
                logger.warning(f"Skipping CORS binding for route '{route_name}': {exc}")
    else:
        logger.warning("CORS_ALLOWED_ORIGINS is not set. The Telegram login widget may not work on external domains.")

    # Setup Jinja2 templates
    template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../session_generator/templates")
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_path))

    # Setup static files for session generator with caching
    static_path = os.path.join(os.path.dirname(__file__), '..', 'session_generator', 'static')
    if os.path.exists(static_path):
        app.router.add_static(
            '/session/static',
            static_path,
            name='session_static',
            show_index=False,  # Security: don't show directory listings
            follow_symlinks=False  # Security: don't follow symlinks
        )
        logger.info(f"Static files configured for session generator at: {static_path}")
    
    logger.info("Web application routes configured with security middleware.")
    return app

# Add these routes after the existing routes
@routes.get("/stream/{encoded_id_str}")
async def stream_route(request: web.Request):
    """Route handler for video streaming."""
    return await stream_video_route(request)

# --- Session Generator Routes ---
@routes.get("/session")
async def session_generator_route(request: web.Request):
    """Session generator main page route."""
    from aiohttp_jinja2 import render_template

    bot_client: Client = request.app['bot_client']
    
    # If already authenticated via cookie and has session, go to success page
    try:
        session_token = get_session_token(request)
        if session_token:
            user_id = await validate_session_token(session_token)
            if user_id:
                from StreamBot.database.user_sessions import get_user_session_info
                user_info = await get_user_session_info(user_id)
                if user_info:
                    return web.HTTPFound('/session/success')
    except Exception:
        pass
    
    # Get bot username for Telegram Login Widget
    bot_username = None
    bot_id = None
    try:
        if bot_client and hasattr(bot_client, 'me') and bot_client.me:
            bot_username = bot_client.me.username
            bot_id = bot_client.me.id
    except Exception as e:
        logger.warning(f"Could not get bot info for session generator: {e}")
    
    context = {
        'bot_username': bot_username,
        'bot_id': bot_id,
        'base_url': Var.BASE_URL,
        'app_name': 'Telegram Session Generator',
        'allow_user_login': Var.ALLOW_USER_LOGIN,
        'login_restricted': not Var.ALLOW_USER_LOGIN
    }
    
    return render_template('index.html', request, context)

#l Slupport trailing slash by redirecting to canonical path
@routes.get("/session/")
async def session_generator_route_slash(request: web.Request):
    return web.HTTPFound('/session')

@routes.get("/session/login")
async def session_login_route(request: web.Request):
    """Route to display the interactive login form."""
    from aiohttp_jinja2 import render_template

    # If already authenticated via cookie and has session, go to success page
    try:
        session_token_cookie = get_session_token(request)
        if session_token_cookie:
            cookie_user_id = await validate_session_token(session_token_cookie)
            if cookie_user_id:
                from StreamBot.database.user_sessions import get_user_session_info
                if await get_user_session_info(cookie_user_id):
                    return web.HTTPFound('/session/success')
    except Exception:
        pass

    token = request.query.get('token')
    user_id = await validate_session_token(token)
    
    if not user_id:
        return web.HTTPFound('/session?error=invalid_token')
        
    context = {
        'token': token,
        'user_id': user_id
    }
    return render_template('login.html', request, context)

@routes.post("/session/send_code")
async def session_send_code_route(request: web.Request):
    """Handle API credentials and phone number submission to send verification code."""
    data = await request.json()
    token = data.get('token')
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    phone_number = data.get('phone_number')
    # Proxy configuration (optional)
    proxy_host = data.get('proxy_host', '').strip() or None
    proxy_port = data.get('proxy_port')
    proxy_type = data.get('proxy_type', 'http').strip().lower()
    proxy_username = data.get('proxy_username', '').strip() or None
    proxy_password = data.get('proxy_password', '').strip() or None
    
    # Validate proxy configuration if provided
    if proxy_host:
        if not proxy_port:
            return web.json_response({'status': 'error', 'message': 'Proxy port is required when proxy host is provided'}, status=400)
        
        try:
            proxy_port = int(proxy_port)
        except (ValueError, TypeError):
            return web.json_response({'status': 'error', 'message': 'Invalid proxy port number'}, status=400)
        
        from StreamBot.utils.proxy_manager import proxy_manager
        is_valid, error_msg = proxy_manager.validate_proxy_input(proxy_host, str(proxy_port), proxy_type)
        if not is_valid:
            return web.json_response({'status': 'error', 'message': f'Proxy validation failed: {error_msg}'}, status=400)
    
    user_id = await validate_session_token(token)
    if not user_id:
        return web.json_response({'status': 'error', 'message': 'Invalid or expired session.'}, status=401)
    
    # Validate input
    if not api_id or not api_hash or not phone_number:
        return web.json_response({'status': 'error', 'message': 'API ID, API Hash, and phone number are required.'}, status=400)
    
    try:
        api_id = int(api_id)
    except (ValueError, TypeError):
        return web.json_response({'status': 'error', 'message': 'Invalid API ID format.'}, status=400)
    
    try:
        result = await interactive_login_manager.start_login(
            user_id, api_id, api_hash, phone_number, proxy_host, proxy_port, proxy_type, proxy_username, proxy_password
        )
        return web.json_response(result)
    except Exception as e:
        logger.error(f"Error in send_code route: {e}")
        return web.json_response({'status': 'error', 'message': 'An error occurred. Please try again.'}, status=500)

@routes.post("/session/submit_code")
async def session_submit_code_route(request: web.Request):
    """Handle verification code submission."""
    data = await request.json()
    token = data.get('token')
    phone_number = data.get('phone_number')
    phone_code_hash = data.get('phone_code_hash')
    code = data.get('code')

    user_id = await validate_session_token(token)
    if not user_id:
        return web.json_response({'status': 'error', 'message': 'Invalid or expired session.'}, status=401)
        
    try:
        result = await asyncio.wait_for(
            interactive_login_manager.submit_code(user_id, phone_number, phone_code_hash, code),
            timeout=35
        )
    except asyncio.TimeoutError:
        try:
            await interactive_login_manager.cleanup_client(user_id)
        except Exception:
            pass
        return web.json_response({'status': 'timeout', 'message': 'Verification timed out. Please request a new code.'}, status=504)
    
    if result.get('status') == 'success':
        # SECURITY: Verify that the logged-in user matches the widget user
        logged_in_user_info = result.get('user_info')
        if not logged_in_user_info or logged_in_user_info.get('id') != user_id:
            await interactive_login_manager.cleanup_client(user_id)
            return web.json_response({
                'status': 'error', 
                'message': 'Account mismatch. The logged-in account does not match the widget account.'
            }, status=400)

        # Store the session and clean up
        from StreamBot.database.user_sessions import store_user_session
        session_stored = await store_user_session(user_id, result['session_string'], logged_in_user_info)
        await interactive_login_manager.cleanup_client(user_id)
        
        if not session_stored:
            logger.error(f"Failed to store session for user {user_id}")
            return web.json_response({
                'status': 'error', 
                'message': 'Failed to store session. Please try again.'
            }, status=500)

        # Notify user via bot DM (non-blocking best-effort)
        try:
            from StreamBot.session_generator.session_manager import session_manager
            asyncio.create_task(session_manager.notify_bot_about_new_session(user_id, logged_in_user_info))
        except Exception as _e:
            logger.debug(f"Notify bot about new session failed for {user_id}: {_e}")

        # Prepare redirect response with session token for the frontend and set cookies
        session_token = generate_session_token(user_id)
        response = web.json_response({
            'status': 'success',
            'redirect_url': '/session/success',
            'session_token': session_token
        })
        try:
            set_auth_cookies(response, session_token, user_id)
        except Exception:
            pass
        return response

    return web.json_response(result)

@routes.post("/session/submit_password")
async def session_submit_password_route(request: web.Request):
    """Handle 2FA password submission."""
    data = await request.json()
    token = data.get('token')
    password = data.get('password')

    user_id = await validate_session_token(token)
    if not user_id:
        return web.json_response({'status': 'error', 'message': 'Invalid or expired session.'}, status=401)

    
    try:
        result = await asyncio.wait_for(
            interactive_login_manager.submit_password(user_id, password),
            timeout=35
        )
    except asyncio.TimeoutError:
        try:
            await interactive_login_manager.cleanup_client(user_id)
        except Exception:
            pass
        return web.json_response({'status': 'timeout', 'message': '2FA verification timed out. Please request a new code.'}, status=504)
    
    if result.get('status') == 'success':
        # SECURITY: Verify that the logged-in user matches the widget user
        logged_in_user_info = result.get('user_info')
        if not logged_in_user_info or logged_in_user_info.get('id') != user_id:
            await interactive_login_manager.cleanup_client(user_id)
            return web.json_response({
                'status': 'error', 
                'message': 'Account mismatch. The logged-in account does not match the widget account.'
            }, status=400)
            
        from StreamBot.database.user_sessions import store_user_session
        session_stored = await store_user_session(user_id, result['session_string'], logged_in_user_info)
        await interactive_login_manager.cleanup_client(user_id)
        
        if not session_stored:
            logger.error(f"Failed to store session for user {user_id}")
            return web.json_response({
                'status': 'error', 
                'message': 'Failed to store session. Please try again.'
            }, status=500)

        # Notify user via bot DM (non-blocking best-effort)
        try:
            from StreamBot.session_generator.session_manager import session_manager
            asyncio.create_task(session_manager.notify_bot_about_new_session(user_id, logged_in_user_info))
        except Exception as _e:
            logger.debug(f"Notify bot about new session failed for {user_id}: {_e}")

        # Prepare redirect response with session token for the frontend and set cookies
        session_token = generate_session_token(user_id)
        response = web.json_response({
            'status': 'success',
            'redirect_url': '/session/success',
            'session_token': session_token
        })
        try:
            set_auth_cookies(response, session_token, user_id)
        except Exception:
            pass
        return response

    return web.json_response(result)

@routes.post("/session/auth")
async def session_auth_route(request: web.Request):
    """Handle Telegram authentication and redirect to interactive login."""
    try:
        data = await request.json()
        
        # Verify Telegram authentication
        from StreamBot.session_generator.telegram_auth import TelegramAuth
        telegram_auth = TelegramAuth()
        
        if not telegram_auth.verify_telegram_auth(data):
            return web.json_response({
                'success': False,
                'error': 'Invalid Telegram authentication'
            }, status=400)
        
        user_id = int(data['id'])

        # Check if user has permission to use session generator (premium access)
        if not await check_session_generator_access(user_id):
            logger.info(f"Session generator disabled - web access denied for user {user_id}")
            return web.json_response({
                'success': False,
                'error': Var.PREMIUM_REQUIRED_TEXT,
            }, status=403)
        
        from StreamBot.database.user_sessions import check_user_has_session
        if await check_user_has_session(user_id):
            session_token = generate_session_token(user_id)
            response = web.json_response({
                'success': True,
                'redirect_url': '/session/success',
                'session_token': session_token
            })
            set_auth_cookies(response, session_token, user_id)
            return response
            
        # Generate a temporary token and redirect to the login form
        session_token = generate_session_token(user_id)
        
        return web.json_response({
                'success': True,
            'redirect_url': f'/session/login?token={session_token}',
            'session_token': session_token
        })
            
    except Exception as e:
        logger.error(f"Error in session auth route: {e}", exc_info=True)
        return web.json_response({
            'success': False,
            'error': 'An internal server error occurred.'
        }, status=500)

@routes.get("/session/success")
async def session_success_route(request: web.Request):
    """Session generation success page route."""
    from aiohttp_jinja2 import render_template
    from StreamBot.database.user_sessions import get_user_session_info
    
    try:
        # Prefer cookie/header session token
        session_token = get_session_token(request)
        user_id = await validate_session_token(session_token) if session_token else None

        if not user_id:
            logger.warning("No valid session token or user_id provided for success page")
            return web.HTTPFound('/session')
        
        # Get user session info from database
        user_session_info = await get_user_session_info(user_id)
        if not user_session_info:
            logger.warning(f"No session info found for user {user_id} on success page")
            return web.HTTPFound('/session')
        
        user_profile = user_session_info.get('user_info', {})
        # Generate deterministic identicon avatar (DiceBear) using SHA-256 seed
        avatar_seed = hashlib.sha256(str(user_id).encode('utf-8')).hexdigest()
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={avatar_seed}&size=128"
        
        # Get bot username for the success page
        bot_client = request.app['bot_client']
        bot_username = bot_client.me.username if bot_client and bot_client.me else 'unknown'
        
        return render_template('session_complete.html', request, {
            'user_info': user_profile,
            'avatar_url': avatar_url,
            'base_url': Var.BASE_URL,
            'bot_username': bot_username
        })
        
    except (ValueError, TypeError):
        logger.warning("Invalid user_id format on success page")
        return web.HTTPFound('/session')
    except Exception as e:
        logger.error(f"Error in session success page: {e}", exc_info=True)
        return web.HTTPFound('/session')

@routes.get("/session/dashboard")
async def session_dashboard_route(request: web.Request):
    """Session generator dashboard for authenticated users with proper session management."""
    from aiohttp_jinja2 import render_template

    # Check for session token in cookies or headers, fallback to query parameter
    session_token = get_session_token(request)
    user_id_param = request.query.get('user_id')

    user_id = None

    try:
        if session_token:
            # Validate session token
            user_id = await validate_session_token(session_token)
        elif user_id_param:
            user_id = int(user_id_param)

        if not user_id:
            logger.warning("No valid session token or user_id provided")
            return web.HTTPFound('/session')

        # Check if user has permission to use session generator (premium access)
        if not await check_session_generator_access(user_id):
            logger.info(f"Session generator disabled - dashboard access denied for user {user_id}")
            return web.Response(
                text="Access Denied: Premium required.\n" + Var.PREMIUM_REQUIRED_TEXT,
                status=403,
                content_type='text/plain'
            )

        # Get user session info
        from StreamBot.database.user_sessions import get_user_session_info
        user_session_info = await get_user_session_info(user_id)

        if not user_session_info:
            logger.warning(f"No session info found for user {user_id}")
            return web.HTTPFound('/session')

        user_profile = user_session_info.get('user_info', {})
        # Generate deterministic identicon avatar (DiceBear) using SHA-256 seed
        avatar_seed = hashlib.sha256(str(user_id).encode('utf-8')).hexdigest()
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={avatar_seed}&size=128"

        # Generate new session token for this session
        new_session_token = generate_session_token(user_id)

        bot_client: Client = request.app.get('bot_client')
        bot_username = getattr(bot_client.me, 'username', None) if bot_client and hasattr(bot_client, 'me') else None

        context = {
            'user_info': user_profile,
            'avatar_url': avatar_url,
            'bot_username': bot_username,
            'base_url': Var.BASE_URL,
            'app_name': 'Telegram Session Generator',
            'session_token': new_session_token
        }

        response = render_template('session_complete.html', request, context)

        # Set session cookie for proper session management
        if hasattr(response, 'set_cookie'):
            is_secure = str(Var.BASE_URL).lower().startswith('https://')
            response.set_cookie('session_token', new_session_token, httponly=True, secure=is_secure, max_age=3600, samesite='Lax')
            # convenience cookies for UI
            response.set_cookie('is_authenticated', 'true', httponly=True, secure=is_secure, max_age=3600, samesite='Lax')
            response.set_cookie('user_id', str(user_id), httponly=True, secure=is_secure, max_age=3600, samesite='Lax')
        else:
            # If render_template doesn't return a response object, create one
            response = web.Response(text=response, content_type='text/html')
            is_secure = str(Var.BASE_URL).lower().startswith('https://')
            response.set_cookie('session_token', new_session_token, httponly=True, secure=is_secure, max_age=3600, samesite='Lax')
            response.set_cookie('is_authenticated', 'true', httponly=True, secure=is_secure, max_age=3600, samesite='Lax')
            response.set_cookie('user_id', str(user_id), httponly=True, secure=is_secure, max_age=3600, samesite='Lax')

        return response

    except (ValueError, TypeError):
        logger.warning(f"Invalid user_id format: {user_id_param}")
        return web.HTTPFound('/session')
    except Exception as e:
        logger.error(f"Error in session dashboard: {e}", exc_info=True)
        return web.HTTPFound('/session')


# Note: /session/logout route removed per UI change


@routes.get("/owner/dashboard")
async def owner_dashboard_route(request: web.Request):
    """Owner analytics dashboard (one-time token URL, then short-lived session)."""
    client_ip = get_client_ip(request)
    if invalid_request_guard.is_blocked(client_ip):
        return web.Response(text="Too many invalid requests. Try again later.", status=429)

    token = request.query.get("token")
    session_id = request.cookies.get("owner_dash_session")

    owner_id = None
    if token:
        owner_id = consume_owner_one_time_token(token)
        if owner_id != Var.OWNER_ID:
            invalid_request_guard.record_invalid(client_ip)
            return web.Response(text="Invalid or expired dashboard token.", status=403)
        session_id = create_dashboard_session(owner_id=owner_id, expires_minutes=30)
    elif session_id:
        owner_id = get_dashboard_session_owner(session_id)
        if owner_id != Var.OWNER_ID:
            invalid_request_guard.record_invalid(client_ip)
            return web.Response(text="Dashboard session expired. Generate a new /dashboard link.", status=403)
    else:
        # Not logging as invalid if someone just hits the URL without any token/cookie, 
        # as it could be casual browsing. But we will for actual APIs.
        return web.Response(text="Dashboard token missing. Generate via /dashboard.", status=403)

    # Load dashboard template from external file
    template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")
    template_file = os.path.join(template_dir, "owner_dashboard.html")
    try:
        with open(template_file, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        logger.error(f"Dashboard template not found at {template_file}")
        return web.Response(text="Dashboard template missing.", status=500)

    resp = web.Response(text=html, content_type="text/html")
    if session_id:
        is_secure = str(Var.BASE_URL).lower().startswith("https://")
        resp.set_cookie("owner_dash_session", session_id, httponly=True, secure=is_secure, max_age=1800, samesite="Lax")
    return resp


@routes.get("/owner/dashboard/data")
async def owner_dashboard_data_route(request: web.Request):
    """Dashboard data endpoint (requires valid owner dashboard session cookie)."""
    client_ip = get_client_ip(request)
    if invalid_request_guard.is_blocked(client_ip):
        return web.json_response({"error": "unauthorized"}, status=429)

    session_id = request.cookies.get("owner_dash_session")
    owner_id = get_dashboard_session_owner(session_id) if session_id else None
    if owner_id != Var.OWNER_ID:
        invalid_request_guard.record_invalid(client_ip)
        return web.json_response({"error": "unauthorized"}, status=403)

    q = (request.query.get("q") or "").strip()
    user_id_raw = (request.query.get("user_id") or "").strip()
    from_raw = (request.query.get("from") or "").strip()
    to_raw = (request.query.get("to") or "").strip()

    uid = None
    if user_id_raw:
        try:
            uid = int(user_id_raw)
        except ValueError:
            uid = None

    from_dt = None
    to_dt = None
    try:
        if from_raw:
            from_dt = datetime.datetime.fromisoformat(from_raw.replace("Z", "+00:00"))
    except Exception:
        from_dt = None
    try:
        if to_raw:
            to_dt = datetime.datetime.fromisoformat(to_raw.replace("Z", "+00:00"))
    except Exception:
        to_dt = None

    def _int_q(name: str, default: int) -> int:
        raw = (request.query.get(name) or "").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    data = await get_dashboard_data(
        search=q,
        user_id=uid,
        start_dt=from_dt,
        end_dt=to_dt,
        links_page=_int_q("links_page", 1),
        links_page_size=_int_q("links_page_size", 50),
        events_page=_int_q("events_page", 1),
        events_page_size=_int_q("events_page_size", 50),
        users_page=_int_q("users_page", 1),
        users_page_size=_int_q("users_page_size", 50),
    )
    return web.json_response(data)


@routes.get("/owner/dashboard/user/{user_id}")
async def owner_dashboard_user_detail_route(request: web.Request):
    """Return granular data for one user (requires owner dashboard session)."""
    client_ip = get_client_ip(request)
    if invalid_request_guard.is_blocked(client_ip):
        return web.json_response({"error": "unauthorized"}, status=429)

    session_id = request.cookies.get("owner_dash_session")
    owner_id = get_dashboard_session_owner(session_id) if session_id else None
    if owner_id != Var.OWNER_ID:
        invalid_request_guard.record_invalid(client_ip)
        logger.warning(f"Dashboard user detail: unauthorized (owner_id={owner_id!r}) from IP {client_ip}")
        return web.json_response({"error": "unauthorized"}, status=403)

    user_id_raw = request.match_info.get("user_id", "")
    try:
        user_id = int(user_id_raw)
    except ValueError:
        return web.json_response({"error": "invalid user_id"}, status=400)

    try:
        data = await get_user_detail(user_id)
    except Exception as e:
        logger.error(f"get_user_detail error for {user_id}: {e}", exc_info=True)
        data = {"profile": {}, "subscription": {}, "links": [], "top_ips": [], "graph": []}

    # Build telegram dict from the stored profile fields (no live API call needed)
    prof = data.get("profile") or {}
    data["telegram"] = {
        "id": user_id,
        "first_name": prof.get("first_name") or "",
        "last_name": prof.get("last_name") or "",
        "username": prof.get("username") or "",
        "is_premium": bool(prof.get("is_premium", False)),
        "is_verified": bool(prof.get("is_verified", False)),
        "is_scam": False,
        "language_code": prof.get("language_code") or "",
        "status": "",
        "has_photo": False,
    }

    return web.json_response(data)



@routes.get("/owner/dashboard/link/{encoded_id}/events")
async def owner_dashboard_link_events_route(request: web.Request):
    """Return per-IP event breakdown for one link (requires owner dashboard session)."""
    client_ip = get_client_ip(request)
    if invalid_request_guard.is_blocked(client_ip):
        return web.json_response({"error": "unauthorized"}, status=429)

    session_id = request.cookies.get("owner_dash_session")
    owner_id = get_dashboard_session_owner(session_id) if session_id else None
    if owner_id != Var.OWNER_ID:
        invalid_request_guard.record_invalid(client_ip)
        return web.json_response({"error": "unauthorized"}, status=403)

    encoded_id = request.match_info.get("encoded_id", "")
    if not encoded_id:
        return web.json_response({"error": "missing encoded_id"}, status=400)

    data = await get_link_events(encoded_id)
    return web.json_response(data)


@routes.route('*', '/{tail:.*}')
async def fallback_redirect_route(request: web.Request):
    """Redirect undefined routes to the bot or repository link."""
    # Never redirect dashboard API sub-routes — they should be handled by
    # their own route handlers.  If we reach here for them, it means the
    # specific route wasn't matched (which should not happen, but guard anyway).
    path = request.path
    if path.startswith("/owner/dashboard/user/") or path.startswith("/owner/dashboard/link/"):
        logger.warning(f"Catch-all hit for dashboard API path: {path}")
        return web.json_response({"error": "not_found"}, status=404)

    redirect_url = None
    bot_username = request.app.get('bot_username')
    if bot_username:
        redirect_url = f"https://telegram.dog/{bot_username}"

    if not redirect_url:
        redirect_url = Var.GITHUB_REPO_URL or "https://telegram.dog"

    raise web.HTTPFound(redirect_url)
