---
title: API Endpoints
description: Detailed documentation for all StreamBot API endpoints including streaming
---

# API Endpoints Reference

This page provides detailed documentation for all available StreamBot API endpoints including the new video streaming capabilities.

## System Information

### GET `/api/info`

Returns comprehensive bot status and configuration information including video streaming status.

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
    "link_expiry_duration_human": "24 hours",
    "video_streaming": true,
    "video_frontend_url": "https://cricster.pages.dev"
  },
  "bandwidth_info": {
    "limit_gb": 100,
    "used_gb": 45.234,
    "used_bytes": 48573440000,
    "month": "2024-01",
    "limit_enabled": true,
    "remaining_gb": 54.766
  },
  "streaming_info": {
    "active_streams": 12,
    "supported_formats": ["mp4", "mkv", "avi", "webm", "mov"],
    "range_requests_supported": true,
    "seeking_supported": true
  },
  "uptime": "2d 14h 32m 18s",
  "server_time_utc": "2024-01-15T14:30:45.123456Z",
  "totaluser": 1250,
  "github_repo": "https://github.com/AnikethJana/Telegram-Download-Link-Generator"
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
| `streaming_info` | object | Video streaming status and capabilities |
| `uptime` | string | Human-readable bot uptime |
| `server_time_utc` | string | Current server time in UTC ISO format |
| `totaluser` | integer | Total number of registered users |
| `github_repo` | string | Repository URL |

## File Downloads

### GET `/dl/{encoded_id}`

Download files via generated download links with range request support.

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

## Video Streaming

### GET `/stream/{encoded_id}`

Stream video files with full seeking support and range requests.

**Authentication**: None (uses encoded file IDs for security)

**Request**:
```http
GET /stream/VGhpcyBpcyBhIGZha2UgZW5jb2RlZCBpZA HTTP/1.1
Host: yourdomain.com
Range: bytes=1048576-2097151
User-Agent: Mozilla/5.0 (compatible)
```

**Response (Success - 200/206)**:
```http
HTTP/1.1 206 Partial Content
Content-Type: video/mp4
Content-Length: 1048576
Content-Range: bytes 1048576-2097151/104857600
Accept-Ranges: bytes
Cache-Control: public, max-age=3600

[Binary video content]
```

**Supported Video Formats**:

| Format | MIME Type | Description |
|--------|-----------|-------------|
| MP4 | `video/mp4` | Most compatible format |
| MKV | `video/x-matroska` | High quality container |
| WebM | `video/webm` | Web-optimized format |

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

# Stream a video with range request
curl -X GET "https://yourdomain.com/stream/encoded_id" \
  -H "Range: bytes=0-1048575" \
  -o "video_chunk.mp4"
```

### Python Examples

```python
import requests

# Get bot information
response = requests.get('https://yourdomain.com/api/info')
data = response.json()
print(f"Video streaming: {data['features']['video_streaming']}")

# Stream video with range requests
def stream_video_chunk(encoded_id, start_byte, end_byte):
    headers = {'Range': f'bytes={start_byte}-{end_byte}'}
    response = requests.get(
        f'https://yourdomain.com/stream/{encoded_id}',
        headers=headers,
        stream=True
    )
    return response.content
```

### JavaScript Examples

```javascript
// Setup video streaming
function setupVideoStreaming(encodedId) {
    const video = document.getElementById('videoPlayer');
    const streamUrl = `https://yourdomain.com/stream/${encodedId}`;
    
    video.src = streamUrl;
    
    // Handle seeking events
    video.addEventListener('seeking', function() {
        console.log('Seeking to:', video.currentTime);
    });
}
```

For more integration examples, see the [Examples section](examples.md). 