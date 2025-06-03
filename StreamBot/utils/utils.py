import mimetypes
from pyrogram.types import Message, Audio, Document, Photo, Video, Animation, Sticker, Voice
import base64
import binascii 
from ..config import Var 
import logging

logger = logging.getLogger(__name__)

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
        base_name = file_unique_id or file_id or f"media_{message.id}"
        guessed_extension = mimetypes.guess_extension(mime_type) if mime_type else None
        if guessed_extension:
            file_name = f"{base_name}{guessed_extension}"
        else:
            # Media type-specific fallbacks
            if isinstance(media, Photo): file_name = f"{base_name}.jpg"
            elif isinstance(media, Video): file_name = f"{base_name}.mp4"
            elif isinstance(media, Audio): file_name = f"{base_name}.mp3"
            elif isinstance(media, Voice): file_name = f"{base_name}.ogg"
            elif isinstance(media, Animation): file_name = f"{base_name}.mp4"
            elif isinstance(media, Sticker): file_name = f"{base_name}.webp"
            elif isinstance(media, Document): file_name = base_name
            else: file_name = base_name

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
    elif isinstance(media, Video) and (not current_extension or current_extension not in ['.mp4', '.mkv', '.mov', '.webm']):
        file_name = f"{file_name.split('.')[0]}.mp4"
        if mime_type not in ["video/mp4", "video/quicktime", "video/x-matroska", "video/webm"]: mime_type = "video/mp4"

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
