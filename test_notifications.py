#!/usr/bin/env python3
"""
Test script for Telegram notification system.
Use this to test if login notifications are working properly.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent / "StreamBot"
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from StreamBot.config import Var
from StreamBot.utils.telegram_notifications import get_telegram_notifier, send_session_notification


async def test_bot_api_connection():
    """Test basic Bot API connection."""
    print("🔗 Testing Telegram Bot API connection...")

    try:
        notifier = get_telegram_notifier()
        success = await notifier.test_bot_connection()

        if success:
            print("✅ Bot API connection successful!")
            return True
        else:
            print("❌ Bot API connection failed!")
            return False

    except Exception as e:
        print(f"❌ Bot API connection error: {e}")
        return False


async def test_send_notification():
    """Test sending a notification message."""
    print("\n📤 Testing notification sending...")

    # Get test user ID from environment or command line
    test_user_id = os.getenv('TEST_USER_ID')
    if not test_user_id:
        if len(sys.argv) > 1:
            test_user_id = sys.argv[1]
        else:
            print("❌ No test user ID provided!")
            print("Set TEST_USER_ID environment variable or pass user ID as argument:")
            print("  export TEST_USER_ID=123456789")
            print("  or")
            print("  python test_notifications.py 123456789")
            return False

    try:
        test_user_id = int(test_user_id)
    except ValueError:
        print(f"❌ Invalid user ID: {test_user_id}")
        return False

    # Mock user info for testing
    test_user_info = {
        'id': test_user_id,
        'first_name': 'Test',
        'last_name': 'User',
        'username': 'testuser',
        'photo_url': None
    }

    print(f"📤 Sending test notification to user {test_user_id}...")

    try:
        success = await send_session_notification(test_user_id, test_user_info)

        if success:
            print("✅ Test notification sent successfully!")
            return True
        else:
            print("❌ Test notification failed!")
            return False

    except Exception as e:
        print(f"❌ Test notification error: {e}")
        return False


async def main():
    """Main test function."""
    print("🧪 Telegram Notification System Test")
    print("=" * 40)

    # Test 1: Bot API connection
    api_success = await test_bot_api_connection()

    if not api_success:
        print("\n❌ Bot API connection failed. Cannot proceed with notification tests.")
        return False

    # Test 2: Send notification (only if API works)
    notification_success = await test_send_notification()

    print("\n" + "=" * 40)
    if api_success and notification_success:
        print("✅ All tests passed! Notification system is working.")
        return True
    elif api_success and not notification_success:
        print("⚠️ Bot API works, but notification sending failed.")
        print("   This could be due to:")
        print("   - User has blocked the bot")
        print("   - Invalid user ID")
        print("   - Network issues")
        return False
    else:
        print("❌ Tests failed. Check your BOT_TOKEN and network connection.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
