"""
Telegram Bot handlers and message processing for the Download Link Generator.

This module contains all bot command handlers, message processors, and helper
functions for managing user interactions with the Telegram bot. It handles:

- Command processing (/start, /help, /login, /logout, etc.)
- File upload processing with download link generation
- Private channel link processing via user sessions
- Rate limiting and security checks
- User management and database operations

All handlers are designed to be memory-efficient and thread-safe.
"""

import logging
import asyncio
import os
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserNotParticipant, FloodWait, UserIsBlocked, InputUserDeactivated
from .database.database import add_user, del_user, full_userbase
from .config import Var
from .utils.utils import get_file_attr, humanbytes, encode_message_id, is_video_file
from .security.rate_limiter import bot_rate_limiter
from .utils.bandwidth import is_bandwidth_limit_exceeded, get_current_bandwidth_usage
from .utils.smart_logger import SmartRateLimitedLogger
from .link_handler import get_message_from_link
from .utils import url_shortener

logger = logging.getLogger(__name__)

# Memory-efficient rate-limited logger for high-frequency operations
rate_limited_logger = SmartRateLimitedLogger(logger)


async def process_link(original_link: str, file_size: int) -> str:
    """
    Process any externally shared link and shorten it if the file size exceeds the threshold.

    This helper is used for download URLs, stream URLs and video frontend links. If
    shortening fails, we gracefully fall back to the original link to ensure functionality
    is not disrupted.

    Args:
        original_link (str): The original link to be shared
        file_size (int): Size of the related file in bytes

    Returns:
        str: The processed link (shortened if needed, otherwise original)
    """
    try:
        # Determine if URL shortening should be applied based on file size
        if await url_shortener.should_use_short_url(file_size):
            rate_limited_logger.log('info', f"File size {file_size} bytes exceeds threshold, shortening URL")
            shortened_url = await url_shortener.shorten_url(original_link)
            if shortened_url:
                rate_limited_logger.log('info', f"URL shortened successfully: {original_link} -> {shortened_url}")
                return shortened_url
            else:
                rate_limited_logger.log('warning', "URL shortening failed, using original link")
                return original_link
        else:
            rate_limited_logger.log('debug', f"File size {file_size} bytes is below threshold, using original link")
            return original_link
    except Exception as e:
        logger.error(f"Error processing download link: {e}", exc_info=True)
        # Graceful fallback - return original link to maintain functionality
        return original_link


def build_active_session_message(session_generator_url: str, is_localhost: bool) -> str:
    """
    Build a message for users who already have an active session.

    Provides guidance on using their existing session and includes localhost-specific
    instructions for development/testing environments.

    Args:
        session_generator_url (str): URL to the session management page
        is_localhost (bool): Whether the application is running on localhost

    Returns:
        str: Formatted message with session usage instructions
    """
    if is_localhost:
        return f"""✅ **You already have an active session!**

Your session is currently active and ready to use for generating download links.

📋 **How to use your active session:**
1️⃣ Share any private channel/group post URL with me
2️⃣ I'll instantly generate a download link for you
3️⃣ Use `/logout` anytime to revoke your session

💡 **Quick Access (Local Testing):**
Open this URL in your browser to manage your session:
`{session_generator_url}`

🔒 **Security Note:** Your session is encrypted and secure. Only you can access your private content."""
    else:
        return """✅ **You already have an active session!**

Your session is currently active and ready to use for generating download links.

📋 **How to use your active session:**
1. Share any private channel/group post URL with me
2. I'll instantly generate a download link for you
3. Use `/logout` anytime to revoke your session

🔒 **Security Note:** Your session is encrypted and secure. Only you can access your private content."""


def build_login_message(session_generator_url: str, is_localhost: bool) -> str:
    """
    Build a login prompt message for users without an active session.

    Provides instructions for creating a new session and includes security warnings
    about responsible usage to prevent account bans.

    Args:
        session_generator_url (str): URL to the session creation page
        is_localhost (bool): Whether the application is running on localhost

    Returns:
        str: Formatted message with login instructions and security warnings
    """
    if is_localhost:
        return f"""🔐 **Login to Session Generator**

Generate secure sessions to get download links from private Telegram channels and groups without sharing your credentials.

📋 **Steps to get started (Local Testing):**
1️⃣ Copy this URL and open it in your browser:
`{session_generator_url}`

2️⃣ Login with your Telegram account using the official widget
3️⃣ Your secure session will be automatically generated
4️⃣ Return here and share private file URLs to get download links

✨ **What you can do:**
• Access files from private channels you're a member of
• Generate instant download links for any media
• Keep your credentials completely secure
• Revoke access anytime with `/logout`

🔒 **Security Features:**
• End-to-end encrypted session storage
• No credentials stored on our servers
• Automatic session expiry for security
• Full control over your access

💡 **Local Testing Note:** Since you're testing locally, click and hold the URL above, then select "Copy" to open it in your browser.

⚠️ **Important Caution:**
Using session-based access with newer accounts, downloading large files continuously, abusing the service, or sharing access with others who spam downloads may result in your Telegram account being banned. Please use responsibly and avoid excessive usage patterns that could trigger Telegram's anti-abuse systems."""
    else:
        return """🔐 **Login to Session Generator**

Generate secure sessions to get download links from private Telegram channels and groups without sharing your credentials.

📋 **Steps to get started:**
1. Click the "🔐 Login to Session Generator" button below
2. Login with your Telegram account using the official widget
3. Your secure session will be automatically generated
4. Return here and share private file URLs to get download links

🔒 **Security Features:**
• End-to-end encrypted session storage
• No credentials stored on our servers

⚠️ **Important Caution:**
Using session-based access with newer accounts, downloading large files continuously, abusing the service, or sharing access with others who spam downloads may result in your Telegram account being banned. Please use responsibly and avoid excessive usage patterns that could trigger Telegram's anti-abuse systems."""

async def check_force_sub(client: Client, message: Message) -> bool:
    """
    Check if user is subscribed to the required force subscription channel.

    This function verifies that users have joined the mandatory channel before
    allowing them to use the bot. If not subscribed, it provides a join link
    and prevents further processing.

    Args:
        client (Client): The Pyrogram client instance
        message (Message): The message from the user to check

    Returns:
        bool: True if user is subscribed or no force subscription is required,
              False if user needs to join the channel
    """
    if not Var.FORCE_SUB_CHANNEL:
        return True

    try:
        # Check user's membership status in the required channel
        member = await client.get_chat_member(Var.FORCE_SUB_CHANNEL, message.from_user.id)
        if member.status not in ["kicked", "left"]:
            return True
        else:
            raise UserNotParticipant

    except UserNotParticipant:
        try:
            # Get channel information and invite link
            chat = await client.get_chat(Var.FORCE_SUB_CHANNEL)
            invite_link = chat.invite_link
            if not invite_link:
                # Create new invite link if none exists
                invite_link_obj = await client.create_chat_invite_link(Var.FORCE_SUB_CHANNEL)
                invite_link = invite_link_obj.invite_link

            # Create join button with channel name
            button_text = f"Join {chat.title}" if chat.title else "Join Channel"
            button = [[InlineKeyboardButton(button_text, url=invite_link)]]
            await message.reply_text(
                Var.FORCE_SUB_JOIN_TEXT,
                reply_markup=InlineKeyboardMarkup(button),
                quote=True
            )
        except FloodWait as e:
            logger.warning(f"FloodWait creating invite link for {Var.FORCE_SUB_CHANNEL}: {e.value}s")
            await message.reply_text(Var.FLOOD_WAIT_TEXT.format(seconds=e.value), quote=True)
        except Exception as e:
            logger.error(f"Could not get channel info or invite link for {Var.FORCE_SUB_CHANNEL}: {e}", exc_info=True)
            await message.reply_text(
                f"{Var.FORCE_SUB_JOIN_TEXT}\n\n(Could not retrieve channel link automatically. Please ensure you have joined the required channel.)",
                quote=True
            )
        return False

    except FloodWait as e:
        logger.warning(f"FloodWait checking membership for {message.from_user.id} in {Var.FORCE_SUB_CHANNEL}: {e.value}s")
        await message.reply_text(Var.FLOOD_WAIT_TEXT.format(seconds=e.value), quote=True)
        return False

    except Exception as e:
        logger.error(f"Error checking membership for {message.from_user.id} in {Var.FORCE_SUB_CHANNEL}: {e}", exc_info=True)
        await message.reply_text("An error occurred while checking channel membership.", quote=True)
        return False


def attach_handlers(app: Client) -> None:
    """
    Register all bot command and message handlers to the provided client instance.

    This function sets up all the event handlers for the Telegram bot including:
    - Command handlers (/start, /help, /login, /logout, etc.)
    - Message handlers for file uploads and URL processing
    - Callback query handlers for interactive buttons
    - Rate limiting and security checks

    Args:
        app (Client): The Pyrogram client instance to attach handlers to
    """
    logger.info("Attaching bot command and message handlers...")

    # Inline keyboard builder for /start command
    def build_start_keyboard(force_sub_link: str = None) -> InlineKeyboardMarkup | None:
        buttons = []

        # Join Channel button (if force subscription is enabled)
        if force_sub_link and Var.FORCE_SUB_CHANNEL:
            buttons.append([InlineKeyboardButton("🔗 Join Channel", url=force_sub_link)])

        # Optional: Login shortcut if allowed and BASE_URL is public
        try:
            session_url = f"{Var.BASE_URL}/session"
            is_localhost = any(h in session_url.lower() for h in ["localhost", "127.0.0.1", "0.0.0.0"])  # Telegram blocks localhost
            if Var.ALLOW_USER_LOGIN and not is_localhost:
                buttons.append([InlineKeyboardButton("🔐 Login", url=session_url)])
        except Exception:
            pass

        # Row: Help / About / Close
        buttons.append([
            InlineKeyboardButton("❓ Help", callback_data="start:help"),
            InlineKeyboardButton("ℹ️ About", callback_data="start:about"),
            InlineKeyboardButton("✖️ Close", callback_data="start:close")
        ])

        return InlineKeyboardMarkup(buttons) if buttons else None

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message) -> None:
        """
        Handle the /start command for new users.

        This handler welcomes users, adds them to the database, and provides
        an interactive keyboard with help options and force subscription links
        if configured.

        Args:
            client (Client): The Pyrogram client instance
            message (Message): The /start command message
        """
        force_sub_link = None
        if Var.FORCE_SUB_CHANNEL:
            try:
                # Get or create force subscription channel invite link
                fsub_chat = await client.get_chat(Var.FORCE_SUB_CHANNEL)
                invite_link = fsub_chat.invite_link
                if not invite_link:
                    invite_link_obj = await client.create_chat_invite_link(Var.FORCE_SUB_CHANNEL)
                    invite_link = invite_link_obj.invite_link
                force_sub_link = invite_link
            except Exception as e:
                logger.warning(f"Could not get ForceSub channel info for start message: {e}")

        user_id = message.from_user.id
        try:
            # Add user to database for tracking and broadcast functionality
            await add_user(user_id)
        except Exception as e:
            logger.error(f"Database error adding user {user_id} on start: {e}")

        # Send welcome message with interactive keyboard
        start_text = Var.START_TEXT.format(mention=message.from_user.mention)

        await message.reply_text(
            start_text,
            quote=True,
            disable_web_page_preview=True,
            reply_markup=build_start_keyboard(force_sub_link)
        )

    @app.on_message(filters.command("help") & filters.private)
    async def help_handler(client: Client, message: Message):
        await message.reply_text(Var.HELP_TEXT, quote=True, disable_web_page_preview=True)

    @app.on_message(filters.command("about") & filters.private)
    async def about_handler(client: Client, message: Message):
        await message.reply_text(Var.ABOUT_TEXT, quote=True, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^start:(help|about|close)$"))
    async def start_menu_callbacks(client: Client, callback_query):
        action = callback_query.data.split(":", 1)[1]
        try:
            if action == "help":
                await callback_query.message.edit_text(
                    Var.HELP_TEXT,
                    disable_web_page_preview=True,
                    reply_markup=build_start_keyboard()
                )
            elif action == "about":
                await callback_query.message.edit_text(
                    Var.ABOUT_TEXT,
                    disable_web_page_preview=True,
                    reply_markup=build_start_keyboard()
                )
            elif action == "close":
                await callback_query.message.delete()
        except Exception:
            # Fallback to answering the callback if edit/delete fails
            await callback_query.answer("Action completed.", show_alert=False)
        else:
            await callback_query.answer()

    @app.on_message(filters.command("logs") & filters.private)
    async def logs_handler(client: Client, message: Message):
        """Handle the /logs command for admins to view logs."""
        user_id = message.from_user.id
        
        if not Var.ADMINS or user_id not in Var.ADMINS:
            await message.reply_text("❌ You don't have permission to access logs.", quote=True)
            logger.warning(f"Unauthorized logs access attempt by user {user_id}")
            return
        
        command_parts = message.text.split()
        
        log_file_path = "tgdlbot.log"
        if not os.path.exists(log_file_path):
            await message.reply_text("❌ Log file not found.", quote=True)
            return
        
        file_stats = os.stat(log_file_path)
        file_size = file_stats.st_size
        last_modified = datetime.datetime.fromtimestamp(file_stats.st_mtime).isoformat()
        
        if len(command_parts) == 1:
            processing_msg = await message.reply_text("⏳ Uploading log file...", quote=True)
            try:
                await client.send_document(
                    chat_id=user_id,
                    document=log_file_path,
                    caption=f"📋 **Log File ({humanbytes(file_size)})** | Last Modified: {last_modified}"
                )
                await processing_msg.delete()
                logger.info(f"Full log file uploaded for admin {user_id}")
                return
            except Exception as e:
                logger.error(f"Error uploading log file for admin {user_id}: {e}", exc_info=True)
                await processing_msg.edit_text(f"❌ Error uploading log file: {str(e)}")
                return
        
        # Parse command arguments
        limit = 50
        level = "ALL"
        filter_text = ""
        
        for i, part_arg in enumerate(command_parts[1:], 1):
            if part_arg.startswith("limit="):
                try:
                    limit = min(int(part_arg.split("=")[1]), 200)
                except:
                    pass
            elif part_arg.startswith("level="):
                level = part_arg.split("=")[1].upper()
            elif part_arg.startswith("filter="):
                filter_text = part_arg.split("=")[1]
        
        level_priority = {
            'DEBUG': 0,
            'INFO': 1,
            'WARNING': 2,
            'ERROR': 3,
            'CRITICAL': 4
        }
        
        min_level_priority = level_priority.get(level, -1) if level != 'ALL' else -1
        
        try:
            processing_msg = await message.reply_text("⏳ Processing logs...", quote=True)
            
            matching_lines = []
            total_matching_lines = 0
            
            with open(log_file_path, 'r', encoding='utf-8', errors='replace') as file:
                lines = file.readlines()
                
                for line in reversed(lines):
                    current_line_level = None
                    for lvl_key in level_priority.keys():
                        if f" - {lvl_key} - " in line:
                            current_line_level = lvl_key
                            break
                    
                    if min_level_priority >= 0 and (current_line_level is None or 
                                                  level_priority.get(current_line_level, -1) < min_level_priority):
                        continue
                    
                    if filter_text and filter_text.lower() not in line.lower():
                        continue
                    
                    total_matching_lines += 1
                    
                    if total_matching_lines <= limit:
                        matching_lines.append(line.strip())
            
            if matching_lines:
                matching_lines.reverse()
                
                logs_text = f"📋 **Log File ({humanbytes(file_size)})** | Last Modified: {last_modified}\n"
                logs_text += f"🔍 Filter: Level={level}" + (f", Text='{filter_text}'" if filter_text else "") + "\n"
                logs_text += f"📊 Showing {len(matching_lines)}/{total_matching_lines} matching lines\n\n"
                
                chunk_size = 3800
                log_chunks = []
                current_chunk = ""
                
                for line in matching_lines:
                    if len(current_chunk) + len(line) + 2 > chunk_size:
                        log_chunks.append(current_chunk)
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
                
                if current_chunk:
                    log_chunks.append(current_chunk)
                
                await processing_msg.edit_text(logs_text + f"```\n{log_chunks[0]}```")
                
                for chunk_idx, chunk in enumerate(log_chunks[1:], 1):
                    await message.reply_text(f"```\n{chunk}```", quote=True)
                    await asyncio.sleep(0.5)
                
                logger.info(f"Logs viewed by admin {user_id} (Level: {level}, Filter: {filter_text})")
            else:
                await processing_msg.edit_text(f"❗ No log entries match your criteria (Level: {level}, Filter: {filter_text})")
        
        except Exception as e:
            logger.error(f"Error reading logs for admin {user_id}: {e}", exc_info=True)
            await message.reply_text(f"❌ Error reading logs: {str(e)}", quote=True)

    @app.on_message(filters.command("stats") & filters.private)
    async def stats_handler(client: Client, message: Message):
        """Handle the /stats command for admins to view memory usage and system stats."""
        user_id = message.from_user.id
        
        if not Var.ADMINS or user_id not in Var.ADMINS:
            await message.reply_text("❌ You don't have permission to access system stats.", quote=True)
            logger.warning(f"Unauthorized stats access attempt by user {user_id}")
            return
        
        try:
            processing_msg = await message.reply_text("⏳ Gathering system statistics...", quote=True)
            
            from StreamBot.utils.memory_manager import memory_manager
            from StreamBot.utils.stream_cleanup import stream_tracker
            from StreamBot.utils.smart_logger import SmartRateLimitedLogger
            
            memory_usage = memory_manager.get_memory_usage()
            active_streams = stream_tracker.get_active_count()
            
            from StreamBot.__main__ import BOT_START_TIME
            import datetime
            if BOT_START_TIME:
                uptime_delta = datetime.datetime.now(datetime.timezone.utc) - BOT_START_TIME
                uptime_days = uptime_delta.days
                uptime_hours, remainder = divmod(uptime_delta.seconds, 3600)
                uptime_minutes, uptime_seconds = divmod(remainder, 60)
                uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m {uptime_seconds}s"
            else:
                uptime_str = "Unknown"
            
            try:
                cache_stats = rate_limited_logger.get_cache_stats()
                cache_info = f"📝 **Logger Cache**: {cache_stats['cache_size']}/{cache_stats['max_cache_size']} entries\n"
            except:
                cache_info = "📝 **Logger Cache**: Unable to retrieve stats\n"
            
            try:
                from StreamBot.__main__ import CLIENT_MANAGER_INSTANCE
                client_count = len(CLIENT_MANAGER_INSTANCE.all_clients) if CLIENT_MANAGER_INSTANCE else 0
            except:
                client_count = "N/A"
            
            # Get bandwidth usage information
            try:
                bandwidth_usage = await get_current_bandwidth_usage()
                bandwidth_info = f"""
📊 **Bandwidth Usage**:
• Used this month: {bandwidth_usage['gb_used']:.3f} GB
• Limit: {Var.BANDWIDTH_LIMIT_GB} GB {'(enabled)' if Var.BANDWIDTH_LIMIT_GB > 0 else '(disabled)'}
• Month: {bandwidth_usage['month_key']}"""
            except Exception as e:
                bandwidth_info = f"""
📊 **Bandwidth Usage**:
• Error retrieving data: {str(e)}"""
            
            memory_text = f"""
📊 **System Statistics**

🧠 **Memory Usage**:
• RSS Memory: {memory_usage.get('rss_mb', 'N/A')} MB
• VMS Memory: {memory_usage.get('vms_mb', 'N/A')} MB  
• Memory %: {memory_usage.get('percent', 'N/A')}%

🌐 **Active Resources**:
• Active Streams: {active_streams}
• Telegram Clients: {client_count}
{bandwidth_info}

{cache_info}
⏰ **Uptime**: {uptime_str}
🕐 **Timestamp**: {memory_usage.get('timestamp', 'N/A')}

💡 **Memory cleanup runs automatically every hour**
"""
            
            await processing_msg.edit_text(memory_text)
            logger.info(f"System stats viewed by admin {user_id}")
            
        except Exception as e:
            logger.error(f"Error getting system stats for admin {user_id}: {e}", exc_info=True)
            await message.reply_text(f"❌ Error retrieving system stats: {str(e)}", quote=True)

    @app.on_message(filters.command("login") & filters.private)
    async def login_handler(client: Client, message: Message):
        """Handle the /login command to provide session generator web link."""
        user_id = message.from_user.id
        
        # Check bandwidth limit (admins bypass this check)
        if user_id not in Var.ADMINS:
            if await is_bandwidth_limit_exceeded():
                await message.reply_text(Var.BANDWIDTH_LIMIT_EXCEEDED_TEXT, quote=True)
                return
        
        # Check if user has permission to use session generator
        if not Var.ALLOW_USER_LOGIN and (not Var.ADMINS or user_id not in Var.ADMINS):
            await message.reply_text(
                "🔒 **Session Generator Access Restricted**\n\n"
                "The session generator feature is currently restricted to administrators only.\n\n"
                "Contact the bot administrator if you need access to private content features.",
                quote=True
            )
            logger.info(f"Session generator access denied for non-admin user {user_id}")
            return
        
        try:
            # Add user to database if not exists (efficient single operation)
            await add_user(user_id)
            
            # Check if user already has an active session efficiently
            from StreamBot.database.user_sessions import check_user_has_session
            has_active_session = await check_user_has_session(user_id)
            
            session_generator_url = f"{Var.BASE_URL}/session"
            
            # Check if URL is localhost (Telegram doesn't allow localhost in inline buttons)
            is_localhost = any(host in session_generator_url.lower() for host in ['localhost', '127.0.0.1', '0.0.0.0'])
            
            if has_active_session:
                if is_localhost:
                    response_text = build_active_session_message(session_generator_url, True)
                    await message.reply_text(
                        response_text,
                        quote=True,
                        disable_web_page_preview=True
                    )
                else:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔐 Login to Session Generator", url=session_generator_url)]
                    ])
                    response_text = build_active_session_message(session_generator_url, False)
                    await message.reply_text(
                        response_text,
                        quote=True,
                        reply_markup=keyboard,
                        disable_web_page_preview=True
                    )

            else:
                if is_localhost:
                    response_text = build_login_message(session_generator_url, True)
                    await message.reply_text(
                        response_text,
                        quote=True,
                        disable_web_page_preview=True
                    )
                else:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔐 Login to Session Generator", url=session_generator_url)]
                    ])
                    response_text = build_login_message(session_generator_url, False)
                    await message.reply_text(
                        response_text,
                        quote=True,
                        reply_markup=keyboard,
                        disable_web_page_preview=True
                    )
            
            logger.info(f"Login command used by user {user_id} ({'localhost' if is_localhost else 'public'} mode)")
            
        except Exception as e:
            logger.error(f"Error in login command for user {user_id}: {e}", exc_info=True)
            await message.reply_text(
                "❌ Error processing login command. Please try again later.",
                quote=True
            )

    @app.on_message(filters.command("logout") & filters.private)
    async def logout_handler(client: Client, message: Message):
        """Handle the /logout command to revoke user session."""
        user_id = message.from_user.id
        
        # Check bandwidth limit (admins bypass this check)
        if user_id not in Var.ADMINS:
            if await is_bandwidth_limit_exceeded():
                await message.reply_text(Var.BANDWIDTH_LIMIT_EXCEEDED_TEXT, quote=True)
                return
        
        # Check if user has permission to use session generator
        if not Var.ALLOW_USER_LOGIN and (not Var.ADMINS or user_id not in Var.ADMINS):
            await message.reply_text(
                "🔒 **Session Generator Access Restricted**\n\n"
                "The session generator feature is currently restricted to administrators only.",
                quote=True
            )
            logger.info(f"Session generator logout access denied for non-admin user {user_id}")
            return
        
        try:
            from StreamBot.database.user_sessions import check_user_has_session, revoke_user_session
            from StreamBot.link_handler import user_session_streamer
            
            # Check if user has an active session efficiently
            has_active_session = await check_user_has_session(user_id)
            
            if not has_active_session:
                await message.reply_text(
                    "ℹ️ **No Active Session**\n\nYou don't have an active session to logout from.\n\nUse `/login` to create a new session.",
                    quote=True
                )
                return
            
            # Revoke (hard delete) the user's session
            success = await revoke_user_session(user_id)
            
            if success:
                # Cleanup any active in-memory user client to immediately invalidate links
                try:
                    await user_session_streamer.cleanup_user_client(user_id)
                except Exception:
                    pass

                # Remove any generated user_session_files entries for this user to invalidate links
                try:
                    if hasattr(client, 'user_session_files') and isinstance(client.user_session_files, dict):
                        keys_to_delete = [k for k, v in client.user_session_files.items() if v.get('user_id') == user_id]
                        for k in keys_to_delete:
                            del client.user_session_files[k]
                except Exception:
                    pass

                response_text = """✅ **Successfully Logged Out**

Your session has been revoked and all generated download links are now invalid.

🔒 **What this means:**
• All your previous download links are now disabled
• You cannot generate new download links until you login again
• Your session data has been securely removed

To generate download links again, use `/login` to create a new session."""

                await message.reply_text(response_text, quote=True)
                logger.info(f"User {user_id} successfully logged out - session revoked")
                
            else:
                await message.reply_text(
                    "❌ **Logout Failed**\n\nThere was an error revoking your session. Please try again or contact support.",
                    quote=True
                )
                logger.error(f"Failed to revoke session for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error in logout command for user {user_id}: {e}", exc_info=True)
            await message.reply_text(
                "❌ Error processing logout command. Please try again later.",
                quote=True
            )

    @app.on_message(filters.command("session") & filters.private)
    async def session_handler(client: Client, message: Message):
        """Handle the /session command to show session info and validate it."""
        from StreamBot.database.user_sessions import check_user_has_session, get_user_session_info, revoke_user_session
        from StreamBot.link_handler import user_session_streamer
        from pyrogram.errors import AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan
        user_id = message.from_user.id
        
        # Check bandwidth limit (admins bypass this check)
        if user_id not in Var.ADMINS:
            if await is_bandwidth_limit_exceeded():
                await message.reply_text(Var.BANDWIDTH_LIMIT_EXCEEDED_TEXT, quote=True)
                return
        
        if not await check_user_has_session(user_id):
            await message.reply_text("ℹ️ You don't have an active session. Use /login to create one.", quote=True)
            return
            
        user_client = await user_session_streamer.get_user_client(user_id)
        if not user_client:
            await revoke_user_session(user_id)
            await message.reply_text("❌ Your session is invalid or has been revoked. Please use /login to create a new one.", quote=True)
            return
            
        try:
            from pyrogram.raw import functions
            raw_auths = await user_client.invoke(functions.account.GetAuthorizations())
            current_auth = next((auth for auth in raw_auths.authorizations if auth.current), None)
            if not current_auth:
                raise ValueError("No current authorization found")
                
            session_info = await get_user_session_info(user_id)
            created_at = datetime.datetime.fromtimestamp(current_auth.date_created).strftime("%Y-%m-%d %H:%M:%S")
            last_active = datetime.datetime.fromtimestamp(current_auth.date_active).strftime("%Y-%m-%d %H:%M:%S")
            
            msg = "**Your Session Information:**\n\n"
            msg += f"**Device:** {current_auth.device_model}\n"
            msg += f"**Platform:** {current_auth.platform}\n"
            msg += f"**System Version:** {current_auth.system_version}\n"
            msg += f"**App Name:** {current_auth.app_name}\n"
            msg += f"**App Version:** {current_auth.app_version}\n"
            msg += f"**Created:** {created_at}\n"
            msg += f"**Last Active:** {last_active}\n"
            msg += f"**IP:** {current_auth.ip}\n"
            msg += f"**Country:** {current_auth.country}\n"
            msg += f"**Region:** {current_auth.region}\n"
            if session_info and 'user_info' in session_info and session_info['user_info'].get('username'):
                msg += f"**Username:** @{session_info['user_info']['username']}\n"
            msg += "\n**Status:** Active"
            
            await message.reply_text(msg, quote=True)
            
        except (AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan, ValueError, Exception) as e:
            logger.error(f"Session validation failed for user {user_id}: {str(e)}", exc_info=True)
            await revoke_user_session(user_id)
            await message.reply_text("❌ Your session is invalid or has been revoked. Please use /login to create a new one.", quote=True)
        finally:
            await user_session_streamer.cleanup_user_client(user_id)

    @app.on_message(filters.private & filters.text & filters.regex(r'https?://t\.me/.*'))
    async def link_handler(client: Client, message: Message):
        """Handle incoming Telegram message links."""
        user_id = message.from_user.id
        
        # Basic checks (rate limit, bandwidth, force sub)
        if user_id not in Var.ADMINS:
            if Var.MAX_LINKS_PER_DAY > 0:
                can_generate = await bot_rate_limiter.check_and_record_link_generation(user_id)
                if not can_generate:
                    _, wait_time_seconds = await bot_rate_limiter.get_user_link_count_and_wait_time(user_id)
                    wait_hours = wait_time_seconds / 3600
                    wait_minutes = (wait_time_seconds % 3600) / 60

                    if wait_time_seconds > 0:
                        reply_text = Var.RATE_LIMIT_EXCEEDED_TEXT.format(
                            max_links=Var.MAX_LINKS_PER_DAY,
                            wait_hours=wait_hours,
                            wait_minutes=wait_minutes
                        )
                    else:
                        reply_text = Var.RATE_LIMIT_EXCEEDED_TEXT_NO_WAIT.format(max_links=Var.MAX_LINKS_PER_DAY)

                    await message.reply_text(reply_text, quote=True)
                    return
            else:
                await bot_rate_limiter.check_and_record_link_generation(user_id)

        if await is_bandwidth_limit_exceeded():
            await message.reply_text(Var.BANDWIDTH_LIMIT_EXCEEDED_TEXT, quote=True)
            return

        if not await check_force_sub(client, message):
            return

        processing_msg = await message.reply_text("⏳ Accessing your private content and generating download link...", quote=True)
        
        result = await get_message_from_link(user_id, message.text)

        if isinstance(result, str):
            # An error occurred
            await processing_msg.edit_text(f"❌ **Error:** {result}")
            return

        # result is a tuple (message, user_client)
        target_message, user_client = result
        
        try:
            # Get file attributes from the message
            _file_id, file_name, file_size, file_mime_type, _file_unique_id = get_file_attr(target_message)
            file_size_str = humanbytes(file_size)

            if not file_name:
                await processing_msg.edit_text("❌ **Error:** Could not determine file information.")
                return

            # Create a virtual message ID for user session files
            # Using a combination that won't conflict with real message IDs
            virtual_msg_id = f"user_{user_id}_{target_message.chat.id}_{target_message.id}"
            
            # Store the user session file info in the existing streaming system
            if not hasattr(client, 'user_session_files'):
                client.user_session_files = {}
            
            client.user_session_files[virtual_msg_id] = {
                'user_id': user_id,
                'chat_id': target_message.chat.id,
                'message_id': target_message.id,
                'file_name': file_name,
                'file_size': file_size,
                'file_mime_type': file_mime_type,
                'created_at': asyncio.get_event_loop().time()
            }

            # Generate download link using the same structure as forwarded files
            encoded_msg_id = encode_message_id(virtual_msg_id)
            download_link = f"{Var.BASE_URL}/dl/{encoded_msg_id}"

            # Process download link (shorten if file size exceeds threshold)
            processed_download_link = await process_link(download_link, file_size)

            is_video = is_video_file(file_mime_type)
            reply_markup = None
            if is_video and Var.VIDEO_FRONTEND_URL:
                # For private content, the stream URL should also be shortened if needed
                stream_link = f"{Var.BASE_URL}/dl/{encoded_msg_id}"  # Same endpoint for streaming private content
                processed_stream_link = stream_link

                import urllib.parse
                encoded_stream_uri = urllib.parse.quote(processed_stream_link)
                video_play_url = f"{Var.VIDEO_FRONTEND_URL}?stream={encoded_stream_uri}"
                video_play_url = await process_link(video_play_url, file_size)
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Play Video", url=video_play_url)]])

            await processing_msg.edit_text(
                f"✅ **Download Link Generated!**\n\n"
                f"**File Name:** `{file_name}`\n"
                f"**File Size:** {file_size_str}\n\n"
                f"**Link:** {processed_download_link}\n\n"
                f"⏳ **Expires:** In approximately 24 hours.\n\n"
                f"🔒 This link uses your personal session to access the private content.",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            logger.info(f"User stream link generated for user {user_id} from URL: {message.text}")

        except Exception as e:
            logger.error(f"Error generating user stream link for user {user_id}: {e}", exc_info=True)
            await processing_msg.edit_text("❌ **Error:** An unexpected error occurred while processing your request.")


    @app.on_message(filters.private & filters.incoming & (
        filters.document | filters.video | filters.audio | filters.photo |
        filters.animation | filters.sticker | filters.voice
    ))
    async def file_handler(client: Client, message: Message) -> None:
        """
        Handle incoming media messages and generate secure download links.

        This handler processes uploaded files by forwarding them to a log channel,
        then generates time-limited download links. It includes comprehensive
        security checks including rate limiting, bandwidth monitoring, and
        force subscription verification.

        Args:
            client (Client): The Pyrogram client instance
            message (Message): The message containing the uploaded file
        """
        user_id = message.from_user.id

        # Rate limiting check - ensure proper enforcement
        if user_id not in Var.ADMINS:  # Always check for non-admins
            if Var.MAX_LINKS_PER_DAY > 0:  # Only if limit is positive
                can_generate = await bot_rate_limiter.check_and_record_link_generation(user_id)
                if not can_generate:
                    _, wait_time_seconds = await bot_rate_limiter.get_user_link_count_and_wait_time(user_id)
                    wait_hours = wait_time_seconds / 3600
                    wait_minutes = (wait_time_seconds % 3600) / 60

                    if wait_time_seconds > 0:
                        reply_text = Var.RATE_LIMIT_EXCEEDED_TEXT.format(
                            max_links=Var.MAX_LINKS_PER_DAY,
                            wait_hours=wait_hours,
                            wait_minutes=wait_minutes
                        )
                    else:
                        reply_text = Var.RATE_LIMIT_EXCEEDED_TEXT_NO_WAIT.format(max_links=Var.MAX_LINKS_PER_DAY)

                    await message.reply_text(reply_text, quote=True)
                    return
            else:
                # If MAX_LINKS_PER_DAY is 0 or negative, still record for stats but don't limit
                await bot_rate_limiter.check_and_record_link_generation(user_id)

        # Bandwidth limit check
        if await is_bandwidth_limit_exceeded():
            logger.warning(f"File upload from user {user_id} rejected: bandwidth limit exceeded")
            await message.reply_text(Var.BANDWIDTH_LIMIT_EXCEEDED_TEXT, quote=True)
            return

        # Force subscription check
        if not await check_force_sub(client, message):
            return

        if not Var.LOG_CHANNEL:
            logger.error("LOG_CHANNEL is not configured. Cannot process files.")
            await message.reply_text("Bot configuration error: Log channel not set.", quote=True)
            return

        processing_msg = await message.reply_text(Var.GENERATING_LINK_TEXT, quote=True)

        try:
            log_msg = await message.forward(chat_id=Var.LOG_CHANNEL)

            if not log_msg or not log_msg.id:
                await processing_msg.edit_text(Var.ERROR_TEXT)
                logger.error(f"Failed to forward message {message.id} from user {message.from_user.id} to log channel {Var.LOG_CHANNEL}.")
                return

            # Get file attributes for response
            _file_id, file_name, file_size, file_mime_type, _file_unique_id = get_file_attr(log_msg)
            file_size_str = humanbytes(file_size)
            if not file_name:
                await processing_msg.edit_text(Var.ERROR_TEXT)
                logger.error(f"Could not get file attributes for message {log_msg.id}")
                return

            # Generate download link
            encoded_msg_id = encode_message_id(log_msg.id)
            download_link = f"{Var.BASE_URL}/dl/{encoded_msg_id}"

            # Process download link (shorten if file size exceeds threshold)
            processed_download_link = await process_link(download_link, file_size)

            # Check if it's a video file and create appropriate response
            is_video = is_video_file(file_mime_type)
            reply_markup = None

            if is_video and Var.VIDEO_FRONTEND_URL:
                # Create inline keyboard with Play Video button - use stream URL directly
                stream_link = f"{Var.BASE_URL}/stream/{encoded_msg_id}"

                import urllib.parse
                encoded_stream_uri = urllib.parse.quote(stream_link)
                video_play_url = f"{Var.VIDEO_FRONTEND_URL}?stream={encoded_stream_uri}"
                video_play_url = await process_link(video_play_url, file_size)

                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎬 Play Video", url=video_play_url)]
                ])

            # Send success response
            await processing_msg.edit_text(
                Var.LINK_GENERATED_TEXT.format(
                    file_name=file_name,
                    file_size=file_size_str,
                    download_link=processed_download_link
                ),
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )

            logger.info(f"Download link generated for user {user_id}, file: {file_name}")

        except FloodWait as e:
            logger.warning(f"FloodWait during file processing for user {user_id}: {e.value}s")
            await processing_msg.edit_text(Var.FLOOD_WAIT_TEXT.format(seconds=e.value))

        except Exception as e:
            logger.error(f"Error processing file from user {user_id}: {e}", exc_info=True)
            await processing_msg.edit_text(Var.ERROR_TEXT)

    @app.on_message(filters.command("broadcast") & filters.private)
    async def broadcast_handler(client: Client, message: Message):
        """Handle the /broadcast command for admins."""
        user_id = message.from_user.id
        
        if not Var.ADMINS or user_id not in Var.ADMINS:
            await message.reply_text(Var.BROADCAST_ADMIN_ONLY, quote=True)
            return
        
        if not message.reply_to_message:
            await message.reply_text(Var.BROADCAST_REPLY_PROMPT, quote=True)
            return
        
        broadcast_message = message.reply_to_message
        status_msg = await message.reply_text(Var.BROADCAST_STARTING, quote=True)
        
        try:
            all_users = await full_userbase()
            total_users = len(all_users)
            successful = 0
            blocked_deleted = 0
            unsuccessful = 0
            
            logger.info(f"Starting broadcast to {total_users} users initiated by admin {user_id}")
            
            for idx, user_data in enumerate(all_users):
                try:
                    target_user_id = user_data.get('user_id')
                    if not target_user_id:
                        unsuccessful += 1
                        continue
                    
                    await broadcast_message.copy(chat_id=target_user_id)
                    successful += 1
                    
                    # Update status every 50 users
                    if (idx + 1) % 50 == 0:
                        try:
                            await status_msg.edit_text(
                                Var.BROADCAST_STATUS_UPDATE.format(
                                    total=total_users,
                                    successful=successful,
                                    blocked_deleted=blocked_deleted,
                                    unsuccessful=unsuccessful
                                )
                            )
                        except:
                            pass
                    
                    await asyncio.sleep(0.05)
                    
                except (UserIsBlocked, InputUserDeactivated):
                    try:
                        await del_user(target_user_id)
                        blocked_deleted += 1
                        logger.debug(f"Removed blocked/deleted user {target_user_id} from database")
                    except:
                        unsuccessful += 1
                        
                except FloodWait as fw:
                    logger.warning(f"FloodWait during broadcast: {fw.value}s")
                    await asyncio.sleep(fw.value)
                    try:
                        await broadcast_message.copy(chat_id=target_user_id)
                        successful += 1
                    except:
                        unsuccessful += 1
                        
                except Exception as e:
                    logger.error(f"Failed to send broadcast to user {target_user_id}: {e}")
                    unsuccessful += 1
            
            # Final status
            await status_msg.edit_text(
                Var.BROADCAST_COMPLETED.format(
                    total=total_users,
                    successful=successful,
                    blocked_deleted=blocked_deleted,
                    unsuccessful=unsuccessful
                )
            )
            
            logger.info(f"Broadcast completed by admin {user_id}: {successful}/{total_users} successful")
            
        except Exception as e:
            logger.error(f"Error during broadcast by admin {user_id}: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ Broadcast failed: {str(e)}")

    logger.info("All bot handlers attached successfully")