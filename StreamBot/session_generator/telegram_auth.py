# StreamBot/session_generator/telegram_auth.py
import hmac
import hashlib
import logging
import time
from typing import Dict, Any, Optional
from StreamBot.config import Var

logger = logging.getLogger(__name__)

class TelegramAuth:
    """Handle Telegram Login Widget authentication verification."""
    
    def __init__(self):
        self.bot_token = Var.BOT_TOKEN
        
    def verify_telegram_auth(self, auth_data: Dict[str, Any]) -> bool:
        """
        Verify Telegram login widget authentication data.
        
        Based on: https://core.telegram.org/widgets/login#checking-authorization
        """
        try:
            # Check if auth_date is present and not too old (24 hours)
            auth_date = auth_data.get('auth_date')
            if not auth_date:
                logger.warning("Missing auth_date in Telegram auth data")
                return False
            
            try:
                auth_timestamp = int(auth_date)
                current_timestamp = int(time.time())
                
                # Check if auth is not older than 24 hours
                if current_timestamp - auth_timestamp > 86400:
                    logger.warning(f"Telegram auth data too old: {current_timestamp - auth_timestamp} seconds")
                    return False
                    
            except (ValueError, TypeError):
                logger.warning(f"Invalid auth_date format: {auth_date}")
                return False
            
            # Get the hash from auth data
            received_hash = auth_data.get('hash')
            if not received_hash:
                logger.warning("Missing hash in Telegram auth data")
                return False
            
            # Remove hash from data for verification
            auth_data_copy = auth_data.copy()
            del auth_data_copy['hash']
            
            # Create the data string for verification
            data_check_arr = []
            for key in sorted(auth_data_copy.keys()):
                value = auth_data_copy[key]
                if value is not None:
                    data_check_arr.append(f"{key}={value}")
            
            data_check_string = '\n'.join(data_check_arr)
            
            # Create secret key from bot token
            secret_key = hashlib.sha256(self.bot_token.encode('utf-8')).digest()
            
            # Calculate expected hash
            expected_hash = hmac.new(
                secret_key,
                data_check_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare hashes
            is_valid = hmac.compare_digest(expected_hash, received_hash)
            
            if not is_valid:
                logger.warning("Telegram auth hash verification failed")
                logger.debug(f"Expected: {expected_hash}, Received: {received_hash}")
                logger.debug(f"Data string: {data_check_string}")
            else:
                logger.info(f"Telegram auth verified for user {auth_data.get('id')}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying Telegram auth: {e}", exc_info=True)
            return False
    
    def extract_user_info(self, auth_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract clean user information from Telegram auth data."""
        try:
            user_id = auth_data.get('id')
            if not user_id:
                logger.warning("Missing user ID in Telegram auth data")
                return None
            
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user ID format: {user_id}")
                return None
            
            # Extract user information
            user_info = {
                'id': user_id,
                'first_name': auth_data.get('first_name', ''),
                'last_name': auth_data.get('last_name', ''),
                'username': auth_data.get('username', ''),
                'photo_url': auth_data.get('photo_url', ''),
                'auth_date': int(auth_data.get('auth_date', 0))
            }
            
            # Clean empty values
            user_info = {k: v for k, v in user_info.items() if v}
            
            logger.debug(f"Extracted user info for {user_id}: {user_info.get('first_name')} @{user_info.get('username', 'No username')}")
            
            return user_info
            
        except Exception as e:
            logger.error(f"Error extracting user info from Telegram auth: {e}", exc_info=True)
            return None
    
    def validate_auth_data_format(self, auth_data: Dict[str, Any]) -> bool:
        """Validate that auth data has required fields in correct format."""
        try:
            # Required fields
            required_fields = ['id', 'auth_date', 'hash']
            
            for field in required_fields:
                if field not in auth_data:
                    logger.warning(f"Missing required field in auth data: {field}")
                    return False
            
            # Validate ID is numeric
            try:
                int(auth_data['id'])
            except (ValueError, TypeError):
                logger.warning(f"Invalid user ID format: {auth_data.get('id')}")
                return False
            
            # Validate auth_date is numeric
            try:
                int(auth_data['auth_date'])
            except (ValueError, TypeError):
                logger.warning(f"Invalid auth_date format: {auth_data.get('auth_date')}")
                return False
            
            # Hash should be present and non-empty
            if not auth_data.get('hash'):
                logger.warning("Empty or missing hash in auth data")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating auth data format: {e}", exc_info=True)
            return False

# Global instance
telegram_auth = TelegramAuth() 