# StreamBot/link_handler.py
import re
import asyncio
import logging
from typing import Optional, Tuple
from pyrogram import Client
from pyrogram.errors import UserNotParticipant, ChannelPrivate, FloodWait
from .database.user_sessions import get_user_session
from .config import Var

logger = logging.getLogger(__name__)

class UserSessionStreamer:
    """Handles streaming files directly from user sessions without forwarding."""
    
    def __init__(self):
        self.active_clients = {}  # user_id -> client instance
        self._lock = asyncio.Lock()
    
    async def get_user_client(self, user_id: int) -> Optional[Client]:
        """Get or create a client for the user's session."""
        async with self._lock:
            if user_id in self.active_clients:
                client = self.active_clients[user_id]
                if client.is_connected:
                    return client
                else:
                    # Clean up disconnected client
                    del self.active_clients[user_id]
            
            # Create new client
            session_string = await get_user_session(user_id)
            if not session_string:
                return None
            
            try:
                client = Client(
                    name=f"user_stream_{user_id}",
                    session_string=session_string,
                    in_memory=True
                )
                await client.start()
                self.active_clients[user_id] = client
                return client
            except Exception as e:
                logger.error(f"Failed to create user client for {user_id}: {e}")
                return None
    
    async def cleanup_user_client(self, user_id: int):
        """Clean up user client after use."""
        async with self._lock:
            if user_id in self.active_clients:
                client = self.active_clients[user_id]
                try:
                    if client.is_connected:
                        await client.stop()
                except:
                    pass
                del self.active_clients[user_id]

# Global instance
user_session_streamer = UserSessionStreamer()

async def get_message_from_link(user_id: int, message_link: str):
    """
    Fetches a message from a t.me link using the user's session.
    Returns a tuple (message, user_client) on success, or error string on failure.
    """
    parsed_link = parse_message_link(message_link)
    if not parsed_link:
        return "The provided link is not a valid Telegram message link."

    chat_id, message_id = parsed_link
    
    try:
        user_client = await user_session_streamer.get_user_client(user_id)
        if not user_client:
            return "Your session has expired or is invalid. Please /login again."

        try:
            message = await user_client.get_messages(chat_id=chat_id, message_ids=message_id)
            if not message or not message.media:
                return "Could not retrieve the message or it contains no media. It may have been deleted or the link is incorrect."
            
            # Return both message and client - client will be used for streaming
            return (message, user_client)

        except UserNotParticipant:
            await user_session_streamer.cleanup_user_client(user_id)
            return "You are not a member of the channel or group from which this link originates. Please join it and try again."
        except ChannelPrivate:
            await user_session_streamer.cleanup_user_client(user_id)
            return "This is a private channel/group. Make sure you are a member."
        except FloodWait as e:
            return f"Rate limited by Telegram. Please wait {e.value} seconds and try again."
        except Exception as e:
            logger.error(f"Error fetching message for user {user_id} from link {message_link}: {e}", exc_info=True)
            await user_session_streamer.cleanup_user_client(user_id)
            return "An unexpected error occurred while trying to access the message. Please ensure the link is correct."

    except Exception as e:
        logger.error(f"Failed to initialize user client for user {user_id}: {e}", exc_info=True)
        return "Could not initialize your session. Please try logging out and in again."


def parse_message_link(link: str) -> Optional[Tuple[str | int, int]]:
    """
    Parses a Telegram message link and extracts the chat ID and message ID.
    Handles both public (t.me/username/123) and private (t.me/c/12345/678) links.
    """
    # IMPORTANT: Check private links FIRST to avoid matching "/c/" as a public username
    # Regex for private channels/supergroups: t.me/c/channel_id/message_id
    private_match = re.match(r"https?://t\.me/c/(\d+)/(\d+)", link)
    if private_match:
        channel_id, message_id = private_match.groups()
        # Private channel IDs need to be prefixed with -100
        return int(f"-100{channel_id}"), int(message_id)

    # Regex for public channels/supergroups: t.me/channel_name/message_id
    public_match = re.match(r"https?://t\.me/(\w+)/(\d+)", link)
    if public_match:
        channel_name, message_id = public_match.groups()
        return f"@{channel_name}", int(message_id)

    return None
