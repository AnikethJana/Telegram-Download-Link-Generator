import mimetypes
from pyrogram.types import Message, Audio, Document, Photo, Video, Animation, Sticker, Voice

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
        return None, None, None, None, None # No media found

    file_name = getattr(media, 'file_name', 'file') # Default name if not available
    file_size = getattr(media, 'file_size', 0)
    mime_type = getattr(media, 'mime_type', None)
    file_id = getattr(media, 'file_id', None)
    file_unique_id = getattr(media, 'file_unique_id', None) # Useful for potential caching later

    if not mime_type and file_name:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    # Ensure filename has an extension if possible (especially for photos)
    if isinstance(media, Photo):
        if not file_name or not '.' in file_name:
             file_name = f"{file_unique_id or file_id}.jpg" # Give photos a .jpg extension
             mime_type = "image/jpeg" # Assume JPEG for photos without mime type
    elif isinstance(media, Sticker):
         if not file_name or not '.' in file_name:
             file_name = f"{file_unique_id or file_id}.webp"
             mime_type = "image/webp"
    elif isinstance(media, Voice):
         if not file_name or not '.' in file_name:
             file_name = f"{file_unique_id or file_id}.ogg"
             mime_type = "audio/ogg"


    return file_id, file_name, file_size, mime_type, file_unique_id

