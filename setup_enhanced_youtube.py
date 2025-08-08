#!/usr/bin/env python3
"""
Setup script for Enhanced YouTube Downloader System
Configures cookies, proxies, and tests the system
"""

import os
import sys
import asyncio
import json
import subprocess
from pathlib import Path

def print_banner():
    """Print setup banner"""
    print("=" * 80)
    print("🚀 Enhanced YouTube Downloader Setup")
    print("   - Automatic Cookie Refresh")
    print("   - Smart Proxy Rotation") 
    print("   - Rate Limiting Protection")
    print("   - Multiple Download Strategies")
    print("=" * 80)
    print()

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'yt-dlp',
        'aiohttp',
        'asyncio'
    ]
    
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Install them with:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    print("✅ All dependencies are installed!")
    return True

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    
    directories = [
        'temp',
        'tools',
        'utils',
        'logs',
        'config'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"   ✅ {directory}/")
    
    print("✅ Directories created!")

def setup_environment_variables():
    """Help user set up environment variables"""
    print("\n🌍 Environment Variables Setup")
    print("You can configure these environment variables:")
    print()
    
    # YouTube proxies
    print("1. YOUTUBE_PROXIES (optional but recommended)")
    print("   Set this to a comma-separated list of proxy URLs")
    print("   Example: 'http://proxy1:8080,http://user:pass@proxy2:3128'")
    current_proxies = os.getenv('YOUTUBE_PROXIES', '')
    if current_proxies:
        print(f"   Current value: {current_proxies}")
    else:
        print("   Current value: Not set")
    print()
    
    # YouTube cookies
    print("2. YOUTUBE_COOKIES (optional)")
    print("   Set this to your YouTube cookies in Netscape format")
    print("   Alternative to using a cookies file")
    current_cookies = os.getenv('YOUTUBE_COOKIES', '')
    if current_cookies:
        print("   Current value: Set (content hidden for security)")
    else:
        print("   Current value: Not set")
    print()
    
    # Log level
    print("3. LOG_LEVEL (optional)")
    print("   Set logging level: DEBUG, INFO, WARNING, ERROR")
    current_log_level = os.getenv('LOG_LEVEL', 'INFO')
    print(f"   Current value: {current_log_level}")
    print()

def check_cookie_files():
    """Check for existing cookie files"""
    print("🍪 Checking for YouTube cookie files...")
    
    cookie_paths = [
        'youtube_cookies.txt',
        os.path.expanduser('~/youtube_cookies.txt'),
        '/home/ubuntu/youtube_cookies.txt',
        '/app/youtube_cookies.txt',
        '/var/www/youtube_cookies.txt'
    ]
    
    found_cookies = []
    
    for path in cookie_paths:
        if os.path.exists(path):
            print(f"   ✅ Found: {path}")
            found_cookies.append(path)
        else:
            print(f"   ❌ Not found: {path}")
    
    if not found_cookies:
        print("\n⚠️ No cookie files found!")
        print("To get the best results, you should:")
        print("1. Log into YouTube in your browser")
        print("2. Export cookies using a browser extension like 'Get cookies.txt LOCALLY'")
        print("3. Save as 'youtube_cookies.txt' in this directory")
        print("4. Run: python tools/cookie_manager.py validate")
    else:
        print(f"\n✅ Found {len(found_cookies)} cookie file(s)")
    
    return found_cookies

def create_sample_config():
    """Create sample configuration files"""
    print("\n⚙️ Creating sample configuration...")
    
    # Sample proxy config
    proxy_config = {
        "proxies": [
            "# Add your proxy URLs here",
            "# http://proxy1:8080",
            "# http://user:pass@proxy2:3128",
            "# socks5://proxy3:1080"
        ],
        "rotation_strategy": "round_robin",
        "health_check_interval": 300,
        "max_failures_before_ban": 3
    }
    
    with open('config/proxy_config.json', 'w') as f:
        json.dump(proxy_config, f, indent=2)
    
    print("   ✅ Created config/proxy_config.json")
    
    # Sample app config
    app_config = {
        "youtube_downloader": {
            "max_retries": 6,
            "timeout_per_strategy": 300,
            "rate_limit_requests_per_hour": 50,
            "auto_refresh_cookies": True
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }
    
    with open('config/app_config.json', 'w') as f:
        json.dump(app_config, f, indent=2)
    
    print("   ✅ Created config/app_config.json")

async def test_system():
    """Test the enhanced YouTube system"""
    print("\n🧪 Testing Enhanced YouTube Downloader System...")
    
    try:
        # Import our services
        sys.path.insert(0, os.getcwd())
        from utils.cookie_refresh_service import cookie_refresh_service
        from utils.youtube_proxy_service import proxy_service
        
        # Test cookie service
        print("   🍪 Testing cookie refresh service...")
        status = cookie_refresh_service.get_status()
        print(f"      Auto refresh: {'✅ Enabled' if status['auto_refresh_enabled'] else '❌ Disabled'}")
        
        # Test proxy service
        print("   🌐 Testing proxy service...")
        try:
            proxy_stats = proxy_service.get_stats()
            print(f"      Total proxies: {proxy_stats['total_proxies']}")
            print(f"      Working proxies: {proxy_stats['working_proxies']}")
        except Exception as e:
            print(f"      ⚠️ Proxy service error: {e}")
        
        # Test cookie validation if cookies exist
        cookie_found = False
        for path in ['youtube_cookies.txt', os.path.expanduser('~/youtube_cookies.txt')]:
            if os.path.exists(path):
                print(f"   🔍 Testing cookie validation for {path}...")
                validation = await cookie_refresh_service.validate_cookie_freshness(path)
                print(f"      Valid: {'✅ Yes' if validation['valid'] else '❌ No'}")
                print(f"      Cookies found: {validation['cookies_found']}")
                cookie_found = True
                break
        
        if not cookie_found:
            print("   ⚠️ No cookies found to validate")
        
        print("✅ System test completed!")
        
    except Exception as e:
        print(f"❌ System test failed: {e}")
        return False
    
    return True

def show_usage_examples():
    """Show usage examples"""
    print("\n📚 Usage Examples:")
    print()
    
    print("1. Cookie Management:")
    print("   python tools/cookie_manager.py validate           # Check your cookies")
    print("   python tools/cookie_manager.py extend --years 100 # Extend expiration")
    print("   python tools/cookie_manager.py auto-refresh       # Auto refresh cookies")
    print("   python tools/cookie_manager.py status             # Check service status")
    print()
    
    print("2. Using the Enhanced YouTube Downloader:")
    print("   from utils.youtube_downloader import YouTubeDownloader")
    print("   downloader = YouTubeDownloader()")
    print("   info = await downloader.get_video_info('https://youtube.com/watch?v=...')")
    print("   file_path = await downloader.download_video(url, job_id)")
    print()
    
    print("3. Testing Proxies:")
    print("   python tools/cookie_manager.py test-proxies       # Test proxy service")
    print()
    
    print("4. Environment Variables (add to your .env or shell):")
    print("   export YOUTUBE_PROXIES='http://proxy1:8080,http://proxy2:3128'")
    print("   export LOG_LEVEL='DEBUG'")

def main():
    """Main setup function"""
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Setup failed - missing dependencies")
        return False
    
    # Create directories
    create_directories()
    
    # Setup environment variables
    setup_environment_variables()
    
    # Check cookie files
    cookie_files = check_cookie_files()
    
    # Create sample config
    create_sample_config()
    
    # Test system
    print("\n" + "=" * 80)
    print("🏁 Running System Tests...")
    print("=" * 80)
    
    success = asyncio.run(test_system())
    
    if success:
        print("\n✅ Enhanced YouTube Downloader setup completed successfully!")
        
        # Show next steps
        print("\n🎯 Next Steps:")
        print("1. Add your YouTube cookies to 'youtube_cookies.txt' (highly recommended)")
        print("2. Configure proxies in 'config/proxy_config.json' or YOUTUBE_PROXIES env var")
        print("3. Test with: python tools/cookie_manager.py validate")
        print("4. Use the enhanced downloader in your application")
        
        show_usage_examples()
        
    else:
        print("\n❌ Setup completed with warnings - check the errors above")
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
