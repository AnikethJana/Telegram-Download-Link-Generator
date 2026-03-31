# StreamBot/security/middleware.py
import logging
from aiohttp import web

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
            # More permissive CSP for session generator pages
            if request.path.startswith('/session'):
                # Allow external resources needed for session generator (Telegram Login Widget)
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://telegram.org https://oauth.telegram.org https://cdnjs.cloudflare.com; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
                    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
                    "frame-src https://oauth.telegram.org https://telegram.org https://t.me; "
                    "connect-src 'self' https://oauth.telegram.org; "
                    "img-src 'self' data: https:; "
                )
            elif request.path.startswith('/owner/dashboard'):
                # Owner dashboard uses inline script/style, Chart.js CDN, and Google Fonts.
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "connect-src 'self'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self' data: https://fonts.gstatic.com; "
                )
            elif request.path.startswith('/dl/'):
                # Download landing pages use inline styles only.
                csp = (
                    "default-src 'self'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "connect-src 'self'; "
                )
            else:
                # Strict CSP for other pages
                csp = "default-src 'self'"
            
            response.headers['Content-Security-Policy'] = csp
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'no-referrer'
            
            # Prevent caching of sensitive dashboard and session pages
            if request.path.startswith('/owner/dashboard') or request.path.startswith('/session'):
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
        
        return response
    
    @classmethod
    def get_middlewares(cls):
        """Get all security middlewares."""
        return [cls.security_headers]