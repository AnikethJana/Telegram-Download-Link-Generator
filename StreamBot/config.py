"""
Configuration management for the Telegram Download Link Generator.

This module provides centralized configuration loading from environment variables
with type conversion, validation, and security features.
"""

import os
from logging import getLogger
import re
import pyrogram

logger = getLogger(__name__)


def get_env(
    name: str,
    default=None,
    required: bool = False,
    is_bool: bool = False,
    is_int: bool = False
):
    """
    Get environment variable with type conversion, validation, and security.
    """
    value = os.environ.get(name, default)

    # Handle inline comments in .env values (e.g. "0.15  # comment")
    # python-dotenv typically keeps them as part of the string in os.environ.
    if isinstance(value, str):
        value = value.split("#", 1)[0].strip()

    if required and value is None:
        logger.critical(f"Missing required environment variable: {name}")
        exit(f"Missing required environment variable: {name}")

    log_value_display = '******' if name.endswith(('TOKEN', 'HASH', 'SECRET', 'KEY')) else value
    logger.info(f"Config: Reading {name} = {log_value_display}")

    if value is None:
        return None

    if is_bool:
        return str(value).lower() in ("true", "1", "yes", "on")
    elif is_int:
        try:
            int_value = int(value)
            if name in ['API_ID', 'LOG_CHANNEL'] and int_value != 0:
                if abs(int_value) > 2**63:
                    logger.error(f"Integer value for {name} exceeds reasonable bounds: {int_value}")
                    if required:
                        exit(f"Invalid required integer environment variable: {name}")
                    return default
            return int_value
        except (ValueError, TypeError):
            logger.error(f"Invalid integer value for {name}: '{value}'. Using default: {default}")
            if required:
                exit(f"Invalid required integer environment variable: {name}='{value}'")
            try:
                return int(default) if default is not None else None
            except (ValueError, TypeError):
                logger.error(f"Default value '{default}' for {name} is also not a valid integer.")
                return default
    else:
        if name == 'API_HASH' and value:
            if not re.match(r'^[a-f0-9]{32}$', str(value)):
                logger.warning("API_HASH format appears invalid (should be 32 hex characters)")
        elif name in ['BOT_TOKEN', 'ADDITIONAL_BOT_TOKENS'] and value:
            if name == 'BOT_TOKEN' and not re.match(r'^\d+:[A-Za-z0-9_-]{35}$', str(value)):
                logger.warning("BOT_TOKEN format appears invalid")
        elif name == 'BASE_URL' and value:
            if not str(value).startswith(('http://', 'https://')):
                logger.warning("BASE_URL should start with http:// or https://")

        return value


class Var:
    """
    Application configuration container loaded from environment variables.
    """

    API_ID = get_env("API_ID", required=True, is_int=True)
    API_HASH = get_env("API_HASH", required=True)
    BOT_TOKEN = get_env("BOT_TOKEN", required=True)

    _additional_bot_tokens_str = get_env("ADDITIONAL_BOT_TOKENS", default="")
    ADDITIONAL_BOT_TOKENS = [token.strip() for token in _additional_bot_tokens_str.split(",") if token.strip()]
    WORKER_CLIENT_PYROGRAM_WORKERS = get_env("WORKER_CLIENT_PYROGRAM_WORKERS", 1, is_int=True)
    WORKER_SESSIONS_IN_MEMORY = get_env("WORKER_SESSIONS_IN_MEMORY", False, is_bool=True)

    LOG_CHANNEL = get_env("LOG_CHANNEL", required=True, is_int=True)

    _space_host = (
        os.environ.get("SPACE_HOST", "").strip()
        or os.environ.get("HF_SPACE_HOST", "").strip()
    )
    _space_id = (
        os.environ.get("SPACE_ID", "").strip()
        or os.environ.get("HF_SPACE_ID", "").strip()
    )
    _space_subdomain = _space_id.replace("/", "-") if _space_id else ""
    _hf_default_base_url = (
        f"https://{_space_host}" if _space_host
        else (f"https://{_space_subdomain}.hf.space" if _space_subdomain else None)
    )
    BASE_URL = str(
        get_env(
            "BASE_URL",
            default=_hf_default_base_url,
            required=_hf_default_base_url is None
        )
    ).rstrip('/')
    PORT = get_env("PORT", 8080, is_int=True)
    BIND_ADDRESS = get_env("BIND_ADDRESS", "0.0.0.0")

    _cors_origins_str = get_env("CORS_ALLOWED_ORIGINS", default="")
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins_str.split(',') if origin.strip()]

    _video_frontend_url = get_env("VIDEO_FRONTEND_URL", default="https://cricster.pages.dev")
    VIDEO_FRONTEND_URL = None if _video_frontend_url and _video_frontend_url.lower() == "false" else _video_frontend_url

    SESSION_NAME = get_env("SESSION_NAME", "TgDlBot")
    WORKERS = get_env("WORKERS", 4, is_int=True)
    GITHUB_REPO_URL = get_env("GITHUB_REPO_URL", default=None)

    DB_URI = get_env("DATABASE_URL", required=True)
    DB_NAME = get_env("DATABASE_NAME", "TgDlBotUsers")

    ALLOW_USER_LOGIN = get_env("ALLOW_USER_LOGIN", default=False, is_bool=True)

    # Premium access: only users in `allowed_users` can use the bot.
    # Owner can add users via `/add <user_id>`.
    OWNER_ID = get_env("OWNER_ID", required=True, is_int=True)

    # Transaction / payments channel (where screenshot + details are sent for owner confirmation)
    TXN_CHNL_ID = get_env("TXN_CHNL_ID", required=True, is_int=True)

    # Pricing configuration
    _price_per_day_usd_raw = get_env("PRICE_PER_DAY_USD", default=0.0)
    try:
        PRICE_PER_DAY_USD = float(_price_per_day_usd_raw)
    except (TypeError, ValueError):
        PRICE_PER_DAY_USD = 0.0

    _price_per_day_inr_raw = get_env("PRICE_PER_DAY_INR", default=0.0)
    try:
        PRICE_PER_DAY_INR = float(_price_per_day_inr_raw)
    except (TypeError, ValueError):
        PRICE_PER_DAY_INR = 0.0

    # Payment method configuration
    USDT_BEP20_ADDRESS = get_env("USDT_BEP20_ADDRESS", default="")
    UPI_ID = get_env("UPI_ID", default="")

    if PORT and (PORT < 1 or PORT > 65535):
        logger.error(f"Invalid PORT value: {PORT}. Must be between 1-65535.")
        PORT = 8080

    if WORKERS and (WORKERS < 1 or WORKERS > 32):
        logger.warning(f"WORKERS value {WORKERS} outside recommended range 1-32. Adjusting to safe value.")
        WORKERS = min(max(WORKERS, 1), 8)

    _admin_str = get_env("ADMINS", default="")
    try:
        ADMINS = [int(admin_id.strip()) for admin_id in _admin_str.split() if admin_id.strip()]
        if ADMINS:
            logger.info(f"Admin user IDs loaded: {ADMINS}")
        else:
            logger.warning("No ADMINS specified in environment variables. Broadcast command will not work.")
    except ValueError:
        logger.error(f"Invalid ADMINS value '{_admin_str}'. Ensure it's a space-separated list of numbers.")
        ADMINS = []

    BROADCAST_REPLY_PROMPT = "Reply to the message you want to broadcast with the `/broadcast` command."
    BROADCAST_ADMIN_ONLY = "❌ Only authorized admins can use this command."
    BROADCAST_STARTING = "⏳ Starting broadcast... This may take some time."
    BROADCAST_STATUS_UPDATE = """
    📢 **Broadcast Progress**

    Total Users: {total}
    Sent: {successful}
    Blocked/Deleted: {blocked_deleted}
    Failed: {unsuccessful}
    """
    BROADCAST_COMPLETED = """
    ✅ **Broadcast Completed**

    Total Users: `{total}`
    Successful: `{successful}`
    Blocked/Deactivated Users Removed: `{blocked_deleted}`
    Failed Attempts: `{unsuccessful}`
    """
    START_TEXT = """
Hello {mention}! 👋

🚀 **Welcome to the Ultimate Download Link Generator!**

📁 Send me any file to get a direct download link instantly.

🔐 **For Private Content:**
• Use `/login` once, then send the t.me post URL here
• Use `/logout` anytime to revoke access

🎯 **Ready to get started? Send me a file now!**
    """

    LINK_GENERATED_TEXT = """
✅ **Download Link Generated!**

**File Name:** `{file_name}`
**File Size:** {file_size}

**Link:** {download_link}

⚠️ This link allows direct download. Do not share it publicly if the file is private.
    """

    GENERATING_LINK_TEXT = "⏳ Generating your download link..."

    FILE_TOO_LARGE_TEXT = "❌ **Error:** File size ({file_size}) exceeds the maximum allowed limit by Telegram for bots."

    ERROR_TEXT = "❌ **Error:** An unexpected error occurred while processing your file. Please try again later."

    FLOOD_WAIT_TEXT = "⏳ Telegram is limiting my actions. Please wait {seconds} seconds and try again."

    HELP_TEXT = """
Here is how to use the bot:

- Send me any file to get a direct download link.
- To access files from private channels/groups you belong to, use /login and authenticate on the session generator, then send the t.me post URL here.
- Use /logout to revoke your session and invalidate your private links.
    """

    PREMIUM_REQUIRED_TEXT = (
        "🔒 Premium required to use this bot.\n\n"
        "Tap the button below to buy premium."
    )

    NON_PREMIUM_START_TEXT = """
Hello {mention}! 👋

🚀 **Welcome to the Ultimate Telegram Download Bot!**

We provide lightning-fast, direct download links for **any** file on Telegram — even from private channels!

🔒 **100% Secure & Private**
⚡ **High-Speed Global Servers**
📈 **Over 10,000+ files processed daily**

Tap the buttons below to see what we can do for you, or hit **🚀 GET STARTED** to unlock premium access instantly!
    """

    FEATURES_TEXT = """
✨ **Premium Features:**

• **Direct Download Links**: Bypass Telegram's clunky app restrictions
• **Private Channel Access**: Get links for files in private channels via secure login
• **High Speed Streaming**: Stream videos directly in your browser without downloading
• **Unlimited Speed**: Enterprise-grade proxy servers for maximum bandwidth
• **Ad-Free Experience**: Smooth, uninterrupted downloads
"""

    HOW_IT_WORKS_TEXT = """
🛠 **How It Works:**

**1️⃣ Public Files:**
Just forward or send any file to the bot. We'll reply instantly with a direct download link!

**2️⃣ Private Channels:**
• Type `/login` to securely authenticate your session
• Copy the message link from any private channel you're a member of
• Send the link to the bot — we'll generate your direct link!

**3️⃣ Stream Anywhere:**
Click the generated link to preview, stream, or download.
"""

    PRICING_TEXT = """
💰 **Premium Plans:**

Stop waiting. Unlock the full power of direct downloads and private channel access today!

• Flexible daily, weekly, and monthly passes
• Pay securely via Crypto (USDT) or UPI
• Instant automated activation

Tap **🚀 GET STARTED** below to view prices and upgrade instantly!
    """

    ABOUT_TEXT = f"""
🤖 **Telegram Download Link Generator**

📦 **PyroFork Version:** {getattr(pyrogram, '__version__', 'unknown')}
☁️ **Deployed on:** [Koyeb](https://koyeb.com)
🔗 **Repository:** [GitHub]({GITHUB_REPO_URL or 'https://github.com'})

💡 **Features:**
• Direct download links for any file
• Private channel/group support via sessions
• Secure encrypted session storage
• Multi-token support for reliability

⚡ **Powered by:** Python, Pyrogram, and MongoDB
    """
