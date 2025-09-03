# StreamBot/utils/secure_storage.py
import os
import json
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

logger = logging.getLogger(__name__)

class SecureCredentialStorage:
    """Secure storage for user API credentials and session data."""
    
    def __init__(self):
        self.storage_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_credentials')
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _get_encryption_key(self, user_id: int, password: str) -> bytes:
        """Generate encryption key from user ID and password."""
        salt = f"telegram_session_{user_id}".encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _get_user_file_path(self, user_id: int) -> str:
        """Get secure file path for user credentials."""
        user_hash = hashlib.sha256(f"{user_id}".encode()).hexdigest()[:16]
        return os.path.join(self.storage_dir, f"cred_{user_hash}.enc")
    
    def store_credentials(self, user_id: int, api_id: int, api_hash: str, phone: str) -> bool:
        """Store user API credentials securely."""
        try:
            # Use phone number as password for encryption key
            key = self._get_encryption_key(user_id, phone)
            fernet = Fernet(key)
            
            credentials = {
                'api_id': api_id,
                'api_hash': api_hash,
                'phone': phone,
                'user_id': user_id
            }
            
            # Encrypt and store
            encrypted_data = fernet.encrypt(json.dumps(credentials).encode())
            
            file_path = self._get_user_file_path(user_id)
            with open(file_path, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info(f"Stored credentials for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credentials for user {user_id}: {e}")
            return False
    
    def get_credentials(self, user_id: int, phone: str) -> dict:
        """Retrieve user API credentials."""
        try:
            file_path = self._get_user_file_path(user_id)
            
            if not os.path.exists(file_path):
                return None
            
            # Decrypt data
            key = self._get_encryption_key(user_id, phone)
            fernet = Fernet(key)
            
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = fernet.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode())
            
            # Verify phone matches
            if credentials.get('phone') != phone:
                logger.warning(f"Phone mismatch for user {user_id}")
                return None
                
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to retrieve credentials for user {user_id}: {e}")
            return None
    
    def delete_credentials(self, user_id: int) -> bool:
        """Delete user credentials."""
        try:
            file_path = self._get_user_file_path(user_id)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted credentials for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete credentials for user {user_id}: {e}")
            return False

# Global instance
secure_storage = SecureCredentialStorage()
