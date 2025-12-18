import math
import asyncio
import logging
from StreamBot.config import Var
from typing import Dict, Union, AsyncGenerator
from pyrogram import Client, utils, raw
from .file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId, FileType, ThumbnailSource

logger = logging.getLogger("streamer")

class ByteStreamer:
    def __init__(self, client: Client):
        """A custom class that holds the cache of a specific client and class functions.
        attributes:
            client: the client that the cache is for.
            cached_file_ids: a dict of cached file IDs.
            cached_file_properties: a dict of cached file properties.
        
        functions:
            generate_file_properties: returns the properties for a media of a specific message contained in Tuple.
            generate_media_session: returns the media session for the DC that contains the media file.
            yield_file: yield a file from telegram servers for streaming.
            
        This is a modified version of the WebStreamer implementation to fix offset errors.
        """
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, message_id: int) -> FileId:
        """
        Returns the properties of a media of a specific message in a FileId class.
        if the properties are cached, then it'll return the cached results.
        or it'll generate the properties from the Message ID and cache them.
        """
        if message_id not in self.cached_file_ids:
            await self.generate_file_properties(message_id)
            logger.debug(f"Cached file properties for message with ID {message_id}")
        return self.cached_file_ids[message_id]
    
    async def generate_file_properties(self, message_id: int) -> FileId:
        """
        Generates the properties of a media file on a specific message.
        returns the properties in a FileId class.
        """
        file_id = await get_file_ids(self.client, Var.LOG_CHANNEL, message_id)
        logger.debug(f"Generated file ID and Unique ID for message with ID {message_id}")
        if not file_id:
            logger.debug(f"Message with ID {message_id} not found")
            raise FileNotFoundError(f"Message {message_id} not found")
        self.cached_file_ids[message_id] = file_id
        logger.debug(f"Cached media message with ID {message_id}")
        return self.cached_file_ids[message_id]

    async def generate_media_session(self, client: Client, file_id: FileId) -> Session:
        """
        Creates or retrieves a media session for the specified data center.
        Media sessions are necessary to download file bytes from Telegram.
        """
        target_dc = file_id.dc_id
        
        # Return existing session if already cached
        if target_dc in client.media_sessions:
            logger.debug(f"Using cached media session for DC {target_dc}")
            return client.media_sessions[target_dc]
        
        # Determine if we need cross-DC authorization
        storage_dc = await client.storage.dc_id()
        test_mode = await client.storage.test_mode()
        requires_auth_transfer = (target_dc != storage_dc)
        
        # Create session based on DC location
        if requires_auth_transfer:
            # Cross-DC session requires authorization export
            auth_key = await Auth(client, target_dc, test_mode).create()
            new_session = Session(client, target_dc, auth_key, test_mode, is_media=True)
            await new_session.start()
            
            # Attempt authorization transfer with retries
            auth_success = False
            for attempt in range(6):
                auth_data = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=target_dc)
                )
                
                try:
                    await new_session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=auth_data.id, bytes=auth_data.bytes
                        )
                    )
                    auth_success = True
                    break
                except AuthBytesInvalid:
                    logger.debug(f"Auth transfer failed for DC {target_dc}, attempt {attempt + 1}/6")
                    
            if not auth_success:
                await new_session.stop()
                raise AuthBytesInvalid
        else:
            # Same-DC session uses existing auth key
            auth_key = await client.storage.auth_key()
            new_session = Session(client, target_dc, auth_key, test_mode, is_media=True)
            await new_session.start()
        
        # Cache and return the new session
        logger.debug(f"Created media session for DC {target_dc}")
        client.media_sessions[target_dc] = new_session
        return new_session

    @staticmethod
    async def get_location(file_id: FileId) -> Union[raw.types.InputPhotoFileLocation,
                                                     raw.types.InputDocumentFileLocation,
                                                     raw.types.InputPeerPhotoFileLocation,]:
        """
        Constructs the appropriate Telegram file location object based on file type.
        """
        media_type = file_id.file_type
        
        # Handle standard photo files
        if media_type == FileType.PHOTO:
            return raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        
        # Handle chat/profile photos with peer-based location
        if media_type == FileType.CHAT_PHOTO:
            chat_identifier = file_id.chat_id
            access_hash_value = file_id.chat_access_hash
            
            # Determine peer type based on chat identifier
            if chat_identifier > 0:
                # Positive ID indicates user
                peer_obj = raw.types.InputPeerUser(
                    user_id=chat_identifier, access_hash=access_hash_value
                )
            elif access_hash_value == 0:
                # No access hash means basic chat
                peer_obj = raw.types.InputPeerChat(chat_id=-chat_identifier)
            else:
                # Negative ID with access hash indicates channel
                peer_obj = raw.types.InputPeerChannel(
                    channel_id=utils.get_channel_id(chat_identifier),
                    access_hash=access_hash_value,
                )
            
            is_big_photo = (file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG)
            return raw.types.InputPeerPhotoFileLocation(
                peer=peer_obj,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=is_big_photo,
            )
        
        # Default: handle documents, videos, audio, etc.
        return raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size,
        )

    async def yield_file(
        self,
        file_id: FileId,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
    ) -> AsyncGenerator[bytes, None]:
        """
        Custom generator that yields the bytes of the media file.
        Modified from WebStreamer implementation to fix offset errors.
        """
        client = self.client
        logger.debug(f"Starting to yield file with client {client.me.username}.")
        media_session = await self.generate_media_session(client, file_id)

        current_part = 1
        location = await self.get_location(file_id)

        try:
            r = await media_session.invoke(
                raw.functions.upload.GetFile(
                    location=location, offset=offset, limit=chunk_size
                ),
            )
            if isinstance(r, raw.types.upload.File):
                while True:
                    chunk = r.bytes
                    if not chunk:
                        break
                    elif part_count == 1:
                        yield chunk[first_part_cut:last_part_cut]
                    elif current_part == 1:
                        yield chunk[first_part_cut:]
                    elif current_part == part_count:
                        yield chunk[:last_part_cut]
                    else:
                        yield chunk

                    current_part += 1
                    offset += chunk_size

                    if current_part > part_count:
                        break

                    r = await media_session.invoke(
                        raw.functions.upload.GetFile(
                            location=location, offset=offset, limit=chunk_size
                        ),
                    )
        except (TimeoutError, AttributeError):
            pass
        finally:
            logger.debug(f"Finished yielding file with {current_part} parts.")

    async def clean_cache(self) -> None:
        """
        Periodic task that clears cached file IDs to prevent memory buildup.
        Runs continuously in the background at intervals defined by clean_timer.
        """
        while True:
            # Wait for the cleanup interval
            await asyncio.sleep(self.clean_timer)
            
            # Remove all cached file ID entries
            self.cached_file_ids.clear()
            logger.debug("Cache cleanup completed - all file IDs cleared") 