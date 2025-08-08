#!/usr/bin/env python3
"""
YouTube Issues Diagnostic and Fix Script
Addresses the rate limiting and 500 error issues seen in the logs
"""

import os
import sys
import time
import asyncio
import logging
import subprocess
from datetime import datetime, timedelta

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('youtube_fix.log')
    ]
)
logger = logging.getLogger(__name__)

class YouTubeFixer:
    def __init__(self):
        self.issues_found = []
        self.fixes_applied = []
        
    def check_dependencies(self):
        """Check if all required dependencies are installed"""
        logger.info("🔍 Checking dependencies...")
        
        missing_deps = []
        required_packages = ['yt-dlp', 'aiohttp', 'asyncio', 'fastapi', 'uvicorn']
        
        for package in required_packages:
            try:
                __import__(package)
                logger.info(f"✅ {package} - OK")
            except ImportError:
                logger.error(f"❌ {package} - MISSING")
                missing_deps.append(package)
                self.issues_found.append(f"Missing dependency: {package}")
        
        if missing_deps:
            logger.error(f"Missing dependencies: {missing_deps}")
            logger.info("Installing missing dependencies...")
            
            for dep in missing_deps:
                try:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep])
                    logger.info(f"✅ Installed {dep}")
                    self.fixes_applied.append(f"Installed {dep}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Failed to install {dep}: {e}")
        else:
            logger.info("✅ All dependencies are installed")
            
    def check_youtube_cookies(self):
        """Check YouTube cookies file"""
        logger.info("🍪 Checking YouTube cookies...")
        
        cookie_paths = [
            'youtube_cookies.txt',
            os.path.expanduser('~/youtube_cookies.txt'),
            '/home/ubuntu/youtube_cookies.txt'
        ]
        
        cookies_found = False
        for path in cookie_paths:
            if os.path.exists(path):
                logger.info(f"✅ Found cookies file: {path}")
                cookies_found = True
                
                # Check if cookies are valid format
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                        if '# Netscape HTTP Cookie File' not in content:
                            logger.warning(f"⚠️ Cookies file {path} may not be in proper Netscape format")
                            self.issues_found.append(f"Cookies file {path} format issue")
                        else:
                            logger.info(f"✅ Cookies file {path} format is valid")
                except Exception as e:
                    logger.error(f"❌ Error reading cookies file {path}: {e}")
                    self.issues_found.append(f"Error reading cookies: {e}")
                break
        
        if not cookies_found:
            logger.warning("⚠️ No YouTube cookies file found")
            logger.info("This may cause authentication issues with YouTube")
            self.issues_found.append("No YouTube cookies file found")
            
            # Create a placeholder cookies file with instructions
            self.create_cookies_placeholder()
            
    def create_cookies_placeholder(self):
        """Create a placeholder cookies file with instructions"""
        try:
            with open('youtube_cookies.txt', 'w') as f:
                f.write("""# Netscape HTTP Cookie File
# This is a placeholder file. To fix YouTube authentication issues:
# 
# 1. Install a browser extension like "Get cookies.txt LOCALLY"
# 2. Go to YouTube.com and log in
# 3. Use the extension to export cookies
# 4. Replace this file with the exported cookies
# 
# Without proper cookies, YouTube may block requests or show errors
""")
            logger.info("✅ Created placeholder cookies file with instructions")
            self.fixes_applied.append("Created cookies placeholder")
        except Exception as e:
            logger.error(f"❌ Failed to create placeholder cookies file: {e}")
    
    def check_rate_limiting(self):
        """Check if we're currently rate limited"""
        logger.info("⏰ Checking rate limiting status...")
        
        # Create a simple rate limit test
        try:
            import yt_dlp
            
            # Test with a simple, non-controversial video
            test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - always available
            
            opts = {
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 10,
                'retries': 1,
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                start_time = time.time()
                try:
                    info = ydl.extract_info(test_url, download=False)
                    elapsed = time.time() - start_time
                    
                    if info:
                        logger.info(f"✅ YouTube access test passed ({elapsed:.1f}s)")
                    else:
                        logger.warning("⚠️ YouTube access test returned no info")
                        self.issues_found.append("YouTube access test failed - no info")
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    if '429' in error_msg or 'too many requests' in error_msg:
                        logger.error("❌ RATE LIMITED - YouTube is blocking requests")
                        logger.info("Recommended: Wait 30-60 minutes before trying again")
                        self.issues_found.append("Rate limited by YouTube")
                    elif 'sign in' in error_msg:
                        logger.error("❌ AUTHENTICATION REQUIRED - Need fresh cookies")
                        self.issues_found.append("YouTube requires authentication")
                    else:
                        logger.error(f"❌ YouTube access test failed: {e}")
                        self.issues_found.append(f"YouTube access error: {e}")
                        
        except ImportError:
            logger.error("❌ yt-dlp not available for rate limit test")
            self.issues_found.append("yt-dlp not available")
        except Exception as e:
            logger.error(f"❌ Rate limit check failed: {e}")
            self.issues_found.append(f"Rate limit check error: {e}")
    
    def fix_job_manager_issues(self):
        """Fix job manager persistence issues"""
        logger.info("🔧 Checking job manager issues...")
        
        # Check Redis connection
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            logger.info("✅ Redis connection successful")
            
            # Check for orphaned jobs
            job_keys = list(client.scan_iter(match="job:*"))
            if job_keys:
                logger.info(f"🔍 Found {len(job_keys)} jobs in Redis")
                
                # Clean up jobs older than 24 hours
                cutoff = datetime.now() - timedelta(hours=24)
                cleaned = 0
                
                for key in job_keys:
                    try:
                        job_data = client.get(key)
                        if job_data:
                            import json
                            data = json.loads(job_data)
                            created_at = data.get('created_at', '')
                            
                            if created_at and created_at < cutoff.isoformat():
                                job_id = key.split(':')[1]
                                client.delete(key)
                                client.delete(f"clips:{job_id}")
                                client.delete(f"job_clips:{job_id}")
                                cleaned += 1
                    except Exception as e:
                        logger.warning(f"⚠️ Error cleaning job {key}: {e}")
                
                if cleaned > 0:
                    logger.info(f"🧹 Cleaned up {cleaned} old jobs from Redis")
                    self.fixes_applied.append(f"Cleaned {cleaned} old Redis jobs")
                    
            else:
                logger.info("📭 No jobs found in Redis")
                
        except ImportError:
            logger.warning("⚠️ Redis not available - job persistence may be affected")
            self.issues_found.append("Redis not available")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.issues_found.append(f"Redis connection error: {e}")
    
    def create_rate_limit_config(self):
        """Create a rate limiting configuration"""
        logger.info("⚙️ Creating rate limiting configuration...")
        
        config = {
            "rate_limiting": {
                "enabled": True,
                "base_delay": 5.0,
                "max_delay": 300.0,
                "requests_per_hour": 30,
                "backoff_multiplier": 2.0,
                "cooldown_on_429": 1800  # 30 minutes
            },
            "youtube_settings": {
                "retry_attempts": 3,
                "timeout_per_request": 60,
                "use_fallback_info": True,
                "enable_cookies": True
            },
            "error_handling": {
                "max_consecutive_failures": 5,
                "failure_backoff_minutes": 10,
                "reset_after_success": True
            }
        }
        
        try:
            import json
            with open('youtube_config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info("✅ Created rate limiting configuration file")
            self.fixes_applied.append("Created rate limiting config")
        except Exception as e:
            logger.error(f"❌ Failed to create config file: {e}")
    
    def test_api_endpoints(self):
        """Test critical API endpoints"""
        logger.info("🌐 Testing API endpoints...")
        
        try:
            import requests
            import json
            
            base_url = "http://127.0.0.1:8000"
            
            # Test health endpoint
            try:
                response = requests.get(f"{base_url}/health", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Health endpoint responding")
                else:
                    logger.warning(f"⚠️ Health endpoint returned {response.status_code}")
                    self.issues_found.append(f"Health endpoint error: {response.status_code}")
            except requests.exceptions.ConnectionError:
                logger.warning("⚠️ API server not running - start with: python main.py")
                self.issues_found.append("API server not running")
            except Exception as e:
                logger.error(f"❌ Health endpoint test failed: {e}")
                self.issues_found.append(f"Health endpoint error: {e}")
            
            # Test video-info endpoint with a safe video
            try:
                test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                response = requests.get(
                    f"{base_url}/video-info", 
                    params={"url": test_url}, 
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info("✅ Video-info endpoint working")
                elif response.status_code == 429:
                    logger.error("❌ Video-info endpoint rate limited")
                    self.issues_found.append("Video-info endpoint rate limited")
                else:
                    logger.warning(f"⚠️ Video-info endpoint returned {response.status_code}")
                    self.issues_found.append(f"Video-info error: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                pass  # Already logged that server isn't running
            except Exception as e:
                logger.error(f"❌ Video-info endpoint test failed: {e}")
                self.issues_found.append(f"Video-info error: {e}")
                
        except ImportError:
            logger.info("📡 requests not available for API testing")
    
    def generate_report(self):
        """Generate a diagnostic report"""
        logger.info("📊 Generating diagnostic report...")
        
        report = f"""
================================
YouTube Issues Diagnostic Report
================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ISSUES FOUND ({len(self.issues_found)}):
{chr(10).join(f"❌ {issue}" for issue in self.issues_found) if self.issues_found else "✅ No issues found"}

FIXES APPLIED ({len(self.fixes_applied)}):
{chr(10).join(f"✅ {fix}" for fix in self.fixes_applied) if self.fixes_applied else "🔧 No fixes needed"}

RECOMMENDATIONS:
"""
        
        if "Rate limited by YouTube" in self.issues_found:
            report += """
🚫 RATE LIMITING DETECTED:
   - Wait 30-60 minutes before making more requests
   - Consider using proxies or VPN
   - Implement longer delays between requests
   - Use different YouTube client types
"""
        
        if "No YouTube cookies file found" in self.issues_found:
            report += """
🍪 MISSING COOKIES:
   - Install browser extension: "Get cookies.txt LOCALLY"
   - Export cookies from logged-in YouTube session
   - Replace youtube_cookies.txt with exported cookies
   - Restart the application after adding cookies
"""
        
        if "API server not running" in self.issues_found:
            report += """
🖥️ SERVER NOT RUNNING:
   - Start server with: python main.py
   - Or use: uvicorn main:app --host 0.0.0.0 --port 8000
   - Check for port conflicts
   - Ensure all dependencies are installed
"""
        
        if not self.issues_found:
            report += """
✅ SYSTEM APPEARS HEALTHY:
   - All dependencies installed
   - YouTube access working
   - API endpoints responding
   - No immediate issues detected
"""
        
        report += f"""

NEXT STEPS:
1. Review any remaining issues above
2. Apply recommended fixes
3. Restart the application
4. Monitor logs for continued issues
5. Re-run this diagnostic if problems persist

================================
"""
        
        # Save report to file
        try:
            with open('youtube_diagnostic_report.txt', 'w') as f:
                f.write(report)
            logger.info("✅ Diagnostic report saved to youtube_diagnostic_report.txt")
        except Exception as e:
            logger.error(f"❌ Failed to save report: {e}")
        
        # Print report to console
        print(report)
    
    async def run_diagnostics(self):
        """Run all diagnostic checks"""
        logger.info("🚀 Starting YouTube diagnostics...")
        
        # Run all checks
        self.check_dependencies()
        self.check_youtube_cookies()
        self.check_rate_limiting()
        self.fix_job_manager_issues()
        self.create_rate_limit_config()
        self.test_api_endpoints()
        
        # Generate report
        self.generate_report()
        
        logger.info("🎉 Diagnostics completed!")

def main():
    """Main function"""
    print("🔧 YouTube Issues Diagnostic and Fix Tool")
    print("=" * 50)
    
    fixer = YouTubeFixer()
    
    try:
        # Run async diagnostics
        asyncio.run(fixer.run_diagnostics())
        
        if fixer.issues_found:
            print(f"\n⚠️ Found {len(fixer.issues_found)} issues that need attention")
            print("📋 Check the diagnostic report for detailed recommendations")
        else:
            print("\n✅ No major issues detected!")
            
        if fixer.fixes_applied:
            print(f"🔧 Applied {len(fixer.fixes_applied)} automatic fixes")
            print("🔄 Consider restarting the application to apply changes")
            
    except KeyboardInterrupt:
        print("\n⏹️ Diagnostics interrupted by user")
    except Exception as e:
        logger.error(f"❌ Diagnostic script failed: {e}")
        print(f"❌ Error: {e}")
    
    print("\n📋 Full diagnostic report saved to youtube_diagnostic_report.txt")
    print("📋 Logs saved to youtube_fix.log")

if __name__ == "__main__":
    main()
