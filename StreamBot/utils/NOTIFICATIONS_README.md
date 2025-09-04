# Telegram Notification System

This document explains how the login notification system works and how to troubleshoot issues.

## Overview

The notification system sends welcome messages to users after they successfully generate a session through the web interface. It uses a dual-method approach for maximum reliability:

1. **Primary Method**: Telegram Bot API (`sendMessage`)
2. **Fallback Method**: Pyrogram client (`send_message`)

## How It Works

### 1. Telegram Bot API Method (Primary)
- Uses the official Telegram Bot API directly
- More reliable and doesn't depend on Pyrogram client state
- Includes retry logic and proper error handling
- Supports Markdown formatting

### 2. Pyrogram Method (Fallback)
- Uses the existing Pyrogram client setup
- Falls back to this method if Bot API fails
- Maintains compatibility with existing code

## Configuration

The system uses the `BOT_TOKEN` from your environment variables (same as the main bot).

## Testing

### Startup Test
The system automatically tests itself during application startup:
```
🧪 Testing notification system...
✅ Notification system test passed - Bot API connection successful
```

### Manual Testing
Use the test script to manually verify the system:

```bash
# Test with environment variable
export TEST_USER_ID=123456789
python test_notifications.py

# Or pass user ID as argument
python test_notifications.py 123456789
```

## Troubleshooting

### Common Issues

#### 1. "Bot API connection test failed"
**Cause**: Bot token is invalid or network issues
**Solution**:
- Verify `BOT_TOKEN` in your `.env` file
- Check network connectivity
- Ensure bot token format is correct: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`

#### 2. "User has blocked the bot"
**Cause**: User blocked your bot
**Solution**:
- User needs to unblock the bot
- Check bot username and ensure it's correct
- Verify the user ID is valid

#### 3. "Chat not found"
**Cause**: Invalid user ID or user never started the bot
**Solution**:
- Verify the user ID is correct
- User must have started a conversation with the bot at least once
- Check if the user ID is a valid Telegram user ID (usually 9-10 digits)

#### 4. Network timeouts
**Cause**: Network connectivity issues
**Solution**:
- Check internet connection
- The system includes automatic retry logic
- Wait a moment and try again

### Debug Logging

Enable detailed logging by setting the log level:

```python
logging.getLogger("StreamBot.utils.telegram_notifications").setLevel(logging.DEBUG)
logging.getLogger("StreamBot.session_generator.session_manager").setLevel(logging.DEBUG)
```

### Log Messages to Look For

#### Success Messages:
```
✅ Notification sent successfully via Bot API to user {user_id}
✅ Welcome message sent successfully via Pyrogram to user {user_id}
```

#### Warning Messages:
```
⚠️ Bot API method failed for user {user_id}, trying Pyrogram fallback
⚠️ Primary client is not connected for user {user_id}
```

#### Error Messages:
```
❌ Both notification methods failed for user {user_id}
❌ Bot was blocked by the user
❌ Chat not found for user {user_id}
```

## Message Content

The welcome message includes:
- Success confirmation with emoji
- User's first name
- Instructions on how to use the bot
- Privacy information
- Security reminders
- Links to available commands

## Rate Limiting

The system includes automatic retry logic with exponential backoff:
- 3 retry attempts for failed messages
- 2-second delay after first failure
- 4-second delay after second failure
- No retry after third failure

## Dependencies

The notification system requires:
- `aiohttp` (already in requirements.txt)
- Valid `BOT_TOKEN` environment variable
- Network connectivity to Telegram API

## API Endpoints Used

- `https://api.telegram.org/bot{BOT_TOKEN}/sendMessage`
- `https://api.telegram.org/bot{BOT_TOKEN}/getMe` (for testing)

## Error Handling

The system handles these specific Telegram API errors:
- `bot was blocked by the user`
- `chat not found`
- `user is deactivated`
- Network timeouts and connection errors
- Invalid token errors
