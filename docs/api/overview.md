---
title: API Overview
description: Introduction to the StreamBot REST API for integrations
---

# StreamBot API

StreamBot provides a RESTful API for interacting with the bot's functionality, monitoring system status, and accessing administrative features. All endpoints return JSON responses and support CORS for web application integration.

## API Basics

**Base URL**: `https://yourdomain.com` (configured via `BASE_URL` environment variable)

## Authentication Methods

The API endpoints are generally public and do not require authentication:

<div class="grid" markdown>

<div class="card" markdown>

### Encoded File IDs

File downloads use encoded message IDs for secure access control.

```http
GET /dl/encoded_file_id HTTP/1.1
Host: yourdomain.com
```

</div>

</div>

## Rate Limiting

All API endpoints implement rate limiting to prevent abuse:

- Standard endpoints: 60 requests per minute
- Download endpoints: 10 requests per minute

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

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|---------------|
| `/api/info` | GET | Bot status and information | None |
| `/dl/{file_id}` | GET | Download file | None* |

*File downloads use encoded IDs for access control

## HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource does not exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server-side error |

## Content Types

The API works with the following content types:

- `application/json` for API requests and responses
- Various MIME types for file downloads
- `multipart/form-data` for file uploads (when applicable)

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
Access-Control-Allow-Headers: Content-Type, Authorization
```

## API Explorer

Use the sections below to explore the available API endpoints in detail:

- [Endpoints Reference](endpoints.md) - Detailed documentation for each endpoint
- [Examples & Integration](examples.md) - Code examples for common scenarios

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
``` 