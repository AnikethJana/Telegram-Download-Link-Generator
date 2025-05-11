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
* **Admin Broadcast:** Allows administrators to send messages to all users who have interacted with the bot.
* **Database Integration:** Uses MongoDB to store user IDs for the broadcast feature.
* **Environment Variable Configuration:** Easy setup using environment variables or a `.env` file.
* **Status API:** Includes a `/api/info` endpoint to check bot status and configuration.
* **Logs API:** Provides a `/api/logs` endpoint for admins to view logs remotely without server access.

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
BASE_URL=[https://yourdomain.com](https://yourdomain.com)
PORT=8080 # Port the web server will listen on
BIND_ADDRESS=0.0.0.0 # Address to bind the web server to

# --- Settings ---
LINK_EXPIRY_SECONDS=86400 # Default: 24 hours (in seconds)
SESSION_NAME=TgDlBot # Pyrogram session file name
WORKERS=4 # Number of Pyrogram worker threads
GITHUB_REPO_URL=[https://github.com/yourusername/your-repo](https://github.com/yourusername/your-repo) # Optional: Link to your repo for /api/info
# Space-separated list of numeric user IDs allowed to use /broadcast and /logs
ADMINS=123456789 987654321

# --- Admin Access for Logs ---
# Token for secure access to log endpoints (auto-generated if not provided)
ADMIN_TOKEN=your_secure_token_here
# Comma-separated list of IP addresses allowed to access admin endpoints
ADMIN_IPS=127.0.0.1,192.168.1.100

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
* **`LINK_EXPIRY_SECONDS`**: Duration (in seconds) for which download links remain valid (default: `86400` = 24 hours).
* **`SESSION_NAME`**: The name for the Pyrogram session file (default: `TgDlBot`).
* **`WORKERS`**: Number of concurrent threads Pyrogram uses (default: `4`).
* **`GITHUB_REPO_URL`**: (Optional) URL of the bot's GitHub repository, displayed in the `/api/info` endpoint.
* **`ADMINS`**: A space-separated list of numeric Telegram User IDs who have permission to use the `/broadcast` and `/logs` commands.
* **`DATABASE_URL`**: Your MongoDB connection string URI.
* **`DATABASE_NAME`**: The name of the MongoDB database to use (default: `TgDlBotUsers`).
* **`ADMIN_TOKEN`**: (Optional) A secure token for accessing the logs API endpoint. If not provided, a random token will be generated on startup.
* **`ADMIN_IPS`**: (Optional) A comma-separated list of IP addresses that are allowed to access admin endpoints. If not provided, only token-based and admin user ID-based authentication will be available.

**How to get Numeric IDs:**

* Forward a message from the target channel/group to [@TGIdsBot](https://t.me/TGIdsBot) .
* For channels, the ID usually starts with `-100`.

## Running the Bot

### Standard Method
```bash
python main.py
```

The bot will start, connect to Telegram, and launch the web server.

### Docker Deployment
This project includes Docker support for easy deployment.

1. **Using Docker Compose** (recommended):
   ```bash
   # Build and start the container in detached mode
   docker-compose up -d
   
   # View logs
   docker-compose logs -f
   
   # Stop the container
   docker-compose down
   ```

2. **Using Docker directly**:
   ```bash
   # Build the Docker image
   docker build -t streambot .
   
   # Run the container
   docker run -d --name streambot -p 8080:8080 --env-file .env -v $(pwd)/tgdlbot.log:/app/tgdlbot.log -v $(pwd)/TgDlBot.session:/app/TgDlBot.session streambot
   
   # View logs
   docker logs -f streambot
   
   # Stop the container
   docker stop streambot
   docker rm streambot
   ```

**Note**: When using Docker, make sure your `.env` file is properly configured and the `BASE_URL` matches your domain or IP address. The `.env` file should be in the same directory as your `docker-compose.yml` file.

## Usage

1.  **Start the Bot:** Send `/start` in a private chat with the bot.
2.  **Send Files:** Send any file (document, video, audio, photo, etc.) to the bot in the private chat.
3.  **Receive Link:** The bot will reply with a direct download link for the file.
4.  **Download:** Click the link to download the file directly through your browser or download manager.

**Admin Commands:**

* `/broadcast`: (Admin only) Reply to a message with this command to send that message to all users who have started the bot.
* `/logs`: (Admin only) Get the URL with authentication token to access the logs API endpoint.

## API Endpoints

* **`GET /api/info`**: Returns a JSON response with bot status, configuration details (like force-sub status, link expiry), uptime, and total registered users.
* **`GET /api/logs`**: (Admin only) Returns log entries with options for filtering and pagination:
  * **Parameters:**
    * `token`: Authentication token (required unless accessing from an admin IP)
    * `lines`: Number of lines to return (default: 100, max: 1000)
    * `tail`: Set to `1` to return the most recent lines (default), `0` for standard pagination
    * `level`: Filter by log level (INFO, ERROR, WARNING, DEBUG, CRITICAL)
    * `search`: Text search term to filter log entries
    * `page`: Page number for pagination (starts at 1)
    * `file`: Log file to read (default: tgdlbot.log)

## Deployment Notes

* Ensure the `BASE_URL` is correctly set to the public URL where the bot's web server is accessible.
* If deploying behind a reverse proxy (like Nginx), configure it to forward requests to the bot's `BIND_ADDRESS` and `PORT`.
* Make sure the necessary ports are open in your firewall settings.
* Keep your MongoDB database secure.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## Acknowledgements

This project was inspired by and references code/logic from the following:

* [CodeXBotz/File-Sharing-Bot](https://github.com/CodeXBotz/File-Sharing-Bot)
* [EverythingSuckz/FileStreamBot](https://github.com/EverythingSuckz/TG-FileStreamBot/tree/python)