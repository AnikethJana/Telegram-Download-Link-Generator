import json
import asyncio
import logging
import time
import jwt
import secrets
import datetime
from collections import defaultdict, deque
from typing import Dict, Any, Optional
from aiohttp import web, ClientSession, ClientError
import aiohttp_cors
from pyrogram import Client
from pyrogram.errors import FloodWait, FileIdInvalid

from StreamBot.config import Var
from StreamBot.utils.utils import decode_message_id, humanbytes, get_file_attr
from StreamBot.utils.exceptions import NoClientsAvailableError
from StreamBot.security.validator import get_client_ip, sanitize_filename
from StreamBot.utils.bandwidth import is_bandwidth_limit_exceeded
from StreamBot.database.database import get_file_metadata, increment_download_count, store_file_metadata

logger = logging.getLogger(__name__)

# DDoS Protection - Rate limiting
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(deque)  # IP -> deque of timestamps
        self.blocked_ips = {}  # IP -> block_until_timestamp
        
    def is_rate_limited(self, ip: str) -> bool:
        """Check if IP is rate limited. Max 10 requests per minute."""
        now = time.time()
        
        # Check if IP is currently blocked
        if ip in self.blocked_ips:
            if now < self.blocked_ips[ip]:
                return True
            else:
                del self.blocked_ips[ip]
        
        # Clean old requests (older than 1 minute)
        minute_ago = now - 60
        while self.requests[ip] and self.requests[ip][0] < minute_ago:
            self.requests[ip].popleft()
        
        # Check request count
        if len(self.requests[ip]) >= 10:  # Max 10 requests per minute
            self.blocked_ips[ip] = now + 300  # Block for 5 minutes
            logger.warning(f"Rate limiting IP {ip} for 5 minutes")
            return True
        
        # Add current request
        self.requests[ip].append(now)
        return False

# Global rate limiter instance
rate_limiter = RateLimiter()

# reCAPTCHA verification
async def verify_recaptcha(response_token: str) -> bool:
    """Verify reCAPTCHA v2 response token."""
    if not response_token:
        return False
    
    # You'll need to set this in your environment variables
    secret_key = Var.RECAPTCHA_SECRET_KEY
    if not secret_key:
        logger.error("RECAPTCHA_SECRET_KEY not configured")
        return False
    
    verify_url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        'secret': secret_key,
        'response': response_token
    }
    
    try:
        async with ClientSession() as session:
            async with session.post(verify_url, data=data, timeout=10) as response:
                result = await response.json()
                return result.get('success', False)
    except (ClientError, asyncio.TimeoutError) as e:
        logger.error(f"reCAPTCHA verification failed: {e}")
        return False

# JWT Token management
def generate_download_token(encoded_id: str, client_ip: str) -> str:
    """Generate a JWT token for secure downloads."""
    payload = {
        'file_id': encoded_id,
        'client_ip': client_ip,
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=Var.JWT_EXPIRY_MINUTES),
        'jti': secrets.token_hex(16)  # Unique token ID
    }
    return jwt.encode(payload, Var.JWT_SECRET_KEY, algorithm='HS256')

def verify_download_token(token: str, client_ip: str) -> Optional[Dict[str, Any]]:
    """Verify JWT download token."""
    try:
        payload = jwt.decode(token, Var.JWT_SECRET_KEY, algorithms=['HS256'])
        
        # Verify IP address matches (optional, for extra security)
        if payload.get('client_ip') != client_ip:
            logger.warning(f"IP mismatch in download token: expected {payload.get('client_ip')}, got {client_ip}")
            # You might want to disable this check if users have dynamic IPs
            # return None
        
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Download token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid download token: {e}")
        return None

# Secure API routes
secure_routes = web.RouteTableDef()

@secure_routes.get("/api/file/{encoded_id}")
async def get_file_metadata_api(request: web.Request):
    """Get file metadata without direct download link."""
    client_ip = get_client_ip(request)
    
    # Rate limiting
    if rate_limiter.is_rate_limited(client_ip):
        logger.warning(f"Rate limited request from {client_ip}")
        raise web.HTTPTooManyRequests(
            text=json.dumps({"error": "Too many requests. Please try again later."}),
            content_type="application/json"
        )
    
    encoded_id = request.match_info['encoded_id']
    
    if not encoded_id or len(encoded_id) > 100:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "Invalid file ID"}),
            content_type="application/json"
        )
    
    # First check if metadata exists in database
    stored_metadata = await get_file_metadata(encoded_id)
    if stored_metadata:
        metadata = {
            "file_id": encoded_id,
            "file_name": stored_metadata['file_name'],
            "file_size": stored_metadata['file_size'],
            "file_size_human": humanbytes(stored_metadata['file_size']) if stored_metadata['file_size'] else "Unknown",
            "mime_type": stored_metadata['mime_type'],
            "requires_recaptcha": True,
            "download_count": stored_metadata.get('download_count', 0),
            "uploaded_on": stored_metadata['created_at'].strftime("%Y-%m-%d") if stored_metadata.get('created_at') else None
        }
        
        logger.info(f"Metadata request for {encoded_id} from {client_ip} (from database)")
        return web.Response(
            text=json.dumps(metadata, default=str),
            content_type="application/json"
        )
    
    # If not in database, fetch from Telegram and store
    message_id = decode_message_id(encoded_id)
    if message_id is None:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "Invalid or malformed file ID"}),
            content_type="application/json"
        )
    
    client_manager = request.app.get('client_manager')
    if not client_manager:
        raise web.HTTPServiceUnavailable(
            text=json.dumps({"error": "Service temporarily unavailable"}),
            content_type="application/json"
        )
    
    try:
        # Get streaming client
        streamer_client = await asyncio.wait_for(
            client_manager.get_streaming_client(),
            timeout=30
        )
        
        if not streamer_client or not streamer_client.is_connected:
            raise web.HTTPServiceUnavailable(
                text=json.dumps({"error": "Service temporarily unavailable"}),
                content_type="application/json"
            )
        
        # Get message
        media_msg = await streamer_client.get_messages(
            chat_id=Var.LOG_CHANNEL, 
            message_ids=message_id
        )
        
        if not media_msg:
            raise web.HTTPNotFound(
                text=json.dumps({"error": "File not found"}),
                content_type="application/json"
            )
        
        # Get file attributes
        file_name, file_size, mime_type = get_file_attr(media_msg)
        
        if not file_name:
            file_name = f"file_{message_id}"
        
        # Store metadata in database for future requests
        file_data = {
            'file_name': sanitize_filename(file_name),
            'file_size': file_size,
            'mime_type': mime_type or "application/octet-stream",
            'message_id': message_id
        }
        await store_file_metadata(encoded_id, file_data)
        
        # Prepare metadata response
        metadata = {
            "file_id": encoded_id,
            "file_name": sanitize_filename(file_name),
            "file_size": file_size,
            "file_size_human": humanbytes(file_size) if file_size else "Unknown",
            "mime_type": mime_type or "application/octet-stream",
            "requires_recaptcha": True,
            "download_count": 0,
            "uploaded_on": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        
        logger.info(f"Metadata request for {message_id} from {client_ip} (from Telegram)")
        
        return web.Response(
            text=json.dumps(metadata),
            content_type="application/json"
        )
        
    except FloodWait as e:
        raise web.HTTPTooManyRequests(
            text=json.dumps({"error": f"Rate limited. Try again in {e.value} seconds"}),
            content_type="application/json"
        )
    except FileIdInvalid:
        raise web.HTTPNotFound(
            text=json.dumps({"error": "File not found or deleted"}),
            content_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error getting metadata for {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "Internal server error"}),
            content_type="application/json"
        )

@secure_routes.post("/api/download/{encoded_id}")
async def secure_download(request: web.Request):
    """Handle secure download with reCAPTCHA verification."""
    client_ip = get_client_ip(request)
    
    # Rate limiting
    if rate_limiter.is_rate_limited(client_ip):
        logger.warning(f"Rate limited download request from {client_ip}")
        raise web.HTTPTooManyRequests(
            text=json.dumps({"error": "Too many requests. Please try again later."}),
            content_type="application/json"
        )
    
    encoded_id = request.match_info['encoded_id']
    
    try:
        # Parse request body
        request_data = await request.json()
        recaptcha_response = request_data.get('recaptcha_response')
        
        if not recaptcha_response:
        raise web.HTTPBadRequest(
                text=json.dumps({"error": "reCAPTCHA response required"}),
            content_type="application/json"
        )
    
    # Verify reCAPTCHA
    if not await verify_recaptcha(recaptcha_response):
            raise web.HTTPBadRequest(
            text=json.dumps({"error": "reCAPTCHA verification failed"}),
            content_type="application/json"
        )
    
        # Generate secure download token
        download_token = generate_download_token(encoded_id, client_ip)
        
        # Increment download count
        await increment_download_count(encoded_id)
        
        # Return the download URL with token
        download_url = f"{Var.BASE_URL}/secure-dl/{encoded_id}?token={download_token}"
        
        logger.info(f"Secure download token generated for {encoded_id} from {client_ip}")
        
        return web.Response(
            text=json.dumps({
                "success": True,
                "download_url": download_url,
                "expires_in_minutes": Var.JWT_EXPIRY_MINUTES
            }),
            content_type="application/json"
        )
    
    except web.HTTPBadRequest as e:
        raise e
    except Exception as e:
        logger.error(f"Error in secure download for {encoded_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "Internal server error"}),
            content_type="application/json"
        )
    
@secure_routes.get("/secure-dl/{encoded_id}")
async def token_download(request: web.Request):
    """Handle token-based download."""
    client_ip = get_client_ip(request)
    encoded_id = request.match_info['encoded_id']
    token = request.query.get('token')
    
    if not token:
        raise web.HTTPBadRequest(text="Download token required")
    
    # Verify token
    token_data = verify_download_token(token, client_ip)
    if not token_data:
        raise web.HTTPUnauthorized(text="Invalid or expired download token")
    
    # Verify token matches the file ID
    if token_data.get('file_id') != encoded_id:
        raise web.HTTPUnauthorized(text="Token does not match file ID")
    
    # Check bandwidth limit
    if await is_bandwidth_limit_exceeded():
        logger.warning(f"Token download request {encoded_id} rejected: bandwidth limit exceeded")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable due to bandwidth limits.")
    
    # Proceed with actual download - redirect to existing download route
    # This maintains all the existing streaming logic
    download_url = f"{Var.BASE_URL}/dl/{encoded_id}"
    
    logger.info(f"Token download authenticated for {encoded_id} from {client_ip}")
    raise web.HTTPFound(location=download_url)

@secure_routes.options("/{path:.*}")
async def options_handler(request: web.Request):
    """Handle CORS preflight requests."""
    origin = request.headers.get('Origin')
    allowed_origins = [origin.strip() for origin in Var.CORS_ALLOWED_ORIGINS.split(',')]
    
    # Check if origin is allowed
    if origin in allowed_origins:
    return web.Response(headers={
            'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400'
    })
    else:
        logger.warning(f"CORS request from unauthorized origin: {origin}")
        return web.Response(status=403, text="Origin not allowed")

def setup_secure_api(app: web.Application):
    """Set up the secure API with CORS."""
    # Add routes
    app.add_routes(secure_routes)
    
    # Parse allowed origins
    allowed_origins = [origin.strip() for origin in Var.CORS_ALLOWED_ORIGINS.split(',')]
    
    # Configure CORS with specific allowed origins
    cors_config = {}
    for origin in allowed_origins:
        cors_config[origin] = aiohttp_cors.ResourceOptions(
            allow_credentials=False,
            expose_headers=["Content-Length", "Content-Range", "Accept-Ranges"],
            allow_headers=["Content-Type", "Authorization", "Range"],
            allow_methods=["GET", "POST", "HEAD", "OPTIONS"]
        )
    
    # Setup CORS with specific origins
    cors = aiohttp_cors.setup(app, defaults=cors_config)
    
    # Add CORS to all routes
    for route in list(app.router.routes()):
        if hasattr(route, 'resource'):
            cors.add(route.resource)
    
    logger.info(f"Secure API initialized with CORS for origins: {allowed_origins}")
    return app 