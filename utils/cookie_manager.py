import os
import time
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class CookieManager:
    """Automated YouTube cookie management system"""
    
    def __init__(self):
        self.cookie_paths = [
            './youtube_cookies.txt',
            '/app/youtube_cookies.txt',
            '/home/ubuntu/youtube_cookies.txt',
            os.path.expanduser('~/youtube_cookies.txt')
        ]
        self.last_refresh_file = './last_cookie_refresh.json'
        self.refresh_interval_days = 365  # Refresh every year (since manually provided cookies have 100-year expiration)
        # No hardcoded credentials needed - we'll use browser sessions
        
    def should_refresh_cookies(self) -> bool:
        """Check if cookies need refreshing"""
        try:
            # Check if any cookie file exists
            cookie_exists = any(os.path.exists(path) for path in self.cookie_paths)
            if not cookie_exists:
                logger.info("No cookie files found, refresh needed")
                return True
            
            # Check last refresh time
            if os.path.exists(self.last_refresh_file):
                with open(self.last_refresh_file, 'r') as f:
                    data = json.load(f)
                    last_refresh = datetime.fromisoformat(data['last_refresh'])
                    next_refresh = last_refresh + timedelta(days=self.refresh_interval_days)
                    
                    if datetime.now() >= next_refresh:
                        logger.info(f"Cookie refresh needed, last refresh: {last_refresh}")
                        return True
                    else:
                        logger.info(f"Cookies still valid until: {next_refresh}")
                        return False
            else:
                logger.info("No refresh history found, refresh needed")
                return True
                
        except Exception as e:
            logger.error(f"Error checking cookie refresh status: {e}")
            return True
    
    def update_refresh_timestamp(self):
        """Update the last refresh timestamp"""
        try:
            data = {
                'last_refresh': datetime.now().isoformat(),
                'next_refresh': (datetime.now() + timedelta(days=self.refresh_interval_days)).isoformat()
            }
            with open(self.last_refresh_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Updated cookie refresh timestamp")
        except Exception as e:
            logger.error(f"Error updating refresh timestamp: {e}")
    
    async def refresh_cookies_browser_popup(self) -> bool:
        """Refresh cookies using browser popup for interactive login"""
        try:
            # Import selenium here to avoid dependency issues if not installed
            try:
                from selenium import webdriver
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.chrome.options import Options
                from selenium.common.exceptions import TimeoutException, NoSuchElementException
            except ImportError:
                logger.error("Selenium not installed. Install with: pip install selenium")
                return False
            
            logger.info("Starting browser popup for YouTube login...")
            
            # Set up Chrome options for visible browser (not headless)
            chrome_options = Options()
            
            # Basic stealth options
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set realistic user agent
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
            
            # Window settings
            chrome_options.add_argument("--window-size=1200,800")
            chrome_options.add_argument("--start-maximized")
            
            # Performance optimizations
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            
            # Add additional stealth properties
            chrome_options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2
            })
            
            driver = None
            try:
                # Initialize Chrome driver with visible window
                driver = webdriver.Chrome(options=chrome_options)
                driver.set_page_load_timeout(60)
                
                # Execute script to remove webdriver properties
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
                driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
                
                # Navigate to YouTube
                logger.info("Opening YouTube login popup...")
                driver.get("https://www.youtube.com")
                await asyncio.sleep(2)
                
                # Check if already logged in by looking for user avatar or profile
                try:
                    # Look for user avatar/profile button
                    user_avatar = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label*='Account'], img[alt*='Avatar'], #avatar-btn"))
                    )
                    logger.info("✅ User is already logged in to YouTube!")
                    
                    # Navigate to a video to ensure session is active
                    driver.get("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
                    await asyncio.sleep(3)
                    
                except TimeoutException:
                    logger.info("User not logged in, showing login popup...")
                    
                    # Click sign in button
                    try:
                        sign_in_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/accounts')] | //paper-button[contains(text(), 'Sign in')] | //yt-button-renderer[contains(@aria-label, 'Sign in')]"))
                        )
                        sign_in_button.click()
                        logger.info("Clicked sign in button - popup should be visible for user login")
                        
                        # Wait for user to complete login (check for profile/avatar)
                        logger.info("⏳ Waiting for user to complete login in the popup window...")
                        logger.info("📋 Please log in to your YouTube account in the browser window that opened")
                        
                        # Wait up to 5 minutes for user to log in
                        user_logged_in = WebDriverWait(driver, 300).until(
                            EC.any_of(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label*='Account']")),
                                EC.presence_of_element_located((By.CSS_SELECTOR, "img[alt*='Avatar']")),
                                EC.presence_of_element_located((By.ID, "avatar-btn")),
                                EC.presence_of_element_located((By.CSS_SELECTOR, "#account-name"))
                            )
                        )
                        
                        if user_logged_in:
                            logger.info("✅ User successfully logged in!")
                            # Navigate to a video to ensure full session
                            driver.get("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
                            await asyncio.sleep(3)
                        
                    except TimeoutException:
                        logger.error("❌ Login timeout - user did not complete login within 5 minutes")
                        return False
                    except Exception as login_error:
                        logger.error(f"❌ Login process failed: {login_error}")
                        return False
                
                # Extract cookies after successful login
                cookies = driver.get_cookies()
                logger.info(f"Extracted {len(cookies)} cookies from browser session")
                
                if not cookies:
                    logger.error("❌ No cookies found after login")
                    return False
                
                # Convert to Netscape format
                cookie_content = self._cookies_to_netscape_format(cookies)
                
                # Save cookies to all paths
                success_count = 0
                for cookie_path in self.cookie_paths:
                    try:
                        # Create directory if needed
                        os.makedirs(os.path.dirname(cookie_path) if os.path.dirname(cookie_path) else '.', exist_ok=True)
                        
                        with open(cookie_path, 'w', encoding='utf-8') as f:
                            f.write(cookie_content)
                        
                        os.chmod(cookie_path, 0o644)
                        logger.info(f"Saved cookies to: {cookie_path}")
                        success_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to save cookies to {cookie_path}: {e}")
                
                if success_count > 0:
                    self.update_refresh_timestamp()
                    logger.info(f"✅ Successfully refreshed cookies and saved to {success_count} locations")
                    
                    # Close browser after successful extraction
                    logger.info("🎉 Cookie extraction complete! Closing browser...")
                    return True
                else:
                    logger.error("❌ Failed to save cookies to any location")
                    return False
                
            except Exception as driver_error:
                logger.error(f"Browser driver error: {driver_error}")
                return False
            finally:
                if driver:
                    try:
                        # Give user a moment to see success message
                        await asyncio.sleep(2)
                        driver.quit()
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error in browser popup login: {e}")
            return False
    
    async def refresh_cookies_from_existing_browser(self) -> bool:
        """Try to extract cookies from existing browser profiles"""
        try:
            # Import selenium here to avoid dependency issues if not installed
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
            except ImportError:
                logger.error("Selenium not installed. Install with: pip install selenium")
                return False
            
            logger.info("Attempting to extract cookies from existing browser sessions...")
            
            # Common browser profile paths
            browser_profiles = [
                # Chrome profiles
                os.path.expanduser("~/.config/google-chrome/Default"),
                os.path.expanduser("~/Library/Application Support/Google/Chrome/Default"),
                os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/Default"),
                # Chrome Flatpak
                os.path.expanduser("~/.var/app/com.google.Chrome/config/google-chrome/Default"),
            ]
            
            for profile_path in browser_profiles:
                if os.path.exists(profile_path):
                    try:
                        logger.info(f"Trying browser profile: {profile_path}")
                        
                        chrome_options = Options()
                        chrome_options.add_argument("--headless")
                        chrome_options.add_argument("--no-sandbox")
                        chrome_options.add_argument("--disable-dev-shm-usage")
                        chrome_options.add_argument(f"--user-data-dir={os.path.dirname(profile_path)}")
                        chrome_options.add_argument(f"--profile-directory={os.path.basename(profile_path)}")
                        
                        driver = None
                        try:
                            driver = webdriver.Chrome(options=chrome_options)
                            driver.set_page_load_timeout(30)
                            
                            # Navigate to YouTube to check login status
                            driver.get("https://www.youtube.com")
                            await asyncio.sleep(3)
                            
                            # Check if logged in
                            try:
                                # Look for user avatar or account elements
                                user_elements = driver.find_elements("css selector", "button[aria-label*='Account'], img[alt*='Avatar'], #avatar-btn")
                                if user_elements:
                                    logger.info("✅ Found logged in YouTube session in existing browser")
                                    
                                    # Extract cookies
                                    cookies = driver.get_cookies()
                                    if cookies:
                                        logger.info(f"Extracted {len(cookies)} cookies from existing browser session")
                                        
                                        # Convert to Netscape format
                                        cookie_content = self._cookies_to_netscape_format(cookies)
                                        
                                        # Save cookies
                                        success_count = 0
                                        for cookie_path in self.cookie_paths:
                                            try:
                                                os.makedirs(os.path.dirname(cookie_path) if os.path.dirname(cookie_path) else '.', exist_ok=True)
                                                
                                                with open(cookie_path, 'w', encoding='utf-8') as f:
                                                    f.write(cookie_content)
                                                
                                                os.chmod(cookie_path, 0o644)
                                                logger.info(f"Saved cookies to: {cookie_path}")
                                                success_count += 1
                                            except Exception as e:
                                                logger.warning(f"Failed to save cookies to {cookie_path}: {e}")
                                        
                                        if success_count > 0:
                                            self.update_refresh_timestamp()
                                            logger.info(f"✅ Successfully extracted cookies from existing browser")
                                            return True
            
                            except Exception as check_error:
                                logger.debug(f"No login found in profile {profile_path}: {check_error}")
                                
                        finally:
                            if driver:
                                driver.quit()
                                
                    except Exception as profile_error:
                        logger.debug(f"Could not access browser profile {profile_path}: {profile_error}")
                        continue
            
            logger.info("No logged in YouTube sessions found in existing browsers")
            return False
            
        except Exception as e:
            logger.error(f"Error extracting from existing browser: {e}")
            return False
    
    async def refresh_cookies_selenium(self) -> bool:
        """Legacy method - now redirects to browser popup"""
        return await self.refresh_cookies_browser_popup()
    
    async def refresh_cookies_puppeteer(self) -> bool:
        """Refresh cookies using Puppeteer (Node.js required) - deprecated, redirects to browser popup"""
        logger.info("Puppeteer method is deprecated, using browser popup instead...")
        return await self.refresh_cookies_browser_popup()
    
    def _cookies_to_netscape_format(self, cookies: List[Dict]) -> str:
        """Convert cookies to Netscape format"""
        netscape_format = "# Netscape HTTP Cookie File\n"
        netscape_format += "# Generated by automated cookie manager\n"
        
        for cookie in cookies:
            if 'youtube.com' in cookie.get('domain', '') or 'google.com' in cookie.get('domain', ''):
                domain = cookie.get('domain', '')
                
                # Handle domain specification correctly for Netscape format
                if domain.startswith('.'):
                    # Domain starts with dot - this means it applies to subdomains
                    domain_specified = 'TRUE'
                else:
                    # Domain doesn't start with dot - add dot and set to TRUE
                    domain = '.' + domain if not domain.startswith('.') else domain
                    domain_specified = 'TRUE'
                
                http_only = 'TRUE' if cookie.get('httpOnly', False) else 'FALSE'
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expires = int(cookie.get('expiry', time.time() + 86400 * 365))  # Default 1 year
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                # Netscape format: domain, domain_specified, path, secure, expires, name, value
                netscape_format += f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
        
        return netscape_format
    
    async def auto_refresh_cookies(self) -> bool:
        """Automatically refresh cookies if needed - but prioritize existing valid cookies"""
        try:
            # First check if we have valid existing cookies
            if self.validate_current_cookies():
                logger.info("✅ Valid cookies already exist, skipping refresh")
                return True
            
            # Check if refresh is needed based on time
            if not self.should_refresh_cookies():
                logger.info("✅ Cookies are fresh, no refresh needed")
                return True
            
            logger.info("🔄 Starting automatic cookie refresh...")
            
            # Try to extract from existing browser sessions first (less intrusive)
            success = await self.refresh_cookies_from_existing_browser()
            if success:
                logger.info("✅ Successfully extracted cookies from existing browser session")
                return True
            
            # Only use browser popup as last resort and only if no cookies exist at all
            cookie_exists = any(os.path.exists(path) for path in self.cookie_paths)
            if not cookie_exists:
                logger.info("No cookies found anywhere, using browser popup as last resort...")
                success = await self.refresh_cookies_browser_popup()
            else:
                logger.info("Existing cookies found but invalid, keeping them for now")
                success = True  # Don't force popup if we have some cookies
            
            if success:
                logger.info("✅ Automatic cookie refresh completed successfully")
            else:
                logger.warning("⚠️ Automatic cookie refresh failed, but continuing with existing cookies")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in auto_refresh_cookies: {e}")
            # Don't fail completely - return True to use existing cookies
            return True
    
    def validate_current_cookies(self) -> bool:
        """Validate if current cookies are working"""
        try:
            import yt_dlp
            
            for cookie_path in self.cookie_paths:
                if os.path.exists(cookie_path):
                    opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'cookiefile': cookie_path,
                        'extract_flat': True,
                    }
                    
                    try:
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False)
                            if info:
                                logger.info(f"✅ Cookies are valid: {cookie_path}")
                                return True
                    except Exception as e:
                        logger.warning(f"Cookie validation failed for {cookie_path}: {str(e)[:100]}...")
            
            logger.warning("⚠️ No valid cookies found")
            return False
            
        except ImportError:
            logger.warning("yt-dlp not available for cookie validation")
            return False
        except Exception as e:
            logger.error(f"Error validating cookies: {e}")
            return False

# Global cookie manager instance
cookie_manager = CookieManager()
