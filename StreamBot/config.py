# StreamBot/config.py
import os
from logging import getLogger
import re
import pyrogram

# Set up basic logging
logger = getLogger(__name__)

# Simple environment variable loader
def get_env(name: str, default=None, required: bool = False, is_bool: bool = False, is_int: bool = False):
    """Get environment variable with type conversion and validation."""
    value = os.environ.get(name, default)

    if required and value is None:
        logger.critical(f"Missing required environment variable: {name}")
        exit(f"Missing required environment variable: {name}")

    # Log config value before potential conversion errors, masking sensitive info
    log_value_display = '******' if name.endswith(('TOKEN', 'HASH', 'SECRET', 'KEY')) else value
    logger.info(f"Config: Reading {name} = {log_value_display}")

    if value is None:
        return None # Return None if default is None and env var is not set

    if is_bool:
        # Handle boolean conversion robustly
        return str(value).lower() in ("true", "1", "yes", "on")
    elif is_int:
        try:
            int_value = int(value)
            # Basic security check for reasonable integer bounds
            if name in ['API_ID', 'LOG_CHANNEL', 'FORCE_SUB_CHANNEL'] and int_value != 0:
                if abs(int_value) > 2**63:  # Prevent overflow
                    logger.error(f"Integer value for {name} exceeds reasonable bounds: {int_value}")
                    if required:
                        exit(f"Invalid required integer environment variable: {name}")
                    return default
            return int_value
        except (ValueError, TypeError):
            logger.error(f"Invalid integer value for {name}: '{value}'. Using default: {default} or exiting if required.")
            if required:
                exit(f"Invalid required integer environment variable: {name}='{value}'")
            # Attempt to convert default to int if it's not None, otherwise return None or the original default
            try:
                return int(default) if default is not None else None
            except (ValueError, TypeError):
                 logger.error(f"Default value '{default}' for {name} is also not a valid integer.")
                 return default # Return original default if it cannot be converted
    else:
        # Basic string validation for critical values
        if name == 'API_HASH' and value:
            if not re.match(r'^[a-f0-9]{32}$', str(value)):
                logger.warning(f"API_HASH format appears invalid (should be 32 hex chars)")
        elif name in ['BOT_TOKEN', 'ADDITIONAL_BOT_TOKENS'] and value:
            # Basic bot token format validation
            if name == 'BOT_TOKEN' and not re.match(r'^\d+:[A-Za-z0-9_-]{35}$', str(value)):
                logger.warning(f"BOT_TOKEN format appears invalid")
        elif name == 'BASE_URL' and value:
            # Basic URL validation
            if not str(value).startswith(('http://', 'https://')):
                logger.warning(f"BASE_URL should start with http:// or https://")
        
        # Return as string (or original type if default was used and not string)
        return value


class Var:
    """Application configuration from environment variables."""
    
    # Telegram API credentials
    API_ID = get_env("API_ID", required=True, is_int=True)
    API_HASH = get_env("API_HASH", required=True)
    BOT_TOKEN = get_env("BOT_TOKEN", required=True)
    
    # Multi-client configuration
    _additional_bot_tokens_str = get_env("ADDITIONAL_BOT_TOKENS", default="")
    ADDITIONAL_BOT_TOKENS = [token.strip() for token in _additional_bot_tokens_str.split(",") if token.strip()]
    WORKER_CLIENT_PYROGRAM_WORKERS = get_env("WORKER_CLIENT_PYROGRAM_WORKERS", 1, is_int=True)
    WORKER_SESSIONS_IN_MEMORY = get_env("WORKER_SESSIONS_IN_MEMORY", False, is_bool=True)

    # Channel configuration
    LOG_CHANNEL = get_env("LOG_CHANNEL", required=True, is_int=True)
    FORCE_SUB_CHANNEL = get_env("FORCE_SUB_CHANNEL", default=None, is_int=True)

    # Web server configuration
    BASE_URL = str(get_env("BASE_URL", required=True)).rstrip('/')
    PORT = get_env("PORT", 8080, is_int=True)
    BIND_ADDRESS = get_env("BIND_ADDRESS", "0.0.0.0")
    
    # CORS configuration
    _cors_origins_str = get_env("CORS_ALLOWED_ORIGINS", default="")
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins_str.split(',') if origin.strip()]
    
    # Video streaming frontend configuration
    _video_frontend_url = get_env("VIDEO_FRONTEND_URL", default="https://cricster.pages.dev")
    VIDEO_FRONTEND_URL = None if _video_frontend_url and _video_frontend_url.lower() == "false" else _video_frontend_url

    # Link expiry and security
    LINK_EXPIRY_SECONDS = get_env("LINK_EXPIRY_SECONDS", 86400, is_int=True)

    # Bot settings
    SESSION_NAME = get_env("SESSION_NAME", "TgDlBot")
    WORKERS = get_env("WORKERS", 4, is_int=True)
    GITHUB_REPO_URL = get_env("GITHUB_REPO_URL", default=None)

    # Database configuration
    DB_URI = get_env("DATABASE_URL", required=True)
    DB_NAME = get_env("DATABASE_NAME", "TgDlBotUsers")
    
    # Rate and bandwidth limiting
    MAX_LINKS_PER_DAY = get_env("MAX_LINKS_PER_DAY", default=5, is_int=True)
    BANDWIDTH_LIMIT_GB = get_env("BANDWIDTH_LIMIT_GB", default=100, is_int=True)
    
    # Session generator access control
    ALLOW_USER_LOGIN = get_env("ALLOW_USER_LOGIN", default=False, is_bool=True)
    
    # Basic security validation
    if PORT and (PORT < 1 or PORT > 65535):
        logger.error(f"Invalid PORT value: {PORT}. Must be between 1-65535.")
        PORT = 8080
    
    if WORKERS and (WORKERS < 1 or WORKERS > 32):
        logger.warning(f"WORKERS value {WORKERS} outside recommended range 1-32. Adjusting to safe value.")
        WORKERS = min(max(WORKERS, 1), 8)  # Clamp to 1-8 for low resources
    

    
    # --- Text Messages ---
    # Function to calculate human-readable duration
    @staticmethod
    def _human_readable_duration(seconds):
        """Convert seconds to human readable duration string."""
        if seconds is None: return "N/A"
        if seconds < 60: return f"{seconds} second{'s' if seconds != 1 else ''}"
        if seconds < 3600: return f"{seconds // 60} minute{'s' if seconds // 60 != 1 else ''}"
        if seconds < 86400: return f"{seconds // 3600} hour{'s' if seconds // 3600 != 1 else ''}"
        return f"{seconds // 86400} day{'s' if seconds // 86400 != 1 else ''}"

    # Calculate expiry duration string dynamically
    _expiry_duration_str = _human_readable_duration(LINK_EXPIRY_SECONDS)
    # --- Admin Users ---
    # List of user IDs who are allowed to use admin commands like /broadcast
    # Separate multiple IDs with spaces in the environment variable
    # Example: ADMINS="12345678 98765432"
    _admin_str = get_env("ADMINS", default="")
    try:
        ADMINS = [int(admin_id.strip()) for admin_id in _admin_str.split() if admin_id.strip()]
        if ADMINS:
            logger.info(f"Admin user IDs loaded: {ADMINS}")
        else:
            logger.warning("No ADMINS specified in environment variables. Broadcast command will not work.")
    except ValueError:
        logger.error(f"Invalid ADMINS value '{_admin_str}'. Ensure it's a space-separated list of numbers.")
        ADMINS = [] # Set to empty list on error

    # --- Broadcast Messages ---
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
    START_TEXT = f"""
Hello {{mention}}! 👋

🚀 **Welcome to the Ultimate Download Link Generator!**

📁 Send me any file to get a direct download link instantly.

🔐 **For Private Content:**
• Use `/login` once, then send the t.me post URL here
• Use `/logout` anytime to revoke access

⏰ Links expire in about {_expiry_duration_str}.

🎯 **Ready to get started? Send me a file now!**
    """


    FORCE_SUB_INFO_TEXT = "❗**You must join our channel to use this bot:**\n\n" # Added for start message

    FORCE_SUB_JOIN_TEXT = """
❗ **Join Required** ❗

You must join the channel below to use this bot. After joining, please send the file again.
    """

    LINK_GENERATED_TEXT = """
✅ **Download Link Generated!**

**File Name:** `{file_name}`
**File Size:** {file_size}

**Link:** {download_link}

⏳ **Expires:** In approximately 24 hours.

⚠️ This link allows direct download. Do not share it publicly if the file is private.
    """

    GENERATING_LINK_TEXT = "⏳ Generating your download link..."

    FILE_TOO_LARGE_TEXT = "❌ **Error:** File size ({file_size}) exceeds the maximum allowed limit by Telegram for bots."

    ERROR_TEXT = "❌ **Error:** An unexpected error occurred while processing your file. Please try again later."

    FLOOD_WAIT_TEXT = "⏳ Telegram is limiting my actions. Please wait {seconds} seconds and try again."

    LINK_EXPIRED_TEXT = "❌ **Error:** This download link has expired (valid for 24 hours)."

    RATE_LIMIT_EXCEEDED_TEXT = """
**Daily Limit Reached** 🤦‍♂️

You have reached your daily limit of {max_links} download links.

⏰ **Try again in:** {wait_hours:.1f} hours ({wait_minutes:.0f} minutes)

This limit helps keep the service running smoothly for everyone! 🙏
    """
    RATE_LIMIT_EXCEEDED_TEXT_NO_WAIT = """
**Daily Limit Reached** 🤦‍♂️

You have reached your daily limit of {max_links} download links.

⏰ **Try again:** Tomorrow

This limit helps keep the service running smoothly for everyone! 🙏
    """
    
    BANDWIDTH_LIMIT_EXCEEDED_TEXT = f"""
**Monthly Bandwidth Limit Exceeded** 📊

The bot has reached its monthly bandwidth limit of {BANDWIDTH_LIMIT_GB} GB.

⏰ **Service will resume:** Next month

Thank you for your understanding! 🙏
    """

    # Start menu info texts (used by buttons/callbacks)
    HELP_TEXT = f"""
Here is how to use the bot:

- Send me any file to get a direct download link.
- To access files from private channels/groups you belong to, use /login and authenticate on the session generator, then send the t.me post URL here.
- Use /logout to revoke your session and invalidate your private links.

Links usually expire in about {_expiry_duration_str}.
    """

    ABOUT_TEXT = f"""
🤖 **Telegram Download Link Generator**

📦 **PyroFork Version:** {getattr(pyrogram, '__version__', 'unknown')}
☁️ **Deployed on:** [Koyeb](https://koyeb.com)
📊 **Bandwidth Limit:** {BANDWIDTH_LIMIT_GB} GB/month {'(enabled)' if BANDWIDTH_LIMIT_GB > 0 else '(disabled)'}
🔗 **Repository:** [GitHub]({GITHUB_REPO_URL or 'https://github.com'})

💡 **Features:**
• Direct download links for any file
• Private channel/group support via sessions
• Secure encrypted session storage
• Rate limiting and bandwidth monitoring
• Multi-token support for reliability

⚡ **Powered by:** Python, Pyrogram, and MongoDB
    """