#!/bin/bash
# TopClip Backend AWS Ubuntu Deployment Script
# Run this script on your AWS Ubuntu instance

set -e  # Exit on any error

echo "🚀 TopClip Backend AWS Ubuntu Deployment"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as ubuntu user."
   exit 1
fi

# Update system
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Redis
print_status "Installing Redis server..."
sudo apt install redis-server -y

# Configure Redis
print_status "Configuring Redis for production..."
sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.backup

# Create Redis configuration
sudo tee /etc/redis/redis.conf > /dev/null <<EOF
# Basic Redis Configuration for TopClip
bind 127.0.0.1
port 6379
timeout 0
tcp-keepalive 300

# Security
requirepass $(openssl rand -base64 32)
protected-mode yes

# Persistence
save 900 1
save 300 10
save 60 10000
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis

# Memory management
maxmemory 512mb
maxmemory-policy allkeys-lru

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Other settings
daemonize yes
pidfile /var/run/redis/redis-server.pid
databases 16
EOF

# Get the generated password
REDIS_PASSWORD=$(sudo grep "requirepass" /etc/redis/redis.conf | awk '{print $2}')

# Start and enable Redis
print_status "Starting Redis service..."
sudo systemctl enable redis-server
sudo systemctl restart redis-server

# Test Redis
print_status "Testing Redis connection..."
if redis-cli -a "$REDIS_PASSWORD" ping | grep -q PONG; then
    print_status "✅ Redis is working correctly"
else
    print_error "❌ Redis test failed"
    exit 1
fi

# Install Python dependencies (if not already installed)
print_status "Installing Python dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
    pip install redis>=4.5.0  # Ensure Redis client is installed
fi

# Update .env file for production
print_status "Configuring environment variables..."
if [ -f ".env" ]; then
    cp .env .env.backup
    
    # Update Redis URL with password
    sed -i "s|REDIS_URL=redis://localhost:6379/0|REDIS_URL=redis://:$REDIS_PASSWORD@localhost:6379/0|g" .env
    
    # Enable production settings
    sed -i 's|# NODE_ENV=production|NODE_ENV=production|g' .env
    sed -i 's|# HOST=0.0.0.0|HOST=0.0.0.0|g' .env
    sed -i 's|# PORT=8000|PORT=8000|g' .env
    sed -i 's|# LOG_LEVEL=INFO|LOG_LEVEL=INFO|g' .env
    
    print_status "Environment configured for production"
else
    print_error ".env file not found. Please create it first."
    exit 1
fi

# Create necessary directories
print_status "Creating application directories..."
mkdir -p temp output thumbnails logs music game_videos fonts

# Set up systemd service
print_status "Setting up systemd service..."
sudo cp topclip-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable topclip-backend

# Configure log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/topclip > /dev/null <<EOF
/home/ubuntu/topclip-backend/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    postrotate
        systemctl reload topclip-backend
    endscript
}
EOF

# Set up Redis backup
print_status "Setting up Redis backup..."
sudo mkdir -p /opt/redis-backups
sudo chown ubuntu:ubuntu /opt/redis-backups

# Create backup script
tee /home/ubuntu/redis-backup.sh > /dev/null <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/redis-backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
redis-cli -a "$REDIS_PASSWORD" BGSAVE

# Wait for background save to complete
while [ $(redis-cli -a "$REDIS_PASSWORD" LASTSAVE) -eq $(redis-cli -a "$REDIS_PASSWORD" LASTSAVE) ]; do
    sleep 1
done

cp /var/lib/redis/dump.rdb $BACKUP_DIR/dump_$DATE.rdb
find $BACKUP_DIR -name "dump_*.rdb" -mtime +7 -delete

echo "Redis backup completed: $BACKUP_DIR/dump_$DATE.rdb"
EOF

chmod +x /home/ubuntu/redis-backup.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/redis-backup.sh") | crontab -

# Configure firewall
print_status "Configuring UFW firewall..."
sudo ufw --force enable
sudo ufw allow 8000/tcp  # Backend API
sudo ufw allow 22/tcp    # SSH
# Note: Redis port 6379 is NOT opened - it's localhost only

# Start the backend service
print_status "Starting TopClip backend service..."
sudo systemctl restart topclip-backend

# Wait a moment for startup
sleep 5

# Check service status
print_status "Checking service status..."
if sudo systemctl is-active --quiet topclip-backend; then
    print_status "✅ TopClip backend service is running"
else
    print_error "❌ TopClip backend service failed to start"
    sudo systemctl status topclip-backend
    exit 1
fi

# Test the API
print_status "Testing API endpoint..."
sleep 2
if curl -s http://localhost:8000/health > /dev/null; then
    print_status "✅ API health check passed"
else
    print_warning "⚠️ API health check failed - service may still be starting"
fi

# Final status check
print_status "Final deployment status check..."
echo "========================================="
echo "🔧 Redis Status:"
sudo systemctl status redis-server --no-pager -l | head -3
echo ""
echo "🚀 Backend Service Status:"
sudo systemctl status topclip-backend --no-pager -l | head -3
echo ""
echo "🌐 API Health Check:"
curl -s http://localhost:8000/health | jq '.status' 2>/dev/null || echo "Health endpoint not responding (may need a few more seconds to start)"
echo ""

print_status "🎉 Deployment completed!"
echo "========================================="
echo "📋 Next Steps:"
echo "1. Test job creation: curl -X POST http://your-instance-ip:8000/api/process-video"
echo "2. Monitor logs: sudo journalctl -u topclip-backend -f"
echo "3. Check Redis: redis-cli -a '$REDIS_PASSWORD' info"
echo "4. View service status: sudo systemctl status topclip-backend"
echo ""
echo "🔐 Security Notes:"
echo "- Redis password: $REDIS_PASSWORD (saved in .env)"
echo "- Redis is bound to localhost only (secure)"
echo "- Firewall configured (UFW enabled)"
echo "- Daily Redis backups scheduled"
echo ""
echo "✅ Your TopClip backend is now running with Redis persistence!"
echo "   Jobs will survive server restarts - no more 404 errors!"
