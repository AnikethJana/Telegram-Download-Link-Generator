# StreamBot/bot.py
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

logger = logging.getLogger(__name__)
# TgDlBot instance will be created and managed by ClientManager in __main__.py
# Handlers will be attached to it there.

# Create a memory-safe rate-limited logger instance
rate_limited_logger = SmartRateLimitedLogger(logger)

# --- Helper: Check Force Subscription 
async def check_force_sub(client: Client, message: Message) -> bool:
    """Check if user is subscribed to force subscription channel."""
    if not Var.FORCE_SUB_CHANNEL:
        return True

    try:
        member = await client.get_chat_member(Var.FORCE_SUB_CHANNEL, message.from_user.id)
        if member.status not in ["kicked", "left"]:
            return True
        else:
            raise UserNotParticipant

    except UserNotParticipant:
        try:
            chat = await client.get_chat(Var.FORCE_SUB_CHANNEL)
            invite_link = chat.invite_link
            if not invite_link:
                 invite_link_obj = await client.create_chat_invite_link(Var.FORCE_SUB_CHANNEL)
                 invite_link = invite_link_obj.invite_link

            button_text = f"Join {chat.title}" if chat.title else "Join Channel"
            button = [[InlineKeyboardButton(button_text, url=invite_link)]]
            await message.reply_text(
                Var.FORCE_SUB_JOIN_TEXT,
                reply_markup=InlineKeyboardMarkup(button),
                quote=True
            )
        except FloodWait as e:
            logger.warning(f"FloodWait creating invite link or getting chat for {Var.FORCE_SUB_CHANNEL}: {e.value}s")
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


# --- Bot Handlers ---
def attach_handlers(app: Client):
    """Register all bot handlers to the provided client instance."""
    logger.info("Attaching bot command and message handlers...")

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message):
        """Handle the /start command."""
        force_sub_info = ""
        if Var.FORCE_SUB_CHANNEL:
            try:
                fsub_chat = await client.get_chat(Var.FORCE_SUB_CHANNEL)
                invite_link = fsub_chat.invite_link
                if not invite_link:
                    invite_link_obj = await client.create_chat_invite_link(Var.FORCE_SUB_CHANNEL)
                    invite_link = invite_link_obj.invite_link
                force_sub_info = Var.FORCE_SUB_INFO_TEXT + f"➡️ [{fsub_chat.title}]({invite_link})\n\n"
            except Exception as e:
                logger.warning(f"Could not get ForceSub channel info for start message: {e}")
                force_sub_info = "❗**Please ensure you join the required channel to use the bot.**\n\n"
        
        user_id = message.from_user.id
        try:
             await add_user(user_id)
        except Exception as e:
             logger.error(f"Database error adding user {user_id} on start: {e}")
        
        await message.reply_text(
            Var.START_TEXT.format(
                mention=message.from_user.mention,
                force_sub_info=force_sub_info
            ),
            quote=True,
            disable_web_page_preview=True
        )

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
            
            if has_active_session:
                response_text = f"""✅ **You already have an active session!**

Your session is currently active and ready to use for generating download links.

🌐 **Session Generator**: [Click here]({session_generator_url})

ℹ️ **How to use:**
1. Visit the session generator web page
2. Your existing session will be automatically loaded
3. Share any Telegram file URL to get instant download links

💡 **Tip**: Your session remains active until you use `/logout`"""

            else:
                response_text = f"""🔐 **Login to Session Generator**

To generate download links for private files, you need to create a session through our secure web interface.

🌐 **Session Generator**: [Click here]({session_generator_url})

📝 **Steps:**
1. Click the link above to open the session generator
2. Login with Telegram using the widget on the page
3. Your session will be automatically generated and saved
4. Start sharing file URLs to get download links!

🔒 **Security**: Your session is encrypted and securely stored. Only you can access your files."""

            await message.reply_text(
                response_text,
                quote=True,
                disable_web_page_preview=True
            )
            
            logger.info(f"Login command used by user {user_id}")
            
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
            
            # Check if user has an active session efficiently
            has_active_session = await check_user_has_session(user_id)
            
            if not has_active_session:
                await message.reply_text(
                    "ℹ️ **No Active Session**\n\nYou don't have an active session to logout from.\n\nUse `/login` to create a new session.",
                    quote=True
                )
                return
            
            # Revoke the user's session
            success = await revoke_user_session(user_id)
            
            if success:
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

    @app.on_message(filters.private & filters.incoming & (
        filters.document | filters.video | filters.audio | filters.photo |
        filters.animation | filters.sticker | filters.voice
    ))
    async def file_handler(client: Client, message: Message):
        """Handle incoming media messages to generate download links."""
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

            # Check if it's a video file and create appropriate response
            is_video = is_video_file(file_mime_type)
            reply_markup = None
            
            if is_video and Var.VIDEO_FRONTEND_URL:
                # Create inline keyboard with Play Video button - use stream URL directly
                stream_link = f"{Var.BASE_URL}/stream/{encoded_msg_id}"
                import urllib.parse
                encoded_stream_uri = urllib.parse.quote(stream_link)
                video_play_url = f"{Var.VIDEO_FRONTEND_URL}?stream={encoded_stream_uri}"
                
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎬 Play Video", url=video_play_url)]
                ])

            # Send success response
            await processing_msg.edit_text(
                Var.LINK_GENERATED_TEXT.format(
                    file_name=file_name,
                    file_size=file_size_str,
                    download_link=download_link
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