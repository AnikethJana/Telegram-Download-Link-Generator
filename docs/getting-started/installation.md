---
title: Installation Guide
description: Step-by-step installation instructions for StreamBot
---

# Installation Guide

This guide will walk you through installing StreamBot on your system. Choose the method that best suits your needs.

## Prerequisites

Before installing StreamBot, ensure you have:

- **Python 3.8 or higher** ([Download Python](https://python.org/downloads/))
- **MongoDB 4.4+** (local or cloud instance)
- **Git** for cloning the repository
- **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
- **Telegram API credentials** from [my.telegram.org](https://my.telegram.org)

## Method 1: Standard Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/StreamBot.git
cd StreamBot
```

### 2. Create Virtual Environment

=== "Windows"

    ```cmd
    python -m venv venv
    venv\Scripts\activate
    ```

=== "macOS/Linux"

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit the configuration file
nano .env  # or use your preferred editor
```

## Method 2: Docker Installation

### 1. Using Docker Compose (Recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/StreamBot.git
cd StreamBot

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start with Docker Compose
docker-compose up -d
```

### 2. Using Docker Only

```bash
# Build the image
docker build -t streambot .

# Run the container
docker run -d \
  --name streambot \
  --env-file .env \
  -p 8080:8080 \
  streambot
```

## Post-Installation Setup

### 1. Telegram Bot Setup

1. **Create a Bot**:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow the instructions
   - Save the bot token

2. **Create Log Channel**:
   - Create a private Telegram channel
   - Add your bot as an admin with "Post Messages" permission
   - Get the channel ID using [@username_to_id_bot](https://t.me/username_to_id_bot)

3. **Get API Credentials**:
   - Visit [my.telegram.org](https://my.telegram.org)
   - Log in with your phone number
   - Go to "API Development Tools"
   - Create a new application to get API ID and Hash

### 2. MongoDB Setup

=== "Local MongoDB"

    ```bash
    # Install MongoDB (Ubuntu/Debian)
    sudo apt update
    sudo apt install mongodb

    # Start MongoDB service
    sudo systemctl start mongodb
    sudo systemctl enable mongodb
    ```

=== "MongoDB Atlas (Cloud)"

    1. Create account at [MongoDB Atlas](https://www.mongodb.com/atlas)
    2. Create a new cluster
    3. Get connection string
    4. Whitelist your IP address

### 3. Configuration

Edit your `.env` file with the following required variables:

```env
# Telegram Configuration
API_ID=your_api_id_here
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here
LOG_CHANNEL=-1001234567890

# Database Configuration
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=StreamBotDB

# Server Configuration
BASE_URL=http://localhost:8080
PORT=8080
BIND_ADDRESS=127.0.0.1

# Admin Configuration
ADMINS=your_telegram_user_id
```

## Verification

### 1. Test the Installation

```bash
# Start StreamBot
python -m StreamBot
```

You should see output like:
```
INFO - StreamBot starting up...
INFO - Primary bot client operational as @YourBotName
INFO - Web server started on http://127.0.0.1:8080
```

### 2. Test Bot Functionality

1. Send `/start` to your bot on Telegram
2. Send a file to test link generation
3. Visit `http://localhost:8080/api/info` to check API status

## Troubleshooting

### Common Issues

**Bot token invalid**:
```
ERROR - Bot token is invalid
```
- Verify your bot token in the `.env` file
- Ensure there are no extra spaces or characters

**Database connection failed**:
```
ERROR - Failed to connect to MongoDB
```
- Check if MongoDB is running: `sudo systemctl status mongodb`
- Verify DATABASE_URL in your `.env` file

**Port already in use**:
```
ERROR - Port 8080 is already in use
```
- Change the PORT in your `.env` file
- Or stop the process using port 8080

**Permission denied for log channel**:
```
ERROR - Bot doesn't have permission to post in log channel
```
- Ensure the bot is added as admin to your log channel
- Verify the LOG_CHANNEL ID is correct (should be negative for channels)

### Getting Help

If you encounter issues:

1. Check the [troubleshooting section](../user-guide/overview.md#troubleshooting)
2. Review logs for error messages
3. Join our [community discussions](https://github.com/yourusername/StreamBot/discussions)
4. Report bugs on [GitHub Issues](https://github.com/yourusername/StreamBot/issues)

## Next Steps

Once installation is complete:

1. [Configure your bot](configuration.md) with additional settings
2. Follow the [Quick Start guide](quick-start.md) for basic usage
3. Review the [User Guide](../user-guide/overview.md) for detailed features 