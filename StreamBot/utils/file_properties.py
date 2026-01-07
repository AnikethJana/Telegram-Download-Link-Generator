from pyrogram import Client
from pyrogram.types import Message
from pyrogram.file_id import FileId
from typing import Any, Optional
from pyrogram.raw.types.messages import Messages


async def parse_file_id(message: "Message") -> Optional[FileId]:
    """Extract and decode the file ID from a message's media attachment."""
    media_obj = get_media_from_message(message)
    if media_obj is not None:
        return FileId.decode(media_obj.file_id)
    return None

async def parse_file_unique_id(message: "Messages") -> Optional[str]:
    """Extract the unique file identifier from a message's media attachment."""
    media_obj = get_media_from_message(message)
    if media_obj is not None:
        return media_obj.file_unique_id
    return None

async def get_file_ids(client: Client, chat_id: int, message_id: int) -> Optional[FileId]:
    message = await client.get_messages(chat_id, message_id)
    if message.empty:
        raise FileNotFoundError(f"Message {message_id} not found")
    media = get_media_from_message(message)
    file_unique_id = await parse_file_unique_id(message)
    file_id = await parse_file_id(message)
    setattr(file_id, "file_size", getattr(media, "file_size", 0))
    setattr(file_id, "mime_type", getattr(media, "mime_type", ""))
    setattr(file_id, "file_name", getattr(media, "file_name", ""))
    setattr(file_id, "unique_id", file_unique_id)
    return file_id

def get_media_from_message(message: "Message") -> Any:
    """
    Searches a message for any media attachments and returns the first one found.
    Checks common media types including documents, photos, videos, and audio.
    """
    # List of possible media attachment attributes
    possible_media_attrs = [
        "document",
        "photo", 
        "video",
        "audio",
        "animation",
        "voice",
        "video_note",
        "sticker",
    ]
    
    # Check each attribute and return first valid media found
    for attr_name in possible_media_attrs:
        media_content = getattr(message, attr_name, None)
        if media_content is not None:
            return media_content
    
    # No media found in message
    return None 