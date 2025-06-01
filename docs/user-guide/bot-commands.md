---
title: Bot Commands
description: Complete reference for all StreamBot Telegram commands
---

# Bot Commands Reference

StreamBot provides various commands for users and administrators. This page documents all available commands and their usage.

## User Commands

These commands are available to all users of the bot.

### Basic Commands

#### `/start`
**Description**: Initialize interaction with the bot and display welcome message.

**Usage**: `/start`

**Response**: Welcome message with bot information and basic instructions.

**Example**:
```
🚀 Welcome to StreamBot!

I can convert your files into direct download links.
Simply send me any file and I'll generate a shareable link for you.

Commands:
• /help - Show available commands
• /info - Bot statistics and status
```

#### `/help`
**Description**: Display list of available commands and their descriptions.

**Usage**: `/help`

**Response**: Comprehensive command list with descriptions.

#### `/info`
**Description**: Show bot statistics, uptime, and current status.

**Usage**: `/info`

**Response**: 
- Bot uptime
- Total users
- Current bandwidth usage
- Available features
- Server status

**Example**:
```
📊 StreamBot Information

🤖 Bot: @YourStreamBot
⏰ Uptime: 5d 12h 34m 16s
👥 Total Users: 1,247
📈 Bandwidth Used: 45.2 GB / 100 GB this month
🔗 Links Generated Today: 127

Features:
✅ Force Subscription: Enabled
✅ Link Expiry: 24 hours
✅ Rate Limiting: 5 links/day
```

### File Upload

#### Send Any File
**Description**: Upload a file to generate a direct download link.

**Usage**: Simply send any file (document, image, video, audio, etc.)

**Supported Types**:
- Documents (PDF, DOCX, TXT, etc.)
- Images (JPG, PNG, GIF, etc.)
- Videos (MP4, AVI, MKV, etc.)
- Audio (MP3, FLAC, OGG, etc.)
- Archives (ZIP, RAR, 7Z, etc.)
- Any other file type

**Response**: Direct download link with file information.

**Example**:
```
✅ File uploaded successfully!

📁 Filename: document.pdf
📏 Size: 2.4 MB
🔗 Download Link: https://yourdomain.com/dl/abc123/document.pdf

⏰ Link expires in 24 hours
📊 Daily links remaining: 4/5
```

### Personal Statistics

#### `/stats`
**Description**: View your personal usage statistics.

**Usage**: `/stats`

**Response**: Personal usage data including:
- Links generated today
- Bandwidth used this month
- Total files uploaded
- Account creation date

**Example**:
```
📊 Your Statistics

🔗 Links Today: 2/5
📈 Bandwidth This Month: 127.3 MB
📁 Total Files: 45
📅 Member Since: Jan 15, 2024

Daily reset: 23:45:12
Monthly reset: Jan 31, 2024
```

### Utility Commands

#### `/ping`
**Description**: Check bot responsiveness and connection status.

**Usage**: `/ping`

**Response**: Simple response time indication.

**Example**:
```
🏓 Pong! 
Response time: 0.12s
```

## Admin Commands

These commands are only available to users configured as administrators.

### System Monitoring

#### `/stats`
**Description**: Check system statistics including memory usage, active streams, bandwidth usage, and uptime.

**Usage**: `/stats`

**Access**: Admin only

**Response**: Comprehensive system information including memory, active resources, and bandwidth data.

**Example**:
```
📊 System Statistics

🧠 Memory Usage:
• RSS Memory: 156.3 MB
• VMS Memory: 203.7 MB  
• Memory %: 8.2%

🌐 Active Resources:
• Active Streams: 23
• Telegram Clients: 3

📊 Bandwidth Usage:
• Used this month: 45.234 GB
• Limit: 100 GB (enabled)
• Month: 2024-01

📝 Logger Cache: 45/1000 entries
⏰ Uptime: 2d 14h 23m 45s
🕐 Timestamp: 2024-01-15T14:30:45.123456

💡 Memory cleanup runs automatically every hour
```

#### `/logs`
**Description**: Access application logs with filtering options.

**Usage**: 
- `/logs` - Recent logs
- `/logs level=ERROR` - Filter by log level
- `/logs limit=50` - Limit number of entries
- `/logs filter=download` - Filter by text content

**Access**: Admin only

**Parameters**:
- `level`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `limit`: Number of log entries (1-100)
- `filter`: Text to search for in logs

**Example**:
```
📋 Application Logs (ERROR level, last 10 entries)

2024-01-15 14:30:45 - ERROR - Download failed for message 12345
2024-01-15 14:25:30 - ERROR - User 67890 hit rate limit
2024-01-15 14:20:15 - ERROR - Database connection timeout

Total matching entries: 156
```

### User Management

#### `/stats_global`
**Description**: View global bot statistics and user data.

**Usage**: `/stats_global`

**Access**: Admin only

**Response**: Comprehensive bot usage statistics.

**Example**:
```
🌍 Global Statistics

👥 Total Users: 1,247
🔗 Links Generated: 15,643
📈 Bandwidth Used: 892.4 GB
📁 Files Processed: 12,891

📊 Today's Activity:
• New Users: 23
• Links Generated: 234
• Bandwidth: 45.2 GB

🏆 Top File Types:
1. PDF (34%)
2. Images (28%)
3. Videos (21%)
4. Archives (17%)
```

### Communication

#### `/broadcast`
**Description**: Send a message to all bot users.

**Usage**: Reply to any message with `/broadcast`

**Access**: Admin only

**Process**:
1. Compose your message
2. Reply to it with `/broadcast`
3. Confirm when prompted
4. Message sent to all users

**Example**:
```
📢 Broadcasting Message

Message: "Server maintenance scheduled for tonight at 2 AM UTC"
Recipients: 1,247 users

Type 'CONFIRM' to proceed or 'CANCEL' to abort.
```

**Confirmation Response**:
```
✅ Broadcast sent successfully!

Sent to: 1,247 users
Failed: 3 users (blocked bot)
Time taken: 2.3 seconds
```

## Error Messages

### Common Error Responses

#### Rate Limit Exceeded
```
⚠️ Rate Limit Exceeded

You've reached your daily limit of 5 links.
Limit resets in: 14h 23m 45s

Upgrade to premium for unlimited links!
```

#### File Too Large
```
❌ File Too Large

Maximum file size: 2 GB
Your file size: 2.1 GB

Please compress or split your file.
```

#### Bandwidth Exceeded
```
📊 Bandwidth Limit Exceeded

Monthly limit: 100 GB
Used: 100.2 GB

Limit resets on: Feb 1, 2024
```

#### Force Subscription Required
```
🔒 Subscription Required

Please join our channel to use this bot:
👉 @YourChannel

After joining, send /start again.
```

#### Invalid Command
```
❓ Unknown Command

I don't understand that command.
Use /help to see available commands.
```

## Command Permissions

### Permission Levels

| Command | User | Admin | Description |
|---------|------|-------|-------------|
| `/start` | ✅ | ✅ | Welcome message |
| `/help` | ✅ | ✅ | Command help |
| `/info` | ✅ | ✅ | Bot information |
| `/stats` | ✅ | ✅ | Personal/System statistics |
| `/ping` | ✅ | ✅ | Connection test |
| File Upload | ✅ | ✅ | Generate download links |
| `/logs` | ❌ | ✅ | Application logs |
| `/broadcast` | ❌ | ✅ | Message all users |

### Becoming an Admin

To become an admin:

1. **Get your Telegram User ID** from [@username_to_id_bot](https://t.me/username_to_id_bot)
2. **Add your ID** to the `ADMINS` environment variable
3. **Restart the bot** for changes to take effect

```env
ADMINS=123456789 987654321
```

## Best Practices

### For Users
- **Use descriptive filenames** for better organization
- **Check file sizes** before uploading
- **Monitor your usage** to avoid hitting limits
- **Keep download links secure** if sensitive

### For Admins
- **Monitor system resources** regularly with `/stats`
- **Check logs** periodically for errors with `/logs`
- **Use broadcasting responsibly** for important announcements only
- **Review global stats** to understand usage patterns

## Troubleshooting

### Command Not Working

1. **Check spelling** - Commands are case-sensitive
2. **Verify permissions** - Some commands require admin access
3. **Try `/ping`** to test bot connectivity
4. **Check bot status** with `/info`

### No Response from Bot

1. **Check bot status** by visiting the API endpoint
2. **Wait a moment** - Bot might be under high load
3. **Try again** in a few minutes
4. **Contact administrators** if persistent

For more help, see the [User Guide](overview.md) or [Troubleshooting section](overview.md#troubleshooting). 