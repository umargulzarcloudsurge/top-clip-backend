#!/bin/bash
# Production setup script for AI Clips Backend

set -e

echo "🚀 Setting up AI Clips Backend for Production"
echo "============================================="

# Check if docker and docker-compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create required directories
echo "📁 Creating required directories..."
mkdir -p volumes/{temp,output,thumbnails,music,game_videos,logs}
mkdir -p nginx/ssl

# Set permissions
chmod 755 volumes/*
echo "✅ Directories created"

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    if [ -f ".env.production.example" ]; then
        echo "⚙️  Creating .env.production from example..."
        cp .env.production.example .env.production
        echo "⚠️  Please edit .env.production with your actual values before running docker-compose"
    else
        echo "❌ .env.production.example not found. Please create .env.production manually."
        exit 1
    fi
else
    echo "✅ .env.production already exists"
fi

# Check required environment variables
echo "🔍 Checking environment configuration..."
if grep -q "your_openai_api_key_here" .env.production 2>/dev/null; then
    echo "⚠️  Please update OPENAI_API_KEY in .env.production"
    ENV_ISSUES=1
fi

if grep -q "your_supabase_project_url" .env.production 2>/dev/null; then
    echo "⚠️  Please update SUPABASE_URL in .env.production"
    ENV_ISSUES=1
fi

if grep -q "your_supabase_service_role_key" .env.production 2>/dev/null; then
    echo "⚠️  Please update SUPABASE_SERVICE_KEY in .env.production"
    ENV_ISSUES=1
fi

if [ "$ENV_ISSUES" = "1" ]; then
    echo ""
    echo "📝 Edit .env.production with your actual API keys before proceeding:"
    echo "   nano .env.production"
    echo ""
else
    echo "✅ Environment configuration looks good"
fi

# Build the Docker image
echo "🏗️  Building Docker image..."
docker-compose -f docker-compose.simple.yml build

# Test the health check
echo "🔍 Testing the application..."
docker-compose -f docker-compose.simple.yml up -d
sleep 10

echo "⏳ Waiting for services to start..."
sleep 5

if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Health check passed!"
    docker-compose -f docker-compose.simple.yml down
else
    echo "⚠️  Health check failed. Check the logs:"
    echo "   docker-compose -f docker-compose.simple.yml logs"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env.production with your actual API keys"
echo "2. Start the services: docker-compose -f docker-compose.simple.yml up -d"
echo "3. View logs: docker-compose -f docker-compose.simple.yml logs -f"
echo "4. Check health: curl http://localhost:8000/health"
echo ""
echo "For SSL/domain setup, use docker-compose.yml instead and configure nginx."
