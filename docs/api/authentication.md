---
title: API Authentication
description: StreamBot API authentication methods and public endpoints
---

# API Authentication

StreamBot is designed with an open architecture where most endpoints are publicly accessible for file downloads and streaming. This guide explains the authentication model and available endpoints.

## Authentication Overview

StreamBot uses a minimal authentication approach focused on functionality rather than restricting access:

### Public Endpoints (No Authentication Required)

Most StreamBot endpoints are publicly accessible:

```bash
# File downloads - no authentication needed
curl https://your-streambot-domain.com/dl/encoded_file_id

# Video streaming - no authentication needed  
curl https://your-streambot-domain.com/stream/encoded_file_id

# Bot information - publicly accessible
curl https://your-streambot-domain.com/api/info
```

### Security Model

StreamBot uses **encoded file IDs** for access control instead of traditional authentication:

- Files are accessed via encoded message IDs that serve as secure tokens
- No user accounts or login systems required
- Access is controlled at the file level, not user level
- Rate limiting is applied based on IP address and usage patterns

## Available Endpoints

### File Access Endpoints

| Endpoint | Authentication | Description |
|----------|----------------|-------------|
| `GET /dl/{encoded_id}` | None | Download file via encoded ID |
| `GET /stream/{encoded_id}` | None | Stream video file with seeking support |
| `GET /api/info` | None | Bot status and capabilities |

### Encoded File ID Security

File access uses encoded IDs for security:

```bash
# Example encoded file ID
https://your-domain.com/dl/VGhpcyBpcyBhIGZha2UgZW5jb2RlZCBpZA

# Example streaming URL
https://your-domain.com/stream/VGhpcyBpcyBhIGZha2UgZW5jb2RlZCBpZA
```

**How it works:**
1. User uploads file to Telegram bot
2. Bot generates encoded ID based on message ID and security parameters
3. Encoded ID provides secure access without exposing internal message IDs
4. IDs can include expiration and access controls

## Usage Examples

### Python Example

```python
import requests

class StreamBotClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'StreamBot-Client/1.0'
        })
    
    def get_bot_info(self):
        """Get bot information - no authentication required."""
        try:
            response = self.session.get(f'{self.base_url}/api/info')
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching bot info: {e}")
            return None
    
    def download_file(self, encoded_id, output_path):
        """Download file using encoded ID."""
        try:
            url = f'{self.base_url}/dl/{encoded_id}'
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except requests.RequestException as e:
            print(f"Download failed: {e}")
            return False
    
    def stream_video_info(self, encoded_id):
        """Get video streaming information."""
        try:
            url = f'{self.base_url}/stream/{encoded_id}'
            response = self.session.head(url)
            response.raise_for_status()
            
            return {
                'content_type': response.headers.get('Content-Type'),
                'content_length': response.headers.get('Content-Length'),
                'accept_ranges': response.headers.get('Accept-Ranges'),
                'supports_streaming': response.headers.get('Accept-Ranges') == 'bytes'
            }
        except requests.RequestException as e:
            print(f"Stream info failed: {e}")
            return None

# Usage
client = StreamBotClient("https://your-streambot-domain.com")

# Get bot information
info = client.get_bot_info()
if info:
    print(f"Bot status: {info['status']}")
    print(f"Video streaming: {info.get('features', {}).get('video_streaming', False)}")

# Download a file
success = client.download_file("encoded_file_id", "download.pdf")

# Get video streaming info
stream_info = client.stream_video_info("encoded_video_id")
if stream_info:
    print(f"Supports streaming: {stream_info['supports_streaming']}")
```

### JavaScript Example

```javascript
class StreamBotAPI {
    constructor(baseUrl) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }
    
    async getBotInfo() {
        try {
            const response = await fetch(`${this.baseUrl}/api/info`);
            if (!response.ok) throw new Error('Failed to fetch bot info');
            return await response.json();
        } catch (error) {
            console.error('Error:', error);
            return null;
        }
    }
    
    async downloadFile(encodedId, filename) {
        try {
            const response = await fetch(`${this.baseUrl}/dl/${encodedId}`);
            if (!response.ok) throw new Error('Download failed');
            
            const blob = await response.blob();
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            return true;
        } catch (error) {
            console.error('Download failed:', error);
            return false;
        }
    }
    
    getStreamingUrl(encodedId) {
        return `${this.baseUrl}/stream/${encodedId}`;
    }
    
    getVideoPlayerUrl(encodedId, frontendUrl = 'https://cricster.pages.dev') {
        const streamUrl = this.getStreamingUrl(encodedId);
        return `${frontendUrl}?stream=${encodeURIComponent(streamUrl)}`;
    }
}

// Usage
const api = new StreamBotAPI('https://your-streambot-domain.com');

// Get bot information
api.getBotInfo().then(info => {
    if (info) {
        console.log('Bot Status:', info.status);
        console.log('Video Streaming:', info.features?.video_streaming);
    }
});

// Setup video player
function setupVideoPlayer(encodedId) {
    const streamUrl = api.getStreamingUrl(encodedId);
    const videoPlayerUrl = api.getVideoPlayerUrl(encodedId);
    
    // Direct video element
    const video = document.getElementById('videoPlayer');
    video.src = streamUrl;
    
    // Or open in Cricster player
    window.open(videoPlayerUrl, '_blank');
}
```

### cURL Examples

```bash
# Get bot information
curl -X GET "https://your-domain.com/api/info"

# Download a file
curl -O -J "https://your-domain.com/dl/encoded_file_id"

# Stream video with range request (for seeking)
curl -H "Range: bytes=0-1048575" \
     "https://your-domain.com/stream/encoded_video_id" \
     -o video_chunk.mp4

# Get file information
curl -I "https://your-domain.com/dl/encoded_file_id"

# Check streaming capabilities
curl -I "https://your-domain.com/stream/encoded_video_id"
```

## Error Handling

### Common Errors

#### 404 - File Not Found

```json
{
    "error": "File not found",
    "message": "The requested file could not be found or has expired"
}
```

**Causes:**
- Invalid encoded file ID
- File has been deleted from Telegram
- Link has expired (if expiration is configured)

#### 429 - Rate Limited

```json
{
    "error": "Rate limited",
    "message": "Too many requests. Please try again later.",
    "retry_after": 60
}
```

**Causes:**
- Too many requests from the same IP
- Daily download limit exceeded
- Bandwidth limit reached

#### 416 - Range Not Satisfiable

```json
{
    "error": "Range not satisfiable",
    "message": "The requested range is not valid for this file"
}
```

**Causes:**
- Invalid range request for video streaming
- Requested range exceeds file size

### Error Handling Example

```python
import requests
from requests.exceptions import RequestException

def safe_download(encoded_id, output_path, base_url):
    """Download with comprehensive error handling."""
    url = f"{base_url}/dl/{encoded_id}"
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return {"success": True, "message": "Download completed"}
            
        elif response.status_code == 404:
            return {"success": False, "error": "File not found or expired"}
            
        elif response.status_code == 429:
            retry_after = response.headers.get('Retry-After', 60)
            return {"success": False, "error": f"Rate limited. Try again in {retry_after}s"}
            
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except RequestException as e:
        return {"success": False, "error": f"Request failed: {e}"}

# Usage
result = safe_download("encoded_id", "file.pdf", "https://your-domain.com")
if result["success"]:
    print("Download successful!")
else:
    print(f"Download failed: {result['error']}")
```

## Rate Limiting

StreamBot implements rate limiting to ensure fair usage:

### Rate Limit Headers

Responses include rate limiting information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642262400
```

### Rate Limit Handling

```python
def handle_rate_limits(response):
    """Handle rate limit headers in responses."""
    if 'X-RateLimit-Remaining' in response.headers:
        remaining = int(response.headers['X-RateLimit-Remaining'])
        limit = int(response.headers.get('X-RateLimit-Limit', 0))
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        
        print(f"Rate limit: {remaining}/{limit} remaining")
        
        if remaining < 5:
            import time
            wait_time = reset_time - int(time.time())
            print(f"Warning: Only {remaining} requests remaining")
            if wait_time > 0:
                print(f"Rate limit resets in {wait_time} seconds")
```

## Integration Patterns

### Video Streaming Integration

```javascript
// Complete video streaming integration
class VideoStreamingClient {
    constructor(baseUrl, frontendUrl = 'https://cricster.pages.dev') {
        this.baseUrl = baseUrl;
        this.frontendUrl = frontendUrl;
    }
    
    // Get direct streaming URL
    getStreamUrl(encodedId) {
        return `${this.baseUrl}/stream/${encodedId}`;
    }
    
    // Get frontend player URL
    getPlayerUrl(encodedId) {
        const streamUrl = this.getStreamUrl(encodedId);
        return `${this.frontendUrl}?stream=${encodeURIComponent(streamUrl)}`;
    }
    
    // Embed video player
    embedPlayer(encodedId, containerId) {
        const playerUrl = this.getPlayerUrl(encodedId);
        const container = document.getElementById(containerId);
        
        const iframe = document.createElement('iframe');
        iframe.src = playerUrl;
        iframe.width = '100%';
        iframe.height = '400';
        iframe.frameBorder = '0';
        iframe.allowFullscreen = true;
        
        container.appendChild(iframe);
    }
    
    // Direct video element setup
    setupDirectVideo(encodedId, videoElementId) {
        const video = document.getElementById(videoElementId);
        video.src = this.getStreamUrl(encodedId);
        video.controls = true;
        
        return video;
    }
}

// Usage
const streaming = new VideoStreamingClient('https://your-domain.com');

// Option 1: Embed Cricster player
streaming.embedPlayer('video_id', 'player-container');

// Option 2: Direct video element
streaming.setupDirectVideo('video_id', 'video-element');
```

## Best Practices

1. **Handle Rate Limits**: Always check rate limit headers and implement backoff
2. **Error Handling**: Implement comprehensive error handling for all requests
3. **Use Streaming**: For videos, use the `/stream/` endpoint for better performance
4. **Cache Responses**: Cache bot info and file metadata when appropriate
5. **Validate IDs**: Check encoded ID format before making requests
6. **Monitor Usage**: Track your API usage to stay within limits

For more integration examples, see the [API Examples](examples.md) documentation. 