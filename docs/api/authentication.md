---
title: API Authentication
description: How to authenticate with the StreamBot API
---

# API Authentication

StreamBot uses token-based authentication for accessing administrative API endpoints. This guide explains how to obtain and use authentication tokens.

## Authentication Methods

### 1. Admin Token Authentication

For administrative endpoints, you need to provide an admin token in the request headers.

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
     https://your-streambot-domain.com/api/info
```

### 2. No Authentication (Public Endpoints)

Some endpoints like file downloads don't require authentication:

```bash
curl https://your-streambot-domain.com/dl/file_id_here
```

## Obtaining Admin Tokens

### Method 1: Environment Configuration

The primary admin token is configured in your `.env` file:

```env
# Admin Configuration
ADMIN_IDS=123456789,987654321
JWT_SECRET=your_secure_jwt_secret_here
```

### Method 2: Generate Token via Bot

If you're configured as an admin user, you can generate an API token through the Telegram bot:

1. Send `/token` command to the bot
2. The bot will generate a secure API token for you
3. Use this token in your API requests

## Using Authentication Tokens

### Request Headers

Include the token in the `Authorization` header:

```http
GET /api/info HTTP/1.1
Host: your-streambot-domain.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
```

### Example Requests

#### Python

```python
import requests

headers = {
    'Authorization': 'Bearer YOUR_ADMIN_TOKEN',
    'Content-Type': 'application/json'
}

response = requests.get(
    'https://your-streambot-domain.com/api/info',
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    print(f"Bot status: {data['status']}")
else:
    print(f"Error: {response.status_code}")
```

#### JavaScript

```javascript
const token = 'YOUR_ADMIN_TOKEN';

const response = await fetch('https://your-streambot-domain.com/api/info', {
    method: 'GET',
    headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    }
});

if (response.ok) {
    const data = await response.json();
    console.log('Bot status:', data.status);
} else {
    console.error('Error:', response.status);
}
```

#### cURL

```bash
curl -X GET \
  https://your-streambot-domain.com/api/info \
  -H 'Authorization: Bearer YOUR_ADMIN_TOKEN' \
  -H 'Content-Type: application/json'
```

## Token Security

### Best Practices

1. **Keep tokens secure**: Never expose tokens in client-side code
2. **Use environment variables**: Store tokens in environment variables, not in code
3. **Regular rotation**: Rotate tokens periodically for security
4. **Limited scope**: Use the minimum required permissions

### Token Storage

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Store token in environment variable
ADMIN_TOKEN = os.getenv('STREAMBOT_ADMIN_TOKEN')

def make_authenticated_request(endpoint):
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = requests.get(f'https://your-domain.com/api/{endpoint}', headers=headers)
    return response.json()
```

### Environment File Example

```env
# .env file
STREAMBOT_ADMIN_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
STREAMBOT_API_BASE_URL=https://your-streambot-domain.com
```

## API Endpoints by Authentication Level

### Public Endpoints (No Authentication)

| Endpoint | Description |
|----------|-------------|
| `GET /dl/{file_id}` | Download file |
| `GET /` | Health check |

### Admin Endpoints (Authentication Required)

| Endpoint | Description |
|----------|-------------|
| `GET /api/info` | Bot information and statistics |
| `GET /api/logs` | Access logs |
| `GET /api/users` | User statistics |
| `POST /api/broadcast` | Send broadcast message |
| `DELETE /api/cleanup` | Clean up expired files |

## Error Handling

### Authentication Errors

#### 401 Unauthorized

```json
{
    "error": "Unauthorized",
    "code": 401,
    "message": "Valid authentication token required"
}
```

**Causes:**
- Missing Authorization header
- Invalid token format
- Expired token
- Revoked token

#### 403 Forbidden

```json
{
    "error": "Forbidden",
    "code": 403,
    "message": "Insufficient permissions"
}
```

**Causes:**
- Valid token but insufficient permissions
- User not in admin list
- IP address restrictions

### Handling Authentication Errors

```python
import requests

def make_api_request(endpoint, token):
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(
            f'https://your-domain.com/api/{endpoint}',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 401:
            print("Authentication failed. Please check your token.")
            return None
        elif response.status_code == 403:
            print("Access denied. Insufficient permissions.")
            return None
        elif response.status_code == 200:
            return response.json()
        else:
            print(f"API error: {response.status_code}")
            return None
            
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None
```

## Token Management

### Token Information

Tokens contain the following information:

- **User ID**: Telegram user ID of the token owner
- **Permissions**: List of allowed actions
- **Expiration**: Token expiry time (if applicable)
- **Issue time**: When the token was created

### Verifying Token

You can verify your token by calling the info endpoint:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-streambot-domain.com/api/info
```

If the token is valid, you'll receive bot information. If invalid, you'll get a 401 error.

### Revoking Tokens

To revoke a token:

1. **Via Bot**: Send `/revoke_token` command to the Telegram bot
2. **Via Environment**: Remove/change the JWT_SECRET in your `.env` file (invalidates all tokens)
3. **Via Admin Panel**: Use the admin API to revoke specific tokens

## Rate Limiting

Authenticated requests are subject to rate limiting:

- **Admin users**: 100 requests per minute
- **Regular users**: 10 requests per minute
- **Global**: 1000 requests per minute across all users

### Rate Limit Headers

Response headers include rate limit information:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

### Handling Rate Limits

```python
import time

def api_call_with_rate_limit(endpoint, token):
    headers = {'Authorization': f'Bearer {token}'}
    
    response = requests.get(
        f'https://your-domain.com/api/{endpoint}',
        headers=headers
    )
    
    if response.status_code == 429:  # Rate limited
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        wait_time = max(0, reset_time - int(time.time()))
        
        print(f"Rate limited. Waiting {wait_time} seconds...")
        time.sleep(wait_time + 1)
        
        # Retry the request
        return api_call_with_rate_limit(endpoint, token)
    
    return response
```

## Security Considerations

### Token Transmission

- Always use HTTPS for API requests
- Never include tokens in URLs or logs
- Use secure headers for token transmission

### Token Storage

- Store tokens securely (encrypted if possible)
- Don't commit tokens to version control
- Use environment variables or secure key stores

### Monitoring

Monitor for:
- Unusual API access patterns
- Failed authentication attempts
- Token usage from unexpected IP addresses

```python
# Example: Logging authentication events
import logging

def log_api_access(endpoint, success, user_id=None):
    if success:
        logging.info(f"API access: {endpoint} by user {user_id}")
    else:
        logging.warning(f"Failed API access attempt: {endpoint}")
``` 