---
title: API Examples
description: Comprehensive code examples for using the StreamBot API with video streaming support
---

# API Examples

This page provides practical examples of how to use the StreamBot API in various programming languages, including the new video streaming capabilities.

## System Information

### Get Bot Status and Video Streaming Info

Get comprehensive bot information including video streaming capabilities:

```bash
curl -X GET "https://yourdomain.com/api/info" \
  -H "Accept: application/json"
```

### Python Example

```python
import requests
import json

def get_bot_info():
    """Get comprehensive bot information including video streaming status."""
    url = "https://yourdomain.com/api/info"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"Bot Status: {data['status']}")
        print(f"Bot Username: @{data['bot_info']['username']}")
        print(f"Total Users: {data['totaluser']}")
        print(f"Uptime: {data['uptime']}")
        
        # Video streaming information
        streaming_info = data.get('streaming_info', {})
        if streaming_info:
            print(f"\nVideo Streaming Features:")
            print(f"  Active Streams: {streaming_info['active_streams']}")
            print(f"  Supported Formats: {', '.join(streaming_info['supported_formats'])}")
            print(f"  Range Requests: {streaming_info['range_requests_supported']}")
            print(f"  Seeking Support: {streaming_info['seeking_supported']}")
        
        # Bandwidth information
        bandwidth = data.get('bandwidth_info', {})
        if bandwidth:
            print(f"\nBandwidth Usage:")
            print(f"  Used: {bandwidth['used_gb']:.2f} GB")
            print(f"  Limit: {bandwidth['limit_gb']} GB")
            print(f"  Remaining: {bandwidth['remaining_gb']:.2f} GB")
        
        return data
        
    except requests.RequestException as e:
        print(f"Error fetching bot info: {e}")
        return None

# Usage
bot_info = get_bot_info()
```

### JavaScript Example

```javascript
async function getBotInfo() {
    try {
        const response = await fetch('https://yourdomain.com/api/info');
        if (!response.ok) throw new Error('Failed to fetch bot info');
        
        const data = await response.json();
        
        console.log('Bot Information:');
        console.log(`Status: ${data.status}`);
        console.log(`Username: @${data.bot_info.username}`);
        console.log(`Total Users: ${data.totaluser}`);
        
        // Display video streaming capabilities
        if (data.streaming_info) {
            console.log('\nVideo Streaming:');
            console.log(`Active Streams: ${data.streaming_info.active_streams}`);
            console.log(`Supported Formats: ${data.streaming_info.supported_formats.join(', ')}`);
            console.log(`Range Requests: ${data.streaming_info.range_requests_supported}`);
        }
        
        return data;
    } catch (error) {
        console.error('Error:', error);
        return null;
    }
}

// Usage
getBotInfo();
```

## File Downloads

### Basic File Download

Download files using the download endpoint:

```bash
curl -O -J "https://yourdomain.com/dl/encoded_file_id"
```

### Download with Progress Tracking

```python
import requests
from tqdm import tqdm

def download_file_with_progress(file_id, output_path):
    """Download a file from StreamBot with progress tracking."""
    url = f"https://yourdomain.com/dl/{file_id}"
    
    try:
        # Get file size first
        head_response = requests.head(url)
        total_size = int(head_response.headers.get('Content-Length', 0))
        
        # Download with progress bar
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as file, tqdm(
            desc=output_path,
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as progress_bar:
            for chunk in response.iter_content(chunk_size=8192):
                size = file.write(chunk)
                progress_bar.update(size)
        
        print(f"Downloaded: {output_path}")
        return True
        
    except requests.RequestException as e:
        print(f"Download failed: {e}")
        return False

# Usage
success = download_file_with_progress("your_file_id", "downloaded_file.pdf")
```

### Range Requests for Large Files

```python
def download_file_range(file_id, start_byte, end_byte, output_path):
    """Download a specific range of bytes from a file."""
    url = f"https://yourdomain.com/dl/{file_id}"
    headers = {'Range': f'bytes={start_byte}-{end_byte}'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded bytes {start_byte}-{end_byte} to {output_path}")
        return True
        
    except requests.RequestException as e:
        print(f"Range download failed: {e}")
        return False

# Download first 1MB of a file
download_file_range("your_file_id", 0, 1048575, "partial_file.bin")
```

## Video Streaming

### Stream Video with Range Requests

```python
import requests

def stream_video_chunk(file_id, start_byte, end_byte):
    """Stream a specific chunk of video for seeking functionality."""
    url = f"https://yourdomain.com/stream/{file_id}"
    headers = {'Range': f'bytes={start_byte}-{end_byte}'}
    
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Check if range request was successful
        if response.status_code == 206:
            print(f"Partial content: {response.headers.get('Content-Range')}")
            return response.content
        else:
            print("Range request not supported")
            return response.content
            
    except requests.RequestException as e:
        print(f"Streaming failed: {e}")
        return None

# Stream first 2MB for video preview
video_chunk = stream_video_chunk("your_video_id", 0, 2097151)
```

### JavaScript Video Player Integration

```javascript
class StreamBotVideoPlayer {
    constructor(videoElement, streamUrl) {
        this.video = videoElement;
        this.streamUrl = streamUrl;
        this.setupPlayer();
    }
    
    setupPlayer() {
        // Set video source
        this.video.src = this.streamUrl;
        
        // Handle seeking events
        this.video.addEventListener('seeking', () => {
            console.log(`Seeking to: ${this.video.currentTime}s`);
        });
        
        // Handle loading events
        this.video.addEventListener('loadstart', () => {
            console.log('Started loading video');
        });
        
        this.video.addEventListener('canplay', () => {
            console.log('Video can start playing');
        });
        
        // Handle errors
        this.video.addEventListener('error', (e) => {
            console.error('Video error:', e);
        });
    }
    
    // Custom seeking method
    seekTo(timeInSeconds) {
        if (this.video.readyState >= 2) { // HAVE_CURRENT_DATA
            this.video.currentTime = timeInSeconds;
        }
    }
}

// Usage
const videoElement = document.getElementById('videoPlayer');
const encodedId = 'your_encoded_video_id';
const streamUrl = `https://yourdomain.com/stream/${encodedId}`;

const player = new StreamBotVideoPlayer(videoElement, streamUrl);

// Seek to 30 seconds
player.seekTo(30);
```

### Frontend Integration Examples

#### Cricster Frontend Integration

```javascript
// Integrate with default Cricster frontend
function playVideoWithCricster(streamUrl) {
    const cricsterUrl = 'https://cricster.pages.dev';
    const encodedStreamUrl = encodeURIComponent(streamUrl);
    const frontendUrl = `${cricsterUrl}?stream=${encodedStreamUrl}`;
    
    // Open in new window/tab
    window.open(frontendUrl, '_blank');
}

// Usage
const streamUrl = 'https://yourdomain.com/stream/encoded_video_id';
playVideoWithCricster(streamUrl);
```

#### Custom Frontend Integration

```javascript
// Integrate with custom video frontend
function playVideoWithCustomFrontend(streamUrl, frontendUrl) {
    const encodedStreamUrl = encodeURIComponent(streamUrl);
    const playerUrl = `${frontendUrl}?stream=${encodedStreamUrl}`;
    
    // Embed in iframe or open in new window
    const iframe = document.createElement('iframe');
    iframe.src = playerUrl;
    iframe.width = '800';
    iframe.height = '450';
    iframe.frameBorder = '0';
    iframe.allowFullscreen = true;
    
    document.getElementById('video-container').appendChild(iframe);
}

// Usage
const streamUrl = 'https://yourdomain.com/stream/encoded_video_id';
const customFrontend = 'https://my-video-player.example.com';
playVideoWithCustomFrontend(streamUrl, customFrontend);
```

## Advanced Video Streaming

### Adaptive Bitrate Streaming Simulation

```python
def get_video_quality_info(file_id):
    """Get video information for quality selection."""
    url = f"https://yourdomain.com/stream/{file_id}"
    
    try:
        # Head request to get video information
        response = requests.head(url)
        response.raise_for_status()
        
        content_length = int(response.headers.get('Content-Length', 0))
        content_type = response.headers.get('Content-Type', '')
        accept_ranges = response.headers.get('Accept-Ranges', '')
        
        return {
            'size': content_length,
            'type': content_type,
            'supports_ranges': accept_ranges == 'bytes',
            'estimated_bitrate': content_length * 8 / 1000  # Rough estimate
        }
        
    except requests.RequestException as e:
        print(f"Failed to get video info: {e}")
        return None

# Check video capabilities
video_info = get_video_quality_info("your_video_id")
if video_info:
    print(f"Video size: {video_info['size']:,} bytes")
    print(f"Type: {video_info['type']}")
    print(f"Range support: {video_info['supports_ranges']}")
```

### Video Thumbnail Generation

```python
def get_video_frame(file_id, timestamp_seconds):
    """Get a frame from video at specific timestamp (requires range requests)."""
    # This is a simplified example - actual implementation would need
    # video parsing libraries like opencv or ffmpeg
    url = f"https://yourdomain.com/stream/{file_id}"
    
    # Estimate byte position based on timestamp (very rough estimate)
    # In practice, you'd need proper video indexing
    estimated_byte_position = timestamp_seconds * 1000000  # Rough estimate
    range_size = 1048576  # 1MB chunk
    
    headers = {
        'Range': f'bytes={estimated_byte_position}-{estimated_byte_position + range_size}'
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 206:
            # This would normally be processed with video libraries
            # to extract actual frame data
            return response.content
        return None
        
    except requests.RequestException as e:
        print(f"Frame extraction failed: {e}")
        return None
```

## Error Handling

### Comprehensive Error Handling

```python
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
import time
import logging

class StreamBotAPIClient:
    def __init__(self, base_url, timeout=30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _make_request(self, method, endpoint, **kwargs):
        """Make a request with comprehensive error handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method, url, timeout=self.timeout, **kwargs
            )
            
            # Handle different status codes
            if response.status_code == 200:
                return response
            elif response.status_code == 206:  # Partial content
                return response
            elif response.status_code == 404:
                raise FileNotFoundError("File not found or expired")
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise TooManyRequestsError(f"Rate limited. Retry after {retry_after}s")
            elif response.status_code >= 500:
                raise ServerError(f"Server error: {response.status_code}")
            else:
                response.raise_for_status()
                
        except Timeout:
            raise TimeoutError("Request timed out")
        except ConnectionError:
            raise ConnectionError("Failed to connect to server")
        except RequestException as e:
            raise APIError(f"Request failed: {e}")
    
    def get_bot_info(self):
        """Get bot information with error handling."""
        try:
            response = self._make_request('GET', '/api/info')
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get bot info: {e}")
            return None
    
    def download_file(self, file_id, output_path, chunk_size=8192):
        """Download file with error handling and resume capability."""
        endpoint = f'/dl/{file_id}'
        
        # Check if partial file exists for resume
        start_byte = 0
        if os.path.exists(output_path):
            start_byte = os.path.getsize(output_path)
            self.logger.info(f"Resuming download from byte {start_byte}")
        
        headers = {}
        if start_byte > 0:
            headers['Range'] = f'bytes={start_byte}-'
        
        try:
            response = self._make_request('GET', endpoint, headers=headers, stream=True)
            
            mode = 'ab' if start_byte > 0 else 'wb'
            with open(output_path, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
            
            self.logger.info(f"Download completed: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return False

# Custom exceptions
class APIError(Exception):
    pass

class TooManyRequestsError(APIError):
    pass

class ServerError(APIError):
    pass

# Usage
client = StreamBotAPIClient("https://yourdomain.com")
info = client.get_bot_info()
success = client.download_file("file_id", "output.pdf")
```

## Batch Operations

### Batch File Downloads

```python
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

async def download_multiple_files(file_ids, base_url, output_dir):
    """Download multiple files concurrently."""
    os.makedirs(output_dir, exist_ok=True)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, file_id in enumerate(file_ids):
            output_path = os.path.join(output_dir, f"file_{i}_{file_id}")
            task = download_single_file(session, base_url, file_id, output_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

async def download_single_file(session, base_url, file_id, output_path):
    """Download a single file asynchronously."""
    url = f"{base_url}/dl/{file_id}"
    
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
            
            return f"Downloaded: {output_path}"
            
    except Exception as e:
        return f"Failed to download {file_id}: {e}"

# Usage
file_ids = ['file1_id', 'file2_id', 'file3_id']
results = asyncio.run(download_multiple_files(
    file_ids, 
    "https://yourdomain.com", 
    "./downloads"
))

for result in results:
    print(result)
```

## Integration Examples

### Discord Bot Integration

```python
import discord
from discord.ext import commands
import requests

class StreamBotIntegration(commands.Cog):
    def __init__(self, bot, streambot_url):
        self.bot = bot
        self.streambot_url = streambot_url
    
    @commands.command(name='stream')
    async def stream_video(self, ctx, file_id: str):
        """Stream a video from StreamBot."""
        stream_url = f"{self.streambot_url}/stream/{file_id}"
        frontend_url = f"https://cricster.pages.dev?stream={requests.utils.quote(stream_url)}"
        
        embed = discord.Embed(
            title="🎬 Video Stream",
            description="Click the link below to watch the video",
            color=0x00ff00
        )
        embed.add_field(
            name="Stream Link", 
            value=f"[Watch Video]({frontend_url})", 
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='download')
    async def download_file(self, ctx, file_id: str):
        """Get download link from StreamBot."""
        download_url = f"{self.streambot_url}/dl/{file_id}"
        
        # Verify file exists
        try:
            response = requests.head(download_url, timeout=10)
            if response.status_code == 200:
                embed = discord.Embed(
                    title="📥 Download Ready",
                    description="Click the link below to download",
                    color=0x0099ff
                )
                embed.add_field(
                    name="Download Link", 
                    value=f"[Download File]({download_url})", 
                    inline=False
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ File not found or expired")
        except requests.RequestException:
            await ctx.send("❌ Unable to verify file")

# Setup
bot = commands.Bot(command_prefix='!')
bot.add_cog(StreamBotIntegration(bot, "https://yourdomain.com"))
```

### Website Integration

```html
<!DOCTYPE html>
<html>
<head>
    <title>StreamBot File Viewer</title>
    <style>
        .video-container {
            width: 100%;
            max-width: 800px;
            margin: 20px auto;
        }
        
        .file-info {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin: 20px auto;
            max-width: 800px;
        }
        
        video {
            width: 100%;
            height: auto;
        }
    </style>
</head>
<body>
    <h1>StreamBot File Viewer</h1>
    
    <div class="file-info">
        <h3>File Information</h3>
        <p id="file-info">Loading...</p>
        
        <h3>Actions</h3>
        <button onclick="playVideo()">🎬 Play Video</button>
        <button onclick="downloadFile()">📥 Download</button>
    </div>
    
    <div class="video-container">
        <video id="videoPlayer" controls style="display: none;">
            Your browser does not support video playback.
        </video>
    </div>

    <script>
        const fileId = 'your_file_id_here';
        const baseUrl = 'https://yourdomain.com';
        
        // Load file information
        async function loadFileInfo() {
            try {
                const response = await fetch(`${baseUrl}/api/info`);
                const data = await response.json();
                
                document.getElementById('file-info').innerHTML = `
                    <strong>Bot Status:</strong> ${data.status}<br>
                    <strong>Video Streaming:</strong> ${data.features?.video_streaming ? 'Enabled' : 'Disabled'}<br>
                    <strong>Frontend:</strong> ${data.features?.video_frontend_url || 'None'}
                `;
            } catch (error) {
                document.getElementById('file-info').innerHTML = 'Error loading file info';
            }
        }
        
        function playVideo() {
            const video = document.getElementById('videoPlayer');
            video.src = `${baseUrl}/stream/${fileId}`;
            video.style.display = 'block';
            video.load();
        }
        
        function downloadFile() {
            window.open(`${baseUrl}/dl/${fileId}`, '_blank');
        }
        
        // Load info on page load
        loadFileInfo();
    </script>
</body>
</html>
```

## Performance Optimization

### Connection Pooling

```python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class OptimizedStreamBotClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = self._create_session()
    
    def _create_session(self):
        """Create optimized session with connection pooling."""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'User-Agent': 'StreamBot-Client/1.0',
            'Accept': 'application/json',
        })
        
        return session
    
    def stream_with_cache(self, file_id, use_cache=True):
        """Stream with client-side caching."""
        cache_headers = {}
        if use_cache:
            cache_headers['Cache-Control'] = 'max-age=3600'
        
        response = self.session.get(
            f"{self.base_url}/stream/{file_id}",
            headers=cache_headers,
            stream=True
        )
        return response

# Usage
client = OptimizedStreamBotClient("https://yourdomain.com")
```

This comprehensive API examples documentation now includes all the modern StreamBot features including video streaming, range requests, frontend integration, and advanced error handling patterns. 