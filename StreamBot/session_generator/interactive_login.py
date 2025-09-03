# StreamBot/session_generator/interactive_login.py
import asyncio
import logging
from typing import Dict, Optional
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid, ApiHashInvalid, PhoneNumberInvalid, PhoneCodeInvalid,
    SessionPasswordNeeded, FloodWait, PhoneCodeExpired, UserNotParticipant
)
from ..config import Var
from ..database.user_sessions import store_user_session

logger = logging.getLogger(__name__)

class InteractiveLoginManager:
    """Manages interactive Pyrogram session generation for multiple users."""

    def __init__(self):
        self.api_id = Var.API_ID
        self.api_hash = Var.API_HASH
        # Use a dictionary to manage client instances for each user's login attempt
        self.clients: Dict[int, Client] = {}
        self._lock = asyncio.Lock()

    async def start_login(self, user_id: int, phone_number: str) -> Dict[str, any]:
        """Initiate the login process for a user."""
        async with self._lock:
            if user_id in self.clients:
                return {'status': 'error', 'message': 'Login process already started.'}

            try:
                client = Client(
                    name=f"user_{user_id}_{phone_number}",
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    in_memory=True  # Use in-memory storage for session generation
                )
                self.clients[user_id] = client

                await client.connect()
                sent_code_info = await client.send_code(phone_number)
                
                return {
                    'status': 'code_sent',
                    'message': 'Verification code has been sent.',
                    'phone_code_hash': sent_code_info.phone_code_hash
                }

            except FloodWait as e:
                await self.cleanup_client(user_id)
                return {'status': 'error', 'message': f"Flood wait: Please wait {e.value} seconds."}
            except PhoneNumberInvalid:
                await self.cleanup_client(user_id)
                return {'status': 'error', 'message': 'The phone number is invalid.'}
            except Exception as e:
                logger.error(f"Error starting login for user {user_id}: {e}", exc_info=True)
                await self.cleanup_client(user_id)
                return {'status': 'error', 'message': 'An unexpected error occurred.'}

    async def submit_code(self, user_id: int, phone_number: str, phone_code_hash: str, code: str) -> Dict[str, any]:
        """Submit the verification code received by the user."""
        client = self.clients.get(user_id)
        if not client:
            return {'status': 'error', 'message': 'Login process not found. Please start over.'}

        try:
            signed_in_user = await client.sign_in(phone_number, phone_code_hash, code)
            
            if isinstance(signed_in_user, UserNotParticipant):
                 return {'status': '2fa_needed', 'message': 'Two-factor authentication is enabled.'}

            # Session generation successful
            session_string = await client.export_session_string()
            me = await client.get_me()
            user_info = {
                'id': me.id, 'first_name': me.first_name, 'last_name': me.last_name, 'username': me.username
            }
            return {'status': 'success', 'session_string': session_string, 'user_info': user_info}

        except PhoneCodeInvalid:
            return {'status': 'error', 'message': 'The verification code is invalid.'}
        except PhoneCodeExpired:
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': 'The verification code has expired. Please try again.'}
        except SessionPasswordNeeded:
            return {'status': '2fa_needed', 'message': 'Two-factor authentication is enabled.'}
        except Exception as e:
            logger.error(f"Error submitting code for user {user_id}: {e}", exc_info=True)
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': 'An error occurred while verifying the code.'}

    async def submit_password(self, user_id: int, password: str) -> Dict[str, any]:
        """Submit the 2FA password for the user."""
        client = self.clients.get(user_id)
        if not client:
            return {'status': 'error', 'message': 'Login process not found. Please start over.'}

        try:
            await client.check_password(password)
            session_string = await client.export_session_string()
            me = await client.get_me()
            user_info = {
                'id': me.id, 'first_name': me.first_name, 'last_name': me.last_name, 'username': me.username
            }
            return {'status': 'success', 'session_string': session_string, 'user_info': user_info}

        except Exception as e:
            logger.error(f"Error submitting password for user {user_id}: {e}", exc_info=True)
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': 'Incorrect password or another error occurred.'}

    async def get_client(self, user_id: int) -> Optional[Client]:
        """Retrieve the client instance for a user."""
        return self.clients.get(user_id)

    async def cleanup_client(self, user_id: int):
        """Clean up the client instance after the login process is complete or fails."""
        async with self._lock:
            client = self.clients.pop(user_id, None)
            if client and client.is_connected:
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.debug(f"Error during client cleanup for user {user_id}: {e}")

# Global instance
interactive_login_manager = InteractiveLoginManager()
