# Telegram File Download Link Generator Bot

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) 

A Telegram bot built with Python (using Pyrogram and aiohttp) that generates temporary, direct download links for files sent to it. It utilizes a log channel to store files and a web server to handle download requests.

## Features

* **File Handling:** Accepts various file types (documents, videos, audio, photos, etc.).
* **Direct Download Links:** Generates unique, direct download links for each file.
* **Web Server:** Serves files directly via HTTP using a built-in aiohttp web server.
* **Link Expiry:** Download links automatically expire after a configurable duration (default: 24 hours).
* **Force Subscription:** (Optional) Requires users to join a specific channel before using the bot.
* **Multi-Bot Architecture:** Supports load distribution across multiple worker bots for improved performance.
* **Admin Broadcast:** Allows administrators to send messages to all users who have interacted with the bot.
* **Database Integration:** Uses MongoDB to store user IDs for the broadcast feature.
* **Logs Command:** View application logs directly within the bot (admin only).
* **Rate Limiting:** Configurable daily limit on link generation per user.
* **Bandwidth Limiting:** Optional monthly bandwidth limit with automatic reset - when reached, users are shown a friendly message and new downloads are temporarily blocked.
* **Environment Variable Configuration:** Easy setup using environment variables or a `.env` file.
* **Status API:** Includes a `/api/info` endpoint to check bot status and configuration.

## Requirements

* Python 3.9 or higher
* MongoDB Database (Cloud Atlas, self-hosted, etc.)
* Telegram API Credentials (`API_ID`, `API_HASH`)
* Telegram Bot Token (`BOT_TOKEN`)
* Two Telegram Channels/Groups (one public/private for logging, one optional for force subscription)

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/AnikethJana/Telegram-Download-Link-Generator
    cd Telegram-Download-Link-Generator
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The bot is configured using environment variables. You can set these directly in your system or create a `.env` file in the project's root directory.

**`.env` File Example:**

```dotenv
# --- Telegram Core ---
API_ID=12345678
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here

# --- Channels ---
# Use the numeric ID (e.g., -1001234567890), not the username.
# Get ID from bots like @userinfobot or @myidbot
# The bot MUST be an admin in the LOG_CHANNEL with permission to post messages.
LOG_CHANNEL=-100xxxxxxxxxx
# Optional: The bot MUST be an admin in the FORCE_SUB_CHANNEL with permission to add members/invite links.
FORCE_SUB_CHANNEL=-100yyyyyyyyyy # Leave empty or remove to disable

# --- Web Server ---
# Full URL, including http:// or https://. MUST NOT end with a '/'
# This is the public URL users will use to download files.
BASE_URL=https://yourdomain.com
PORT=8080 # Port the web server will listen on
BIND_ADDRESS=0.0.0.0 # Address to bind the web server to

# --- Video Streaming Frontend ---
# Optional: URL of your video streaming frontend (deployed on Cloudflare Pages or similar)
# When set, video files will show a "Play Video" button
VIDEO_FRONTEND_URL=https://your-video-frontend.pages.dev

# --- Settings ---
LINK_EXPIRY_SECONDS=86400 # Default: 24 hours (in seconds)
SESSION_NAME=TgDlBot # Pyrogram session file name
WORKERS=4 # Number of Pyrogram worker threads
GITHUB_REPO_URL=https://github.com/yourusername/your-repo # Optional: Link to your repo for /api/info
# Space-separated list of numeric user IDs allowed to use /broadcast and /logs
ADMINS=123456789 987654321

# --- Rate Limiting ---
MAX_LINKS_PER_DAY=5 # Maximum links a user can generate per day (0 to disable)

# --- Bandwidth Limiting ---
BANDWIDTH_LIMIT_GB=100 # Monthly bandwidth limit in GigaBytes (0 to disable)

# --- Multiple Bot Support ---
# Space-separated list of additional bot tokens for streaming only
ADDITIONAL_BOT_TOKENS=token1 token2 token3
# Number of Pyrogram workers for each additional bot (default: 1)
WORKER_CLIENT_PYROGRAM_WORKERS=1
# Whether to store worker bot sessions in memory only (default: true)
WORKER_SESSIONS_IN_MEMORY=true

# --- Database (MongoDB) ---
# Replace <username>, <password>, <your-cluster-url>, and ensure <database_name> matches DB_NAME below or remove it from URI
DATABASE_URL=mongodb+srv://<username>:<password>@<your-cluster-url>/<database_name>?retryWrites=true&w=majority
DATABASE_NAME=TgDlBotUsers # Name of the database to use
```

**Environment Variable Details:**

* **`API_ID`**: Your Telegram application's API ID (from [my.telegram.org](https://my.telegram.org/apps)).
* **`API_HASH`**: Your Telegram application's API Hash (from [my.telegram.org](https://my.telegram.org/apps)).
* **`BOT_TOKEN`**: The token for your Telegram bot (from [@BotFather](https://t.me/BotFather)).
* **`LOG_CHANNEL`**: The numeric ID of the **private** channel/group where the bot will forward files. **The bot MUST be an admin here.** This channel acts as storage.
* **`FORCE_SUB_CHANNEL`**: (Optional) The numeric ID of the channel/group users must join. **The bot MUST be an admin here.** Leave empty to disable.
* **`BASE_URL`**: The public-facing base URL of your web server (where the bot is hosted). **Crucial for download links.** Do *not* include a trailing slash (`/`).
* **`PORT`**: The network port the internal web server will listen on (default: `8080`).
* **`BIND_ADDRESS`**: The network address the web server will bind to (default: `0.0.0.0` to listen on all interfaces).
* **`VIDEO_FRONTEND_URL`**: (Optional) URL of your video streaming frontend. When set, video files will display a "Play Video" button.
* **`LINK_EXPIRY_SECONDS`**: Duration (in seconds) for which download links remain valid (default: `86400` = 24 hours).
* **`SESSION_NAME`**: The name for the Pyrogram session file (default: `TgDlBot`).
* **`WORKERS`**: Number of concurrent threads Pyrogram uses (default: `4`).
* **`GITHUB_REPO_URL`**: (Optional) URL of the bot's GitHub repository, displayed in the `/api/info` endpoint.
* **`ADMINS`**: A space-separated list of numeric Telegram User IDs who have permission to use the `/broadcast` and `/logs` commands.
* **`MAX_LINKS_PER_DAY`**: Maximum number of links a user can generate in a 24-hour period (default: `5`). Set to `0` to disable this limit.
* **`BANDWIDTH_LIMIT_GB`**: Monthly bandwidth limit in GigaBytes (default: `100`). Set to `0` to disable this limit.
* **`ADDITIONAL_BOT_TOKENS`**: Space-separated list of additional bot tokens that will be used as worker bots for file streaming. All these bots must be administrators in the LOG_CHANNEL.
* **`WORKER_CLIENT_PYROGRAM_WORKERS`**: Number of Pyrogram workers for each worker bot (default: `1`).
* **`WORKER_SESSIONS_IN_MEMORY`**: Whether to store worker bot sessions in memory only, avoiding disk writes (default: `true`).
* **`DATABASE_URL`**: Your MongoDB connection string URI.
* **`DATABASE_NAME`**: The name of the MongoDB database to use (default: `TgDlBotUsers`).

**How to get Numeric IDs:**

* Forward a message from the target channel/group to [@TGIdsBot](https://t.me/TGIdsBot) .
* For channels, the ID usually starts with `-100`.

## Multi-Client Architecture

The bot now supports a multi-bot architecture for improved performance and load distribution:

1. **Primary Bot:** Handles all user interactions, commands, and file uploads. This is the bot users interact with.
2. **Worker Bots:** Additional bots that only handle file streaming tasks. These are used to distribute the load when users download files.

This architecture provides several benefits:
- **Higher Throughput:** More concurrent downloads can be handled.
- **Reduced Rate Limiting:** Telegram API limits are distributed across multiple bots.
- **Improved Reliability:** If one bot hits rate limits, others can continue serving files.

To use this feature, simply add additional bot tokens to your configuration using the `ADDITIONAL_BOT_TOKENS` environment variable. All bots (primary and workers) must be administrators in the `LOG_CHANNEL`.

## Running the Bot

```bash
python -m StreamBot
```

The bot will start, connect to Telegram, and launch the web server.

## Docker Deployment

1. **Build Docker image:**
   ```bash
   docker build -t streambot .
   ```

2. **Run container:**
   ```bash
   docker run -d --name streambot -p 8080:8080 --env-file .env streambot
   ```
## Usage
**User Commands:**
1.  **Start the Bot:** Send `/start` in a private chat with the bot.
2.  **Send Files:** Send any file (document, video, audio, photo, etc.) to the bot in the private chat.
3.  **Receive Link:** The bot will reply with a direct download link for the file.
4.  **Download:** Click the link to download the file directly through your browser or download manager.

**Admin Commands:**

* `/broadcast`: Reply to a message with this command to send that message to all users who have started the bot.
* `/logs`: View application logs directly within the bot. Supports filtering by log level and text search with arguments.
  * Example: `/logs level=ERROR limit=100 filter=download`
  * Without arguments: `/logs` uploads the complete log file as a document
* `/stats`: View system statistics including memory usage, active streams, uptime, and other performance metrics.

## API Endpoints

* **`GET /api/info`**: Returns a JSON response with bot status, configuration details (like force-sub status, link expiry), bandwidth usage information, uptime, and total registered users.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## Acknowledgements

This project was inspired from :

* [CodeXBotz/File-Sharing-Bot](https://github.com/CodeXBotz/File-Sharing-Bot)
* [EverythingSuckz/FileStreamBot](https://github.com/EverythingSuckz/TG-FileStreamBot/tree/python)