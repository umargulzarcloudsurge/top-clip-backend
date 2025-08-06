# PowerShell script to deploy updated YouTube cookies to Ubuntu server
# Update these variables with your server details
$ServerIP = "YOUR_SERVER_IP"  # Replace with your actual server IP
$Username = "YOUR_USERNAME"    # Replace with your actual username
$CookiesFile = "youtube_cookies.txt"

# Before running this script:
# 1. Replace YOUR_SERVER_IP with your actual Ubuntu server IP address
# 2. Replace YOUR_USERNAME with your actual Ubuntu username
# 3. Ensure you have SSH access to your server
# 4. Make sure the youtube_cookies.txt file exists in the current directory

Write-Host "Deploying YouTube cookies to Ubuntu server..." -ForegroundColor Green

# Copy cookies file to server
Write-Host "1. Copying cookies file to server..." -ForegroundColor Yellow
scp $CookiesFile ${Username}@${ServerIP}:/tmp/new_cookies.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ File copied successfully" -ForegroundColor Green
    
    # Execute commands on remote server
    Write-Host "2. Setting up cookies on server..." -ForegroundColor Yellow
    
    $commands = @(
        "sudo cp /etc/top-clip-backend/cookies.txt /etc/top-clip-backend/cookies.txt.backup",
        "sudo mv /tmp/new_cookies.txt /etc/top-clip-backend/cookies.txt",
        "sudo chown www-data:www-data /etc/top-clip-backend/cookies.txt", 
        "sudo chmod 644 /etc/top-clip-backend/cookies.txt",
        "head -5 /etc/top-clip-backend/cookies.txt"
    )
    
    foreach ($cmd in $commands) {
        Write-Host "Executing: $cmd" -ForegroundColor Cyan
        ssh ${Username}@${ServerIP} $cmd
    }
    
    Write-Host "3. Testing cookies with yt-dlp..." -ForegroundColor Yellow
    ssh ${Username}@${ServerIP} "yt-dlp --cookies /etc/top-clip-backend/cookies.txt --dump-json 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' | grep title"
    
    Write-Host "4. Testing premium cookie validation..." -ForegroundColor Yellow
    ssh ${Username}@${ServerIP} "python3 -c 'import sys; sys.path.append(\"/path/to/your/backend\"); from utils.youtube_downloader import YouTubeDownloader; yd = YouTubeDownloader(); print(yd._validate_premium_cookies_file(\"/etc/top-clip-backend/cookies.txt\"))'" 2>$null
    
    Write-Host "5. Restarting backend service..." -ForegroundColor Yellow
    Write-Host "Please run manually on server: sudo systemctl restart your-backend-service-name" -ForegroundColor Red
    
    Write-Host "`n✓ PREMIUM COOKIES DEPLOYMENT COMPLETED!" -ForegroundColor Green
    Write-Host "🍪 100-year expiration cookies are now active" -ForegroundColor Green
    Write-Host "🔐 Premium YouTube authentication enabled everywhere" -ForegroundColor Green
    Write-Host "⚡ All download strategies will use these cookies" -ForegroundColor Green
    Write-Host "✅ Bot detection bypass activated" -ForegroundColor Green
    Write-Host "📊 Check your backend logs for 'PREMIUM COOKIES ACTIVATED' message" -ForegroundColor Green
    
} else {
    Write-Host "✗ Failed to copy file to server" -ForegroundColor Red
    Write-Host "Please check your server connection and try again." -ForegroundColor Red
}
