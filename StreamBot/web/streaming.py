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
from StreamBot.utils.smart_logger import SmartRateLimitedLogger

logger = logging.getLogger(__name__)
streaming_rate_limited_logger = SmartRateLimitedLogger(logger)

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
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Connection': 'keep-alive',
            'Content-Disposition': 'inline'
        }

        # Handle range requests for video seeking - FIXED CALCULATION
        range_header = request.headers.get('Range')
        status_code = 200
        start_offset = 0
        end_offset = file_size - 1

        if range_header:
            logger.debug(f"Video range request for {message_id}: {range_header}")
            range_result = validate_range_header(range_header, file_size)
            if range_result is None:
                raise web.HTTPRequestRangeNotSatisfiable(
                    headers={'Content-Range': f'bytes */{file_size}'}
                )
            
            start_offset, end_offset = range_result
            
            # IMPORTANT FIX: Only limit response size for very large requests
            # Let the browser request what it needs, but prevent abuse
            requested_size = end_offset - start_offset + 1
            max_reasonable_request = 50 * 1024 * 1024  # 50MB max per request
            
            if requested_size > max_reasonable_request:
                # Only limit if the request is unreasonably large
                end_offset = start_offset + max_reasonable_request - 1
                # Make sure we don't exceed file size
                if end_offset >= file_size:
                    end_offset = file_size - 1
                logger.debug(f"Limited large range request from {requested_size} to {end_offset - start_offset + 1} bytes")
            
            headers['Content-Range'] = f'bytes {start_offset}-{end_offset}/{file_size}'
            headers['Content-Length'] = str(end_offset - start_offset + 1)
            status_code = 206
            logger.debug(f"Serving video range {start_offset}-{end_offset}/{file_size} for {message_id}")
        else:
            headers['Content-Length'] = str(file_size)
            logger.debug(f"Serving full video {file_size} bytes for {message_id}")

        response = web.StreamResponse(status=status_code, headers=headers)
        await response.prepare(request)

        # --- REVISED STREAMING LOGIC ---
        # Using Pyrogram's high-level stream_media for better reliability and seeking.
        chunk_size = 1024 * 1024  # Pyrogram's stream_media uses 1MB chunks.
        
        # Calculate chunk offset and how many bytes to skip in the first chunk.
        start_chunk = start_offset // chunk_size
        skip_bytes = start_offset % chunk_size
        
        # Calculate the total bytes we need to serve for this request.
        bytes_to_serve = end_offset - start_offset + 1

        bytes_streamed = 0
        request_id = f"stream_{message_id}_{encoded_id[:10]}"
        max_retries = 2
        current_retry = 0

        async with tracked_stream_response(response, stream_tracker, request_id):
            while current_retry <= max_retries:
                try:
                    # CRITICAL: Calculate remaining bytes to stream based on what we've already sent
                    # This ensures proper resumption after client switches
                    remaining_bytes = bytes_to_serve - bytes_streamed
                    
                    if remaining_bytes <= 0:
                        # Already streamed everything
                        logger.info(f"All bytes already streamed for video {message_id}. Total: {bytes_streamed}")
                        break
                    
                    # Recalculate chunk offset and skip bytes based on current position (memory-efficient)
                    current_byte_offset = start_offset + bytes_streamed
                    current_start_chunk = current_byte_offset // chunk_size
                    current_skip_bytes = current_byte_offset % chunk_size
                    
                    if bytes_streamed > 0:
                        logger.debug(f"Resuming video stream for {message_id}. Already sent: {bytes_streamed}, Remaining: {remaining_bytes}")
                    
                    # Get the async generator for media chunks.
                    # NOTE: stream_media offset parameter is in chunks, not bytes
                    media_stream = streamer_client.stream_media(
                        media_msg,
                        offset=current_start_chunk  # This is chunk offset, not byte offset
                    )
                    
                    current_chunk = 0
                    async for chunk in media_stream:
                        if not chunk:
                            break  # End of file.

                        # If this is the first chunk from our current position, skip the unneeded bytes from the beginning.
                        if current_chunk == 0:
                            chunk = chunk[current_skip_bytes:]

                        # If this chunk would exceed our byte limit, truncate it.
                        if bytes_streamed + len(chunk) > bytes_to_serve:
                            chunk = chunk[:bytes_to_serve - bytes_streamed]

                        try:
                            await response.write(chunk)
                            bytes_streamed += len(chunk)
                        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
                            logger.debug(f"Client disconnected during video stream {message_id}")
                            return response  # Exit cleanly on client disconnect.
                        except Exception as e:
                            streaming_rate_limited_logger.log(
                                'error',
                                f"Error streaming chunk for {message_id}: {e}"
                            )
                            return response  # Exit on write errors.
                        
                        current_chunk += 1
                        
                        # Stop if we have served all required bytes.
                        if bytes_streamed >= bytes_to_serve:
                            break
                    
                    # If we reach here, streaming completed successfully.
                    break

                except FloodWait as e:
                    logger.warning(f"FloodWait during video stream {message_id}: {e}. Already streamed: {bytes_streamed}")
                    # Try alternative client first before waiting.
                    try:
                        alternative_client = await client_manager.get_alternative_streaming_client(streamer_client)
                        if alternative_client:
                            logger.info(f"Switching from @{streamer_client.me.username} to @{alternative_client.me.username} for {message_id}. Will resume from byte {bytes_streamed}")
                            streamer_client = alternative_client
                            await asyncio.sleep(1)
                            continue  # Retry with new client, will resume from current position
                        else:
                            # No alternative client, wait briefly (cap at 60s for low-resource server)
                            await asyncio.sleep(min(e.value, 60))
                            continue  # Retry with same client after waiting
                    except Exception as alt_e:
                        streaming_rate_limited_logger.log(
                            'error',
                            f"Error switching client for {message_id}: {alt_e}"
                        )
                        await asyncio.sleep(min(e.value, 60))  # Cap wait time
                        continue  # Retry after waiting

                except Exception as e:
                    current_retry += 1
                    streaming_rate_limited_logger.log(
                        'error',
                        f"Error during video streaming {message_id} (attempt {current_retry}): {e}"
                    )
                    if current_retry > max_retries:
                        streaming_rate_limited_logger.log('error', f"Max retries reached for {message_id}, aborting")
                        break
                    await asyncio.sleep(2 * current_retry)  # Exponential backoff

        # Record bandwidth usage
        if bytes_streamed > 0:
            await add_bandwidth_usage(bytes_streamed)

        logger.info(f"Video stream completed for {message_id}: {bytes_streamed} bytes (expected: {bytes_to_serve})")
        return response

    except (web.HTTPNotFound, web.HTTPServiceUnavailable, web.HTTPBadRequest) as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in video streaming {message_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text="Streaming error occurred.")
