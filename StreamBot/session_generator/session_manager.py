# StreamBot/session_generator/session_manager.py
import asyncio
import logging
from typing import Optional, Dict, Any
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid, PhoneNumberInvalid,
    SessionPasswordNeeded, FloodWait, AuthKeyUnregistered
)
from StreamBot.config import Var
from StreamBot.database.user_sessions import store_user_session

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages Pyrogram session generation for users with memory optimization and thread safety."""

    def __init__(self):
        self.api_id = Var.API_ID
        self.api_hash = Var.API_HASH
        self._lock = asyncio.Lock()  # Thread safety for concurrent session generation
        self._active_sessions = set()  # Track active session generation to prevent duplicates
        
    async def generate_user_session(self, user_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a Pyrogram session for the user using the bot's API credentials.
        Thread-safe with race condition prevention.
        """
        async with self._lock:
            # Prevent concurrent session generation for the same user
            if user_id in self._active_sessions:
                logger.warning(f"Session generation already in progress for user {user_id}")
                return {
                    'success': False,
                    'error': 'Session generation already in progress'
                }

            self._active_sessions.add(user_id)

        try:
            logger.info(f"Starting session generation for user {user_id}")

            # Check if user already has an active session
            from StreamBot.database.user_sessions import check_user_has_session
            has_session = await check_user_has_session(user_id)
            if has_session:
                logger.info(f"User {user_id} already has an active session")
                return {
                    'success': False,
                    'error': 'User already has an active session'
                }

            # Use a simple session name with timestamp for uniqueness
            session_name = f"user_{user_id}_{int(asyncio.get_event_loop().time())}"

            session_string = await self._create_bot_session_for_user(user_id, session_name)

            if session_string:
                # Store the session in database
                success = await store_user_session(user_id, session_string, user_info)

                if success:
                    logger.info(f"Session successfully generated and stored for user {user_id}")

                    # Send notification without blocking
                    asyncio.create_task(self.notify_bot_about_new_session(user_id, user_info))

                    return {
                        'success': True,
                        'message': 'Session generated successfully',
                        'user_id': user_id
                    }
                else:
                    logger.error(f"Failed to store session for user {user_id}")
                    return {
                        'success': False,
                        'error': 'Failed to store session in database'
                    }
            else:
                logger.error(f"Failed to generate session for user {user_id}")
                return {
                    'success': False,
                    'error': 'Failed to generate session'
                }

        except Exception as e:
            logger.error(f"Error in session generation for user {user_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Session generation failed: {str(e)}'
            }
        finally:
            # Always remove from active sessions set
            async with self._lock:
                self._active_sessions.discard(user_id)
    
    async def _create_bot_session_for_user(self, user_id: int, session_name: str) -> Optional[str]:
        """
        Create a session string using bot credentials.
        Memory optimized - uses in-memory session and immediate cleanup.
        """
        client = None
        try:
            # Create a memory-only client to reduce disk I/O and cleanup overhead
            client = Client(
                name=session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                bot_token=Var.BOT_TOKEN,
                in_memory=True,  # Keep in memory only for efficiency
                workers=1  # Minimal workers for session generation
            )
            
            # Start the client to generate session
            await client.start()
            
            # Get the session string
            session_string = await client.export_session_string()
            
            logger.debug(f"Session string generated for user {user_id}")
            
            return session_string
            
        except Exception as e:
            logger.error(f"Error creating session for user {user_id}: {e}")
            return None
        finally:
            # Always cleanup the client to free memory
            if client:
                try:
                    if client.is_connected:
                        await client.stop()
                except Exception as cleanup_error:
                    logger.debug(f"Error during client cleanup: {cleanup_error}")
                finally:
                    # Force cleanup
                    client = None
    
    async def notify_bot_about_new_session(self, user_id: int, user_info: Dict[str, Any]) -> bool:
        """
        Notify the main bot about a new user session via internal communication.
        Non-blocking to avoid memory pressure.
        """
        try:
            # Import here to avoid circular imports
            from StreamBot.__main__ import CLIENT_MANAGER_INSTANCE
            
            if CLIENT_MANAGER_INSTANCE:
                primary_client = CLIENT_MANAGER_INSTANCE.get_primary_client()
                
                if primary_client and primary_client.is_connected:
                    # Send a message to the user about successful session creation
                    welcome_message = f"""✅ **Session Generated Successfully!**

Hello {user_info.get('first_name', 'User')}! Your session has been created and securely stored.

You can now:
• Share private channel/group post URLs with me
• Get direct download links for private content
• Use `/logout` to remove your session anytime

**Privacy:** Your session is encrypted and only used to access content you share with me."""
                    
                    try:
                        await primary_client.send_message(
                            chat_id=user_id,
                            text=welcome_message
                        )
                        logger.info(f"Welcome message sent to user {user_id}")
                        return True
                    except Exception as e:
                        logger.warning(f"Could not send welcome message to user {user_id}: {e}")
                        return False
                else:
                    logger.warning("Primary client not available for sending notification")
                    return False
            else:
                logger.warning("ClientManager not available for sending notification")
                return False
                
        except Exception as e:
            logger.error(f"Error notifying bot about new session for user {user_id}: {e}", exc_info=True)
            return False
    
    async def validate_session_string(self, session_string: str) -> bool:
        """Validate that a session string is properly formatted."""
        try:
            if not session_string or not isinstance(session_string, str):
                return False
            
            # Basic validation - Pyrogram session strings are base64-like
            # and have a specific length range
            if len(session_string) < 100 or len(session_string) > 1000:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating session string: {e}")
            return False

# Global instance
session_manager = SessionManager() 