# StreamBot/web.py
import re
import logging
import asyncio
import datetime
import os
from aiohttp import web
import aiohttp_cors
from pyrogram import Client
from pyrogram.errors import FloodWait, FileIdInvalid, RPCError, OffsetInvalid as PyrogramOffsetInvalid # Import specific error
from pyrogram.types import Message, User

from StreamBot.config import Var
# Ensure decode_message_id is imported from utils
from StreamBot.utils.utils import get_file_attr, humanbytes, decode_message_id
from StreamBot.utils.exceptions import NoClientsAvailableError # Import custom exception

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# --- Helper: Format Uptime --- (keep as is)
def format_uptime(start_time_dt: datetime.datetime) -> str:
    """Formats the uptime into a human-readable string."""
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
    """Fetches the media message object from the LOG_CHANNEL and checks expiry."""
    if not bot_client or not bot_client.is_connected:
        logger.error("Bot client is not available or connected for get_media_message.")
        raise web.HTTPServiceUnavailable(text="Bot service temporarily unavailable.")

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
                raise web.HTTPTooManyRequests(text=f"Rate limited by Telegram. Please try again in {e.value} seconds.")
            sleep_duration = e.value + 2
            logger.warning(f"FloodWait getting message {message_id} from {Var.LOG_CHANNEL}. Retrying in {sleep_duration}s (Attempt {current_retry+1}/{max_retries}).")
            await asyncio.sleep(sleep_duration)
            current_retry += 1
        except FileIdInvalid:
            logger.error(f"FileIdInvalid for message {message_id} in log channel {Var.LOG_CHANNEL}. File might be deleted.")
            raise web.HTTPNotFound(text="File link is invalid or the file has been deleted.")
        except (ConnectionError, RPCError, TimeoutError) as e: # RPCError includes OffsetInvalid, but we catch it more specifically in download_route
            if current_retry == max_retries - 1:
                logger.error(f"Max retries reached for network/RPC error getting message {message_id}: {e}. Aborting.")
                raise web.HTTPServiceUnavailable(text="Temporary issue communicating with Telegram. Please try again later.")
            sleep_duration = 5 * (current_retry + 1)
            logger.warning(f"Network/RPC error getting message {message_id}: {e}. Retrying in {sleep_duration}s (Attempt {current_retry+1}/{max_retries}).")
            await asyncio.sleep(sleep_duration)
            current_retry += 1
        except Exception as e:
            logger.error(f"Unexpected error getting message {message_id} from {Var.LOG_CHANNEL}: {e}", exc_info=True)
            raise web.HTTPInternalServerError(text="Could not retrieve file details: An internal error occurred.")

    if not media_msg:
        logger.error(f"Failed to retrieve message {message_id} after retries, but no exception was raised (should not happen).")
        raise web.HTTPServiceUnavailable(text="Failed to retrieve file details after multiple retries.")

    # --- Link Expiry Check ---
    if hasattr(media_msg, 'date') and isinstance(media_msg.date, datetime.datetime):
        message_timestamp = media_msg.date.replace(tzinfo=datetime.timezone.utc)
        current_timestamp = datetime.datetime.now(datetime.timezone.utc)
        time_difference = current_timestamp - message_timestamp
        expiry_seconds = Var.LINK_EXPIRY_SECONDS
        if expiry_seconds > 0 and time_difference.total_seconds() > expiry_seconds: # Check if expiry is enabled
            logger.warning(f"Download link for message {message_id} expired. Age: {time_difference} > {expiry_seconds}s")
            raise web.HTTPGone(text=Var.LINK_EXPIRED_TEXT)
    else:
        logger.warning(f"Could not determine message timestamp for message {message_id}. Skipping expiry check.")

    return media_msg

# --- Download Route (Refactored with improved logging and error handling) ---
@routes.get("/dl/{encoded_id_str}")
async def download_route(request: web.Request):
    # Get the client_manager from the app state
    client_manager = request.app.get('client_manager')
    if not client_manager:
        logger.error("ClientManager not found in web app state.")
        raise web.HTTPServiceUnavailable(text="Bot service configuration error.")

    start_time_request = asyncio.get_event_loop().time() # For overall request timing

    encoded_id = request.match_info['encoded_id_str']
    message_id = decode_message_id(encoded_id)

    if message_id is None:
        logger.warning(f"Download request with invalid or undecodable ID: {encoded_id}")
        raise web.HTTPBadRequest(text="Invalid or malformed download link.")

    logger.info(f"Download request for decoded message_id: {message_id} (encoded: {encoded_id}) from {request.remote}")

    try:
        # Get a streaming client from the manager
        streamer_client = await client_manager.get_streaming_client()
        if not streamer_client or not streamer_client.is_connected: # Ensure client is connected
            logger.error(f"Failed to obtain a connected streaming client for message_id {message_id}")
            raise web.HTTPServiceUnavailable(text="Bot service temporarily overloaded. Please try again shortly.")

        logger.debug(f"Using client @{streamer_client.me.username} for streaming message_id {message_id}")
        media_msg = await get_media_message(streamer_client, message_id)
    except (web.HTTPNotFound, web.HTTPServiceUnavailable, web.HTTPTooManyRequests, web.HTTPGone, web.HTTPInternalServerError) as e:
        logger.warning(f"Error during get_media_message for {message_id}: {type(e).__name__} - {e.text}")
        raise e
    except NoClientsAvailableError as e:
        logger.error(f"No clients available for streaming message_id {message_id}: {e}")
        raise web.HTTPServiceUnavailable(text="All streaming resources are currently busy or unavailable. Please try again later.")
    except Exception as e: # Catch any other unexpected error from get_media_message
        logger.error(f"Unexpected error from get_media_message for {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Failed to retrieve file information.")

    # Use get_file_attr on the fetched media_msg from the log channel
    _file_id, file_name, file_size, file_mime_type, _ = get_file_attr(media_msg)

    # file_size from get_file_attr is now guaranteed to be an int (0 if unknown)
    # file_name is guaranteed to be a string (e.g., "unknown_file" if unknown)
    if file_name == "unknown_file" and file_size == 0:
        logger.error(f"Could not extract valid file attributes from message {message_id} in log channel. Name: {file_name}, Size: {file_size}")
        raise web.HTTPInternalServerError(text="Failed to get file details from message after fetching.")


    headers = {
        'Content-Type': file_mime_type or 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{file_name}"',
        'Accept-Ranges': 'bytes'
    }

    range_header = request.headers.get('Range')
    status_code = 200
    start_offset = 0
    end_offset = file_size - 1 if file_size > 0 else 0 # Handle 0-byte files for end_offset
    is_range_request = False

    if range_header:
        logger.info(f"Range header for {message_id}: '{range_header}', File size: {humanbytes(file_size)}")
        try:
            range_match = re.match(r'bytes=(\d+)?-(\d+)?', range_header)
            if not range_match:
                 raise ValueError("Malformed Range header")

            req_start_str, req_end_str = range_match.groups()

            if req_start_str is None and req_end_str is None:
                 raise ValueError("Invalid Range header: must specify start or end")

            if file_size == 0: # If file is 0 bytes, no range is satisfiable unless it's bytes=0-0 or similar
                if req_start_str == "0" and (req_end_str is None or req_end_str == "0" or req_end_str == "-1"):
                    start_offset = 0
                    end_offset = -1 # Will result in Content-Length: 0
                else:
                    raise ValueError("Range not satisfiable for 0-byte file")


            if req_start_str is not None:
                 start_offset = int(req_start_str)
                 if req_end_str is not None:
                     end_offset = int(req_end_str)
                 # else end_offset remains file_size - 1
            elif req_end_str is not None: # Only end is specified (e.g., bytes=-500)
                 # Request last N bytes. end_offset is file_size - 1.
                 # start_offset is file_size - N.
                 start_offset = max(0, file_size - int(req_end_str))

            # Validate offsets against actual file_size
            # Ensure end_offset is not less than start_offset
            # Ensure start_offset is within bounds [0, file_size-1]
            # Ensure end_offset is within bounds [start_offset, file_size-1]
            if start_offset < 0 or start_offset >= file_size and file_size > 0 : # Allow start_offset = 0 for 0-byte file if end_offset is also 0 or -1
                 raise ValueError(f"Start offset {start_offset} out of bounds for file size {file_size}")
            if end_offset < start_offset or end_offset >= file_size:
                 # If end_offset was not specified, it defaults to file_size -1, which is fine.
                 # This check is mainly if end_offset was explicitly set too high or below start.
                 if req_end_str is not None: # Only if req_end was specified and is invalid
                    raise ValueError(f"End offset {end_offset} out of bounds for start {start_offset} and file size {file_size}")
                 end_offset = file_size - 1 # Correct if it was beyond due to no req_end_str

            headers['Content-Range'] = f'bytes {start_offset}-{end_offset}/{file_size}'
            headers['Content-Length'] = str(end_offset - start_offset + 1)
            status_code = 206
            is_range_request = True
            logger.info(f"Serving range request for {message_id}: bytes {start_offset}-{end_offset}/{file_size}. Content-Length: {headers['Content-Length']}")

        except ValueError as e:
             logger.error(f"Invalid Range header '{range_header}' for file size {file_size}: {e}")
             raise web.HTTPRequestRangeNotSatisfiable(headers={'Content-Range': f'bytes */{file_size}'})
    else:
        headers['Content-Length'] = str(file_size)
        logger.info(f"Serving full download for {message_id}. File size: {humanbytes(file_size)}. Content-Length: {headers['Content-Length']}")

    response = web.StreamResponse(status=status_code, headers=headers)
    await response.prepare(request)

    bytes_streamed = 0
    stream_start_time = asyncio.get_event_loop().time()
    max_retries_stream = 2
    current_retry_stream = 0

    # stream_media's 'limit' is number of bytes *from the offset*
    # If it's a full request (is_range_request is False), start_offset is 0, end_offset is file_size-1.
    # stream_limit should be 0 for full file, or (end_offset - start_offset + 1) for range.
    stream_length_to_request = (end_offset - start_offset + 1) if is_range_request else 0 # 0 means stream to end from offset

    # Handle 0-byte file case: if length is 0, don't try to stream.
    if (end_offset - start_offset + 1) == 0 and file_size == 0 and status_code in [200, 206]:
        logger.info(f"Serving 0-byte file {message_id}. No data to stream.")
        # Response already prepared with Content-Length: 0. Just return.
        return response


    logger.debug(f"Preparing to stream for {message_id}. Effective range: {start_offset}-{end_offset}. Stream length to request: {stream_length_to_request if stream_length_to_request > 0 else 'to end'}.")

    while current_retry_stream <= max_retries_stream:
        try:
            async for chunk in streamer_client.stream_media(
                media_msg,
                offset=start_offset, # Absolute offset in the file
                limit=stream_length_to_request # Number of bytes from offset, 0 for "to end"
                ):
                try:
                    await response.write(chunk)
                    bytes_streamed += len(chunk)
                except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError) as client_e:
                     logger.warning(f"Client connection issue during write for {message_id} (ID {encoded_id}): {type(client_e).__name__}. Streamed {humanbytes(bytes_streamed)}. Aborting stream for this request.")
                     return response # Abort for this specific request
                except Exception as write_e:
                     logger.error(f"Error writing chunk for {message_id} (ID {encoded_id}): {write_e}", exc_info=True)
                     # This is a server-side write error, might not be recoverable for this request
                     return response # Abort, don't raise HTTPInternalServerError yet, let it be caught by outer try if needed

            logger.info(f"Successfully finished streaming loop for {message_id} (ID {encoded_id}).")
            break # Exit retry loop on successful completion of async for

        except PyrogramOffsetInvalid as e: # Specific catch for OffsetInvalid
            logger.error(f"Pyrogram OffsetInvalid error during stream for {message_id} (ID {encoded_id}). Offset: {start_offset}, Limit: {stream_length_to_request}. Error: {e}. Aborting retries for this error.", exc_info=True)
            # Don't typically retry OffsetInvalid with the same parameters
            # Let the outer error handling decide the HTTP response, or raise a specific one.
            # For now, we break the retry loop and let it fall through.
            # If bytes_streamed is 0, it will be handled by the check after the loop.
            # If some bytes were streamed, it will be a partial success/failure.
            # This error often means the file or offset is truly problematic with Telegram.
            if bytes_streamed == 0: # If OffsetInvalid happened at the very start
                 raise web.HTTPInternalServerError(text=f"Telegram reported an issue with the file offset (OffsetInvalid). Unable to start download for {file_name}.")
            break # Break retry loop for OffsetInvalid

        except FloodWait as e:
             logger.warning(f"FloodWait during stream for {message_id} (ID {encoded_id}). Waiting {e.value}s. Attempt {current_retry_stream+1}/{max_retries_stream+1}")
             await asyncio.sleep(e.value + 2)
             # Continue to the next iteration of the while loop (retry)
             # No need to increment current_retry_stream here, it's for other errors

        except (ConnectionError, TimeoutError, RPCError) as e: # Catches other RPC errors
             current_retry_stream += 1
             logger.warning(f"Stream interrupted for {message_id} (ID {encoded_id}) (Attempt {current_retry_stream}/{max_retries_stream+1}): {type(e).__name__} - {e}. Retrying...")
             if current_retry_stream > max_retries_stream:
                  logger.error(f"Max retries reached for stream error. Aborting stream for {message_id} (ID {encoded_id}) after {humanbytes(bytes_streamed)} bytes.")
                  # Don't raise here, let the check after loop handle it based on bytes_streamed
                  break # Exit retry loop
             await asyncio.sleep(2 * current_retry_stream)
             logger.info(f"Retrying stream for {message_id} (ID {encoded_id}) from offset {start_offset}.")
        except Exception as e:
             logger.error(f"Unexpected error during streaming for {message_id} (ID {encoded_id}): {e}", exc_info=True)
             # This is an unexpected error, probably best to abort the request
             return response # Abort this request

    stream_duration = asyncio.get_event_loop().time() - stream_start_time
    expected_bytes_to_serve = (end_offset - start_offset + 1)

    if bytes_streamed == expected_bytes_to_serve:
        logger.info(f"Finished streaming {humanbytes(bytes_streamed)} for {message_id} (ID {encoded_id}) in {stream_duration:.2f}s. Expected: {humanbytes(expected_bytes_to_serve)}.")
    else:
        logger.warning(f"Stream for {message_id} (ID {encoded_id}) ended. Expected to serve {humanbytes(expected_bytes_to_serve)}, actually sent {humanbytes(bytes_streamed)} in {stream_duration:.2f}s.")
        if bytes_streamed == 0 and expected_bytes_to_serve > 0 and status_code != 206: # If it was a full request and nothing sent
             logger.error(f"Failed to stream any data for {message_id} (ID {encoded_id}) for a non-empty file/range.")
             # Consider raising an error if no bytes were streamed for a non-empty file unless it was a client disconnect
             # This part is tricky because client disconnects also result in bytes_streamed < expected_bytes

    total_request_duration = asyncio.get_event_loop().time() - start_time_request
    logger.info(f"Download request for {message_id} (ID {encoded_id}) completed. Total duration: {total_request_duration:.2f}s")
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

    if not bot_client or not bot_client.is_connected:
        return web.json_response({
            "status": "error", "bot_status": "disconnected",
            "message": "Bot client is not currently connected to Telegram.",
            "uptime": format_uptime(start_time), "github_repo": Var.GITHUB_REPO_URL,
            "totaluser": user_count,
        }, status=503)

    try:
        bot_me: User = getattr(bot_client, 'me', None)
        if not bot_me: # Fetch if not cached on client
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
            "totaluser": user_count
        }
        return web.json_response(info_data)
    except Exception as e:
        logger.error(f"Error fetching bot info for API: {e}", exc_info=True)
        return web.json_response({
            "status": "error", "bot_status": "unknown",
            "message": f"An error occurred while fetching bot details: {str(e)}",
            "uptime": format_uptime(start_time), "github_repo": Var.GITHUB_REPO_URL,
            "totaluser": user_count,
        }, status=500)

# --- Logs Endpoint ---
@routes.get("/api/logs")
async def logs_route(request: web.Request):
    """Stream logs from the log file with filtering options."""
    # Security check: require token or admin IP
    token = request.query.get('token')
    client_ip = request.remote
    
    is_authorized = False
    
    # Check token first (preferred method)
    if token and token == Var.LOGS_ACCESS_TOKEN:
        is_authorized = True
        logger.info(f"Logs accessed with valid token from {client_ip}")
    
    # If token check failed, check admin IP
    if not is_authorized and client_ip in Var.ADMIN_IPS:
        is_authorized = True
        logger.info(f"Logs accessed from admin IP {client_ip}")
    
    # If neither passed, reject the request
    if not is_authorized:
        logger.warning(f"Unauthorized logs access attempt from {client_ip}")
        return web.json_response({
            "status": "error",
            "message": "Unauthorized access"
        }, status=403)
    
    # Get query parameters with defaults
    limit = min(int(request.query.get('limit', 100)), 1000)  # Default 100, max 1000 lines
    level = request.query.get('level', 'ALL').upper()  # ALL, DEBUG, INFO, WARNING, ERROR, CRITICAL
    page = max(int(request.query.get('page', 1)), 1)  # Page number, minimum 1
    filter_text = request.query.get('filter', '')  # Text to filter logs by

    # Log file path
    log_file_path = "tgdlbot.log"
    
    # Check if file exists
    if not os.path.exists(log_file_path):
        return web.json_response({
            "status": "error",
            "message": "Log file not found"
        }, status=404)
    
    # Get file size and basic stats
    file_stats = os.stat(log_file_path)
    file_size = file_stats.st_size
    last_modified = datetime.datetime.fromtimestamp(file_stats.st_mtime).isoformat()
    
    # Define log level mapping for filtering
    level_priority = {
        'DEBUG': 0,
        'INFO': 1,
        'WARNING': 2,
        'ERROR': 3,
        'CRITICAL': 4
    }
    
    # Initialize response data
    log_lines = []
    total_matching_lines = 0
    
    # Determine priority level for filtering
    min_level_priority = level_priority.get(level, -1) if level != 'ALL' else -1
    
    try:
        # Read and process logs in a memory-efficient way
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as file:
            matching_lines = []
            
            for line in file:
                # Check if line contains log level indicator
                current_line_level = None
                for lvl in level_priority.keys():
                    if f" - {lvl} - " in line:
                        current_line_level = lvl
                        break
                
                # Apply level filter
                if min_level_priority >= 0 and (current_line_level is None or 
                                              level_priority.get(current_line_level, -1) < min_level_priority):
                    continue
                
                # Apply text filter if specified
                if filter_text and filter_text.lower() not in line.lower():
                    continue
                
                # Count total matching lines for pagination info
                total_matching_lines += 1
                
                # Keep only lines for current page
                if (page - 1) * limit < total_matching_lines <= page * limit:
                    matching_lines.append(line.strip())
            
            log_lines = matching_lines
    except Exception as e:
        logger.error(f"Error reading log file: {e}", exc_info=True)
        return web.json_response({
            "status": "error",
            "message": f"Failed to read log file: {str(e)}"
        }, status=500)
    
    # Calculate pagination info
    total_pages = (total_matching_lines + limit - 1) // limit if total_matching_lines > 0 else 1
    
    # Send response
    return web.json_response({
        "status": "ok",
        "file_info": {
            "path": log_file_path,
            "size_bytes": file_size,
            "size_human": humanbytes(file_size),
            "last_modified": last_modified
        },
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_matching_lines": total_matching_lines
        },
        "filter": {
            "level": level,
            "text": filter_text
        },
        "logs": log_lines
    })

# --- Setup Web App --- (Keep as is, assuming it's working)
async def setup_webapp(bot_instance: Client, client_manager, start_time: datetime.datetime): # Added client_manager
    webapp = web.Application()
    webapp.add_routes(routes)
    webapp['bot_client'] = bot_instance # This is the primary client for general info like /api/info
    webapp['client_manager'] = client_manager # For download routes to get worker clients
    webapp['start_time'] = start_time # type: ignore
    logger.info("Web application routes configured.")
    cors = aiohttp_cors.setup(webapp, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, expose_headers="*", allow_headers="*", allow_methods="*",
        )
    })
    for route in list(webapp.router.routes()):
        cors.add(route)
    logger.info("CORS configured for all routes.")
    return webapp
