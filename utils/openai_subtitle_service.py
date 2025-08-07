import os
import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None
    OpenAI = None

from .config import config
from .models import TranscriptionSegment, WordTiming

logger = logging.getLogger(__name__)

class OpenAISubtitleService:
    """Service for generating AI-powered subtitles for video clips using OpenAI GPT"""
    
    def __init__(self):
        logger.info("🔧 Initializing OpenAI Subtitle Service...")
        
        if not OPENAI_AVAILABLE:
            logger.error("❌ OpenAI library not available")
            raise ImportError("OpenAI library is required. Install with: pip install openai")
        
        # Get API key from config
        api_key = config.OPENAI_API_KEY
        if not api_key:
            logger.error("❌ OPENAI_API_KEY not found in config")
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Initialize OpenAI client
        try:
            self.client = OpenAI(api_key=api_key)
            logger.info("✅ OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {str(e)}")
            raise
    
    async def generate_subtitles_for_clip(
        self,
        video_title: str,
        clip_title: str,
        clip_duration: float,
        start_time: float = 0.0,
        context: Optional[str] = None,
        style: str = "engaging"
    ) -> Dict[str, Any]:
        """
        Generate AI subtitles for a video clip
        
        Args:
            video_title: Original video title
            clip_title: Title of the clip
            clip_duration: Duration of the clip in seconds
            start_time: Start time of clip in original video
            context: Additional context about the video/clip
            style: Subtitle style (engaging, professional, casual, energetic)
        
        Returns:
            Dictionary with subtitle segments and metadata
        """
        try:
            logger.info(f"📝 Generating AI subtitles for clip: '{clip_title}' ({clip_duration}s)")
            
            # Create segments based on clip duration (aim for 2-4 second segments)
            segment_duration = min(3.5, clip_duration / 6)  # Aim for 6-8 segments per clip
            num_segments = max(3, int(clip_duration / segment_duration))
            
            # Generate subtitle content using GPT
            subtitle_content = await self._generate_subtitle_content(
                video_title, clip_title, clip_duration, num_segments, context, style
            )
            
            # Create timed segments
            segments = self._create_timed_segments(subtitle_content, clip_duration, num_segments)
            
            # Generate word-level timing (estimated)
            words = self._generate_word_timings(segments)
            
            result = {
                'text': ' '.join([seg['text'] for seg in segments]),
                'segments': segments,
                'words': words,
                'clip_title': clip_title,
                'style': style,
                'generated_at': datetime.now().isoformat(),
                'duration': clip_duration,
                'language': 'en'
            }
            
            logger.info(f"✅ Generated {len(segments)} subtitle segments with {len(words)} words")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating AI subtitles: {str(e)}")
            # Return fallback subtitles
            return self._generate_fallback_subtitles(clip_title, clip_duration)
    
    async def _generate_subtitle_content(
        self,
        video_title: str,
        clip_title: str,
        clip_duration: float,
        num_segments: int,
        context: Optional[str] = None,
        style: str = "engaging"
    ) -> List[str]:
        """Generate subtitle content using GPT"""
        
        # Build the prompt based on style
        style_prompts = {
            "engaging": "Create engaging, hook-worthy subtitles that capture attention and encourage viewers to keep watching. Use dynamic language and compelling phrases.",
            "professional": "Create professional, clear subtitles that convey information effectively. Use formal language and precise terminology.",
            "casual": "Create casual, conversational subtitles that feel natural and relatable. Use everyday language and friendly tone.",
            "energetic": "Create high-energy subtitles with excitement and enthusiasm. Use action words, caps for emphasis, and dynamic expressions.",
            "educational": "Create educational subtitles that explain concepts clearly. Use instructional language and helpful explanations."
        }
        
        prompt = f"""
Generate {num_segments} compelling subtitle segments for a {clip_duration:.1f}-second video clip.

Video Context:
- Original Video: "{video_title}"
- Clip Title: "{clip_title}"
- Duration: {clip_duration:.1f} seconds
{f"- Additional Context: {context}" if context else ""}

Style: {style_prompts.get(style, style_prompts["engaging"])}

Requirements:
1. Generate exactly {num_segments} subtitle segments
2. Each segment should be 3-8 words long
3. Segments should flow naturally and build narrative tension
4. Use the clip title as inspiration for the content
5. Make it suitable for social media (viral potential)
6. Avoid repetitive language between segments
7. Create a compelling hook that matches the clip title

Return ONLY a JSON array of strings, like:
["First subtitle segment", "Second subtitle segment", "Third subtitle segment", ...]
"""

        try:
            # Generate content using OpenAI
            def _generate():
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an expert subtitle writer for viral social media clips. Generate engaging, attention-grabbing subtitles that maximize viewer retention."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.8
                )
                return response.choices[0].message.content.strip()
            
            # Run in executor to avoid blocking
            response_text = await asyncio.get_event_loop().run_in_executor(None, _generate)
            
            # Parse the JSON response
            try:
                subtitle_segments = json.loads(response_text)
                if isinstance(subtitle_segments, list) and len(subtitle_segments) >= 3:
                    logger.info(f"✅ Generated {len(subtitle_segments)} AI subtitle segments")
                    return subtitle_segments[:num_segments]  # Ensure we don't exceed requested count
                else:
                    raise ValueError("Invalid response format")
            except (json.JSONDecodeError, ValueError) as parse_error:
                logger.warning(f"⚠️ Failed to parse GPT response, using fallback: {parse_error}")
                return self._generate_fallback_content(clip_title, num_segments)
                
        except Exception as e:
            logger.error(f"❌ OpenAI API error: {str(e)}")
            return self._generate_fallback_content(clip_title, num_segments)
    
    def _generate_fallback_content(self, clip_title: str, num_segments: int) -> List[str]:
        """Generate fallback subtitle content when AI fails"""
        
        # Create basic segments based on clip title
        title_words = clip_title.split()
        
        if num_segments <= 3:
            # Short clip
            segments = [
                "Check this out!",
                f"{' '.join(title_words[:3])}",
                f"{' '.join(title_words[3:6]) if len(title_words) > 3 else 'Amazing content!'}"
            ]
        elif num_segments <= 6:
            # Medium clip
            segments = [
                "You won't believe this!",
                f"{' '.join(title_words[:2])}",
                f"{' '.join(title_words[2:4]) if len(title_words) > 2 else 'This is incredible'}",
                f"{' '.join(title_words[4:6]) if len(title_words) > 4 else 'Watch until the end'}",
                "Mind-blowing results!",
                "Like and subscribe!"
            ]
        else:
            # Long clip
            segments = [
                "This will shock you!",
                f"{' '.join(title_words[:2])}",
                "Wait for it...",
                f"{' '.join(title_words[2:4]) if len(title_words) > 2 else 'Something amazing happens'}",
                "Here it comes!",
                f"{' '.join(title_words[4:6]) if len(title_words) > 4 else 'Unbelievable moment'}",
                "Did you see that?",
                "Share with friends!"
            ]
        
        return segments[:num_segments]
    
    def _create_timed_segments(
        self,
        subtitle_content: List[str],
        clip_duration: float,
        num_segments: int
    ) -> List[Dict[str, Any]]:
        """Create timed subtitle segments"""
        
        segments = []
        segment_duration = clip_duration / len(subtitle_content)
        
        for i, text in enumerate(subtitle_content):
            start_time = i * segment_duration
            end_time = min((i + 1) * segment_duration, clip_duration)
            
            segments.append({
                'start': round(start_time, 2),
                'end': round(end_time, 2),
                'text': text.strip(),
                'words': []  # Will be populated by word timing generation
            })
        
        return segments
    
    def _generate_word_timings(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate word-level timing for all segments"""
        
        all_words = []
        
        for segment in segments:
            words_in_segment = segment['text'].split()
            segment_duration = segment['end'] - segment['start']
            word_duration = segment_duration / max(1, len(words_in_segment))
            
            segment_words = []
            for j, word in enumerate(words_in_segment):
                word_start = segment['start'] + (j * word_duration)
                word_end = segment['start'] + ((j + 1) * word_duration)
                
                word_timing = {
                    'start': round(word_start, 2),
                    'end': round(word_end, 2),
                    'text': word,
                    'word': word
                }
                
                segment_words.append(word_timing)
                all_words.append(word_timing)
            
            # Add words to the segment
            segment['words'] = segment_words
        
        return all_words
    
    def _generate_fallback_subtitles(
        self,
        clip_title: str,
        clip_duration: float
    ) -> Dict[str, Any]:
        """Generate basic fallback subtitles when all else fails"""
        
        logger.warning("⚠️ Generating fallback subtitles")
        
        # Create 3-5 basic segments
        num_segments = min(5, max(3, int(clip_duration / 3)))
        
        fallback_texts = [
            "Check this out!",
            "Amazing content ahead",
            "You won't believe this",
            "Keep watching!",
            "Like and subscribe!"
        ][:num_segments]
        
        segments = []
        segment_duration = clip_duration / len(fallback_texts)
        
        for i, text in enumerate(fallback_texts):
            start_time = i * segment_duration
            end_time = min((i + 1) * segment_duration, clip_duration)
            
            segments.append({
                'start': round(start_time, 2),
                'end': round(end_time, 2),
                'text': text,
                'words': []
            })
        
        # Generate word timings
        words = self._generate_word_timings(segments)
        
        return {
            'text': ' '.join(fallback_texts),
            'segments': segments,
            'words': words,
            'clip_title': clip_title,
            'style': 'fallback',
            'generated_at': datetime.now().isoformat(),
            'duration': clip_duration,
            'language': 'en',
            'fallback': True
        }
    
    async def generate_multiple_clip_subtitles(
        self,
        clips: List[Dict[str, Any]],
        video_title: str,
        context: Optional[str] = None,
        style: str = "engaging"
    ) -> List[Dict[str, Any]]:
        """Generate subtitles for multiple clips efficiently"""
        
        logger.info(f"📝 Generating AI subtitles for {len(clips)} clips")
        
        subtitle_results = []
        
        # Process clips in batches to avoid rate limiting
        batch_size = 3
        
        for i in range(0, len(clips), batch_size):
            batch = clips[i:i + batch_size]
            batch_tasks = []
            
            for clip in batch:
                task = self.generate_subtitles_for_clip(
                    video_title=video_title,
                    clip_title=clip.get('title', f'Clip {i+1}'),
                    clip_duration=clip.get('duration', 30.0),
                    start_time=clip.get('start_time', 0.0),
                    context=context,
                    style=style
                )
                batch_tasks.append(task)
            
            # Execute batch
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"❌ Batch subtitle generation failed: {str(result)}")
                        # Add fallback result
                        subtitle_results.append(self._generate_fallback_subtitles("Clip", 30.0))
                    else:
                        subtitle_results.append(result)
                
                # Small delay between batches to respect rate limits
                if i + batch_size < len(clips):
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Batch processing error: {str(e)}")
                # Add fallback results for the entire batch
                for _ in batch:
                    subtitle_results.append(self._generate_fallback_subtitles("Clip", 30.0))
        
        logger.info(f"✅ Generated subtitles for {len(subtitle_results)} clips")
        return subtitle_results
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the OpenAI API connection"""
        
        try:
            def _test():
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "user", "content": "Test connection. Respond with 'OK'"}
                    ],
                    max_tokens=10
                )
                return response.choices[0].message.content.strip()
            
            result = await asyncio.get_event_loop().run_in_executor(None, _test)
            
            return {
                "success": True,
                "message": "OpenAI API connection successful",
                "response": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "OpenAI API connection failed"
            }

# Global instance
openai_subtitle_service = None

def get_openai_subtitle_service():
    """Get or create the OpenAI subtitle service instance"""
    global openai_subtitle_service
    
    if openai_subtitle_service is None:
        try:
            openai_subtitle_service = OpenAISubtitleService()
            logger.info("✅ OpenAI Subtitle Service initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI Subtitle Service: {str(e)}")
            raise
    
    return openai_subtitle_service
