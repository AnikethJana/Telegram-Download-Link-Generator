# StreamBot/security/middleware.py
import logging
from aiohttp import web
from .rate_limiter import web_rate_limiter
from .validator import get_client_ip

logger = logging.getLogger(__name__)

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
        """Rate limiting for download endpoints only."""
        # Only rate limit download endpoints
        if request.path.startswith('/dl/'):
            client_ip = get_client_ip(request)
            
            if not await web_rate_limiter.is_allowed(client_ip):
                logger.warning(f"Rate limit exceeded for IP {client_ip} on {request.path}")
                raise web.HTTPTooManyRequests(
                    text="Too many download requests. Please wait before trying again.",
                    headers={'Retry-After': '600'}  # 10 minutes
                )
        
        return await handler(request)
    
    @classmethod
    def get_middlewares(cls):
        """Get all security middlewares."""
        return [cls.security_headers, cls.rate_limiter] 