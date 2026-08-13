"""
Telegram Bot handlers and message processing for the Download Link Generator.

This module contains all bot command handlers, message processors, and helper
functions for managing user interactions with the Telegram bot. It handles:

- Command processing (/start, /help, /login, /logout, etc.)
- File upload processing with download link generation
- Private channel link processing via user sessions
- User management and database operations (including admin broadcast target list)

All handlers are designed to be memory-efficient and thread-safe.
"""

import logging
import asyncio
import math
import os
import datetime
import secrets
import pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from .database.database import add_user, del_user, full_userbase, get_user_language, set_user_language
from .locale_strings import t, LANG_PICKER_ROWS
from .database.user_access import (
    is_user_allowed,
    add_allowed_user,
    remove_allowed_user,
    create_pending_txn,
    set_pending_txn_paid,
    set_pending_txn_screenshot,
    cancel_pending_txn,
    get_latest_pending_txn_for_user,
    get_pending_txn,
    approve_pending_txn,
    reject_pending_txn,
    mark_pending_txn_submitted,
    is_user_admin,
    add_admin_user,
)
from .database.analytics import record_link_generated
from .web.dashboard_auth import create_owner_one_time_token
from .config import Var
from .utils.utils import get_file_attr, humanbytes, encode_message_id, is_video_file
from .utils.smart_logger import SmartRateLimitedLogger
from .link_handler import get_message_from_link
from .group_handler import attach_group_handlers

logger = logging.getLogger(__name__)

# Memory-efficient rate-limited logger for high-frequency operations
rate_limited_logger = SmartRateLimitedLogger(logger)


def is_privileged_user(user_id: int) -> bool:
    """Admin/owner bypass premium restrictions."""
    if user_id == Var.OWNER_ID:
        return True
    return bool(Var.ADMINS) and user_id in Var.ADMINS


async def user_has_premium_access(user_id: int) -> bool:
    """Return True if user can use the bot (owner/admin or added user)."""
    if is_privileged_user(user_id):
        return True
    if await is_user_admin(user_id):
        return True
    return await is_user_allowed(user_id)


def language_picker_rows() -> list[list[InlineKeyboardButton]]:
    """Inline buttons for /start language selection (English + requested locales)."""
    return [
        [InlineKeyboardButton(lbl, callback_data=f"lang:{code}") for lbl, code in row]
        for row in LANG_PICKER_ROWS
    ]


def premium_access_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Entry keyboard for non-premium users, including language picker."""
    rows = [
        [InlineKeyboardButton(t(lang, "premium_get_started"), callback_data="premium:buy")],
        [
            InlineKeyboardButton(t(lang, "premium_how_it_works"), callback_data="premium:howitworks"),
            InlineKeyboardButton(t(lang, "premium_features"), callback_data="premium:features"),
        ],
        [
            InlineKeyboardButton(t(lang, "premium_pricing"), callback_data="premium:pricing"),
            InlineKeyboardButton(t(lang, "premium_help"), callback_data="premium:help"),
        ],
    ]
    rows.extend(language_picker_rows())
    return InlineKeyboardMarkup(rows)


_DAYS_BUTTON_CHOICES = [1, 2, 3, 5, 7, 10, 14, 30]


def _ceil_money(amount: float, decimal_places: int = 2) -> float:
    """Round monetary amount up to a fixed number of decimal places (never extend subscription days)."""
    if amount <= 0:
        return amount
    factor = 10**decimal_places
    # Small epsilon avoids float noise like 1.0050000000000001 missing the ceil boundary.
    return math.ceil(amount * factor - 1e-9) / factor


def _method_label(method: str, lang: str) -> str:
    if method == "crypto":
        return t(lang, "pay_method_crypto")
    return t(lang, "pay_method_upi")


def buy_method_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(lang, "pay_btn_crypto"), callback_data="premium:method:crypto"),
                InlineKeyboardButton(t(lang, "pay_btn_upi"), callback_data="premium:method:upi"),
            ]
        ]
    )


def buy_days_keyboard(method: str, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for d in _DAYS_BUTTON_CHOICES:
        row.append(
            InlineKeyboardButton(
                t(lang, "pay_days_choice", n=d),
                callback_data=f"premium:days:{method}:{d}",
            )
        )
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def process_link(original_link: str, *_args, **_kwargs) -> str:
    """Return the direct link (no URL shortener or monetization layer)."""
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


def attach_handlers(app: Client) -> None:
    """
    Register all bot command and message handlers to the provided client instance.

    This function sets up all the event handlers for the Telegram bot including:
    - Command handlers (/start, /help, /login, /logout, etc.)
    - Message handlers for file uploads and URL processing
    - Callback query handlers for interactive buttons
    Args:
        app (Client): The Pyrogram client instance to attach handlers to
    """
    logger.info("Attaching bot command and message handlers...")
    attach_group_handlers(app)

    SESSION_GENERATOR_DISABLED_TEXT = (
        "🔒 **Session Generator Disabled**\n\n"
        "The session generator feature is currently disabled for all users.\n\n"
        "Please try again later."
    )

    # Inline keyboard builder for /start command (localized + language picker)
    def build_start_keyboard(lang: str) -> InlineKeyboardMarkup | None:
        buttons = []

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
            InlineKeyboardButton(t(lang, "btn_help"), callback_data="start:help"),
            InlineKeyboardButton(t(lang, "btn_about"), callback_data="start:about"),
            InlineKeyboardButton(t(lang, "btn_close"), callback_data="start:close"),
        ])
        buttons.extend(language_picker_rows())

        return InlineKeyboardMarkup(buttons) if buttons else None

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message) -> None:
        """
        Handle the /start command for new users.

        This handler welcomes users, adds them to the database, and provides
        an interactive keyboard with help options.

        Args:
            client (Client): The Pyrogram client instance
            message (Message): The /start command message
        """
        user_id = message.from_user.id
        try:
            # Add user to database for tracking and broadcast functionality
            await add_user(user_id)
        except Exception as e:
            logger.error(f"Database error adding user {user_id} on start: {e}")

        lang = await get_user_language(user_id)

        # Premium access gate for non-admin users.
        if not await user_has_premium_access(user_id):
            await message.reply_text(
                t(lang, "start_non_premium", mention=message.from_user.mention),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
            return

        # Send welcome message with interactive keyboard
        start_text = t(lang, "start_premium", mention=message.from_user.mention)

        await message.reply_text(
            start_text,
            quote=True,
            disable_web_page_preview=True,
            reply_markup=build_start_keyboard(lang),
        )

    @app.on_message(filters.command("help") & filters.private)
    async def help_handler(client: Client, message: Message):
        user_id = message.from_user.id
        lang = await get_user_language(user_id)
        if not await user_has_premium_access(user_id):
            await message.reply_text(
                t(lang, "premium_required"),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
            return
        await message.reply_text(t(lang, "help"), quote=True, disable_web_page_preview=True)

    @app.on_message(filters.command("about") & filters.private)
    async def about_handler(client: Client, message: Message):
        user_id = message.from_user.id
        lang = await get_user_language(user_id)
        if not await user_has_premium_access(user_id):
            await message.reply_text(
                t(lang, "premium_required"),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
            return
        await message.reply_text(
            t(
                lang,
                "about",
                pyro_version=getattr(pyrogram, "__version__", "unknown"),
                github_url=Var.GITHUB_REPO_URL or "https://github.com",
            ),
            quote=True,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^lang:(en|id|ms|ar|es|zh)$"))
    async def language_select_callback(client: Client, callback_query):
        """Persist language and refresh the welcome screen (premium or non-premium)."""
        user_id = callback_query.from_user.id
        lang_code = (callback_query.data or "").split(":")[-1]
        await set_user_language(user_id, lang_code)
        lang = await get_user_language(user_id)
        await callback_query.answer(t(lang, "lang_saved"), show_alert=False)

        mention = callback_query.from_user.mention
        try:
            if await user_has_premium_access(user_id):
                text = t(lang, "start_premium", mention=mention)
                markup = build_start_keyboard(lang)
            else:
                text = t(lang, "start_non_premium", mention=mention)
                markup = premium_access_keyboard(lang)
            await callback_query.message.edit_text(
                text,
                disable_web_page_preview=True,
                reply_markup=markup,
            )
        except Exception as e:
            logger.warning(f"language_select_callback edit_text failed: {e}")

    @app.on_callback_query(filters.regex(r"^start:(help|about|close)$"))
    async def start_menu_callbacks(client: Client, callback_query):
        action = callback_query.data.split(":", 1)[1]
        lang = await get_user_language(callback_query.from_user.id)
        try:
            if action == "help":
                await callback_query.message.edit_text(
                    t(lang, "help"),
                    disable_web_page_preview=True,
                    reply_markup=build_start_keyboard(lang),
                )
            elif action == "about":
                await callback_query.message.edit_text(
                    t(
                        lang,
                        "about",
                        pyro_version=getattr(pyrogram, "__version__", "unknown"),
                        github_url=Var.GITHUB_REPO_URL or "https://github.com",
                    ),
                    disable_web_page_preview=True,
                    reply_markup=build_start_keyboard(lang),
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
            
            memory_text = f"""
📊 **System Statistics**

🧠 **Memory Usage**:
• RSS Memory: {memory_usage.get('rss_mb', 'N/A')} MB
• VMS Memory: {memory_usage.get('vms_mb', 'N/A')} MB  
• Memory %: {memory_usage.get('percent', 'N/A')}%

🌐 **Active Resources**:
• Active Streams: {active_streams}
• Telegram Clients: {client_count}

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

    @app.on_message(filters.command("add") & filters.private)
    async def add_user_handler(client: Client, message: Message):
        """Grant bot access to a user (owner/admin only)."""
        requester_id = message.from_user.id

        if not is_privileged_user(requester_id) and not await is_user_admin(requester_id):
            await message.reply_text("❌ Only the owner/admin can use this command.", quote=True)
            return

        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.reply_text("Usage: /add <user_id>", quote=True)
            return

        try:
            target_user_id = int(parts[1])
        except ValueError:
            await message.reply_text("Invalid user_id. It must be a number.", quote=True)
            return

        ok = await add_admin_user(target_user_id)
        if not ok:
            await message.reply_text("Failed to add user. Please try again.", quote=True)
            return

        await message.reply_text(
            f"✅ User `{target_user_id}` added as admin (dynamic admin).",
            quote=True,
            disable_web_page_preview=True,
        )

    @app.on_message(filters.command("ban") & filters.private)
    async def ban_user_handler(client: Client, message: Message):
        """Remove user from subscription (does not ban Telegram account)."""
        requester_id = message.from_user.id
        if not is_privileged_user(requester_id) and not await is_user_admin(requester_id):
            await message.reply_text("❌ Only owner/admin can use this command.", quote=True)
            return

        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.reply_text("Usage: /ban <user_id>", quote=True)
            return

        try:
            target_user_id = int(parts[1])
        except ValueError:
            await message.reply_text("Invalid user_id. It must be a number.", quote=True)
            return

        removed = await remove_allowed_user(target_user_id)

        # Invalidate in-memory private-session links generated by this user immediately.
        try:
            if hasattr(client, "user_session_files") and isinstance(client.user_session_files, dict):
                keys_to_delete = [k for k, v in client.user_session_files.items() if v.get("user_id") == target_user_id]
                for k in keys_to_delete:
                    del client.user_session_files[k]
        except Exception:
            pass

        if removed:
            await message.reply_text(
                f"✅ User `{target_user_id}` removed from subscription.\n"
                "Their generated links will stop working.",
                quote=True,
            )
        else:
            await message.reply_text(
                f"ℹ️ User `{target_user_id}` was not in active subscription list.",
                quote=True,
            )

    @app.on_message(filters.command("dashboard") & filters.private)
    async def dashboard_url_handler(client: Client, message: Message):
        """Owner-only command: generate one-time dashboard URL (30 minutes)."""
        user_id = message.from_user.id
        if user_id != Var.OWNER_ID:
            await message.reply_text("❌ Only the owner can use /dashboard.", quote=True)
            return

        token = create_owner_one_time_token(owner_id=user_id, expires_minutes=30)
        dashboard_url = f"{Var.BASE_URL}/owner/dashboard?token={token}"
        await message.reply_text(
            "Owner dashboard link (one-time use, expires in 30 minutes):\n"
            f"{dashboard_url}",
            quote=True,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^premium:buy$"))
    async def premium_buy_entry(client: Client, callback_query):
        """Show payment method selection."""
        await callback_query.answer()
        lang = await get_user_language(callback_query.from_user.id)
        try:
            await callback_query.message.edit_text(
                t(lang, "pay_choose_method"),
                reply_markup=buy_method_keyboard(lang),
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning(f"premium_buy_entry edit_text failed: {e}")
            await callback_query.message.reply_text(
                t(lang, "pay_choose_method"),
                reply_markup=buy_method_keyboard(lang),
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex(r"^premium:features$"))
    async def premium_features_entry(client: Client, callback_query):
        """Show features text for non-premium users."""
        await callback_query.answer()
        lang = await get_user_language(callback_query.from_user.id)
        try:
            await callback_query.message.edit_text(
                t(lang, "features"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
        except Exception:
            await callback_query.message.reply_text(
                t(lang, "features"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex(r"^premium:howitworks$"))
    async def premium_howitworks_entry(client: Client, callback_query):
        """Show how it works text for non-premium users."""
        await callback_query.answer()
        lang = await get_user_language(callback_query.from_user.id)
        try:
            await callback_query.message.edit_text(
                t(lang, "how_it_works"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
        except Exception:
            await callback_query.message.reply_text(
                t(lang, "how_it_works"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex(r"^premium:pricing$"))
    async def premium_pricing_entry(client: Client, callback_query):
        """Show pricing overview for non-premium users."""
        await callback_query.answer()
        lang = await get_user_language(callback_query.from_user.id)
        try:
            await callback_query.message.edit_text(
                t(lang, "pricing"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
        except Exception:
            await callback_query.message.reply_text(
                t(lang, "pricing"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex(r"^premium:help$"))
    async def premium_help_entry(client: Client, callback_query):
        """Show help text for non-premium users."""
        await callback_query.answer()
        lang = await get_user_language(callback_query.from_user.id)
        try:
            await callback_query.message.edit_text(
                t(lang, "help"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
        except Exception:
            await callback_query.message.reply_text(
                t(lang, "help"),
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex(r"^premium:method:(crypto|upi)$"))
    async def premium_method_selected(client: Client, callback_query):
        """Show days selection after payment method."""
        await callback_query.answer()
        data = callback_query.data or ""
        method = data.split(":")[-1]
        lang = await get_user_language(callback_query.from_user.id)
        txt = t(lang, "pay_method_selected_header", method=_method_label(method, lang)) + t(
            lang, "pay_choose_duration_hint"
        )
        try:
            await callback_query.message.edit_text(
                txt,
                reply_markup=buy_days_keyboard(method, lang),
            )
        except Exception as e:
            logger.warning(f"premium_method_selected edit_text failed: {e}")
            await callback_query.message.reply_text(
                txt,
                reply_markup=buy_days_keyboard(method, lang),
            )

    @app.on_callback_query(filters.regex(r"^premium:days:(crypto|upi):(\d+)$"))
    async def premium_days_selected(client: Client, callback_query):
        """Create a pending transaction and show payment instructions."""
        await callback_query.answer()
        data = callback_query.data or ""
        _, _, method, days_raw = data.split(":", 3)
        selected_days = int(days_raw)
        lang = await get_user_language(callback_query.from_user.id)

        priced_days = selected_days
        if Var.PRICE_PER_DAY_USD <= 0 and Var.PRICE_PER_DAY_INR <= 0:
            await callback_query.message.reply_text(
                t(lang, "pay_pricing_not_configured"),
                quote=True,
            )
            return

        amount_usd = None
        amount_inr = None
        if Var.PRICE_PER_DAY_USD > 0:
            amount_usd = _ceil_money(Var.PRICE_PER_DAY_USD * priced_days)
        if Var.PRICE_PER_DAY_INR > 0:
            amount_inr = _ceil_money(Var.PRICE_PER_DAY_INR * priced_days)

        txn_id = secrets.token_hex(4)  # 8 hex chars, safe for callback_data

        user = callback_query.from_user
        user_snapshot = {
            "user_id": user.id,
            "first_name": getattr(user, "first_name", "") or "",
            "last_name": getattr(user, "last_name", "") or "",
            "username": getattr(user, "username", "") or "",
            "language_code": getattr(user, "language_code", "") or "",
        }

        ok = await create_pending_txn(
            txn_id=txn_id,
            user_id=user.id,
            method=method,
            selected_days=selected_days,
            priced_days=priced_days,
            amount_usd=amount_usd,
            amount_inr=amount_inr,
            user_snapshot=user_snapshot,
        )
        if not ok:
            await callback_query.message.reply_text(
                t(lang, "pay_failed_start"),
                quote=True,
            )
            return

        # Display amounts
        if method == "crypto":
            if amount_usd is None:
                await callback_query.message.reply_text(
                    t(lang, "pay_crypto_config_err"),
                    quote=True,
                )
                return
            pay_line = t(lang, "pay_amount_usdt", amount=f"{amount_usd:.2f}")
            address_line = t(lang, "pay_usdt_address_block", address=Var.USDT_BEP20_ADDRESS)
        else:
            if amount_inr is None:
                await callback_query.message.reply_text(
                    t(lang, "pay_upi_config_err"),
                    quote=True,
                )
                return
            pay_line = t(lang, "pay_amount_inr", amount=f"{amount_inr:.2f}")
            address_line = t(lang, "pay_upi_block", upi_id=Var.UPI_ID)

        try:
            payment_msg = t(
                lang,
                "pay_invoice",
                method=_method_label(method, lang),
                days=priced_days,
                amount_line=pay_line,
                address_block=address_line,
            )
            paid_cancel = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            t(lang, "pay_btn_i_paid"),
                            callback_data=f"premium:paid:{txn_id}",
                        ),
                        InlineKeyboardButton(
                            t(lang, "pay_btn_cancel"),
                            callback_data=f"premium:cancel:{txn_id}",
                        ),
                    ]
                ]
            )
            await callback_query.message.edit_text(
                payment_msg,
                reply_markup=paid_cancel,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning(f"premium_days_selected edit_text failed: {e}")
            await callback_query.message.reply_text(
                payment_msg,
                reply_markup=paid_cancel,
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex(r"^premium:paid:([0-9a-fA-F]{8})$"))
    async def premium_paid_clicked(client: Client, callback_query):
        """User marked payment as done; now request screenshot."""
        await callback_query.answer()
        txn_id = (callback_query.data or "").split(":")[-1]
        lang = await get_user_language(callback_query.from_user.id)

        ok = await set_pending_txn_paid(txn_id)
        if not ok:
            await callback_query.message.reply_text(t(lang, "pay_step_inactive"))
            return

        cancel_only = InlineKeyboardMarkup(
            [[InlineKeyboardButton(t(lang, "pay_btn_cancel"), callback_data=f"premium:cancel:{txn_id}")]]
        )
        try:
            await callback_query.message.edit_text(
                t(lang, "pay_marked_paid_intro"),
                reply_markup=cancel_only,
                disable_web_page_preview=True,
            )
        except Exception:
            await callback_query.message.reply_text(
                t(lang, "pay_upload_screenshot_short"),
                reply_markup=cancel_only,
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex(r"^premium:cancel:([0-9a-fA-F]{8})$"))
    async def premium_cancel_clicked(client: Client, callback_query):
        await callback_query.answer()
        txn_id = (callback_query.data or "").split(":")[-1]
        lang = await get_user_language(callback_query.from_user.id)

        ok = await cancel_pending_txn(txn_id)
        if not ok:
            return
        await callback_query.message.reply_text(t(lang, "pay_cancelled"))

    @app.on_message(
        filters.private
        & (filters.photo | filters.document),
        group=1,
    )
    async def premium_screenshot_handler(client: Client, message: Message):
        """Receive screenshot after user clicks I PAID."""
        user_id = message.from_user.id
        lang = await get_user_language(user_id)
        pending = await get_latest_pending_txn_for_user(user_id)
        if not pending or pending.get("status") != "awaiting_screenshot":
            return

        txn_id = pending.get("_id")
        if not txn_id:
            return

        screenshot_file_id = None
        screenshot_file_unique_id = None
        screenshot_is_photo = None

        if message.photo:
            # Best-effort: take the largest photo variant
            screenshot_is_photo = True
            screenshot_file_id = message.photo.file_id
            screenshot_file_unique_id = getattr(message.photo, "file_unique_id", None)
        elif message.document:
            screenshot_is_photo = False
            screenshot_file_id = message.document.file_id
            screenshot_file_unique_id = getattr(message.document, "file_unique_id", None)

        if not screenshot_file_id:
            await message.reply_text(t(lang, "err_screenshot_file"))
            return

        ok = await set_pending_txn_screenshot(
            txn_id,
            screenshot_file_id=screenshot_file_id,
            screenshot_file_unique_id=screenshot_file_unique_id,
            screenshot_is_photo=screenshot_is_photo,
        )
        if not ok:
            await message.reply_text(t(lang, "err_screenshot_upload"))
            return

        pending2 = await get_pending_txn(txn_id)
        if not pending2:
            await message.reply_text(t(lang, "err_unexpected_retry"))
            return

        user_snapshot = pending2.get("user_snapshot", {}) or {}
        amount_line = ""
        if pending2.get("method") == "crypto" and pending2.get("amount_usd") is not None:
            amount_line = f"{pending2['amount_usd']:.2f} USDT"
        elif pending2.get("amount_inr") is not None:
            amount_line = f"INR {pending2['amount_inr']:.2f}"

        details_text = (
            t(lang, "pay_review_header")
            + t(lang, "pay_review_txn_id", tid=txn_id)
            + "\n"
            + t(lang, "pay_review_user_id", uid=user_snapshot.get("user_id", user_id))
            + "\n"
            + t(
                lang,
                "pay_review_username",
                username="@" + (user_snapshot.get("username", "") or "N/A"),
            )
            + "\n"
            + t(
                lang,
                "pay_review_name",
                name=(
                    f"{user_snapshot.get('first_name', '')} {user_snapshot.get('last_name', '')}".strip()
                    or "—"
                ),
            )
            + "\n"
            + t(
                lang,
                "pay_review_language",
                tg_lang=user_snapshot.get("language_code", "") or "N/A",
            )
            + "\n"
            + t(
                lang,
                "pay_review_method",
                method=_method_label(pending2.get("method") or "upi", lang),
            )
            + "\n"
            + t(lang, "pay_review_days", days=pending2.get("priced_days"))
            + "\n"
            + t(lang, "pay_review_amount", amount=amount_line)
            + "\n"
        )

        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(t(lang, "pay_btn_confirm"), callback_data=f"premium:submit:{txn_id}"),
                    InlineKeyboardButton(t(lang, "pay_btn_cancel"), callback_data=f"premium:cancel:{txn_id}"),
                ]
            ]
        )
        if screenshot_is_photo:
            await message.reply_photo(
                screenshot_file_id,
                caption=details_text,
                reply_markup=markup,
            )
        else:
            await message.reply_document(
                screenshot_file_id,
                caption=details_text,
                reply_markup=markup,
            )

    @app.on_callback_query(filters.regex(r"^premium:submit:([0-9a-fA-F]{8})$"))
    async def premium_submit_clicked(client: Client, callback_query):
        """User confirms; send to txn channel for admin approval."""
        await callback_query.answer()
        txn_id = (callback_query.data or "").split(":")[-1]
        u_lang = await get_user_language(callback_query.from_user.id)
        pending = await get_pending_txn(txn_id)
        if not pending:
            await callback_query.message.reply_text(t(u_lang, "pay_txn_not_found"))
            return
        status = pending.get("status")
        if status == "submitted_to_admin":
            await callback_query.message.reply_text(t(u_lang, "pay_already_submitted"))
            return
        if status != "awaiting_admin":
            await callback_query.message.reply_text(t(u_lang, "pay_txn_not_ready"))
            return

        # Mark as submitted to prevent duplicates
        await mark_pending_txn_submitted(txn_id)

        user_snapshot = pending.get("user_snapshot", {}) or {}
        method = pending.get("method")
        priced_days = pending.get("priced_days")
        amount_usd = pending.get("amount_usd")
        amount_inr = pending.get("amount_inr")

        if method == "crypto":
            amount_line = f"{amount_usd:.2f} USDT"
            address_line = f"USDT BEP20: {Var.USDT_BEP20_ADDRESS}"
        else:
            amount_line = f"INR {amount_inr:.2f}"
            address_line = f"UPI ID: {Var.UPI_ID}"

        caption = (
            "New premium payment submission (pending admin approval)\n\n"
            f"Transaction ID: {txn_id}\n"
            f"User ID: {user_snapshot.get('user_id')}\n"
            f"Username: @{user_snapshot.get('username') or 'N/A'}\n"
            f"Name: {user_snapshot.get('first_name', '')} {user_snapshot.get('last_name', '')}".strip() + "\n"
            f"Language: {user_snapshot.get('language_code', '') or 'N/A'}\n"
            f"Method: {_method_label(method, 'en')}\n"
            f"Days: {priced_days}\n"
            f"Amount: {amount_line}\n\n"
            f"{address_line}\n"
        )

        screenshot_file_id = pending.get("screenshot_file_id")
        screenshot_is_photo = pending.get("screenshot_is_photo")
        if not screenshot_file_id:
            await callback_query.message.reply_text(t(u_lang, "pay_screenshot_missing"))
            return

        try:
            if screenshot_is_photo:
                await client.send_photo(
                    chat_id=Var.TXN_CHNL_ID,
                    photo=screenshot_file_id,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "CONFIRM",
                                    callback_data=f"txn:confirm:{txn_id}",
                                ),
                                InlineKeyboardButton(
                                    "REJECT",
                                    callback_data=f"txn:reject:{txn_id}",
                                ),
                            ]
                        ]
                    ),
                )
            else:
                await client.send_document(
                    chat_id=Var.TXN_CHNL_ID,
                    document=screenshot_file_id,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "CONFIRM",
                                    callback_data=f"txn:confirm:{txn_id}",
                                ),
                                InlineKeyboardButton(
                                    "REJECT",
                                    callback_data=f"txn:reject:{txn_id}",
                                ),
                            ]
                        ]
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to send transaction {txn_id} to TXN_CHNL_ID={Var.TXN_CHNL_ID}: {e}", exc_info=True)
            await callback_query.message.reply_text(t(u_lang, "pay_fail_channel"))
            return

        await callback_query.message.reply_text(t(u_lang, "pay_submitted_wait"))

    @app.on_callback_query(filters.regex(r"^txn:(confirm|reject):([0-9a-fA-F]{8})$"))
    async def txn_admin_decision(client: Client, callback_query):
        """Owner/admin confirms/rejects a transaction from txn channel."""
        await callback_query.answer()
        if not callback_query.message or not callback_query.data:
            return

        # Only allow decision from the configured txn channel
        try:
            if callback_query.message.chat.id != Var.TXN_CHNL_ID:
                return
        except Exception:
            return

        actor_id = callback_query.from_user.id
        if not is_privileged_user(actor_id) and not await is_user_admin(actor_id):
            return

        parts = callback_query.data.split(":")
        action = parts[1]
        txn_id = parts[2]

        if action == "confirm":
            approved = await approve_pending_txn(txn_id, admin_id=actor_id)
            if not approved:
                await callback_query.message.reply_text("Approval failed (txn not found/ready).")
                return

            # Notify user
            user_id = int(approved["user_id"])
            expires_at = approved["expires_at"]
            notify_lang = await get_user_language(user_id)
            await client.send_message(
                chat_id=user_id,
                text=t(notify_lang, "premium_approved", expires=expires_at.isoformat()),
            )

            try:
                await callback_query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        else:
            ok = await reject_pending_txn(txn_id, admin_id=actor_id)
            if not ok:
                await callback_query.message.reply_text("Rejection failed (txn not found/ready).")
                return

            pending = await get_pending_txn(txn_id)
            user_id = pending.get("user_id") if pending else None
            if user_id:
                rej_lang = await get_user_language(int(user_id))
                await client.send_message(chat_id=int(user_id), text=t(rej_lang, "premium_rejected"))

            try:
                await callback_query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

    @app.on_message(filters.command("login") & filters.private)
    async def login_handler(client: Client, message: Message):
        """Handle the /login command to provide session generator web link."""
        user_id = message.from_user.id

        if not await user_has_premium_access(user_id):
            lang = await get_user_language(user_id)
            await message.reply_text(
                t(lang, "premium_required"),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
            return

        if not Var.ALLOW_USER_LOGIN:
            await message.reply_text(SESSION_GENERATOR_DISABLED_TEXT, quote=True)
            logger.info(f"Session generator disabled - login denied for user {user_id}")
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

        if not await user_has_premium_access(user_id):
            lang = await get_user_language(user_id)
            await message.reply_text(
                t(lang, "premium_required"),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
            return

        if not Var.ALLOW_USER_LOGIN:
            await message.reply_text(SESSION_GENERATOR_DISABLED_TEXT, quote=True)
            logger.info(f"Session generator disabled - logout denied for user {user_id}")
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

        if not await user_has_premium_access(user_id):
            lang = await get_user_language(user_id)
            await message.reply_text(
                t(lang, "premium_required"),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
            return

        if not Var.ALLOW_USER_LOGIN:
            await message.reply_text(SESSION_GENERATOR_DISABLED_TEXT, quote=True)
            logger.info(f"Session generator disabled - session info denied for user {user_id}")
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

        if not await user_has_premium_access(user_id):
            lang = await get_user_language(user_id)
            await message.reply_text(
                t(lang, "premium_required"),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
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
            await record_link_generated(
                encoded_id=encoded_msg_id,
                user_id=user_id,
                file_name=file_name,
                file_size=file_size,
                source="private_session",
                user_profile={
                    "username": getattr(message.from_user, "username", "") or "",
                    "first_name": getattr(message.from_user, "first_name", "") or "",
                    "last_name": getattr(message.from_user, "last_name", "") or "",
                    "language_code": getattr(message.from_user, "language_code", "") or "",
                    "is_premium": bool(getattr(message.from_user, "is_premium", False)),
                    "is_verified": bool(getattr(message.from_user, "is_verified", False)),
                },
            )

            # Process download link (shorten if file size exceeds threshold)
            processed_download_link = process_link(download_link, file_size, user_id=user_id)

            is_video = is_video_file(file_mime_type)
            reply_markup = None
            if is_video and Var.VIDEO_FRONTEND_URL:
                # For private content, the stream URL should also be shortened if needed
                stream_link = f"{Var.BASE_URL}/dl/{encoded_msg_id}"  # Same endpoint for streaming private content
                processed_stream_link = stream_link

                import urllib.parse
                encoded_stream_uri = urllib.parse.quote(processed_stream_link)
                video_play_url = f"{Var.VIDEO_FRONTEND_URL}?stream={encoded_stream_uri}"
                video_play_url = process_link(video_play_url, file_size, user_id=user_id)
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Play Video", url=video_play_url)]])

            await processing_msg.edit_text(
                f"✅ **Download Link Generated!**\n\n"
                f"**File Name:** `{file_name}`\n"
                f"**File Size:** {file_size_str}\n\n"
                f"**Link:** {processed_download_link}\n\n"
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
        Handle incoming media messages and generate download links.

        This handler forwards uploads to the log channel and returns a direct download URL.

        Args:
            client (Client): The Pyrogram client instance
            message (Message): The message containing the uploaded file
        """
        user_id = message.from_user.id

        # If the user is in the middle of a payment screenshot upload,
        # don't trigger normal download-link logic.
        pending = await get_latest_pending_txn_for_user(user_id)
        if pending and pending.get("status") == "awaiting_screenshot":
            return

        if not await user_has_premium_access(user_id):
            lang = await get_user_language(user_id)
            await message.reply_text(
                t(lang, "premium_required"),
                quote=True,
                reply_markup=premium_access_keyboard(lang),
                disable_web_page_preview=True,
            )
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
            await record_link_generated(
                encoded_id=encoded_msg_id,
                user_id=user_id,
                file_name=file_name,
                file_size=file_size,
                source="uploaded_media",
                user_profile={
                    "username": getattr(message.from_user, "username", "") or "",
                    "first_name": getattr(message.from_user, "first_name", "") or "",
                    "last_name": getattr(message.from_user, "last_name", "") or "",
                    "language_code": getattr(message.from_user, "language_code", "") or "",
                    "is_premium": bool(getattr(message.from_user, "is_premium", False)),
                    "is_verified": bool(getattr(message.from_user, "is_verified", False)),
                },
            )

            # Process download link (shorten if file size exceeds threshold)
            processed_download_link = process_link(download_link, file_size, user_id=user_id)

            # Check if it's a video file and create appropriate response
            is_video = is_video_file(file_mime_type)
            reply_markup = None

            if is_video and Var.VIDEO_FRONTEND_URL:
                # Create inline keyboard with Play Video button - use stream URL directly
                stream_link = f"{Var.BASE_URL}/stream/{encoded_msg_id}"

                import urllib.parse
                encoded_stream_uri = urllib.parse.quote(stream_link)
                video_play_url = f"{Var.VIDEO_FRONTEND_URL}?stream={encoded_stream_uri}"
                video_play_url = process_link(video_play_url, file_size, user_id=user_id)

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

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(
            [
                "start",
                "help",
                "about",
                "add",
                "ban",
                "dashboard",
                "logs",
                "stats",
                "broadcast",
                "login",
                "logout",
                "session",
            ]
        )
        & ~filters.regex(r"https?://t\.me/.*")
    )
    async def premium_gate_text_fallback(client: Client, message: Message):
        """Ask non-premium users to contact the owner."""
        user_id = message.from_user.id
        if await user_has_premium_access(user_id):
            return

        lang = await get_user_language(user_id)
        await message.reply_text(
            t(lang, "premium_required"),
            quote=True,
            reply_markup=premium_access_keyboard(lang),
            disable_web_page_preview=True,
        )

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