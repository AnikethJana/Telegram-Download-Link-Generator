---
title: Docker Deployment
description: Deploy StreamBot using Docker and Docker Compose
---

# Docker Deployment

Docker provides an easy way to deploy StreamBot with all dependencies included. This guide covers both Docker and Docker Compose deployment methods.

## Prerequisites

- **Docker** 20.10+ installed
- **Docker Compose** v2.0+ (if using compose method)
- **Git** for cloning the repository

## Method 1: Docker Compose (Recommended)

Docker Compose is the easiest way to deploy StreamBot with MongoDB included.

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/StreamBot.git
cd StreamBot
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Telegram Configuration
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
LOG_CHANNEL=-1001234567890

# Database (MongoDB container)
DATABASE_URL=mongodb://mongodb:27017
DATABASE_NAME=StreamBotDB

# Server Configuration
BASE_URL=https://yourdomain.com
PORT=8080
BIND_ADDRESS=0.0.0.0

# Admin Configuration
ADMINS=your_telegram_user_id
```

### 3. Create Docker Compose File

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  streambot:
    build: .
    container_name: streambot
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=mongodb://mongodb:27017
    env_file:
      - .env
    depends_on:
      - mongodb
    volumes:
      - ./sessions:/app/sessions
    networks:
      - streambot-network

  mongodb:
    image: mongo:6.0
    container_name: streambot-mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      - MONGO_INITDB_DATABASE=StreamBotDB
    networks:
      - streambot-network

volumes:
  mongodb_data:

networks:
  streambot-network:
    driver: bridge
```

### 4. Deploy

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f streambot

# Stop services
docker-compose down
```

## Method 2: Docker Only

If you have an existing MongoDB instance, you can run just the StreamBot container.

### 1. Build Image

```bash
# Clone repository
git clone https://github.com/yourusername/StreamBot.git
cd StreamBot

# Build Docker image
docker build -t streambot:latest .
```

### 2. Run Container

```bash
docker run -d \
  --name streambot \
  --restart unless-stopped \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/sessions:/app/sessions \
  streambot:latest
```

## Advanced Configuration

### Production Docker Compose

For production deployment with additional services:

```yaml
version: '3.8'

services:
  streambot:
    build: .
    container_name: streambot
    restart: unless-stopped
    environment:
      - DATABASE_URL=mongodb://mongodb:27017
    env_file:
      - .env
    depends_on:
      - mongodb
    volumes:
      - ./sessions:/app/sessions
      - ./logs:/app/logs
    networks:
      - streambot-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.streambot.rule=Host(`files.yourdomain.com`)"
      - "traefik.http.routers.streambot.tls.certresolver=letsencrypt"

  mongodb:
    image: mongo:6.0
    container_name: streambot-mongodb
    restart: unless-stopped
    volumes:
      - mongodb_data:/data/db
      - ./backups:/backups
    environment:
      - MONGO_INITDB_DATABASE=StreamBotDB
    networks:
      - streambot-network

  nginx:
    image: nginx:alpine
    container_name: streambot-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - streambot
    networks:
      - streambot-network

volumes:
  mongodb_data:

networks:
  streambot-network:
    driver: bridge
```

### Environment Variables for Docker

```env
# Docker-specific settings
BIND_ADDRESS=0.0.0.0
DATABASE_URL=mongodb://mongodb:27017

# Production settings
WORKERS=4
SESSION_NAME=StreamBotProd
```

## Monitoring and Maintenance

### View Logs

```bash
# StreamBot logs
docker-compose logs -f streambot

# MongoDB logs
docker-compose logs -f mongodb

# All services
docker-compose logs -f
```

### Health Checks

Add health checks to your `docker-compose.yml`:

```yaml
services:
  streambot:
    # ... other configuration
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/info"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Backup MongoDB

```bash
# Create backup
docker exec streambot-mongodb mongodump --db StreamBotDB --out /backups/$(date +%Y%m%d_%H%M%S)

# Restore backup
docker exec streambot-mongodb mongorestore --db StreamBotDB /backups/backup_folder
```

### Update Deployment

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Reverse Proxy Configuration

### Nginx Configuration

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream streambot {
        server streambot:8080;
    }

    server {
        listen 80;
        server_name files.yourdomain.com;
        
        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name files.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        client_max_body_size 2G;

        location / {
            proxy_pass http://streambot;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### Traefik Configuration

```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.9
    container_name: traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik.yml:/etc/traefik/traefik.yml
      - ./acme.json:/acme.json
    networks:
      - streambot-network

  streambot:
    # ... existing configuration
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.streambot.rule=Host(`files.yourdomain.com`)"
      - "traefik.http.routers.streambot.tls.certresolver=letsencrypt"
```

## Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs for errors
docker-compose logs streambot

# Verify environment variables
docker-compose exec streambot env | grep -E "(API_ID|BOT_TOKEN|DATABASE_URL)"
```

**Database connection fails:**
```bash
# Check MongoDB status
docker-compose exec mongodb mongo --eval "db.adminCommand('ismaster')"

# Verify network connectivity
docker-compose exec streambot ping mongodb
```

**Permission issues:**
```bash
# Fix session directory permissions
sudo chown -R 1000:1000 sessions/

# Fix log directory permissions
sudo chown -R 1000:1000 logs/
```

### Performance Tuning

```yaml
services:
  streambot:
    # ... other configuration
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Security Considerations

### Best Practices

1. **Use secrets for sensitive data:**
```yaml
secrets:
  bot_token:
    file: ./secrets/bot_token.txt
    
services:
  streambot:
    secrets:
      - bot_token
```

2. **Limit container capabilities:**
```yaml
services:
  streambot:
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETUID
      - SETGID
```

3. **Use non-root user:**
```dockerfile
FROM python:3.9-slim
RUN useradd -m -s /bin/bash streambot
USER streambot
# ... rest of Dockerfile
```

This Docker deployment method provides a robust, scalable way to run StreamBot in production environments. 