#!/usr/bin/env python3
"""
YouTube Proxy Service
Advanced proxy rotation and unblocking service for YouTube downloads
"""

import os
import random
import requests
import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class ProxyConfig:
    """Configuration for a proxy server"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = 'http'  # http, https, socks4, socks5
    country: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None
    avg_response_time: float = 0.0
    is_blocked: bool = False
    blocked_until: Optional[datetime] = None

    def __post_init__(self):
        if self.last_used is None:
            self.last_used = datetime.now() - timedelta(hours=1)
            
    @property
    def url(self) -> str:
        """Get proxy URL for requests"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    @property
    def is_available(self) -> bool:
        """Check if proxy is available for use"""
        if self.is_blocked and self.blocked_until:
            if datetime.now() < self.blocked_until:
                return False
            else:
                # Unblock expired blocks
                self.is_blocked = False
                self.blocked_until = None
        return True

class YouTubeProxyService:
    """Advanced proxy service for YouTube unblocking"""
    
    def __init__(self):
        self.proxies: List[ProxyConfig] = []
        self.current_proxy_index = 0
        self.test_url = "https://httpbin.org/ip"  # For testing proxy functionality
        self.youtube_test_urls = [
            "https://www.youtube.com/robots.txt",
            "https://www.googleapis.com/youtube/v3/videos?part=snippet&id=dQw4w9WgXcQ&key=fake"
        ]
        self._load_proxies_from_config()
        logger.info(f"YouTubeProxyService initialized with {len(self.proxies)} proxies")
    
    def _load_proxies_from_config(self):
        """Load proxy configurations from environment and config files"""
        
        # Load from environment variable
        proxy_list_env = os.getenv('YOUTUBE_PROXIES', '')
        if proxy_list_env:
            for proxy_str in proxy_list_env.split(','):
                proxy_str = proxy_str.strip()
                if proxy_str:
                    try:
                        proxy_config = self._parse_proxy_string(proxy_str)
                        if proxy_config:
                            self.proxies.append(proxy_config)
                    except Exception as e:
                        logger.warning(f"Failed to parse proxy '{proxy_str}': {e}")
        
        # Load from proxy config file
        proxy_files = [
            'proxies.txt',
            'config/proxies.txt', 
            '/etc/topclip/proxies.txt',
            os.path.expanduser('~/proxies.txt')
        ]
        
        for proxy_file in proxy_files:
            if os.path.exists(proxy_file):
                try:
                    with open(proxy_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                try:
                                    proxy_config = self._parse_proxy_string(line)
                                    if proxy_config:
                                        self.proxies.append(proxy_config)
                                except Exception as e:
                                    logger.warning(f"Failed to parse proxy from file '{line}': {e}")
                    logger.info(f"Loaded proxies from {proxy_file}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to read proxy file {proxy_file}: {e}")
        
        # If no proxies configured, don't add invalid fallback proxies
        if not self.proxies:
            logger.info("No proxies configured. Using direct connection (no proxy)")
            # Don't add any fallback proxies that might cause connection errors
    
    def _parse_proxy_string(self, proxy_str: str) -> Optional[ProxyConfig]:
        """Parse proxy string into ProxyConfig"""
        try:
            # Format: protocol://[username:password@]host:port
            # Examples: 
            # http://proxy.example.com:8080
            # http://user:pass@proxy.example.com:8080
            # socks5://user:pass@proxy.example.com:1080
            
            if '://' not in proxy_str:
                # Default to http if no protocol specified
                proxy_str = f"http://{proxy_str}"
            
            protocol = proxy_str.split('://')[0]
            remainder = proxy_str.split('://')[1]
            
            username = None
            password = None
            
            if '@' in remainder:
                auth_part, remainder = remainder.split('@', 1)
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                else:
                    username = auth_part
            
            if ':' in remainder:
                host, port_str = remainder.rsplit(':', 1)
                port = int(port_str)
            else:
                host = remainder
                port = 8080 if protocol.startswith('http') else 1080
            
            return ProxyConfig(
                host=host,
                port=port,
                username=username,
                password=password,
                protocol=protocol
            )
            
        except Exception as e:
            logger.error(f"Error parsing proxy string '{proxy_str}': {e}")
            return None
    
    def get_best_proxy(self) -> Optional[ProxyConfig]:
        """Get the best available proxy based on success rate and recent usage"""
        available_proxies = [p for p in self.proxies if p.is_available]
        
        if not available_proxies:
            logger.warning("No available proxies found")
            return None
        
        # Sort by success rate and least recently used
        def proxy_score(proxy: ProxyConfig) -> float:
            """Calculate proxy score (higher is better)"""
            # Base score from success rate
            score = proxy.success_rate
            
            # Bonus for recent success
            if proxy.last_success:
                hours_since_success = (datetime.now() - proxy.last_success).total_seconds() / 3600
                score += max(0, 1.0 - hours_since_success / 24)  # Bonus fades over 24 hours
            
            # Penalty for recent usage (encourage rotation)
            hours_since_use = (datetime.now() - proxy.last_used).total_seconds() / 3600
            score += min(1.0, hours_since_use / 2)  # Bonus for not being used recently
            
            # Penalty for slow response times
            if proxy.avg_response_time > 0:
                score -= min(1.0, proxy.avg_response_time / 10)  # Penalty for slow proxies
            
            return score
        
        # Select proxy with highest score
        best_proxy = max(available_proxies, key=proxy_score)
        best_proxy.last_used = datetime.now()
        
        logger.debug(f"Selected proxy {best_proxy.host}:{best_proxy.port} (score: {proxy_score(best_proxy):.2f})")
        return best_proxy
    
    async def test_proxy(self, proxy: ProxyConfig, test_youtube: bool = True) -> Dict[str, Any]:
        """Test proxy functionality and return results"""
        results = {
            'proxy': f"{proxy.host}:{proxy.port}",
            'working': False,
            'response_time': None,
            'youtube_accessible': False,
            'error': None,
            'ip_address': None
        }
        
        try:
            proxies = {'http': proxy.url, 'https': proxy.url}
            start_time = datetime.now()
            
            # Test basic connectivity
            response = requests.get(
                self.test_url, 
                proxies=proxies, 
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
            )
            
            response_time = (datetime.now() - start_time).total_seconds()
            results['response_time'] = response_time
            
            if response.status_code == 200:
                results['working'] = True
                data = response.json()
                results['ip_address'] = data.get('origin', 'Unknown')
                
                # Update proxy stats
                proxy.success_count += 1
                proxy.last_success = datetime.now()
                proxy.avg_response_time = (proxy.avg_response_time + response_time) / 2
                
                # Test YouTube accessibility if requested
                if test_youtube:
                    try:
                        youtube_response = requests.get(
                            self.youtube_test_urls[0],
                            proxies=proxies,
                            timeout=15,
                            headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
                        )
                        if youtube_response.status_code == 200:
                            results['youtube_accessible'] = True
                            logger.info(f"✅ Proxy {proxy.host}:{proxy.port} can access YouTube")
                        else:
                            logger.warning(f"⚠️ Proxy {proxy.host}:{proxy.port} blocked from YouTube")
                    except Exception as yt_error:
                        logger.warning(f"YouTube test failed for {proxy.host}:{proxy.port}: {yt_error}")
                        results['youtube_accessible'] = False
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            results['error'] = str(e)
            proxy.failure_count += 1
            
            # Check if this looks like a permanent block
            error_str = str(e).lower()
            if any(block_indicator in error_str for block_indicator in [
                'forbidden', '403', 'blocked', 'denied', 'unauthorized'
            ]):
                proxy.is_blocked = True
                proxy.blocked_until = datetime.now() + timedelta(hours=2)
                logger.warning(f"Proxy {proxy.host}:{proxy.port} appears blocked, disabling for 2 hours")
        
        return results
    
    async def test_all_proxies(self) -> List[Dict[str, Any]]:
        """Test all configured proxies"""
        if not self.proxies:
            logger.warning("No proxies configured for testing")
            return []
        
        logger.info(f"Testing {len(self.proxies)} proxies...")
        results = []
        
        # Test proxies in parallel (but with reasonable concurrency limit)
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent tests
        
        async def test_single_proxy(proxy: ProxyConfig):
            async with semaphore:
                return await self.test_proxy(proxy, test_youtube=True)
        
        tasks = [test_single_proxy(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log summary
        valid_results = [r for r in results if isinstance(r, dict)]
        working_proxies = [r for r in valid_results if r['working']]
        youtube_proxies = [r for r in valid_results if r.get('youtube_accessible')]
        
        logger.info(f"Proxy test results: {len(working_proxies)}/{len(self.proxies)} working, "
                   f"{len(youtube_proxies)} can access YouTube")
        
        return valid_results
    
    def get_proxy_for_ytdlp(self) -> Optional[str]:
        """Get proxy URL formatted for yt-dlp"""
        proxy = self.get_best_proxy()
        if proxy:
            return proxy.url
        return None
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """Get proxy dictionary for requests library"""
        proxy = self.get_best_proxy()
        if proxy:
            return {
                'http': proxy.url,
                'https': proxy.url
            }
        return None
    
    def mark_proxy_failed(self, proxy_url: str, error: str = ""):
        """Mark a proxy as failed"""
        for proxy in self.proxies:
            if proxy.url == proxy_url or f"{proxy.host}:{proxy.port}" in proxy_url:
                proxy.failure_count += 1
                
                # Check if this looks like YouTube blocking
                error_str = error.lower()
                if any(block_indicator in error_str for block_indicator in [
                    'sign in', 'bot', 'unavailable', '429', 'too many requests'
                ]):
                    proxy.is_blocked = True
                    proxy.blocked_until = datetime.now() + timedelta(hours=1)
                    logger.warning(f"Proxy {proxy.host}:{proxy.port} blocked by YouTube for 1 hour")
                break
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get proxy service statistics"""
        total_proxies = len(self.proxies)
        available_proxies = len([p for p in self.proxies if p.is_available])
        working_proxies = len([p for p in self.proxies if p.success_count > 0])
        blocked_proxies = len([p for p in self.proxies if p.is_blocked])
        
        avg_success_rate = 0
        if self.proxies:
            avg_success_rate = sum(p.success_rate for p in self.proxies) / len(self.proxies)
        
        return {
            'total_proxies': total_proxies,
            'available_proxies': available_proxies,
            'working_proxies': working_proxies,
            'blocked_proxies': blocked_proxies,
            'average_success_rate': avg_success_rate
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Alias for get_statistics for backward compatibility"""
        return self.get_statistics()

# Global proxy service instance
proxy_service = YouTubeProxyService()
