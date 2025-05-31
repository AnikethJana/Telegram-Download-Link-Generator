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
BIND_ADDRESS=127.0.0.1
```

| Variable | Description | Examples |
|----------|-------------|----------|
| `BASE_URL` | Public URL for download links | `https://files.yourdomain.com`, `http://localhost:8080` |
| `PORT` | Port for web server | `8080`, `3000`, `80` |
| `BIND_ADDRESS` | IP address to bind server | `127.0.0.1` (local), `0.0.0.0` (public) |

## Optional Configuration

### Admin Settings

```env
# Admin users and access
ADMINS=123456789 987654321
LOGS_ACCESS_TOKEN=your_secure_random_token_here
ADMIN_IPS=127.0.0.1,203.0.113.1
```

| Variable | Description | Format |
|----------|-------------|--------|
| `ADMINS` | Space-separated admin user IDs | `123456789 987654321` |
| `LOGS_ACCESS_TOKEN` | Token for API log access | Generate secure random string |
| `ADMIN_IPS` | Comma-separated admin IP addresses | `127.0.0.1,203.0.113.1` |

### Multi-Client Support

```env
# Additional bot tokens for load balancing
ADDITIONAL_BOT_TOKENS=token1,token2,token3
```

| Variable | Description | Benefits |
|----------|-------------|----------|
| `ADDITIONAL_BOT_TOKENS` | Comma-separated additional bot tokens | Increases download throughput, load balancing |

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
WORKER_CLIENT_PYROGRAM_WORKERS=1
SESSION_NAME=StreamBot
```

| Variable | Description | Default | Recommendations |
|----------|-------------|---------|-----------------|
| `WORKERS` | Number of worker threads | `4` | 2-8 depending on server |
| `WORKER_CLIENT_PYROGRAM_WORKERS` | Pyrogram workers per client | `1` | Keep at 1 for stability |
| `SESSION_NAME` | Session file prefix | `StreamBot` | Unique name per instance |

### Link Management

```env
# Link expiration settings
LINK_EXPIRY_ENABLED=true
LINK_EXPIRY_DURATION_SECONDS=86400
```

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `LINK_EXPIRY_ENABLED` | Enable link expiration | `true` | Set to `false` to disable |
| `LINK_EXPIRY_DURATION_SECONDS` | Link validity duration | `86400` (24 hours) | In seconds |

### External Integrations

```env
# Optional external services
GITHUB_REPO_URL=https://github.com/yourusername/StreamBot
SUPPORT_CHAT_ID=-1001234567890
```

| Variable | Description | Usage |
|----------|-------------|-------|
| `GITHUB_REPO_URL` | Repository URL for info display | Shown in `/info` command |
| `SUPPORT_CHAT_ID` | Support chat/group ID | For user support redirects |

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
ADMINS=your_telegram_user_id
LOGS_ACCESS_TOKEN=your_secure_production_token
ADMIN_IPS=your.server.ip,your.home.ip
MAX_LINKS_PER_DAY=5
BANDWIDTH_LIMIT_GB=100
FORCE_SUB_CHANNEL=-1009876543210
ADDITIONAL_BOT_TOKENS=token1,token2
SESSION_NAME=StreamBotProd
WORKERS=4
LINK_EXPIRY_ENABLED=true
LINK_EXPIRY_DURATION_SECONDS=86400
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

## Security Best Practices

### Environment Variables Security

1. **Never commit `.env` files** to version control
2. **Use strong tokens** for `LOGS_ACCESS_TOKEN`
3. **Restrict admin IPs** with `ADMIN_IPS`
4. **Use HTTPS** in production for `BASE_URL`

### Generating Secure Tokens

```bash
# Generate secure random token (Linux/macOS)
openssl rand -hex 32

# Generate secure random token (Python)
python -c "import secrets; print(secrets.token_hex(32))"
```

### IP Address Restrictions

```env
# Restrict admin access to specific IPs
ADMIN_IPS=203.0.113.1,198.51.100.2,127.0.0.1
```

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
BIND_ADDRESS=127.0.0.1

# Admin Configuration
ADMINS=your_telegram_user_id
LOGS_ACCESS_TOKEN=generate_secure_token
ADMIN_IPS=127.0.0.1

# Optional Features
MAX_LINKS_PER_DAY=5
BANDWIDTH_LIMIT_GB=100
FORCE_SUB_CHANNEL=
ADDITIONAL_BOT_TOKENS=

# Performance Settings
WORKERS=4
SESSION_NAME=StreamBot
LINK_EXPIRY_ENABLED=true
LINK_EXPIRY_DURATION_SECONDS=86400
```

## Troubleshooting Configuration

If StreamBot fails to start, check:

1. **Environment file exists**: Ensure `.env` file is in the project root
2. **Required variables set**: All required variables have values
3. **Format correctness**: Variables follow the correct format
4. **File permissions**: `.env` file is readable by the application
5. **No trailing spaces**: Remove any trailing spaces from variable values

For additional help, see the [Installation Guide](installation.md) or [User Guide](../user-guide/overview.md). 