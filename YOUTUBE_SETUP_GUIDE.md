# YouTube Authentication Setup Guide

This guide helps you resolve the YouTube bot detection issue: "Sign in to confirm you're not a bot" that occurs on live servers.

## Problem

Your application works locally but fails on your Ubuntu server with this error:
```
ERROR: [youtube] Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication.
```

## Solution Overview

The issue occurs because YouTube detects server requests as bot traffic. The solution is to use browser cookies from an authenticated session.

## Step-by-Step Setup

### 1. Export YouTube Cookies (On Your Local Machine)

**Option A: Using Browser Extension (Recommended)**
1. Install the "Get cookies.txt LOCALLY" extension for Chrome/Firefox
2. Go to YouTube.com and log in to your account
3. Click the extension and export cookies for `youtube.com`
4. Save the file as `youtube_cookies.txt`

**Option B: Using Developer Tools**
1. Go to YouTube.com and log in
2. Open Developer Tools (F12)
3. Go to Application > Storage > Cookies > https://www.youtube.com
4. Manually export cookie data (more complex)

### 2. Transfer Cookies to Your Server

**Upload the cookies file to your server:**
```bash
# Using scp
scp youtube_cookies.txt user@your-server:/home/ubuntu/

# Or using your preferred file transfer method
```

### 3. Set Up Cookies on Server

**Method 1: Using the Setup Script**
```bash
# Upload the setup script to your server
cd /path/to/your/project
python setup_youtube_cookies.py --cookies-file /home/ubuntu/youtube_cookies.txt
```

**Method 2: Manual Setup**
```bash
# Copy cookies to standard locations
sudo cp youtube_cookies.txt /app/youtube_cookies.txt
sudo cp youtube_cookies.txt /home/ubuntu/youtube_cookies.txt
sudo chmod 644 /app/youtube_cookies.txt
sudo chmod 644 /home/ubuntu/youtube_cookies.txt
```

**Method 3: Environment Variable**
```bash
# Set cookies as environment variable
export YOUTUBE_COOKIES="$(cat youtube_cookies.txt)"

# Add to your deployment script or .bashrc
echo 'export YOUTUBE_COOKIES="$(cat /path/to/youtube_cookies.txt)"' >> ~/.bashrc
```

### 4. Verify Setup

**Test the setup:**
```bash
python setup_youtube_cookies.py --test
```

**Or test manually:**
```bash
python -c "
import yt_dlp
opts = {'cookiefile': '/app/youtube_cookies.txt', 'quiet': True}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False)
    print('✅ Success!' if info else '❌ Failed')
"
```

## Deployment Integration

### Docker Setup

If using Docker, add this to your Dockerfile:
```dockerfile
# Copy cookies file
COPY youtube_cookies.txt /app/youtube_cookies.txt
RUN chmod 644 /app/youtube_cookies.txt
```

### Environment Variables

Add to your deployment environment:
```bash
# If using environment variable method
YOUTUBE_COOKIES="$(cat youtube_cookies.txt)"
```

### Systemd Service

If using systemd, add to your service file:
```ini
[Service]
Environment=YOUTUBE_COOKIES_FILE=/app/youtube_cookies.txt
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **Cookie Expiration**: YouTube cookies expire. You may need to refresh them periodically (every few weeks/months).

2. **Account Safety**: Use a dedicated/throwaway YouTube account for this purpose to avoid risking your main account.

3. **File Permissions**: Ensure cookies files have appropriate permissions (644) and are not accessible to unauthorized users.

4. **Rate Limiting**: Don't make too many requests to avoid being flagged as a bot again.

## Troubleshooting

### Issue: "No cookies found"
**Solution**: Verify file paths and permissions
```bash
ls -la /app/youtube_cookies.txt
ls -la ~/youtube_cookies.txt
```

### Issue: "Invalid cookies format"
**Solution**: Ensure the file starts with the proper header:
```
# Netscape HTTP Cookie File
```

### Issue: Still getting bot detection
**Solutions**:
1. Try refreshing your cookies (re-export from browser)
2. Use a different YouTube account
3. Add delays between requests
4. Use proxy servers (if available)

### Issue: Cookies expired
**Solution**: Re-export cookies from your browser and update the server files.

## Advanced Configuration

### Using Multiple Strategies

The updated code now tries multiple extraction strategies:
1. Mobile web client (mweb) - often bypasses detection
2. Android embedded client
3. TV embedded client  
4. Various other clients

### Custom Cookie Locations

You can specify custom cookie file locations:
```python
python setup_youtube_cookies.py --cookies-file cookies.txt --locations /custom/path/cookies.txt
```

### Proxy Support

If you have proxies, set them via environment:
```bash
export YOUTUBE_PROXIES="proxy1:port,proxy2:port"
```

## Testing Your Setup

### Quick Test
```bash
# Test with a public video
curl -s "http://your-server/api/video-info" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### Monitoring

Monitor your logs for these messages:
- `✅ Using YouTube cookies file from: /path/to/cookies`
- `⚠️ No YouTube cookies found - using enhanced anti-bot strategies`

## Maintenance

### Regular Tasks
1. **Monitor cookie expiration** - refresh every 1-2 months
2. **Check logs** for bot detection errors
3. **Update yt-dlp** regularly for latest fixes
4. **Rotate YouTube accounts** if one gets flagged

### Automation
Create a cron job to check cookie validity:
```bash
# Add to crontab
0 0 * * 0 cd /app && python setup_youtube_cookies.py --test
```

## Support

If you continue to have issues:

1. Check the application logs for detailed error messages
2. Verify your cookies are valid and recent
3. Try using a different YouTube account
4. Consider using a VPN or proxy service
5. Update yt-dlp to the latest version

Remember: YouTube frequently updates their bot detection, so this is an ongoing maintenance task.
