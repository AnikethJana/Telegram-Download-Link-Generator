---
title: Quick Start Guide
description: Get StreamBot running in minutes
---

# Quick Start Guide

Get StreamBot up and running in just a few minutes! This guide assumes you have already completed the [installation](installation.md).

## Prerequisites Check

Before starting, ensure you have:

- [x] Python 3.11+ installed
- [x] MongoDB running (local or cloud)
- [x] StreamBot repository cloned
- [x] Dependencies installed (`pip install -r requirements.txt`)

## Step 1: Get Telegram Credentials

### Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Save the bot token (format: `123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi`)

### Get API Credentials

1. Visit [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Go to "API Development Tools"
4. Create a new application
5. Note down your `API ID` and `API Hash`

### Create Log Channel

1. Create a private Telegram channel
2. Add your bot as an administrator
3. Give the bot "Post Messages" permission
4. Get the channel ID:
   - Forward a message from the channel to [@username_to_id_bot](https://t.me/username_to_id_bot)
   - The ID will be negative (e.g., `-1001234567890`)

## Step 2: Configure Environment

Create your `.env` file:

```bash
cp .env.example .env
```

Edit the `.env` file with your credentials:

```env
# Replace with your actual values
API_ID=12345678
API_HASH=your_api_hash_here
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
LOG_CHANNEL=-1001234567890

# Database (adjust if needed)
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=StreamBotDB

# Server settings
BASE_URL=http://localhost:8080
PORT=8080
BIND_ADDRESS=127.0.0.1

# Video frontend (defaults to Cricster)
VIDEO_FRONTEND_URL=https://cricster.pages.dev

# Your Telegram user ID (get from @username_to_id_bot)
ADMINS=your_telegram_user_id
```

## Step 3: Start StreamBot

```bash
# Activate virtual environment (if using one)
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Start the bot
python -m StreamBot
```

You should see output like:

```
INFO - Starting Telegram Download Link Generator Bot...
INFO - Primary bot client operational as @YourBotName
INFO - Web server started successfully on http://127.0.0.1:8080
```

## Step 4: Test Your Bot

### Test Bot Commands

1. Open Telegram and find your bot
2. Send `/start` command
3. You should receive a welcome message

### Test File Upload

1. Send any file to your bot (image, document, video, etc.)
2. The bot should respond with download and streaming links
3. Click the links to test functionality

### Test Video Streaming

1. Send a video file (MP4, MKV, etc.) to your bot
2. You should see:
   - Regular download link
   - "🎬 Play Video" button (if VIDEO_FRONTEND_URL is configured)
3. Click the "🎬 Play Video" button to test streaming
4. Test video seeking and playback controls

### Test API

Open your browser and visit: `http://localhost:8080/api/info`

You should see JSON response with bot information including video streaming status.

## Step 5: Verify Everything Works

### ✅ Checklist

- [ ] Bot responds to `/start` command
- [ ] Bot generates download links for files
- [ ] Download links work in browser
- [ ] Video files show "🎬 Play Video" button
- [ ] Video streaming works with seeking support
- [ ] API endpoint returns bot information
- [ ] No error messages in console

### Common Issues

!!! warning "Bot doesn't respond"
    - Check if `BOT_TOKEN` is correct
    - Ensure bot is not blocked by Telegram
    - Verify network connection

!!! warning "Database errors"
    - Confirm MongoDB is running: `sudo systemctl status mongodb`
    - Check `DATABASE_URL` format
    - Ensure database is accessible

!!! warning "Download links don't work"
    - Verify `LOG_CHANNEL` ID is correct and negative
    - Ensure bot has admin permissions in log channel
    - Check if `BASE_URL` is accessible

!!! warning "Video streaming not working"
    - Check `VIDEO_FRONTEND_URL` configuration
    - Ensure frontend URL is accessible
    - Set to `false` to disable video frontend
    - Test with different video formats

## Next Steps

Now that StreamBot is running:

### Basic Usage

1. **Send files** to your bot to get download/streaming links
2. **Share links** with others for easy file access
3. **Use admin commands** like `/stats` to monitor usage
4. **Test video streaming** with various video formats

### Advanced Configuration

1. **Enable rate limiting**: Set `MAX_LINKS_PER_DAY=5` in `.env`
2. **Add bandwidth limits**: Set `BANDWIDTH_LIMIT_GB=100`
3. **Force subscription**: Set `FORCE_SUB_CHANNEL` to require users to join a channel
4. **Multi-client setup**: Add `ADDITIONAL_BOT_TOKENS` for better performance
5. **Custom video frontend**: Configure your own `VIDEO_FRONTEND_URL`

### Production Deployment

For production use:

1. **Get a domain name** and set up HTTPS
2. **Use a cloud database** like MongoDB Atlas
3. **Deploy to a VPS** or cloud platform
4. **Set up monitoring** and backup systems
5. **Configure CDN** for better video streaming performance

## Useful Commands

### Bot Commands (Telegram)

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show help information |
| `/stats` | Show bot statistics (admin only) |
| `/logs` | View recent logs (admin only) |

### Admin Commands (Telegram)

| Command | Description | Usage |
|---------|-------------|-------|
| `/stats` | Check system statistics with memory and bandwidth | `/stats` |
| `/logs` | View logs with filtering | `/logs level=ERROR limit=50` |
| `/broadcast` | Send message to all users | Reply to message with `/broadcast` |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/info` | Bot status and information |
| `GET /dl/{file_id}` | Download file via link |
| `GET /stream/{file_id}` | Stream video file |

## Video Streaming Features

### Supported Video Formats

- MP4, WebM, MKV, AVI, MOV
- H.264, H.265, VP8, VP9 codecs
- Various audio codecs (AAC, MP3, Opus)

### Streaming Capabilities

- **Seeking Support**: Jump to any point in the video
- **Range Requests**: Efficient video loading
- **Multiple Quality**: Automatic quality detection
- **Cross-Platform**: Works on desktop and mobile browsers

### Frontend Integration

By default, videos use Cricster frontend (`https://cricster.pages.dev`):

- Modern video player interface
- Seeking controls and timeline
- Volume controls
- Fullscreen support
- Mobile-responsive design

## Getting Help

If you encounter issues:

1. **Check logs** for error messages
2. **Review configuration** in your `.env` file
3. **Consult documentation**:
   - [Configuration Guide](configuration.md)
   - [User Guide](../user-guide/overview.md)
   - [Troubleshooting](../user-guide/overview.md#troubleshooting)
4. **Get community support**:
   - [GitHub Discussions](https://github.com/AnikethJana/Telegram-Download-Link-Generator/discussions)
   - [GitHub Issues](https://github.com/AnikethJana/Telegram-Download-Link-Generator/issues)
   - [Telegram Support](https://t.me/ajmods_bot)

## What's Next?

- [User Guide](../user-guide/overview.md) - Learn about all features including video streaming
- [Deployment Guide](../deployment/overview.md) - Deploy to production
- [API Reference](../api/overview.md) - Integrate with your applications
- [Developer Guide](../developer-guide/architecture.md) - Understand the architecture

Congratulations! StreamBot is now running successfully with full video streaming support. 🎉 