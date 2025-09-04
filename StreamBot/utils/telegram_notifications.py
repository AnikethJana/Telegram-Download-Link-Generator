# StreamBot/utils/telegram_notifications.py
"""
Telegram notification utilities for sending messages to users.
Uses Telegram Bot API directly for reliable message delivery.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import aiohttp
from aiohttp import ClientTimeout
from StreamBot.config import Var

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles sending notifications to users via Telegram Bot API."""

    def __init__(self):
        self.bot_token = Var.BOT_TOKEN
        self.base_url = "https://api.telegram.org"
        self.api_url = f"{self.base_url}/bot{self.bot_token}"
        self.timeout = ClientTimeout(total=30)  # 30 second timeout

        # Validate bot token
        if not self.bot_token:
            logger.error("❌ BOT_TOKEN not found in configuration")
            raise ValueError("BOT_TOKEN is required for notifications")

        logger.info("✅ Telegram Notifier initialized with Bot API")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
        retry_count: int = 3
    ) -> bool:
        """
        Send a message to a user via Telegram Bot API.

        Args:
            chat_id: Telegram user ID to send message to
            text: Message text to send
            parse_mode: Message parse mode (Markdown, HTML, etc.)
            disable_web_page_preview: Whether to disable web page preview
            retry_count: Number of retry attempts on failure

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        logger.info(f"📤 Attempting to send message to user {chat_id} (length: {len(text)})")

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }

        for attempt in range(retry_count):
            try:
                logger.debug(f"Sending message attempt {attempt + 1}/{retry_count} to {chat_id}")

                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        f"{self.api_url}/sendMessage",
                        json=payload
                    ) as response:

                        response_data = await response.json()
                        logger.debug(f"Telegram API response: {response.status} - {response_data}")

                        if response.status == 200 and response_data.get("ok"):
                            logger.info(f"✅ Message sent successfully to user {chat_id}")
                            return True
                        else:
                            error_description = response_data.get("description", "Unknown error")
                            logger.warning(f"⚠️ Telegram API error for user {chat_id}: {error_description}")

                            # Check for specific error types
                            if "bot was blocked by the user" in error_description.lower():
                                logger.warning(f"🚫 User {chat_id} has blocked the bot")
                                return False
                            elif "chat not found" in error_description.lower():
                                logger.warning(f"🚫 Chat not found for user {chat_id}")
                                return False
                            elif "user is deactivated" in error_description.lower():
                                logger.warning(f"🚫 User {chat_id} account is deactivated")
                                return False
                            else:
                                # Retry for other errors
                                if attempt < retry_count - 1:
                                    wait_time = (attempt + 1) * 2  # Exponential backoff
                                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    logger.error(f"❌ Failed to send message to user {chat_id} after {retry_count} attempts")
                                    return False

            except aiohttp.ClientError as e:
                logger.warning(f"🌐 Network error sending message to {chat_id} (attempt {attempt + 1}): {e}")
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue

            except Exception as e:
                logger.error(f"❌ Unexpected error sending message to {chat_id}: {e}", exc_info=True)
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue

        logger.error(f"❌ All {retry_count} attempts failed to send message to user {chat_id}")
        return False

    async def send_session_success_notification(self, user_id: int, user_info: Dict[str, Any]) -> bool:
        """
        Send a welcome message to user after successful session generation.

        Args:
            user_id: Telegram user ID
            user_info: User information dictionary

        Returns:
            bool: True if notification sent successfully
        """
        logger.info(f"🎉 Preparing session success notification for user {user_id}")

        # Get user name
        first_name = user_info.get('first_name', 'User')
        last_name = user_info.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()

        welcome_message = f"""✅ **Session Generated Successfully!**

Hello {first_name}! 👋 Your session has been created and securely stored.

**🎯 What you can do now:**
• Share private channel/group post URLs with me
• Get instant download links for private content
• Use `/logout` to remove your session anytime

**🔒 Privacy & Security:**
• Your session is encrypted and secure
• Only used to access content you share with me
• No access to your personal messages or data

**⚠️ Important Reminder:**
Using session-based access with newer accounts, downloading large files continuously, abusing the service, or sharing access with others who spam downloads may result in your Telegram account being banned. Please use responsibly and avoid excessive usage patterns that could trigger Telegram's anti-abuse systems.

**📝 Need Help?**
Just send me a private post URL and I'll generate a download link for you!"""

        return await self.send_message(
            chat_id=user_id,
            text=welcome_message,
            parse_mode="Markdown"
        )

    async def test_bot_connection(self) -> bool:
        """
        Test if the bot can connect to Telegram API.

        Returns:
            bool: True if connection successful
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.api_url}/getMe") as response:
                    response_data = await response.json()

                    if response.status == 200 and response_data.get("ok"):
                        bot_info = response_data.get("result", {})
                        logger.info(f"✅ Bot connection test successful: @{bot_info.get('username', 'unknown')}")
                        return True
                    else:
                        logger.error(f"❌ Bot connection test failed: {response_data}")
                        return False

        except Exception as e:
            logger.error(f"❌ Bot connection test error: {e}")
            return False


# Global notifier instance
_telegram_notifier = None

def get_telegram_notifier() -> TelegramNotifier:
    """Get or create the global Telegram notifier instance."""
    global _telegram_notifier
    if _telegram_notifier is None:
        try:
            _telegram_notifier = TelegramNotifier()
            logger.info("✅ Telegram Notifier instance created")
        except Exception as e:
            logger.error(f"❌ Failed to create Telegram Notifier: {e}")
            raise
    return _telegram_notifier

async def send_session_notification(user_id: int, user_info: Dict[str, Any]) -> bool:
    """
    Convenience function to send session success notification.

    Args:
        user_id: Telegram user ID
        user_info: User information dictionary

    Returns:
        bool: True if notification sent successfully
    """
    try:
        notifier = get_telegram_notifier()
        return await notifier.send_session_success_notification(user_id, user_info)
    except Exception as e:
        logger.error(f"❌ Error in send_session_notification: {e}")
        return False
