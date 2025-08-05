import yt_dlp
import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import random
import time
from .cookie_manager import cookie_manager

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    def __init__(self):
        self.proxies = self._get_proxy_list()
        logger.info(f"YouTube downloader initialized with {len(self.proxies)} proxies")
    
    def _get_random_user_agent(self):
        """Get a random user agent to avoid detection"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        return random.choice(user_agents)
    
    def _get_proxy_list(self):
        """Get list of proxies from environment variable"""
        proxy_env = os.getenv('YOUTUBE_PROXIES', '')
        if proxy_env:
            return proxy_env.split(',')
        return []
        
    def _get_random_proxy(self):
        """Get a random proxy"""
        if self.proxies:
            return random.choice(self.proxies)
        return None
    
    def _validate_cookies_file(self, cookies_path: str) -> bool:
        """Validate that cookies file is in proper Netscape format"""
        try:
            with open(cookies_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                
            # Check if file has proper header
            if not lines or not lines[0].startswith('# Netscape HTTP Cookie File'):
                logger.warning("Cookies file missing Netscape header")
                return False
            
            # Validate cookie lines (skip comments and empty lines)
            valid_cookies = 0
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Check if line has correct number of tab-separated fields
                fields = line.split('\t')
                if len(fields) != 7:
                    logger.warning(f"Invalid cookie format at line {line_num}: expected 7 fields, got {len(fields)}")
                    continue
                    
                # Basic validation of required fields
                domain, domain_specified, path, secure, expiration, name, value = fields
                if not domain or not name:
                    logger.warning(f"Invalid cookie at line {line_num}: missing domain or name")
                    continue
                    
                valid_cookies += 1
            
            if valid_cookies == 0:
                logger.warning("No valid cookies found in file")
                return False
                
            logger.info(f"Cookies file validation passed: {valid_cookies} valid cookies found")
            return True
            
        except Exception as e:
            logger.error(f"Error validating cookies file: {str(e)}")
            return False
    
    def _setup_cookies(self, opts: dict) -> dict:
        """Setup cookies for yt-dlp options - used by all methods"""
        try:
            # Try to find cookies file in current directory
            cookies_path = os.path.join(os.getcwd(), 'youtube_cookies.txt')
            if os.path.exists(cookies_path):
                # Validate cookies file before using it
                if self._validate_cookies_file(cookies_path):
                    opts['cookiefile'] = cookies_path
                    logger.info("✅ Using YouTube cookies file from current directory")
                    return opts
                else:
                    logger.warning("⚠️ Cookies file exists but is invalid, proceeding without cookies")
            
            # Try alternative cookie file locations (Linux/Ubuntu paths)
            alternative_paths = [
                os.path.expanduser('~/youtube_cookies.txt'),
                '/home/ubuntu/youtube_cookies.txt',
                '/var/www/youtube_cookies.txt',
                '/opt/app/youtube_cookies.txt',
                '/app/youtube_cookies.txt',
                '/tmp/youtube_cookies.txt',
                'cookies/youtube_cookies.txt',
                'config/youtube_cookies.txt'
            ]
            
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    opts['cookiefile'] = alt_path
                    logger.info(f"✅ Using YouTube cookies file from: {alt_path}")
                    return opts
            
            # Try cookies from environment variable
            if os.getenv('YOUTUBE_COOKIES'):
                cookies_content = os.getenv('YOUTUBE_COOKIES')
                temp_cookies_path = '/tmp/youtube_cookies_temp.txt'
                with open(temp_cookies_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                opts['cookiefile'] = temp_cookies_path
                logger.info("✅ Using YouTube cookies from environment variable")
                return opts
            
            # Enhanced options for no-cookies scenario
            logger.warning("⚠️ No YouTube cookies found - using enhanced anti-bot strategies")
            
            # Add enhanced headers and options for better success without cookies
            opts.update({
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Accept-Encoding': 'gzip,deflate',
                    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                },
                'sleep_interval': 2,
                'max_sleep_interval': 5,
                'socket_timeout': 30,
                'retries': 5,
            })
            
            return opts
            
        except Exception as e:
            logger.error(f"❌ Error setting up cookies: {str(e)}")
            return opts
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading with improved strategies"""
        try:
            if not self.is_valid_youtube_url(url):
                raise Exception("Invalid YouTube URL format")
            
            # Check and refresh cookies if needed (runs in background)
            try:
                await cookie_manager.auto_refresh_cookies()
            except Exception as cookie_error:
                logger.warning(f"Cookie auto-refresh failed: {cookie_error}")
            
            def _get_info():
                # Try multiple strategies with improved configurations for server environments
                strategies = [
                    ('mweb', self._get_mweb_opts),  # Mobile web - often bypasses bot detection
                    ('android_embedded', self._get_android_embedded_opts),
                    ('android_testsuite', self._get_android_testsuite_opts),
                    ('tv_embedded', self._get_tv_embedded_opts),
                    ('web_embedded', self._get_web_embedded_opts),
                    ('ios_music', self._get_ios_music_opts),
                    ('web_safari', self._get_web_safari_opts),  # Safari user agent
                    ('android_creator', self._get_android_creator_opts)  # Creator Studio app
                ]
                
                for i, (client_name, opts_func) in enumerate(strategies):
                    try:
                        logger.info(f"Trying YouTube extraction with {client_name} client (attempt {i+1})")
                        
                        ydl_opts = opts_func()
                        
                        # Setup cookies for video info extraction
                        ydl_opts = self._setup_cookies(ydl_opts)
                        
                        # Add proxy if available (fallback)
                        proxy = self._get_random_proxy()
                        if proxy:
                            ydl_opts['proxy'] = proxy
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            # Add exponential backoff
                            time.sleep(random.uniform(0.5 + i * 0.5, 1.5 + i * 0.5))
                            info = ydl.extract_info(url, download=False)
                            
                            if not info:
                                raise Exception("No video information found")
                            
                            # Success! Return formatted info
                            return {
                                'title': info.get('title', 'Unknown Title'),
                                'duration': info.get('duration', 0),
                                'views': info.get('view_count'),
                                'author': info.get('uploader', 'Unknown Author'),
                                'description': info.get('description', ''),
                                'thumbnail_url': info.get('thumbnail'),
                                'upload_date': info.get('upload_date'),
                                'video_id': info.get('id'),
                                'webpage_url': info.get('webpage_url')
                            }
                            
                    except Exception as e:
                        error_msg = str(e).lower()
                        logger.warning(f"{client_name} client failed: {str(e)[:100]}...")
                        
                        # If this is the last strategy, try fallback
                        if i == len(strategies) - 1:
                            logger.info("All strategies failed, trying fallback method...")
                            return self._get_fallback_info(url)
                        
                        # Continue to next strategy
                        time.sleep(random.uniform(1.0, 2.0))
                        continue
                
                # If we get here, all strategies failed
                raise Exception("All YouTube extraction strategies failed")
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _get_info)
            
            logger.info(f"Successfully got video info for: {info['title']}")
            return info
            
        except Exception as e:
            logger.error(f"Error getting video info for URL {url}: {str(e)}")
            raise Exception(f"Failed to get video information: {str(e)}")
    
    async def download_video(self, url: str, job_id: str) -> str:
        """Download video from YouTube URL with multiple strategies"""
        strategy_results = []  # Track results for user feedback
        
        try:
            # Get video info first
            info = await self.get_video_info(url)
            video_id = info.get('video_id', 'unknown')
            
            # Try multiple download strategies with timeout protection
            strategies = [
                ('Simple Download', self._download_simple, 'Basic download with cookies - usually fastest'),
                ('Android Client', self._download_android_client, 'Android app simulation - good for restricted videos'), 
                ('Web Client', self._download_web_client, 'Web browser simulation - reliable fallback'),
                ('Updated Method', self._download_updated_method, 'Latest yt-dlp settings - handles new restrictions'),
                ('Cookies Method', self._download_cookies_method, 'Enhanced cookies approach - bypasses bot detection'),
                ('No Cookies', self._download_no_cookies, 'Final fallback without authentication - last resort')
            ]
            
            for i, (strategy_name, strategy_func, description) in enumerate(strategies):
                start_time = time.time()
                try:
                    logger.info(f"🔄 Trying strategy {i+1}/{len(strategies)}: {strategy_name}")
                    logger.info(f"📝 Strategy info: {description}")
                    
                    # Add timeout protection for each strategy
                    result = await asyncio.wait_for(
                        strategy_func(url, job_id, video_id),
                        timeout=300  # 5 minute timeout per strategy
                    )
                    
                    elapsed_time = time.time() - start_time
                    
                    if result and os.path.exists(result):
                        file_size = os.path.getsize(result) / (1024 * 1024)  # MB
                        success_info = {
                            'strategy': strategy_name,
                            'description': description,
                            'status': 'SUCCESS',
                            'time_taken': f"{elapsed_time:.1f}s",
                            'file_size': f"{file_size:.1f}MB",
                            'message': f"✅ Successfully downloaded using {strategy_name}"
                        }
                        strategy_results.append(success_info)
                        
                        logger.info(f"✅ Download successful with {strategy_name} in {elapsed_time:.1f}s ({file_size:.1f}MB)")
                        
                        # Log all strategy results for user feedback
                        self._log_strategy_results(job_id, strategy_results)
                        return result
                        
                except asyncio.TimeoutError:
                    elapsed_time = time.time() - start_time
                    failure_info = {
                        'strategy': strategy_name,
                        'description': description,
                        'status': 'TIMEOUT',
                        'time_taken': f"{elapsed_time:.1f}s",
                        'message': f"⏱️ {strategy_name} timed out after 5 minutes"
                    }
                    strategy_results.append(failure_info)
                    logger.warning(f"⏱️ Strategy {strategy_name} timed out after 5 minutes")
                    continue
                    
                except Exception as strategy_error:
                    elapsed_time = time.time() - start_time
                    error_msg = str(strategy_error)[:100]  # Truncate long errors
                    failure_info = {
                        'strategy': strategy_name,
                        'description': description,
                        'status': 'FAILED',
                        'time_taken': f"{elapsed_time:.1f}s",
                        'error': error_msg,
                        'message': f"❌ {strategy_name} failed: {error_msg}"
                    }
                    strategy_results.append(failure_info)
                    logger.warning(f"❌ Strategy {strategy_name} failed: {error_msg}")
                    
                    # Add delay between strategies to avoid rate limiting
                    if i < len(strategies) - 1:  # Don't delay after last strategy
                        await asyncio.sleep(random.uniform(2, 5))
                    continue
            
            # All strategies failed - log results for debugging
            self._log_strategy_results(job_id, strategy_results)
            
            # Create detailed failure message
            failed_strategies = [r['strategy'] for r in strategy_results if r['status'] != 'SUCCESS']
            raise Exception(f"All {len(strategies)} download strategies failed: {', '.join(failed_strategies)}")
            
        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            # Log strategy results even on failure
            if strategy_results:
                self._log_strategy_results(job_id, strategy_results)
            raise Exception(f"Failed to download video: {str(e)}")
    
    async def _download_simple(self, url: str, job_id: str, video_id: str) -> Optional[str]:
        """Simple download with cookies - often works best"""
        try:
            def _download():
                opts = {
                    'format': 'worst[height<=480]/worst',
                    'outtmpl': f'temp/{job_id}_{video_id}_simple.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                    'postprocessor_args': [
                        '-t', '2400',  # Limit to first 40 minutes (2400 seconds)
                    ],
                    'socket_timeout': 60,  # Increase socket timeout
                    'retries': 3,  # Retry failed downloads
                }
                
                # Add cookies to this method
                opts = self._setup_cookies(opts)
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    time.sleep(random.uniform(0.5, 1.5))
                    ydl.download([url])
                    
                    # Find downloaded file
                    for ext in ['mp4', 'webm', 'mkv']:
                        file_path = f'temp/{job_id}_{video_id}_simple.{ext}'
                        if os.path.exists(file_path):
                            return file_path
                    
                    return None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _download)
            
        except Exception as e:
            logger.error(f"Simple download failed: {str(e)}")
            return None
    
    async def _download_android_client(self, url: str, job_id: str, video_id: str) -> Optional[str]:
        """Android client download with cookies"""
        try:
            def _download():
                opts = {
                    'format': 'worst[height<=360]/worst',
                    'outtmpl': f'temp/{job_id}_{video_id}_android.%(ext)s',
                    'quiet': True,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android'],
                            'skip': ['hls', 'dash'],
                        }
                    },
                    'http_headers': {
                        'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 11) gzip'
                    },
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                    'postprocessor_args': [
                        '-t', '2400',  # Limit to first 40 minutes (2400 seconds)
                    ],
                    'socket_timeout': 60,  # Increase socket timeout
                    'retries': 3,  # Retry failed downloads
                }
                
                # Add cookies to this method
                opts = self._setup_cookies(opts)
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    time.sleep(random.uniform(1, 2))
                    ydl.download([url])
                    
                    # Find downloaded file
                    for ext in ['mp4', 'webm', 'mkv']:
                        file_path = f'temp/{job_id}_{video_id}_android.{ext}'
                        if os.path.exists(file_path):
                            return file_path
                    
                    return None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _download)
            
        except Exception as e:
            logger.error(f"Android client download failed: {str(e)}")
            return None
    
    async def _download_web_client(self, url: str, job_id: str, video_id: str) -> Optional[str]:
        """Web client download with cookies"""
        try:
            def _download():
                opts = {
                    'format': 'worst[height<=480]/worst',
                    'outtmpl': f'temp/{job_id}_{video_id}_web.%(ext)s',
                    'quiet': True,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['web'],
                        }
                    },
                    'http_headers': {
                        'User-Agent': self._get_random_user_agent()
                    },
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                    'postprocessor_args': [
                        '-t', '2400',  # Limit to first 40 minutes (2400 seconds)
                    ],
                }
                
                # Add cookies to this method
                opts = self._setup_cookies(opts)
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    time.sleep(random.uniform(1, 2))
                    ydl.download([url])
                    
                    # Find downloaded file
                    for ext in ['mp4', 'webm', 'mkv']:
                        file_path = f'temp/{job_id}_{video_id}_web.{ext}'
                        if os.path.exists(file_path):
                            return file_path
                    
                    return None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _download)
            
        except Exception as e:
            logger.error(f"Web client download failed: {str(e)}")
            return None
    
    async def _download_updated_method(self, url: str, job_id: str, video_id: str) -> Optional[str]:
        """Try with updated yt-dlp settings and cookies"""
        try:
            def _download():
                opts = {
                    'format': 'worstvideo[height<=360]+worstaudio/worst[height<=360]/worst',
                    'outtmpl': f'temp/{job_id}_{video_id}_updated.%(ext)s',
                    'quiet': True,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web'],
                            'skip': ['hls', 'dash', 'live_chat'],
                        }
                    },
                    'http_headers': {
                        'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 11) gzip'
                    },
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                    'postprocessor_args': [
                        '-t', '2400',  # Limit to first 40 minutes (2400 seconds)
                    ],
                }
                
                # Add cookies to this method
                opts = self._setup_cookies(opts)
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    time.sleep(random.uniform(2, 4))
                    ydl.download([url])
                    
                    # Find downloaded file
                    for ext in ['mp4', 'webm', 'mkv']:
                        file_path = f'temp/{job_id}_{video_id}_updated.{ext}'
                        if os.path.exists(file_path):
                            return file_path
                    
                    return None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _download)
            
        except Exception as e:
            logger.error(f"Updated method download failed: {str(e)}")
            return None
    
    async def _download_cookies_method(self, url: str, job_id: str, video_id: str) -> Optional[str]:
        """Download using enhanced cookies method with robust settings"""
        try:
            def _download():
                opts = {
                    'format': 'worst[height<=360]/worst[ext=mp4]',
                    'outtmpl': f'temp/{job_id}_{video_id}_cookies.%(ext)s',
                    'quiet': True,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android_embedded', 'android', 'web'],
                            'skip': ['hls', 'dash'],
                        }
                    },
                    'http_headers': {
                        'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 11) gzip',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                    },
                    'sleep_interval': 2,
                    'max_sleep_interval': 5,
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                    'postprocessor_args': [
                        '-t', '2400',  # Limit to first 40 minutes (2400 seconds)
                    ],
                }
                
                # Add cookies to this method (now it actually uses cookies!)
                opts = self._setup_cookies(opts)
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    time.sleep(random.uniform(2, 4))
                    ydl.download([url])
                    
                    # Find downloaded file
                    for ext in ['mp4', 'webm', 'mkv']:
                        file_path = f'temp/{job_id}_{video_id}_cookies.{ext}'
                        if os.path.exists(file_path):
                            return file_path
                    
                    return None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _download)
            
        except Exception as e:
            logger.error(f"Cookies method download failed: {str(e)}")
            return None
    
    async def _download_no_cookies(self, url: str, job_id: str, video_id: str) -> Optional[str]:
        """Final fallback: download without any cookies at all"""
        try:
            def _download():
                opts = {
                    'format': 'worst[height<=480]/worst',
                    'outtmpl': f'temp/{job_id}_{video_id}_nocookies.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android_embedded', 'web'],
                            'skip': ['hls', 'dash'],
                        }
                    },
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-us,en;q=0.5',
                        'Accept-Encoding': 'gzip,deflate',
                        'Connection': 'keep-alive',
                    },
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                    'postprocessor_args': [
                        '-t', '2400',  # Limit to first 40 minutes (2400 seconds)
                    ],
                    'socket_timeout': 30,
                    'retries': 5,
                    'sleep_interval': 3,
                    'max_sleep_interval': 8,
                    # Explicitly do NOT add cookies to this method
                }
                
                logger.info("Attempting final fallback download without cookies")
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    time.sleep(random.uniform(3, 6))  # Longer delay for final attempt
                    ydl.download([url])
                    
                    # Find downloaded file
                    for ext in ['mp4', 'webm', 'mkv']:
                        file_path = f'temp/{job_id}_{video_id}_nocookies.{ext}'
                        if os.path.exists(file_path):
                            return file_path
                    
                    return None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _download)
            
        except Exception as e:
            logger.error(f"No-cookies download failed: {str(e)}")
            return None
    
    def _get_android_embedded_opts(self):
        """Get options for android_embedded client - often works best"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'user_agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 11) gzip',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_embedded'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 11) gzip',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        }
    
    def _get_tv_embedded_opts(self):
        """Get options for tv_embedded client"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        }
    
    def _get_web_embedded_opts(self):
        """Get options for web_embedded client"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web_embedded'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': self._get_random_user_agent(),
                'Accept-Language': 'en-US,en;q=0.9',
            },
        }
    
    def _get_android_testsuite_opts(self):
        """Get options for android_testsuite client"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_testsuite'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 11) gzip',
            },
        }
    
    def _get_ios_music_opts(self):
        """Get options for ios_music client"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios_music'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.ios.youtubemusic/4.32.1 (iPhone12,1; U; CPU OS 14_6 like Mac OS X)',
            },
        }
    
    def _get_mweb_opts(self):
        """Get options for mweb (mobile web) client - often bypasses bot detection"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        }
    
    def _get_web_safari_opts(self):
        """Get options for Safari web client"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        }
    
    def _get_android_creator_opts(self):
        """Get options for Android Creator Studio client"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_creator'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.apps.youtube.creator/22.43.101 (Linux; U; Android 11) gzip',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        }
    
    def _get_fallback_info(self, url: str) -> Dict[str, Any]:
        """Fallback method to get basic video info when all else fails"""
        try:
            import re
            # Extract video ID from URL
            video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
            if not video_id_match:
                raise Exception("Could not extract video ID from URL")
            
            video_id = video_id_match.group(1)
            
            # Return minimal info that allows processing to continue
            logger.warning(f"Using fallback video info for {video_id}")
            return {
                'title': f'Video {video_id}',
                'duration': 300,  # 5 minutes default
                'views': None,
                'author': 'Unknown Author',
                'description': 'Video information could not be retrieved due to YouTube restrictions.',
                'thumbnail_url': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
                'upload_date': None,
                'video_id': video_id,
                'webpage_url': url,
                'fallback': True
            }
        except Exception as fallback_error:
            logger.error(f"Fallback info extraction also failed: {str(fallback_error)}")
            raise Exception("Unable to extract any video information")
    
    def _log_strategy_results(self, job_id: str, strategy_results: List[Dict[str, Any]]):
        """Log strategy results for user feedback and debugging"""
        try:
            logger.info(f"📊 Strategy Results Summary for Job {job_id}:")
            
            for i, result in enumerate(strategy_results, 1):
                status_emoji = {
                    'SUCCESS': '✅',
                    'FAILED': '❌', 
                    'TIMEOUT': '⏱️'
                }.get(result['status'], '❓')
                
                logger.info(f"  {i}. {status_emoji} {result['strategy']} ({result['time_taken']})")
                if result['status'] == 'SUCCESS':
                    logger.info(f"     File size: {result.get('file_size', 'Unknown')}")
                elif result['status'] == 'FAILED':
                    logger.info(f"     Error: {result.get('error', 'Unknown error')}")
                logger.info(f"     Description: {result['description']}")
                
            # Performance summary
            success_count = len([r for r in strategy_results if r['status'] == 'SUCCESS'])
            failure_count = len([r for r in strategy_results if r['status'] == 'FAILED'])
            timeout_count = len([r for r in strategy_results if r['status'] == 'TIMEOUT'])
            
            logger.info(f"📈 Performance Summary: ✅{success_count} ❌{failure_count} ⏱️{timeout_count}")
            
            # Store results for potential user display (could be extended to database)
            if not hasattr(self, 'strategy_logs'):
                self.strategy_logs = {}
            self.strategy_logs[job_id] = {
                'timestamp': datetime.now().isoformat(),
                'results': strategy_results,
                'summary': {
                    'success': success_count,
                    'failed': failure_count,
                    'timeout': timeout_count,
                    'total': len(strategy_results)
                }
            }
            
        except Exception as e:
            logger.error(f"Error logging strategy results: {str(e)}")
    
    def get_strategy_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get strategy results for a specific job (for debugging/analysis)"""
        if not hasattr(self, 'strategy_logs'):
            return None
        return self.strategy_logs.get(job_id)
    
    def is_valid_youtube_url(self, url: str) -> bool:
        """Validate if URL is a valid YouTube URL"""
        import re
        
        youtube_patterns = [
            r'(https?://)?(www\.)?(youtube\.com/watch\?v=)[\w-]+',
            r'(https?://)?(www\.)?(youtube\.com/embed/)[\w-]+',
            r'(https?://)?(www\.)?(youtube\.com/shorts/)[\w-]+',
            r'(https?://)?(www\.)?(youtu\.be/)[\w-]+',
            r'(https?://)?(m\.)?(youtube\.com/watch\?v=)[\w-]+',
        ]
        
        for pattern in youtube_patterns:
            if re.match(pattern, url):
                return True
        
        return False
    
    async def get_video_duration(self, url: str) -> int:
        """Get video duration in seconds"""
        try:
            info = await self.get_video_info(url)
            return info.get('duration', 0)
        except Exception as e:
            logger.error(f"Error getting video duration: {str(e)}")
            return 0