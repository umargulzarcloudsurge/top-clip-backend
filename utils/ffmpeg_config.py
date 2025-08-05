"""
Global FFmpeg configuration utility
Ensures FFmpeg is properly configured for all modules that need it
"""
import os
import subprocess
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class FFmpegConfig:
    _ffmpeg_path = None
    _ffprobe_path = None
    _configured = False
    
    @classmethod
    def get_ffmpeg_path(cls) -> Optional[str]:
        """Get the configured FFmpeg path"""
        if not cls._configured:
            cls.configure()
        return cls._ffmpeg_path
    
    @classmethod
    def get_ffprobe_path(cls) -> Optional[str]:
        """Get the configured FFprobe path"""
        if not cls._configured:
            cls.configure()
        return cls._ffprobe_path
    
    @classmethod
    def configure(cls) -> bool:
        """Configure FFmpeg paths globally"""
        if cls._configured:
            return cls._ffmpeg_path is not None
        
        try:
            logger.info("🔧 Configuring FFmpeg globally...")
            
            # First try to find ffmpeg using system commands
            ffmpeg_path = None
            
            try:
                result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True, check=True)
                if result.stdout.strip():
                    ffmpeg_path = result.stdout.strip().split('\n')[0]
                    logger.info(f"✅ Found FFmpeg via 'where': {ffmpeg_path}")
            except:
                try:
                    ffmpeg_path = shutil.which('ffmpeg')
                    if ffmpeg_path:
                        logger.info(f"✅ Found FFmpeg via 'which': {ffmpeg_path}")
                except:
                    pass
            
            if not ffmpeg_path:
                # Try common Windows locations
                common_paths = [
                    r"C:\Users\TaimoorAli\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1.1-full_build\bin\ffmpeg.exe",
                    r"C:\ffmpeg\bin\ffmpeg.exe",
                    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
                ]
                
                for path in common_paths:
                    if os.path.exists(path):
                        ffmpeg_path = path
                        logger.info(f"✅ Found FFmpeg at: {ffmpeg_path}")
                        break
            
            if ffmpeg_path and os.path.exists(ffmpeg_path):
                cls._ffmpeg_path = ffmpeg_path
                cls._ffprobe_path = ffmpeg_path.replace('ffmpeg.exe', 'ffprobe.exe')
                
                # Verify ffprobe exists
                if not os.path.exists(cls._ffprobe_path):
                    logger.warning(f"⚠️ FFprobe not found at expected location: {cls._ffprobe_path}")
                    cls._ffprobe_path = None
                
                # Set environment variables
                os.environ['FFMPEG_BINARY'] = cls._ffmpeg_path
                if cls._ffprobe_path:
                    os.environ['FFPROBE_BINARY'] = cls._ffprobe_path
                
                # Configure pydub
                cls._configure_pydub()
                
                cls._configured = True
                logger.info(f"✅ FFmpeg configured globally: {cls._ffmpeg_path}")
                if cls._ffprobe_path:
                    logger.info(f"✅ FFprobe configured: {cls._ffprobe_path}")
                
                return True
            else:
                logger.error("❌ FFmpeg not found in any expected location")
                cls._configured = True
                return False
                
        except Exception as e:
            logger.error(f"❌ FFmpeg configuration failed: {str(e)}")
            cls._configured = True
            return False
    
    @classmethod
    def _configure_pydub(cls):
        """Configure pydub to use the found FFmpeg"""
        try:
            from pydub import AudioSegment
            import pydub.utils
            
            # Set pydub's FFmpeg paths
            AudioSegment.converter = cls._ffmpeg_path
            AudioSegment.ffmpeg = cls._ffmpeg_path
            if cls._ffprobe_path:
                AudioSegment.ffprobe = cls._ffprobe_path
            
            # Store original which function
            original_which = pydub.utils.which
            
            # Also monkey-patch pydub's which function to always return our path
            def custom_which(name):
                if name in ['ffmpeg', 'ffmpeg.exe']:
                    return cls._ffmpeg_path
                elif name in ['ffprobe', 'ffprobe.exe']:
                    return cls._ffprobe_path
                else:
                    return original_which(name)  # Use original function for other tools
            
            # Replace pydub's which function
            pydub.utils.which = custom_which
            
            # Also set environment variables that pydub might use
            import os
            os.environ['PATH'] = os.path.dirname(cls._ffmpeg_path) + os.pathsep + os.environ.get('PATH', '')
            
            logger.info("✅ Pydub configured with custom FFmpeg paths")
            logger.info(f"✅ Added FFmpeg directory to PATH: {os.path.dirname(cls._ffmpeg_path)}")
            
        except ImportError:
            logger.warning("⚠️ Pydub not available for configuration")
        except Exception as e:
            logger.error(f"❌ Pydub configuration failed: {str(e)}")
    
    @classmethod
    def test_configuration(cls) -> bool:
        """Test if FFmpeg configuration is working"""
        try:
            if not cls._configured:
                cls.configure()
            
            if not cls._ffmpeg_path:
                return False
            
            # Test FFmpeg execution
            result = subprocess.run([cls._ffmpeg_path, '-version'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info("✅ FFmpeg test successful")
                return True
            else:
                logger.error(f"❌ FFmpeg test failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ FFmpeg test error: {str(e)}")
            return False

# Auto-configure on module import
_auto_configured = FFmpegConfig.configure()
if _auto_configured:
    logger.info("🎉 FFmpeg auto-configuration successful")
else:
    logger.warning("⚠️ FFmpeg auto-configuration failed")
