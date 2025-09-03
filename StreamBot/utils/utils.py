import mimetypes
from pyrogram.types import Message, Audio, Document, Photo, Video, Animation, Sticker, Voice
from pyrogram import Client
from pyrogram.errors import FloodWait, FileIdInvalid, RPCError
import base64
import binascii 
import asyncio
import datetime
from ..config import Var 
import logging

logger = logging.getLogger(__name__)

# Shared video MIME types for consistency across the application
VIDEO_MIME_TYPES = {
    'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime',
    'video/x-msvideo', 'video/x-matroska', 'video/avi', 'video/mkv'
}

def humanbytes(size: int) -> str:
    """Convert bytes to human-readable format."""
    if not size:
        return "0 B"
    power = 1024
    t_n = 0
    power_dict = {0: " ", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size /= power
        t_n += 1
    return "{:.2f} {}B".format(size, power_dict[t_n])

def is_video_file(mime_type: str) -> bool:
    """Check if the file is a video based on MIME type."""
    if not mime_type:
        return False
    
    return mime_type.lower() in VIDEO_MIME_TYPES

async def get_media_message(bot_client: Client, message_id: int) -> Message:
    """Fetch the media message object from the LOG_CHANNEL and check expiry."""
    from aiohttp import web  # Import here to avoid circular imports
    
    if not bot_client or not bot_client.is_connected:
        logger.error("Bot client is not available or connected for get_media_message.")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable.")

    max_retries = 3
    current_retry = 0
    media_msg = None
    while current_retry < max_retries:
        try:
            media_msg = await bot_client.get_messages(chat_id=Var.LOG_CHANNEL, message_ids=message_id)
            break
        except FloodWait as e:
            if current_retry == max_retries - 1:
                logger.error(f"Max retries reached for FloodWait getting message {message_id}. Aborting.")
                raise web.HTTPTooManyRequests(text="Service temporarily rate limited. Please try again later.")
            sleep_duration = e.value + 2
            logger.warning(f"FloodWait getting message {message_id} from {Var.LOG_CHANNEL}. Retrying in {sleep_duration}s (Attempt {current_retry+1}/{max_retries}).")
            await asyncio.sleep(sleep_duration)
            current_retry += 1
        except FileIdInvalid:
            logger.error(f"FileIdInvalid for message {message_id} in log channel {Var.LOG_CHANNEL}. File might be deleted.")
            raise web.HTTPNotFound(text="File not found or has been deleted.")
        except (ConnectionError, RPCError, TimeoutError) as e:
            if current_retry == max_retries - 1:
                logger.error(f"Max retries reached for network/RPC error getting message {message_id}: {e}. Aborting.")
                raise web.HTTPServiceUnavailable(text="Service temporarily unavailable. Please try again later.")
            sleep_duration = 5 * (current_retry + 1)
            logger.warning(f"Network/RPC error getting message {message_id}: {e}. Retrying in {sleep_duration}s (Attempt {current_retry+1}/{max_retries}).")
            await asyncio.sleep(sleep_duration)
            current_retry += 1
        except Exception as e:
            logger.error(f"Unexpected error getting message {message_id} from {Var.LOG_CHANNEL}: {e}", exc_info=True)
            raise web.HTTPInternalServerError(text="Internal server error occurred.")

    if not media_msg:
        logger.error(f"Failed to retrieve message {message_id} after retries, but no exception was raised (should not happen).")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable.")

    # --- Link Expiry Check ---
    if hasattr(media_msg, 'date') and isinstance(media_msg.date, datetime.datetime):
        message_timestamp = media_msg.date.replace(tzinfo=datetime.timezone.utc)
        current_timestamp = datetime.datetime.now(datetime.timezone.utc)
        time_difference = current_timestamp - message_timestamp
        expiry_seconds = Var.LINK_EXPIRY_SECONDS
        
        # Check if expiry is enabled
        if expiry_seconds > 0 and time_difference.total_seconds() > expiry_seconds:
            logger.warning(f"Download link for message {message_id} expired. Age: {time_difference} > {expiry_seconds}s")
            raise web.HTTPGone(text="Download link has expired.")
    else:
        logger.warning(f"Could not determine message timestamp for message {message_id}. Skipping expiry check.")

    return media_msg

def get_file_attr(message: Message):
    """Extract essential file attributes from a Pyrogram Message object."""
    if not message or not isinstance(message, Message):
        logger.warning("Invalid message object provided to get_file_attr")
        return None, "unknown_file", 0, "application/octet-stream", None
        
    media = (
        message.audio or message.document or message.photo or message.video or
        message.animation or message.sticker or message.voice
    )

    if not media:
        logger.warning(f"No media found in message ID {message.id} from chat {message.chat.id if message.chat else 'Unknown'}.")
        return None, "unknown_file", 0, "application/octet-stream", None

    file_id = getattr(media, 'file_id', None)
    file_unique_id = getattr(media, 'file_unique_id', None)
    file_name = getattr(media, 'file_name', None)
    file_size = getattr(media, 'file_size', None) 
    mime_type = getattr(media, 'mime_type', None)

    if file_name is None:
        logger.warning(f"Media object for message {message.id} (type: {type(media).__name__}) missing 'file_name'. File ID: {file_id}")
    if file_size is None:
        logger.warning(f"Media object for message {message.id} (type: {type(media).__name__}) missing 'file_size'. File ID: {file_id}. Defaulting to 0.")
        file_size = 0

    # Generate fallback file name
    if not file_name:
        # Use original logic that was working before - file IDs contain useful info
        base_name = file_unique_id or file_id or f"media_{message.id}"

        guessed_extension = mimetypes.guess_extension(mime_type) if mime_type else None
        if guessed_extension:
            file_name = f"{base_name}{guessed_extension}"
        else:
            # Media type-specific fallbacks with proper extensions
            if isinstance(media, Photo):
                file_name = f"{base_name}.jpg"
            elif isinstance(media, Video):
                file_name = f"{base_name}.mp4"
            elif isinstance(media, Audio):
                file_name = f"{base_name}.mp3"
            elif isinstance(media, Voice):
                file_name = f"{base_name}.ogg"
            elif isinstance(media, Animation):
                file_name = f"{base_name}.mp4"
            elif isinstance(media, Sticker):
                file_name = f"{base_name}.webp"
            elif isinstance(media, Document):
                file_name = base_name  # Documents might have their own extensions
            else:
                file_name = base_name

    # Generate fallback MIME type
    if not mime_type:
        if file_name:
            mime_type = mimetypes.guess_type(file_name)[0]
        if not mime_type:
            logger.warning(f"Could not determine mime_type for message {message.id}, file_name: {file_name}. Defaulting to octet-stream.")
            mime_type = "application/octet-stream"

    # Ensure proper file extensions for specific media types
    current_extension = "." + file_name.split(".")[-1].lower() if "." in file_name else None

    if isinstance(media, Photo) and (not current_extension or current_extension not in ['.jpg', '.jpeg', '.png']):
        file_name = f"{file_name.split('.')[0]}.jpg"
        if mime_type not in ["image/jpeg", "image/png"]: mime_type = "image/jpeg"
    elif isinstance(media, Sticker) and (not current_extension or current_extension != '.webp'):
        file_name = f"{file_name.split('.')[0]}.webp"
        if mime_type != "image/webp": mime_type = "image/webp"
    elif isinstance(media, Voice) and (not current_extension or current_extension not in ['.ogg', '.oga']):
        file_name = f"{file_name.split('.')[0]}.ogg"
        if mime_type not in ["audio/ogg", "audio/oga"]: mime_type = "audio/ogg"
    elif isinstance(media, Video) and (not current_extension or current_extension not in ['.mp4', '.mkv', '.mov', '.webm', '.avi', '.ogg']):
        file_name = f"{file_name.split('.')[0]}.mp4"
        # Preserve more video MIME types instead of forcing to video/mp4
        valid_video_mimes = ["video/mp4", "video/quicktime", "video/x-matroska", "video/webm", 
                           "video/x-msvideo", "video/avi", "video/ogg"]
        if mime_type not in valid_video_mimes: 
            mime_type = "video/mp4"

    if not isinstance(file_size, int):
        logger.warning(f"File size for message {message.id} was not an int ('{file_size}'). Defaulting to 0.")
        file_size = 0

    return file_id, file_name, file_size, mime_type, file_unique_id

def get_id_encoder_key():
    """Get the key used for encoding/decoding message IDs."""
    key = abs(Var.LOG_CHANNEL)
    if key == 0:
        logger.critical("LOG_CHANNEL is 0, which is invalid for ID encoding. Please set a valid LOG_CHANNEL.")
        return 961748927  # Fallback prime number
    return key

def encode_message_id(message_id: int) -> str:
    """Encode a message ID for use in URLs."""
    try:
        # Input validation
        if not isinstance(message_id, int) or message_id <= 0:
            logger.warning(f"Invalid message_id for encoding: {message_id}")
            return str(message_id)
            
        key = get_id_encoder_key()
        transformed_id = message_id * key
        encoded_bytes = base64.urlsafe_b64encode(str(transformed_id).encode('utf-8'))
        return encoded_bytes.decode('utf-8').rstrip("=")
    except Exception as e:
        logger.error(f"Error encoding message ID {message_id}: {e}", exc_info=True)
        return str(message_id)

def decode_message_id(encoded_id_str: str) -> int | None:
    """Decode an encoded ID string back to a message ID."""
    try:
        # Input validation
        if not encoded_id_str or not isinstance(encoded_id_str, str):
            logger.warning("Empty or invalid encoded_id_str provided")
            return None
            
        # Length validation to prevent DoS
        if len(encoded_id_str) > 200:  # Reasonable limit
            logger.warning(f"Encoded ID too long: {len(encoded_id_str)} chars")
            return None
        
        # Basic character validation for base64url
        import string
        valid_chars = string.ascii_letters + string.digits + '-_'
        if not all(c in valid_chars for c in encoded_id_str):
            logger.warning(f"Invalid characters in encoded ID: {encoded_id_str[:50]}...")
            return None
        
        key = get_id_encoder_key()
        padding = "=" * (-len(encoded_id_str) % 4)
        decoded_bytes = base64.urlsafe_b64decode((encoded_id_str + padding).encode('utf-8'))
        transformed_id_str = decoded_bytes.decode('utf-8')

        transformed_id = int(transformed_id_str)

        if transformed_id % key != 0:
            logger.warning(f"Invalid encoded ID (key mismatch): {encoded_id_str[:50]}...")
            return None

        original_message_id = transformed_id // key

        # Verify the decoded ID is reasonable
        if original_message_id <= 0 or original_message_id > 2**63:  # Reasonable bounds
            logger.warning(f"Decoded message ID out of reasonable bounds: {original_message_id}")
            return None

        # Verify the encoded ID
        if (original_message_id * key) != transformed_id:
            logger.warning(f"Encoded ID verification failed for {encoded_id_str[:50]}...")
            return None

        return original_message_id
    except (binascii.Error, ValueError, UnicodeDecodeError) as e:
        logger.warning(f"Error decoding ID '{encoded_id_str[:50]}...': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding ID '{encoded_id_str[:50]}...': {e}", exc_info=True)
        return None
