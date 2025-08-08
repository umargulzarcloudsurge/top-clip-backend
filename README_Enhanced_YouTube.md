# 🚀 Enhanced YouTube Downloader System

This enhanced YouTube downloader system addresses the YouTube blocking issues you've been experiencing with a comprehensive approach including automatic cookie management, smart proxy rotation, and advanced anti-bot strategies.

## 🎯 Key Features

- **🍪 Automatic Cookie Refresh**: Automatically validates and extends YouTube cookie expiration dates
- **🌐 Smart Proxy Rotation**: Intelligent proxy management with health monitoring and rotation
- **⚡ Rate Limiting Protection**: Prevents YouTube from rate-limiting your requests
- **🔄 Multiple Download Strategies**: 6+ different download methods with fallback support
- **📊 Detailed Error Logging**: Comprehensive error tracking and instant console feedback
- **🛡️ Anti-Bot Detection**: Advanced user-agent rotation and request patterns

## 🛠️ Quick Setup

### 1. Install Dependencies
```bash
pip install yt-dlp aiohttp asyncio
```

### 2. Run Setup Script
```bash
python setup_enhanced_youtube.py
```

This will:
- Check dependencies
- Create necessary directories
- Set up configuration files
- Test the system
- Show usage examples

### 3. Add YouTube Cookies (Highly Recommended)
1. Log into YouTube in your browser
2. Export cookies using a browser extension like "Get cookies.txt LOCALLY"
3. Save as `youtube_cookies.txt` in the root directory
4. Validate: `python tools/cookie_manager.py validate`

### 4. Configure Proxies (Optional but Recommended)
Set the `YOUTUBE_PROXIES` environment variable:
```bash
export YOUTUBE_PROXIES="http://proxy1:8080,http://user:pass@proxy2:3128"
```

Or edit `config/proxy_config.json`.

## 📚 Usage

### Basic Usage
```python
from utils.youtube_downloader import YouTubeDownloader
import asyncio

async def download_video():
    downloader = YouTubeDownloader()
    
    # Get video information
    info = await downloader.get_video_info('https://youtube.com/watch?v=VIDEO_ID')
    print(f"Title: {info['title']}")
    print(f"Duration: {info['duration']} seconds")
    
    # Download video
    file_path = await downloader.download_video(url, job_id="unique_job_id")
    print(f"Downloaded to: {file_path}")

# Run the download
asyncio.run(download_video())
```

### Cookie Management
```bash
# Validate current cookies
python tools/cookie_manager.py validate

# Extend cookie expiration by 100 years
python tools/cookie_manager.py extend --years 100

# Run automatic refresh
python tools/cookie_manager.py auto-refresh

# Check service status
python tools/cookie_manager.py status

# Test proxy service
python tools/cookie_manager.py test-proxies
```

### Advanced Configuration
```python
from utils.cookie_refresh_service import cookie_refresh_service
from utils.youtube_proxy_service import proxy_service

# Manually refresh cookies
refresh_result = await cookie_refresh_service.auto_validate_and_refresh()

# Get a proxy for yt-dlp
proxy_url = proxy_service.get_proxy_for_ytdlp()

# Check proxy statistics
stats = proxy_service.get_stats()
```

## 🔧 Configuration

### Environment Variables
- `YOUTUBE_PROXIES`: Comma-separated list of proxy URLs
- `YOUTUBE_COOKIES`: Alternative to cookie file (Netscape format)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Configuration Files
- `config/proxy_config.json`: Proxy configuration and settings
- `config/app_config.json`: Application settings and timeouts

## 🍪 Cookie Management Deep Dive

### Automatic Cookie Refresh
The system automatically:
1. **Validates cookies** every 6 hours
2. **Extends expiration dates** when cookies are about to expire
3. **Creates backups** before making changes
4. **Tests YouTube access** to ensure cookies work

### Manual Cookie Operations
```bash
# Create long-lasting cookies from fresh ones
python tools/cookie_manager.py create-long --source fresh_cookies.txt --years 100

# Extend existing cookies
python tools/cookie_manager.py extend --file youtube_cookies.txt --years 50

# Enable/disable auto-refresh
python tools/cookie_manager.py enable-auto
python tools/cookie_manager.py disable-auto
```

### Cookie File Locations
The system checks these locations automatically:
- `./youtube_cookies.txt` (current directory)
- `~/youtube_cookies.txt` (user home)
- `/home/ubuntu/youtube_cookies.txt` (Ubuntu server)
- `/app/youtube_cookies.txt` (containerized apps)
- `/var/www/youtube_cookies.txt` (web server)

## 🌐 Proxy Management

### Proxy Sources
Proxies are loaded from:
1. `YOUTUBE_PROXIES` environment variable
2. `config/proxy_config.json` file
3. `proxies.txt` file
4. Built-in fallback list

### Proxy Health Monitoring
- **Automatic testing** against YouTube endpoints
- **Health scoring** based on success/failure rates
- **Automatic banning** of problematic proxies
- **Smart rotation** to distribute load

### Proxy Formats Supported
- HTTP: `http://proxy:8080`
- HTTPS: `https://proxy:8080`
- SOCKS5: `socks5://proxy:1080`
- Authentication: `http://user:pass@proxy:8080`

## 🔄 Download Strategies

The system uses 6+ different download strategies with fallback:

1. **Simple Download**: Basic download with cookies
2. **Android Client**: Simulates Android YouTube app
3. **Web Client**: Simulates web browser
4. **Updated Method**: Latest yt-dlp configurations
5. **Cookies Method**: Enhanced cookies approach
6. **No Cookies**: Final fallback without authentication

Each strategy:
- Has **5-minute timeout protection**
- Uses **different user agents** and headers
- Applies **exponential backoff** between attempts
- Provides **detailed error logging**

## 📊 Error Handling & Logging

### Instant Console Feedback
Real-time error messages show:
- Strategy being attempted
- Error type and message
- Retry information
- Next strategy to try

### Comprehensive Logging
- **Strategy results tracking**
- **Performance metrics**
- **Rate limiting status**
- **Cookie validation history**
- **Proxy health statistics**

### Error Recovery
- **Automatic strategy fallback**
- **Rate limit detection and backoff**
- **Proxy rotation on failures**
- **Cookie auto-refresh on expiry**

## 🚨 Troubleshooting

### "All strategies failed" Error
1. **Check cookies**: `python tools/cookie_manager.py validate`
2. **Refresh cookies**: `python tools/cookie_manager.py auto-refresh`
3. **Test proxies**: `python tools/cookie_manager.py test-proxies`
4. **Check rate limits**: Wait 10-15 minutes and try again

### Cookie Issues
1. **Export fresh cookies** from a logged-in browser
2. **Use incognito mode** when exporting
3. **Ensure Netscape format** (not JSON)
4. **Check essential cookies** (SAPISID, SSID, HSID, SID, APISID)

### Proxy Issues
1. **Test proxy connectivity** manually
2. **Check authentication** credentials
3. **Verify proxy type** (HTTP vs SOCKS5)
4. **Monitor proxy health** in logs

### Rate Limiting
1. **Reduce request frequency**
2. **Use more proxies**
3. **Enable auto-refresh** for cookies
4. **Monitor rate limit logs**

## 🔐 Security Best Practices

### Cookie Security
- **Never commit cookies** to version control
- **Use environment variables** in production
- **Rotate cookies regularly**
- **Monitor for unauthorized access**

### Proxy Security
- **Use trusted proxy providers**
- **Avoid free public proxies** for production
- **Monitor proxy logs** for abuse
- **Implement IP whitelisting** where possible

## 📈 Performance Optimization

### For High Volume Usage
1. **Use multiple proxy pools**
2. **Implement request queuing**
3. **Monitor rate limits closely**
4. **Scale horizontally** with multiple instances

### Memory Management
- **Clean up temp files** regularly
- **Monitor download directory** disk usage
- **Limit concurrent downloads**
- **Use streaming downloads** for large files

## 🤝 Contributing

To extend the system:

1. **Add new download strategies** in `youtube_downloader.py`
2. **Enhance proxy sources** in `youtube_proxy_service.py`
3. **Improve cookie validation** in `cookie_refresh_service.py`
4. **Add monitoring features** in the CLI tools

## 📄 License

This enhanced YouTube downloader system is provided as-is for educational and development purposes. Ensure compliance with YouTube's Terms of Service and applicable laws when using this system.

## 🆘 Support

For issues or improvements:
1. Check the troubleshooting section
2. Review log files in the `logs/` directory
3. Test with the CLI tools
4. Monitor system status with `python tools/cookie_manager.py status`

---

**Remember**: Always respect YouTube's Terms of Service and rate limits. This system is designed to work within reasonable usage patterns and should not be used for abuse or violations of service terms.
