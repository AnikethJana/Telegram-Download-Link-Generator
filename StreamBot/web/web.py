# StreamBot/web.py
import re
import logging
import asyncio
import datetime
import os
import math
from aiohttp import web
import aiohttp_cors
from pyrogram import Client
from pyrogram.errors import FloodWait, FileIdInvalid, RPCError
from pyrogram.types import Message, User

from StreamBot.config import Var
# Ensure decode_message_id is imported from utils
from StreamBot.utils.utils import get_file_attr, humanbytes, decode_message_id, get_media_message
from StreamBot.utils.exceptions import NoClientsAvailableError # Import custom exception
from StreamBot.utils.bandwidth import is_bandwidth_limit_exceeded, add_bandwidth_usage
from StreamBot.utils.stream_cleanup import stream_tracker, tracked_stream_response
from StreamBot.security.middleware import SecurityMiddleware
from StreamBot.security.validator import validate_range_header, sanitize_filename, get_client_ip
from StreamBot.utils.custom_dl import ByteStreamer
from .streaming import stream_video_route

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# Helper function to check session generator access permissions
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
        # Add timeout to prevent hanging requests - increased for large file support
        streamer_client = await asyncio.wait_for(
            client_manager.get_streaming_client(),
            timeout=60  # Increased from 30 to 60 seconds for large file handling
        )
        if not streamer_client or not streamer_client.is_connected:
            logger.error(f"Failed to obtain a connected streaming client for message_id {message_id}")
            raise web.HTTPServiceUnavailable(text="Service temporarily overloaded. Please try again shortly.")

        logger.debug(f"Using client @{streamer_client.me.username} for streaming message_id {message_id}")
        media_msg = await get_media_message(streamer_client, message_id)
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

    # Get ByteStreamer instance for the client
    byte_streamer = client_manager.get_streamer_for_client(streamer_client)
    if not byte_streamer:
        logger.error(f"No ByteStreamer found for client @{streamer_client.me.username}")
        raise web.HTTPInternalServerError(text="Streaming service not available.")

    # Use ByteStreamer to get file properties (similar to WebStreamer approach)
    try:
        file_id = await byte_streamer.get_file_properties(message_id)
    except FileNotFoundError:
        logger.error(f"File properties not found for message {message_id}")
        raise web.HTTPNotFound(text="File not found or has been deleted.")
    except Exception as e:
        logger.error(f"Error getting file properties for message {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Failed to get file details.")

    # Extract file information from FileId object
    file_size = getattr(file_id, 'file_size', 0)
    file_name = getattr(file_id, 'file_name', None)
    file_mime_type = getattr(file_id, 'mime_type', None)

    # Generate fallback filename if needed
    if not file_name:
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
    bot_client: Client = request.app['bot_client']
    start_time: datetime.datetime = request.app['start_time']
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
    middlewares = SecurityMiddleware.get_middlewares()
    webapp = web.Application(middlewares=middlewares)
    
    # Setup Jinja2 templates for session generator with memory optimization
    try:
        import aiohttp_jinja2
        import jinja2
        
        # Configure template directory
        template_path = os.path.join(os.path.dirname(__file__), '..', 'session_generator', 'templates')
        if not os.path.exists(template_path):
            logger.warning(f"Template directory not found: {template_path}")
            os.makedirs(template_path, exist_ok=True)
        
        # Memory-optimized Jinja2 setup for low-resource environment
        aiohttp_jinja2.setup(
            webapp,
            loader=jinja2.FileSystemLoader(template_path),
            # Enable template caching to reduce memory usage
            enable_async=False,  # Disable async for lower memory overhead
            cache_size=10,  # Small cache size for low memory
            auto_reload=False,  # Disable auto-reload for production efficiency
            undefined=jinja2.StrictUndefined  # Catch template errors early
        )
        logger.info(f"Jinja2 templates configured for session generator at: {template_path}")
        
        # Setup static files for session generator with caching
        static_path = os.path.join(os.path.dirname(__file__), '..', 'session_generator', 'static')
        if os.path.exists(static_path):
            webapp.router.add_static(
                '/session/static', 
                static_path, 
                name='session_static',
                # Add cache headers for better performance
                show_index=False,  # Security: don't show directory listings
                follow_symlinks=False  # Security: don't follow symlinks
            )
            logger.info(f"Static files configured for session generator at: {static_path}")
        
    except ImportError:
        logger.warning("aiohttp_jinja2 not available. Session generator templates will not work.")
    except Exception as e:
        logger.error(f"Error setting up templates for session generator: {e}")
    
    webapp.add_routes(routes)
    webapp['bot_client'] = bot_instance # This is the primary client for general info like /api/info
    webapp['client_manager'] = client_manager # For download routes to get worker clients
    webapp['start_time'] = start_time # type: ignore
    logger.info("Web application routes configured with security middleware.")
    
    # Memory-optimized CORS configuration
    cors = aiohttp_cors.setup(webapp, defaults={
        # Restrict CORS to essential headers only to reduce memory overhead
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=False,
            expose_headers=["Content-Length", "Content-Range"],
            allow_headers=["Range", "Content-Type"],
            allow_methods=["GET", "HEAD", "OPTIONS", "POST"],  # Added POST for session auth
            max_age=3600  # Cache preflight for 1 hour to reduce requests
        )
    })
    
    # Only add CORS to routes that need it (more memory efficient)
    for route in list(webapp.router.routes()):
        if route.method in ["GET", "POST", "OPTIONS"]:
            cors.add(route)
    
    logger.info("CORS configured with memory optimization.")
    return webapp

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

@routes.post("/session/auth")
async def session_auth_route(request: web.Request):
    """Handle Telegram authentication for session generation."""
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
                'error': 'Access to session generator is restricted to administrators only'
            }, status=403)
        user_info = {
            'id': user_id,
            'username': data.get('username'),
            'first_name': data.get('first_name'),
            'last_name': data.get('last_name'),
            'photo_url': data.get('photo_url'),
            'auth_date': int(data['auth_date'])
        }
        
        # Generate user session
        from StreamBot.session_generator.session_manager import SessionManager
        session_manager = SessionManager()
        
        result = await session_manager.generate_user_session(user_id, user_info)
        
        if result['success']:
            # Add user to database
            from StreamBot.database.database import add_user
            await add_user(user_id)
            
            return web.json_response({
                'success': True,
                'message': 'Session generated successfully!',
                'session_active': True
            })
        else:
            return web.json_response({
                'success': False,
                'error': result['error']
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in session authentication: {e}", exc_info=True)
        return web.json_response({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@routes.get("/session/dashboard")
async def session_dashboard_route(request: web.Request):
    """Session generator dashboard for authenticated users."""
    from aiohttp_jinja2 import render_template
    
    # For now, we'll check session via query parameter
    # In production, you'd use proper session management
    user_id = request.query.get('user_id')
    if not user_id:
        # Redirect to main page
        raise web.HTTPFound('/session')
    
    try:
        user_id = int(user_id)
        
        # Check if user has permission to use session generator
        if not check_session_generator_access(user_id):
            logger.info(f"Session generator dashboard access denied for non-admin user {user_id}")
            # Create a simple access denied response
            return web.Response(
                text="Access Denied: Session generator is restricted to administrators only.",
                status=403,
                content_type='text/plain'
            )
        
        # Get user session info
        from StreamBot.database.user_sessions import get_user_session
        session_info = await get_user_session(user_id)
        
        if not session_info or not session_info.get('is_active'):
            # Redirect to main page if no active session
            raise web.HTTPFound('/session')
        
        bot_client: Client = request.app['bot_client']
        bot_username = getattr(bot_client.me, 'username', None) if hasattr(bot_client, 'me') else None
        
        context = {
            'user_info': session_info,
            'bot_username': bot_username,
            'base_url': Var.BASE_URL,
            'app_name': 'Telegram Session Generator'
        }
        
        return render_template('dashboard.html', request, context)
        
    except (ValueError, TypeError):
        raise web.HTTPFound('/session')
    except Exception as e:
        logger.error(f"Error in session dashboard: {e}", exc_info=True)
        raise web.HTTPFound('/session')


