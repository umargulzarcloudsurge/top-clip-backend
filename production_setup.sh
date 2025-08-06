#!/bin/bash

# Production Setup Script for TopClip Backend
# Run this on your Ubuntu server to match local environment

echo "🚀 Starting TopClip Backend Production Setup..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install system dependencies
echo "🔧 Installing system dependencies..."
sudo apt install -y python3.10 python3.10-venv python3-pip ffmpeg git curl redis-server

# Start and enable Redis
echo "⚡ Setting up Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
else
    echo "❌ Redis failed to start"
    exit 1
fi

# Navigate to backend directory (adjust path as needed)
cd /home/ubuntu/Backend-main || {
    echo "❌ Backend directory not found. Please adjust the path in this script."
    exit 1
}

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3.10 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
echo "📚 Installing Python packages..."
pip install aiofiles==24.1.0
pip install certifi==2025.7.14
pip install fastapi==0.116.1
pip install ffmpeg_python==0.2.0
pip install httpx==0.28.1
pip install numpy==1.24.3
pip install openai==1.97.1
pip install opencv_python==4.8.1.78
pip install Pillow==11.3.0
pip install pydantic==2.11.7
pip install pydub==0.25.1
pip install python-dotenv==1.1.1
pip install redis==5.0.1
pip install stripe==12.3.0
pip install supabase==2.17.0
pip install uvicorn==0.35.0

# Install the exact same yt-dlp version as local
echo "📺 Installing yt-dlp (exact version)..."
pip install yt-dlp==2025.7.21

# Verify yt-dlp installation
if yt-dlp --version; then
    echo "✅ yt-dlp installed successfully"
else
    echo "❌ yt-dlp installation failed"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p temp output thumbnails music game_videos fonts

# Set permissions
chmod 755 temp output thumbnails music game_videos fonts

echo "✅ Production setup completed!"
echo ""
echo "Next steps:"
echo "1. Copy your .env file to the server"
echo "2. Copy your youtube_cookies.txt file"
echo "3. Start the server with: source venv/bin/activate && python main.py"
echo ""
echo "🔍 Verify installation:"
echo "- Python version: $(python --version)"
echo "- yt-dlp version: $(yt-dlp --version)"
echo "- Redis status: $(redis-cli ping)"
