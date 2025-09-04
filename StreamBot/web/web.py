# StreamBot/web.py
import re
import logging
import asyncio
import datetime
import os
import math
from aiohttp import web
import aiohttp_cors
import jinja2
from pyrogram import Client
from pyrogram.errors import FloodWait, FileIdInvalid, RPCError
from pyrogram.types import Message, User
import aiohttp_jinja2
from StreamBot.config import Var
# Ensure decode_message_id is imported from utils
from StreamBot.utils.utils import get_file_attr, humanbytes, decode_message_id, get_media_message
from StreamBot.utils.file_properties import parse_file_id
from StreamBot.utils.exceptions import NoClientsAvailableError # Import custom exception
from StreamBot.utils.bandwidth import is_bandwidth_limit_exceeded, add_bandwidth_usage
from StreamBot.utils.stream_cleanup import stream_tracker, tracked_stream_response
from StreamBot.security.middleware import SecurityMiddleware
from StreamBot.security.validator import validate_range_header, sanitize_filename, get_client_ip
from StreamBot.utils.custom_dl import ByteStreamer
from .streaming import stream_video_route
from ..utils.stream_cleanup import stream_tracker, tracked_stream_response
from ..utils.bandwidth import is_bandwidth_limit_exceeded, add_bandwidth_usage
from ..utils.exceptions import NoClientsAvailableError
from ..session_generator.interactive_login import interactive_login_manager
from .auth_cookies import set_auth_cookies, clear_auth_cookies, get_session_token

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# Favicon route to prevent 404 errors
@routes.get("/favicon.ico")
async def favicon_route(request: web.Request):
    """Serve a simple favicon to prevent 404 errors."""
    # Return a simple transparent 1x1 PNG as ICO
    favicon_data = b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x00\x00\x00\x00(\x00\x00\x00\x16\x00\x00\x00(\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00'
    return web.Response(body=favicon_data, content_type='image/x-icon')

# User session streaming is now integrated into the main download route

# Helper function to check session generator access permissions
def generate_session_token(user_id: int) -> str:
    """Generate a secure session token for user authentication."""
    import secrets
    import hashlib
    import time

    # Create a unique token with timestamp and random data
    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(16)
    token_data = f"{user_id}:{timestamp}:{random_data}"

    # Hash the token for security
    token_hash = hashlib.sha256(token_data.encode()).hexdigest()

    # Store token mapping (in production, use Redis or database)
    # For now, we'll store in a simple in-memory dict
    if not hasattr(generate_session_token, '_token_store'):
        generate_session_token._token_store = {}
        # Start cleanup task for expired tokens
        asyncio.create_task(cleanup_expired_tokens())

    # Clean up expired tokens before adding new one
    current_time = int(time.time())
    expired_tokens = [
        token for token, data in generate_session_token._token_store.items()
        if current_time > int(data['expires_at'])
    ]
    for token in expired_tokens:
        del generate_session_token._token_store[token]

    generate_session_token._token_store[token_hash] = {
        'user_id': user_id,
        'created_at': timestamp,
        'expires_at': str(int(time.time()) + 3600)  # 1 hour expiry
    }

    return token_hash

async def cleanup_expired_tokens():
    """Periodically clean up expired session tokens."""
    while True:
        try:
            await asyncio.sleep(300)  # Clean up every 5 minutes

            if hasattr(generate_session_token, '_token_store'):
                current_time = int(datetime.datetime.now().timestamp())
                expired_tokens = [
                    token for token, data in generate_session_token._token_store.items()
                    if current_time > int(data['expires_at'])
                ]
                for token in expired_tokens:
                    del generate_session_token._token_store[token]

                if expired_tokens:
                    logger.debug(f"Cleaned up {len(expired_tokens)} expired session tokens")

        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying

async def validate_session_token(token: str) -> int | None:
    """Validate session token and return user_id if valid."""
    import time

    if not hasattr(generate_session_token, '_token_store'):
        return None

    token_data = generate_session_token._token_store.get(token)
    if not token_data:
        return None

    # Check if token has expired
    current_time = int(time.time())
    if current_time > int(token_data['expires_at']):
        # Remove expired token
        del generate_session_token._token_store[token]
        return None

    return token_data['user_id']

def check_session_generator_access(user_id: int) -> bool:
    """Check if user has permission to access session generator features."""
    # If ALLOW_USER_LOGIN is True, everyone can access
    if Var.ALLOW_USER_LOGIN:
        return True
    
    # If ALLOW_USER_LOGIN is False, only admins can access
    if Var.ADMINS and user_id in Var.ADMINS:
        return True
    
    return False

# Request timeout for streaming operations (2 hours max)
STREAM_TIMEOUT = 7200  # 2 hours

# --- Helper: Format Uptime 
def format_uptime(start_time_dt: datetime.datetime) -> str:
    """Format the uptime into a human-readable string."""
    if start_time_dt is None:
        return "N/A"
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - start_time_dt
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    uptime_str = ""
    if days > 0:
        uptime_str += f"{days}d "
    if hours > 0:
        uptime_str += f"{hours}h "
    if minutes > 0:
        uptime_str += f"{minutes}m "
    uptime_str += f"{seconds}s"
    return uptime_str.strip() if uptime_str else "0s"

# get_media_message function moved to utils.py to avoid circular imports

# --- Download Route (Fixed streaming error) ---
@routes.get("/dl/{encoded_id_str}")
async def download_route(request: web.Request):
    """Handle file download requests with range support."""
    client_manager = request.app.get('client_manager')
    if not client_manager:
        logger.error("ClientManager not found in web app state.")
        raise web.HTTPServiceUnavailable(text="Service configuration error.")

    start_time_request = asyncio.get_event_loop().time()

    encoded_id = request.match_info['encoded_id_str']
    
    # Enhanced input validation
    if not encoded_id or len(encoded_id) > 100:  # Reasonable length limit
        logger.warning(f"Invalid encoded ID format from {get_client_ip(request)}: {encoded_id[:50]}...")
        raise web.HTTPBadRequest(text="Invalid download link format.")
    
    message_id = decode_message_id(encoded_id)

    if message_id is None:
        logger.warning(f"Download request with invalid or undecodable ID: {encoded_id[:50]} from {get_client_ip(request)}")
        raise web.HTTPBadRequest(text="Invalid or malformed download link.")

    logger.info(f"Download request for decoded message_id: {message_id} (encoded: {encoded_id[:20]}...) from {get_client_ip(request)}")

    # Check bandwidth limit before processing
    if await is_bandwidth_limit_exceeded():
        logger.warning(f"Download request {message_id} rejected: bandwidth limit exceeded")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable due to bandwidth limits.")

    try:
        # Check if this is a user session file (virtual message ID)
        is_user_session = isinstance(message_id, str) and message_id.startswith('user_')
        if is_user_session:
            # Handle user session file - anyone with the link can download
            # This is intentional: users can share their generated links with others
            bot_client = request.app['bot_client']
            if not hasattr(bot_client, 'user_session_files') or message_id not in bot_client.user_session_files:
                raise web.HTTPNotFound(text="File not found or expired.")
            
            session_info = bot_client.user_session_files[message_id]
            
            # Check if expired (24 hours)
            current_time = asyncio.get_event_loop().time()
            if current_time - session_info['created_at'] > 86400:
                del bot_client.user_session_files[message_id]
                raise web.HTTPGone(text="Download link has expired.")
            
            # Get user's client for streaming
            from StreamBot.link_handler import user_session_streamer
            user_client = await user_session_streamer.get_user_client(session_info['user_id'])
            if not user_client:
                raise web.HTTPUnauthorized(text="User session expired. Please login again.")
            
            # Get the actual message from user's session
            media_msg = await user_client.get_messages(
                chat_id=session_info['chat_id'], 
                message_ids=session_info['message_id']
            )
            if not media_msg or not media_msg.media:
                raise web.HTTPNotFound(text="File not found or no longer available.")
            
            # Use user's client for streaming
            streamer_client = user_client
            logger.debug(f"Using user session client for streaming user file: {message_id}")
            # Create a ByteStreamer for the user's client (not managed by ClientManager)
            byte_streamer = ByteStreamer(streamer_client)
            
        else:
            # Handle regular forwarded file
            # Add timeout to prevent hanging requests - increased for large file support
            streamer_client = await asyncio.wait_for(
                client_manager.get_streaming_client(),
                timeout=60  # Increased from 30 to 60 seconds for large file handling
            )
            if not streamer_client or not getattr(streamer_client, "is_connected", False):
                logger.error(f"Failed to obtain a connected streaming client for message_id {message_id}")
                raise web.HTTPServiceUnavailable(text="Service temporarily overloaded. Please try again shortly.")
            logger.debug(f"Using client @{streamer_client.me.username} for streaming message_id {message_id}")
            # Fetch the media message from the log channel using bot/worker client
            media_msg = await get_media_message(streamer_client, message_id)
            # Get ByteStreamer instance for the client from ClientManager
            byte_streamer = client_manager.get_streamer_for_client(streamer_client)
            if not byte_streamer:
                logger.error(f"No ByteStreamer found for client @{streamer_client.me.username}")
                raise web.HTTPInternalServerError(text="Streaming service not available.")
    except asyncio.TimeoutError:
        logger.error(f"Timeout getting streaming client for message_id {message_id}")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable.")
    except (web.HTTPNotFound, web.HTTPServiceUnavailable, web.HTTPTooManyRequests, web.HTTPGone, web.HTTPInternalServerError) as e:
        logger.warning(f"Error during get_media_message for {message_id}: {type(e).__name__}")
        raise e
    except NoClientsAvailableError as e:
        logger.error(f"No clients available for streaming message_id {message_id}: {e}")
        raise web.HTTPServiceUnavailable(text="Service temporarily overloaded. Please try again later.")
    except Exception as e: # Catch any other unexpected error from get_media_message
        logger.error(f"Unexpected error from get_media_message for {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Internal server error occurred.")

    # Use ByteStreamer to get file properties (similar to WebStreamer approach)
    try:
        if is_user_session:
            # For user session files, derive FileId directly from the fetched message
            file_id = await parse_file_id(media_msg)
            if not file_id:
                raise FileNotFoundError("Unable to parse file id from user session message")
        else:
            # For regular files in log channel, get properties by message_id
            file_id = await byte_streamer.get_file_properties(message_id)
    except FileNotFoundError:
        logger.error(f"File properties not found for message {message_id}")
        raise web.HTTPNotFound(text="File not found or has been deleted.")
    except Exception as e:
        logger.error(f"Error getting file properties for message {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Failed to get file details.")

    # Extract file information using get_file_attr (proper filename handling)
    file_id_str, file_name, file_size, file_mime_type, file_unique_id = get_file_attr(media_msg)

    if not file_name:
        logger.warning(f"No filename could be determined for message {message_id}")
        file_name = f"file_{message_id}"

    # Sanitize filename for security
    safe_filename = sanitize_filename(file_name)

    # Validate file size
    if file_size == 0:
        logger.warning(f"File size is 0 for message {message_id}")
        # Don't raise error, let it proceed for 0-byte files


    headers = {
        'Content-Type': file_mime_type or 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{safe_filename}"',
        'Accept-Ranges': 'bytes'
    }

    range_header = request.headers.get('Range')
    status_code = 200
    start_offset = 0
    end_offset = file_size - 1 if file_size > 0 else 0 # Handle 0-byte files for end_offset
    is_range_request = False

    if range_header:
        logger.info(f"Range header for {message_id}: '{range_header}', File size: {humanbytes(file_size)}")
        
        # Use secure range validation
        range_result = validate_range_header(range_header, file_size)
        if range_result is None:
            logger.error(f"Invalid Range header '{range_header}' for file size {file_size}")
            raise web.HTTPRequestRangeNotSatisfiable(headers={'Content-Range': f'bytes */{file_size}'})
        
        start_offset, end_offset = range_result
        headers['Content-Range'] = f'bytes {start_offset}-{end_offset}/{file_size}'
        headers['Content-Length'] = str(end_offset - start_offset + 1)
        status_code = 206
        is_range_request = True
        logger.info(f"Serving range request for {message_id}: bytes {start_offset}-{end_offset}/{file_size}. Content-Length: {headers['Content-Length']}")

    else:
        headers['Content-Length'] = str(file_size)
        logger.info(f"Serving full download for {message_id}. File size: {humanbytes(file_size)}. Content-Length: {headers['Content-Length']}")

    response = web.StreamResponse(status=status_code, headers=headers)
    await response.prepare(request)

    bytes_streamed = 0
    stream_start_time = asyncio.get_event_loop().time()
    max_retries_stream = 2
    current_retry_stream = 0



    # Handle 0-byte file case: if length is 0, don't try to stream.
    if (end_offset - start_offset + 1) == 0 and file_size == 0 and status_code in [200, 206]:
        logger.info(f"Serving 0-byte file {message_id}. No data to stream.")
        # Response already prepared with Content-Length: 0. Just return.
        return response

    # Calculate streaming parameters based on WebStreamer approach
    chunk_size = 1024 * 1024  # 1MB chunks
    until_bytes = min(end_offset, file_size - 1)
    offset = start_offset - (start_offset % chunk_size)
    first_part_cut = start_offset - offset
    last_part_cut = until_bytes % chunk_size + 1
    part_count = math.ceil((until_bytes + 1) / chunk_size) - math.floor(offset / chunk_size)

    logger.debug(f"Preparing WebStreamer-style streaming for {message_id}. Range: {start_offset}-{end_offset}, Offset: {offset}, Parts: {part_count}")

    # Use stream tracking context manager for proper cleanup
    request_id = f"{message_id}_{encoded_id[:10]}"
    async with tracked_stream_response(response, stream_tracker, request_id):
        while current_retry_stream <= max_retries_stream:
            try:
                # Use WebStreamer-style streaming with ByteStreamer
                try:
                    # Create the streaming coroutine using ByteStreamer
                    async def stream_data():
                        async for chunk in byte_streamer.yield_file(
                            file_id,
                            offset,
                            first_part_cut,
                            last_part_cut,
                            part_count,
                            chunk_size
                        ):
                            try:
                                await response.write(chunk)
                                nonlocal bytes_streamed
                                bytes_streamed += len(chunk)
                            except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError) as client_e:
                                logger.warning(f"Client connection issue during write for {message_id}: {type(client_e).__name__}. Streamed {humanbytes(bytes_streamed)}.")
                                return
                            except Exception as write_e:
                                logger.error(f"Error writing chunk for {message_id}: {write_e}", exc_info=True)
                                return
                    
                    # Apply timeout to the entire streaming operation
                    await asyncio.wait_for(stream_data(), timeout=STREAM_TIMEOUT)
                    
                except asyncio.TimeoutError:
                    logger.error(f"Stream timeout for {message_id} after {STREAM_TIMEOUT}s")
                    if bytes_streamed == 0:
                        raise web.HTTPGatewayTimeout(text="Request timeout. Please try again.")
                    break

                logger.info(f"Successfully finished WebStreamer-style streaming for {message_id}.")
                break # Exit retry loop on successful completion

            except FloodWait as e:
                 logger.warning(f"FloodWait during stream for {message_id} on client @{streamer_client.me.username}. FloodWait: {e.value}s. Attempting to get alternative client...")
                 
                 # Try to get a different client instead of waiting
                 try:
                     alternative_client = await client_manager.get_alternative_streaming_client(streamer_client)
                     if alternative_client:
                         logger.info(f"Switching from @{streamer_client.me.username} to @{alternative_client.me.username} for {message_id} due to FloodWait")
                         streamer_client = alternative_client
                         # Update ByteStreamer instance
                         byte_streamer = client_manager.get_streamer_for_client(streamer_client)
                         if not byte_streamer:
                             logger.error(f"No ByteStreamer found for alternative client @{streamer_client.me.username}")
                             break
                         # Small delay to avoid rapid switching
                         await asyncio.sleep(1)
                     else:
                         logger.warning(f"No alternative clients available for {message_id}. Waiting {e.value}s for FloodWait on @{streamer_client.me.username}")
                         await asyncio.sleep(e.value + 2)
                 except Exception as client_e:
                     logger.warning(f"Error getting alternative client for {message_id}: {client_e}. Falling back to waiting.")
                     await asyncio.sleep(e.value + 2)
                 
                 # Continue to the next iteration of the while loop (retry with potentially different client)

            except (ConnectionError, TimeoutError, RPCError) as e: # Catches other RPC errors
                 current_retry_stream += 1
                 logger.warning(f"Stream interrupted for {message_id} (Attempt {current_retry_stream}/{max_retries_stream+1}): {type(e).__name__}")
                 if current_retry_stream > max_retries_stream:
                      logger.error(f"Max retries reached for stream error. Aborting stream for {message_id} after {humanbytes(bytes_streamed)} bytes.")
                      break
                 await asyncio.sleep(2 * current_retry_stream)
                 logger.info(f"Retrying stream for {message_id} from offset {start_offset}.")
            except Exception as e:
                 logger.error(f"Unexpected error during WebStreamer-style streaming for {message_id}: {e}", exc_info=True)
                 return response

    stream_duration = asyncio.get_event_loop().time() - stream_start_time
    expected_bytes_to_serve = (end_offset - start_offset + 1)

    # Always record bandwidth for bytes actually streamed, if any
    if bytes_streamed > 0:
        await add_bandwidth_usage(bytes_streamed)
        logger.info(f"Recorded {humanbytes(bytes_streamed)} for bandwidth usage for {message_id}.")

    if bytes_streamed == expected_bytes_to_serve:
        logger.info(f"Finished streaming {humanbytes(bytes_streamed)} for {message_id} in {stream_duration:.2f}s. Expected: {humanbytes(expected_bytes_to_serve)}.")
    else:
        logger.warning(f"Stream for {message_id} ended. Expected to serve {humanbytes(expected_bytes_to_serve)}, actually sent {humanbytes(bytes_streamed)} in {stream_duration:.2f}s.")

    total_request_duration = asyncio.get_event_loop().time() - start_time_request
    logger.info(f"Download request for {message_id} completed. Total duration: {total_request_duration:.2f}s")
    return response


# --- API Info Route --- (Keep as is, assuming it's working)
@routes.get("/api/info")
async def api_info_route(request: web.Request):
    """Provides bot status and information via API."""
    bot_client: Client = request.app.get('bot_client')
    # Backward-compatible: support both 'start_time' and 'bot_start_time'
    start_time = request.app.get('start_time') or request.app.get('bot_start_time')
    if start_time is None:
        try:
            # Fallback to global if available
            from StreamBot.__main__ import BOT_START_TIME  # type: ignore
            start_time = BOT_START_TIME
        except Exception:
            start_time = None
    user_count = 0
    try:
        from StreamBot.database.database import total_users_count # Assuming this exists
        user_count = await total_users_count()
    except Exception as e:
         logger.error(f"Failed to get total user count for API info: {e}")

    # Get bandwidth usage information
    bandwidth_info = {}
    try:
        from StreamBot.utils.bandwidth import get_current_bandwidth_usage
        bandwidth_usage = await get_current_bandwidth_usage()
        bandwidth_info = {
            "limit_gb": Var.BANDWIDTH_LIMIT_GB,
            "used_gb": bandwidth_usage["gb_used"],
            "used_bytes": bandwidth_usage["bytes_used"],
            "month": bandwidth_usage["month_key"],
            "limit_enabled": Var.BANDWIDTH_LIMIT_GB > 0,
            "remaining_gb": max(0, Var.BANDWIDTH_LIMIT_GB - bandwidth_usage["gb_used"]) if Var.BANDWIDTH_LIMIT_GB > 0 else None
        }
    except Exception as e:
        logger.error(f"Failed to get bandwidth info for API: {e}")
        bandwidth_info = {"limit_enabled": False, "error": "Failed to retrieve bandwidth data"}

    if not bot_client or not bot_client.is_connected:
        return web.json_response({
            "status": "error", "bot_status": "disconnected",
            "message": "Bot service is not currently available.",
            "uptime": format_uptime(start_time), "github_repo": Var.GITHUB_REPO_URL,
            "totaluser": user_count,
            "bandwidth_info": bandwidth_info
        }, status=503)

    try:
        bot_me: User = getattr(bot_client, 'me', None)
        if not bot_me: 
            bot_me = await bot_client.get_me()
            setattr(bot_client, 'me', bot_me)

        features = {
             "force_subscribe": bool(Var.FORCE_SUB_CHANNEL),
             "force_subscribe_channel_id": Var.FORCE_SUB_CHANNEL if Var.FORCE_SUB_CHANNEL else None, # Use different key
             "link_expiry_enabled": Var.LINK_EXPIRY_SECONDS > 0,
             "link_expiry_duration_seconds": Var.LINK_EXPIRY_SECONDS,
             "link_expiry_duration_human": Var._human_readable_duration(Var.LINK_EXPIRY_SECONDS)
        }
        info_data = {
            "status": "ok", "bot_status": "connected",
            "bot_info": {"id": bot_me.id, "username": bot_me.username, "first_name": bot_me.first_name, "mention": bot_me.mention},
            "features": features, "uptime": format_uptime(start_time),
            "github_repo": Var.GITHUB_REPO_URL,
            "server_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "totaluser": user_count,
            "bandwidth_info": bandwidth_info
        }
        return web.json_response(info_data)
    except Exception as e:
        logger.error(f"Error fetching bot info for API: {e}", exc_info=True)
        return web.json_response({
            "status": "error", "bot_status": "unknown",
            "message": "Service temporarily unavailable.",
            "uptime": format_uptime(start_time), "github_repo": Var.GITHUB_REPO_URL,
            "totaluser": user_count,
            "bandwidth_info": bandwidth_info
        }, status=500)

# --- Setup Web App ---
async def setup_webapp(bot_instance: Client, client_manager, start_time: datetime.datetime):
    # Create app with security middleware
    app = web.Application(middlewares=SecurityMiddleware.get_middlewares())

    # Store bot instance and client manager
    app['bot_client'] = bot_instance
    app['client_manager'] = client_manager
    # Store both keys for compatibility with existing code paths
    app['bot_start_time'] = start_time
    app['start_time'] = start_time
    
    # Add routes
    app.add_routes(routes)
    
    # Configure CORS
    if Var.CORS_ALLOWED_ORIGINS:
        logger.info(f"CORS enabled for origins: {Var.CORS_ALLOWED_ORIGINS}")
        cors = aiohttp_cors.setup(app, defaults={
            origin: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS"],
            ) for origin in Var.CORS_ALLOWED_ORIGINS
        })
        for route in list(app.router.routes()):
            cors.add(route)
    else:
        logger.warning("CORS_ALLOWED_ORIGINS is not set. The Telegram login widget may not work on external domains.")

    # Setup Jinja2 templates
    template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../session_generator/templates")
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_path))

    # Setup static files for session generator with caching
    static_path = os.path.join(os.path.dirname(__file__), '..', 'session_generator', 'static')
    if os.path.exists(static_path):
        app.router.add_static(
            '/session/static',
            static_path,
            name='session_static',
            show_index=False,  # Security: don't show directory listings
            follow_symlinks=False  # Security: don't follow symlinks
        )
        logger.info(f"Static files configured for session generator at: {static_path}")
    
    logger.info("Web application routes configured with security middleware.")
    return app

# Add these routes after the existing routes
@routes.get("/stream/{encoded_id_str}")
async def stream_route(request: web.Request):
    """Route handler for video streaming."""
    return await stream_video_route(request)

# --- Session Generator Routes ---
@routes.get("/session")
async def session_generator_route(request: web.Request):
    """Session generator main page route."""
    from aiohttp_jinja2 import render_template
    
    bot_client: Client = request.app['bot_client']
    
    # If already authenticated via cookie and has session, go to success page
    try:
        session_token = get_session_token(request)
        if session_token:
            user_id = await validate_session_token(session_token)
            if user_id:
                from StreamBot.database.user_sessions import get_user_session_info
                user_info = await get_user_session_info(user_id)
                if user_info:
                    return web.HTTPFound('/session/success')
    except Exception:
        pass
    
    # Get bot username for Telegram Login Widget
    bot_username = None
    bot_id = None
    try:
        if bot_client and hasattr(bot_client, 'me') and bot_client.me:
            bot_username = bot_client.me.username
            bot_id = bot_client.me.id
    except Exception as e:
        logger.warning(f"Could not get bot info for session generator: {e}")
    
    context = {
        'bot_username': bot_username,
        'bot_id': bot_id,
        'base_url': Var.BASE_URL,
        'app_name': 'Telegram Session Generator',
        'allow_user_login': Var.ALLOW_USER_LOGIN,
        'login_restricted': not Var.ALLOW_USER_LOGIN
    }
    
    return render_template('index.html', request, context)

#l Slupport trailing slash by redirecting to canonical path
@routes.get("/session/")
async def session_generator_route_slash(request: web.Request):
    return web.HTTPFound('/session')

@routes.get("/session/login")
async def session_login_route(request: web.Request):
    """Route to display the interactive login form."""
    from aiohttp_jinja2 import render_template
    
    # If already authenticated via cookie and has session, go to success page
    try:
        session_token_cookie = get_session_token(request)
        if session_token_cookie:
            cookie_user_id = await validate_session_token(session_token_cookie)
            if cookie_user_id:
                from StreamBot.database.user_sessions import get_user_session_info
                if await get_user_session_info(cookie_user_id):
                    return web.HTTPFound('/session/success')
    except Exception:
        pass

    token = request.query.get('token')
    user_id = await validate_session_token(token)
    
    if not user_id:
        return web.HTTPFound('/session?error=invalid_token')
        
    context = {
        'token': token,
        'user_id': user_id
    }
    return render_template('login.html', request, context)

@routes.post("/session/send_code")
async def session_send_code_route(request: web.Request):
    """Handle API credentials and phone number submission to send verification code."""
    data = await request.json()
    token = data.get('token')
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    phone_number = data.get('phone_number')
    proxy_username = data.get('proxy_username')
    proxy_password = data.get('proxy_password')
    
    user_id = await validate_session_token(token)
    if not user_id:
        return web.json_response({'status': 'error', 'message': 'Invalid or expired session.'}, status=401)
    
    # Validate input
    if not api_id or not api_hash or not phone_number:
        return web.json_response({'status': 'error', 'message': 'API ID, API Hash, and phone number are required.'}, status=400)
    
    try:
        api_id = int(api_id)
    except (ValueError, TypeError):
        return web.json_response({'status': 'error', 'message': 'Invalid API ID format.'}, status=400)
    
    try:
        result = await interactive_login_manager.start_login(
            user_id, api_id, api_hash, phone_number, proxy_username, proxy_password
        )
        return web.json_response(result)
    except Exception as e:
        logger.error(f"Error in send_code route: {e}")
        return web.json_response({'status': 'error', 'message': 'An error occurred. Please try again.'}, status=500)

@routes.post("/session/submit_code")
async def session_submit_code_route(request: web.Request):
    """Handle verification code submission."""
    data = await request.json()
    token = data.get('token')
    phone_number = data.get('phone_number')
    phone_code_hash = data.get('phone_code_hash')
    code = data.get('code')

    user_id = await validate_session_token(token)
    if not user_id:
        return web.json_response({'status': 'error', 'message': 'Invalid or expired session.'}, status=401)
        
    try:
        result = await asyncio.wait_for(
            interactive_login_manager.submit_code(user_id, phone_number, phone_code_hash, code),
            timeout=35
        )
    except asyncio.TimeoutError:
        try:
            await interactive_login_manager.cleanup_client(user_id)
        except Exception:
            pass
        return web.json_response({'status': 'timeout', 'message': 'Verification timed out. Please request a new code.'}, status=504)
    
    if result.get('status') == 'success':
        # SECURITY: Verify that the logged-in user matches the widget user
        logged_in_user_info = result.get('user_info')
        if not logged_in_user_info or logged_in_user_info.get('id') != user_id:
            await interactive_login_manager.cleanup_client(user_id)
            return web.json_response({
                'status': 'error', 
                'message': 'Account mismatch. The logged-in account does not match the widget account.'
            }, status=400)

        # Store the session and clean up
        from StreamBot.database.user_sessions import store_user_session
        session_stored = await store_user_session(user_id, result['session_string'], logged_in_user_info)
        await interactive_login_manager.cleanup_client(user_id)
        
        if not session_stored:
            logger.error(f"Failed to store session for user {user_id}")
            return web.json_response({
                'status': 'error', 
                'message': 'Failed to store session. Please try again.'
            }, status=500)

        # Notify user via bot DM (non-blocking best-effort)
        try:
            from StreamBot.session_generator.session_manager import session_manager
            asyncio.create_task(session_manager.notify_bot_about_new_session(user_id, logged_in_user_info))
        except Exception as _e:
            logger.debug(f"Notify bot about new session failed for {user_id}: {_e}")

        # Prepare redirect response with session token for the frontend and set cookies
        session_token = generate_session_token(user_id)
        response = web.json_response({
            'status': 'success',
            'redirect_url': '/session/success',
            'session_token': session_token
        })
        try:
            set_auth_cookies(response, session_token, user_id)
        except Exception:
            pass
        return response

    return web.json_response(result)

@routes.post("/session/submit_password")
async def session_submit_password_route(request: web.Request):
    """Handle 2FA password submission."""
    data = await request.json()
    token = data.get('token')
    password = data.get('password')

    user_id = await validate_session_token(token)
    if not user_id:
        return web.json_response({'status': 'error', 'message': 'Invalid or expired session.'}, status=401)

    try:
        result = await asyncio.wait_for(
            interactive_login_manager.submit_password(user_id, password),
            timeout=35
        )
    except asyncio.TimeoutError:
        try:
            await interactive_login_manager.cleanup_client(user_id)
        except Exception:
            pass
        return web.json_response({'status': 'timeout', 'message': '2FA verification timed out. Please request a new code.'}, status=504)
    
    if result.get('status') == 'success':
        # SECURITY: Verify that the logged-in user matches the widget user
        logged_in_user_info = result.get('user_info')
        if not logged_in_user_info or logged_in_user_info.get('id') != user_id:
            await interactive_login_manager.cleanup_client(user_id)
            return web.json_response({
                'status': 'error', 
                'message': 'Account mismatch. The logged-in account does not match the widget account.'
            }, status=400)
            
        from StreamBot.database.user_sessions import store_user_session
        session_stored = await store_user_session(user_id, result['session_string'], logged_in_user_info)
        await interactive_login_manager.cleanup_client(user_id)
        
        if not session_stored:
            logger.error(f"Failed to store session for user {user_id}")
            return web.json_response({
                'status': 'error', 
                'message': 'Failed to store session. Please try again.'
            }, status=500)

        # Notify user via bot DM (non-blocking best-effort)
        try:
            from StreamBot.session_generator.session_manager import session_manager
            asyncio.create_task(session_manager.notify_bot_about_new_session(user_id, logged_in_user_info))
        except Exception as _e:
            logger.debug(f"Notify bot about new session failed for {user_id}: {_e}")

        # Prepare redirect response with session token for the frontend and set cookies
        session_token = generate_session_token(user_id)
        response = web.json_response({
            'status': 'success',
            'redirect_url': '/session/success',
            'session_token': session_token
        })
        try:
            set_auth_cookies(response, session_token, user_id)
        except Exception:
            pass
        return response

    return web.json_response(result)

@routes.post("/session/auth")
async def session_auth_route(request: web.Request):
    """Handle Telegram authentication and redirect to interactive login."""
    try:
        data = await request.json()
        
        # Verify Telegram authentication
        from StreamBot.session_generator.telegram_auth import TelegramAuth
        telegram_auth = TelegramAuth()
        
        if not telegram_auth.verify_telegram_auth(data):
            return web.json_response({
                'success': False,
                'error': 'Invalid Telegram authentication'
            }, status=400)
        
        user_id = int(data['id'])
        
        # Check if user has permission to use session generator
        if not check_session_generator_access(user_id):
            logger.info(f"Session generator web access denied for non-admin user {user_id}")
            return web.json_response({
                'success': False,
                'error': 'Access to the session generator is restricted to administrators.'
            }, status=403)
            
        # Generate a temporary token and redirect to the login form
        session_token = generate_session_token(user_id)
        
        return web.json_response({
                'success': True,
            'redirect_url': f'/session/login?token={session_token}',
            'session_token': session_token
        })
            
    except Exception as e:
        logger.error(f"Error in session auth route: {e}", exc_info=True)
        return web.json_response({
            'success': False,
            'error': 'An internal server error occurred.'
        }, status=500)

@routes.get("/session/success")
async def session_success_route(request: web.Request):
    """Session generation success page route."""
    from aiohttp_jinja2 import render_template
    from StreamBot.database.user_sessions import get_user_session_info
    
    try:
        # Prefer cookie/header session token
        session_token = get_session_token(request)
        user_id = await validate_session_token(session_token) if session_token else None
        
        if not user_id:
            logger.warning("No valid session token or user_id provided for success page")
            return web.HTTPFound('/session')
        
        # Get user session info from database
        user_info = await get_user_session_info(user_id)
        if not user_info:
            logger.warning(f"No session info found for user {user_id} on success page")
            return web.HTTPFound('/session')
        
        # Get bot username for the success page
        bot_client = request.app['bot_client']
        bot_username = bot_client.me.username if bot_client and bot_client.me else 'unknown'
        
        return render_template('success.html', request, {
            'user_info': user_info,
            'base_url': Var.BASE_URL,
            'bot_username': bot_username
        })
        
    except (ValueError, TypeError):
        logger.warning("Invalid user_id format on success page")
        return web.HTTPFound('/session')
    except Exception as e:
        logger.error(f"Error in session success page: {e}", exc_info=True)
        return web.HTTPFound('/session')

@routes.get("/session/dashboard")
async def session_dashboard_route(request: web.Request):
    """Session generator dashboard for authenticated users with proper session management."""
    from aiohttp_jinja2 import render_template

    # Check for session token in cookies or headers, fallback to query parameter
    session_token = get_session_token(request)
    user_id_param = request.query.get('user_id')

    user_id = None

    try:
        if session_token:
            # Validate session token
            user_id = await validate_session_token(session_token)
        elif user_id_param:
            user_id = int(user_id_param)

        if not user_id:
            logger.warning("No valid session token or user_id provided")
            return web.HTTPFound('/session')

        # Check if user has permission to use session generator
        if not check_session_generator_access(user_id):
            logger.info(f"Session generator dashboard access denied for non-admin user {user_id}")
            return web.Response(
                text="Access Denied: Session generator is restricted to administrators only.",
                status=403,
                content_type='text/plain'
            )

        # Get user session info
        from StreamBot.database.user_sessions import get_user_session_info
        user_info = await get_user_session_info(user_id)

        if not user_info:
            logger.warning(f"No session info found for user {user_id}")
            return web.HTTPFound('/session')

        # Generate new session token for this session
        new_session_token = generate_session_token(user_id)

        bot_client: Client = request.app.get('bot_client')
        bot_username = getattr(bot_client.me, 'username', None) if bot_client and hasattr(bot_client, 'me') else None

        context = {
            'user_info': user_info,
            'bot_username': bot_username,
            'base_url': Var.BASE_URL,
            'app_name': 'Telegram Session Generator',
            'session_token': new_session_token
        }

        response = render_template('dashboard.html', request, context)

        # Set session cookie for proper session management
        if hasattr(response, 'set_cookie'):
            is_secure = str(Var.BASE_URL).lower().startswith('https://')
            response.set_cookie('session_token', new_session_token, httponly=True, secure=is_secure, max_age=3600, samesite='Lax')
            # convenience cookies for UI
            response.set_cookie('is_authenticated', 'true', secure=is_secure, max_age=3600, samesite='Lax')
            response.set_cookie('user_id', str(user_id), secure=is_secure, max_age=3600, samesite='Lax')
        else:
            # If render_template doesn't return a response object, create one
            response = web.Response(text=response, content_type='text/html')
            is_secure = str(Var.BASE_URL).lower().startswith('https://')
            response.set_cookie('session_token', new_session_token, httponly=True, secure=is_secure, max_age=3600, samesite='Lax')
            response.set_cookie('is_authenticated', 'true', secure=is_secure, max_age=3600, samesite='Lax')
            response.set_cookie('user_id', str(user_id), secure=is_secure, max_age=3600, samesite='Lax')

        return response

    except (ValueError, TypeError):
        logger.warning(f"Invalid user_id format: {user_id_param}")
        return web.HTTPFound('/session')
    except Exception as e:
        logger.error(f"Error in session dashboard: {e}", exc_info=True)
        return web.HTTPFound('/session')


# --- Web Logout Route ---
@routes.get("/session/logout")
async def session_logout_route(request: web.Request):
    """Logout user: revoke session (if any) and clear cookies, then redirect home."""
    try:
        session_token = get_session_token(request)
        user_id = await validate_session_token(session_token) if session_token else None
        if user_id:
            try:
                from StreamBot.database.user_sessions import revoke_user_session
                await revoke_user_session(user_id)
            except Exception as _e:
                logger.debug(f"Revoke session failed during web logout for {user_id}: {_e}")

        # Redirect to home and clear cookies
        response = web.HTTPFound('/session')
        try:
            clear_auth_cookies(response)
        except Exception:
            pass
        return response
    except Exception as e:
        logger.error(f"Error in web logout route: {e}")
        return web.HTTPFound('/session')
