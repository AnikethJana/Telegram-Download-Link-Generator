---
title: API Endpoints
description: Detailed documentation for all StreamBot API endpoints
---

# API Endpoints Reference

This page provides detailed documentation for all available StreamBot API endpoints.

## System Information

### GET `/api/info`

Returns comprehensive bot status and configuration information.

**Authentication**: None required

**Request**:
```http
GET /api/info HTTP/1.1
Host: yourdomain.com
Accept: application/json
```

**Response (Success - 200)**:
```json
{
  "status": "ok",
  "bot_status": "connected",
  "bot_info": {
    "id": 123456789,
    "username": "YourBotName",
    "first_name": "StreamBot",
    "mention": "@YourBotName"
  },
  "features": {
    "force_subscribe": true,
    "force_subscribe_channel_id": -1001234567890,
    "link_expiry_enabled": true,
    "link_expiry_duration_seconds": 86400,
    "link_expiry_duration_human": "24 hours"
  },
  "bandwidth_info": {
    "limit_gb": 100,
    "used_gb": 45.234,
    "used_bytes": 48573440000,
    "month": "2024-01",
    "limit_enabled": true,
    "remaining_gb": 54.766
  },
  "uptime": "2d 14h 32m 18s",
  "server_time_utc": "2024-01-15T14:30:45.123456Z",
  "totaluser": 1250,
  "github_repo": "https://github.com/yourusername/StreamBot"
}
```

**Response (Error - 500)**:
```json
{
  "status": "error",
  "bot_status": "disconnected",
  "message": "Bot client is not currently connected to Telegram.",
  "uptime": "0s",
  "totaluser": 0,
  "bandwidth_info": {
    "limit_enabled": false,
    "error": "Failed to retrieve bandwidth data"
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | API response status (`ok` or `error`) |
| `bot_status` | string | Telegram bot connection status |
| `bot_info` | object | Bot identity information |
| `features` | object | Enabled features and their configuration |
| `bandwidth_info` | object | Current bandwidth usage and limits |
| `uptime` | string | Human-readable bot uptime |
| `server_time_utc` | string | Current server time in UTC ISO format |
| `totaluser` | integer | Total number of registered users |
| `github_repo` | string | Repository URL (if configured) |

## Log Access

### GET `/api/logs`

Access application logs with filtering and pagination support.

**Authentication**: Token required (`LOGS_ACCESS_TOKEN`)

**Request**:
```http
GET /api/logs?token=your_token&level=ERROR&limit=50&page=1 HTTP/1.1
Host: yourdomain.com
Accept: application/json
```

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | string | - | Authentication token (required) |
| `level` | string | `ALL` | Log level filter (`ALL`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `limit` | integer | `100` | Lines per page (max 1000) |
| `page` | integer | `1` | Page number (starts at 1) |
| `filter` | string | - | Text filter for log content |

**Response (Success - 200)**:
```json
{
  "status": "ok",
  "file_info": {
    "path": "tgdlbot.log",
    "size_bytes": 2048576,
    "size_human": "2.0 MB",
    "last_modified": "2024-01-15T14:30:45.123456"
  },
  "pagination": {
    "page": 1,
    "limit": 50,
    "total_pages": 25,
    "total_matching_lines": 1234
  },
  "filter": {
    "level": "ERROR",
    "text": null
  },
  "logs": [
    "2024-01-15 14:30:45,123 - StreamBot.web.web - ERROR - Download failed for message 12345: Network timeout",
    "2024-01-15 14:25:30,456 - StreamBot.bot - ERROR - Failed to process file from user 67890: File too large"
  ]
}
```

**Response (Error - 401)**:
```json
{
  "status": "error",
  "message": "Unauthorized access"
}
```

**Response (Error - 400)**:
```json
{
  "status": "error",
  "message": "Invalid page number"
}
```

## File Downloads

### GET `/dl/{encoded_id}`

Download files via generated download links.

**Authentication**: None (uses encoded file IDs for security)

**Request**:
```http
GET /dl/VGhpcyBpcyBhIGZha2UgZW5jb2RlZCBpZA HTTP/1.1
Host: yourdomain.com
Range: bytes=0-1023
User-Agent: Mozilla/5.0 (compatible)
```

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `encoded_id` | string | Base64-encoded message ID with security transformation |

**Request Headers**:

| Header | Required | Description |
|--------|----------|-------------|
| `Range` | No | HTTP range for partial content (e.g., `bytes=0-1023`) |
| `User-Agent` | No | Client identification |

**Response (Success - 200/206)**:
```http
HTTP/1.1 206 Partial Content
Content-Type: application/pdf
Content-Length: 1024
Content-Range: bytes 0-1023/2048576
Content-Disposition: attachment; filename="document.pdf"
Accept-Ranges: bytes

[Binary file content]
```

**Response Headers**:

| Header | Description |
|--------|-------------|
| `Content-Type` | File MIME type |
| `Content-Length` | Content size in bytes |
| `Content-Disposition` | Download filename |
| `Accept-Ranges` | Range request support (`bytes`) |
| `Content-Range` | Range information (for partial content) |

**Error Responses**:

**404 - File Not Found**:
```json
{
  "error": "File link is invalid or the file has been deleted."
}
```

**410 - Link Expired**:
```json
{
  "error": "This download link has expired (valid for 24 hours)."
}
```

**429 - Rate Limited**:
```json
{
  "error": "Rate limited by Telegram. Please try again in 30 seconds."
}
```

**503 - Service Unavailable**:
```json
{
  "error": "Bot service temporarily overloaded. Please try again shortly."
}
```

## Error Handling

### Common Error Responses

All endpoints may return these common errors:

**400 - Bad Request**:
```json
{
  "status": "error",
  "message": "Invalid request parameters",
  "error_code": "BAD_REQUEST"
}
```

**401 - Unauthorized**:
```json
{
  "status": "error",
  "message": "Authentication required",
  "error_code": "UNAUTHORIZED"
}
```

**403 - Forbidden**:
```json
{
  "status": "error",
  "message": "Access forbidden",
  "error_code": "FORBIDDEN"
}
```

**429 - Too Many Requests**:
```json
{
  "status": "error",
  "message": "Rate limit exceeded",
  "error_code": "RATE_LIMITED",
  "retry_after": 60
}
```

**500 - Internal Server Error**:
```json
{
  "status": "error",
  "message": "Internal server error",
  "error_code": "INTERNAL_ERROR"
}
```

### Rate Limiting Headers

All responses include rate limiting information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642262400
Retry-After: 60
```

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests per window |
| `X-RateLimit-Remaining` | Remaining requests in current window |
| `X-RateLimit-Reset` | Unix timestamp when limit resets |
| `Retry-After` | Seconds to wait before retrying (when rate limited) |

## Usage Examples

### cURL Examples

```bash
# Get bot information
curl -X GET "https://yourdomain.com/api/info"

# Get error logs with pagination
curl -X GET "https://yourdomain.com/api/logs" \
  -G \
  -d "token=your_access_token" \
  -d "level=ERROR" \
  -d "limit=50" \
  -d "page=1"

# Download a file
curl -X GET "https://yourdomain.com/dl/encoded_id/filename.pdf" \
  -o "downloaded_file.pdf"

# Download with range request (first 1024 bytes)
curl -X GET "https://yourdomain.com/dl/encoded_id/filename.pdf" \
  -H "Range: bytes=0-1023" \
  -o "partial_file.pdf"
```

### Python Examples

```python
import requests

# Get bot information
response = requests.get('https://yourdomain.com/api/info')
data = response.json()
print(f"Bot status: {data['bot_status']}")

# Get logs (admin only)
response = requests.get('https://yourdomain.com/api/logs', params={
    'token': 'your_token',
    'level': 'ERROR',
    'limit': 50
})
logs = response.json()

# Download file with progress
def download_file(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('Content-Length', 0))
    
    with open(filename, 'wb') as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            progress = (downloaded / total_size) * 100
            print(f"Progress: {progress:.1f}%")
```

### JavaScript Examples

```javascript
// Get bot information
async function getBotInfo() {
    try {
        const response = await fetch('https://yourdomain.com/api/info');
        const data = await response.json();
        console.log('Bot info:', data);
    } catch (error) {
        console.error('Error:', error);
    }
}

// Download file with progress tracking
async function downloadFile(url, filename) {
    const response = await fetch(url);
    const contentLength = response.headers.get('Content-Length');
    const total = parseInt(contentLength, 10);
    
    const reader = response.body.getReader();
    let downloaded = 0;
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        downloaded += value.length;
        const progress = (downloaded / total) * 100;
        console.log(`Progress: ${progress.toFixed(1)}%`);
    }
}
```

For more integration examples, see the [Examples section](examples.md). 