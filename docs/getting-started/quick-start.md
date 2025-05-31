---
title: Quick Start Guide
description: Get StreamBot running in minutes
---

# Quick Start Guide

Get StreamBot up and running in just a few minutes! This guide assumes you have already completed the [installation](installation.md).

## Prerequisites Check

Before starting, ensure you have:

- [x] Python 3.8+ installed
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
2. The bot should respond with a download link
3. Click the link to test the download

### Test API

Open your browser and visit: `http://localhost:8080/api/info`

You should see JSON response with bot information.

## Step 5: Verify Everything Works

### ✅ Checklist

- [ ] Bot responds to `/start` command
- [ ] Bot generates download links for files
- [ ] Download links work in browser
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

## Next Steps

Now that StreamBot is running:

### Basic Usage

1. **Send files** to your bot to get download links
2. **Share links** with others for easy file access
3. **Use admin commands** like `/stats` to monitor usage

### Advanced Configuration

1. **Enable rate limiting**: Set `MAX_LINKS_PER_DAY=5` in `.env`
2. **Add bandwidth limits**: Set `BANDWIDTH_LIMIT_GB=100`
3. **Force subscription**: Set `FORCE_SUB_CHANNEL` to require users to join a channel

### Production Deployment

For production use:

1. **Get a domain name** and set up HTTPS
2. **Use a cloud database** like MongoDB Atlas
3. **Deploy to a VPS** or cloud platform
4. **Set up monitoring** and backup systems

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
| `/stats` | Check system statistics | `/stats` |
| `/logs` | View logs with filtering | `/logs level=ERROR limit=50` |
| `/broadcast` | Send message to all users | Reply to message with `/broadcast` |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/info` | Bot status and information |
| `GET /dl/{file_id}` | Download file via link |

## Getting Help

If you encounter issues:

1. **Check logs** for error messages
2. **Review configuration** in your `.env` file
3. **Consult documentation**:
   - [Configuration Guide](configuration.md)
   - [User Guide](../user-guide/overview.md)
   - [Troubleshooting](../user-guide/overview.md#troubleshooting)
4. **Get community support**:
   - [GitHub Discussions](https://github.com/yourusername/StreamBot/discussions)
   - [GitHub Issues](https://github.com/yourusername/StreamBot/issues)

## What's Next?

- [User Guide](../user-guide/overview.md) - Learn about all features
- [Deployment Guide](../deployment/overview.md) - Deploy to production
- [API Reference](../api/overview.md) - Integrate with your applications
- [Developer Guide](../developer-guide/architecture.md) - Understand the architecture

Congratulations! StreamBot is now running successfully. 🎉 