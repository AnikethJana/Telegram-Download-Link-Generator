---
title: API Examples
description: Code examples for using the StreamBot API
---

# API Examples

This page provides practical examples of how to use the StreamBot API in various programming languages.

## Authentication

Most API endpoints require authentication. You can authenticate using an admin token in the headers:

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
     https://your-streambot-domain.com/api/info
```

## Download File

### Example: Download a file using the download endpoint

```bash
curl -o downloaded_file.pdf \
     https://your-streambot-domain.com/dl/file_id_here
```

### Python Example

```python
import requests

def download_file(file_id, output_path):
    """Download a file from StreamBot"""
    url = f"https://your-streambot-domain.com/dl/{file_id}"
    
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"Downloaded file to {output_path}")

# Usage
download_file("your_file_id", "downloaded_file.pdf")
```

### JavaScript Example

```javascript
async function downloadFile(fileId, fileName) {
    const url = `https://your-streambot-domain.com/dl/${fileId}`;
    
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Download failed');
        
        const blob = await response.blob();
        
        // Create download link
        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
        console.error('Download failed:', error);
    }
}

// Usage
downloadFile('your_file_id', 'downloaded_file.pdf');
```

## Get Bot Information

### Get bot status and statistics

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
     https://your-streambot-domain.com/api/info
```

### Python Example

```python
import requests

def get_bot_info(admin_token):
    """Get bot information and statistics"""
    headers = {'Authorization': f'Bearer {admin_token}'}
    url = "https://your-streambot-domain.com/api/info"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json()

# Usage
info = get_bot_info("your_admin_token")
print(f"Bot status: {info['status']}")
print(f"Total users: {info['users_count']}")
```

### Response Example

```json
{
    "status": "running",
    "uptime": "2 days, 14 hours",
    "users_count": 1250,
    "files_served": 8432,
    "total_bandwidth": "45.2 GB",
    "version": "1.0.0"
}
```

## Error Handling

### Common Error Responses

```json
{
    "error": "File not found",
    "code": 404,
    "message": "The requested file could not be found"
}
```

```json
{
    "error": "Unauthorized",
    "code": 401,
    "message": "Valid authentication token required"
}
```

```json
{
    "error": "Rate limited",
    "code": 429,
    "message": "Too many requests, please try again later"
}
```

### Python Error Handling Example

```python
import requests
from requests.exceptions import RequestException

def safe_api_call(url, headers=None):
    """Make a safe API call with proper error handling"""
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print("File not found")
        elif response.status_code == 401:
            print("Authentication failed")
        elif response.status_code == 429:
            print("Rate limited, please wait")
        else:
            print(f"API error: {response.status_code}")
            
    except RequestException as e:
        print(f"Request failed: {e}")
    
    return None
```

## Integration Examples

### Webhook Integration

If you want to be notified when files are uploaded:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle StreamBot webhook notifications"""
    data = request.get_json()
    
    if data.get('event') == 'file_uploaded':
        file_id = data['file_id']
        user_id = data['user_id']
        filename = data['filename']
        
        print(f"New file uploaded: {filename} by user {user_id}")
        print(f"Download link: https://your-domain.com/dl/{file_id}")
        
        # Your custom logic here
        
    return jsonify({'status': 'received'})

if __name__ == '__main__':
    app.run(port=5000)
```

### Batch Download

```python
import requests
import os
from concurrent.futures import ThreadPoolExecutor

def download_multiple_files(file_ids, output_dir):
    """Download multiple files concurrently"""
    os.makedirs(output_dir, exist_ok=True)
    
    def download_single(file_id):
        url = f"https://your-streambot-domain.com/dl/{file_id}"
        response = requests.get(url, stream=True)
        
        if response.ok:
            filename = f"{file_id}"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return f"Downloaded: {filename}"
        else:
            return f"Failed: {file_id}"
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(download_single, file_ids))
    
    return results

# Usage
file_ids = ['file1', 'file2', 'file3']
results = download_multiple_files(file_ids, './downloads')
for result in results:
    print(result)
```

## Rate Limiting

Be aware of rate limits when making API calls:

- **Download endpoints**: No authentication required, but IP-based rate limiting may apply
- **Admin endpoints**: Require authentication, limited to authorized users
- **Recommended**: Implement exponential backoff for retries

```python
import time
import random

def api_call_with_retry(url, headers=None, max_retries=3):
    """API call with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 429:  # Rate limited
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Rate limited, waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                continue
                
            return response
            
        except RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)
    
    return None
```

print(response.json()) 