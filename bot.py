# StreamBot/bot.py
import logging
import asyncio
import os
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserNotParticipant, FloodWait, UserIsBlocked, InputUserDeactivated
from database import add_user, del_user, full_userbase
from config import Var
from utils import get_file_attr, humanbytes, encode_message_id
from rate_limiter import check_and_record_link_generation, get_user_link_count_and_wait_time
logger = logging.getLogger(__name__)

TgDlBot = Client(
    name=Var.SESSION_NAME,
    api_id=Var.API_ID,
    api_hash=Var.API_HASH,
    bot_token=Var.BOT_TOKEN,
    workers=Var.WORKERS,
)

# --- Helper: Check Force Subscription 
async def check_force_sub(client: Client, message: Message) -> bool:
    """Checks if the user is subscribed to the FORCE_SUB_CHANNEL. Returns True if subscribed or check is disabled."""
    if not Var.FORCE_SUB_CHANNEL:
        return True # Force sub is disabled

    try:
        # Check membership
        member = await client.get_chat_member(Var.FORCE_SUB_CHANNEL, message.from_user.id)
        # Allow members, administrators, owners
        if member.status not in ["kicked", "left"]:
            return True
        else:
            # User was kicked or left, treat as not participant
            # logger.info(f"User {message.from_user.id} is kicked/left from {Var.FORCE_SUB_CHANNEL}")
            # Fall through to the UserNotParticipant handling below
            raise UserNotParticipant # Simulate the error to use the same handling logic

    except UserNotParticipant:
        # logger.info(f"User {message.from_user.id} is not a participant in {Var.FORCE_SUB_CHANNEL}")
        try:
            # Get chat info to display name/link
            chat = await client.get_chat(Var.FORCE_SUB_CHANNEL)
            invite_link = chat.invite_link
            # If no invite link (e.g., private channel), try creating one
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
            # Fallback message if link generation fails
            await message.reply_text(
                f"{Var.FORCE_SUB_JOIN_TEXT}\n\n(Could not retrieve channel link automatically. Please ensure you have joined the required channel.)",
                quote=True
            )
        return False # User is not subscribed

    except FloodWait as e:
        logger.warning(f"FloodWait checking membership for {message.from_user.id} in {Var.FORCE_SUB_CHANNEL}: {e.value}s")
        await message.reply_text(Var.FLOOD_WAIT_TEXT.format(seconds=e.value), quote=True)
        return False # Treat as failure during flood wait

    except Exception as e:
        logger.error(f"Error checking membership for {message.from_user.id} in {Var.FORCE_SUB_CHANNEL}: {e}", exc_info=True)
        await message.reply_text("An error occurred while checking channel membership.", quote=True)
        return False # Treat as failure on other errors


# --- Bot Handlers ---

@TgDlBot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Handles the /start command."""
    force_sub_info = ""
    if Var.FORCE_SUB_CHANNEL:
        # Try to get channel details for the start message
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
         # logger.info(f"Checked/Added user {user_id} on /start command.")
    except Exception as e:
         logger.error(f"Database error adding user {user_id} on start: {e}")
    
    # Use the START_TEXT directly from Var which now includes dynamic duration
    await message.reply_text(
        Var.START_TEXT.format(
            mention=message.from_user.mention,
            force_sub_info=force_sub_info # Add the info text here
        ),
        quote=True,
        disable_web_page_preview=True
    )

@TgDlBot.on_message(filters.command("logs") & filters.private)
async def logs_handler(client: Client, message: Message):
    """Handles the /logs command for admins to view logs."""
    user_id = message.from_user.id
    
    # Check if user is an admin
    if not Var.ADMINS or user_id not in Var.ADMINS:
        await message.reply_text("❌ You don't have permission to access logs.", quote=True)
        logger.warning(f"Unauthorized logs access attempt by user {user_id}")
        return
    
    # Parse command arguments
    command_parts = message.text.split()
    
    # Default parameters
    limit = 50  # Default number of lines
    level = "ALL"  # Default level
    filter_text = ""  # Default filter
    
    # Parse command arguments if any
    for i, part in enumerate(command_parts[1:], 1):
        if part.startswith("limit="):
            try:
                limit = min(int(part.split("=")[1]), 200)  # Cap at 200 lines
            except:
                pass
        elif part.startswith("level="):
            level = part.split("=")[1].upper()
        elif part.startswith("filter="):
            filter_text = part.split("=")[1]
    
    # Check if log file exists
    log_file_path = "tgdlbot.log"
    if not os.path.exists(log_file_path):
        await message.reply_text("❌ Log file not found.", quote=True)
        return
    
    # Get file size and basic info
    file_stats = os.stat(log_file_path)
    file_size = file_stats.st_size
    last_modified = datetime.datetime.fromtimestamp(file_stats.st_mtime).isoformat()
    
    # Define log level mapping for filtering
    level_priority = {
        'DEBUG': 0,
        'INFO': 1,
        'WARNING': 2,
        'ERROR': 3,
        'CRITICAL': 4
    }
    
    # Determine priority level for filtering
    min_level_priority = level_priority.get(level, -1) if level != 'ALL' else -1
    
    # Read log file
    try:
        # Inform user that logs are being processed
        processing_msg = await message.reply_text("⏳ Processing logs...", quote=True)
        
        matching_lines = []
        total_matching_lines = 0
        
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as file:
            # Read file from the end to get the most recent logs first
            lines = file.readlines()
            
            # Process lines in reverse (newest first)
            for line in reversed(lines):
                # Check if line contains log level indicator
                current_line_level = None
                for lvl in level_priority.keys():
                    if f" - {lvl} - " in line:
                        current_line_level = lvl
                        break
                
                # Apply level filter
                if min_level_priority >= 0 and (current_line_level is None or 
                                              level_priority.get(current_line_level, -1) < min_level_priority):
                    continue
                
                # Apply text filter if specified
                if filter_text and filter_text.lower() not in line.lower():
                    continue
                
                # Count matching lines
                total_matching_lines += 1
                
                # Only add up to the limit
                if total_matching_lines <= limit:
                    matching_lines.append(line.strip())
        
        # Prepare log content
        if matching_lines:
            # Reverse back to chronological order
            matching_lines.reverse()
            
            # Format logs for message
            logs_text = f"📋 **Log File ({humanbytes(file_size)})** | Last Modified: {last_modified}\n"
            logs_text += f"🔍 Filter: Level={level}" + (f", Text='{filter_text}'" if filter_text else "") + "\n"
            logs_text += f"📊 Showing {len(matching_lines)}/{total_matching_lines} matching lines\n\n"
            
            # Split logs into chunks of ~4000 chars for Telegram message limit
            chunk_size = 3800  # Leave room for headers
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
            
            # Send first part with the header
            await processing_msg.edit_text(logs_text + f"```\n{log_chunks[0]}```")
            
            # Send additional parts if any
            for i, chunk in enumerate(log_chunks[1:], 1):
                await message.reply_text(f"```\n{chunk}```", quote=True)
                # Small delay to avoid flood limits
                await asyncio.sleep(0.5)
            
            logger.info(f"Logs viewed by admin {user_id} (Level: {level}, Filter: {filter_text})")
        else:
            await processing_msg.edit_text(f"❗ No log entries match your criteria (Level: {level}, Filter: {filter_text})")
    
    except Exception as e:
        logger.error(f"Error reading logs for admin {user_id}: {e}", exc_info=True)
        await message.reply_text(f"❌ Error reading logs: {str(e)}", quote=True)

@TgDlBot.on_message(filters.private & filters.incoming & (
    filters.document | filters.video | filters.audio | filters.photo |
    filters.animation | filters.sticker | filters.voice
))
async def file_handler(client: Client, message: Message):
    """Handles incoming media messages to generate download links."""
    user_id = message.from_user.id

    # --- Rate Limiting Check ---
    if Var.MAX_LINKS_PER_DAY > 0 and user_id not in Var.ADMINS: # Only apply if limit is positive
        can_generate = await check_and_record_link_generation(user_id)
        if not can_generate:
            # Get current count and wait time to provide more info to user
            _, wait_time_seconds = await get_user_link_count_and_wait_time(user_id)
            wait_hours = wait_time_seconds / 3600
            wait_minutes = (wait_time_seconds % 3600) / 60

            if wait_time_seconds > 0:
                reply_text = Var.RATE_LIMIT_EXCEEDED_TEXT.format(
                    max_links=Var.MAX_LINKS_PER_DAY,
                    wait_hours=wait_hours,
                    wait_minutes=wait_minutes
                )
            else: # Should not happen if can_generate is False and wait_time is 0, but as a fallback
                reply_text = Var.RATE_LIMIT_EXCEEDED_TEXT_NO_WAIT.format(max_links=Var.MAX_LINKS_PER_DAY)

            await message.reply_text(reply_text, quote=True)
            return # Stop processing

    # --- Force Subscription Check ---
    if not await check_force_sub(client, message):
        return # Stop processing if user is not subscribed

    if not Var.LOG_CHANNEL:
        logger.error("LOG_CHANNEL is not configured. Cannot process files.")
        await message.reply_text("Bot configuration error: Log channel not set.", quote=True)
        return

    # Send a "processing" message
    processing_msg = await message.reply_text(Var.GENERATING_LINK_TEXT, quote=True)

    try:
        # Forward the message to the log channel
        log_msg = await message.forward(chat_id=Var.LOG_CHANNEL)

        # Check if forwarding was successful
        if not log_msg or not log_msg.id:
            await processing_msg.edit_text(Var.ERROR_TEXT)
            logger.error(f"Failed to forward message {message.id} from user {message.from_user.id} to log channel {Var.LOG_CHANNEL}.")
            return

        # --- Get only necessary file attributes ---
        # Indices: 1=file_name, 2=file_size
        attrs = get_file_attr(message)
        if attrs is None:
            # This case should be unlikely given the message filters, but handle defensively
            logger.error(f"Could not get file attributes for message {message.id} from user {message.from_user.id}.")
            await processing_msg.edit_text(Var.ERROR_TEXT)
            return

        file_name = attrs[1] # Index 1 is file_name
        file_size = attrs[2] # Index 2 is file_size

        # Generate the download link using the encoded log message ID
        encoded_log_id = encode_message_id(log_msg.id)
        download_link = f"{Var.BASE_URL.rstrip('/')}/dl/{encoded_log_id}"

        await processing_msg.edit_text(
            Var.LINK_GENERATED_TEXT.format(
                file_name=file_name,
                file_size=humanbytes(file_size),
                download_link=download_link # This now uses the encoded ID
            ),
            disable_web_page_preview=True
        )
        # logger.info(f"Generated download link for message {log_msg.id} (original: {message.id}) for user {message.from_user.id}")

    except FloodWait as e:
        logger.warning(f"FloodWait encountered for user {message.from_user.id}: Sleeping for {e.value}s")
        # Use the FLOOD_WAIT_TEXT from Var
        await processing_msg.edit_text(Var.FLOOD_WAIT_TEXT.format(seconds=e.value))
        await asyncio.sleep(e.value + 2) # Add buffer
        try:
             await processing_msg.edit_text("Please try sending the file again now.") # Ask user to retry
        except Exception as edit_e:
             logger.warning(f"Could not edit flood wait message after wait: {edit_e}")


    except Exception as e:
        logger.error(f"Error processing file for user {message.from_user.id}: {e}", exc_info=True)
        try:
            # Use the ERROR_TEXT from Var
            await processing_msg.edit_text(Var.ERROR_TEXT)
        except Exception as edit_err:
            logger.error(f"Error editing processing message to show final error: {edit_err}")

@TgDlBot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_handler(client: Client, message: Message):
    """Handles the /broadcast command for admins."""

    # --- Admin Check ---
    if not Var.ADMINS or message.from_user.id not in Var.ADMINS:
        await message.reply_text(Var.BROADCAST_ADMIN_ONLY, quote=True)
        return

    # --- Check if it's a reply ---
    if not message.reply_to_message:
        await message.reply_text(Var.BROADCAST_REPLY_PROMPT, quote=True)
        return

    broadcast_msg = message.reply_to_message
    status_msg = await message.reply_text(Var.BROADCAST_STARTING, quote=True)

    # --- Get Users ---
    try:
        all_users = await full_userbase()
        total_users = len(all_users)
        logger.info(f"Starting broadcast to {total_users} users.")
    except Exception as e:
        logger.error(f"Database error fetching users for broadcast: {e}")
        await status_msg.edit_text(f"❌ Error fetching users from database: {e}")
        return

    if total_users == 0:
         await status_msg.edit_text("No users found in the database to broadcast to.")
         return

    # --- Broadcast Loop ---
    successful = 0
    blocked_deleted = 0
    unsuccessful = 0
    start_time = asyncio.get_event_loop().time()

    for i, user_id in enumerate(all_users):
        try:
            await broadcast_msg.copy(chat_id=user_id)
            successful += 1
        except FloodWait as e:
            wait_time = e.value + 2 # Add buffer
            logger.warning(f"FloodWait during broadcast to {user_id}. Sleeping for {wait_time}s.")
            await asyncio.sleep(wait_time)
            # Retry after wait
            try:
                await broadcast_msg.copy(chat_id=user_id)
                successful += 1
            except Exception as retry_e: # Catch potential errors on retry
                 logger.error(f"Broadcast failed to {user_id} after FloodWait retry: {retry_e}")
                 unsuccessful += 1
        except (UserIsBlocked, InputUserDeactivated) as e:
            logger.info(f"User {user_id} is blocked or deactivated. Removing.")
            await del_user(user_id) # Remove from DB
            blocked_deleted += 1
        except Exception as e:
            logger.error(f"Broadcast failed to {user_id}: {type(e).__name__} - {e}")
            unsuccessful += 1

        # --- Optional: Update status periodically ---
        # Avoid editing too frequently to prevent flood waits on the status message itself
        if (i + 1) % 50 == 0 or (i + 1) == total_users: # Update every 50 users or at the end
            try:
                await status_msg.edit_text(
                    Var.BROADCAST_STATUS_UPDATE.format(
                        total=total_users,
                        successful=successful,
                        blocked_deleted=blocked_deleted,
                        unsuccessful=unsuccessful
                    )
                )
            except FloodWait as fe:
                 logger.warning(f"FloodWait editing broadcast status message: {fe.value}s")
                 await asyncio.sleep(fe.value) # Wait if editing status gets limited
            except Exception as edit_e:
                 logger.error(f"Could not edit broadcast status message: {edit_e}")


    end_time = asyncio.get_event_loop().time()
    duration = round(end_time - start_time)
    logger.info(f"Broadcast finished in {duration} seconds.")

    # --- Final Status ---
    try:
         await status_msg.edit_text(
             Var.BROADCAST_COMPLETED.format(
                 total=total_users,
                 successful=successful,
                 blocked_deleted=blocked_deleted,
                 unsuccessful=unsuccessful
             )
         )
    except Exception as final_edit_e:
         logger.error(f"Failed to edit final broadcast status: {final_edit_e}")
         # Send as a new message if editing fails
         await message.reply_text(
             Var.BROADCAST_COMPLETED.format(
                 total=total_users,
                 successful=successful,
                 blocked_deleted=blocked_deleted,
                 unsuccessful=unsuccessful
             ), quote=True)