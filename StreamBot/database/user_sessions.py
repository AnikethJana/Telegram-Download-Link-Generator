# StreamBot/database/user_sessions.py
import logging
import datetime
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
import os
import base64
from .database import database

logger = logging.getLogger(__name__)

# User sessions collection with optimized settings
user_sessions = database['user_sessions']

# Encryption key for session strings (derived from LOG_CHANNEL for consistency)
def get_encryption_key() -> bytes:
    """Generate a consistent encryption key from LOG_CHANNEL."""
    from StreamBot.config import Var
    # Use LOG_CHANNEL as seed for encryption key
    seed = str(abs(Var.LOG_CHANNEL)).encode('utf-8')
    # Pad or truncate to 32 bytes for Fernet
    key = base64.urlsafe_b64encode(seed.ljust(32)[:32])
    return key

# Initialize Fernet cipher once to save memory
_cipher = Fernet(get_encryption_key())

async def store_user_session(user_id: int, session_string: str, user_info: Dict[str, Any]) -> bool:
    """Store encrypted user session in database with memory optimization."""
    try:
        # Input validation
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id for session storage: {user_id}")
            return False
        
        if not session_string or not isinstance(session_string, str):
            logger.warning(f"Invalid session_string for user {user_id}")
            return False
        
        # Encrypt session string
        encrypted_session = _cipher.encrypt(session_string.encode('utf-8'))
        
        # Prepare document with minimal data to save memory
        session_doc = {
            '_id': user_id,
            'encrypted_session': encrypted_session,
            'user_info': {
                'first_name': user_info.get('first_name', '')[:50],  # Limit length to save space
                'username': user_info.get('username', '')[:32],  # Limit length to save space
                'auth_date': user_info.get('auth_date')
            },
            'created_at': datetime.datetime.utcnow(),
            'last_used': datetime.datetime.utcnow(),
            'is_active': True
        }
        
        # Store in database (upsert) with write concern optimization
        result = user_sessions.replace_one(
            {'_id': user_id},
            session_doc,
            upsert=True
        )
        
        logger.info(f"User session stored for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing session for user {user_id}: {e}", exc_info=True)
        return False

async def get_user_session(user_id: int) -> Optional[str]:
    """Retrieve and decrypt user session from database with memory optimization."""
    try:
        # Input validation
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id for session retrieval: {user_id}")
            return None
        
        # Find session with minimal projection to save memory
        session_doc = user_sessions.find_one(
            {'_id': user_id, 'is_active': True},
            {'encrypted_session': 1, '_id': 1}  # Only get what we need
        )
        
        if not session_doc:
            logger.debug(f"No active session found for user {user_id}")
            return None
        
        # Decrypt session string
        encrypted_session = session_doc.get('encrypted_session')
        if not encrypted_session:
            logger.warning(f"Session document for user {user_id} missing encrypted_session")
            return None
        
        decrypted_session = _cipher.decrypt(encrypted_session).decode('utf-8')
        
        # Update last_used timestamp efficiently (separate operation)
        user_sessions.update_one(
            {'_id': user_id},
            {'$set': {'last_used': datetime.datetime.utcnow()}}
        )
        
        logger.debug(f"Session retrieved for user {user_id}")
        return decrypted_session
        
    except Exception as e:
        logger.error(f"Error retrieving session for user {user_id}: {e}", exc_info=True)
        return None

async def delete_user_session(user_id: int) -> bool:
    """Delete user session from database efficiently."""
    try:
        # Input validation
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id for session deletion: {user_id}")
            return False
        
        # Mark session as inactive instead of deleting for audit trail
        result = user_sessions.update_one(
            {'_id': user_id},
            {
                '$set': {
                    'is_active': False,
                    'deleted_at': datetime.datetime.utcnow()
                },
                '$unset': {'encrypted_session': 1}  # Remove encrypted data to save space
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Session deleted for user {user_id}")
            return True
        else:
            logger.warning(f"No session found to delete for user {user_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error deleting session for user {user_id}: {e}", exc_info=True)
        return False

async def check_user_has_session(user_id: int) -> bool:
    """Check if user has an active session efficiently."""
    try:
        # Input validation
        if not isinstance(user_id, int) or user_id <= 0:
            return False
        
        # Check for active session with minimal projection
        session_doc = user_sessions.find_one(
            {'_id': user_id, 'is_active': True},
            {'_id': 1}  # Only return _id field for efficiency
        )
        
        return session_doc is not None
        
    except Exception as e:
        logger.error(f"Error checking session for user {user_id}: {e}", exc_info=True)
        return False

async def get_user_session_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user session metadata (without decrypting session string) efficiently."""
    try:
        # Input validation
        if not isinstance(user_id, int) or user_id <= 0:
            return None
        
        # Find session metadata with projection to save memory
        session_doc = user_sessions.find_one(
            {'_id': user_id, 'is_active': True},
            {
                '_id': 1,
                'user_info': 1,
                'created_at': 1,
                'last_used': 1,
                'is_active': 1
            }
        )
        
        if not session_doc:
            return None
        
        return {
            'user_id': session_doc['_id'],
            'user_info': session_doc.get('user_info', {}),
            'created_at': session_doc.get('created_at'),
            'last_used': session_doc.get('last_used'),
            'is_active': session_doc.get('is_active', False)
        }
        
    except Exception as e:
        logger.error(f"Error getting session info for user {user_id}: {e}", exc_info=True)
        return None

async def cleanup_old_sessions(days_old: int = 30) -> int:
    """Clean up inactive sessions older than specified days efficiently."""
    try:
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_old)
        
        # Delete old inactive sessions in small batches to avoid memory spikes
        batch_size = 100
        total_deleted = 0
        
        while True:
            # Find and delete a batch of old sessions
            old_sessions = list(user_sessions.find(
                {
                    'is_active': False,
                    'deleted_at': {'$lt': cutoff_date}
                },
                {'_id': 1}
            ).limit(batch_size))
            
            if not old_sessions:
                break
            
            session_ids = [doc['_id'] for doc in old_sessions]
            result = user_sessions.delete_many({'_id': {'$in': session_ids}})
            
            batch_deleted = result.deleted_count
            total_deleted += batch_deleted
            
            if batch_deleted < batch_size:
                break
        
        if total_deleted > 0:
            logger.info(f"Cleaned up {total_deleted} old inactive sessions")
        
        return total_deleted
        
    except Exception as e:
        logger.error(f"Error cleaning up old sessions: {e}", exc_info=True)
        return 0

# Alias for backwards compatibility
async def revoke_user_session(user_id: int) -> bool:
    """Alias for delete_user_session for backwards compatibility."""
    return await delete_user_session(user_id) 