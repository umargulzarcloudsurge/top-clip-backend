import cv2
import numpy as np
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import os
import json
from datetime import datetime
import subprocess
import traceback

from .models import Highlight, ProcessingOptions, ClipLength, TranscriptionSegment, TranscriptionWord
from .transcription_service import TranscriptionService  # FIXED: Correct import

logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file


class ClipAnalyzer:
    def __init__(self):
        self.transcription_service = TranscriptionService()
        
        # Initialize OpenAI client with proper error handling
        try:
            import openai
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.openai_client = openai.OpenAI(api_key=api_key)
                logger.info("✅ OpenAI client for ClipAnalyzer initialized successfully")
            else:
                self.openai_client = None
                logger.warning("❌ OpenAI API key not found. Subtitles will not work.")
                logger.warning("   Set OPENAI_API_KEY environment variable to enable subtitles")
        except Exception as e:
            logger.error(f"❌ OpenAI client initialization failed: {str(e)}")
            self.openai_client = None
        
    async def analyze_video(self, video_path: str, options: ProcessingOptions) -> List[Highlight]:
        """Analyze video and generate multiple highlights based on AI analysis"""
        try:
            logger.info(f"🎬 Analyzing video for clips: {video_path}")
            logger.info(f"📊 Clip count requested: {options.clipCount}")
            
            # Get video duration
            duration = await self._get_video_duration(video_path)
            logger.info(f"⏱️ Video duration: {duration:.2f} seconds")
            
            # Get basic transcription for the clip to work with captions
            logger.info("🎙️ Getting transcription for AI analysis...")
            transcript = await self._get_transcription_with_fallback(video_path)
            
            # Analyze audio features (simplified for now)
            audio_features = {"energy_levels": [], "speech_rate": 1.0}
            
            # Analyze visual features (simplified for now) 
            visual_features = {"scene_changes": [], "motion_intensity": []}
            
            # Generate highlights using transcription and AI analysis
            highlights = await self._generate_highlights_with_transcription(
                audio_features, visual_features, transcript, options
            )
            
            logger.info(f"✅ Generated {len(highlights)} highlights from {duration:.1f}s video")
            for i, highlight in enumerate(highlights):
                logger.info(f"   Clip {i+1}: {highlight.start_time:.1f}s-{highlight.end_time:.1f}s ({highlight.end_time-highlight.start_time:.1f}s)")
            
            return highlights
            
        except Exception as e:
            logger.error(f"❌ Error in video analysis: {str(e)}")
            logger.error(f"   Full traceback: {traceback.format_exc()}")
            
            # INSTANT CONSOLE ERROR - AI Analysis Fallback
            print(f"\n🚨 INSTANT AI ANALYSIS FALLBACK! 🚨")
            print(f"🤖 AI Analysis Failed - falling back to time-based clips")
            print(f"📺 Video Path: {video_path}")
            print(f"🔧 Error Type: {type(e).__name__}")
            print(f"💬 Error Message: {str(e)}")
            print(f"🔄 Fallback Reason: AI clip analysis failed - using basic time intervals instead")
            print(f"💡 Fallback Strategy: Will create {options.clipCount} clips at even time intervals")
            print(f"⚡ Clips will still be generated but without AI-powered highlights")
            
            # Show full traceback for debugging
            import traceback
            traceback_str = traceback.format_exc()
            print(f"📚 Full Traceback:\n{traceback_str}")
            print("="*80)
            
            # Return fallback highlights
            return await self._create_fallback_highlights(video_path, options)
    
    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
        except Exception as e:
            logger.error(f"❌ Error getting video duration: {str(e)}")
            return 600.0  # Default to 10 minutes if we can't get duration
    
    async def _get_transcription_with_fallback(self, video_path: str) -> Dict[str, Any]:
        """Get transcription with proper error handling and logging"""
        try:
            if not self.openai_client:
                logger.warning("🚫 No OpenAI client - clips will have no subtitles")
                logger.warning("   To enable subtitles, set OPENAI_API_KEY environment variable")
                return {'text': '', 'segments': [], 'words': []}
            
            logger.info("🎙️ Starting video transcription...")
            
            # Add timeout protection for transcription
            transcript = await asyncio.wait_for(
                self.transcription_service.transcribe_audio(video_path),
                timeout=240  # 4 minute timeout for transcription
            )
            
            # Validate transcription result
            if not transcript:
                logger.error("❌ Transcription returned None")
                return {'text': '', 'segments': [], 'words': []}
            
            segments = transcript.get('segments', [])
            words = transcript.get('words', [])
            text = transcript.get('text', '')
            
            logger.info(f"✅ Transcription successful:")
            logger.info(f"   📝 Text length: {len(text)} characters")
            logger.info(f"   📋 Segments: {len(segments)}")
            logger.info(f"   🔤 Words: {len(words)}")
            
            if len(segments) == 0:
                logger.warning("⚠️ No transcription segments found - subtitles will be empty")
                logger.warning("   This could be due to:")
                logger.warning("   - Silent or very quiet audio")
                logger.warning("   - Non-English speech (try setting language parameter)")
                logger.warning("   - Audio quality issues")
            else:
                # Log first few segments for debugging
                logger.info("   📋 First segments:")
                for i, segment in enumerate(segments[:3]):
                    start = segment.get('start', 0)
                    end = segment.get('end', 0)
                    text_preview = segment.get('text', '')[:50]
                    logger.info(f"      {i+1}. '{text_preview}...' ({start:.1f}s-{end:.1f}s)")
            
            return transcript
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Transcription timed out after 4 minutes")
            logger.info("🚫 Clips will be generated without subtitles")
            
            # INSTANT CONSOLE ERROR - Clip Analyzer Transcription Timeout Fallback
            print(f"\n🚨 INSTANT CLIP ANALYZER TRANSCRIPTION TIMEOUT FALLBACK! 🚨")
            print(f"🎙️ Video Path: {video_path}")
            print(f"⏰ Timeout Duration: 4 minutes (240 seconds)")
            print(f"🔄 Fallback Reason: Transcription took too long during clip analysis")
            print(f"💡 Fallback Strategy: Will generate clips without captions/subtitles")
            print(f"⚡ Clips will still be created but without transcription-based highlights")
            print("="*80)
            
            return {'text': '', 'segments': [], 'words': []}
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # INSTANT CONSOLE ERROR - Clip Analyzer Transcription Error Fallback
            instant_error_msg = f"\n🚨 INSTANT CLIP ANALYZER TRANSCRIPTION ERROR FALLBACK! 🚨\n🎤 Video Path: {video_path}\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n🎬 Context: During AI clip analysis phase\n❌ Issue: Transcription failed during clip analysis\n🔍 This indicates API issues or audio processing problems during analysis\n📁 Fallback: Will generate clips without captions/subtitles\n⚙️ Impact: AI analysis will continue but clips won't have subtitles\n" + "="*80
            
            # Log to both console and log file
            print(instant_error_msg)
            logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
            
            logger.error(f"❌ Transcription failed: {str(e)}")
            logger.error(f"   Full error: {traceback.format_exc()}")
            logger.info("🚫 Clips will be generated without subtitles")
            return {'text': '', 'segments': [], 'words': []}
    
    async def _generate_highlights_with_transcription(
        self, 
        audio_features: Dict[str, Any], 
        visual_features: Dict[str, Any], 
        transcript: Dict[str, Any], 
        options: ProcessingOptions
    ) -> List[Highlight]:
        """Generate highlights ensuring transcription segments are properly included"""
        try:
            highlights = []
            
            # Get clip duration preferences
            min_duration, max_duration = self._get_duration_range(options.clipLength)
            
            # Get video duration
            duration = audio_features.get('duration', 300.0)
            logger.info(f"📹 Video duration: {duration:.1f}s, Target clip duration: {min_duration}-{max_duration}s")
            
            # Get transcription data
            segments = transcript.get('segments', [])
            words = transcript.get('words', [])
            
            # Create highlights based on time intervals
            num_clips = min(options.clipCount or 3, 5)
            logger.info(f"🔢 DEBUG: Requested clipCount: {options.clipCount}, Using num_clips: {num_clips}")
            
            if len(segments) > 0:
                # Use transcription-based highlights
                logger.info(f"🎯 Creating transcription-based highlights from {len(segments)} segments")
                highlights = await self._create_transcription_based_highlights(
                    segments, words, duration, num_clips, min_duration, max_duration
                )
            else:
                # Fallback to time-based highlights (no subtitles)
                logger.warning("⚠️ Creating time-based highlights without subtitles")
                highlights = await self._create_time_based_highlights(
                    duration, num_clips, min_duration, max_duration
                )
            
            return highlights
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # INSTANT CONSOLE ERROR - Highlights Generation With Transcription Failed
            instant_error_msg = f"\n🚨 INSTANT HIGHLIGHTS GENERATION ERROR FALLBACK! 🚨\n🎬 Processing Options: {options}\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n❌ Issue: Failed to generate highlights with transcription data\n🔍 This indicates problems combining AI analysis with transcription\n📁 Fallback: Will generate basic fallback highlights\n⚙️ Impact: Reduced quality highlights without AI analysis\n" + "="*80
            
            # Log to both console and log file
            print(instant_error_msg)
            logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
            
            logger.error(f"❌ Error generating highlights with transcription: {str(e)}")
            return await self._create_fallback_highlights("", options)
    
    async def _create_transcription_based_highlights(
        self,
        segments: List[Dict[str, Any]], 
        words: List[Dict[str, Any]], 
        duration: float,
        num_clips: int,
        min_duration: float,
        max_duration: float
    ) -> List[Highlight]:
        """Create highlights based on transcription segments"""
        try:
            highlights = []
            
            # Group segments into clips
            clips_segments = self._group_segments_into_clips(
                segments, num_clips, min_duration, max_duration
            )
            
            logger.info(f"📊 Grouped segments into {len(clips_segments)} clips")
            logger.info(f"🔍 DEBUG: Total words available: {len(words)}")
            if words:
                logger.info(f"🔍 DEBUG: First word: {words[0]}")
                logger.info(f"🔍 DEBUG: Last word: {words[-1]}")
            
            for i, clip_segments in enumerate(clips_segments):
                if not clip_segments:
                    continue
                
                # Calculate clip boundaries
                start_time = clip_segments[0]['start']
                end_time = clip_segments[-1]['end']
                
                # Ensure clip meets duration requirements
                clip_duration = end_time - start_time
                if clip_duration < min_duration:
                    # Extend the clip
                    extension = (min_duration - clip_duration) / 2
                    start_time = max(0, start_time - extension)
                    end_time = min(duration, end_time + extension)
                elif clip_duration > max_duration:
                    # Trim the clip
                    end_time = start_time + max_duration
                
                # Create transcription segments for this highlight
                transcription_segments = []
                
                for segment in clip_segments:
                    segment_start = segment.get('start', 0)
                    segment_end = segment.get('end', 0)
                    segment_text = segment.get('text', '').strip()
                    
                    if not segment_text:
                        continue
                    
                    # Adjust segment times to be relative to highlight start
                    adjusted_start = max(0, segment_start - start_time)
                    adjusted_end = min(end_time - start_time, segment_end - start_time)
                    
                    if adjusted_end > adjusted_start and adjusted_end > 0:
                        # Find words for this segment - simplified matching logic
                        segment_words = []
                        logger.info(f"🔍 DEBUG: Looking for words in segment {segment_text[:30]}... (segment: {segment_start:.2f}-{segment_end:.2f}s, clip: {start_time:.2f}-{end_time:.2f}s)")
                        
                        for word in words:
                            word_start = word.get('start', 0)
                            word_end = word.get('end', 0)
                            word_text = word.get('text', '').strip()
                            
                            # Simplified check: word just needs to overlap with segment timeframe
                            # Allow some tolerance for timing precision issues
                            tolerance = 0.1  # 100ms tolerance
                            if (word_text and 
                                word_start is not None and word_end is not None and
                                word_start >= (segment_start - tolerance) and 
                                word_end <= (segment_end + tolerance)):
                                
                                # Adjust word times relative to highlight start
                                adjusted_word_start = max(0, word_start - start_time)
                                adjusted_word_end = min(end_time - start_time, word_end - start_time)
                                
                                # Ensure valid timing
                                if adjusted_word_end > adjusted_word_start and adjusted_word_start >= 0:
                                    segment_words.append(TranscriptionWord(
                                        start=adjusted_word_start,
                                        end=adjusted_word_end,
                                        text=word_text
                                    ))
                        
                        logger.info(f"🔍 DEBUG: Found {len(segment_words)} words for segment")
                        
                        transcription_segments.append(TranscriptionSegment(
                            start=adjusted_start,
                            end=adjusted_end,
                            text=segment_text,
                            words=segment_words if segment_words else None
                        ))
                
                # Create highlight
                highlight_title = self._generate_highlight_title(clip_segments)
                
                highlight = Highlight(
                    start_time=start_time,
                    end_time=end_time,
                    score=0.8 - (i * 0.05),  # Decreasing score
                    title=highlight_title,
                    transcription_segments=transcription_segments,
                    audio_features={},
                    visual_features={},
                    content_features={}
                )
                
                highlights.append(highlight)
                
                logger.info(f"✅ Created highlight {i+1}: '{highlight_title}' ({start_time:.1f}s-{end_time:.1f}s)")
                logger.info(f"   📝 Subtitle segments: {len(transcription_segments)}")
                
                # Debug: Log subtitle content
                if transcription_segments:
                    for j, seg in enumerate(transcription_segments[:2]):  # First 2 segments
                        logger.debug(f"      Subtitle {j+1}: '{seg.text[:40]}...' ({seg.start:.1f}s-{seg.end:.1f}s)")
                        if seg.words:
                            word_texts = [w.text for w in seg.words[:5]]  # First 5 words
                            logger.debug(f"         Words: {word_texts}")
                else:
                    logger.warning(f"   ⚠️ NO SUBTITLE SEGMENTS for highlight {i+1}")
            
            return highlights
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # INSTANT CONSOLE ERROR - Transcription-Based Highlights Failed
            instant_error_msg = f"\n🚨 INSTANT TRANSCRIPTION-BASED HIGHLIGHTS ERROR! 🚨\n🔢 Number of Clips: {num_clips}\n📊 Segments Count: {len(segments)}\n🕒 Duration: {duration:.2f}s\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n❌ Issue: Failed to create highlights from transcription segments\n🔍 This indicates problems processing transcription data for highlights\n📁 Fallback: Will return empty highlights list (higher-level fallback will trigger)\n" + "="*80
            
            # Log to both console and log file
            print(instant_error_msg)
            logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
            
            logger.error(f"❌ Error creating transcription-based highlights: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def _group_segments_into_clips(
        self, 
        segments: List[Dict[str, Any]], 
        num_clips: int, 
        min_duration: float, 
        max_duration: float
    ) -> List[List[Dict[str, Any]]]:
        """Group transcription segments into clips"""
        try:
            if not segments:
                logger.warning("No segments to group")
                return []
            
            # Special case: if only 1 clip is requested, group all segments into one clip
            if num_clips == 1:
                logger.debug(f"Creating single clip from all {len(segments)} segments")
                return [segments]
            
            clips = []
            current_clip = []
            current_duration = 0
            
            # Calculate target duration per clip
            total_duration = segments[-1]['end'] - segments[0]['start']
            target_duration = min(max_duration * 0.8, total_duration / num_clips)  # Use 80% of max duration as target
            
            logger.debug(f"Grouping {len(segments)} segments into {num_clips} clips")
            logger.debug(f"Target duration per clip: {target_duration:.1f}s (max: {max_duration:.1f}s)")
            
            for segment_idx, segment in enumerate(segments):
                segment_duration = segment['end'] - segment['start']
                
                # Check if adding this segment would exceed target duration
                potential_duration = current_duration + segment_duration
                
                if current_clip and potential_duration > target_duration:
                    # Finalize current clip if it meets minimum duration
                    if current_duration >= min_duration:
                        clips.append(current_clip)
                        logger.debug(f"   Created clip {len(clips)} with {len(current_clip)} segments ({current_duration:.1f}s)")
                        current_clip = []
                        current_duration = 0
                    
                    # Stop if we have enough clips
                    if len(clips) >= num_clips:
                        break
                
                # Add segment to current clip
                current_clip.append(segment)
                current_duration += segment_duration
                
                logger.debug(f"      Added segment {segment_idx+1}: '{segment.get('text', '')[:30]}...' (+{segment_duration:.1f}s, total: {current_duration:.1f}s)")
            
            # Add final clip if valid and we need more clips
            if current_clip and current_duration >= min_duration and len(clips) < num_clips:
                clips.append(current_clip)
                logger.debug(f"   Created final clip {len(clips)} with {len(current_clip)} segments ({current_duration:.1f}s)")
            
            logger.info(f"📊 Grouped segments into {len(clips)} clips (requested: {num_clips})")
            return clips[:num_clips]
            
        except Exception as e:
            logger.error(f"❌ Error grouping segments into clips: {str(e)}")
            return []
    
    def _generate_highlight_title(self, segments: List[Dict[str, Any]]) -> str:
        """Generate a title for the highlight based on transcript content"""
        try:
            if not segments:
                return "Video Highlight"
            
            # Combine text from segments
            full_text = " ".join([seg.get('text', '').strip() for seg in segments if seg.get('text', '').strip()])
            
            if not full_text:
                return "Video Highlight"
            
            # Take first 8 words as title
            words = full_text.split()[:8]
            title = " ".join(words)
            
            # Clean up title
            if len(title) > 50:
                title = title[:47] + "..."
            
            return title if title else "Video Highlight"
            
        except Exception as e:
            logger.error(f"❌ Error generating highlight title: {str(e)}")
            return "Video Highlight"
    
    async def _create_time_based_highlights(
        self,
        duration: float,
        num_clips: int,
        min_duration: float,
        max_duration: float
    ) -> List[Highlight]:
        """Create time-based highlights without transcription"""
        try:
            highlights = []
            
            # Create clips at regular intervals
            interval = duration / num_clips
            
            logger.info(f"⏰ Creating {num_clips} time-based highlights (interval: {interval:.1f}s)")
            
            for i in range(num_clips):
                start_time = i * interval
                end_time = min(start_time + min_duration, duration, start_time + max_duration)
                
                if end_time - start_time >= min_duration:
                    highlight = Highlight(
                        start_time=start_time,
                        end_time=end_time,
                        score=0.6 - (i * 0.05),
                        title=f"Highlight {i+1}",
                        transcription_segments=[],  # No subtitles
                        audio_features={},
                        visual_features={},
                        content_features={}
                    )
                    highlights.append(highlight)
                    
                    logger.info(f"⏱️ Created time-based highlight {i+1}: ({start_time:.1f}s-{end_time:.1f}s) - NO SUBTITLES")
            
            return highlights
            
        except Exception as e:
            logger.error(f"❌ Error creating time-based highlights: {str(e)}")
            return []

    # Simplified feature extraction methods
    async def _extract_audio_features_simple(self, video_path: str) -> Dict[str, Any]:
        """Simplified audio feature extraction"""
        try:
            def _get_duration():
                try:
                    result = subprocess.run([
                        'ffprobe', '-v', 'quiet', '-show_entries', 
                        'format=duration', '-of', 'csv=p=0', video_path
                    ], capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        duration = float(result.stdout.strip())
                        logger.debug(f"📹 Video duration from ffprobe: {duration:.1f}s")
                        return duration
                    else:
                        logger.warning(f"ffprobe failed: {result.stderr}")
                        return 300.0
                except Exception as e:
                    logger.warning(f"ffprobe error: {str(e)}")
                    return 300.0
            
            loop = asyncio.get_event_loop()
            duration = await loop.run_in_executor(None, _get_duration)
            
            return {
                'duration': duration,
                'times': list(range(0, int(duration), 10)),
                'rms': [0.5] * (int(duration) // 10),
                'spectral_centroid': [1000] * (int(duration) // 10),
                'zcr': [0.1] * (int(duration) // 10),
                'onsets': [],
                'tempo': 120.0,
                'beats': []
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting audio features: {str(e)}")
            return {'duration': 300.0, 'times': [], 'rms': [], 'spectral_centroid': [], 'zcr': [], 'onsets': [], 'tempo': 120.0, 'beats': []}

    async def _extract_visual_features_simple(self, video_path: str) -> Dict[str, Any]:
        """Simplified visual feature extraction"""
        try:
            return {
                'scene_changes': [0.3, 0.2, 0.5, 0.1, 0.4],
                'motion_intensity': [0.4, 0.6, 0.3, 0.8, 0.2],
                'face_detections': [1, 0, 2, 1, 0],
                'frame_times': [0, 60, 120, 180, 240],
                'brightness_changes': [100, 120, 90, 110, 95]
            }
        except Exception as e:
            logger.error(f"❌ Error extracting visual features: {str(e)}")
            return {'scene_changes': [], 'motion_intensity': [], 'face_detections': [], 'frame_times': [], 'brightness_changes': []}
    
    async def _create_fallback_highlights(self, video_path: str, options: ProcessingOptions) -> List[Highlight]:
        """Create fallback highlights when analysis fails"""
        try:
            min_duration, max_duration = self._get_duration_range(options.clipLength)
            
            highlight = Highlight(
                start_time=10.0,
                end_time=10.0 + min_duration,
                score=0.6,
                title="Video Highlight",
                transcription_segments=[],  # No subtitles in fallback
                audio_features={},
                visual_features={},
                content_features={}
            )
            
            logger.warning("⚠️ Using fallback highlight - NO SUBTITLES")
            return [highlight]
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # INSTANT CONSOLE ERROR - Final Fallback Highlights Failed
            instant_error_msg = f"\n🚨 INSTANT FINAL FALLBACK HIGHLIGHTS ERROR! 🚨\n📁 Video Path: {video_path}\n⚙️ Options: {options}\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n❌ Issue: Even the basic fallback highlight creation failed\n🔍 This indicates critical system problems - unable to create even basic clips\n📁 Final Result: No highlights will be generated (complete failure)\n" + "="*80
            
            # Log to both console and log file
            print(instant_error_msg)
            logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
            
            logger.error(f"❌ Error creating fallback highlights: {str(e)}")
            return []
    
    def _get_duration_range(self, clip_length: ClipLength) -> Tuple[float, float]:
        """Get duration range based on clip length setting"""
        if clip_length == ClipLength.SHORT:
            return (15, 30)
        elif clip_length == ClipLength.MEDIUM:
            return (30, 60)
        elif clip_length == ClipLength.LONG:
            return (60, 90)
        else:
            return (20, 45)
    
    # Test methods for debugging
    async def test_transcription_only(self, video_path: str) -> Dict[str, Any]:
        """Test transcription service only"""
        try:
            logger.info("🧪 Testing transcription service only...")
            result = await self._get_transcription_with_fallback(video_path)
            return {
                "success": True,
                "text_length": len(result.get('text', '')),
                "segments_count": len(result.get('segments', [])),
                "words_count": len(result.get('words', [])),
                "first_segments": result.get('segments', [])[:3]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_highlight_generation(self, video_path: str, options: ProcessingOptions) -> Dict[str, Any]:
        """Test highlight generation with detailed output"""
        try:
            logger.info("🧪 Testing highlight generation...")
            highlights = await self.analyze_video(video_path, options)
            
            result = []
            for i, highlight in enumerate(highlights):
                highlight_data = {
                    "highlight_index": i + 1,
                    "start_time": highlight.start_time,
                    "end_time": highlight.end_time,
                    "duration": highlight.end_time - highlight.start_time,
                    "title": highlight.title,
                    "score": highlight.score,
                    "has_transcription_segments": bool(highlight.transcription_segments),
                    "transcription_segments_count": len(highlight.transcription_segments) if highlight.transcription_segments else 0
                }
                
                # Add details about first segment
                if highlight.transcription_segments:
                    first_segment = highlight.transcription_segments[0]
                    highlight_data["first_segment"] = {
                        "text": first_segment.text,
                        "start": first_segment.start,
                        "end": first_segment.end,
                        "word_count": len(first_segment.words) if first_segment.words else 0
                    }
                
                result.append(highlight_data)
            
            return {"success": True, "highlights": result}
            
        except Exception as e:
            return {"success": False, "error": str(e)}