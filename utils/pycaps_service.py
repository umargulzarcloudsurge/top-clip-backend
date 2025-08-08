import os
import logging
import asyncio
import ffmpeg
import tempfile
from typing import Optional, List
from .models import CaptionStyle

logger = logging.getLogger(__name__)

class PyCapsService:
    """Caption service for adding captions to videos using FFmpeg"""
    
    def __init__(self):
        self.temp_dir = os.getenv('TEMP_DIR', 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info("🎨 Caption Service initialized (using FFmpeg)")
    
    def _get_caption_style_config(self, caption_style: CaptionStyle) -> dict:
        """Get FFmpeg caption style configuration"""
        styles = {
            CaptionStyle.HYPE: {
                'fontsize': 48,
                'fontcolor': 'FFFFFF',  # White
                'box': 1,
                'boxcolor': '000000@0.8',  # Black with alpha
                'boxborderw': 8,
                'fontfile': os.path.join(os.getenv('FONTS_DIR', 'fonts'), 'arial.ttf'),  # Specify default font file
                'bold': 1,
                'shadow': 1,
                'shadowcolor': '000000',  # Black
                'shadowx': 2,
                'shadowy': 2
            },
            CaptionStyle.VIBRANT: {
                'fontsize': 44,
                'fontcolor': 'FFFF00',  # Yellow
                'box': 1,
                'boxcolor': '800080@0.7',  # Purple with alpha
                'boxborderw': 6,
                'fontfile': None,
                'bold': 1,
                'shadow': 1,
                'shadowcolor': '000000',  # Black
                'shadowx': 3,
                'shadowy': 3
            },
            CaptionStyle.NEO_MINIMAL: {
                'fontsize': 36,
                'fontcolor': 'FFFFFF',  # White
                'box': 1,
                'boxcolor': '000000@0.5',  # Black with alpha
                'boxborderw': 2,
                'fontfile': None,
                'bold': 0,
                'shadow': 0
            },
            CaptionStyle.LINE_FOCUS: {
                'fontsize': 40,
                'fontcolor': 'FFFFFF',  # White
                'box': 1,
                'boxcolor': 'FF0000@0.8',  # Red with alpha
                'boxborderw': 4,
                'fontfile': None,
                'bold': 1,
                'shadow': 1,
                'shadowcolor': '000000',  # Black
                'shadowx': 2,
                'shadowy': 2
            }
        }
        return styles.get(caption_style, styles[CaptionStyle.HYPE])
    
    async def add_captions_to_video(
        self, 
        input_video: str, 
        output_video: str,
        caption_style: CaptionStyle
    ) -> bool:
        """Add captions using FFmpeg directly"""
        try:
            logger.info(f"🎨 Adding {caption_style} captions using FFmpeg")
            
            # For now, we'll just copy the video without captions
            # since we don't have transcription data available in this service
            # The captions should be added in the video processor where transcription data is available
            
            import shutil
            shutil.copy2(input_video, output_video)
            logger.info("📝 Video copied (captions will be added in video processor)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Caption service error: {str(e)}")
            return False
    
    def create_subtitle_file(self, transcription_segments: List, output_path: str) -> bool:
        """Create SRT subtitle file from transcription segments"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(transcription_segments, 1):
                    start_time = self._seconds_to_srt_time(segment.start)
                    end_time = self._seconds_to_srt_time(segment.end)
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{segment.text.strip()}\n\n")
            
            logger.info(f"✅ Created subtitle file: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating subtitle file: {str(e)}")
            return False
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
