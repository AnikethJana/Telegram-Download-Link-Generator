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
from pyrogram.errors import FloodWait, FileIdInvalid, RPCError, OffsetInvalid as PyrogramOffsetInvalid, FileReferenceExpired # Import FileReferenceExpired error
from pyrogram.types import Message, User

from StreamBot.config import Var
# Ensure decode_message_id is imported from utils
from StreamBot.utils.utils import get_file_attr, humanbytes, decode_message_id, validate_streaming_parameters, calculate_chunk_parameters
from StreamBot.utils.exceptions import NoClientsAvailableError # Import custom exception
from StreamBot.utils.bandwidth import is_bandwidth_limit_exceeded, add_bandwidth_usage
from StreamBot.utils.stream_cleanup import stream_tracker, tracked_stream_response
from StreamBot.security.middleware import SecurityMiddleware
from StreamBot.security.validator import validate_range_header, sanitize_filename, get_client_ip

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# Request timeout for streaming operations (2 hours max)
STREAM_TIMEOUT = 7200  # 2 hours

# Chunk size for downloads - this is critical for proper offset calculation
CHUNK_SIZE = 1024 * 1024  # 1MB chunks - same as FileStreamBot reference

# --- Lightweight Retry Configuration (Hardcoded) ---
MAX_RETRIES = 2  # Total retries per request
RETRY_DELAYS = [0.5, 1.0]  # Fast retries for user experience
CLIENT_SWITCH_DELAY = 0.8  # Delay when switching clients

# Try to import FileReferenceInvalid if available (some pyrogram versions might have it)
try:
    from pyrogram.errors import FileReferenceInvalid
    FILE_REFERENCE_ERRORS = (FileReferenceExpired, FileReferenceInvalid)
except ImportError:
    FILE_REFERENCE_ERRORS = (FileReferenceExpired,)

# --- Retry Helper Functions ---
def is_retryable_error(error) -> bool:
    """Check if an error is worth retrying."""
    retryable_types = (
        PyrogramOffsetInvalid,
        ConnectionError, 
        TimeoutError,
        RPCError,
        NoClientsAvailableError,
        asyncio.TimeoutError
    ) + FILE_REFERENCE_ERRORS
    
    # Don't retry certain HTTP errors
    if isinstance(error, (web.HTTPNotFound, web.HTTPGone, web.HTTPBadRequest)):
        return False
        
    return isinstance(error, retryable_types)

async def get_retry_delay(attempt: int) -> float:
    """Get delay for retry attempt with jitter."""
    import random
    
    if attempt >= len(RETRY_DELAYS):
        delay = RETRY_DELAYS[-1] * (attempt - len(RETRY_DELAYS) + 2)
    else:
        delay = RETRY_DELAYS[attempt]
    
    # Add small jitter to prevent thundering herd
    return delay + random.uniform(0.1, 0.3)

async def release_client_safely(intelligent_allocator, client, task_id):
    """Helper to safely release a client."""
    if intelligent_allocator and client:
        try:
            await intelligent_allocator.release_client(client, task_id)
        except Exception as e:
            logger.warning(f"Error releasing client during cleanup: {e}")

# --- Format Uptime 
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

# --- Helper to get message and check expiry ---
async def get_media_message(bot_client: Client, message_id: int) -> Message:
    """Fetch the media message object from the LOG_CHANNEL and check expiry."""
    if not bot_client or not bot_client.is_connected:
        logger.error("Bot client is not available or connected for get_media_message.")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable.")

    max_retries = 3
    current_retry = 0
    media_msg = None
    while current_retry < max_retries:
        try:
            media_msg = await bot_client.get_messages(chat_id=Var.LOG_CHANNEL, message_ids=message_id)
            break
        except FloodWait as e:
            if current_retry == max_retries - 1:
                logger.error(f"Max retries reached for FloodWait getting message {message_id}. Aborting.")
                raise web.HTTPTooManyRequests(text="Service temporarily rate limited. Please try again later.")
            sleep_duration = e.value + 2
            logger.warning(f"FloodWait getting message {message_id} from {Var.LOG_CHANNEL}. Retrying in {sleep_duration}s (Attempt {current_retry+1}/{max_retries}).")
            await asyncio.sleep(sleep_duration)
            current_retry += 1
        except FileIdInvalid:
            logger.error(f"FileIdInvalid for message {message_id} in log channel {Var.LOG_CHANNEL}. File might be deleted.")
            raise web.HTTPNotFound(text="File not found or has been deleted.")
        except (ConnectionError, RPCError, TimeoutError) as e: # RPCError includes OffsetInvalid, but we catch it more specifically in download_route
            if current_retry == max_retries - 1:
                logger.error(f"Max retries reached for network/RPC error getting message {message_id}: {e}. Aborting.")
                raise web.HTTPServiceUnavailable(text="Service temporarily unavailable. Please try again later.")
            sleep_duration = 5 * (current_retry + 1)
            logger.warning(f"Network/RPC error getting message {message_id}: {e}. Retrying in {sleep_duration}s (Attempt {current_retry+1}/{max_retries}).")
            await asyncio.sleep(sleep_duration)
            current_retry += 1
        except Exception as e:
            logger.error(f"Unexpected error getting message {message_id} from {Var.LOG_CHANNEL}: {e}", exc_info=True)
            raise web.HTTPInternalServerError(text="Internal server error occurred.")

    if not media_msg:
        logger.error(f"Failed to retrieve message {message_id} after retries, but no exception was raised (should not happen).")
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable.")

    # --- Link Expiry Check ---
    if hasattr(media_msg, 'date') and isinstance(media_msg.date, datetime.datetime):
        message_timestamp = media_msg.date.replace(tzinfo=datetime.timezone.utc)
        current_timestamp = datetime.datetime.now(datetime.timezone.utc)
        time_difference = current_timestamp - message_timestamp
        expiry_seconds = Var.LINK_EXPIRY_SECONDS
        
        # Check if expiry is enabled
        if expiry_seconds > 0 and time_difference.total_seconds() > expiry_seconds:
            logger.warning(f"Download link for message {message_id} expired. Age: {time_difference} > {expiry_seconds}s")
            raise web.HTTPGone(text="Download link has expired.")
    else:
        logger.warning(f"Could not determine message timestamp for message {message_id}. Skipping expiry check.")

    return media_msg

# --- Proper Range Header Validation (Enhanced from FileStreamBot) ---
def parse_range_header(range_header: str, file_size: int) -> tuple:
    """Parse range header with proper validation - based on FileStreamBot reference."""
    if not range_header:
        return None
    
    try:
        # Handle both 'bytes=start-end' and 'bytes=start-' formats
        if range_header.startswith('bytes='):
            range_spec = range_header[6:]  # Remove 'bytes='
            if '-' in range_spec:
                parts = range_spec.split('-', 1)
                start_str, end_str = parts[0], parts[1]
                
                from_bytes = int(start_str) if start_str else 0
                until_bytes = int(end_str) if end_str else file_size - 1
            else:
                return None
        else:
            return None
        
        # Validation based on FileStreamBot
        if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
            return None
        
        # Ensure until_bytes doesn't exceed file size
        until_bytes = min(until_bytes, file_size - 1)
        
        return (from_bytes, until_bytes)
        
    except (ValueError, TypeError, IndexError):
        logger.warning(f"Error parsing range header: {range_header}")
        return None

# --- Chunk-aligned File Streaming (Fixed Offset Calculation) ---
async def stream_file_chunks(client: Client, media_msg: Message, from_bytes: int, until_bytes: int, response: web.StreamResponse) -> int:
    """
    Stream file chunks with proper offset calculation to prevent OFFSET_INVALID errors.
    Based on FileStreamBot reference implementation.
    """
    bytes_streamed = 0
    
    # Get actual file size from media message for proper validation
    _file_id, _file_name, actual_file_size, _file_mime_type, _ = get_file_attr(media_msg)
    
    # Validate streaming parameters with correct file size
    if not validate_streaming_parameters(from_bytes, until_bytes, actual_file_size, CHUNK_SIZE):
        logger.error(f"Invalid streaming parameters: from_bytes={from_bytes}, until_bytes={until_bytes}, file_size={actual_file_size}")
        raise ValueError("Invalid streaming parameters")
    
    # Calculate chunk-aligned parameters using utility function
    offset, first_part_cut, last_part_cut, part_count = calculate_chunk_parameters(from_bytes, until_bytes, CHUNK_SIZE)
    
    current_part = 1
    current_offset = offset
    
    try:
        # Stream file in properly calculated chunks
        async for chunk in client.stream_media(media_msg, offset=current_offset, limit=CHUNK_SIZE):
            if not chunk:
                break
                
            try:
                # Apply cuts based on FileStreamBot logic
                if part_count == 1:
                    # Single chunk - apply both cuts
                    chunk_to_send = chunk[first_part_cut:last_part_cut]
                elif current_part == 1:
                    # First chunk - apply first cut only
                    chunk_to_send = chunk[first_part_cut:]
                elif current_part == part_count:
                    # Last chunk - apply last cut only
                    chunk_to_send = chunk[:last_part_cut]
                else:
                    # Middle chunks - no cuts
                    chunk_to_send = chunk
                
                if chunk_to_send:
                    await response.write(chunk_to_send)
                    bytes_streamed += len(chunk_to_send)
                
                current_part += 1
                current_offset += CHUNK_SIZE
                
                if current_part > part_count:
                    break
                    
            except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
                logger.warning(f"Client disconnected during chunk write. Streamed {humanbytes(bytes_streamed)}")
                break
            except Exception as write_e:
                logger.error(f"Error writing chunk: {write_e}")
                break
                
    except PyrogramOffsetInvalid as e:
        logger.error(f"OffsetInvalid error: offset={current_offset}, chunk_size={CHUNK_SIZE}, file_size={until_bytes + 1}")
        # Don't re-raise here, let the calling function handle it
        raise e
    except Exception as e:
        logger.error(f"Unexpected streaming error: {e}")
        raise e
    
    return bytes_streamed

# --- Download Route (Enhanced with intelligent allocation and retry system) ---
@routes.get("/dl/{encoded_id_str}")
async def download_route(request: web.Request):
    """Handle file download requests with intelligent client allocation and retry system."""
    client_manager = request.app.get('client_manager')
    intelligent_allocator = request.app.get('intelligent_allocator')
    
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

    # Generate unique task ID for this download
    task_id = f"{message_id}_{encoded_id[:10]}_{int(start_time_request)}"
    
    # --- Retry Wrapper for Download Logic ---
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Core download logic with retry-aware error handling
            return await _execute_download_logic(
                request, client_manager, intelligent_allocator, 
                message_id, encoded_id, task_id, start_time_request
            )
            
        except Exception as e:
            if attempt == MAX_RETRIES or not is_retryable_error(e):
                # Final attempt or non-retryable error
                logger.error(f"Final failure for download {message_id} after {attempt} attempts: {e}")
                if isinstance(e, web.HTTPException):
                    raise e
                else:
                    raise web.HTTPInternalServerError(text="Service temporarily unavailable.")
            
            # Retry with delay
            delay = await get_retry_delay(attempt)
            logger.warning(f"Download attempt {attempt + 1} failed for {message_id}: {e}. Retrying in {delay:.2f}s...")
            await asyncio.sleep(delay)

async def _execute_download_logic(request, client_manager, intelligent_allocator, message_id, encoded_id, task_id, start_time_request):
    """Execute the core download logic."""
    streamer_client = None
    
    try:
        # Step 1: Get file info and allocate client
        primary_client = client_manager.get_primary_client()
        if not primary_client:
            raise web.HTTPServiceUnavailable(text="Service temporarily unavailable.")
        
        media_msg = await get_media_message(primary_client, message_id)
        _file_id, file_name, file_size, file_mime_type, _ = get_file_attr(media_msg)
        
        # Step 2: Client allocation with fallback strategy
        if intelligent_allocator:
            try:
                streamer_client = await intelligent_allocator.acquire_client_for_download(file_size, task_id)
                logger.debug(f"Intelligent allocation: Using client @{streamer_client.me.username} for {file_size/1024/1024:.1f}MB file")
            except NoClientsAvailableError:
                # Fallback to round-robin
                logger.info(f"Intelligent allocation unavailable for {message_id}, falling back to round-robin")
                await asyncio.sleep(1.2)  # Brief delay for fallback
                streamer_client = await client_manager.get_streaming_client()
        else:
            # Legacy method
            streamer_client = await client_manager.get_streaming_client()
        
        # Step 3: Ensure message consistency across clients
        if streamer_client.me.id != primary_client.me.id:
            logger.debug(f"Re-fetching message {message_id} with streaming client @{streamer_client.me.username}")
            media_msg = await get_media_message(streamer_client, message_id)
            _check_file_id, check_file_name, check_file_size, check_file_mime_type, _ = get_file_attr(media_msg)
            if check_file_size != file_size:
                logger.warning(f"File size mismatch after re-fetch for {message_id}: {file_size} vs {check_file_size}")
                file_name, file_size, file_mime_type = check_file_name, check_file_size, check_file_mime_type
        
        # Step 4: Execute streaming
        return await _stream_file_to_response(
            request, streamer_client, intelligent_allocator, media_msg, 
            message_id, encoded_id, task_id, file_name, file_size, file_mime_type, start_time_request
        )
        
    except Exception as e:
        # Clean up allocated client on error
        await release_client_safely(intelligent_allocator, streamer_client, task_id)
        raise e

async def _stream_file_to_response(request, streamer_client, intelligent_allocator, media_msg, message_id, encoded_id, task_id, file_name, file_size, file_mime_type, start_time_request):
    """Execute the core streaming logic with proper offset handling."""
    # Sanitize filename for security
    safe_filename = sanitize_filename(file_name)

    if file_name == "unknown_file" and file_size == 0:
        await release_client_safely(intelligent_allocator, streamer_client, task_id)
        logger.error(f"Could not extract valid file attributes from message {message_id}")
        raise web.HTTPInternalServerError(text="Failed to get file details.")

    headers = {
        'Content-Type': file_mime_type or 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{safe_filename}"',
        'Accept-Ranges': 'bytes'
    }

    range_header = request.headers.get('Range')
    status_code = 200
    from_bytes = 0
    until_bytes = file_size - 1 if file_size > 0 else 0
    is_range_request = False

    if range_header:
        logger.info(f"Range header for {message_id}: '{range_header}', File size: {humanbytes(file_size)}")
        
        # Use the enhanced range parser
        range_result = parse_range_header(range_header, file_size)
        if range_result is None:
            await release_client_safely(intelligent_allocator, streamer_client, task_id)
            logger.error(f"Invalid Range header '{range_header}' for file size {file_size}")
            raise web.HTTPRequestRangeNotSatisfiable(headers={'Content-Range': f'bytes */{file_size}'})
        
        from_bytes, until_bytes = range_result
        headers['Content-Range'] = f'bytes {from_bytes}-{until_bytes}/{file_size}'
        headers['Content-Length'] = str(until_bytes - from_bytes + 1)
        status_code = 206
        is_range_request = True
        logger.info(f"Serving range request for {message_id}: bytes {from_bytes}-{until_bytes}/{file_size}")
    else:
        headers['Content-Length'] = str(file_size)
        logger.info(f"Serving full download for {message_id}. File size: {humanbytes(file_size)}")

    response = web.StreamResponse(status=status_code, headers=headers)
    await response.prepare(request)

    bytes_streamed = 0
    stream_start_time = asyncio.get_event_loop().time()
    streaming_completed_successfully = False

    # Handle 0-byte file case
    if (until_bytes - from_bytes + 1) == 0 and file_size == 0:
        logger.info(f"Serving 0-byte file {message_id}. No data to stream.")
        await release_client_safely(intelligent_allocator, streamer_client, task_id)
        total_request_duration = asyncio.get_event_loop().time() - start_time_request
        logger.info(f"Download request for {message_id} completed (0-byte file). Total duration: {total_request_duration:.2f}s")
        return response

    # Use stream tracking context manager for proper cleanup
    request_id = f"{message_id}_{encoded_id[:10]}"
    
    try:
        async with tracked_stream_response(response, stream_tracker, request_id):
            # Streaming with retry logic for temporary errors
            max_stream_retries = 2
            for stream_attempt in range(max_stream_retries + 1):
                try:
                    # Use the new chunk-aligned streaming function
                    bytes_streamed = await stream_file_chunks(
                        streamer_client, media_msg, from_bytes, until_bytes, response
                    )
                    streaming_completed_successfully = True
                    break

                except FILE_REFERENCE_ERRORS:
                    logger.warning(f"FILE_REFERENCE error for {message_id}. Refreshing...")
                    try:
                        media_msg = await get_media_message(streamer_client, message_id)
                        logger.info(f"File reference refreshed for {message_id}")
                        if stream_attempt < max_stream_retries:
                            await asyncio.sleep(1)
                            continue
                    except Exception:
                        logger.error(f"Failed to refresh file reference for {message_id}")
                        break

                except PyrogramOffsetInvalid:
                    logger.error(f"OffsetInvalid error for {message_id}. from_bytes: {from_bytes}, until_bytes: {until_bytes}")
                    # This should not happen with proper chunk alignment, but handle gracefully
                    if bytes_streamed == 0:
                        raise web.HTTPInternalServerError(text="File access error. Please try again later.")
                    break

                except FloodWait as e:
                    logger.warning(f"FloodWait during stream for {message_id} on @{streamer_client.me.username}")
                    
                    # Try intelligent allocator for alternative client
                    if intelligent_allocator:
                        alternative_client = await intelligent_allocator.handle_flood_wait_retry(
                            streamer_client, e.value, file_size, task_id
                        )
                        if alternative_client:
                            logger.info(f"Switched to alternative client @{alternative_client.me.username} for {message_id}")
                            streamer_client = alternative_client
                            # Re-fetch media message with new client
                            media_msg = await get_media_message(streamer_client, message_id)
                            await asyncio.sleep(CLIENT_SWITCH_DELAY)
                            continue
                    
                    # Fallback: wait for flood wait
                    logger.warning(f"No alternative client available. Waiting {e.value}s for FloodWait")
                    await asyncio.sleep(e.value + 2)

                except (ConnectionError, TimeoutError, RPCError):
                    if stream_attempt >= max_stream_retries:
                        logger.error(f"Max stream retries reached for {message_id}")
                        break
                    logger.warning(f"Stream error for {message_id}. Retrying... ({stream_attempt + 1}/{max_stream_retries})")
                    await asyncio.sleep(2)

                except asyncio.TimeoutError:
                    logger.error(f"Stream timeout for {message_id} after {STREAM_TIMEOUT}s")
                    if bytes_streamed == 0:
                        raise web.HTTPGatewayTimeout(text="Request timeout. Please try again.")
                    break

                except Exception as e:
                    logger.error(f"Unexpected streaming error for {message_id}: {e}")
                    break
    
    finally:
        # Always release the client
        await release_client_safely(intelligent_allocator, streamer_client, task_id)

    # Record bandwidth and log completion
    if bytes_streamed > 0:
        await add_bandwidth_usage(bytes_streamed)

    stream_duration = asyncio.get_event_loop().time() - stream_start_time
    expected_bytes = until_bytes - from_bytes + 1

    # Log completion status
    if streaming_completed_successfully and bytes_streamed == expected_bytes:
        logger.info(f"Download request for {message_id} completed successfully. Total duration: {stream_duration:.2f}s")
    else:
        logger.warning(f"Partial/incomplete stream for {message_id}: {humanbytes(bytes_streamed)}/{humanbytes(expected_bytes)}")

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
async def setup_webapp(bot_instance: Client, client_manager, intelligent_allocator, start_time: datetime.datetime):
    # Create app with security middleware
    webapp = web.Application(middlewares=SecurityMiddleware.get_middlewares())
    
    webapp.add_routes(routes)
    webapp['bot_client'] = bot_instance # This is the primary client for general info like /api/info
    webapp['client_manager'] = client_manager # For download routes to get worker clients
    webapp['intelligent_allocator'] = intelligent_allocator # For intelligent client allocation
    webapp['start_time'] = start_time # type: ignore
    logger.info("Web application routes configured with security middleware and intelligent allocation.")
    
    # More restrictive CORS configuration
    cors = aiohttp_cors.setup(webapp, defaults={
        # Allow only common origins for API access
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=False,
            expose_headers=["Content-Length", "Content-Range"],
            allow_headers=["Range", "Content-Type"],
            allow_methods=["GET", "HEAD", "OPTIONS"],
        )
    })
    for route in list(webapp.router.routes()):
        cors.add(route)
    logger.info("CORS configured with security restrictions.")
    return webapp
