#!/usr/bin/env python3
"""
Fix FFmpeg path configuration for the backend
"""

import os
from pydub import AudioSegment
from pydub.utils import which

def configure_ffmpeg_path():
    """Configure FFmpeg path for pydub"""
    
    # Check current FFmpeg availability
    ffmpeg_path = which("ffmpeg")
    print(f"Current FFmpeg path: {ffmpeg_path}")
    
    if not ffmpeg_path:
        # Try to find FFmpeg in common Windows locations
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Users\TaimoorAli\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1.1-full_build\bin\ffmpeg.exe"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                ffmpeg_path = path
                print(f"Found FFmpeg at: {ffmpeg_path}")
                break
    
    if ffmpeg_path:
        # Set the FFmpeg path explicitly for pydub
        from pydub import AudioSegment
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffmpeg = ffmpeg_path
        AudioSegment.ffprobe = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")
        
        print(f"✅ FFmpeg configured for pydub:")
        print(f"  - Converter: {AudioSegment.converter}")
        print(f"  - FFmpeg: {AudioSegment.ffmpeg}")
        print(f"  - FFprobe: {AudioSegment.ffprobe}")
        
        # Test audio creation
        try:
            audio = AudioSegment.silent(duration=100)
            print("✅ FFmpeg test successful!")
            return True
        except Exception as e:
            print(f"❌ FFmpeg test failed: {e}")
            return False
    else:
        print("❌ FFmpeg not found!")
        return False

if __name__ == "__main__":
    configure_ffmpeg_path()
