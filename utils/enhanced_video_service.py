#!/usr/bin/env python3
"""
Enhanced Video Processing Service
Provides robust video clip generation with comprehensive error handling and fallback mechanisms.
"""

import logging
import asyncio
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from .models import ProcessingOptions, Highlight, ClipResult, TranscriptionSegment, WordTiming
from .transcription_service import TranscriptionService
from .video_processor import VideoProcessor
from .clip_analyzer import ClipAnalyzer

logger = logging.getLogger(__name__)


class EnhancedVideoService:
    """Enhanced video processing service with robust error handling"""
    
    def __init__(self):
        self.transcription_service = TranscriptionService()
        self.video_processor = VideoProcessor()
        self.clip_analyzer = ClipAnalyzer()
        logger.info("✅ Enhanced Video Service initialized")
    
    async def process_video_with_captions(
        self,
        video_path: str,
        options: ProcessingOptions,
        job_id: str,
        job_manager,
        transcript: Optional[Dict[str, Any]] = None,
        disable_assembly_ai: bool = True,
        enable_ai_enhancements: bool = False
    ) -> List[ClipResult]:
        """
        Process video with captions using multiple fallback strategies
        
        Args:
            video_path: Path to the video file
            options: Processing options
            job_id: Unique job identifier
            job_manager: Job manager instance
            disable_assembly_ai: Whether to disable AssemblyAI (use OpenAI Whisper instead)
        
        Returns:
            List of successfully created clips
        """
        request_id = job_id[:8]
        logger.info(f"🎬 [{request_id}] Starting enhanced video processing with comprehensive error logging")
        
        # Initialize strategy tracking with enhanced error logging
        all_strategy_results = []
        error_logger = self._create_enhanced_error_logger(request_id)
        
        try:
            # Step 1: Validate video file
            await self._validate_video_file(video_path, request_id)
            
            # Step 2: Get video duration and basic info
            video_duration = await self._get_video_duration(video_path)
            logger.info(f"📹 [{request_id}] Video duration: {video_duration:.1f}s")
            
            # Update progress
            await job_manager.update_job_status(
                job_id, "processing", 10.0,
                "Analyzing video content and generating transcription",
                "Content Analysis"
            )
            
            # Step 3: Use provided transcript or generate new one (with fallback)
            if transcript and transcript.get('segments'):
                logger.info(f"📝 [{request_id}] Using provided transcript with {len(transcript['segments'])} segments")
                all_strategy_results.append({
                    'step': 'Transcription',
                    'strategy': 'Provided Transcript',
                    'status': 'SUCCESS',
                    'time_taken': '0.0s',
                    'message': f'Using provided transcript with {len(transcript["segments"])} segments'
                })
            else:
                logger.info(f"🎙️ [{request_id}] No transcript provided, generating new transcription")
                transcript, transcription_strategies = await self._get_transcription_with_fallback(
                    video_path, request_id, disable_assembly_ai
                )
                all_strategy_results.extend(transcription_strategies)
            
            # Step 4: Generate highlights (with multiple fallback strategies)
            highlights, highlight_strategies = await self._generate_highlights_with_fallbacks(
                video_path, transcript, options, video_duration, request_id
            )
            all_strategy_results.extend(highlight_strategies)
            
            # Debug: Log transcription segments for each highlight
            for i, highlight in enumerate(highlights):
                if highlight.transcription_segments:
                    logger.info(f"📝 [{request_id}] Highlight {i+1} has {len(highlight.transcription_segments)} transcription segments")
                    for j, seg in enumerate(highlight.transcription_segments[:3]):  # Log first 3 segments
                        logger.debug(f"  Segment {j+1}: {seg.start:.2f}-{seg.end:.2f}s: '{seg.text[:50]}...'")
                else:
                    logger.warning(f"⚠️ [{request_id}] Highlight {i+1} has NO transcription segments!")
            
            if not highlights:
                logger.error(f"❌ [{request_id}] No highlights generated")
                raise Exception("Failed to generate any highlights from video content")
            
            # Update progress
            await job_manager.update_job_status(
                job_id, "processing", 40.0,
                f"Processing {len(highlights)} video clips with captions",
                "Video Processing"
            )
            
            # Step 5: Process clips with enhanced error handling
            clips = await self._process_clips_with_fallbacks(
                video_path, highlights, options, job_id, request_id
            )
            
            if not clips:
                logger.error(f"❌ [{request_id}] No clips were successfully created")
                raise Exception("Video processing failed - no clips were successfully created")
            
            logger.info(f"✅ [{request_id}] Successfully created {len(clips)} clips")
            
            # Enhanced logging of strategy results with detailed error information
            try:
                await job_manager.set_strategy_results(job_id, all_strategy_results)
                logger.info(f"📊 [{request_id}] Strategy results stored successfully")
                
                # Log comprehensive strategy summary to console for debugging
                self._log_strategy_summary_to_console(all_strategy_results, request_id)
                
            except Exception as strategy_error:
                logger.error(f"❌ [{request_id}] Failed to store strategy results: {str(strategy_error)}")
                import traceback
                logger.error(f"❌ [{request_id}] Strategy storage error traceback: {traceback.format_exc()}")
            
            return clips
            
        except Exception as e:
            logger.error(f"❌ [{request_id}] Enhanced video processing failed: {str(e)}")
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"❌ [{request_id}] Enhanced video processing error traceback:\n{error_traceback}")
            
            # Log final strategy results even on failure for debugging
            if all_strategy_results:
                self._log_strategy_summary_to_console(all_strategy_results, request_id, is_failure=True)
            
            raise
    
    async def _validate_video_file(self, video_path: str, request_id: str):
        """Validate video file exists and is readable"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        file_size = os.path.getsize(video_path)
        if file_size < 1024:  # Less than 1KB
            raise ValueError("Video file is too small or corrupted")
        
        logger.info(f"✅ [{request_id}] Video file validated: {file_size / (1024*1024):.1f}MB")
    
    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe"""
        try:
            import subprocess
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-show_entries',
                'format=duration', '-of', 'csv=p=0', video_path
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                logger.warning("⚠️ Failed to get video duration, using default")
                return 300.0  # 5 minute default
                
        except Exception as e:
            logger.warning(f"⚠️ Error getting video duration: {str(e)}")
            return 300.0
    
    async def _get_transcription_with_fallback(
        self, 
        video_path: str, 
        request_id: str,
        disable_assembly_ai: bool = True
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Get transcription with fallback mechanisms"""
        logger.info(f"🎙️ [{request_id}] Generating transcription (AssemblyAI disabled: {disable_assembly_ai})")
        
        strategy_results = []
        start_time = datetime.now()
        
        try:
            # Use OpenAI Whisper (since AssemblyAI is disabled) with enhanced error logging
            logger.info(f"🔊 [{request_id}] Using OpenAI Whisper for transcription")
            
            transcript = await asyncio.wait_for(
                self.transcription_service.transcribe_audio(video_path),
                timeout=300  # 5 minute timeout
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if transcript and transcript.get('segments'):
                logger.info(f"✅ [{request_id}] Transcription successful: {len(transcript['segments'])} segments")
                strategy_results.append({
                    'step': 'Transcription',
                    'strategy': 'OpenAI Whisper',
                    'status': 'SUCCESS',
                    'time_taken': f'{elapsed:.1f}s',
                    'message': f'Generated {len(transcript["segments"])} transcript segments'
                })
                return transcript, strategy_results
            else:
                logger.error(f"❌ [{request_id}] Transcription returned no segments")
                strategy_results.append({
                    'step': 'Transcription',
                    'strategy': 'OpenAI Whisper',
                    'status': 'FAILED',
                    'time_taken': f'{elapsed:.1f}s',
                    'message': 'Transcription returned no segments',
                    'error': 'No segments generated from transcription'
                })
                return self._create_empty_transcript(), strategy_results
                
        except asyncio.TimeoutError:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [{request_id}] Transcription timed out after 5 minutes")
            # Use the error_logger from the outer scope
            if 'error_logger' in locals():
                error_logger.log_strategy_timeout('OpenAI Whisper', 'Transcription', 300)
            strategy_results.append({
                'step': 'Transcription',
                'strategy': 'OpenAI Whisper',
                'status': 'TIMEOUT',
                'time_taken': f'{elapsed:.1f}s',
                'message': 'Transcription timed out after 5 minutes'
            })
            return self._create_empty_transcript(), strategy_results
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [{request_id}] Transcription failed: {str(e)}, continuing without captions")
            # Use the error_logger from the outer scope
            if 'error_logger' in locals():
                error_logger.log_strategy_error('OpenAI Whisper', 'Transcription', e, {
                    'video_path': video_path,
                    'disable_assembly_ai': disable_assembly_ai,
                    'elapsed_time': elapsed
                })
            strategy_results.append({
                'step': 'Transcription',
                'strategy': 'OpenAI Whisper',
                'status': 'FAILED',
                'time_taken': f'{elapsed:.1f}s',
                'message': f'Transcription failed: {str(e)}',
                'error': str(e)
            })
            return self._create_empty_transcript(), strategy_results
    
    def _create_empty_transcript(self) -> Dict[str, Any]:
        """Create empty transcript for fallback"""
        return {
            'text': '',
            'segments': [],
            'words': [],
            'language': 'en'
        }
    
    async def _generate_highlights_with_fallbacks(
        self,
        video_path: str,
        transcript: Dict[str, Any],
        options: ProcessingOptions,
        video_duration: float,
        request_id: str
    ) -> tuple[List[Highlight], List[Dict[str, Any]]]:
        """Generate highlights with multiple fallback strategies"""
        
        strategy_results = []
        
        # Strategy 1: Try AI analysis first with enhanced error logging
        start_time = datetime.now()
        try:
            logger.info(f"🤖 [{request_id}] Attempting AI-based highlight generation")
            highlights = await asyncio.wait_for(
                self.clip_analyzer.analyze_video(video_path, options),
                timeout=180  # 3 minute timeout
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if highlights and len(highlights) > 0:
                # Enhance AI highlights with transcription data
                if transcript.get('segments'):
                    highlights = self._enhance_highlights_with_transcription(
                        highlights, transcript, request_id
                    )
                logger.info(f"✅ [{request_id}] AI analysis generated {len(highlights)} highlights")
                strategy_results.append({
                    'step': 'Highlight Generation',
                    'strategy': 'AI Analysis',
                    'status': 'SUCCESS',
                    'time_taken': f'{elapsed:.1f}s',
                    'message': f'Generated {len(highlights)} AI-based highlights'
                })
                return highlights, strategy_results
                
        except asyncio.TimeoutError:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [{request_id}] AI analysis timed out after 3 minutes")
            error_logger.log_strategy_timeout('AI Analysis', 'Highlight Generation', 180)
            strategy_results.append({
                'step': 'Highlight Generation',
                'strategy': 'AI Analysis',
                'status': 'TIMEOUT',
                'time_taken': f'{elapsed:.1f}s',
                'message': 'AI analysis timed out after 3 minutes'
            })
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [{request_id}] AI analysis failed: {str(e)}, using fallback")
            error_logger.log_strategy_error('AI Analysis', 'Highlight Generation', e, {
                'video_path': video_path,
                'options': str(options),
                'elapsed_time': elapsed
            })
            strategy_results.append({
                'step': 'Highlight Generation',
                'strategy': 'AI Analysis',
                'status': 'FAILED',
                'time_taken': f'{elapsed:.1f}s',
                'message': f'AI analysis failed: {str(e)}',
                'error': str(e)
            })
        
        # Strategy 2: Transcription-based highlights with enhanced error logging
        if transcript.get('segments'):
            start_time = datetime.now()
            try:
                logger.info(f"📝 [{request_id}] Generating transcription-based highlights")
                highlights = self._create_transcription_based_highlights(
                    transcript, options, video_duration, request_id
                )
                elapsed = (datetime.now() - start_time).total_seconds()
                
                if highlights:
                    logger.info(f"✅ [{request_id}] Created {len(highlights)} transcription-based highlights")
                    strategy_results.append({
                        'step': 'Highlight Generation',
                        'strategy': 'Transcription-Based',
                        'status': 'SUCCESS',
                        'time_taken': f'{elapsed:.1f}s',
                        'message': f'Generated {len(highlights)} transcription-based highlights'
                    })
                    return highlights, strategy_results
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.error(f"❌ [{request_id}] Transcription-based generation failed: {str(e)}")
                error_logger.log_strategy_error('Transcription-Based', 'Highlight Generation', e, {
                    'transcript_segments': len(transcript.get('segments', [])),
                    'video_duration': video_duration,
                    'options': str(options),
                    'elapsed_time': elapsed
                })
                strategy_results.append({
                    'step': 'Highlight Generation',
                    'strategy': 'Transcription-Based',
                    'status': 'FAILED',
                    'time_taken': f'{elapsed:.1f}s',
                    'message': f'Transcription-based generation failed: {str(e)}',
                    'error': str(e)
                })
        
        # Strategy 3: Time-based fallback highlights
        start_time = datetime.now()
        logger.info(f"⏰ [{request_id}] Using time-based fallback highlights")
        highlights = self._create_time_based_highlights(options, video_duration, request_id)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        strategy_results.append({
            'step': 'Highlight Generation',
            'strategy': 'Time-Based Fallback',
            'status': 'SUCCESS',
            'time_taken': f'{elapsed:.1f}s',
            'message': f'Generated {len(highlights)} fallback highlights with captions'
        })
        
        return highlights, strategy_results
    
    def _enhance_highlights_with_transcription(
        self,
        highlights: List[Highlight],
        transcript: Dict[str, Any],
        request_id: str
    ) -> List[Highlight]:
        """Enhance AI-generated highlights with transcription data"""
        
        segments = transcript.get('segments', [])
        words = transcript.get('words', [])
        
        for i, highlight in enumerate(highlights):
            try:
                # Find transcript segments that overlap with this highlight
                transcription_segments = []
                
                for seg in segments:
                    seg_start = seg.get('start', 0)
                    seg_end = seg.get('end', 0)
                    
                    # Check for overlap
                    if seg_start < highlight.end_time and seg_end > highlight.start_time:
                        # Adjust timing to be relative to highlight start
                        adjusted_start = max(0, seg_start - highlight.start_time)
                        adjusted_end = min(
                            highlight.end_time - highlight.start_time,
                            seg_end - highlight.start_time
                        )
                        
                        if adjusted_end > adjusted_start:
                            # Create word timings for this segment
                            word_timings = self._extract_word_timings_for_segment(
                                seg, words, highlight.start_time, highlight.end_time
                            )
                            
                            transcription_segments.append(TranscriptionSegment(
                                start=adjusted_start,
                                end=adjusted_end,
                                text=seg.get('text', ''),
                                words=word_timings
                            ))
                
                highlight.transcription_segments = transcription_segments
                logger.debug(f"📝 [{request_id}] Enhanced highlight {i+1} with {len(transcription_segments)} segments")
                
            except Exception as e:
                logger.warning(f"⚠️ [{request_id}] Failed to enhance highlight {i+1}: {str(e)}")
                highlight.transcription_segments = []
        
        return highlights
    
    def _extract_word_timings_for_segment(
        self,
        segment: Dict[str, Any],
        all_words: List[Dict[str, Any]],
        highlight_start: float,
        highlight_end: float
    ) -> List[WordTiming]:
        """Extract word timings for a specific segment"""
        
        word_timings = []
        seg_start = segment.get('start', 0)
        seg_end = segment.get('end', 0)
        
        # First try segment-level words
        if segment.get('words'):
            for word_dict in segment['words']:
                word_start = word_dict.get('start', 0)
                word_end = word_dict.get('end', 0)
                
                if word_start < highlight_end and word_end > highlight_start:
                    adjusted_start = max(0, word_start - highlight_start)
                    adjusted_end = min(highlight_end - highlight_start, word_end - highlight_start)
                    
                    if adjusted_end > adjusted_start:
                        word_timings.append(WordTiming(
                            start=adjusted_start,
                            end=adjusted_end,
                            text=word_dict.get('word', word_dict.get('text', '')),
                            word=word_dict.get('word', word_dict.get('text', ''))
                        ))
        
        # Fallback to top-level words if no segment words
        elif all_words:
            for word_dict in all_words:
                word_start = word_dict.get('start', 0)
                word_end = word_dict.get('end', 0)
                
                # Check if word is within segment timeframe AND highlight timeframe
                if (seg_start <= word_start < seg_end and 
                    word_start < highlight_end and word_end > highlight_start):
                    
                    adjusted_start = max(0, word_start - highlight_start)
                    adjusted_end = min(highlight_end - highlight_start, word_end - highlight_start)
                    
                    if adjusted_end > adjusted_start:
                        word_timings.append(WordTiming(
                            start=adjusted_start,
                            end=adjusted_end,
                            text=word_dict.get('word', word_dict.get('text', '')),
                            word=word_dict.get('word', word_dict.get('text', ''))
                        ))
        
        return word_timings
    
    def _create_transcription_based_highlights(
        self,
        transcript: Dict[str, Any],
        options: ProcessingOptions,
        video_duration: float,
        request_id: str
    ) -> List[Highlight]:
        """Create highlights based on transcription content"""
        
        segments = transcript.get('segments', [])
        if not segments:
            return []
        
        highlights = []
        clip_count = min(options.clipCount or 3, 5)
        
        # Group segments into clips
        segments_per_clip = max(1, len(segments) // clip_count)
        
        for i in range(clip_count):
            start_idx = i * segments_per_clip
            end_idx = min((i + 1) * segments_per_clip, len(segments))
            
            if start_idx >= len(segments):
                break
            
            clip_segments = segments[start_idx:end_idx]
            
            # Calculate clip boundaries
            clip_start = clip_segments[0]['start']
            clip_end = clip_segments[-1]['end']
            
            # Ensure reasonable clip length (30-60 seconds)
            clip_duration = clip_end - clip_start
            if clip_duration < 30:
                # Extend clip
                extension = (30 - clip_duration) / 2
                clip_start = max(0, clip_start - extension)
                clip_end = min(video_duration, clip_end + extension)
            elif clip_duration > 60:
                # Limit clip length
                clip_end = clip_start + 60
            
            # Create transcription segments for this highlight
            transcription_segments = []
            for seg in clip_segments:
                adjusted_start = max(0, seg['start'] - clip_start)
                adjusted_end = min(clip_end - clip_start, seg['end'] - clip_start)
                
                if adjusted_end > adjusted_start:
                    # Extract word timings
                    word_timings = self._extract_word_timings_for_segment(
                        seg, transcript.get('words', []), clip_start, clip_end
                    )
                    
                    transcription_segments.append(TranscriptionSegment(
                        start=adjusted_start,
                        end=adjusted_end,
                        text=seg.get('text', ''),
                        words=word_timings
                    ))
            
            # Generate title from transcript content
            title = self._generate_title_from_segments(clip_segments)
            
            highlights.append(Highlight(
                start_time=clip_start,
                end_time=clip_end,
                title=title,
                score=0.8 - (i * 0.1),
                transcription_segments=transcription_segments
            ))
        
        return highlights
    
    def _create_enhanced_error_logger(self, request_id: str):
        """Create enhanced error logger for comprehensive strategy failure tracking"""
        class EnhancedErrorLogger:
            def __init__(self, request_id):
                self.request_id = request_id
                self.error_count = 0
                
            def log_strategy_error(self, strategy_name: str, step: str, error: Exception, context: dict = None):
                """Log detailed strategy error information to console"""
                self.error_count += 1
                error_type = type(error).__name__
                error_msg = str(error)
                
                logger.error(f"❌ STRATEGY FAILURE #{self.error_count} [{self.request_id}] {step} - {strategy_name}")
                logger.error(f"   📋 Error Type: {error_type}")
                logger.error(f"   💬 Error Message: {error_msg}")
                
                if context:
                    logger.error(f"   🔍 Context: {json.dumps(context, indent=2)}")
                
                # Log full traceback for critical debugging
                import traceback
                traceback_str = traceback.format_exc()
                logger.error(f"   📚 Full Traceback:\n{traceback_str}")
                
                # Log to console separately for immediate visibility
                print(f"\n🚨 CLIP CREATION ERROR #{self.error_count} - {strategy_name} 🚨")
                print(f"Step: {step}")
                print(f"Error: {error_type} - {error_msg}")
                if context:
                    print(f"Context: {context}")
                print(f"Traceback: {traceback_str}")
                print("="*80)
                
            def log_strategy_timeout(self, strategy_name: str, step: str, timeout_seconds: int):
                """Log strategy timeout with detailed information"""
                self.error_count += 1
                logger.error(f"⏱️ STRATEGY TIMEOUT #{self.error_count} [{self.request_id}] {step} - {strategy_name}")
                logger.error(f"   ⏰ Timeout Duration: {timeout_seconds} seconds")
                
                print(f"\n🚨 CLIP CREATION TIMEOUT #{self.error_count} - {strategy_name} 🚨")
                print(f"Step: {step}")
                print(f"Timeout: {timeout_seconds} seconds")
                print("="*80)
        
        return EnhancedErrorLogger(request_id)
    
    def _log_strategy_summary_to_console(self, strategy_results: List[Dict[str, Any]], request_id: str, is_failure: bool = False):
        """Log comprehensive strategy summary to console for debugging"""
        try:
            status_prefix = "❌ FAILED" if is_failure else "✅ COMPLETED"
            print(f"\n🚨 {status_prefix} CLIP CREATION STRATEGY SUMMARY [{request_id}] 🚨")
            print("="*100)
            
            # Count strategy results by status
            success_count = len([r for r in strategy_results if r.get('status') == 'SUCCESS'])
            failed_count = len([r for r in strategy_results if r.get('status') == 'FAILED'])
            timeout_count = len([r for r in strategy_results if r.get('status') == 'TIMEOUT'])
            
            print(f"📊 OVERALL STATISTICS:")
            print(f"   ✅ Successful Strategies: {success_count}")
            print(f"   ❌ Failed Strategies: {failed_count}")
            print(f"   ⏱️ Timed Out Strategies: {timeout_count}")
            print(f"   📈 Total Strategies: {len(strategy_results)}")
            print(f"   🎯 Success Rate: {(success_count/len(strategy_results)*100) if strategy_results else 0:.1f}%")
            print()
            
            # Group by step for better organization
            steps = {}
            for result in strategy_results:
                step = result.get('step', 'Unknown')
                if step not in steps:
                    steps[step] = []
                steps[step].append(result)
            
            # Log each step with its strategies
            for step_name, step_results in steps.items():
                print(f"🔄 STEP: {step_name.upper()}")
                print("-" * 50)
                
                for i, result in enumerate(step_results, 1):
                    status = result.get('status', 'UNKNOWN')
                    strategy = result.get('strategy', 'Unknown Strategy')
                    time_taken = result.get('time_taken', '0.0s')
                    message = result.get('message', 'No message')
                    
                    status_emoji = {
                        'SUCCESS': '✅',
                        'FAILED': '❌',
                        'TIMEOUT': '⏱️'
                    }.get(status, '❓')
                    
                    print(f"   {i}. {status_emoji} {strategy}")
                    print(f"      ⏰ Time: {time_taken}")
                    print(f"      💬 Message: {message}")
                    
                    # Log additional error details for failed strategies
                    if status == 'FAILED' and 'error' in result:
                        print(f"      🚨 Error: {result['error']}")
                    
                    print()
            
            print("="*100)
            print(f"🏁 END STRATEGY SUMMARY [{request_id}]")
            print()
            
        except Exception as summary_error:
            logger.error(f"❌ Failed to log strategy summary: {str(summary_error)}")
            print(f"\n❌ Failed to log strategy summary: {str(summary_error)}")
    
    def _create_time_based_highlights(
        self,
        options: ProcessingOptions,
        video_duration: float,
        request_id: str
    ) -> List[Highlight]:
        """Create time-based highlights as ultimate fallback WITH fallback captions"""
        
        highlights = []
        clip_count = min(options.clipCount or 3, 5)
        clip_duration = 45  # 45 second clips
        
        # Distribute clips evenly across video
        interval = max(clip_duration, video_duration / (clip_count + 1))
        
        # Enhanced fallback captions when no transcription is available
        fallback_captions = [
            "🎬 Amazing content ahead!",
            "⚡ Don't miss this moment!", 
            "🔥 This is incredible!",
            "✨ Watch closely!",
            "💫 Pure entertainment!",
            "🌟 You won't believe this!",
            "⭐ Absolutely stunning!",
            "🎯 Pay attention here!",
            "🚀 Mind-blowing moment!",
            "💯 This is epic!"
        ]
        
        for i in range(clip_count):
            start_time = i * interval
            end_time = min(start_time + clip_duration, video_duration)
            
            if start_time >= video_duration:
                break
            
            # Create fallback transcription segments with engaging captions
            duration = end_time - start_time
            segments_per_highlight = 3  # 3 caption segments per highlight  
            segment_duration = duration / segments_per_highlight
            
            transcription_segments = []
            for j in range(segments_per_highlight):
                seg_start = j * segment_duration
                seg_end = min((j + 1) * segment_duration, duration)
                
                # Use cycling fallback captions
                caption_text = fallback_captions[(i * segments_per_highlight + j) % len(fallback_captions)]
                
                transcription_segments.append(TranscriptionSegment(
                    start=seg_start,
                    end=seg_end,
                    text=caption_text,
                    words=[]
                ))
            
            highlights.append(Highlight(
                start_time=start_time,
                end_time=end_time,
                title=f"Highlight {i+1}",
                score=0.7,
                transcription_segments=transcription_segments  # NOW WITH CAPTIONS!
            ))
        
        logger.info(f"⏰ [{request_id}] Created {len(highlights)} time-based highlights WITH fallback captions")
        return highlights
    
    def _generate_title_from_segments(self, segments: List[Dict[str, Any]]) -> str:
        """Generate a meaningful title from transcript segments"""
        
        if not segments:
            return "Video Highlight"
        
        # Combine text from segments
        full_text = " ".join([seg.get('text', '').strip() for seg in segments])
        
        # Create a short title (first few words)
        words = full_text.split()
        if len(words) > 5:
            title = " ".join(words[:5]) + "..."
        else:
            title = full_text
        
        return title or "Video Highlight"
    
    async def _process_clips_with_fallbacks(
        self,
        video_path: str,
        highlights: List[Highlight],
        options: ProcessingOptions,
        job_id: str,
        request_id: str
    ) -> List[ClipResult]:
        """Process clips with fallback mechanisms"""
        
        logger.info(f"🎥 [{request_id}] Processing {len(highlights)} clips")
        
        # Create enhanced error logger for this method
        error_logger = self._create_enhanced_error_logger(request_id)
        
        try:
            # Process clips with timeout and enhanced error logging
            logger.info(f"🎥 [{request_id}] Starting video clip processing with {len(highlights)} highlights")
            clips = await asyncio.wait_for(
                self.video_processor.process_highlights(
                    video_path, highlights, options, job_id
                ),
                timeout=1200  # 20 minute timeout
            )
            
            if clips:
                logger.info(f"✅ [{request_id}] Successfully processed {len(clips)} clips")
                return clips
            else:
                # INSTANT CONSOLE ERROR - No clips returned
                instant_error_msg = f"\n🚨 INSTANT VIDEO PROCESSING ERROR: NO CLIPS RETURNED! 🚨\n🎥 Request ID: {request_id}\n📏 Video Path: {video_path}\n🔢 Highlights Count: {len(highlights)}\n⚙️ Options: {options}\n❌ Issue: Video processor completed but returned zero clips\n🔍 This usually indicates FFmpeg processing errors or format issues\n" + "="*80
                
                # Log to both console and log file
                print(instant_error_msg)
                logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
                
                logger.error(f"❌ [{request_id}] Video processor returned no clips")
                error_logger.log_strategy_error('Video Processor', 'Clip Processing', 
                    Exception("Video processor returned no clips"), {
                        'highlights_count': len(highlights),
                        'video_path': video_path,
                        'options': str(options)
                    })
                raise Exception("Video processor returned no clips")
                
        except asyncio.TimeoutError:
            # INSTANT CONSOLE ERROR - Timeout
            print(f"\n🚨 INSTANT VIDEO PROCESSING ERROR: TIMEOUT! 🚨")
            print(f"⏱️ Request ID: {request_id}")
            print(f"📏 Video Path: {video_path}")
            print(f"🔢 Highlights Count: {len(highlights)}")
            print(f"⏰ Timeout Duration: 20 minutes (1200 seconds)")
            print("❌ Issue: Video processing took too long")
            print("🔍 This may indicate complex video or insufficient resources")
            print("="*80)
            
            logger.error(f"❌ [{request_id}] Clip processing timed out after 20 minutes")
            error_logger.log_strategy_timeout('Video Processor', 'Clip Processing', 1200)
            raise Exception("Video processing timed out - video may be too complex")
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # INSTANT CONSOLE ERROR - General processing failure
            print(f"\n🚨 INSTANT VIDEO PROCESSING ERROR: CLIP PROCESSING FAILED! 🚨")
            print(f"🎥 Request ID: {request_id}")
            print(f"📏 Video Path: {video_path}")
            print(f"🔢 Highlights Count: {len(highlights)}")
            print(f"🔧 Error Type: {error_type}")
            print(f"💬 Error Message: {error_msg}")
            print(f"⚙️ Options: {options}")
            
            # Show critical error details for common issues
            if 'ffmpeg' in error_msg.lower():
                print("⚙️ Issue: FFmpeg processing error")
            elif 'memory' in error_msg.lower():
                print("💾 Issue: Memory/resource limitation")
            elif 'timeout' in error_msg.lower():
                print("⏰ Issue: Processing timeout")
            elif 'not found' in error_msg.lower():
                print("🔍 Issue: File or resource not found")
            
            # Full traceback
            import traceback
            traceback_str = traceback.format_exc()
            print(f"Traceback: {traceback_str}")
            print("="*80)
            
            logger.error(f"❌ [{request_id}] Clip processing failed: {str(e)}")
            error_logger.log_strategy_error('Video Processor', 'Clip Processing', e, {
                'highlights_count': len(highlights),
                'video_path': video_path,
                'options': str(options)
            })
            raise Exception(f"Video processing failed: {str(e)}")
