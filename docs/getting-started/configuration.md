---
title: Configuration Guide
description: Complete configuration options for StreamBot
---

# Configuration Guide

StreamBot uses environment variables for configuration. This guide covers all available options and their purposes.

## Environment File Setup

Create a `.env` file in your project root:

```bash
cp .env.example .env
```

## Required Configuration

### Telegram Settings

```env
# Telegram API credentials (required)
API_ID=12345678
API_HASH=your_api_hash_from_my_telegram_org
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
LOG_CHANNEL=-1001234567890
```

| Variable | Description | How to Get |
|----------|-------------|------------|
| `API_ID` | Telegram API ID | Get from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Telegram API Hash | Get from [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | Bot token from BotFather | Message [@BotFather](https://t.me/botfather) |
| `LOG_CHANNEL` | Channel ID for file storage | Create private channel, add bot as admin |

### Database Configuration

```env
# MongoDB connection (required)
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=StreamBotDB
```

| Variable | Description | Examples |
|----------|-------------|----------|
| `DATABASE_URL` | MongoDB connection string | `mongodb://localhost:27017` (local)<br>`mongodb+srv://user:pass@cluster.mongodb.net/` (Atlas) |
| `DATABASE_NAME` | Database name | `StreamBotDB`, `MyStreamBot` |

### Server Configuration

```env
# Web server settings (required)
BASE_URL=https://yourdomain.com
PORT=8080
BIND_ADDRESS=0.0.0.0
```

| Variable | Description | Examples |
|----------|-------------|----------|
| `BASE_URL` | Public URL for download/streaming links | `https://files.yourdomain.com`, `http://localhost:8080` |
| `PORT` | Port for web server | `8080`, `3000`, `80` |
| `BIND_ADDRESS` | IP address to bind server | `127.0.0.1` (local), `0.0.0.0` (public) |

### Video Streaming Frontend

```env
# Video streaming frontend (defaults to Cricster)
VIDEO_FRONTEND_URL=https://cricster.pages.dev
```

| Variable | Description | Default | Disable |
|----------|-------------|---------|---------|
| `VIDEO_FRONTEND_URL` | Video player frontend URL | `https://cricster.pages.dev` | Set to `false` |

## Optional Configuration

### Admin Settings

```env
# Admin users and access
ADMINS=123456789 987654321
```

| Variable | Description | Format |
|----------|-------------|--------|
| `ADMINS` | Space-separated admin user IDs | `123456789 987654321` |

### Multi-Client Support

```env
# Additional bot tokens for load balancing
ADDITIONAL_BOT_TOKENS=token1,token2,token3
WORKER_CLIENT_PYROGRAM_WORKERS=1
WORKER_SESSIONS_IN_MEMORY=true
```

| Variable | Description | Benefits |
|----------|-------------|----------|
| `ADDITIONAL_BOT_TOKENS` | Comma-separated additional bot tokens | Increases download/streaming throughput, load balancing |
| `WORKER_CLIENT_PYROGRAM_WORKERS` | Workers per additional client | Keep at 1 for stability |
| `WORKER_SESSIONS_IN_MEMORY` | Store sessions in memory | Reduces disk I/O |

### Rate Limiting

```env
# User rate limiting
MAX_LINKS_PER_DAY=5
BANDWIDTH_LIMIT_GB=100
```

| Variable | Description | Default | Disable |
|----------|-------------|---------|---------|
| `MAX_LINKS_PER_DAY` | Daily link generation limit per user | `5` | `0` (unlimited) |
| `BANDWIDTH_LIMIT_GB` | Monthly bandwidth limit in GB | `100` | `0` (unlimited) |

### Force Subscription

```env
# Require channel subscription
FORCE_SUB_CHANNEL=-1009876543210
```

| Variable | Description | Usage |
|----------|-------------|-------|
| `FORCE_SUB_CHANNEL` | Channel ID for required subscription | Users must join channel before using bot |

### Performance Tuning

```env
# Application performance settings
WORKERS=4
SESSION_NAME=StreamBot
```

| Variable | Description | Default | Recommendations |
|----------|-------------|---------|-----------------|
| `WORKERS` | Number of worker threads | `4` | 2-8 depending on server |
| `SESSION_NAME` | Session file prefix | `TgDlBot` | Unique name per instance |

### Link Management

```env
# Link expiration settings
LINK_EXPIRY_SECONDS=86400
```

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `LINK_EXPIRY_SECONDS` | Link validity duration | `86400` (24 hours) | In seconds, affects both download and streaming links |

### External Integrations

```env
# Optional external services
GITHUB_REPO_URL=https://github.com/AnikethJana/Telegram-Download-Link-Generator
```

| Variable | Description | Usage |
|----------|-------------|-------|
| `GITHUB_REPO_URL` | Repository URL for info display | Shown in `/info` command and API |

## Environment-Specific Configurations

### Development Environment

```env
# Development settings
API_ID=12345678
API_HASH=your_dev_api_hash
BOT_TOKEN=your_dev_bot_token
LOG_CHANNEL=-1001234567890
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=StreamBotDev
BASE_URL=http://localhost:8080
PORT=8080
BIND_ADDRESS=127.0.0.1
VIDEO_FRONTEND_URL=https://cricster.pages.dev
ADMINS=your_telegram_user_id
MAX_LINKS_PER_DAY=0
BANDWIDTH_LIMIT_GB=0
SESSION_NAME=StreamBotDev
WORKERS=2
```

### Production Environment

```env
# Production settings
API_ID=12345678
API_HASH=your_production_api_hash
BOT_TOKEN=your_production_bot_token
LOG_CHANNEL=-1001234567890
DATABASE_URL=mongodb+srv://user:password@cluster.mongodb.net/
DATABASE_NAME=StreamBotProd
BASE_URL=https://files.yourdomain.com
PORT=8080
BIND_ADDRESS=0.0.0.0
VIDEO_FRONTEND_URL=https://cricster.pages.dev
ADMINS=your_telegram_user_id
MAX_LINKS_PER_DAY=5
BANDWIDTH_LIMIT_GB=100
FORCE_SUB_CHANNEL=-1009876543210
ADDITIONAL_BOT_TOKENS=token1,token2
SESSION_NAME=StreamBotProd
WORKERS=4
LINK_EXPIRY_SECONDS=86400
```

## Video Frontend Configuration

### Default Cricster Integration

StreamBot comes with Cricster integration by default:

```env
# Uses Cricster as default video frontend
VIDEO_FRONTEND_URL=https://cricster.pages.dev
```

### Custom Frontend

To use your own video frontend:

```env
# Your custom video frontend
VIDEO_FRONTEND_URL=https://my-video-player.example.com
```

Your frontend will receive streaming URLs as: `{VIDEO_FRONTEND_URL}?stream={encoded_stream_url}`

### Disable Video Frontend

```env
# Disable video frontend entirely
VIDEO_FRONTEND_URL=false
```

## Configuration Validation

StreamBot validates your configuration on startup. Common validation errors:

!!! error "Missing Required Variables"
    ```
    ERROR - Missing required environment variable: BOT_TOKEN
    ```
    **Solution**: Ensure all required variables are set in your `.env` file.

!!! error "Invalid Bot Token"
    ```
    ERROR - Bot token format is invalid
    ```
    **Solution**: Check your bot token format. It should look like `123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi`

!!! error "Database Connection Failed"
    ```
    ERROR - Failed to connect to MongoDB
    ```
    **Solution**: Verify your `DATABASE_URL` and ensure MongoDB is running.

!!! error "Invalid Channel ID"
    ```
    ERROR - LOG_CHANNEL must be a negative integer
    ```
    **Solution**: Channel IDs should be negative numbers like `-1001234567890`

!!! error "Video Frontend Not Accessible"
    ```
    WARNING - Video frontend URL not accessible
    ```
    **Solution**: Check your `VIDEO_FRONTEND_URL` or set to `false` to disable.

## Security Best Practices

### Environment Variables Security

1. **Never commit `.env` files** to version control
2. **Use HTTPS** in production for `BASE_URL`
3. **Restrict admin access** with proper `ADMINS` configuration
4. **Use secure MongoDB connections** with authentication

### IP Address Restrictions

For additional security, configure your reverse proxy or firewall to restrict access to specific IP addresses.

## Configuration Templates

### `.env.example` Template

```env
# Telegram Configuration (Required)
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
LOG_CHANNEL=your_log_channel_id

# Database Configuration (Required)
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=StreamBotDB

# Server Configuration (Required)
BASE_URL=https://yourdomain.com
PORT=8080
BIND_ADDRESS=0.0.0.0

# Video Frontend (defaults to Cricster)
VIDEO_FRONTEND_URL=https://cricster.pages.dev

# Admin Configuration
ADMINS=your_telegram_user_id

# Optional Features
MAX_LINKS_PER_DAY=5
BANDWIDTH_LIMIT_GB=100
FORCE_SUB_CHANNEL=
ADDITIONAL_BOT_TOKENS=

# Performance Settings
WORKERS=4
SESSION_NAME=TgDlBot
LINK_EXPIRY_SECONDS=86400
```

## Troubleshooting Configuration

If StreamBot fails to start, check:

1. **Environment file exists**: Ensure `.env` file is in the project root
2. **Required variables set**: All required variables have values
3. **Format correctness**: Variables follow the correct format
4. **File permissions**: `.env` file is readable by the application
5. **No trailing spaces**: Remove any trailing spaces from variable values
6. **Video frontend accessibility**: Ensure VIDEO_FRONTEND_URL is accessible or set to `false`

For additional help, see the [Installation Guide](installation.md) or [User Guide](../user-guide/overview.md). 