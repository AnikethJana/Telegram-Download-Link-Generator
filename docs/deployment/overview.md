---
title: Deployment Overview
description: Choose the best deployment method for StreamBot with video streaming support
---

# Deployment Overview

StreamBot is a highly flexible application that can be deployed in various environments. This guide helps you choose the best deployment method for your needs.

## Prerequisites

Before deploying StreamBot, ensure you have:

- **Python 3.11 or higher** installed
- **MongoDB 4.4+** (local or cloud instance like MongoDB Atlas)
- **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
- **Telegram API credentials** from [my.telegram.org](https://my.telegram.org)
- **Domain name** with SSL certificate (for production)
- **Sufficient storage** for temporary file caching
- **Adequate bandwidth** for video streaming capabilities

## System Requirements

### Minimum Requirements

| Resource | Requirement | Notes |
|----------|-------------|-------|
| **CPU** | 1 vCPU | For basic usage |
| **RAM** | 512 MB | Minimum for bot operation |
| **Storage** | 5 GB | For application and logs |
| **Bandwidth** | 100 Mbps | For download/streaming functionality |
| **OS** | Linux/Windows/macOS | Ubuntu 20.04+ recommended |

### Recommended Requirements

| Resource | Requirement | Notes |
|----------|-------------|-------|
| **CPU** | 2+ vCPU | For optimal video streaming performance |
| **RAM** | 2 GB+ | Better for multiple concurrent streams |
| **Storage** | 20 GB+ | For caching and better performance |
| **Bandwidth** | 1 Gbps+ | For high-quality video streaming |
| **OS** | Ubuntu 22.04 LTS | Most tested environment |

## Deployment Methods

<div class="grid cards" markdown>

- :fontawesome-brands-docker:{ .lg .middle } **Docker Deployment**

    ---

    The easiest and most reliable way to deploy StreamBot with consistent environments and easy scaling.

    [:octicons-arrow-right-24: Docker Guide](docker.md)

- :material-cloud:{ .lg .middle } **Cloud Platforms**

    ---

    Deploy on popular cloud platforms like AWS, Google Cloud, DigitalOcean, or Railway with pre-configured templates.

    [:octicons-arrow-right-24: Cloud Guide](cloud-platforms.md)

- :material-server:{ .lg .middle } **VPS/Dedicated Server**

    ---

    Full control deployment on your own Virtual Private Server or dedicated hardware.

    [:octicons-arrow-right-24: VPS Guide](vps-setup.md)

- :material-dev-to:{ .lg .middle } **Development Setup**

    ---

    Local development environment for testing and customization.

    [:octicons-arrow-right-24: Dev Guide](../getting-started/installation.md)

</div>

## Quick Deployment Options

### 1. Docker (Recommended)

**Best for**: Production deployments, consistent environments, easy updates

```bash
# Clone repository
git clone https://github.com/AnikethJana/Telegram-Download-Link-Generator.git
cd Telegram-Download-Link-Generator

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Deploy with Docker Compose
docker-compose up -d
```

**Advantages**:
- ✅ Consistent environment across platforms
- ✅ Easy updates and rollbacks
- ✅ Isolated dependencies
- ✅ Built-in health checks
- ✅ Simple scaling with compose
- ✅ Video streaming optimized configuration

### 2. Cloud Platform (One-Click)

**Best for**: Beginners, quick setup, managed infrastructure

**Supported Platforms**:
- Railway (One-click deploy)
- Heroku (Buildpack available)
- DigitalOcean App Platform
- Google Cloud Run
- AWS Elastic Beanstalk

**Railway Quick Deploy**:
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template-id)

### 3. VPS/Server

**Best for**: Custom configurations, high performance, full control

```bash
# Install dependencies
sudo apt update && sudo apt install python3.11 python3.11-pip mongodb

# Clone and setup
git clone https://github.com/AnikethJana/Telegram-Download-Link-Generator.git
cd Telegram-Download-Link-Generator
pip install -r requirements.txt

# Configure and run
cp .env.example .env
# Edit .env file
python -m StreamBot
```

## Environment Configuration

### Required Environment Variables

```env
# Telegram Configuration
API_ID=12345678
API_HASH=your_api_hash_from_my_telegram_org
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
LOG_CHANNEL=-1001234567890

# Database
DATABASE_URL=mongodb://localhost:27017/streambot

# Server Configuration
BASE_URL=https://yourdomain.com
PORT=8080

# Video Streaming (NEW)
VIDEO_FRONTEND_URL=https://cricster.pages.dev
# Set to 'false' to disable video frontend

# Optional Features
FORCE_SUB_CHANNELS=-1001234567890
LINK_EXPIRY_DURATION=86400
MONTHLY_BANDWIDTH_LIMIT_GB=100
USERS_DAILY_LIMIT=5
```

### Video Streaming Configuration

StreamBot now includes advanced video streaming capabilities:

**Default Configuration**:
- **Video Frontend**: `https://cricster.pages.dev` (automatically enabled)
- **Range Requests**: Fully supported for seeking
- **Supported Formats**: MP4, MKV, AVI, WebM, MOV
- **Streaming Optimization**: Automatic buffering and progressive loading

**To disable video frontend**:
```env
VIDEO_FRONTEND_URL=false
```

**To use custom video frontend**:
```env
VIDEO_FRONTEND_URL=https://your-custom-player.pages.dev
```

## Performance Considerations

### Video Streaming Optimization

For optimal video streaming performance:

**Server Configuration**:
- Use SSD storage for faster I/O
- Configure adequate RAM for file caching
- Ensure high bandwidth capacity
- Use CDN for global content delivery

**Network Optimization**:
- Enable HTTP/2 for better streaming
- Configure proper caching headers
- Use compression for metadata
- Implement rate limiting for stream protection

### Resource Planning

**Concurrent Users Estimation**:

| Users | CPU | RAM | Bandwidth | Storage |
|-------|-----|-----|-----------|---------|
| 1-100 | 1 vCPU | 1 GB | 100 Mbps | 10 GB |
| 100-500 | 2 vCPU | 2 GB | 500 Mbps | 20 GB |
| 500-1000 | 4 vCPU | 4 GB | 1 Gbps | 50 GB |
| 1000+ | 8+ vCPU | 8+ GB | 2+ Gbps | 100+ GB |

**Video Streaming Specific**:
- Each active stream: ~50-100 MB RAM
- HD video streaming: ~5-10 Mbps per user
- 4K video streaming: ~25-40 Mbps per user

## Security Considerations

### Essential Security Measures

1. **SSL/TLS Certificate**: Required for production deployment
2. **Environment Variables**: Keep credentials secure and never commit them
3. **Rate Limiting**: Prevent abuse with proper limits
4. **Access Control**: Use force subscription and admin controls
5. **Regular Updates**: Keep dependencies and base images updated
6. **Video Frontend Security**: Validate streaming URLs and implement CORS properly

### Network Security

```nginx
# Example Nginx configuration for video streaming
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Proxy to StreamBot
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Optimize for video streaming
    location /stream/ {
        proxy_pass http://localhost:8080;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

## Monitoring and Maintenance

### Health Checks

StreamBot provides several endpoints for monitoring:

```bash
# Basic health check
curl https://yourdomain.com/api/info

# Check streaming service
curl -I https://yourdomain.com/stream/test

# Memory and performance
curl https://yourdomain.com/api/info | jq '.streaming_info'
```

### Log Monitoring

```bash
# Docker logs
docker logs streambot-app -f

# File logs (if configured)
tail -f logs/streambot.log

# Filter for errors
docker logs streambot-app 2>&1 | grep ERROR
```

### Backup Strategy

**Critical Data to Backup**:
- Environment configuration (`.env`)
- MongoDB database
- Application logs
- SSL certificates
- Custom configurations

**Automated Backup Script**:
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/$DATE"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup MongoDB
mongodump --db streambot --out $BACKUP_DIR/mongodb

# Backup configuration
cp .env $BACKUP_DIR/
cp docker-compose.yml $BACKUP_DIR/

# Compress
tar -czf "backup_$DATE.tar.gz" -C /backups $DATE
rm -rf $BACKUP_DIR

echo "Backup completed: backup_$DATE.tar.gz"
```

## Scaling Considerations

### Horizontal Scaling

For high-traffic deployments:

1. **Load Balancer**: Distribute traffic across multiple instances
2. **Database Clustering**: Use MongoDB replica sets
3. **CDN Integration**: Offload static content and video streaming
4. **Caching Layer**: Implement Redis for session management
5. **Queue System**: Use Celery for background processing

### Multi-Region Deployment

```yaml
# docker-compose.prod.yml example
version: '3.8'
services:
  streambot-us:
    image: streambot:latest
    environment:
      - REGION=us-east-1
      - VIDEO_CDN_URL=https://us.yourcdn.com
    
  streambot-eu:
    image: streambot:latest
    environment:
      - REGION=eu-west-1
      - VIDEO_CDN_URL=https://eu.yourcdn.com
    
  nginx-lb:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

## Troubleshooting

### Common Deployment Issues

**Port Conflicts**:
```bash
# Check port usage
netstat -tulpn | grep :8080

# Change port in .env
PORT=8081
```

**Permission Issues**:
```bash
# Fix file permissions
chmod +x StreamBot/__main__.py
chown -R $USER:$USER .
```

**MongoDB Connection**:
```bash
# Test MongoDB connection
mongosh "mongodb://localhost:27017/streambot"

# Check MongoDB logs
sudo journalctl -u mongodb
```

**Video Streaming Issues**:
```bash
# Test streaming endpoint
curl -I https://yourdomain.com/stream/test

# Check video frontend URL
curl -I https://cricster.pages.dev

# Verify CORS headers
curl -H "Origin: https://cricster.pages.dev" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS https://yourdomain.com/stream/test
```

## Next Steps

1. **Choose your deployment method** from the options above
2. **Follow the specific guide** for your chosen platform
3. **Configure security measures** including SSL and rate limiting
4. **Set up monitoring** and backup procedures
5. **Test video streaming** functionality thoroughly
6. **Scale** as your user base grows

For detailed platform-specific instructions, see:
- [Docker Deployment](docker.md)
- [Cloud Platform Setup](cloud-platforms.md)
- [VPS Configuration](vps-setup.md)
- [Security Best Practices](security.md) 