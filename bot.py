# StreamBot/bot.py
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserNotParticipant

from config import Var
from utils import get_file_attr, humanbytes

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

    # Use the START_TEXT directly from Var which now includes dynamic duration
    await message.reply_text(
        Var.START_TEXT.format(
            mention=message.from_user.mention,
            force_sub_info=force_sub_info # Add the info text here
        ),
        quote=True,
        disable_web_page_preview=True
    )

@TgDlBot.on_message(filters.private & filters.incoming & (
    filters.document | filters.video | filters.audio | filters.photo |
    filters.animation | filters.sticker | filters.voice
))
async def file_handler(client: Client, message: Message):
    """Handles incoming media messages to generate download links."""

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

        if file_name is None or file_size is None:
             logger.error(f"Extracted null file_name or file_size for message {message.id}.")
             await processing_msg.edit_text(Var.ERROR_TEXT)
             return

        # Generate the download link using the log message ID
        download_link = f"{Var.BASE_URL.rstrip('/')}/dl/{log_msg.id}"

        # Use the LINK_GENERATED_TEXT directly from Var which now includes dynamic duration
        await processing_msg.edit_text(
            Var.LINK_GENERATED_TEXT.format(
                file_name=file_name,
                file_size=humanbytes(file_size),
                download_link=download_link
            ),
            disable_web_page_preview=True # Optional: prevent link preview
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