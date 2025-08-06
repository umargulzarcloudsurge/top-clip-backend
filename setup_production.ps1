# Production setup script for AI Clips Backend (Windows PowerShell)

Write-Host "🚀 Setting up AI Clips Backend for Production" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Check if docker and docker-compose are installed
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

if (!(Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker Compose is not installed. Please install Docker Compose first." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Docker and Docker Compose are installed" -ForegroundColor Green

# Create required directories
Write-Host "📁 Creating required directories..." -ForegroundColor Yellow
$directories = @("volumes\temp", "volumes\output", "volumes\thumbnails", "volumes\music", "volumes\game_videos", "volumes\logs", "nginx\ssl")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "✅ Directories created" -ForegroundColor Green

# Check if .env.production exists
if (!(Test-Path ".env.production")) {
    if (Test-Path ".env.production.example") {
        Write-Host "⚙️  Creating .env.production from example..." -ForegroundColor Yellow
        Copy-Item ".env.production.example" ".env.production"
        Write-Host "⚠️  Please edit .env.production with your actual values before running docker-compose" -ForegroundColor Yellow
    } else {
        Write-Host "❌ .env.production.example not found. Please create .env.production manually." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ .env.production already exists" -ForegroundColor Green
}

# Check required environment variables
Write-Host "🔍 Checking environment configuration..." -ForegroundColor Yellow
$envIssues = $false

if (Test-Path ".env.production") {
    $content = Get-Content ".env.production" -Raw
    
    if ($content -match "your_openai_api_key_here") {
        Write-Host "⚠️  Please update OPENAI_API_KEY in .env.production" -ForegroundColor Yellow
        $envIssues = $true
    }
    
    if ($content -match "your_supabase_project_url") {
        Write-Host "⚠️  Please update SUPABASE_URL in .env.production" -ForegroundColor Yellow
        $envIssues = $true
    }
    
    if ($content -match "your_supabase_service_role_key") {
        Write-Host "⚠️  Please update SUPABASE_SERVICE_KEY in .env.production" -ForegroundColor Yellow
        $envIssues = $true
    }
}

if ($envIssues) {
    Write-Host ""
    Write-Host "📝 Edit .env.production with your actual API keys before proceeding:" -ForegroundColor Yellow
    Write-Host "   notepad .env.production" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "✅ Environment configuration looks good" -ForegroundColor Green
}

# Build the Docker image
Write-Host "🏗️  Building Docker image..." -ForegroundColor Yellow
& docker-compose -f docker-compose.simple.yml build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed" -ForegroundColor Red
    exit 1
}

# Test the health check
Write-Host "🔍 Testing the application..." -ForegroundColor Yellow
& docker-compose -f docker-compose.simple.yml up -d

Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method GET -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Health check passed!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Health check returned status: $($response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Health check failed: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "Check the logs with: docker-compose -f docker-compose.simple.yml logs" -ForegroundColor Gray
}

& docker-compose -f docker-compose.simple.yml down

Write-Host ""
Write-Host "🎉 Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit .env.production with your actual API keys" -ForegroundColor White
Write-Host "2. Start the services: docker-compose -f docker-compose.simple.yml up -d" -ForegroundColor White
Write-Host "3. View logs: docker-compose -f docker-compose.simple.yml logs -f" -ForegroundColor White
Write-Host "4. Check health: curl http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "For SSL/domain setup, use docker-compose.yml instead and configure nginx." -ForegroundColor Gray
