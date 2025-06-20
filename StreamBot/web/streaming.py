import logging
import asyncio
import math
from aiohttp import web
from pyrogram.errors import FloodWait
from StreamBot.config import Var
from StreamBot.utils.utils import decode_message_id, get_file_attr, VIDEO_MIME_TYPES, get_media_message
from StreamBot.utils.bandwidth import is_bandwidth_limit_exceeded, add_bandwidth_usage
from StreamBot.utils.stream_cleanup import stream_tracker, tracked_stream_response
from StreamBot.security.validator import validate_range_header, get_client_ip

logger = logging.getLogger(__name__)

@web.middleware
async def cors_handler(request, handler):
    """CORS middleware for streaming endpoints."""
    if request.method == 'OPTIONS':
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                'Access-Control-Allow-Headers': 'Range, Content-Type',
                'Access-Control-Max-Age': '86400'
            }
        )
    
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range, Accept-Ranges'
    return response

async def stream_video_route(request: web.Request):
    """Handle video streaming requests with optimized streaming support."""
    client_manager = request.app.get('client_manager')
    if not client_manager:
        raise web.HTTPServiceUnavailable(text="Service configuration error.")

    encoded_id = request.match_info['encoded_id_str']
    
    if not encoded_id or len(encoded_id) > 100:
        raise web.HTTPBadRequest(text="Invalid stream link format.")
    
    message_id = decode_message_id(encoded_id)
    if message_id is None:
        raise web.HTTPBadRequest(text="Invalid or malformed stream link.")

    logger.info(f"Video stream request for message_id: {message_id} from {get_client_ip(request)}")

    # Check bandwidth limit
    if await is_bandwidth_limit_exceeded():
        raise web.HTTPServiceUnavailable(text="Service temporarily unavailable due to bandwidth limits.")

    try:
        streamer_client = await asyncio.wait_for(
            client_manager.get_streaming_client(),
            timeout=30
        )
        if not streamer_client or not streamer_client.is_connected:
            raise web.HTTPServiceUnavailable(text="Streaming service temporarily unavailable.")

        media_msg = await get_media_message(streamer_client, message_id)
        
        # Get file attributes
        file_id, file_name, file_size, file_mime_type, file_unique_id = get_file_attr(media_msg)
        
        if not file_id:
            raise web.HTTPNotFound(text="File not found or invalid.")

        # Check if file is a video using shared VIDEO_MIME_TYPES
        if file_mime_type not in VIDEO_MIME_TYPES:
            raise web.HTTPBadRequest(text="File is not a streamable video format.")

        # Get ByteStreamer
        byte_streamer = client_manager.get_streamer_for_client(streamer_client)
        if not byte_streamer:
            raise web.HTTPInternalServerError(text="Streaming service not available.")

        # Get file properties
        file_id_obj = await byte_streamer.get_file_properties(message_id)
        file_size = getattr(file_id_obj, 'file_size', file_size)

        if file_size == 0:
            raise web.HTTPBadRequest(text="Invalid video file.")

        # Streaming-optimized headers
        headers = {
            'Content-Type': file_mime_type,
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'public, max-age=3600',
            'Connection': 'keep-alive'
        }

        # Handle range requests for video seeking
        range_header = request.headers.get('Range')
        status_code = 200
        start_offset = 0
        end_offset = file_size - 1

        if range_header:
            range_result = validate_range_header(range_header, file_size)
            if range_result is None:
                raise web.HTTPRequestRangeNotSatisfiable(
                    headers={'Content-Range': f'bytes */{file_size}'}
                )
            
            start_offset, end_offset = range_result
            headers['Content-Range'] = f'bytes {start_offset}-{end_offset}/{file_size}'
            headers['Content-Length'] = str(end_offset - start_offset + 1)
            status_code = 206
        else:
            headers['Content-Length'] = str(file_size)

        response = web.StreamResponse(status=status_code, headers=headers)
        await response.prepare(request)

        # Streaming parameters optimized for video
        chunk_size = 512 * 1024  # 512KB chunks for smoother video streaming
        until_bytes = min(end_offset, file_size - 1)
        offset = start_offset - (start_offset % chunk_size)
        first_part_cut = start_offset - offset
        last_part_cut = until_bytes % chunk_size + 1
        part_count = math.ceil((until_bytes + 1) / chunk_size) - math.floor(offset / chunk_size)

        bytes_streamed = 0
        request_id = f"stream_{message_id}_{encoded_id[:10]}"

        async with tracked_stream_response(response, stream_tracker, request_id):
            try:
                async for chunk in byte_streamer.yield_file(
                    file_id_obj,
                    offset,
                    first_part_cut,
                    last_part_cut,
                    part_count,
                    chunk_size
                ):
                    try:
                        await response.write(chunk)
                        bytes_streamed += len(chunk)
                    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
                        logger.debug(f"Client disconnected during video stream {message_id}")
                        break
                    except Exception as e:
                        logger.error(f"Error streaming chunk for {message_id}: {e}")
                        break

            except FloodWait as e:
                logger.warning(f"FloodWait during video stream {message_id}: {e.value}s")
                # Try alternative client
                try:
                    alternative_client = await client_manager.get_alternative_streaming_client(streamer_client)
                    if alternative_client:
                        logger.info(f"Switching client for video stream {message_id}")
                        streamer_client = alternative_client
                        byte_streamer = client_manager.get_streamer_for_client(streamer_client)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Error during video streaming {message_id}: {e}")

        # Record bandwidth usage
        if bytes_streamed > 0:
            await add_bandwidth_usage(bytes_streamed)

        logger.info(f"Video stream completed for {message_id}: {bytes_streamed} bytes")
        return response

    except (web.HTTPNotFound, web.HTTPServiceUnavailable, web.HTTPBadRequest) as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in video streaming {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Streaming error occurred.")
