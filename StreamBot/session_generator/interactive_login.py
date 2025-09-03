# StreamBot/session_generator/interactive_login.py
import asyncio
import logging
from typing import Dict, Optional
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid,
    SessionPasswordNeeded, FloodWait, PhoneCodeExpired, UserNotParticipant
)
try:
    from pyrogram.errors import PhoneNumberBanned  # Pyrogram >= 2.3.x
except Exception:  # Fallback if class name differs
    PhoneNumberBanned = type("PhoneNumberBanned", (Exception,), {})
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
        # Track login state for timeouts and cleanup
        self.login_state: Dict[int, Dict[str, any]] = {}

    async def start_login(self, user_id: int, phone_number: str) -> Dict[str, any]:
        """Initiate the login process for a user."""
        async with self._lock:
            if user_id in self.clients:
                return {'status': 'error', 'message': 'Login process already started.'}

            try:
                # Sanitize phone number: keep leading '+' and digits, strip spaces/hyphens/parentheses
                if phone_number:
                    cleaned = ''.join(ch for ch in phone_number.strip() if ch.isdigit() or ch == '+')
                    # Ensure only one '+' at start
                    if '+' in cleaned:
                        cleaned = '+' + cleaned.replace('+', '')
                    phone_number = cleaned

                client = Client(
                    name=f"user_{user_id}_{phone_number}",
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    in_memory=True  # Use in-memory storage for session generation
                )
                self.clients[user_id] = client

                await client.connect()
                # Apply 30s timeout to the server-side code dispatch call itself
                try:
                    sent_code_info = await asyncio.wait_for(client.send_code(phone_number), timeout=30)
                except asyncio.TimeoutError:
                    await self.cleanup_client(user_id)
                    return {'status': 'timeout', 'message': 'No response from Telegram while sending code. Please try again.'}
                
                # Record login state and start timeout watcher (30s)
                self.login_state[user_id] = {
                    'started_at': asyncio.get_event_loop().time(),
                    'timeout_secs': 30,
                    'completed': False,
                    'proxy_used': False,
                    'phone_number': phone_number
                }
                asyncio.create_task(self._watch_timeout(user_id))

                return {
                    'status': 'code_sent',
                    'message': 'Verification code has been sent.',
                    'phone_code_hash': sent_code_info.phone_code_hash
                }

            except FloodWait as e:
                await self.cleanup_client(user_id)
                return {'status': 'error', 'message': f"Flood wait: Please wait {e.value} seconds."}
            except PhoneNumberBanned:
                await self.cleanup_client(user_id)
                return {
                    'status': 'error',
                    'message': (
                        'Login was rejected for this number. This can happen due to temporary restrictions '
                        'or security filters. Please verify the number format (+countrycodeXXXXXXXXXX) and '
                        'try again later.'
                    )
                }
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
            # Enforce 30s timeout window
            state = self.login_state.get(user_id)
            if state:
                started = state.get('started_at', 0.0)
                timeout_secs = state.get('timeout_secs', 30)
                if asyncio.get_event_loop().time() - started > timeout_secs:
                    await self.cleanup_client(user_id)
                    self.login_state.pop(user_id, None)
                    return {'status': 'timeout', 'message': 'Code session timed out. Please request a new code.'}

            signed_in_user = await client.sign_in(phone_number, phone_code_hash, code)
            
            if isinstance(signed_in_user, UserNotParticipant):
                 return {'status': '2fa_needed', 'message': 'Two-factor authentication is enabled.'}

            # Session generation successful
            session_string = await client.export_session_string()
            me = await client.get_me()
            user_info = {
                'id': me.id, 
                'first_name': me.first_name or '', 
                'last_name': me.last_name or '', 
                'username': me.username or ''
            }
            logger.debug(f"Interactive login successful for user {user_id}, user_info: {user_info}")
            # Mark completed
            self.login_state.pop(user_id, None)
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
            # Enforce 30s timeout window for 2FA as well
            state = self.login_state.get(user_id)
            if state:
                started = state.get('started_at', 0.0)
                timeout_secs = state.get('timeout_secs', 30)
                if asyncio.get_event_loop().time() - started > timeout_secs:
                    await self.cleanup_client(user_id)
                    self.login_state.pop(user_id, None)
                    return {'status': 'timeout', 'message': '2FA session timed out. Please request a new code.'}

            await client.check_password(password)
            session_string = await client.export_session_string()
            me = await client.get_me()
            user_info = {
                'id': me.id, 
                'first_name': me.first_name or '', 
                'last_name': me.last_name or '', 
                'username': me.username or ''
            }
            logger.debug(f"Interactive login with 2FA successful for user {user_id}, user_info: {user_info}")
            # Mark completed
            self.login_state.pop(user_id, None)
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
            # Clear state
            self.login_state.pop(user_id, None)

    async def _watch_timeout(self, user_id: int):
        """Background watcher to auto-cleanup stale login sessions after timeout."""
        try:
            state = self.login_state.get(user_id)
            if not state:
                return
            timeout_secs = state.get('timeout_secs', 30)
            await asyncio.sleep(timeout_secs + 1)
            # If still not completed, cleanup
            state_after = self.login_state.get(user_id)
            if state_after is not None:
                await self.cleanup_client(user_id)
                logger.debug(f"Login session timed out for user {user_id}; cleaned up.")
        except Exception as e:
            logger.debug(f"Timeout watcher error for user {user_id}: {e}")

# Global instance
interactive_login_manager = InteractiveLoginManager()
