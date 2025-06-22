---
title: Security Configuration
description: Security best practices for StreamBot deployment
---

# Security Configuration

This comprehensive guide provides security guidelines and best practices for production StreamBot deployments, including video streaming security considerations.

## Complete Security Implementation Guide

### Server Security

#### Operating System Hardening

**Ubuntu/Debian Hardening**:
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install security updates automatically
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades

# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable cups
sudo systemctl disable avahi-daemon

# Configure automatic security updates
echo 'Unattended-Upgrade::Automatic-Reboot "false";' | sudo tee -a /etc/apt/apt.conf.d/20auto-upgrades
echo 'Unattended-Upgrade::Remove-Unused-Dependencies "true";' | sudo tee -a /etc/apt/apt.conf.d/20auto-upgrades
```

**System Hardening Configuration**:
```bash
# Configure kernel parameters for security
sudo nano /etc/sysctl.conf
```

```ini
# Network security
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.tcp_syncookies = 1

# Apply settings
sudo sysctl -p
```

#### Firewall Setup (UFW)

```bash
# Reset UFW to defaults
sudo ufw --force reset

# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change port if customized)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow MongoDB only from localhost
sudo ufw allow from 127.0.0.1 to any port 27017

# Enable UFW
sudo ufw enable

# Check status
sudo ufw status verbose
```

**Advanced Firewall Rules**:
```bash
# Rate limiting for SSH
sudo ufw limit ssh

# Allow specific IP ranges for admin access
sudo ufw allow from 192.168.1.0/24 to any port 22

# Block common attack ports
sudo ufw deny 23
sudo ufw deny 135
sudo ufw deny 445
sudo ufw deny 1433
sudo ufw deny 3389
```

#### SSH Security Hardening

```bash
# Backup original SSH config
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Configure SSH security
sudo nano /etc/ssh/sshd_config
```

```ini
# SSH Security Configuration
Port 2222  # Change from default port 22
Protocol 2

# Authentication
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
ChallengeResponseAuthentication no
UsePAM no

# Connection settings
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
MaxSessions 2
MaxStartups 2

# Disable dangerous features
X11Forwarding no
AllowTcpForwarding no
GatewayPorts no
PermitTunnel no

# Allow only specific users
AllowUsers streambot

# Logging
LogLevel VERBOSE
SyslogFacility AUTH
```

```bash
# Restart SSH service
sudo systemctl restart ssh
```

### Application Security

#### Environment Variables Security

**Secure .env File Management**:
```bash
# Set proper permissions for .env file
chmod 600 .env
chown streambot:streambot .env

# Create encrypted backup
gpg --cipher-algo AES256 --compress-algo 1 --s2k-mode 3 \
    --s2k-digest-algo SHA512 --s2k-count 65536 \
    --symmetric --output .env.gpg .env

# Securely delete original if needed
shred -vfz -n 3 .env.backup
```

**Environment Variable Validation**:
```python
# Add to StreamBot/config.py
import os
import sys
from typing import Optional

def validate_security_config():
    """Validate critical security configuration."""
    required_vars = [
        'API_ID', 'API_HASH', 'BOT_TOKEN', 
        'DATABASE_URL', 'ADMINS'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"SECURITY ERROR: Missing required environment variables: {missing_vars}")
        sys.exit(1)
    
    # Validate admin IDs format
    admin_ids = os.getenv('ADMINS', '').split(',')
    for admin_id in admin_ids:
        if admin_id.strip() and not admin_id.strip().isdigit():
            print(f"SECURITY ERROR: Invalid admin ID format: {admin_id}")
            sys.exit(1)
    
    # Validate JWT secret strength
    jwt_secret = os.getenv('JWT_SECRET', '')
    if len(jwt_secret) < 32:
        print("SECURITY WARNING: JWT_SECRET should be at least 32 characters")
```

#### API Security Implementation

**Rate Limiting Configuration**:
```python
# StreamBot/security/rate_limiter.py
import time
from collections import defaultdict
from typing import Dict, Tuple

class AdvancedRateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Dict[str, float] = {}
    
    def is_allowed(self, identifier: str, limit: int = 60, window: int = 3600) -> Tuple[bool, int]:
        """Check if request is allowed under rate limit."""
        current_time = time.time()
        
        # Check if IP is temporarily blocked
        if identifier in self.blocked_ips:
            if current_time < self.blocked_ips[identifier]:
                return False, 0
            else:
                del self.blocked_ips[identifier]
        
        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < window
        ]
        
        # Check rate limit
        if len(self.requests[identifier]) >= limit:
            # Block IP for escalating time based on violations
            block_duration = min(3600, len(self.requests[identifier]) * 60)
            self.blocked_ips[identifier] = current_time + block_duration
            return False, 0
        
        # Allow request
        self.requests[identifier].append(current_time)
        remaining = limit - len(self.requests[identifier])
        return True, remaining
```

#### File Upload Security

**Malware Scanning Integration**:
```python
# StreamBot/security/file_scanner.py
import hashlib
import magic
import requests
from typing import Optional, Dict, Any

class FileSecurityScanner:
    def __init__(self):
        self.max_file_size = 2 * 1024 * 1024 * 1024  # 2GB
        self.allowed_mime_types = {
            'image/*', 'video/*', 'audio/*', 'text/*',
            'application/pdf', 'application/zip',
            'application/x-rar-compressed'
        }
        self.dangerous_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr',
            '.vbs', '.js', '.jar', '.ps1', '.sh'
        }
    
    def scan_file(self, file_path: str, file_size: int) -> Dict[str, Any]:
        """Comprehensive file security scan."""
        results = {
            'safe': True,
            'issues': [],
            'file_type': None,
            'hash': None
        }
        
        # Size check
        if file_size > self.max_file_size:
            results['safe'] = False
            results['issues'].append('File size exceeds maximum limit')
            return results
        
        # MIME type detection
        try:
            mime_type = magic.from_file(file_path, mime=True)
            results['file_type'] = mime_type
            
            # Check allowed MIME types
            if not any(mime_type.startswith(allowed.rstrip('*')) 
                      for allowed in self.allowed_mime_types):
                results['safe'] = False
                results['issues'].append(f'Dangerous file type: {mime_type}')
        
        except Exception as e:
            results['issues'].append(f'MIME type detection failed: {str(e)}')
        
        # File hash calculation
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                results['hash'] = file_hash
        except Exception as e:
            results['issues'].append(f'Hash calculation failed: {str(e)}')
        
        return results
```

### Network Security

#### HTTPS/TLS Configuration

**Nginx SSL Configuration**:
```nginx
# /etc/nginx/sites-available/streambot-ssl
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # SSL session settings
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;
    
    # OCSP stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/yourdomain.com/chain.pem;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https://cricster.pages.dev; media-src 'self'" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=download:10m rate=5r/s;
    limit_req_zone $binary_remote_addr zone=stream:10m rate=20r/s;
    
    # Main application
    location / {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8080;
        include /etc/nginx/proxy_params;
    }
    
    # Download endpoint
    location /dl/ {
        limit_req zone=download burst=10 nodelay;
        proxy_pass http://127.0.0.1:8080;
        include /etc/nginx/proxy_params;
    }
    
    # Streaming endpoint with special handling
    location /stream/ {
        limit_req zone=stream burst=50 nodelay;
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering off;
        proxy_request_buffering off;
        include /etc/nginx/proxy_params;
    }
}
```

#### DDoS Protection

**Fail2Ban Configuration for StreamBot**:
```bash
# Create custom filter
sudo nano /etc/fail2ban/filter.d/streambot.conf
```

```ini
[Definition]
failregex = ^.*"GET /(?:dl|stream)/.*" 429.*$
            ^.*"POST /api/.*" 429.*$
            ^.*StreamBot.*Rate limit exceeded.*<HOST>.*$
ignoreregex =
```

```bash
# Configure jail
sudo nano /etc/fail2ban/jail.d/streambot.conf
```

```ini
[streambot-rate-limit]
enabled = true
port = http,https
filter = streambot
logpath = /var/log/nginx/access.log
maxretry = 10
findtime = 300
bantime = 3600
action = iptables-multiport[name=streambot, port="http,https", protocol=tcp]

[streambot-api-abuse]
enabled = true
port = http,https
filter = streambot
logpath = /home/streambot/Telegram-Download-Link-Generator/logs/streambot.log
maxretry = 5
findtime = 600
bantime = 7200
```

### Database Security

#### MongoDB Security Hardening

```bash
# Create MongoDB admin user
mongosh --eval "
use admin
db.createUser({
  user: 'admin',
  pwd: 'your-secure-admin-password',
  roles: [{role: 'userAdminAnyDatabase', db: 'admin'}]
})
"

# Create StreamBot database user
mongosh --eval "
use streambot
db.createUser({
  user: 'streambot_user',
  pwd: 'your-secure-database-password',
  roles: [{role: 'readWrite', db: 'streambot'}]
})
"
```

**MongoDB Configuration**:
```yaml
# /etc/mongod.conf
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true
  wiredTiger:
    engineConfig:
      cacheSizeGB: 1
    collectionConfig:
      blockCompressor: snappy
    indexConfig:
      prefixCompression: true

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log
  logRotate: rename

net:
  port: 27017
  bindIp: 127.0.0.1

security:
  authorization: enabled

processManagement:
  timeZoneInfo: /usr/share/zoneinfo

operationProfiling:
  slowOpThresholdMs: 100
  mode: slowOp

setParameter:
  authenticationMechanisms: SCRAM-SHA-1,SCRAM-SHA-256
```

#### Database Encryption

```bash
# Enable encryption at rest (MongoDB Enterprise)
# Add to mongod.conf:
security:
  enableEncryption: true
  encryptionKeyFile: /etc/mongodb-keyfile

# Create keyfile
openssl rand -base64 32 > /etc/mongodb-keyfile
chmod 400 /etc/mongodb-keyfile
chown mongodb:mongodb /etc/mongodb-keyfile
```

## Quick Security Checklist

While comprehensive guides are being prepared, here's a basic security checklist:

### ✅ Essential Security Steps

```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# 3. Secure SSH (if using SSH)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
# Set: PermitRootLogin no
sudo systemctl restart ssh

# 4. Install fail2ban
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
```

### 🔐 Environment Security

```env
# Use strong, unique passwords and tokens
JWT_SECRET=use_a_very_long_random_string_here_64_chars_minimum
BOT_TOKEN=your_secure_bot_token_from_botfather

# Restrict admin access
ADMIN_IDS=your_user_id_only

# Use secure database connections
DATABASE_URL=mongodb://username:password@localhost:27017/streambot?authSource=admin

# Enable HTTPS
BASE_URL=https://yourdomain.com
```

### 🛡️ File Security

```bash
# Set proper file permissions
chmod 600 .env
chmod 755 /path/to/upload/directory
chown -R streambot:streambot /app

# Create dedicated user
sudo useradd -m -s /bin/bash streambot
sudo usermod -aG docker streambot  # if using Docker
```

## Security Features in Development

### Planned Security Enhancements
- **File Encryption** - End-to-end encryption for uploaded files
- **Two-Factor Authentication** - 2FA for admin access
- **Audit Logging** - Comprehensive security event logging
- **Malware Scanning** - Automatic file scanning
- **Rate Limiting** - Advanced rate limiting per user/IP
- **Access Tokens** - Granular permission system

### Monitoring & Alerting
- **Security Dashboards** - Real-time security monitoring
- **Threat Detection** - Automated threat identification
- **Incident Response** - Security incident procedures
- **Compliance Tools** - GDPR and privacy compliance

## Common Security Vulnerabilities

### What We're Protecting Against
- **File Upload Attacks** - Malicious file uploads
- **Path Traversal** - Directory traversal attacks
- **Rate Limit Bypass** - API abuse prevention
- **Credential Theft** - Token and password security
- **DDoS Attacks** - Service availability protection
- **Data Breaches** - User data protection

## Security Resources

While detailed guides are in development:

### Immediate Security Help
- 💬 Contact me on Telegram: [@ajmods_bot](https://t.me/ajmods_bot)
- 🐛 Report security issues on [GitHub](https://github.com/anikethjana/Telegram-Download-Link-Generator/security)
- 📖 Check current [deployment guides](overview.md)

### External Security Resources
- [OWASP Security Guidelines](https://owasp.org/)
- [CIS Security Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [Let's Encrypt SSL Certificates](https://letsencrypt.org/)
- [Fail2Ban Documentation](https://fail2ban.readthedocs.io/)

## Security Update Schedule

- **Critical Security Updates**: Immediate release
- **Security Patches**: Within 48 hours
- **Security Documentation**: Weekly updates
- **Security Audits**: Monthly reviews

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** create a public GitHub issue
2. Contact me privately on Telegram: [@ajmods_bot](https://t.me/ajmods_bot)
3. Use GitHub's [Security Advisory](https://github.com/anikethjana/Telegram-Download-Link-Generator/security/advisories/new) feature
4. Provide detailed information about the vulnerability
5. Allow time for patch development before public disclosure

---

*Comprehensive security documentation is actively being developed. Your security is our priority!* 