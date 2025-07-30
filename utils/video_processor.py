import ffmpeg
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import zipfile
import json
from datetime import datetime
import tempfile
import uuid
from PIL import Image, ImageDraw, ImageFont

from .models import (
    ProcessingOptions, ClipResult, Highlight, Layout, 
    CaptionStyle, TranscriptionSegment, WordTiming
)
from .viral_potential import (
    generate_viral_potential_score, 
    analyze_content_for_viral_factors,
    update_clip_with_viral_score
)
from .pycaps_service import PyCapsService  # PyCaps import
from .transcription_service import TranscriptionService 

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        # Get paths from environment variables with defaults
        self.temp_dir = os.getenv('TEMP_DIR', 'temp')
        self.output_dir = os.getenv('OUTPUT_DIR', 'output')
        self.thumbnails_dir = os.getenv('THUMBNAILS_DIR', 'thumbnails')
        self.fonts_dir = os.getenv('FONTS_DIR', 'fonts')
        self.game_videos_dir = os.getenv('GAME_VIDEOS_DIR', 'game_videos')
        self.music_dir = os.getenv('MUSIC_DIR', 'music')

        # Ensure directories exist
        for directory in [self.temp_dir, self.output_dir, self.thumbnails_dir, 
                         self.fonts_dir, self.game_videos_dir, self.music_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Initialize PyCaps caption service
        self.caption_service = PyCapsService()
        
        logger.info("🎬 Video Processor initialized with PyCaps captions")
        logger.info(f"📁 Directories: output={self.output_dir}, temp={self.temp_dir}")
    
    async def process_highlights(
        self, 
        video_path: str, 
        highlights: List[Highlight], 
        options: ProcessingOptions, 
        job_id: str
    ) -> List[ClipResult]:
        """Process video highlights into clips with modern subtitles"""
        try:
            clips = []
            job_output_dir = os.path.join(self.output_dir, job_id)
            os.makedirs(job_output_dir, exist_ok=True)
            
            logger.info(f"🎬 Processing {len(highlights)} highlights for job {job_id}")
            
            # Get video info
            video_info = await self._get_video_info(video_path)
            logger.info(f"📹 Video: {video_info['width']}x{video_info['height']}, {video_info['duration']:.1f}s")
            
            for i, highlight in enumerate(highlights):
                try:
                    logger.info(f"🎥 Processing clip {i+1}/{len(highlights)}: '{highlight.title}'")
                    
                    # Generate clip filename with unique identifier
                    safe_title = "".join(c for c in highlight.title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:30]
                    unique_id = str(uuid.uuid4())[:10]  # Generate 10-character unique identifier
                    clip_filename = f"clip_{i+1:02d}_{safe_title.replace(' ', '_')}_{unique_id}.mp4"
                    clip_path = os.path.join(job_output_dir, clip_filename)
                    
                    # Use the original title
                    hook_title = highlight.title
                    
                    # Check if we have word-level timing
                    has_words = self._has_word_timing(highlight)
                    if not has_words:
                        logger.warning(f"⚠️ No word-level timing for clip {i+1}, will use segment-level timing")
                    
                    # Process the clip
                    success = await self._process_single_clip(
                        video_path, 
                        highlight, 
                        clip_path, 
                        options, 
                        video_info,
                        has_words,
                        hook_title
                    )
                    
                    if success:
                        # Create initial clip result
                        clip_result = ClipResult(
                            filename=clip_filename,
                            title=highlight.title,
                            duration=highlight.end_time - highlight.start_time,
                            start_time=highlight.start_time,
                            end_time=highlight.end_time,
                            score=highlight.score,
                            hook_title=hook_title,
                            engagement_score=highlight.engagement_score
                        )
                        
                        # Update with calculated viral potential
                        clip_result = update_clip_with_viral_score(clip_result, highlight)
                        
                        logger.info(f"✅ Clip created: {clip_filename} (Viral: {clip_result.viral_potential}%)")
                        clips.append(clip_result)
                    else:
                        logger.error(f"❌ Failed to create clip {i+1}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing clip {i+1}: {str(e)}")
                    continue
            
            logger.info(f"✅ Completed: {len(clips)}/{len(highlights)} clips created")
            return clips
            
        except Exception as e:
            logger.error(f"❌ Critical error: {str(e)}")
            raise
    
    def _has_word_timing(self, highlight: Highlight) -> bool:
        """Check if highlight has word-level timing"""
        if not highlight.transcription_segments:
            return False
        
        for segment in highlight.transcription_segments:
            if segment.words and len(segment.words) > 0:
                return True
        return False
    
    async def _process_single_clip(
        self, 
        video_path: str, 
        highlight: Highlight, 
        output_path: str, 
        options: ProcessingOptions, 
        video_info: Dict[str, Any],
        has_words: bool,
        hook_title: str = None
    ) -> bool:
        """Process a single video clip with FFmpeg captions"""
        try:
            # Create temporary files for processing
            temp_extracted = os.path.join(self.temp_dir, f"temp_extracted_{uuid.uuid4()}.mp4")
            temp_filtered = os.path.join(self.temp_dir, f"temp_filtered_{uuid.uuid4()}.mp4")
            temp_captioned = os.path.join(self.temp_dir, f"temp_captioned_{uuid.uuid4()}.mp4")
            
            try:
                # Step 1: Extract clip segment
                await self._extract_clip(video_path, highlight, temp_extracted)
                
                # Step 2: Apply filters and effects (without captions)
                processed_path = await self._apply_filters(
                    temp_extracted, options, highlight, video_info, has_words, hook_title
                )
                
                # Step 3: Add captions using PyCaps
                logger.info(f"🎨 Adding captions with PyCaps to {processed_path}")
                
                style = CaptionStyle(options.captionStyle)   # convert string ➜ enum
                
                logger.info(f"🎨 Using caption style: {style}")
                
                caption_success = await self.caption_service.add_captions_to_video(
                    processed_path, temp_captioned, style
                )
                
                logger.info(f"🎨 PyCaps returned: {caption_success}")
                
                if caption_success and os.path.exists(temp_captioned):
                    # Move to final output
                    import shutil
                    shutil.move(temp_captioned, output_path)
                    logger.info(f"✅ Captions added successfully with PyCaps")
                else:
                    # If captions failed, use the processed video without captions
                    logger.warning("⚠️ PyCaps failed, using video without captions")
                    import shutil
                    shutil.move(processed_path, output_path)
                
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
                
            finally:
                # Enhanced cleanup of temp files
                for temp_file in [temp_extracted, temp_filtered, temp_captioned]:
                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                            logger.debug(f"🗑️ Cleaned up temp file: {temp_file}")
                        except Exception as cleanup_error:
                            logger.warning(f"⚠️ Failed to cleanup {temp_file}: {cleanup_error}")
                
                # Also cleanup any processed_path if it's different from output_path
                if 'processed_path' in locals() and processed_path != output_path and os.path.exists(processed_path):
                    try:
                        os.remove(processed_path)
                        logger.debug(f"🗑️ Cleaned up processed file: {processed_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"⚠️ Failed to cleanup {processed_path}: {cleanup_error}")
            
        except Exception as e:
            logger.error(f"❌ Error in clip processing: {str(e)}")
            return False
    
    async def _extract_clip(self, video_path: str, highlight: Highlight, output_path: str):
        """Extract clip segment from video"""
        try:
            duration = highlight.end_time - highlight.start_time
            
            def _extract():
                try:
                    (
                        ffmpeg
                        .input(video_path, ss=highlight.start_time, t=duration)
                        .output(
                            output_path, 
                            vcodec='libx264',
                            acodec='aac',
                            preset='fast',  # Changed from 'medium' to 'fast' for better performance
                            crf=23,  # Slightly higher CRF for faster encoding
                            movflags='faststart'  # Optimize for streaming
                        )
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True, quiet=True)
                    )
                except ffmpeg.Error as e:
                    logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
                    raise
            
            # Add timeout protection with shorter timeout
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _extract),
                timeout=120  # Reduced to 2 minute timeout
            )
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Clip extraction timed out after 2 minutes")
            raise Exception("Video processing timed out - video may be corrupted or too complex")
        except Exception as e:
            logger.error(f"❌ Error extracting clip: {str(e)}")
            raise
    
    async def _apply_filters(
        self, 
        input_path: str, 
        options: ProcessingOptions, 
        highlight: Highlight, 
        video_info: Dict[str, Any],
        has_words: bool,
        hook_title: str = None
    ) -> str:
        """Apply all filters and effects to the video"""
        try:
            output_path = input_path.replace('.mp4', '_filtered.mp4')
            
            def _process():
                # Get target dimensions
                target_width, target_height = self._get_target_dimensions(options.layout)
                
                # Load input
                input_stream = ffmpeg.input(input_path)
                video = input_stream.video
                audio = input_stream.audio
                
                # Apply layout transformation
                video = self._apply_layout(video, options.layout, target_width, target_height)
                
                # Apply color grading
                if options.colorGrading and options.colorGrading != 'None':
                    video = self._apply_color_grading(video, options.colorGrading)
                
                # Add game video overlay if specified
                if options.gameVideo:
                    video = self._add_game_overlay(
                        video, options.gameVideo, target_width, target_height, 
                        highlight.end_time - highlight.start_time
                    )
                
                # Mix background music if specified
                if options.backgroundMusic:
                    audio = self._mix_background_music(
                        audio, options.backgroundMusic, 
                        highlight.end_time - highlight.start_time
                    )
                
                # Output with optimized settings
                output = ffmpeg.output(
                    video, audio, output_path,
                    vcodec='libx264',
                    acodec='aac',
                    **self._get_quality_settings(options.qualityLevel)
                )
                
                ffmpeg.run(output, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            
            # Add timeout protection for complex filtering
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _process),
                timeout=300  # Reduced to 5 minute timeout for complex operations
            )
            return output_path
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Filter processing timed out after 5 minutes")
            logger.warning(f"⚠️ Returning unfiltered clip due to timeout")
            return input_path
        except Exception as e:
            logger.error(f"❌ Error applying filters: {str(e)}")
            logger.warning(f"⚠️ Returning unfiltered clip due to error")
            return input_path
    
    def _get_target_dimensions(self, layout: Layout) -> Tuple[int, int]:
        """Get target dimensions for layout"""
        if layout == Layout.VERTICAL:
            return (1080, 1920)  # 9:16 vertical
        elif layout == Layout.SQUARE:
            return (1080, 1080)  # 1:1 square
        else:  # FIT_WITH_BLUR - assume 16:9 landscape
            return (1920, 1080)  # 16:9 landscape
    
    def _apply_layout(self, video_stream, layout: Layout, width: int, height: int):
        """Apply layout transformation"""
        if layout == Layout.VERTICAL:
            # For TikTok: Crop to fill the frame instead of padding with black bars
            video = video_stream.filter('scale', width, height, force_original_aspect_ratio='increase')
            video = video.filter('crop', width, height, '(iw-ow)/2', '(ih-oh)*0.25')  # Slight upward bias for faces
            
        elif layout == Layout.SQUARE:
            # Square content: crop to square, then fit to 9:16 with padding
            video = video_stream.filter('crop', 'min(iw,ih)', 'min(iw,ih)')
            video = video.filter('scale', width, height, force_original_aspect_ratio='decrease')
            video = video.filter('pad', width, height, '(ow-iw)/2', '(oh-ih)/2', color='black')
            
        elif layout == Layout.FIT_WITH_BLUR:
            # Create blurred background
            blur_bg = video_stream.filter('scale', width, height, force_original_aspect_ratio='increase')
            blur_bg = blur_bg.filter('crop', width, height)
            blur_bg = blur_bg.filter('gblur', sigma=30)
            blur_bg = blur_bg.filter('eq', brightness=-0.4)
            
            # Scale main video
            main = video_stream.filter('scale', width, height, force_original_aspect_ratio='decrease')

            # Overlay
            video = ffmpeg.filter([blur_bg, main], 'overlay', '(W-w)/2', '(H-h)/2')
        else:
            video = video_stream
        
        return video
        
    def _apply_color_grading(self, video_stream, color_grading: str):
        """Apply color grading"""
        if color_grading == 'Vibrant':
            video = video_stream.filter('eq', saturation=1.4, contrast=1.1)
        elif color_grading == 'Cinematic':
            video = video_stream.filter('eq', contrast=1.2, saturation=0.9)
            video = video.filter('colorbalance', rs=0.1, bs=-0.1)
        elif color_grading == 'Vintage':
            video = video_stream.filter('eq', contrast=0.9, saturation=0.7, gamma=1.1)
        elif color_grading == 'Neon':
            video = video_stream.filter('eq', saturation=1.6, contrast=1.3)
        else:
            video = video_stream
        
        return video
    
    def _add_game_overlay(self, main_video, game_file: str, width: int, height: int, duration: float):
        """Add game video overlay with better proportions"""
        try:
            game_path = os.path.join(self.game_videos_dir, game_file)
            
            if not os.path.exists(game_path):
                logger.warning(f"Game video not found: {game_path}")
                return main_video
            
            # Load game video
            game_input = ffmpeg.input(game_path, stream_loop=-1, t=duration)
            
            # Better split screen layout - 60/40 instead of 75/25
            main_height = int(height * 0.6)  # Main video gets 60%
            game_height = height - main_height  # Game gets 40%
            
            # Scale videos with better quality
            main_scaled = main_video.filter('scale', width, main_height, force_original_aspect_ratio='decrease')
            main_scaled = main_scaled.filter('pad', width, main_height, '(ow-iw)/2', '(oh-ih)/2', color='black')
            
            # Scale game video to fill the space better
            game_scaled = game_input.video.filter('scale', width, game_height, force_original_aspect_ratio='increase')
            game_scaled = game_scaled.filter('crop', width, game_height)
            
            # Add subtle border between videos
            main_with_border = main_scaled.filter('pad', width, main_height + 2, 0, 0, color='#333333')
            
            # Stack vertically
            return ffmpeg.filter([main_with_border, game_scaled], 'vstack')
            
        except Exception as e:
            logger.error(f"Error adding game overlay: {str(e)}")
            return main_video
    
    def _mix_background_music(self, audio_stream, music_file: str, duration: float):
        """Mix background music with proper audio normalization"""
        try:
            music_path = os.path.join(self.music_dir, music_file)
            
            if not os.path.exists(music_path):
                logger.warning(f"Music file not found: {music_path}")
                return audio_stream
            
            # Load music with loop and duration
            music_input = ffmpeg.input(music_path, stream_loop=-1, t=duration)
            
            # Apply audio normalization and volume control
            # 1. Normalize the original audio to prevent clipping
            normalized_audio = ffmpeg.filter(audio_stream, 'loudnorm', I=-16, LRA=11, TP=-1.5)
            
            # 2. Apply volume reduction to background music (much quieter)
            quiet_music = ffmpeg.filter(music_input.audio, 'volume', 0.12)  # 12% volume
            
            # 3. Mix with original audio prioritized
            return ffmpeg.filter(
                [normalized_audio, quiet_music], 
                'amix', 
                inputs=2, 
                duration='first',
                weights='1.0 0.8'  # Original: 100%, Music: 80% of its already reduced volume
            )
            
        except Exception as e:
            logger.error(f"Error mixing music: {str(e)}")
            return audio_stream
    
    
    def _get_quality_settings(self, quality_level: str) -> Dict[str, Any]:
        """Get encoding settings for quality level"""
        settings = {
            'Standard': {
                'preset': 'medium',
                'crf': 25,  # Good quality, smaller files
                'profile:v': 'high',
                'level': '4.1'
            },
            'High': {
                'preset': 'medium',  # Faster encoding
                'crf': 23,  # High quality but reasonable file size
                'profile:v': 'high',
                'level': '4.1'
            },
            'Ultra': {
                'preset': 'medium',  # Faster encoding
                'crf': 21,  # Excellent quality but not excessive
                'profile:v': 'high',
                'level': '4.2'
            }
        }
        
        base = settings.get(quality_level, settings['High'])
        base['pix_fmt'] = 'yuv420p'
        base['movflags'] = 'faststart'
        
        return base
    
    async def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get video information"""
        try:
            def _probe():
                probe = ffmpeg.probe(video_path)
                video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
                
                if not video_stream:
                    return {'width': 1920, 'height': 1080, 'duration': 0}
                
                return {
                    'width': int(video_stream['width']),
                    'height': int(video_stream['height']),
                    'duration': float(probe['format']['duration']),
                    'fps': eval(video_stream['r_frame_rate']) if 'r_frame_rate' in video_stream else 30
                }
            
            return await asyncio.get_event_loop().run_in_executor(None, _probe)
            
        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            return {'width': 1920, 'height': 1080, 'duration': 0, 'fps': 30}
    
    async def generate_enhanced_thumbnails(self, clips: List[ClipResult], job_id: str):
        """Generate thumbnails for clips"""
        try:
            thumbnails_dir = os.path.join(self.thumbnails_dir, job_id)
            os.makedirs(thumbnails_dir, exist_ok=True)
            
            for clip in clips:
                try:
                    clip_path = os.path.join(self.output_dir, job_id, clip.filename)
                    thumbnail_filename = clip.filename.replace('.mp4', '.jpg')
                    thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
                    
                    # Generate at 30% through the clip
                    thumbnail_time = clip.duration * 0.3
                    
                    await self._generate_thumbnail(clip_path, thumbnail_path, thumbnail_time)
                    
                    clip.thumbnail_url = f"/api/thumbnail/{job_id}/{thumbnail_filename}"
                    
                except Exception as e:
                    logger.error(f"Error generating thumbnail: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in thumbnail generation: {str(e)}")
    
    async def _generate_thumbnail(self, video_path: str, output_path: str, time: float):
        """Generate a single thumbnail"""
        try:
            def _generate():
                (
                    ffmpeg
                    .input(video_path, ss=time)
                    .output(output_path, vframes=1, format='image2', vcodec='mjpeg')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            
            # Add timeout protection for thumbnail generation
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _generate),
                timeout=30  # 30 second timeout
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Thumbnail generation timed out after 30 seconds")
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
    
    async def create_clips_archive(self, job_id: str, archive_path: str):
        """Create ZIP archive of all clips"""
        try:
            def _create():
                job_output_dir = os.path.join(self.output_dir, job_id)
                
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(job_output_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, job_output_dir)
                            zipf.write(file_path, arcname)
            
            await asyncio.get_event_loop().run_in_executor(None, _create)
            
        except Exception as e:
            logger.error(f"Error creating archive: {str(e)}")
            raise