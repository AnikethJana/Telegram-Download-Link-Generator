# StreamBot/security/validator.py
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RequestValidator:
    """Request validation and sanitization utilities."""
    
    @staticmethod
    def validate_range_header(range_header: str, file_size: int) -> Optional[tuple]:
        """Validate and parse Range header safely."""
        if not range_header or not isinstance(range_header, str):
            return None
        
        # Basic format validation
        if not re.match(r'^bytes=\d*-\d*$', range_header):
            return None
        
        try:
            range_match = re.match(r'bytes=(\d+)?-(\d+)?', range_header)
            if not range_match:
                return None
            
            start_str, end_str = range_match.groups()
            
            # Validate ranges
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            
            # Security checks
            if start < 0 or end < 0:
                return None
            if start >= file_size or end >= file_size:
                return None
            if start > end:
                return None
            
            return (start, end)
        
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        if not filename or not isinstance(filename, str):
            return "download"
        
        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        sanitized = sanitized.strip('. ')
        
        # Limit length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
        
        return sanitized or "download"


def get_client_ip(request) -> str:
    """Get client IP safely."""
    # Check for forwarded headers (common in reverse proxies)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take first IP in case of multiple
        return forwarded_for.split(',')[0].strip()
    
    return request.remote or '127.0.0.1'


# Convenience functions for backward compatibility
validate_range_header = RequestValidator.validate_range_header
sanitize_filename = RequestValidator.sanitize_filename 