# StreamBot/config.py
import os
from logging import getLogger

# Set up basic logging
logger = getLogger(__name__)

# Simple environment variable loader
def get_env(name: str, default=None, required: bool = False, is_bool: bool = False, is_int: bool = False):
    """Gets an environment variable, logs status, handles required vars, and types."""
    value = os.environ.get(name, default)

    if required and value is None:
        logger.critical(f"Missing required environment variable: {name}")
        # Exit or raise error if a critical variable is missing
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
            return int(value)
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
        # Return as string (or original type if default was used and not string)
        return value


class Var:
    # --- Essential Telegram API/Bot Config ---
    API_ID = get_env("API_ID", required=True, is_int=True)
    API_HASH = get_env("API_HASH", required=True)
    BOT_TOKEN = get_env("BOT_TOKEN", required=True)
    # --- Multi-Client Configuration ---
    # Comma-separated list of additional bot tokens for worker clients
    _additional_bot_tokens_str = get_env("ADDITIONAL_BOT_TOKENS", default="")
    ADDITIONAL_BOT_TOKENS = [token.strip() for token in _additional_bot_tokens_str.split(",") if token.strip()]
    WORKER_CLIENT_PYROGRAM_WORKERS = get_env("WORKER_CLIENT_PYROGRAM_WORKERS", 1, is_int=True)
    WORKER_SESSIONS_IN_MEMORY = get_env("WORKER_SESSIONS_IN_MEMORY", False, is_bool=True)

    # --- Log Channel ---
    # ID of a private channel where the bot will forward files. Bot must be an admin.
    LOG_CHANNEL = get_env("LOG_CHANNEL", required=True, is_int=True) # Make sure this is an integer ID

    # --- Force Subscription ---
    # Optional: ID of a channel users must join to use the bot. Bot must be admin.
    # Leave blank or remove the variable to disable force-sub.
    FORCE_SUB_CHANNEL = get_env("FORCE_SUB_CHANNEL", default=None, is_int=True) # Should be an integer ID if set

    # --- Web Server Config ---
    # Base URL of your web server (e.g., "https://yourdomain.com" or "http://localhost:8080")
    # No trailing slash!
    BASE_URL = str(get_env("BASE_URL", required=True)).rstrip('/') # Ensure no trailing slash and is string
    # Port for the web server
    PORT = get_env("PORT", 8080, is_int=True)
    # Bind address for the web server
    BIND_ADDRESS = get_env("BIND_ADDRESS", "0.0.0.0")

    # --- Link Expiry ---
    # Expiry time for download links in seconds (24 hours = 86400 seconds)
    LINK_EXPIRY_SECONDS = get_env("LINK_EXPIRY_SECONDS", 86400, is_int=True) # Default to 24 hours

    # --- Logs Access Security ---
    # Token for accessing logs via API endpoint
    LOGS_ACCESS_TOKEN = get_env("LOGS_ACCESS_TOKEN", os.urandom(16).hex())
    # Admin IPs allowed to access logs without token (comma-separated)
    _admin_ips_str = get_env("ADMIN_IPS", "127.0.0.1")
    ADMIN_IPS = [ip.strip() for ip in _admin_ips_str.split(",") if ip.strip()]

    # --- Optional Settings ---
    # Session name for pyrogram (change if running multiple bots on one machine)
    SESSION_NAME = get_env("SESSION_NAME", "TgDlBot")
    # Number of worker threads for pyrogram
    WORKERS = get_env("WORKERS", 4, is_int=True)
    # URL to the bot's GitHub repository (Optional)
    GITHUB_REPO_URL = get_env("GITHUB_REPO_URL", default=None)

    # --- Database Config (MongoDB) ---
    # Connection URI string for your MongoDB database
    DB_URI = get_env("DATABASE_URL", required=True) # Changed from DATABASE_URL in reference to DB_URI
    # Name of the database to use
    DB_NAME = get_env("DATABASE_NAME", "TgDlBotUsers") # Changed default name
    # --- Rate Limiting ---
    # Maximum number of links a user can generate in a 24-hour period.
    # Set to 0 or a negative number to disable rate limiting.
    MAX_LINKS_PER_DAY = get_env("MAX_LINKS_PER_DAY", default=5, is_int=True)
    # --- Text Messages ---
    # Function to calculate human-readable duration
    @staticmethod
    def _human_readable_duration(seconds):
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

I am Telegram File to Link Bot.

➡️ **Send me any file** and I will generate a direct download link for you .

{{force_sub_info}}
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

You have generated the maximum of **{max_links}** links allowed in a 24-hour period.
Please try again in approximately **{wait_hours:.1f} hours **.
    """
    RATE_LIMIT_EXCEEDED_TEXT_NO_WAIT = """
❗ **Daily Limit Reached** ❗

You have generated the maximum of **{max_links}** links allowed in a 24-hour period.
Please try again later.
    """