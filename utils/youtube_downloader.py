import yt_dlp
import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import random
import time

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
    
    def _setup_cookies(self, opts: dict) -> dict:
        """Setup cookies for yt-dlp options - used by all methods"""
        try:
            # Try to find cookies file in current directory
            cookies_path = os.path.join(os.getcwd(), 'youtube_cookies.txt')
            if os.path.exists(cookies_path):
                opts['cookiefile'] = cookies_path
                logger.info("✅ Using YouTube cookies file from current directory")
                return opts
            
            # Try alternative cookie file locations
            alternative_paths = [
                os.path.expanduser('~/youtube_cookies.txt'),
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
                with open(temp_cookies_path, 'w') as f:
                    f.write(cookies_content)
                opts['cookiefile'] = temp_cookies_path
                logger.info("✅ Using YouTube cookies from environment variable")
                return opts
            
            # No cookies found
            logger.warning("⚠️ No YouTube cookies found - downloads may fail for restricted videos")
            return opts
            
        except Exception as e:
            logger.error(f"❌ Error setting up cookies: {str(e)}")
            return opts
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading"""
        try:
            if not self.is_valid_youtube_url(url):
                raise Exception("Invalid YouTube URL format")
            
            def _get_info():
                # Try with different strategies if blocked
                strategies = ['mweb', 'android', 'ios', 'web']
                
                for i, client in enumerate(strategies):
                    try:
                        logger.info(f"Trying YouTube extraction with {client} client (attempt {i+1})")
                        
                        # Try basic extraction first
                        ydl_opts = {
                            'quiet': True,
                            'no_warnings': True,
                            'extract_flat': False,
                            'ignoreerrors': False,
                            'user_agent': self._get_random_user_agent(),
                            'extractor_args': {
                                'youtube': {
                                    'player_client': [client],  # Try one client at a time
                                    'skip': ['hls', 'dash'],
                                }
                            },
                            'http_headers': {
                                'User-Agent': self._get_random_user_agent(),
                                'Accept-Language': 'en-US,en;q=0.9',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            },
                            'sleep_interval': 1.0 + i,  # Increase delay with each retry
                            'sleep_interval_subtitles': 2.0,
                        }
                        
                        # Setup cookies for video info extraction
                        ydl_opts = self._setup_cookies(ydl_opts)
                        
                        # Add proxy if available (fallback)
                        proxy = self._get_random_proxy()
                        if proxy:
                            ydl_opts['proxy'] = proxy
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            time.sleep(random.uniform(1.0 + i, 3.0 + i))  # Exponential backoff
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
                        if i == len(strategies) - 1:  # Last attempt
                            raise e
                        elif 'sign in' in error_msg or 'bot' in error_msg:
                            logger.warning(f"{client} client failed: {e}. Trying next client...")
                            time.sleep(random.uniform(2.0, 5.0))  # Wait before retry
                            continue
                        else:
                            raise e
                
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
        try:
            # Get video info first
            info = await self.get_video_info(url)
            video_id = info.get('video_id', 'unknown')
            
            # Try multiple download strategies with timeout protection
            strategies = [
                ('simple', self._download_simple),
                ('android_client', self._download_android_client), 
                ('web_client', self._download_web_client),
                ('updated_method', self._download_updated_method),
                ('cookies_method', self._download_cookies_method)
            ]
            
            for i, (strategy_name, strategy_func) in enumerate(strategies):
                try:
                    logger.info(f"Trying download strategy {i+1}/{len(strategies)}: {strategy_name}")
                    
                    # Add timeout protection for each strategy
                    result = await asyncio.wait_for(
                        strategy_func(url, job_id, video_id),
                        timeout=300  # 5 minute timeout per strategy
                    )
                    
                    if result and os.path.exists(result):
                        logger.info(f"Download successful with strategy: {strategy_name}")
                        return result
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Strategy {strategy_name} timed out after 5 minutes")
                    continue
                except Exception as strategy_error:
                    logger.warning(f"Strategy {strategy_name} failed: {str(strategy_error)}")
                    # Add delay between strategies to avoid rate limiting
                    if i < len(strategies) - 1:  # Don't delay after last strategy
                        await asyncio.sleep(random.uniform(2, 5))
                    continue
            
            raise Exception("All download strategies failed")
            
        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
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