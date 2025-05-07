import mimetypes
from pyrogram.types import Message, Audio, Document, Photo, Video, Animation, Sticker, Voice
import base64
import binascii # For catching specific base64 errors
from config import Var # To access LOG_CHANNEL for the key
import logging

logger = logging.getLogger(__name__)
# --- Human Readable Size ---
def humanbytes(size: int) -> str:
    """Converts bytes to a human-readable format."""
    if not size:
        return "0 B"
    power = 1024
    t_n = 0
    power_dict = {0: " ", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size /= power
        t_n += 1
    return "{:.2f} {}B".format(size, power_dict[t_n])

# --- Get File Attributes ---
def get_file_attr(message: Message):
    """Extracts essential file attributes from a Pyrogram Message object."""
    media = (
        message.audio or message.document or message.photo or message.video or
        message.animation or message.sticker or message.voice
    )

    if not media:
        logger.warning(f"No media found in message ID {message.id} from chat {message.chat.id if message.chat else 'Unknown'}.")
        return None, "unknown_file", 0, "application/octet-stream", None # Provide defaults

    file_id = getattr(media, 'file_id', None)
    file_unique_id = getattr(media, 'file_unique_id', None) # Useful for potential caching later
    
    # Initialize with defaults or attempt to get actual values
    file_name = getattr(media, 'file_name', None)
    file_size = getattr(media, 'file_size', None) 
    mime_type = getattr(media, 'mime_type', None)

    # Log if critical info is missing from the media object itself
    if file_name is None:
        logger.warning(f"Media object for message {message.id} (type: {type(media).__name__}) missing 'file_name'. File ID: {file_id}")
    if file_size is None: # Specifically check for None, 0 is a valid size
        logger.warning(f"Media object for message {message.id} (type: {type(media).__name__}) missing 'file_size'. File ID: {file_id}. Defaulting to 0.")
        file_size = 0 # Default to 0 if None
    
    # Fallback for file_name
    if not file_name:
        base_name = file_unique_id or file_id or f"media_{message.id}"
        # Try to guess extension from mime_type if available
        guessed_extension = mimetypes.guess_extension(mime_type) if mime_type else None
        if guessed_extension:
            file_name = f"{base_name}{guessed_extension}"
        else:
            # Fallback extensions based on media type if name is still missing
            if isinstance(media, Photo): file_name = f"{base_name}.jpg"
            elif isinstance(media, Video): file_name = f"{base_name}.mp4"
            elif isinstance(media, Audio): file_name = f"{base_name}.mp3"
            elif isinstance(media, Voice): file_name = f"{base_name}.ogg"
            elif isinstance(media, Animation): file_name = f"{base_name}.mp4" # Often GIFs are sent as MP4
            elif isinstance(media, Sticker): file_name = f"{base_name}.webp"
            elif isinstance(media, Document): file_name = base_name # No good default extension for generic document
            else: file_name = base_name # Ultimate fallback

    # Fallback for mime_type
    if not mime_type:
        if file_name:
            mime_type = mimetypes.guess_type(file_name)[0]
        if not mime_type: # If still no mime_type
            logger.warning(f"Could not determine mime_type for message {message.id}, file_name: {file_name}. Defaulting to octet-stream.")
            mime_type = "application/octet-stream"


    # Specific type handling from original code (good for ensuring extensions if name was generic)
    # This can refine a generic name obtained above if it didn't have an extension
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
    # Add similar for Video, Animation if their file_names are often extensionless
    elif isinstance(media, Video) and (not current_extension or current_extension not in ['.mp4', '.mkv', '.mov', '.webm']):
        file_name = f"{file_name.split('.')[0]}.mp4" # Default to .mp4 if unknown video
        if mime_type not in ["video/mp4", "video/quicktime", "video/x-matroska", "video/webm"]: mime_type = "video/mp4"


    # Final check for size, ensure it's an int
    if not isinstance(file_size, int):
        logger.warning(f"File size for message {message.id} was not an int ('{file_size}'). Defaulting to 0.")
        file_size = 0

    return file_id, file_name, file_size, mime_type, file_unique_id

def get_id_encoder_key():
    """
    Returns the key used for encoding/decoding message IDs.
    Ensures the key is not zero.
    """
    key = abs(Var.LOG_CHANNEL)
    if key == 0:
        logger.critical("LOG_CHANNEL is 0, which is invalid for ID encoding. Please set a valid LOG_CHANNEL.")
        # Fallback to a default prime if LOG_CHANNEL is somehow 0, though LOG_CHANNEL should always be non-zero.
        # This is a safeguard; configuration should ensure LOG_CHANNEL is valid.
        return 961748927 # A large prime number
    return key

def encode_message_id(message_id: int) -> str:
    """Encodes a message ID for use in URLs."""
    try:
        key = get_id_encoder_key()
        transformed_id = message_id * key
        encoded_bytes = base64.urlsafe_b64encode(str(transformed_id).encode('utf-8'))
        return encoded_bytes.decode('utf-8').rstrip("=") # Remove padding
    except Exception as e:
        logger.error(f"Error encoding message ID {message_id}: {e}", exc_info=True)
        # Fallback to plain message_id if encoding fails, though this should be rare
        return str(message_id)

def decode_message_id(encoded_id_str: str) -> int | None:
    """Decodes an encoded ID string back to a message ID."""
    try:
        key = get_id_encoder_key()
        # Add padding back if it was removed
        padding = "=" * (-len(encoded_id_str) % 4)
        decoded_bytes = base64.urlsafe_b64decode((encoded_id_str + padding).encode('utf-8'))
        transformed_id_str = decoded_bytes.decode('utf-8')

        transformed_id = int(transformed_id_str)

        if transformed_id % key != 0:
            # This means the number wasn't a clean multiple, so it's likely invalid or tampered
            logger.warning(f"Invalid encoded ID (key mismatch): {encoded_id_str}")
            return None

        original_message_id = transformed_id // key

        # Sanity check: re-encode and see if it matches part of the logic
        # This helps ensure the division was "clean" and it's not a random number
        # that happens to be divisible by the key.
        if (original_message_id * key) != transformed_id:
            logger.warning(f"Encoded ID verification failed for {encoded_id_str}. Potential tampering or wrong key.")
            return None

        return original_message_id
    except (binascii.Error, ValueError, UnicodeDecodeError) as e:
        logger.warning(f"Error decoding ID '{encoded_id_str}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding ID '{encoded_id_str}': {e}", exc_info=True)
        return None
