# AI Clips Backend - Production Deployment Guide

This guide covers deploying the AI Clips Backend to production using Docker and Docker Compose.

## Prerequisites

- Docker and Docker Compose installed on your server
- Domain name pointed to your server (for SSL)
- Required API keys and credentials

## Quick Start

1. **Clone the repository** to your production server:
   ```bash
   git clone <your-repo-url>
   cd Backend-main
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.production.example .env.production
   # Edit .env.production with your actual values
   nano .env.production
   ```

3. **Create required directories**:
   ```bash
   mkdir -p volumes/{temp,output,thumbnails,music,game_videos,logs}
   mkdir -p nginx/ssl  # If using SSL
   ```

4. **Start the services**:
   ```bash
   docker-compose up -d
   ```

## Environment Configuration

### Required Environment Variables

Copy `.env.production.example` to `.env.production` and configure:

```bash
# Core Configuration
ENVIRONMENT=production
PORT=8000
WORKERS=4
HOST=0.0.0.0

# OpenAI API (Required)
OPENAI_API_KEY=your_actual_openai_api_key

# Supabase Configuration (Required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key

# Stripe Configuration (Required for payments)
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret

# CORS Configuration
CORS_ORIGINS=["https://your-frontend-domain.com"]

# Frontend URL
FRONTEND_URL=https://your-frontend-domain.com

# Performance Settings
MAX_FILE_SIZE_MB=1000
MAX_CONCURRENT_JOBS=10
CLEANUP_TEMP_FILES=true
UPLOAD_IMMEDIATELY=true

# Storage Settings
SUPABASE_BUCKET_NAME=user-clips
STORAGE_CLEANUP_ENABLED=true
```

## File Structure

After setup, your directory should look like:

```
Backend-main/
├── docker-compose.yml
├── Dockerfile
├── run_production.py
├── .env.production
├── nginx/
│   ├── nginx.conf
│   └── ssl/           # SSL certificates (if using HTTPS)
│       ├── cert.pem
│       └── key.pem
├── volumes/           # Persistent storage
│   ├── temp/          # Temporary video files
│   ├── output/        # Generated clips
│   ├── thumbnails/    # Video thumbnails
│   ├── music/         # Background music
│   ├── game_videos/   # Game footage
│   └── logs/          # Application logs
└── ... (source code)
```

## Docker Services

The deployment includes three services:

### 1. Backend (AI Clips API)
- Runs the FastAPI application
- Processes videos and generates clips
- Handles all API endpoints
- Uses multiple workers for production

### 2. Redis (Job Management)
- Manages background jobs and caching
- Provides job persistence
- Configured with memory limits

### 3. Nginx (Optional Reverse Proxy)
- Handles SSL termination
- Provides rate limiting
- Serves static files
- Proxies requests to backend

## SSL/HTTPS Setup

### Option 1: Let's Encrypt with Certbot

1. **Install Certbot**:
   ```bash
   sudo apt-get update
   sudo apt-get install certbot python3-certbot-nginx
   ```

2. **Generate SSL certificates**:
   ```bash
   sudo certbot certonly --standalone -d your-domain.com
   ```

3. **Copy certificates to nginx directory**:
   ```bash
   sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
   sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
   sudo chown $USER:$USER nginx/ssl/*
   ```

4. **Update nginx.conf** and uncomment the HTTPS server block

5. **Restart services**:
   ```bash
   docker-compose restart nginx
   ```

### Option 2: Custom SSL Certificates

Place your SSL certificates in `nginx/ssl/`:
- `cert.pem` - Your SSL certificate
- `key.pem` - Your private key

## Production Commands

### Start Services
```bash
docker-compose up -d
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f redis
docker-compose logs -f nginx
```

### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build backend
docker-compose up -d backend
```

### Stop Services
```bash
docker-compose down
```

### Backup Data
```bash
# Backup volumes
tar -czf backup-$(date +%Y%m%d).tar.gz volumes/

# Backup Redis data
docker exec aiclips-redis redis-cli BGSAVE
```

## Monitoring and Health Checks

### Health Check Endpoints
- Backend health: `http://your-domain.com/health`
- API docs: `http://your-domain.com/docs` (disabled in production by default)

### Log Files
- Application logs: `volumes/logs/`
- Nginx logs: `volumes/logs/nginx/`
- Redis logs: `docker-compose logs redis`

### Performance Monitoring
```bash
# Check container stats
docker stats

# Check disk usage
df -h volumes/

# Monitor Redis
docker exec aiclips-redis redis-cli INFO memory
```

## Troubleshooting

### Common Issues

1. **Video processing fails**:
   - Check FFmpeg installation in container
   - Verify file permissions in volumes
   - Check available disk space

2. **Redis connection issues**:
   - Ensure Redis container is running
   - Check network connectivity between containers

3. **High memory usage**:
   - Adjust WORKERS count based on server specs
   - Monitor video file sizes and processing concurrency

4. **SSL certificate issues**:
   - Verify certificate files exist and are readable
   - Check domain name matches certificate
   - Ensure certificates are not expired

### Log Locations
- Container logs: `docker-compose logs <service>`
- Application logs: `volumes/logs/`
- Nginx logs: `volumes/logs/nginx/`

### Performance Tuning

Based on your server specifications:

**Small server (2 CPU, 4GB RAM)**:
```
WORKERS=2
MAX_CONCURRENT_JOBS=3
```

**Medium server (4 CPU, 8GB RAM)**:
```
WORKERS=4
MAX_CONCURRENT_JOBS=5
```

**Large server (8+ CPU, 16GB+ RAM)**:
```
WORKERS=8
MAX_CONCURRENT_JOBS=10
```

## Security Considerations

1. **Firewall**: Only expose ports 80 and 443
2. **API Keys**: Never commit API keys to version control
3. **File Permissions**: Ensure proper permissions on volume directories
4. **Rate Limiting**: Nginx is configured with rate limiting
5. **CORS**: Configure CORS_ORIGINS for your frontend domain only

## Backup Strategy

1. **Regular backups of volumes/**:
   ```bash
   # Daily backup script
   tar -czf "backup-$(date +%Y%m%d).tar.gz" volumes/
   ```

2. **Database backups** (if using additional database)

3. **Redis persistence**: Redis is configured with AOF persistence

## Scaling

For high traffic, consider:

1. **Multiple backend instances** behind a load balancer
2. **Redis Cluster** for job management
3. **External storage** (AWS S3, Google Cloud Storage) for files
4. **CDN** for serving generated clips

## Support

For issues and questions:
1. Check the logs first
2. Review this deployment guide
3. Check the main README.md for development setup
4. Verify all environment variables are set correctly
