---
title: API Overview
description: Introduction to the StreamBot REST API for integrations and streaming
---

# StreamBot API

StreamBot provides a comprehensive RESTful API for interacting with the bot's functionality, monitoring system status, accessing download/streaming endpoints, and administrative features. All endpoints return JSON responses and support CORS for web application integration.

## API Basics

**Base URL**: `https://yourdomain.com` (configured via `BASE_URL` environment variable)

## Authentication Methods

The API endpoints are generally public for file access and do not require authentication:

<div class="grid" markdown>

<div class="card" markdown>

### Encoded File IDs

File downloads and streaming use encoded message IDs for secure access control.

```http
GET /dl/encoded_file_id HTTP/1.1
GET /stream/encoded_file_id HTTP/1.1
Host: yourdomain.com
```

</div>

</div>

## Rate Limiting

All API endpoints implement rate limiting to prevent abuse:

- Standard endpoints: 60 requests per minute
- Download/streaming endpoints: 10 requests per minute
- Range requests: Additional optimizations for video streaming

Rate limit headers are included in all responses:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1619135876
```

## Response Format

All API responses use a consistent JSON format:

```json
{
  "status": "ok",
  "data": {
    // Response data here
  }
}
```

Error responses follow this format:

```json
{
  "status": "error",
  "error": "Error message",
  "error_code": "ERROR_CODE"
}
```

## Available Endpoints

| Endpoint | Method | Description | Authentication | Video Support |
|----------|--------|-------------|---------------|---------------|
| `/api/info` | GET | Bot status and information | None | ✅ Streaming status |
| `/dl/{file_id}` | GET | Download file | None* | ✅ Range requests |
| `/stream/{file_id}` | GET | Stream video file | None* | ✅ Full streaming |

*File downloads and streaming use encoded IDs for access control

## Streaming Capabilities

### Video Streaming Endpoints

StreamBot now provides dedicated streaming endpoints with advanced features:

**Streaming URL Format:**
```
GET /stream/{encoded_file_id}
```

**Features:**
- **Range Request Support**: Full HTTP range request support for seeking
- **Progressive Loading**: Start playback while downloading
- **Multiple Formats**: Support for various video containers and codecs
- **Efficient Buffering**: Optimized for video streaming performance

**Example Range Request:**
```http
GET /stream/abc123def456 HTTP/1.1
Range: bytes=1048576-2097152
Host: yourdomain.com
```

### Download vs Streaming

| Feature | Download Endpoint | Streaming Endpoint |
|---------|------------------|-------------------|
| URL Pattern | `/dl/{file_id}` | `/stream/{file_id}` |
| Purpose | Full file download | Progressive video streaming |
| Range Support | ✅ Partial downloads | ✅ Video seeking |
| Video Optimized | ❌ | ✅ |
| File Types | All types | Video files |

## HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 206 | Partial Content (range requests) |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource does not exist |
| 416 | Range Not Satisfiable - Invalid range request |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server-side error |

## Content Types

The API works with the following content types:

- `application/json` for API requests and responses
- Various MIME types for file downloads and streaming:
  - Video: `video/mp4`, `video/webm`, `video/mkv`
  - Audio: `audio/mp3`, `audio/aac`, `audio/ogg`
  - Images: `image/jpeg`, `image/png`, `image/gif`
  - Documents: `application/pdf`, `text/plain`, etc.
- `multipart/form-data` for file uploads (when applicable)

## Video Streaming Features

### Supported Video Formats

**Container Formats:**
- MP4, MKV, AVI, WebM, MOV, 3GP

**Video Codecs:**
- H.264 (AVC), H.265 (HEVC), VP8, VP9, AV1

**Audio Codecs:**
- AAC, MP3, Opus, Vorbis

### Range Request Support

StreamBot provides full HTTP range request support for efficient video streaming:

```http
# Request first 1MB of video
Range: bytes=0-1048575

# Request from 1MB to 2MB
Range: bytes=1048576-2097151

# Request from 5MB to end of file
Range: bytes=5242880-
```

### Response Headers

Streaming responses include appropriate headers:

```http
HTTP/1.1 206 Partial Content
Content-Type: video/mp4
Content-Length: 1048576
Content-Range: bytes 0-1048575/104857600
Accept-Ranges: bytes
Cache-Control: public, max-age=3600
```

## Versioning

The current API version is integrated directly into the endpoints. Future versions will use the format:

```
/api/v2/endpoint
```

## Cross-Origin Resource Sharing (CORS)

The API supports CORS for web application integration. The following headers are included in responses:

```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, Range
Access-Control-Expose-Headers: Content-Range, Accept-Ranges
```

## Frontend Integration

### Video Player Integration

StreamBot integrates with video frontends using URL parameters:

```
{VIDEO_FRONTEND_URL}?stream={encoded_stream_url}
```

**Default Integration (Cricster):**
```
https://cricster.pages.dev?stream=https%3A//yourdomain.com/stream/abc123
```

**Custom Frontend Example:**
```javascript
// Extract stream URL from query parameter
const urlParams = new URLSearchParams(window.location.search);
const streamUrl = urlParams.get('stream');

// Use with HTML5 video element
const video = document.getElementById('videoPlayer');
video.src = streamUrl;
```

## API Explorer

Use the sections below to explore the available API endpoints in detail:

- [Endpoints Reference](endpoints.md) - Detailed documentation for each endpoint
- [Examples & Integration](examples.md) - Code examples for common scenarios
- [Authentication](authentication.md) - Authentication methods and security

## Testing the API

You can test the API endpoints using:

- **cURL**: Command line HTTP client
- **Postman**: GUI-based API testing tool
- **Your browser**: For GET endpoints like `/api/info`
- **Programming languages**: Python, JavaScript, etc.

### Quick Test

```bash
# Test if the API is accessible
curl https://yourdomain.com/api/info

# Test video streaming with range request
curl -H "Range: bytes=0-1048576" https://yourdomain.com/stream/your_file_id

# Test download endpoint
curl -O https://yourdomain.com/dl/your_file_id
```

## Performance Considerations

### Streaming Optimization

- **Range Requests**: Use range requests for efficient video seeking
- **Chunk Size**: Optimal chunk sizes for different network conditions
- **Caching**: Implement client-side caching for better performance
- **CDN Integration**: Use CDN for global content delivery

### Rate Limiting

- **Respect Limits**: Stay within rate limit boundaries
- **Exponential Backoff**: Implement retry logic with exponential backoff
- **Multiple Clients**: Use multiple client tokens for higher throughput

## Integration Examples

### Video Streaming in Web App

```html
<video id="videoPlayer" controls>
    <source src="https://yourdomain.com/stream/file_id" type="video/mp4">
    Your browser does not support the video tag.
</video>

<script>
const video = document.getElementById('videoPlayer');

// Enable seeking with range requests
video.addEventListener('seeking', function() {
    console.log('Seeking to:', video.currentTime);
});

// Handle loading events
video.addEventListener('loadstart', function() {
    console.log('Started loading video');
});
</script>
```

### Download Progress Tracking

```javascript
async function downloadWithProgress(fileId) {
    const response = await fetch(`https://yourdomain.com/dl/${fileId}`);
    const contentLength = response.headers.get('Content-Length');
    const total = parseInt(contentLength, 10);
    
    const reader = response.body.getReader();
    let received = 0;
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        received += value.length;
        const progress = (received / total) * 100;
        console.log(`Progress: ${progress.toFixed(1)}%`);
    }
}
```

This API overview provides comprehensive information about StreamBot's REST API with full video streaming support. For detailed endpoint documentation, see the [Endpoints Reference](endpoints.md). 