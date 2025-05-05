# StreamBot/web.py
import re
import logging
import asyncio
import datetime
from aiohttp import web
import aiohttp_cors 
from pyrogram import Client
from pyrogram.errors import FloodWait, FileIdInvalid, RPCError
from pyrogram.types import Message, User

from config import Var
from utils import get_file_attr, humanbytes 

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# Chunk size for streaming (pyrogram handles chunking, this is less critical now but kept for reference)
# CHUNK_SIZE = 1024 * 1024 * 1 # 1 MB chunks

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

# --- Helper to get message and check expiry --- (keep as is)
async def get_media_message(bot_client: Client, message_id: int) -> Message:
    """Fetches the media message object from the LOG_CHANNEL and checks expiry."""
    if not bot_client or not bot_client.is_connected:
        logger.error("Bot client is not available or connected.")
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
        except (ConnectionError, RPCError, TimeoutError) as e:
            if current_retry == max_retries - 1:
                logger.error(f"Max retries reached for network/RPC error getting message {message_id}: {e}. Aborting.")
                raise web.HTTPServiceUnavailable(text="Temporary issue communicating with Telegram. Please try again later.")
            sleep_duration = 5 * (current_retry + 1)
            logger.warning(f"Network/RPC error getting message {message_id}: {e}. Retrying in {sleep_duration}s (Attempt {current_retry+1}/{max_retries}).")
            await asyncio.sleep(sleep_duration)
            current_retry += 1
        except Exception as e:
            logger.error(f"Unexpected error getting message {message_id} from {Var.LOG_CHANNEL}: {e}", exc_info=True)
            raise web.HTTPInternalServerError(text=f"Could not retrieve file details: An internal error occurred.")

    if not media_msg:
        # This case should ideally be covered by the retries raising exceptions
        logger.error(f"Failed to retrieve message {message_id} after retries, but no exception was raised.")
        raise web.HTTPServiceUnavailable(text="Failed to retrieve file details after multiple retries.")

    # --- Link Expiry Check ---
    if hasattr(media_msg, 'date') and isinstance(media_msg.date, datetime.datetime):
        message_timestamp = media_msg.date.replace(tzinfo=datetime.timezone.utc)
        current_timestamp = datetime.datetime.now(datetime.timezone.utc)
        time_difference = current_timestamp - message_timestamp
        expiry_seconds = Var.LINK_EXPIRY_SECONDS
        if time_difference.total_seconds() > expiry_seconds:
            logger.warning(f"Download link for message {message_id} expired. Age: {time_difference} > {expiry_seconds}s")
            raise web.HTTPGone(text=Var.LINK_EXPIRED_TEXT) 
    else:
        logger.warning(f"Could not determine message timestamp for message {message_id}. Skipping expiry check.")

    return media_msg

# --- Download Route (Refactored) ---
@routes.get("/dl/{message_id}")
async def download_route(request: web.Request):
    """Handles the download request, streaming the file (Refactored)."""
    bot_client: Client = request.app['bot_client']

    try:
        message_id = int(request.match_info['message_id'])
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid message ID format.")

    try:
        media_msg = await get_media_message(bot_client, message_id)
    except (web.HTTPNotFound, web.HTTPServiceUnavailable, web.HTTPTooManyRequests, web.HTTPGone, web.HTTPInternalServerError) as e:
        
        raise e
    except Exception as e:
        logger.error(f"Unexpected error retrieving/checking message {message_id} for download: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Failed to retrieve file information.")

    _file_id, file_name, file_size, file_mime_type, _ = get_file_attr(media_msg)

    if file_size is None or file_name is None:
        logger.error(f"Could not extract file attributes from message {message_id}.")
        raise web.HTTPInternalServerError(text="Failed to get file details from message.")

    headers = {
        'Content-Type': file_mime_type or 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{file_name}"',
        'Accept-Ranges': 'bytes' 
        # Content-Length will be set based on whether it's a range request or full file
    }

    range_header = request.headers.get('Range')
    status_code = 200
    start_offset = 0
    end_offset = file_size - 1 
    is_range_request = False

    if range_header:
        try:
            # Attempt to parse range header (e.g., "bytes=0-499", "bytes=500-", "bytes=-500")
            range_match = re.match(r'bytes=(\d+)?-(\d+)?', range_header)
            if not range_match:
                 raise ValueError("Malformed Range header")

            req_start, req_end = range_match.groups()

            if req_start is None and req_end is None:
                 raise ValueError("Invalid Range header: must specify start or end")

            if req_start is not None:
                 start_offset = int(req_start)
                 if req_end is not None:
                     end_offset = int(req_end)
                 
            elif req_end is not None:
                 
                 start_offset = max(0, file_size - int(req_end))
                 # end_offset remains file_size - 1

            # Validate offsets
            if start_offset >= file_size or start_offset < 0 or end_offset < start_offset or end_offset >= file_size:
                 raise ValueError(f"Invalid range: {start_offset}-{end_offset} for file size {file_size}")

            # Update headers for partial content
            headers['Content-Range'] = f'bytes {start_offset}-{end_offset}/{file_size}'
            headers['Content-Length'] = str(end_offset - start_offset + 1)
            status_code = 206 
            is_range_request = True
            logger.info(f"Serving range request for {message_id}: bytes {start_offset}-{end_offset}")

        except ValueError as e:
             logger.error(f"Invalid Range header value '{range_header}': {e}")
             
             raise web.HTTPRequestRangeNotSatisfiable(headers={'Content-Range': f'bytes */{file_size}'})
    else:
        # Full file request
        headers['Content-Length'] = str(file_size)
        # logger.info(f"Serving full download request for {message_id}")

    # --- Prepare Streaming Response ---
    response = web.StreamResponse(status=status_code, headers=headers)
    await response.prepare(request) 

    # --- Stream the Data ---
    bytes_streamed = 0
    stream_start_time = asyncio.get_event_loop().time()
    max_retries_stream = 2 
    current_retry_stream = 0

    # Calculate limit for stream_media if it's a range request
    # stream_media's 'limit' is number of bytes *from the offset*
    stream_limit = (end_offset - start_offset + 1) if is_range_request else 0 

    while current_retry_stream <= max_retries_stream:
        try:
            # Use offset and limit parameters in stream_media
            async for chunk in bot_client.stream_media(
                media_msg,
                offset=start_offset,
                limit=stream_limit
                ):
                try:
                    bytes_streamed += len(chunk)
                    await response.write(chunk)
                    # Optional: Add a small sleep to prevent overwhelming the event loop on very fast streams
                    # await asyncio.sleep(0.001)
                except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError) as client_e:
                     
                     logger.warning(f"Client connection issue during write for {message_id}: {type(client_e).__name__}. Aborting stream.")
                     return response 
                except Exception as write_e:
                     logger.error(f"Error writing chunk for {message_id}: {write_e}", exc_info=True)
                     raise web.HTTPInternalServerError(text="Error sending file data.")

            
            break

        except FloodWait as e:
             logger.warning(f"FloodWait during stream for {message_id}. Waiting {e.value}s.")
             await asyncio.sleep(e.value + 2)
             

        except (ConnectionError, TimeoutError, RPCError) as e:
             current_retry_stream += 1
             logger.warning(f"Stream interrupted for {message_id} (Attempt {current_retry_stream}/{max_retries_stream}): {type(e).__name__}. Retrying...")
             if current_retry_stream > max_retries_stream:
                  logger.error(f"Max retries reached. Aborting stream for {message_id} after {humanbytes(bytes_streamed)} bytes.")
                  return response
             await asyncio.sleep(2 * current_retry_stream)
             logger.info(f"Retrying stream for {message_id} from offset {start_offset}.")
        except Exception as e:
             logger.error(f"Unexpected error during streaming for {message_id}: {e}", exc_info=True)
             return response

    stream_duration = asyncio.get_event_loop().time() - stream_start_time
    expected_bytes = end_offset - start_offset + 1 if is_range_request else file_size
    if bytes_streamed == expected_bytes:
        logger.info(f"Finished streaming {humanbytes(bytes_streamed)} for {message_id} in {stream_duration:.2f}s.")
    else:
         logger.warning(f"Stream for {message_id} ended. Expected {humanbytes(expected_bytes)}, sent {humanbytes(bytes_streamed)} in {stream_duration:.2f}s.")

    return response


# --- API Info Route --- 
@routes.get("/api/info")
async def api_info_route(request: web.Request):
    """Provides bot status and information via API."""
    bot_client: Client = request.app['bot_client']
    start_time: datetime.datetime = request.app['start_time']

    if not bot_client or not bot_client.is_connected:
        # Return basic info even if bot is down, but indicate status
        return web.json_response({
            "status": "error",
            "bot_status": "disconnected",
            "message": "Bot client is not currently connected to Telegram.",
            "uptime": format_uptime(start_time),
            "github_repo": Var.GITHUB_REPO_URL,
        }, status=503) 

    try:
        bot_me: User = getattr(bot_client, 'me', None)
        if not bot_me:
            bot_me = await bot_client.get_me() 
            setattr(bot_client, 'me', bot_me) 

        features = {
             "force_subscribe": bool(Var.FORCE_SUB_CHANNEL),
             "force_subscribe_channel": Var.FORCE_SUB_CHANNEL if Var.FORCE_SUB_CHANNEL else None,
             "link_expiry_enabled": True, # Assumed always enabled by design
             "link_expiry_duration_seconds": Var.LINK_EXPIRY_SECONDS,
             "link_expiry_duration_human": Var._human_readable_duration(Var.LINK_EXPIRY_SECONDS) # Use dynamic helper
        }

        # Prepare data payload
        info_data = {
            "status": "ok",
            "bot_status": "connected",
            "bot_info": {
                "id": bot_me.id,
                "username": bot_me.username,
                "first_name": bot_me.first_name,
                "mention": bot_me.mention
            },
            "features": features,
            "uptime": format_uptime(start_time),
            "github_repo": Var.GITHUB_REPO_URL,
            "server_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        return web.json_response(info_data)

    except Exception as e:
        logger.error(f"Error fetching bot info for API: {e}", exc_info=True)
        return web.json_response({
            "status": "error",
            "bot_status": "unknown", # Status uncertain if get_me failed
            "message": f"An error occurred while fetching bot details: {str(e)}",
            "uptime": format_uptime(start_time),
            "github_repo": Var.GITHUB_REPO_URL,
        }, status=500) 

# --- Setup Web App --- (keep as is, ensure CORS is added below)
async def setup_webapp(bot_instance: Client, start_time: datetime.datetime):
    """Creates and configures the aiohttp web application."""
    webapp = web.Application()
    webapp.add_routes(routes)
    # Store the bot client instance and start time in the app context
    webapp['bot_client'] = bot_instance
    webapp['start_time'] = start_time
    logger.info("Web application routes configured.")

    # --- Configure CORS ---
    # Allow requests from any origin for the API endpoint.
    # For production, you should restrict this to your frontend's domain(s).
    cors = aiohttp_cors.setup(webapp, defaults={
        "*": aiohttp_cors.ResourceOptions( 
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*",
        )
    })
    
    # Apply CORS settings to all registered routes
    for route in list(webapp.router.routes()):
        cors.add(route)
    logger.info("CORS configured for all routes.")

    return webapp