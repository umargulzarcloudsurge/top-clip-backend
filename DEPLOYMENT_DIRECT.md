# AI Clips Backend - Direct Python + Nginx Deployment on Ubuntu

This guide covers deploying the AI Clips Backend directly with Python and Nginx (no Docker) on Ubuntu.

## 📋 Prerequisites

- Ubuntu server with sudo access
- Python 3.11+ installed
- Nginx installed
- Redis server running
- Domain name pointed to your server

## 🚀 Step-by-Step Deployment

### 1. Prepare the Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install python3-pip python3-venv nginx redis-server ffmpeg -y

# Install additional dependencies for video processing
sudo apt install build-essential libssl-dev libffi-dev python3-dev -y
```

### 2. Setup Application Directory

```bash
# Create application directory
sudo mkdir -p /opt/aiclips-backend
sudo chown $USER:$USER /opt/aiclips-backend
cd /opt/aiclips-backend

# Upload your backend files here
# (transfer run_production.py, main.py, utils/, requirements.txt, etc.)
```

### 3. Setup Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install additional production dependencies
pip install gunicorn
```

### 4. Configure Environment Variables

```bash
# Copy environment template
cp .env.production.example .env.production

# Edit with your actual values
nano .env.production
```

**Required variables in `.env.production`:**
```bash
# Core Configuration
ENVIRONMENT=production
HOST=127.0.0.1
PORT=8000
WORKERS=4

# API Keys (Update these!)
OPENAI_API_KEY=your_actual_openai_api_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_actual_supabase_key
SUPABASE_ANON_KEY=your_actual_anon_key
STRIPE_SECRET_KEY=your_actual_stripe_key
STRIPE_WEBHOOK_SECRET=your_actual_webhook_secret

# Redis Configuration
REDIS_URL=redis://localhost:6379

# CORS and Frontend
FRONTEND_URL=https://your-frontend-domain.com
CORS_ORIGINS=["https://your-frontend-domain.com"]

# Performance Settings
MAX_FILE_SIZE_MB=1000
MAX_CONCURRENT_JOBS=10
CLEANUP_TEMP_FILES=true
UPLOAD_IMMEDIATELY=true

# Storage Settings
SUPABASE_BUCKET_NAME=user-clips
STORAGE_CLEANUP_ENABLED=true
```

### 5. Create Required Directories

```bash
# Create application directories
mkdir -p temp output thumbnails music game_videos logs
chmod 755 temp output thumbnails music game_videos logs
```

### 6. Setup Systemd Service

```bash
# Copy service file
sudo cp aiclips-backend.service /etc/systemd/system/

# Edit service file with correct paths
sudo nano /etc/systemd/system/aiclips-backend.service
```

**Update these paths in the service file:**
```ini
WorkingDirectory=/opt/aiclips-backend
Environment=PATH=/opt/aiclips-backend/venv/bin
EnvironmentFile=/opt/aiclips-backend/.env.production
ExecStart=/opt/aiclips-backend/venv/bin/python run_production.py
ReadWritePaths=/opt/aiclips-backend/temp /opt/aiclips-backend/output /opt/aiclips-backend/thumbnails /opt/aiclips-backend/music /opt/aiclips-backend/game_videos /opt/aiclips-backend/logs
```

### 7. Setup Nginx

```bash
# Copy nginx configuration
sudo cp nginx_direct.conf /etc/nginx/sites-available/aiclips-backend

# Edit with your domain
sudo nano /etc/nginx/sites-available/aiclips-backend
```

**Update in nginx configuration:**
- Replace `your-domain.com` with your actual domain
- Update `/path/to/your/backend/static/` if you have static files

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/aiclips-backend /etc/nginx/sites-enabled/

# Remove default nginx site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

### 8. Start Services

```bash
# Start Redis (if not already running)
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Enable and start the backend service
sudo systemctl daemon-reload
sudo systemctl enable aiclips-backend
sudo systemctl start aiclips-backend

# Check service status
sudo systemctl status aiclips-backend
```

### 9. Verify Deployment

```bash
# Check backend health
curl http://localhost:8000/health

# Check through nginx
curl http://your-domain.com/health

# View logs
sudo journalctl -u aiclips-backend -f
```

## 🔒 SSL/HTTPS Setup (Let's Encrypt)

### Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### Get SSL Certificate
```bash
# Generate certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal (already setup by certbot)
sudo systemctl status certbot.timer
```

## 📊 Monitoring and Maintenance

### View Logs
```bash
# Backend application logs
sudo journalctl -u aiclips-backend -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Redis logs
sudo journalctl -u redis-server -f
```

### Service Management
```bash
# Restart backend
sudo systemctl restart aiclips-backend

# Restart nginx
sudo systemctl restart nginx

# Check status
sudo systemctl status aiclips-backend
sudo systemctl status nginx
sudo systemctl status redis-server
```

### Update Application
```bash
# Navigate to app directory
cd /opt/aiclips-backend

# Pull updates (if using git)
git pull origin main

# Restart service
sudo systemctl restart aiclips-backend
```

## 🔧 Troubleshooting

### Backend Won't Start
```bash
# Check service logs
sudo journalctl -u aiclips-backend -n 50

# Check if port 8000 is in use
sudo netstat -tlnp | grep 8000

# Test manually
cd /opt/aiclips-backend
source venv/bin/activate
python run_production.py
```

### Nginx Issues
```bash
# Test nginx config
sudo nginx -t

# Check nginx status
sudo systemctl status nginx

# View error logs
sudo tail -f /var/log/nginx/error.log
```

### Redis Issues
```bash
# Check redis status
sudo systemctl status redis-server

# Test redis connection
redis-cli ping
```

### File Permissions
```bash
# Fix ownership
sudo chown -R www-data:www-data /opt/aiclips-backend/temp
sudo chown -R www-data:www-data /opt/aiclips-backend/output
sudo chown -R www-data:www-data /opt/aiclips-backend/logs

# Fix permissions
chmod 755 /opt/aiclips-backend/temp
chmod 755 /opt/aiclips-backend/output
chmod 755 /opt/aiclips-backend/logs
```

## 📈 Performance Optimization

### For High Traffic
- Increase `WORKERS` in `.env.production`
- Use Nginx upstream for load balancing
- Consider Redis clustering
- Monitor system resources

### Resource Monitoring
```bash
# CPU and Memory usage
htop

# Disk usage
df -h

# Network connections
sudo netstat -tulnp | grep :8000
```

## 🛡️ Security Checklist

- ✅ Firewall configured (only ports 22, 80, 443 open)
- ✅ SSL certificate installed
- ✅ Environment variables secured (not in git)
- ✅ Service running as www-data user
- ✅ File permissions properly set
- ✅ Regular security updates
- ✅ Rate limiting enabled in Nginx

## 🎯 Quick Commands Summary

```bash
# Status check
sudo systemctl status aiclips-backend nginx redis-server

# Restart all services
sudo systemctl restart aiclips-backend nginx

# View all logs
sudo journalctl -u aiclips-backend -f

# Health check
curl http://your-domain.com/health

# Update application
cd /opt/aiclips-backend && git pull && sudo systemctl restart aiclips-backend
```
