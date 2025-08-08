# AWS Ubuntu Setup Guide - TopClip Redis Fix

## Prerequisites

This guide assumes you have:
- Ubuntu 20.04+ AWS EC2 instance
- SSH access to your server
- Sudo privileges
- TopClip backend already deployed

## Step 1: Install Redis on Ubuntu AWS

### Option A: Install Redis Server (Recommended for Production)

```bash
# Update package list
sudo apt update

# Install Redis server
sudo apt install redis-server -y

# Check Redis version
redis-server --version

# Enable Redis to start on boot
sudo systemctl enable redis-server

# Start Redis service
sudo systemctl start redis-server

# Check Redis status
sudo systemctl status redis-server
```

### Option B: Install Redis via Snap (Alternative)

```bash
# Install Redis via snap
sudo snap install redis

# Redis will automatically start
```

### Option C: Install Latest Redis from Source

```bash
# Install dependencies
sudo apt update
sudo apt install build-essential tcl wget -y

# Download and compile Redis 7.x (latest stable)
cd /tmp
wget https://download.redis.io/redis-stable.tar.gz
tar xzf redis-stable.tar.gz
cd redis-stable
make
sudo make install

# Create Redis user and directories
sudo adduser --system --group --no-create-home redis
sudo mkdir -p /var/lib/redis /var/log/redis /etc/redis
sudo chown redis:redis /var/lib/redis /var/log/redis
```

## Step 2: Configure Redis for AWS Production

### Basic Configuration

```bash
# Edit Redis configuration
sudo nano /etc/redis/redis.conf
```

**Key settings for AWS:**

```conf
# Bind to localhost only (secure)
bind 127.0.0.1

# Set a password (IMPORTANT for security)
requirepass your-super-secure-redis-password-here

# Enable persistence
save 900 1
save 300 10
save 60 10000

# Set memory policy
maxmemory 512mb
maxmemory-policy allkeys-lru

# Log configuration
loglevel notice
logfile /var/log/redis/redis-server.log

# Background saving
daemonize yes

# PID file
pidfile /var/run/redis/redis-server.pid

# Database directory
dir /var/lib/redis
```

### Create Systemd Service (if installing from source)

```bash
# Create systemd service file
sudo nano /etc/systemd/system/redis.service
```

**Service file content:**

```ini
[Unit]
Description=Redis In-Memory Data Store
After=network.target

[Service]
User=redis
Group=redis
ExecStart=/usr/local/bin/redis-server /etc/redis/redis.conf
ExecStop=/usr/local/bin/redis-cli shutdown
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

**Enable and start the service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable redis
sudo systemctl start redis
sudo systemctl status redis
```

## Step 3: Configure Firewall and Security

### UFW Firewall Setup

```bash
# Enable UFW if not already enabled
sudo ufw enable

# Redis should only be accessible locally
# Don't open port 6379 to the internet
# Redis is accessed locally by your backend

# Check UFW status
sudo ufw status
```

### AWS Security Group Configuration

In your AWS Console:
1. **DO NOT** open port 6379 to 0.0.0.0/0
2. Redis should only be accessible within your instance
3. Your backend connects to Redis via localhost (127.0.0.1)

## Step 4: Test Redis Installation

```bash
# Test Redis connection
redis-cli ping
# Expected: PONG

# Test with password (if configured)
redis-cli -a your-super-secure-redis-password-here ping
# Expected: PONG

# Check Redis info
redis-cli info server

# Test basic operations
redis-cli set test "Hello World"
redis-cli get test
redis-cli del test
```

## Step 5: Update Backend Configuration

### Update .env File

```bash
# Navigate to your backend directory
cd /path/to/your/topclip-backend

# Edit .env file
nano .env
```

**Add/Update these lines:**

```env
# Redis Configuration for AWS Ubuntu
REDIS_URL=redis://localhost:6379/0

# If you set a password:
# REDIS_URL=redis://:your-super-secure-redis-password-here@localhost:6379/0

# AWS Specific Settings
NODE_ENV=production
HOST=0.0.0.0
PORT=8000

# Logging level for production
LOG_LEVEL=INFO
```

### Update Requirements (if needed)

```bash
# Ensure Redis Python client is installed
pip install redis>=4.5.0

# Or if using pipenv
pipenv install redis>=4.5.0

# Or add to requirements.txt
echo "redis>=4.5.0" >> requirements.txt
pip install -r requirements.txt
```

## Step 6: Deploy and Restart Backend

### Restart Your Backend Service

```bash
# If using systemd service
sudo systemctl restart topclip-backend

# If running with screen/tmux
# Kill existing process and restart

# If running directly
python main.py

# If using Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

### Verify Deployment

```bash
# Check backend logs for Redis connection
tail -f /path/to/your/logs/ai_clips_enhanced.log

# Look for these success messages:
# ✅ Redis connected on attempt 1: redis://localhost:6379/0
# ✅ EnhancedJobManager created with Redis persistence

# Test the API health endpoint
curl http://localhost:8000/health

# Should show Redis status in response
```

## Step 7: AWS-Specific Production Optimizations

### Memory Configuration

```bash
# Check available memory
free -h

# Configure Redis memory limit based on instance size
sudo nano /etc/redis/redis.conf

# For t3.micro (1GB RAM): Set maxmemory to 200-300MB
# For t3.small (2GB RAM): Set maxmemory to 500-700MB
# For t3.medium (4GB RAM): Set maxmemory to 1-1.5GB
```

### Log Rotation

```bash
# Configure log rotation for Redis
sudo nano /etc/logrotate.d/redis
```

**Log rotation config:**

```
/var/log/redis/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    postrotate
        systemctl reload redis
    endscript
}
```

### Backup Strategy

```bash
# Create backup script
sudo nano /usr/local/bin/redis-backup.sh
```

**Backup script:**

```bash
#!/bin/bash
BACKUP_DIR="/opt/redis-backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Create Redis dump
redis-cli BGSAVE

# Wait for background save to complete
while [ $(redis-cli LASTSAVE) -eq $(redis-cli LASTSAVE) ]; do
    sleep 1
done

# Copy dump file with timestamp
cp /var/lib/redis/dump.rdb $BACKUP_DIR/dump_$DATE.rdb

# Keep only last 7 days of backups
find $BACKUP_DIR -name "dump_*.rdb" -mtime +7 -delete

echo "Redis backup completed: $BACKUP_DIR/dump_$DATE.rdb"
```

**Make executable and schedule:**

```bash
sudo chmod +x /usr/local/bin/redis-backup.sh

# Add to crontab (daily backup at 2 AM)
echo "0 2 * * * /usr/local/bin/redis-backup.sh" | sudo crontab -
```

## Step 8: Monitoring and Maintenance

### Redis Monitoring Commands

```bash
# Check Redis stats
redis-cli info stats

# Monitor Redis in real-time
redis-cli monitor

# Check memory usage
redis-cli info memory

# Check connected clients
redis-cli info clients

# Check persistence info
redis-cli info persistence
```

### CloudWatch Integration (Advanced)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

# Configure CloudWatch to monitor Redis metrics
# Create IAM role with CloudWatch permissions
# Configure custom metrics for Redis monitoring
```

## Step 9: Testing the Fix

### Create Test Job

```bash
# Test job creation and persistence
curl -X POST http://your-aws-instance:8000/api/process-video \
  -F "youtube_url=https://youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "options={\"clipLength\":\"30-60s\",\"captionStyle\":\"Hype\",\"enableHookTitles\":true,\"layout\":\"Vertical (9:16)\",\"clipCount\":3}"

# Note the job_id from the response
```

### Test Persistence Across Restarts

```bash
# Restart your backend service
sudo systemctl restart topclip-backend

# Wait a few seconds, then check job status
curl http://your-aws-instance:8000/api/job-status/YOUR_JOB_ID_HERE

# Should return job data (not 404) - proving Redis persistence works
```

### Verify Redis Data

```bash
# Check Redis contains job data
redis-cli KEYS "job:*"

# Check specific job
redis-cli HGETALL "job:YOUR_JOB_ID_HERE"

# Check clips data
redis-cli KEYS "clips:*"
```

## Troubleshooting AWS-Specific Issues

### Issue: Redis Connection Refused

```bash
# Check if Redis is running
sudo systemctl status redis-server

# Check Redis logs
sudo journalctl -u redis-server -f

# Check if Redis is listening
sudo netstat -tlnp | grep 6379

# Test local connection
redis-cli ping
```

### Issue: Out of Memory

```bash
# Check memory usage
free -h
redis-cli info memory

# Increase swap if needed (for small instances)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Issue: Permission Denied

```bash
# Fix Redis permissions
sudo chown -R redis:redis /var/lib/redis
sudo chown -R redis:redis /var/log/redis
sudo chmod 755 /var/lib/redis
sudo chmod 755 /var/log/redis

# Restart Redis
sudo systemctl restart redis-server
```

### Issue: Backend Can't Connect to Redis

```bash
# Check Redis configuration
sudo grep -n "^bind" /etc/redis/redis.conf

# Should show: bind 127.0.0.1
# Check if protected mode is off for localhost
redis-cli config get protected-mode

# Check backend logs
tail -f /path/to/your/backend/logs/ai_clips_enhanced.log
```

## AWS Instance Sizing Recommendations

### For Production:

- **Minimum**: t3.small (2GB RAM, 2 vCPU) - Good for testing
- **Recommended**: t3.medium (4GB RAM, 2 vCPU) - Good for moderate traffic
- **High Traffic**: c5.large (4GB RAM, 2 vCPU) - Better CPU performance

### Redis Memory Allocation by Instance:

- **t3.micro (1GB)**: Redis maxmemory 200MB
- **t3.small (2GB)**: Redis maxmemory 500MB  
- **t3.medium (4GB)**: Redis maxmemory 1GB
- **t3.large (8GB)**: Redis maxmemory 2GB

## Security Checklist for AWS

- ✅ Redis password configured (`requirepass`)
- ✅ Redis bound to localhost only (`bind 127.0.0.1`)
- ✅ Port 6379 NOT open in Security Group
- ✅ UFW firewall enabled
- ✅ Redis running as non-root user
- ✅ Regular backups configured
- ✅ Log rotation configured
- ✅ CloudWatch monitoring (optional)

## Expected Results

After successful setup:

- ✅ Redis running and persistent across reboots
- ✅ Backend connects to Redis successfully
- ✅ Zero 404 errors for valid job IDs after server restarts
- ✅ Jobs persist in Redis for 1 week
- ✅ Graceful degradation if Redis temporarily fails
- ✅ Production-ready monitoring and backups

Your TopClip backend will now have enterprise-grade job persistence on AWS Ubuntu, eliminating the 404 errors that users experienced after server restarts.
