# StreamBot/security/middleware.py
import logging
import re # Import re for extracting encoded_id
from aiohttp import web
from .rate_limiter import web_rate_limiter
from .validator import get_client_ip

logger = logging.getLogger(__name__)

# Pre-compile regex for extracting encoded_id from /dl/ path
# This will match /dl/ followed by any characters until the end or a query string
DL_PATH_REGEX = re.compile(r"^/dl/([^/?]+)")

class SecurityMiddleware:
    """Consolidated security middleware for aiohttp."""
    
    @staticmethod
    @web.middleware
    async def security_headers(request, handler):
        """Add essential security headers to responses."""
        response = await handler(request)
        
        # Only add essential headers to minimize overhead
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        
        # Only add CSP for HTML responses (reduces header size for downloads)
        if response.content_type and 'text/html' in response.content_type:
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
    
    @staticmethod
    @web.middleware
    async def rate_limiter(request, handler):
        """Rate limiting for download endpoints only, now with encoded_id awareness."""
        # Only rate limit download endpoints
        if request.path.startswith('/dl/'):
            client_ip = get_client_ip(request)
            encoded_id = None
            
            # Extract encoded_id from the path
            match = DL_PATH_REGEX.match(request.path)
            if match:
                encoded_id = match.group(1)
            
            if not await web_rate_limiter.is_allowed(client_ip, encoded_id=encoded_id):
                # Log which ID was involved if available
                id_info = f" (file: {encoded_id})" if encoded_id else ""
                logger.warning(f"Rate limit exceeded for IP {client_ip} on {request.path}{id_info}")
                raise web.HTTPTooManyRequests(
                    text="Too many download requests. Please wait before trying again.",
                    headers={'Retry-After': str(web_rate_limiter.main_window_seconds)} # Use the main window as retry-after
                )
        
        return await handler(request)
    
    @classmethod
    def get_middlewares(cls):
        """Get all security middlewares."""
        return [cls.security_headers, cls.rate_limiter] 