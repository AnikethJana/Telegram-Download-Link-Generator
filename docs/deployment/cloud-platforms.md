---
title: Cloud Platform Deployment
description: Deploy StreamBot on major cloud platforms with video streaming support
---

# Cloud Platform Deployment

This guide covers deploying StreamBot on major cloud platforms with comprehensive instructions for each provider, including video streaming optimizations.

## Platform Comparison

| Platform | Ease of Use | Cost | Performance | Video Streaming | Free Tier |
|----------|-------------|------|-------------|-----------------|-----------|
| Railway | ⭐⭐⭐⭐⭐ | $$ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ |
| Heroku | ⭐⭐⭐⭐ | $$$ | ⭐⭐⭐ | ⭐⭐⭐ | ✅ |
| DigitalOcean | ⭐⭐⭐⭐ | $$ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ |
| AWS | ⭐⭐⭐ | $ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ |
| Google Cloud | ⭐⭐⭐ | $$ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ |
| Render | ⭐⭐⭐⭐ | $$ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ |

## Railway (Recommended for Beginners)

Railway offers the simplest deployment process with excellent performance for video streaming.

### Quick Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/streambot)

### Manual Deployment

1. **Create Railway Account**: Sign up at [railway.app](https://railway.app)

2. **Connect GitHub Repository**:
   ```bash
   # Fork the repository first
   git clone https://github.com/AnikethJana/Telegram-Download-Link-Generator.git
   cd Telegram-Download-Link-Generator
   ```

3. **Create New Project** in Railway dashboard

4. **Deploy from GitHub**:
   - Connect your GitHub account
   - Select the forked repository
   - Railway will auto-detect the Python app

5. **Configure Environment Variables**:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   BOT_TOKEN=your_bot_token
   LOG_CHANNEL=-1001234567890
   DATABASE_URL=${{MongoDB.DATABASE_URL}}
   BASE_URL=https://your-app.railway.app
   PORT=8080
   VIDEO_FRONTEND_URL=https://cricster.pages.dev
   ADMINS=your_telegram_user_id
   ```

6. **Add MongoDB Service**:
   - Click "New Service" → "Database" → "MongoDB"
   - Railway will automatically provide `DATABASE_URL`

7. **Custom Domain** (Optional):
   - Go to Settings → Custom Domain
   - Add your domain and configure DNS

### Railway Optimization for Video Streaming

```env
# Railway-specific optimizations
RAILWAY_ENVIRONMENT=production
PYTHONUNBUFFERED=1
WEB_CONCURRENCY=4
MAX_WORKERS=4

# Video streaming optimizations
VIDEO_CHUNK_SIZE=1048576
STREAM_TIMEOUT=3600
MAX_CONCURRENT_STREAMS=50
```

## Heroku

Heroku provides a robust platform with excellent addon ecosystem.

### Prerequisites

- Heroku CLI installed
- Git repository ready

### Deployment Steps

1. **Install Heroku CLI**:
   ```bash
   # Windows (using Chocolatey)
   choco install heroku-cli
   
   # macOS (using Homebrew)
   brew tap heroku/brew && brew install heroku
   
   # Ubuntu/Debian
   curl https://cli-assets.heroku.com/install.sh | sh
   ```

2. **Login and Create App**:
   ```bash
   heroku login
   heroku create your-streambot-app
   ```

3. **Add MongoDB Addon**:
   ```bash
   heroku addons:create mongolab:sandbox
   ```

4. **Configure Environment Variables**:
   ```bash
   heroku config:set API_ID=your_api_id
   heroku config:set API_HASH=your_api_hash
   heroku config:set BOT_TOKEN=your_bot_token
   heroku config:set LOG_CHANNEL=-1001234567890
   heroku config:set BASE_URL=https://your-streambot-app.herokuapp.com
   heroku config:set VIDEO_FRONTEND_URL=https://cricster.pages.dev
   heroku config:set ADMINS=your_telegram_user_id
   heroku config:set PYTHON_VERSION=3.11.0
   ```

5. **Create Procfile**:
   ```procfile
   web: python -m StreamBot
   worker: python -m StreamBot --worker-mode
   ```

6. **Deploy**:
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

7. **Scale Dynos**:
   ```bash
   heroku ps:scale web=1 worker=1
   ```

### Heroku Video Streaming Configuration

```bash
# Configure for video streaming
heroku config:set MAX_REQUEST_SIZE=2147483648
heroku config:set STREAM_CHUNK_SIZE=1048576
heroku config:set ENABLE_RANGE_REQUESTS=true
heroku config:set VIDEO_CACHE_TTL=3600
```

## DigitalOcean App Platform

DigitalOcean App Platform offers excellent performance for video streaming with competitive pricing.

### Deployment via GitHub

1. **Create DigitalOcean Account**: Sign up at [digitalocean.com](https://digitalocean.com)

2. **Create App**:
   - Go to Apps → Create App
   - Connect GitHub repository
   - Select your StreamBot repository

3. **Configure Build Settings**:
   ```yaml
   # .do/app.yaml
   name: streambot
   services:
   - name: web
     source_dir: /
     github:
       repo: your-username/Telegram-Download-Link-Generator
       branch: main
     run_command: python -m StreamBot
     environment_slug: python
     instance_count: 1
     instance_size_slug: basic-xxs
     http_port: 8080
     routes:
     - path: /
   databases:
   - name: mongodb
     engine: MONGODB
     version: "5"
   ```

4. **Environment Variables**:
   ```env
   API_ID=${API_ID}
   API_HASH=${API_HASH}
   BOT_TOKEN=${BOT_TOKEN}
   LOG_CHANNEL=${LOG_CHANNEL}
   DATABASE_URL=${mongodb.DATABASE_URL}
   BASE_URL=https://your-app.ondigitalocean.app
   VIDEO_FRONTEND_URL=https://cricster.pages.dev
   ADMINS=${ADMINS}
   ```

### DigitalOcean CDN for Video Streaming

```bash
# Enable CDN for better video streaming
curl -X POST \
  https://api.digitalocean.com/v2/cdn/endpoints \
  -H "Authorization: Bearer $DO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "your-app.ondigitalocean.app",
    "ttl": 3600,
    "custom_domain": "cdn.yourdomain.com"
  }'
```

## Amazon Web Services (AWS)

AWS provides the most comprehensive cloud infrastructure with global CDN for optimal video streaming.

### AWS Elastic Beanstalk Deployment

1. **Install AWS CLI and EB CLI**:
   ```bash
   pip install awscli awsebcli
   aws configure
   ```

2. **Initialize Elastic Beanstalk**:
   ```bash
   eb init streambot --platform python-3.11 --region us-east-1
   ```

3. **Create Environment**:
   ```bash
   eb create streambot-production
   ```

4. **Configure Environment Variables**:
   ```bash
   eb setenv API_ID=your_api_id \
            API_HASH=your_api_hash \
            BOT_TOKEN=your_bot_token \
            LOG_CHANNEL=-1001234567890 \
            DATABASE_URL=mongodb://your-mongodb-url \
            VIDEO_FRONTEND_URL=https://cricster.pages.dev \
            ADMINS=your_telegram_user_id
   ```

5. **Deploy**:
   ```bash
   eb deploy
   ```

### AWS DocumentDB (MongoDB Compatible)

```bash
# Create DocumentDB cluster
aws docdb create-db-cluster \
    --db-cluster-identifier streambot-cluster \
    --engine docdb \
    --master-username admin \
    --master-user-password your-secure-password \
    --vpc-security-group-ids sg-xxxxxxxx
```

### AWS CloudFront for Video Streaming

```json
{
  "DistributionConfig": {
    "CallerReference": "streambot-cdn",
    "DefaultRootObject": "index.html",
    "Origins": {
      "Quantity": 1,
      "Items": [
        {
          "Id": "streambot-origin",
          "DomainName": "your-app.elasticbeanstalk.com",
          "CustomOriginConfig": {
            "HTTPPort": 80,
            "HTTPSPort": 443,
            "OriginProtocolPolicy": "https-only"
          }
        }
      ]
    },
    "DefaultCacheBehavior": {
      "TargetOriginId": "streambot-origin",
      "ViewerProtocolPolicy": "redirect-to-https",
      "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
      "Compress": true
    }
  }
}
```

## Google Cloud Platform (GCP)

GCP offers excellent global infrastructure with competitive pricing for video streaming.

### Google Cloud Run Deployment

1. **Install Google Cloud SDK**:
   ```bash
   # Linux/macOS
   curl https://sdk.cloud.google.com | bash
   
   # Windows
   # Download and install from cloud.google.com/sdk
   ```

2. **Initialize Project**:
   ```bash
   gcloud auth login
   gcloud config set project your-project-id
   gcloud services enable run.googleapis.com
   ```

3. **Create Dockerfile** (if not exists):
   ```dockerfile
   FROM python:3.11-slim
   
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   COPY . .
   
   CMD ["python", "-m", "StreamBot"]
   ```

4. **Build and Deploy**:
   ```bash
   gcloud builds submit --tag gcr.io/your-project-id/streambot
   gcloud run deploy streambot \
     --image gcr.io/your-project-id/streambot \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --cpu 2 \
     --max-instances 10
   ```

5. **Set Environment Variables**:
   ```bash
   gcloud run services update streambot \
     --set-env-vars="API_ID=your_api_id,API_HASH=your_api_hash,BOT_TOKEN=your_bot_token,LOG_CHANNEL=-1001234567890,VIDEO_FRONTEND_URL=https://cricster.pages.dev"
   ```

### Google Cloud CDN for Video Streaming

```bash
# Create Cloud CDN
gcloud compute backend-services create streambot-backend \
    --global \
    --load-balancing-scheme=EXTERNAL
    
gcloud compute url-maps create streambot-map \
    --default-service streambot-backend
    
gcloud compute target-https-proxies create streambot-proxy \
    --url-map streambot-map \
    --ssl-certificates streambot-ssl
```

## Render

Render provides a modern platform with automatic SSL and easy deployments.

### Render Deployment

1. **Connect GitHub**: Link your GitHub account to Render

2. **Create Web Service**:
   - Select your repository
   - Choose "Web Service"
   - Configure build settings:

3. **Build Configuration**:
   ```yaml
   # render.yaml
   services:
     - type: web
       name: streambot
       env: python
       buildCommand: pip install -r requirements.txt
       startCommand: python -m StreamBot
       envVars:
         - key: API_ID
           value: your_api_id
         - key: API_HASH
           value: your_api_hash
         - key: BOT_TOKEN
           value: your_bot_token
         - key: LOG_CHANNEL
           value: -1001234567890
         - key: VIDEO_FRONTEND_URL
           value: https://cricster.pages.dev
         - key: DATABASE_URL
           fromDatabase:
             name: streambot-db
             property: connectionString
   
   databases:
     - name: streambot-db
       databaseName: streambot
       user: streambot
   ```

4. **Auto-Deploy**: Render automatically deploys on git push

## Video Streaming Optimizations

### CDN Configuration

For optimal video streaming performance across all platforms:

```nginx
# Nginx configuration for video streaming
location /stream/ {
    proxy_pass http://localhost:8080;
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    
    # Enable range requests
    proxy_set_header Range $http_range;
    proxy_set_header If-Range $http_if_range;
    
    # Optimize for video streaming
    proxy_cache_bypass $http_range;
    proxy_no_cache $http_range;
}
```

### Environment Variables for Video Streaming

```env
# Video streaming optimizations (all platforms)
VIDEO_CHUNK_SIZE=1048576
MAX_CONCURRENT_STREAMS=50
STREAM_TIMEOUT=3600
ENABLE_RANGE_REQUESTS=true
VIDEO_CACHE_TTL=3600
CORS_ORIGINS=https://cricster.pages.dev,https://yourdomain.com
```

## Cost Optimization

### Free Tier Recommendations

1. **Development**: Railway or Render free tier
2. **Small Production**: Heroku hobby tier
3. **High Traffic**: DigitalOcean or AWS with reserved instances

### Cost Monitoring

```bash
# Set up billing alerts (AWS example)
aws budgets create-budget \
    --account-id 123456789012 \
    --budget '{
        "BudgetName": "StreamBot Monthly Budget",
        "BudgetLimit": {
            "Amount": "50",
            "Unit": "USD"
        },
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST"
    }'
```

## Monitoring and Scaling

### Health Checks

All platforms should monitor these endpoints:

```bash
# Health check endpoint
curl https://your-app.com/api/info

# Video streaming health
curl -I https://your-app.com/stream/test
```

### Auto-Scaling Configuration

```yaml
# Kubernetes auto-scaling example
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: streambot-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: streambot
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Troubleshooting

### Common Deployment Issues

**Build Failures**:
```bash
# Check Python version
python --version  # Should be 3.11+

# Install dependencies locally first
pip install -r requirements.txt
```

**Environment Variable Issues**:
```bash
# Test environment variables
python -c "import os; print(os.getenv('BOT_TOKEN'))"
```

**Video Streaming Issues**:
```bash
# Test streaming endpoint
curl -I https://your-app.com/stream/test
curl -H "Range: bytes=0-1023" https://your-app.com/stream/test
```

### Performance Optimization

```python
# Add to your deployment configuration
import os

# Optimize for cloud deployment
if os.getenv('CLOUD_PROVIDER') == 'heroku':
    # Heroku-specific optimizations
    MAX_WORKERS = int(os.getenv('WEB_CONCURRENCY', 4))
    WORKER_TIMEOUT = 120
    
elif os.getenv('CLOUD_PROVIDER') == 'aws':
    # AWS-specific optimizations
    MAX_WORKERS = int(os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', 512)) // 128
    
elif os.getenv('CLOUD_PROVIDER') == 'gcp':
    # GCP-specific optimizations
    MAX_WORKERS = int(os.getenv('CLOUD_RUN_CPU', 1)) * 2
```

## Next Steps

After deployment:

1. **Configure Custom Domain**: Set up your own domain for better branding
2. **Enable HTTPS**: Ensure SSL certificates are properly configured
3. **Set Up Monitoring**: Configure uptime monitoring and alerts
4. **Optimize Performance**: Implement CDN and caching strategies
5. **Security Hardening**: Follow security best practices for your platform
6. **Backup Strategy**: Set up automated backups for your database

For platform-specific advanced configurations, refer to:
- [Docker Deployment](docker.md) for containerized deployments
- [VPS Setup](vps-setup.md) for self-hosted solutions
- [Security Configuration](security.md) for hardening your deployment

---

*These comprehensive cloud deployment guides are currently in development. Stay tuned for detailed instructions!* 