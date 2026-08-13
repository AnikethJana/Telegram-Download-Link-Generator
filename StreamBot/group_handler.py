"""
Group message and command handlers for Telegram Download Link Generator.

This module processes commands and file requests in authorized Telegram group chats.
To prevent spam, link generation in groups is explicitly triggered via `/gen` or
`/gen@botusername` when replying to a message with media/link, sending a file with
caption `/gen`, or passing a t.me post URL.
"""

import re
import urllib.parse
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from .config import Var
from .database.group_access import (
    is_group_authorized,
    add_authorized_group,
    remove_authorized_group,
    get_all_authorized_groups,
)
from .database.user_access import is_user_admin
from .database.analytics import record_link_generated
from .utils.utils import (
    get_file_attr,
    humanbytes,
    encode_message_id,
    is_video_file,
    process_link,
)
from .link_handler import get_message_from_link, parse_message_link

logger = logging.getLogger(__name__)


def is_privileged_user(user_id: int) -> bool:
    """Check if user is owner or configured admin."""
    if user_id == Var.OWNER_ID:
        return True
    return bool(Var.ADMINS) and user_id in Var.ADMINS


async def check_admin_privileges(user_id: int) -> bool:
    """Check admin access via config, owner ID, or dynamic admins DB."""
    if is_privileged_user(user_id):
        return True
    return await is_user_admin(user_id)


def attach_group_handlers(app: Client) -> None:
    """Attach all group command and message handlers to Pyrogram client."""
    logger.info("Attaching group command and message handlers...")

    @app.on_message(filters.command(["gen", "gen@"]) & filters.group)
    async def gen_command_group_handler(client: Client, message: Message) -> None:
        """
        Handle /gen and /gen@botusername in group chats.
        
        Triggers link generation for:
        1. Replied message with file/media or t.me post link.
        2. Media uploaded directly with /gen caption.
        3. /gen <t.me link> text command.
        """
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0

        # Verify group authorization
        if not await is_group_authorized(chat_id):
            logger.warning(f"Unauthorized group {chat_id} ('{message.chat.title}') attempted /gen command.")
            await message.reply_text(
                "❌ **Group Not Authorized**\n\n"
                "This group is not authorized to use the download link generator bot.\n"
                "Please contact the bot owner to authorize this group.",
                quote=True,
            )
            return

        target_message = None
        tme_link = None

        # Case 1: Message is a reply to another message
        if message.reply_to_message:
            rep = message.reply_to_message
            if rep.media:
                target_message = rep
            else:
                text_content = rep.text or rep.caption or ""
                url_match = re.search(r"https?://t\.me/\S+", text_content)
                if url_match:
                    tme_link = url_match.group(0)

        # Case 2: Current message has media attached (caption /gen)
        elif message.media:
            target_message = message

        # Case 3: Command contains t.me URL argument
        elif message.text:
            url_match = re.search(r"https?://t\.me/\S+", message.text)
            if url_match:
                tme_link = url_match.group(0)

        # Case 4: No valid media or link target found
        if not target_message and not tme_link:
            bot_username = getattr(client.me, "username", "bot") if hasattr(client, "me") and client.me else "bot"
            await message.reply_text(
                "ℹ️ **How to use `/gen` in group:**\n\n"
                "1️⃣ **Reply to a file/video** with `/gen` or `/gen@" + bot_username + "`\n"
                "2️⃣ **Reply to a Telegram link** (`t.me/...`) with `/gen`\n"
                "3️⃣ **Send link**: `/gen https://t.me/...`\n"
                "4️⃣ **Upload File**: Add `/gen` in file caption",
                quote=True,
            )
            return

        processing_msg = await message.reply_text("⏳ Generating link...", quote=True)

        # Handle t.me post link processing
        if tme_link:
            # First attempt: If the bot is a member/admin in the source channel/group,
            # fetch the message directly using the bot client.
            parsed_link = parse_message_link(tme_link)
            if parsed_link:
                c_id, m_id = parsed_link
                try:
                    bot_fetched = await client.get_messages(chat_id=c_id, message_ids=m_id)
                    if bot_fetched and bot_fetched.media:
                        logger.info(f"Bot client successfully fetched channel message directly from chat {c_id}")
                        target_message = bot_fetched
                        tme_link = None  # Fall through to direct target_message processing below!
                except Exception as ex:
                    logger.debug(f"Bot client direct fetch failed for channel {c_id}: {ex}; trying user session fallback.")

        if tme_link:
            try:
                result = await get_message_from_link(user_id, tme_link)
                if isinstance(result, str):
                    await processing_msg.edit_text(f"❌ **Error:** {result}")
                    return

                target_msg, user_client = result
                _file_id, file_name, file_size, file_mime_type, _file_unique_id = get_file_attr(target_msg)
                file_size_str = humanbytes(file_size)

                if not file_name:
                    await processing_msg.edit_text("❌ **Error:** Could not determine file information.")
                    return

                virtual_msg_id = f"user_{user_id}_{target_msg.chat.id}_{target_msg.id}"
                if not hasattr(client, 'user_session_files'):
                    client.user_session_files = {}

                client.user_session_files[virtual_msg_id] = {
                    'user_id': user_id,
                    'chat_id': target_msg.chat.id,
                    'message_id': target_msg.id,
                    'file_name': file_name,
                    'file_size': file_size,
                    'file_mime_type': file_mime_type,
                    'created_at': asyncio.get_event_loop().time()
                }

                encoded_msg_id = encode_message_id(virtual_msg_id)
                download_link = f"{Var.BASE_URL}/dl/{encoded_msg_id}"

                await record_link_generated(
                    encoded_id=encoded_msg_id,
                    user_id=user_id,
                    file_name=file_name,
                    file_size=file_size,
                    source="group_session_link",
                    user_profile={
                        "username": getattr(message.from_user, "username", "") or "",
                        "first_name": getattr(message.from_user, "first_name", "") or "",
                    },
                )

                processed_download_link = process_link(download_link, file_size, user_id=user_id)
                reply_markup = None
                if is_video_file(file_mime_type) and Var.VIDEO_FRONTEND_URL:
                    encoded_stream_uri = urllib.parse.quote(download_link)
                    video_play_url = f"{Var.VIDEO_FRONTEND_URL}?stream={encoded_stream_uri}"
                    video_play_url = process_link(video_play_url, file_size, user_id=user_id)
                    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Play Video", url=video_play_url)]])

                await processing_msg.edit_text(
                    f"✅ **Download Link Generated!**\n\n"
                    f"**File Name:** `{file_name}`\n"
                    f"**File Size:** {file_size_str}\n\n"
                    f"**Download Link:** {processed_download_link}",
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
                return
            except Exception as e:
                logger.error(f"Error handling group t.me link {tme_link}: {e}", exc_info=True)
                await processing_msg.edit_text("❌ **Error:** Failed to process Telegram link.")
                return

        # Handle direct target media message
        if target_message:
            if not Var.LOG_CHANNEL:
                logger.error("LOG_CHANNEL is not configured.")
                await processing_msg.edit_text("❌ Bot configuration error: LOG_CHANNEL not set.")
                return

            try:
                log_msg = await target_message.forward(chat_id=Var.LOG_CHANNEL)
                if not log_msg or not log_msg.id:
                    await processing_msg.edit_text(Var.ERROR_TEXT)
                    return

                _file_id, file_name, file_size, file_mime_type, _file_unique_id = get_file_attr(log_msg)
                file_size_str = humanbytes(file_size)
                if not file_name:
                    await processing_msg.edit_text(Var.ERROR_TEXT)
                    return

                encoded_msg_id = encode_message_id(log_msg.id)
                download_link = f"{Var.BASE_URL}/dl/{encoded_msg_id}"

                await record_link_generated(
                    encoded_id=encoded_msg_id,
                    user_id=user_id,
                    file_name=file_name,
                    file_size=file_size,
                    source="group_uploaded_media",
                    user_profile={
                        "username": getattr(message.from_user, "username", "") or "",
                        "first_name": getattr(message.from_user, "first_name", "") or "",
                    },
                )

                processed_download_link = process_link(download_link, file_size, user_id=user_id)
                reply_markup = None
                if is_video_file(file_mime_type) and Var.VIDEO_FRONTEND_URL:
                    encoded_stream_uri = urllib.parse.quote(download_link)
                    video_play_url = f"{Var.VIDEO_FRONTEND_URL}?stream={encoded_stream_uri}"
                    video_play_url = process_link(video_play_url, file_size, user_id=user_id)
                    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Play Video", url=video_play_url)]])

                await processing_msg.edit_text(
                    f"✅ **Download Link Generated!**\n\n"
                    f"**File Name:** `{file_name}`\n"
                    f"**File Size:** {file_size_str}\n\n"
                    f"**Download Link:** {processed_download_link}",
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Error handling group target media message: {e}", exc_info=True)
                await processing_msg.edit_text(Var.ERROR_TEXT)

    # Group/Channel Admin Management Commands: /addgroup, /addchannel, /rmgroup, /rmchannel, /groups
    @app.on_message(filters.command(["addgroup", "addgroup@", "addchannel", "addchannel@"]))
    async def add_group_command(client: Client, message: Message) -> None:
        """Authorize a group or channel ID for link generation (Admins only)."""
        user_id = message.from_user.id if message.from_user else 0
        if not await check_admin_privileges(user_id):
            await message.reply_text("❌ Only authorized admins can use this command.", quote=True)
            return

        target_chat_id = None
        target_title = ""

        # Check command args: /addgroup <chat_id> or /addchannel <chat_id>
        cmd_args = message.text.split(maxsplit=1)
        if len(cmd_args) > 1 and cmd_args[1].strip():
            try:
                target_chat_id = int(cmd_args[1].strip())
                # Try fetching chat details to get title if bot is already a member
                try:
                    chat_info = await client.get_chat(target_chat_id)
                    if chat_info and chat_info.title:
                        target_title = chat_info.title
                except Exception:
                    pass
            except ValueError:
                await message.reply_text("❌ Invalid ID. Must be an integer (e.g. `-1001234567890`).", quote=True)
                return
        elif getattr(message.chat, "type", None) in ("group", "supergroup", "channel"):
            target_chat_id = message.chat.id
            target_title = getattr(message.chat, "title", "") or ""
        else:
            await message.reply_text("Usage: `/addgroup <id>` or `/addchannel <id>` (or run inside group/channel).", quote=True)
            return

        success = await add_authorized_group(target_chat_id, title=target_title, added_by=user_id)
        if success:
            await message.reply_text(
                f"✅ **Chat Authorized Successfully!**\n\n"
                f"**ID:** `{target_chat_id}`\n"
                f"**Title:** {target_title or 'N/A'}",
                quote=True,
            )
        else:
            await message.reply_text("❌ Failed to add group/channel to database.", quote=True)

    @app.on_message(filters.command(["rmgroup", "rmgroup@", "rmchannel", "rmchannel@"]))
    async def remove_group_command(client: Client, message: Message) -> None:
        """Revoke group/channel authorization (Admins only)."""
        user_id = message.from_user.id if message.from_user else 0
        if not await check_admin_privileges(user_id):
            await message.reply_text("❌ Only authorized admins can use this command.", quote=True)
            return

        target_chat_id = None

        cmd_args = message.text.split(maxsplit=1)
        if len(cmd_args) > 1 and cmd_args[1].strip():
            try:
                target_chat_id = int(cmd_args[1].strip())
            except ValueError:
                await message.reply_text("❌ Invalid ID. Must be an integer.", quote=True)
                return
        elif getattr(message.chat, "type", None) in ("group", "supergroup", "channel"):
            target_chat_id = message.chat.id
        else:
            await message.reply_text("Usage: `/rmgroup <id>` or `/rmchannel <id>`.", quote=True)
            return

        success = await remove_authorized_group(target_chat_id)
        if success:
            await message.reply_text(f"✅ Authorization revoked for ID `{target_chat_id}`.", quote=True)
        else:
            await message.reply_text(f"⚠️ Chat ID `{target_chat_id}` was not found in authorized database.", quote=True)

    @app.on_message(filters.command(["groups", "groups@"]))
    async def list_groups_command(client: Client, message: Message) -> None:
        """List all authorized groups (Admins only)."""
        user_id = message.from_user.id if message.from_user else 0
        if not await check_admin_privileges(user_id):
            await message.reply_text("❌ Only authorized admins can use this command.", quote=True)
            return

        groups_list = await get_all_authorized_groups()
        if not groups_list:
            await message.reply_text("ℹ️ No authorized groups configured.", quote=True)
            return

        text = "👥 **Authorized Groups List**\n\n"
        for g in groups_list:
            gid = g.get("_id")
            title = g.get("title") or "Group"
            source = g.get("source", "db")
            text += f"• `{gid}` — **{title}** ({source})\n"

        await message.reply_text(text, quote=True)
