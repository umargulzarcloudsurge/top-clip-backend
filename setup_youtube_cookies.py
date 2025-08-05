#!/usr/bin/env python3
"""
YouTube Cookies Setup Script for Server Deployment

This script helps you set up YouTube cookies for your server environment
to bypass YouTube's bot detection when using yt-dlp.

Instructions:
1. On your local machine with a browser, go to YouTube and log in
2. Install a browser extension like "Get cookies.txt LOCALLY" 
3. Export YouTube cookies to a file
4. Transfer the cookies file to your server
5. Run this script to set up the cookies properly

Usage:
    python setup_youtube_cookies.py --cookies-file /path/to/youtube_cookies.txt
    python setup_youtube_cookies.py --cookies-env "cookie content here"
    python setup_youtube_cookies.py --help
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_cookies_file(cookies_path):
    """Validate that the cookies file is in the correct format"""
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for proper cookies.txt format
        if not (content.startswith('# Netscape HTTP Cookie File') or 
                content.startswith('# HTTP Cookie File')):
            logger.warning("⚠️ Cookies file doesn't start with proper header")
            logger.warning("Expected: '# Netscape HTTP Cookie File' or '# HTTP Cookie File'")
        
        # Check for YouTube domain cookies
        if 'youtube.com' not in content:
            logger.warning("⚠️ No YouTube cookies found in file")
            return False
        
        # Count number of cookie lines
        cookie_lines = [line for line in content.split('\n') if line and not line.startswith('#')]
        logger.info(f"✅ Found {len(cookie_lines)} cookie entries")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error validating cookies file: {e}")
        return False

def setup_cookies_file(cookies_path, target_locations=None):
    """Set up cookies file in standard locations"""
    if target_locations is None:
        target_locations = [
            '/home/ubuntu/youtube_cookies.txt',
            '/var/www/youtube_cookies.txt', 
            '/opt/app/youtube_cookies.txt',
            '/app/youtube_cookies.txt',
            './youtube_cookies.txt',
            os.path.expanduser('~/youtube_cookies.txt')
        ]
    
    if not os.path.exists(cookies_path):
        logger.error(f"❌ Cookies file not found: {cookies_path}")
        return False
    
    if not validate_cookies_file(cookies_path):
        logger.error("❌ Invalid cookies file format")
        return False
    
    success_count = 0
    
    for target_path in target_locations:
        try:
            # Create directory if it doesn't exist
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            
            # Copy cookies file
            import shutil
            shutil.copy2(cookies_path, target_path)
            
            # Set appropriate permissions (readable by user and group)
            os.chmod(target_path, 0o644)
            
            logger.info(f"✅ Cookies file copied to: {target_path}")
            success_count += 1
            
        except PermissionError:
            logger.warning(f"⚠️ Permission denied for: {target_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to copy to {target_path}: {e}")
    
    if success_count > 0:
        logger.info(f"🎉 Successfully set up cookies in {success_count} locations")
        return True
    else:
        logger.error("❌ Failed to set up cookies in any location")
        return False

def setup_cookies_env(cookies_content):
    """Set up cookies from environment variable content"""
    try:
        # Validate content
        if 'youtube.com' not in cookies_content:
            logger.warning("⚠️ No YouTube cookies found in content")
        
        # Write to temporary file for validation
        temp_path = '/tmp/youtube_cookies_temp.txt'
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        
        if validate_cookies_file(temp_path):
            logger.info("✅ Environment cookies content is valid")
            logger.info("💡 To use these cookies, set the YOUTUBE_COOKIES environment variable:")
            logger.info(f"   export YOUTUBE_COOKIES='{cookies_content[:50]}...'")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"❌ Error processing cookies content: {e}")
        return False

def create_sample_cookies():
    """Create a sample cookies file template"""
    sample_content = """# Netscape HTTP Cookie File
# This is a sample file. Replace with real YouTube cookies.
# To get real cookies:
# 1. Log into YouTube in your browser
# 2. Use "Get cookies.txt LOCALLY" browser extension
# 3. Export cookies for youtube.com
# 4. Replace this content with the exported cookies

# Sample format (replace with real values):
# .youtube.com	TRUE	/	FALSE	1234567890	cookie_name	cookie_value
"""
    
    sample_path = './youtube_cookies_sample.txt'
    with open(sample_path, 'w', encoding='utf-8') as f:
        f.write(sample_content)
    
    logger.info(f"📝 Created sample cookies file: {sample_path}")
    logger.info("💡 Edit this file with your real YouTube cookies")

def test_yt_dlp_with_cookies():
    """Test if yt-dlp can use the cookies"""
    try:
        import yt_dlp
        
        # Test locations where cookies might be
        test_locations = [
            './youtube_cookies.txt',
            os.path.expanduser('~/youtube_cookies.txt'),
            '/app/youtube_cookies.txt'
        ]
        
        for cookies_path in test_locations:
            if os.path.exists(cookies_path):
                logger.info(f"🧪 Testing yt-dlp with cookies from: {cookies_path}")
                
                opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'cookiefile': cookies_path,
                    'extract_flat': True,
                }
                
                # Test with a simple YouTube URL
                test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(test_url, download=False)
                        if info:
                            logger.info("✅ yt-dlp successfully used cookies!")
                            return True
                except Exception as e:
                    logger.warning(f"⚠️ yt-dlp test failed: {str(e)[:100]}...")
        
        logger.warning("⚠️ No working cookies found for yt-dlp test")
        return False
        
    except ImportError:
        logger.warning("⚠️ yt-dlp not installed, skipping test")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing yt-dlp: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Set up YouTube cookies for server deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_youtube_cookies.py --cookies-file ./my_cookies.txt
  python setup_youtube_cookies.py --cookies-env "$(cat cookies.txt)"
  python setup_youtube_cookies.py --sample
  python setup_youtube_cookies.py --test
        """
    )
    
    parser.add_argument('--cookies-file', '-f', 
                        help='Path to YouTube cookies.txt file')
    parser.add_argument('--cookies-env', '-e',
                        help='YouTube cookies content as string')
    parser.add_argument('--sample', '-s', action='store_true',
                        help='Create a sample cookies file template')
    parser.add_argument('--test', '-t', action='store_true',
                        help='Test yt-dlp with existing cookies')
    parser.add_argument('--locations', '-l', nargs='+',
                        help='Custom target locations for cookies file')
    
    args = parser.parse_args()
    
    if args.sample:
        create_sample_cookies()
        return
    
    if args.test:
        success = test_yt_dlp_with_cookies()
        sys.exit(0 if success else 1)
    
    if args.cookies_file:
        success = setup_cookies_file(args.cookies_file, args.locations)
        if success and not args.cookies_env:
            # Test the setup
            test_yt_dlp_with_cookies()
        sys.exit(0 if success else 1)
    
    if args.cookies_env:
        success = setup_cookies_env(args.cookies_env)
        sys.exit(0 if success else 1)
    
    # No arguments provided
    parser.print_help()
    logger.info("\n💡 Quick start:")
    logger.info("1. python setup_youtube_cookies.py --sample")  
    logger.info("2. Get real cookies from your browser and replace sample content")
    logger.info("3. python setup_youtube_cookies.py --cookies-file youtube_cookies_sample.txt")
    logger.info("4. python setup_youtube_cookies.py --test")

if __name__ == '__main__':
    main()
