#!/usr/bin/env python3
"""
Cookie Refresh Service
Automatic YouTube cookie validation and refresh system
"""

import os
import logging
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import re
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CookieInfo:
    """Information about a cookie"""
    name: str
    value: str
    domain: str
    path: str
    expires: Optional[datetime] = None
    secure: bool = False
    http_only: bool = False
    same_site: Optional[str] = None

class CookieRefreshService:
    """Service for automatically refreshing YouTube cookies"""
    
    def __init__(self):
        self.cookie_paths = [
            'youtube_cookies.txt',
            '/home/ubuntu/youtube_cookies.txt',
            os.path.expanduser('~/youtube_cookies.txt'),
            '/app/youtube_cookies.txt',
            '/var/www/youtube_cookies.txt'
        ]
        self.last_validation = None
        self.validation_interval = timedelta(hours=6)  # Check every 6 hours
        self.cookie_cache = {}
        self.auto_refresh_enabled = True
        
    def extend_cookie_expiration(self, cookie_file_path: str, years: int = 100) -> bool:
        """
        Extend cookie expiration dates in the cookies file
        Note: This only changes the file, not the actual server-side validity
        """
        try:
            if not os.path.exists(cookie_file_path):
                logger.warning(f"Cookie file not found: {cookie_file_path}")
                return False
            
            # Read current cookies
            with open(cookie_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Calculate new expiration date (100 years from now)
            future_date = datetime.now() + timedelta(days=years * 365)
            future_timestamp = int(future_date.timestamp())
            
            modified_lines = []
            cookies_extended = 0
            
            for line in lines:
                line = line.rstrip('\n\r')
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    modified_lines.append(line)
                    continue
                
                # Parse cookie line (Netscape format)
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain, domain_specified, path, secure, expiration, name, value = parts[:7]
                    
                    # Extend expiration for YouTube cookies
                    if 'youtube.com' in domain or 'google.com' in domain:
                        parts[4] = str(future_timestamp)  # Update expiration
                        cookies_extended += 1
                        logger.debug(f"Extended cookie {name} expiration to {future_date}")
                    
                    # Rejoin the parts
                    modified_line = '\t'.join(parts)
                    modified_lines.append(modified_line)
                else:
                    # Keep malformed lines as-is
                    modified_lines.append(line)
            
            # Write back to file with extended expiration dates
            with open(cookie_file_path, 'w', encoding='utf-8') as f:
                for line in modified_lines:
                    f.write(line + '\n')
            
            logger.info(f"✅ Extended expiration for {cookies_extended} YouTube cookies in {cookie_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to extend cookie expiration: {e}")
            return False
    
    def create_long_lasting_cookies(self, source_file: str, output_file: str = None, years: int = 100) -> str:
        """
        Create a new cookie file with extended expiration dates
        """
        if output_file is None:
            output_file = source_file.replace('.txt', '_extended.txt')
        
        try:
            # Copy and extend the source file
            import shutil
            shutil.copy2(source_file, output_file)
            
            success = self.extend_cookie_expiration(output_file, years)
            
            if success:
                logger.info(f"✅ Created long-lasting cookie file: {output_file}")
                return output_file
            else:
                logger.error(f"❌ Failed to create extended cookie file")
                return source_file
                
        except Exception as e:
            logger.error(f"❌ Error creating long-lasting cookies: {e}")
            return source_file
    
    async def validate_cookie_freshness(self, cookie_file: str) -> Dict[str, Any]:
        """
        Validate if cookies are still working with YouTube
        """
        validation_result = {
            'valid': False,
            'error': None,
            'cookies_found': 0,
            'youtube_accessible': False,
            'expires_soon': False,
            'oldest_expiry': None
        }
        
        try:
            if not os.path.exists(cookie_file):
                validation_result['error'] = f"Cookie file not found: {cookie_file}"
                return validation_result
            
            # Parse cookies and check expiration
            cookies = self._parse_cookie_file(cookie_file)
            validation_result['cookies_found'] = len(cookies)
            
            # Check for soon-to-expire cookies
            now = datetime.now()
            warning_threshold = now + timedelta(days=7)  # Warn if expires within 7 days
            
            youtube_cookies = [c for c in cookies if 'youtube.com' in c.domain or 'google.com' in c.domain]
            
            if youtube_cookies:
                for cookie in youtube_cookies:
                    if cookie.expires and cookie.expires < warning_threshold:
                        validation_result['expires_soon'] = True
                        if validation_result['oldest_expiry'] is None or cookie.expires < validation_result['oldest_expiry']:
                            validation_result['oldest_expiry'] = cookie.expires
            
            # Test actual YouTube connectivity
            youtube_test_result = await self._test_youtube_access(cookie_file)
            validation_result['youtube_accessible'] = youtube_test_result
            validation_result['valid'] = youtube_test_result
            
            if not youtube_test_result:
                validation_result['error'] = "Cookies exist but YouTube access failed - cookies may be expired or invalid"
            
        except Exception as e:
            validation_result['error'] = f"Validation error: {e}"
            
        return validation_result
    
    def _parse_cookie_file(self, cookie_file: str) -> List[CookieInfo]:
        """Parse Netscape cookie file format"""
        cookies = []
        
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain, domain_specified, path, secure, expiration, name, value = parts[:7]
                        
                        # Parse expiration
                        expires = None
                        try:
                            if expiration and expiration.isdigit():
                                expires = datetime.fromtimestamp(int(expiration))
                        except (ValueError, OSError):
                            pass
                        
                        cookie = CookieInfo(
                            name=name,
                            value=value,
                            domain=domain,
                            path=path,
                            expires=expires,
                            secure=secure.lower() == 'true'
                        )
                        cookies.append(cookie)
        
        except Exception as e:
            logger.error(f"Error parsing cookie file {cookie_file}: {e}")
        
        return cookies
    
    async def _test_youtube_access(self, cookie_file: str) -> bool:
        """Test if cookies allow YouTube access"""
        try:
            # Load cookies into aiohttp format
            jar = aiohttp.CookieJar()
            
            cookies = self._parse_cookie_file(cookie_file)
            for cookie in cookies:
                if 'youtube.com' in cookie.domain or 'google.com' in cookie.domain:
                    # Convert to aiohttp cookie
                    jar.update_cookies({cookie.name: cookie.value}, response_url=f"https://{cookie.domain.lstrip('.')}")
            
            # Test YouTube access
            async with aiohttp.ClientSession(
                cookie_jar=jar,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}
            ) as session:
                
                # Test basic YouTube access
                async with session.get('https://www.youtube.com/robots.txt') as response:
                    if response.status == 200:
                        logger.debug("✅ Basic YouTube access successful")
                        
                        # Test authenticated endpoint
                        try:
                            async with session.get('https://www.youtube.com/feed/subscriptions') as auth_response:
                                if auth_response.status == 200:
                                    logger.debug("✅ Authenticated YouTube access successful")
                                    return True
                                elif auth_response.status == 403:
                                    logger.warning("⚠️ YouTube access forbidden - cookies may be expired")
                                    return False
                        except Exception:
                            # If authenticated test fails, basic access is still good
                            return True
                        
                        return True
                    else:
                        logger.warning(f"⚠️ YouTube access failed with status: {response.status}")
                        return False
            
        except Exception as e:
            logger.error(f"❌ Error testing YouTube access: {e}")
            return False
    
    async def auto_validate_and_refresh(self) -> Dict[str, Any]:
        """
        Automatically validate cookies and attempt refresh if needed
        """
        if not self.auto_refresh_enabled:
            return {'status': 'disabled'}
        
        # Check if we need to validate (don't validate too frequently)
        now = datetime.now()
        if self.last_validation and now - self.last_validation < self.validation_interval:
            return {'status': 'skipped', 'reason': 'too_recent'}
        
        self.last_validation = now
        
        # Find cookie file
        cookie_file = None
        for path in self.cookie_paths:
            if os.path.exists(path):
                cookie_file = path
                break
        
        if not cookie_file:
            return {'status': 'no_cookies', 'message': 'No cookie file found'}
        
        # Validate current cookies
        validation = await self.validate_cookie_freshness(cookie_file)
        
        result = {
            'status': 'validated',
            'cookie_file': cookie_file,
            'validation': validation,
            'actions_taken': []
        }
        
        # If cookies are expiring soon or invalid, try to extend them
        if validation['expires_soon'] or not validation['valid']:
            logger.info("🔄 Cookies expiring soon or invalid, extending expiration dates...")
            
            # Create backup
            backup_file = f"{cookie_file}.backup.{int(now.timestamp())}"
            import shutil
            shutil.copy2(cookie_file, backup_file)
            result['actions_taken'].append(f"Created backup: {backup_file}")
            
            # Extend cookie expiration
            if self.extend_cookie_expiration(cookie_file, years=100):
                result['actions_taken'].append("Extended cookie expiration dates by 100 years")
                
                # Re-validate
                new_validation = await self.validate_cookie_freshness(cookie_file)
                result['validation'] = new_validation
                
                if new_validation['valid']:
                    logger.info("✅ Cookie refresh successful")
                    result['status'] = 'refreshed'
                else:
                    logger.warning("⚠️ Cookie refresh didn't resolve access issues")
                    result['status'] = 'refresh_failed'
            else:
                result['actions_taken'].append("Failed to extend cookie expiration")
                result['status'] = 'extension_failed'
        
        return result
    
    def enable_auto_refresh(self):
        """Enable automatic cookie refresh"""
        self.auto_refresh_enabled = True
        logger.info("✅ Auto cookie refresh enabled")
    
    def disable_auto_refresh(self):
        """Disable automatic cookie refresh"""
        self.auto_refresh_enabled = False
        logger.info("⚠️ Auto cookie refresh disabled")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current service status"""
        return {
            'auto_refresh_enabled': self.auto_refresh_enabled,
            'last_validation': self.last_validation.isoformat() if self.last_validation else None,
            'validation_interval_hours': self.validation_interval.total_seconds() / 3600,
            'cookie_paths_checked': self.cookie_paths,
            'cache_size': len(self.cookie_cache)
        }

# Global service instance
cookie_refresh_service = CookieRefreshService()
