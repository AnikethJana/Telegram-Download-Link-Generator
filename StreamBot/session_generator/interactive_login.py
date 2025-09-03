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
from ..database.user_sessions import store_user_session
from ..utils.secure_storage import secure_storage
from ..utils.webshare_proxy import webshare_proxy

logger = logging.getLogger(__name__)

class InteractiveLoginManager:
    """Manages interactive Pyrogram session generation for multiple users."""

    def __init__(self):
        # Use a dictionary to manage client instances for each user's login attempt
        self.clients: Dict[int, Client] = {}
        self._lock = asyncio.Lock()
        # Track login state for timeouts and cleanup
        self.login_state: Dict[int, Dict[str, any]] = {}
        
        logger.info("InteractiveLoginManager initialized for user credential-based sessions")
    
    def _create_client(self, name: str, api_id: int, api_hash: str, 
                      proxy_username: str = None, proxy_password: str = None) -> Client:
        """Create Pyrogram client with user's API credentials and optional Webshare proxy."""
        client_kwargs = {
            'name': name,
            'api_id': api_id,
            'api_hash': api_hash,
            'in_memory': True
        }
        
        # Add Webshare proxy if credentials provided
        if proxy_username and proxy_password:
            proxy_config = webshare_proxy.get_proxy_config(proxy_username, proxy_password)
            if proxy_config:
                client_kwargs['proxy'] = proxy_config
        
        return Client(**client_kwargs)

    async def start_login(self, user_id: int, api_id: int, api_hash: str, 
                         phone_number: str, proxy_username: str = None, proxy_password: str = None) -> Dict[str, any]:
        """Initiate the login process with user's API credentials."""
        async with self._lock:
            if user_id in self.clients:
                return {'status': 'error', 'message': 'Login process already started.'}

        try:
            # Store credentials securely
            secure_storage.store_credentials(user_id, api_id, api_hash, phone_number)
            
            # Create client with user's credentials
            client = self._create_client(f"user_{user_id}", api_id, api_hash, proxy_username, proxy_password)
            self.clients[user_id] = client

            await client.connect()
            
            # Send verification code
            sent_code_info = await client.send_code(phone_number)
            
            # Record login state
            self.login_state[user_id] = {
                'started_at': asyncio.get_event_loop().time(),
                'completed': False,
                'phone_number': phone_number
            }
            asyncio.create_task(self._watch_timeout(user_id))

            logger.info(f"Verification code sent to user {user_id}")
            return {
                'status': 'code_sent',
                'message': 'Verification code has been sent to your phone.',
                'phone_code_hash': sent_code_info.phone_code_hash
            }

        except FloodWait as e:
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': f'Rate limited. Please wait {e.value} seconds.'}
        except PhoneNumberBanned:
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': 'This phone number is restricted. Please try a different number.'}
        except PhoneNumberInvalid:
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': 'Invalid phone number. Please include country code (+1234567890).'}
        except ApiIdInvalid:
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': 'Invalid API credentials. Please check your API ID and Hash.'}
        except Exception as e:
            logger.error(f"Login error for user {user_id}: {e}")
            await self.cleanup_client(user_id)
            return {'status': 'error', 'message': 'An error occurred. Please try again.'}

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
                'id': me.id, 
                'first_name': me.first_name or '', 
                'last_name': me.last_name or '', 
                'username': me.username or ''
            }
            # Mark completed
            if user_id in self.login_state:
                self.login_state[user_id]['completed'] = True
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
                'id': me.id, 
                'first_name': me.first_name or '', 
                'last_name': me.last_name or '', 
                'username': me.username or ''
            }
            # Mark completed  
            if user_id in self.login_state:
                self.login_state[user_id]['completed'] = True
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
            await asyncio.sleep(300)  # 5 minutes timeout
            state = self.login_state.get(user_id)
            if state and not state.get('completed', False):
                await self.cleanup_client(user_id)
                logger.info(f"Login session timed out for user {user_id}")
        except Exception as e:
            logger.debug(f"Timeout watcher error for user {user_id}: {e}")

# Global instance
interactive_login_manager = InteractiveLoginManager()
