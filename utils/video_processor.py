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

# Import FFmpeg configuration first
from .ffmpeg_config import FFmpegConfig

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
        # Use global FFmpeg configuration
        ffmpeg_configured = FFmpegConfig.configure()
        if ffmpeg_configured:
            logger.info(f"✅ Video processor using global FFmpeg: {FFmpegConfig.get_ffmpeg_path()}")
        else:
            logger.warning("⚠️ FFmpeg not configured - video processing may fail")
        
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
                    error_type = type(e).__name__
                    error_msg = str(e)
                    request_id = job_id[:8]
                    
                    # INSTANT CONSOLE ERROR - Individual clip processing failure
                    instant_error_msg = f"\n🚨 INSTANT CLIP PROCESSING ERROR: INDIVIDUAL CLIP FAILED! 🚨\n🎬 Request ID: {request_id}\n🔢 Clip Number: {i+1}/{len(highlights)}\n⏰ Start Time: {highlight.start_time:.2f}s\n⏰ End Time: {highlight.end_time:.2f}s\n📝 Title: {highlight.title}\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n❌ Issue: Failed to create individual video clip\n🔍 This may indicate FFmpeg issues, file corruption, or timing problems\n" + "="*80
                    
                    # Log to both console and log file
                    print(instant_error_msg)
                    logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
                    
                    logger.error(f"❌ Error processing clip {i+1}: {str(e)}")
                    continue
            
            logger.info(f"✅ Completed: {len(clips)}/{len(highlights)} clips created")
            return clips
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            request_id = job_id[:8]
            
            # INSTANT CONSOLE ERROR - Critical video processing failure
            instant_error_msg = f"\n🚨 INSTANT VIDEO PROCESSOR CRITICAL ERROR! 🚨\n🎬 Request ID: {request_id}\n📁 Video Path: {video_path}\n🔢 Total Highlights: {len(highlights)}\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n❌ Issue: Critical failure in video processor initialization or setup\n🔍 This indicates fundamental processing issues or resource problems\n" + "="*80
            
            # Log to both console and log file
            print(instant_error_msg)
            logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
            
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
                
                # Step 3: Add captions with transcription data if available
                if highlight.transcription_segments and len(highlight.transcription_segments) > 0:
                    logger.info(f"🎨 Adding captions with transcription data to {processed_path}")
                    logger.info(f"📊 Found {len(highlight.transcription_segments)} transcription segments")
                    
                    # Log segment details for debugging
                    for i, seg in enumerate(highlight.transcription_segments):
                        logger.debug(f"Segment {i+1}: {seg.start:.2f}-{seg.end:.2f}s: '{seg.text[:30]}...'")
                    
                    style = CaptionStyle(options.captionStyle) if isinstance(options.captionStyle, str) else options.captionStyle
                    logger.info(f"🎨 Using caption style: {style}")
                    
                    # Add captions to the processed video
                    caption_success = await self._add_captions_with_ffmpeg(
                        processed_path, temp_captioned, highlight.transcription_segments, style
                    )
                    
                    if caption_success and os.path.exists(temp_captioned):
                        # Move to final output
                        import shutil
                        shutil.move(temp_captioned, output_path)
                        logger.info("✅ Captions added successfully with FFmpeg")
                    else:
                        logger.error("❌ Caption rendering failed, verify FFmpeg command.")
                        logger.warning("⚠️ Using video without captions due to error")
                        import shutil
                        shutil.move(processed_path, output_path)
                else:
                    # No transcription data, use video without captions
                    logger.warning("⚠️ No transcription data available, using video without captions")
                    # Apply minimum resolution to the processed video
                    await self._ensure_minimum_resolution(processed_path, output_path, 1280, 720)
                
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
            error_type = type(e).__name__
            error_msg = str(e)
            
            # INSTANT CONSOLE ERROR - Single clip processing failure
            instant_error_msg = f"\n🚨 INSTANT SINGLE CLIP ERROR! 🚨\n📁 Video Path: {video_path}\n📝 Output Path: {output_path}\n⏰ Start Time: {highlight.start_time:.2f}s\n⏰ End Time: {highlight.end_time:.2f}s\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n❌ Issue: Individual clip processing pipeline failed\n" + "="*80
            
            # Log to both console and log file
            print(instant_error_msg)
            logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
            
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
    
    async def _ensure_minimum_resolution(self, input_path: str, output_path: str, min_width: int, min_height: int) -> None:
        """Ensure video resolution is at least minimum specified dimensions"""
        try:
            if not os.path.exists(input_path):
                logger.error(f"Input file does not exist: {input_path}")
                raise Exception(f"Input file does not exist: {input_path}")
            
            # Get current video dimensions first
            probe = ffmpeg.probe(input_path)
            video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            
            if not video_stream:
                logger.error("No video stream found in input file")
                # Copy file as-is if no video stream
                import shutil
                shutil.copy2(input_path, output_path)
                return
            
            current_width = int(video_stream['width'])
            current_height = int(video_stream['height'])
            
            logger.debug(f"Current resolution: {current_width}x{current_height}, Target: {min_width}x{min_height}")
            
            # If resolution is already adequate, just copy the file
            if current_width >= min_width and current_height >= min_height:
                logger.debug("Resolution already meets minimum requirements, copying file")
                import shutil
                shutil.copy2(input_path, output_path)
                return
            
            # Calculate scaling
            scale_filter = f"scale='max({min_width},iw)':'max({min_height},ih)'"
            
            def _scale():
                try:
                    (
                        ffmpeg
                        .input(input_path)
                        .filter('scale', f'max({min_width},iw)', f'max({min_height},ih)')
                        .output(
                            output_path, 
                            vcodec='libx264', 
                            acodec='aac',
                            preset='fast',
                            crf=23
                        )
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True, quiet=True)
                    )
                    logger.debug(f"Successfully scaled video to minimum resolution")
                except ffmpeg.Error as e:
                    error_msg = e.stderr.decode() if e.stderr else 'Unknown error'
                    logger.error(f"FFmpeg scaling error: {error_msg}")
                    # Fallback: copy original file
                    import shutil
                    shutil.copy2(input_path, output_path)
            
            await asyncio.get_event_loop().run_in_executor(None, _scale)
            
        except Exception as e:
            logger.error(f"Error in resolution scaling: {str(e)}")
            # Fallback: copy original file
            try:
                import shutil
                shutil.copy2(input_path, output_path)
                logger.info("Copied original file as fallback")
            except Exception as copy_error:
                logger.error(f"Failed to copy original file: {str(copy_error)}")
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
        """Get target dimensions for layout - ensures minimum 720p"""
        if layout == Layout.VERTICAL:
            return (1280, 1920)  # 9:16 vertical, minimum 720p width (1280x720)
        elif layout == Layout.SQUARE:
            return (1280, 1280)  # 1:1 square, minimum 720p
        else:  # FIT_WITH_BLUR - assume 16:9 landscape
            return (1920, 1080)  # 16:9 landscape, minimum 720p height
    
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
    
    async def _add_captions_with_ffmpeg(
        self, 
        input_video: str, 
        output_video: str, 
        transcription_segments: List[TranscriptionSegment], 
        style: CaptionStyle
    ) -> bool:
        """Add captions to video using SRT subtitle file to avoid long command lines"""
        try:
            logger.info(f"📝 Adding captions with style {style} to video")
            style_config = self.caption_service._get_caption_style_config(style)

            # Create SRT subtitle file
            srt_file = os.path.join(self.temp_dir, f"captions_{uuid.uuid4()}.srt")
            srt_content = self._create_srt_content(transcription_segments)
            
            if not srt_content:
                logger.warning("⚠️ No captions to add, copying video...")
                import shutil
                shutil.copy2(input_video, output_video)
                return True
            
            # Write SRT file
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            logger.info(f"📄 Created SRT file: {srt_file}")
            
            try:
                # Use FFmpeg with subtitles filter
                input_stream = ffmpeg.input(input_video)
                video = input_stream.video
                audio = input_stream.audio
                
                # Apply subtitles using the SRT file
                video = video.filter(
                    'subtitles', 
                    srt_file.replace('\\', '/'),  # FFmpeg expects forward slashes
                    force_style=f"FontName=Arial,FontSize={style_config['fontsize']},PrimaryColour={self._hex_to_ass_color(style_config['fontcolor'])},Alignment=2,MarginV=50"
                )
                
                output = ffmpeg.output(
                    video, audio, output_video,
                    vcodec='libx264',
                    acodec='aac',
                    preset='fast',
                    crf=23,
                    movflags='faststart'
                )
                
                def _run_ffmpeg():
                    ffmpeg.run(output, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                
                # Add timeout protection
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, _run_ffmpeg),
                    timeout=180  # 3 minute timeout
                )
                
                logger.info("✅ Captions added successfully with SRT subtitles")
                return True
                
            finally:
                # Clean up SRT file
                if os.path.exists(srt_file):
                    try:
                        os.remove(srt_file)
                        logger.debug(f"🗑️ Cleaned up SRT file: {srt_file}")
                    except Exception as cleanup_error:
                        logger.warning(f"⚠️ Failed to cleanup SRT file: {cleanup_error}")
            
        except asyncio.TimeoutError:
            logger.error("❌ Caption rendering timed out after 3 minutes")
            return False
        except Exception as e:
            logger.error(f"❌ Error adding captions with FFmpeg: {str(e)}")
            return False
    
    def _create_srt_content(self, transcription_segments: List[TranscriptionSegment]) -> str:
        """Create SRT subtitle content from transcription segments"""
        srt_content = ""
        subtitle_index = 1
        
        for segment in transcription_segments:
            if segment.words and len(segment.words) > 0:
                # Use word-level timing for precise captions
                for word in segment.words:
                    word_text = (getattr(word, 'word', getattr(word, 'text', '')) or '').strip()
                    if not word_text:
                        continue
                    
                    start_time = self._seconds_to_srt_time(word.start)
                    end_time = self._seconds_to_srt_time(word.end)
                    
                    srt_content += f"{subtitle_index}\n"
                    srt_content += f"{start_time} --> {end_time}\n"
                    srt_content += f"{word_text}\n\n"
                    subtitle_index += 1
            elif segment.text.strip():
                # Fallback to segment-level timing
                start_time = self._seconds_to_srt_time(segment.start)
                end_time = self._seconds_to_srt_time(segment.end)
                
                srt_content += f"{subtitle_index}\n"
                srt_content += f"{start_time} --> {end_time}\n"
                srt_content += f"{segment.text.strip()}\n\n"
                subtitle_index += 1
        
        return srt_content
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def _hex_to_ass_color(self, color: str) -> str:
        """Convert color name or hex color to ASS format (BGR)"""
        # Color name to hex mapping
        color_map = {
            'white': 'FFFFFF',
            'black': '000000',
            'red': 'FF0000',
            'green': '00FF00',
            'blue': '0000FF',
            'yellow': 'FFFF00',
            'cyan': '00FFFF',
            'magenta': 'FF00FF',
            'purple': '800080',
            'orange': 'FFA500',
            'pink': 'FFC0CB',
            'brown': 'A52A2A',
            'gray': '808080',
            'grey': '808080'
        }
        
        # Convert color name to hex if needed
        color_lower = color.lower().strip()
        if color_lower in color_map:
            hex_color = color_map[color_lower]
        else:
            # Assume it's already hex, remove # if present
            hex_color = color.lstrip('#')
            
            # Validate hex color format
            if len(hex_color) != 6 or not all(c in '0123456789ABCDEFabcdef' for c in hex_color):
                # Default to white if invalid
                hex_color = 'FFFFFF'
        
        # Convert hex to RGB
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except ValueError:
            # Default to white if conversion fails
            r, g, b = 255, 255, 255
        
        # ASS uses BGR format
        return f"&H00{b:02X}{g:02X}{r:02X}"
    
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
