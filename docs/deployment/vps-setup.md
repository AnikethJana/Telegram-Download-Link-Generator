---
title: VPS Setup Guide
description: Complete guide to deploy StreamBot on Virtual Private Servers with video streaming optimization
---

# VPS Setup Guide

This comprehensive guide covers deploying StreamBot on Virtual Private Servers (VPS) from various providers, with optimizations for video streaming performance.

## VPS Provider Comparison

| Provider | CPU Performance | Network Speed | Storage Type | Price Range | Video Streaming |
|----------|----------------|---------------|--------------|-------------|-----------------|
| DigitalOcean | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | SSD | $5-40/month | ⭐⭐⭐⭐⭐ |
| Vultr | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | SSD/NVMe | $3-40/month | ⭐⭐⭐⭐⭐ |
| Linode | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | SSD | $5-40/month | ⭐⭐⭐⭐ |
| AWS EC2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | EBS/NVMe | $5-100+/month | ⭐⭐⭐⭐⭐ |
| Google Cloud | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | SSD | $5-100+/month | ⭐⭐⭐⭐⭐ |
| Hetzner | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | SSD/NVMe | $3-50/month | ⭐⭐⭐⭐ |

## System Requirements

### Minimum Requirements
- **CPU**: 1 vCPU (2.4GHz+)
- **RAM**: 1 GB
- **Storage**: 20 GB SSD
- **Bandwidth**: 1 TB/month
- **OS**: Ubuntu 22.04 LTS or CentOS 8+

### Recommended for Video Streaming
- **CPU**: 2+ vCPU (3.0GHz+)
- **RAM**: 4 GB+
- **Storage**: 50 GB+ SSD/NVMe
- **Bandwidth**: 5 TB/month
- **Network**: 1 Gbps port speed

## DigitalOcean Deployment

### 1. Create Droplet

```bash
# Using DigitalOcean CLI (doctl)
doctl compute droplet create streambot \
  --image ubuntu-22-04-x64 \
  --size s-2vcpu-4gb \
  --region nyc1 \
  --ssh-keys your-ssh-key-id \
  --enable-monitoring \
  --enable-backups
```

### 2. Initial Server Setup

```bash
# Connect to your droplet
ssh root@your-droplet-ip

# Update system packages
apt update && apt upgrade -y

# Create a new user for StreamBot
adduser streambot
usermod -aG sudo streambot
usermod -aG docker streambot

# Switch to new user
su - streambot
```

### 3. Install Dependencies

```bash
# Install Python 3.11
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv python3.11-dev -y

# Install system dependencies
sudo apt install git curl wget nginx certbot python3-certbot-nginx -y

# Install MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install mongodb-org -y
sudo systemctl enable mongod
sudo systemctl start mongod
```

### 4. Install Docker (Optional but Recommended)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login to apply docker group changes
exit
ssh streambot@your-droplet-ip
```

### 5. Deploy StreamBot

```bash
# Clone repository
git clone https://github.com/AnikethJana/Telegram-Download-Link-Generator.git
cd Telegram-Download-Link-Generator

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create environment file
cp .env.example .env
nano .env
```

### 6. Configure Environment Variables

```env
# Telegram Configuration
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
LOG_CHANNEL=-1001234567890

# Database Configuration
DATABASE_URL=mongodb://localhost:27017/streambot

# Server Configuration
BASE_URL=https://yourdomain.com
PORT=8080
BIND_ADDRESS=0.0.0.0

# Video Streaming Configuration
VIDEO_FRONTEND_URL=https://cricster.pages.dev
VIDEO_CHUNK_SIZE=1048576
MAX_CONCURRENT_STREAMS=50
STREAM_TIMEOUT=3600

# Admin Configuration
ADMINS=your_telegram_user_id

# Performance Optimizations
WORKERS=4
MAX_CONNECTIONS=1000
KEEPALIVE_TIMEOUT=65
```

### 7. Create Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/streambot.service
```

```ini
[Unit]
Description=StreamBot Telegram File to Link Generator
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=streambot
Group=streambot
WorkingDirectory=/home/streambot/Telegram-Download-Link-Generator
Environment=PATH=/home/streambot/Telegram-Download-Link-Generator/venv/bin
ExecStart=/home/streambot/Telegram-Download-Link-Generator/venv/bin/python -m StreamBot
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=streambot

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/streambot/Telegram-Download-Link-Generator

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable streambot
sudo systemctl start streambot
sudo systemctl status streambot
```

## Nginx Configuration for Video Streaming

### 1. Configure Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/streambot
```

```nginx
# Nginx configuration optimized for video streaming
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # General proxy settings
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Main application
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Optimized configuration for video streaming
    location /stream/ {
        proxy_pass http://127.0.0.1:8080;
        
        # Disable buffering for streaming
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        
        # Enable range requests for video seeking
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        
        # Bypass cache for range requests
        proxy_cache_bypass $http_range;
        proxy_no_cache $http_range;
        
        # Increase timeouts for large video files
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Handle large files
        client_max_body_size 2G;
        proxy_max_temp_file_size 0;
        
        # CORS headers for video frontend
        add_header Access-Control-Allow-Origin "https://cricster.pages.dev" always;
        add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Range, If-Range, Accept-Encoding" always;
        add_header Access-Control-Expose-Headers "Content-Range, Accept-Ranges, Content-Length" always;
        
        # Handle preflight requests
        if ($request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin "https://cricster.pages.dev";
            add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS";
            add_header Access-Control-Allow-Headers "Range, If-Range, Accept-Encoding";
            add_header Access-Control-Max-Age 86400;
            add_header Content-Type "text/plain charset=UTF-8";
            add_header Content-Length 0;
            return 204;
        }
    }
    
    # Download endpoint optimization
    location /dl/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering on;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
        
        # Enable range requests
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        
        # Timeouts for large downloads
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Handle large files
        client_max_body_size 2G;
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
# Enable site and restart Nginx
sudo ln -s /etc/nginx/sites-available/streambot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 2. SSL Certificate Setup

```bash
# Install SSL certificate using Certbot
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Set up automatic renewal
sudo crontab -e
# Add this line:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change 22 to your custom SSH port if different)
sudo ufw allow 22

# Allow HTTP and HTTPS
sudo ufw allow 80
sudo ufw allow 443

# Allow MongoDB (only if external access needed)
# sudo ufw allow from your-trusted-ip to any port 27017

# Enable firewall
sudo ufw enable
sudo ufw status
```

## Performance Optimization

### 1. System Optimizations

```bash
# Optimize system settings for video streaming
sudo nano /etc/sysctl.conf
```

```ini
# Network optimizations
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 12582912 16777216
net.ipv4.tcp_wmem = 4096 12582912 16777216
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_congestion_control = bbr

# File system optimizations
fs.file-max = 65536
fs.inotify.max_user_watches = 524288

# Virtual memory optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
```

```bash
# Apply settings
sudo sysctl -p
```

### 2. MongoDB Optimization

```bash
# Configure MongoDB for better performance
sudo nano /etc/mongod.conf
```

```yaml
# MongoDB configuration for StreamBot
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true
  wiredTiger:
    engineConfig:
      cacheSizeGB: 1  # Adjust based on available RAM
    collectionConfig:
      blockCompressor: snappy
    indexConfig:
      prefixCompression: true

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log
  logRotate: rename
  verbosity: 1

net:
  port: 27017
  bindIp: 127.0.0.1

processManagement:
  timeZoneInfo: /usr/share/zoneinfo

security:
  authorization: enabled

operationProfiling:
  slowOpThresholdMs: 100
  mode: slowOp
```

```bash
# Restart MongoDB
sudo systemctl restart mongod
```

### 3. Nginx Optimization

```bash
# Optimize Nginx for high performance
sudo nano /etc/nginx/nginx.conf
```

```nginx
# Nginx optimization for video streaming
user www-data;
worker_processes auto;
worker_rlimit_nofile 65535;
pid /run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Basic Settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 1000;
    types_hash_max_size 2048;
    server_tokens off;
    
    # File size limits for video streaming
    client_max_body_size 2G;
    client_body_buffer_size 128k;
    client_header_buffer_size 3m;
    large_client_header_buffers 4 256k;
    
    # Timeout settings
    client_body_timeout 60s;
    client_header_timeout 60s;
    send_timeout 60s;
    
    # Proxy settings
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;
    
    # Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=download:10m rate=5r/s;
    
    # Include site configurations
    include /etc/nginx/mime.types;
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
```

## Monitoring and Logging

### 1. System Monitoring

```bash
# Install monitoring tools
sudo apt install htop iotop nethogs -y

# Install and configure fail2ban
sudo apt install fail2ban -y
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
```

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 2. Log Management

```bash
# Configure log rotation for StreamBot
sudo nano /etc/logrotate.d/streambot
```

```
/home/streambot/Telegram-Download-Link-Generator/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    su streambot streambot
}
```

### 3. Backup Strategy

```bash
# Create backup script
nano /home/streambot/backup.sh
```

```bash
#!/bin/bash
# StreamBot backup script

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/streambot/backups"
APP_DIR="/home/streambot/Telegram-Download-Link-Generator"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup MongoDB
mongodump --db streambot --out $BACKUP_DIR/mongodb_$DATE

# Backup application files
tar -czf $BACKUP_DIR/app_$DATE.tar.gz -C $APP_DIR .env sessions/

# Backup Nginx configuration
sudo cp /etc/nginx/sites-available/streambot $BACKUP_DIR/nginx_$DATE.conf

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "mongodb_*" -mtime +7 -exec rm -rf {} \;

echo "Backup completed: $DATE"
```

```bash
# Make executable and add to crontab
chmod +x /home/streambot/backup.sh
crontab -e
# Add: 0 2 * * * /home/streambot/backup.sh
```

## Security Hardening

### 1. SSH Security

```bash
# Configure SSH security
sudo nano /etc/ssh/sshd_config
```

```ini
# SSH security configuration
Port 2222  # Change default port
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
ChallengeResponseAuthentication no
UsePAM no
X11Forwarding no
PrintMotd no
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
MaxSessions 2
Protocol 2
```

```bash
sudo systemctl restart ssh
```

### 2. Intrusion Detection

```bash
# Install and configure AIDE
sudo apt install aide -y
sudo aideinit
sudo mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db

# Add to crontab for daily checks
echo "0 1 * * * /usr/bin/aide --check" | sudo crontab -
```

## Troubleshooting

### Common Issues

**Service Won't Start**:
```bash
# Check service status
sudo systemctl status streambot
sudo journalctl -u streambot -f

# Check logs
tail -f /home/streambot/Telegram-Download-Link-Generator/logs/streambot.log
```

**High Memory Usage**:
```bash
# Monitor memory usage
htop
free -h

# Restart service if needed
sudo systemctl restart streambot
```

**Video Streaming Issues**:
```bash
# Test streaming endpoint
curl -I http://localhost:8080/stream/test
curl -H "Range: bytes=0-1023" http://localhost:8080/stream/test

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

**Database Connection Issues**:
```bash
# Check MongoDB status
sudo systemctl status mongod
mongosh --eval "db.adminCommand('ping')"

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log
```

### Performance Monitoring

```bash
# Monitor system resources
htop
iotop
nethogs

# Monitor disk usage
df -h
du -sh /home/streambot/*

# Monitor network connections
ss -tuln
netstat -tlnp | grep :8080
```

## Scaling Considerations

### Vertical Scaling (Upgrade VPS)

```bash
# Before upgrading, backup everything
./backup.sh

# After upgrade, optimize for new resources
# Update MongoDB cache size
sudo nano /etc/mongod.conf
# Increase cacheSizeGB based on new RAM

# Update Nginx worker processes
sudo nano /etc/nginx/nginx.conf
# Set worker_processes to match new CPU cores

# Update StreamBot workers
nano .env
# Increase WORKERS based on new CPU cores
```

### Horizontal Scaling (Multiple Servers)

For high-traffic deployments, consider:

1. **Load Balancer**: Use Nginx or HAProxy
2. **Database Clustering**: MongoDB replica sets
3. **CDN**: CloudFlare or AWS CloudFront
4. **Monitoring**: Prometheus + Grafana

## Next Steps

After successful deployment:

1. **Monitor Performance**: Set up monitoring dashboards
2. **Regular Backups**: Ensure backup script is working
3. **Security Updates**: Keep system and dependencies updated
4. **SSL Renewal**: Verify automatic SSL certificate renewal
5. **Scaling**: Monitor usage and scale as needed

For additional deployment options, see:
- [Docker Deployment](docker.md) for containerized setup
- [Cloud Platforms](cloud-platforms.md) for managed services
- [Security Configuration](security.md) for advanced security

---

*This documentation is actively being developed. Check back soon for detailed VPS setup instructions!* 