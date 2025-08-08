import os
import logging
import asyncio
import tempfile
import subprocess
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime

# Import global FFmpeg configuration first
from .ffmpeg_config import FFmpegConfig

# Import pydub
from pydub import AudioSegment
from pydub.utils import which

try:
    import openai
    if hasattr(openai, '__version__') and openai.__version__.startswith('1.'):
        CLIENT_TYPE = 'v1'
    else:
        CLIENT_TYPE = 'v0'
except ImportError:
    openai = None
    CLIENT_TYPE = None

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        logger.info("🔧 Initializing TranscriptionService...")

        # Use global FFmpeg configuration
        ffmpeg_configured = FFmpegConfig.configure()
        if ffmpeg_configured:
            logger.info(f"✅ Transcription service using global FFmpeg: {FFmpegConfig.get_ffmpeg_path()}")
        else:
            logger.warning("⚠️ FFmpeg not configured - transcription may fail")
        
        self.client = None
        self.http_client = None
        self.temp_dir = os.getenv('TEMP_DIR', 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            logger.error("❌ OPENAI_API_KEY not found")
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        if not openai:
            logger.error("❌ OpenAI library not installed")
            raise ImportError("OpenAI library is required. Install with: pip install openai")
        
        try:
            if CLIENT_TYPE == 'v1':
                import httpx
                import certifi
                
                # Create robust HTTP client with proper SSL and timeout settings
                self.http_client = httpx.Client(
                    verify=certifi.where(),
                    timeout=httpx.Timeout(60.0, connect=10.0),  # 60s total, 10s connect
                    limits=httpx.Limits(
                        max_connections=5,
                        max_keepalive_connections=2,
                        keepalive_expiry=30.0
                    )
                )
                
                self.client = openai.OpenAI(
                    api_key=api_key,
                    http_client=self.http_client,
                    max_retries=3,
                    timeout=60.0
                )
                logger.info("✅ OpenAI v1.x client initialized with robust settings")
            elif CLIENT_TYPE == 'v0':
                openai.api_key = api_key
                self.client = openai
                logger.info("✅ OpenAI v0.x client initialized")
            else:
                raise ValueError("Unable to determine OpenAI library version")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {str(e)}")
            raise
    
    def __del__(self):
        """Cleanup HTTP client on destruction"""
        if hasattr(self, 'http_client') and self.http_client:
            try:
                self.http_client.close()
            except:
                pass
    
    async def _ensure_connection_health(self):
        """Ensure the connection is healthy before making requests"""
        try:
            # Quick health check - list models with short timeout
            def _health_check():
                if CLIENT_TYPE == 'v1':
                    models = list(self.client.models.list())
                    return len(models) > 0
                elif CLIENT_TYPE == 'v0':
                    # For v0, we can't easily check models, so just return True
                    # Health check will be implicit when making actual transcription calls
                    return True
                else:
                    return False
            
            healthy = await asyncio.get_event_loop().run_in_executor(None, _health_check)
            if not healthy:
                logger.warning("⚠️ Connection health check failed")
                return False
            
            logger.debug("✅ Connection health check passed")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Connection health check error: {str(e)}")
            return False
    
    async def transcribe_audio(self, audio_path: str, language: str = "en") -> Dict[str, Any]:
        """Transcribe audio file using OpenAI Whisper API with strategy tracking"""
        strategy_results = []
        start_time = datetime.now()
        
        try:
            if not self.client:
                raise ValueError("OpenAI client not initialized")
            
            # Check connection health before starting
            logger.info("🔍 Checking connection health...")
            health_start = datetime.now()
            health_check = await self._ensure_connection_health()
            health_time = (datetime.now() - health_start).total_seconds()
            
            strategy_results.append({
                'strategy': 'OpenAI Connection Health Check',
                'status': 'SUCCESS' if health_check else 'FAILED',
                'time_taken': f'{health_time:.2f}s',
                'message': 'Connection healthy' if health_check else 'Connection health check failed, proceeding anyway'
            })
            
            if not health_check:
                logger.warning("⚠️ Connection health check failed, proceeding anyway...")
            
            logger.info(f"🎙️ Transcribing: {audio_path}")
            
            # Validate file
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            file_size = os.path.getsize(audio_path)
            logger.info(f"📁 File size: {file_size / (1024*1024):.1f} MB")
            
            # Extract audio if needed
            audio_file_path = await self._prepare_audio(audio_path)
            
            # Split if too large
            audio_chunks = await self._split_audio_if_needed(audio_file_path)
            
            # Transcribe all chunks
            all_segments = []
            all_words = []
            current_offset = 0
            
            for i, chunk_path in enumerate(audio_chunks):
                logger.info(f"🎙️ Transcribing chunk {i + 1}/{len(audio_chunks)}")
                
                chunk_result = await self._transcribe_chunk(chunk_path, language)
                
                if chunk_result:
                    # Adjust timestamps
                    for segment in chunk_result.get('segments', []):
                        segment['start'] += current_offset
                        segment['end'] += current_offset
                        
                        # Adjust word timestamps
                        if 'words' in segment:
                            for word in segment['words']:
                                word['start'] += current_offset
                                word['end'] += current_offset
                        
                        all_segments.append(segment)
                    
                    # Handle top-level words
                    for word in chunk_result.get('words', []):
                        word['start'] += current_offset
                        word['end'] += current_offset
                        all_words.append(word)
                    
                    # Update offset
                    chunk_duration = await self._get_audio_duration(chunk_path)
                    current_offset += chunk_duration
                
                # Cleanup chunk
                if chunk_path != audio_file_path:
                    self._cleanup_file(chunk_path)
            
            # Cleanup extracted audio
            if audio_file_path != audio_path:
                self._cleanup_file(audio_file_path)
            
            # Build final result
            result = {
                'text': " ".join([seg['text'] for seg in all_segments]),
                'segments': all_segments,
                'words': all_words,
                'language': language
            }
            
            logger.info(f"✅ Transcription complete: {len(all_segments)} segments, {len(all_words)} words")
            
            return result
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # INSTANT CONSOLE ERROR - Critical transcription failure
            instant_error_msg = f"\n🚨 INSTANT TRANSCRIPTION CRITICAL ERROR! 🚨\n🎤 Audio Path: {audio_path}\n🔙 Language: {language}\n⏰ Elapsed Time: {elapsed:.2f}s\n🔧 Error Type: {error_type}\n💬 Error Message: {error_msg}\n❌ Issue: Critical failure in transcription service\n🔍 This indicates API issues, network problems, or audio processing failures\n📁 Fallback: Video clips will be generated without captions\n" + "="*80
            
            # Log to both console and log file
            print(instant_error_msg)
            logger.error(f"🚨 INSTANT ERROR: {instant_error_msg}")
            
            logger.error(f"❌ Transcription error: {str(e)}")
            raise
    
    async def _prepare_audio(self, video_path: str) -> str:
        """Extract audio from video if needed"""
        try:
            # Check if already audio
            if video_path.lower().endswith(('.mp3', '.wav', '.m4a', '.aac')):
                return video_path
            
            logger.info("🎵 Extracting audio from video")
            
            def _extract():
                audio = AudioSegment.from_file(video_path)
                audio_path = os.path.join(self.temp_dir, f"audio_{os.getpid()}.wav")
                
                # Convert to mono 16kHz for optimal Whisper performance
                audio = audio.set_channels(1)
                audio = audio.set_frame_rate(16000)
                audio.export(audio_path, format="wav")
                
                return audio_path
            
            return await asyncio.get_event_loop().run_in_executor(None, _extract)
            
        except Exception as e:
            logger.error(f"❌ Audio extraction error: {str(e)}")
            raise
    
    async def _split_audio_if_needed(self, audio_path: str, max_size_mb: int = 24) -> List[str]:
        """Split audio into chunks if too large"""
        try:
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            
            if file_size_mb <= max_size_mb:
                return [audio_path]
            
            logger.info(f"✂️ Splitting audio ({file_size_mb:.1f} MB > {max_size_mb} MB)")
            
            def _split():
                audio = AudioSegment.from_file(audio_path)
                chunk_duration_ms = int((max_size_mb / file_size_mb) * len(audio) * 0.9)
                
                chunks = []
                for i in range(0, len(audio), chunk_duration_ms):
                    chunk = audio[i:i + chunk_duration_ms]
                    chunk_path = os.path.join(self.temp_dir, f"chunk_{os.getpid()}_{len(chunks)}.wav")
                    chunk.export(chunk_path, format="wav")
                    chunks.append(chunk_path)
                
                return chunks
            
            return await asyncio.get_event_loop().run_in_executor(None, _split)
            
        except Exception as e:
            logger.error(f"❌ Audio split error: {str(e)}")
            return [audio_path]
    
    async def _transcribe_chunk(self, audio_path: str, language: str) -> Dict[str, Any]:
        """Transcribe a single audio chunk with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🎙️ Transcription attempt {attempt + 1}/{max_retries}")
                
                def _transcribe():
                    with open(audio_path, 'rb') as audio_file:
                        if CLIENT_TYPE == 'v1':
                            # OpenAI v1.x API
                            response = self.client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                language=language,
                                response_format="verbose_json",
                                timestamp_granularities=["word", "segment"]
                            )
                        elif CLIENT_TYPE == 'v0':
                            # OpenAI v0.x API
                            response = openai.Audio.transcribe(
                                model="whisper-1",
                                file=audio_file,
                                language=language,
                                response_format="verbose_json"
                            )
                        else:
                            raise ValueError(f"Unsupported OpenAI client type: {CLIENT_TYPE}")
                        
                        # Process response (handle both v1 and v0 structures)
                        segments = []
                        words = []
                        
                        # Handle different response formats
                        if CLIENT_TYPE == 'v1':
                            # v1 API response object
                            response_segments = response.segments
                        else:
                            # v0 API response dict
                            response_segments = response.get('segments', [])
                        
                        for segment in response_segments:
                            # Handle both object attributes and dict access
                            if hasattr(segment, 'start'):
                                # v1 API object
                                seg_data = {
                                    'start': segment.start,
                                    'end': segment.end,
                                    'text': segment.text,
                                    'words': []
                                }
                            else:
                                # v0 API dict
                                seg_data = {
                                    'start': segment.get('start', 0),
                                    'end': segment.get('end', 0),
                                    'text': segment.get('text', ''),
                                    'words': []
                                }
                            
                            # Add word data to segment if available
                            segment_words = getattr(segment, 'words', segment.get('words', [])) if hasattr(segment, 'words') or isinstance(segment, dict) else []
                            
                            if segment_words:
                                for word in segment_words:
                                    if hasattr(word, 'start'):
                                        # v1 API object
                                        word_data = {
                                            'start': word.start,
                                            'end': word.end,
                                            'text': getattr(word, 'word', getattr(word, 'text', '')),
                                            'word': getattr(word, 'word', getattr(word, 'text', ''))
                                        }
                                    else:
                                        # v0 API dict
                                        word_data = {
                                            'start': word.get('start', 0),
                                            'end': word.get('end', 0),
                                            'text': word.get('word', word.get('text', '')),
                                            'word': word.get('word', word.get('text', ''))
                                        }
                                    seg_data['words'].append(word_data)
                                    words.append(word_data)
                            
                            segments.append(seg_data)
                        
                        # Also collect top-level words if available
                        top_level_words = getattr(response, 'words', response.get('words', [])) if hasattr(response, 'words') or isinstance(response, dict) else []
                        
                        if top_level_words:
                            for word in top_level_words:
                                if hasattr(word, 'start'):
                                    # v1 API object
                                    words.append({
                                        'start': word.start,
                                        'end': word.end,
                                        'text': getattr(word, 'word', getattr(word, 'text', '')),
                                        'word': getattr(word, 'word', getattr(word, 'text', ''))
                                    })
                                else:
                                    # v0 API dict
                                    words.append({
                                        'start': word.get('start', 0),
                                        'end': word.get('end', 0),
                                        'text': word.get('word', word.get('text', '')),
                                        'word': word.get('word', word.get('text', ''))
                                    })
                        
                        # Get response text (handle both v1 and v0 formats)
                        response_text = getattr(response, 'text', response.get('text', '')) if hasattr(response, 'text') or isinstance(response, dict) else ''
                        
                        return {
                            'text': response_text,
                            'segments': segments,
                            'words': words
                        }
                
                # Add timeout protection to transcription
                return await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, _transcribe),
                    timeout=120  # 2 minute timeout per chunk
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Transcription chunk timed out on attempt {attempt + 1}")
                
                # INSTANT CONSOLE ERROR - Transcription Timeout Fallback
                print(f"\n🚨 INSTANT TRANSCRIPTION TIMEOUT FALLBACK! 🚨")
                print(f"🎙️ Attempt: {attempt + 1}/{max_retries}")
                print(f"⏰ Timeout Duration: 2 minutes (120 seconds)")
                print(f"📁 Audio Chunk: {audio_path}")
                print(f"🔄 Fallback Reason: Transcription API took too long to respond")
                
                if attempt < max_retries - 1:
                    print(f"💡 Next Strategy: Will retry with exponential backoff ({retry_delay}s delay)")
                    print(f"⚡ Retrying transcription in {retry_delay} seconds...")
                    print("="*80)
                    
                    logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"❌ Final timeout after {max_retries} attempts - transcription failed")
                    print(f"💡 Fallback Result: Clips will be generated without captions/subtitles")
                    print("="*80)
                    
                    logger.error(f"❌ Transcription chunk timed out after {max_retries} attempts")
                    raise Exception("Transcription timed out after multiple attempts")
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if it's a retryable error
                retryable_errors = [
                    'ssl', 'connection', 'timeout', 'network', 'read error',
                    'bad record mac', 'connection reset', 'connection aborted'
                ]
                
                is_retryable = any(err in error_str for err in retryable_errors)
                
                if attempt < max_retries - 1 and is_retryable:
                    logger.warning(f"⚠️ Retryable error on attempt {attempt + 1}: {str(e)}")
                    
                    # INSTANT CONSOLE ERROR - Transcription Retryable Error Fallback
                    print(f"\n🚨 INSTANT TRANSCRIPTION RETRY FALLBACK! 🚨")
                    print(f"🎙️ Attempt: {attempt + 1}/{max_retries}")
                    print(f"🔧 Error Type: {type(e).__name__}")
                    print(f"💬 Error Message: {str(e)}")
                    print(f"📁 Audio Chunk: {audio_path}")
                    print(f"🔄 Fallback Reason: Network/connection issue - will retry with backoff")
                    
                    if 'ssl' in error_str:
                        print("💡 Issue: SSL/TLS connection error - network security issue")
                    elif 'connection' in error_str:
                        print("💡 Issue: Network connection problem - temporary connectivity issue")
                    elif 'timeout' in error_str:
                        print("💡 Issue: Request timeout - slow network or API overload")
                    elif 'network' in error_str:
                        print("💡 Issue: General network error - connectivity problem")
                    
                    print(f"⚡ Next Strategy: Will retry in {retry_delay} seconds with exponential backoff")
                    print("="*80)
                    
                    logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    # INSTANT CONSOLE ERROR - Final Transcription Failure
                    print(f"\n🚨 INSTANT TRANSCRIPTION FINAL FAILURE! 🚨")
                    print(f"🎙️ Final Attempt: {attempt + 1}/{max_retries}")
                    print(f"🔧 Error Type: {type(e).__name__}")
                    print(f"💬 Error Message: {str(e)}")
                    print(f"📁 Audio Chunk: {audio_path}")
                    print(f"❌ All retry attempts exhausted")
                    print(f"💡 Fallback Result: Clips will be generated without captions/subtitles")
                    print("="*80)
                    
                    logger.error(f"❌ Chunk transcription error (attempt {attempt + 1}): {str(e)}")
                    raise
    
    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds"""
        try:
            def _get_duration():
                audio = AudioSegment.from_file(audio_path)
                return len(audio) / 1000.0
            
            return await asyncio.get_event_loop().run_in_executor(None, _get_duration)
            
        except Exception as e:
            logger.error(f"❌ Duration error: {str(e)}")
            return 0.0
    
    def _cleanup_file(self, file_path: str):
        """Clean up temporary file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️ Cleaned: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup failed: {str(e)}")
    
    def find_quotable_moments(self, transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find quotable moments in transcript"""
        quotable_moments = []
        
        try:
            for segment in transcript.get('segments', []):
                text = segment.get('text', '').strip()
                if not text:
                    continue
                
                score = 0
                word_count = len(text.split())
                
                # Scoring logic
                if 5 <= word_count <= 15:
                    score += 20
                if text.endswith('?'):
                    score += 15
                if text.endswith('!'):
                    score += 10
                
                # Check for emotional words
                emotional_words = ['amazing', 'incredible', 'shocking', 'unbelievable']
                for word in emotional_words:
                    if word in text.lower():
                        score += 15
                
                if score >= 20:
                    quotable_moments.append({
                        'start': segment['start'],
                        'end': segment['end'],
                        'text': text,
                        'score': score
                    })
            
            return sorted(quotable_moments, key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Error finding quotes: {str(e)}")
            return []
    
    def detect_speech_energy(self, transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect high-energy speech moments"""
        energy_moments = []
        
        try:
            for segment in transcript.get('segments', []):
                text = segment.get('text', '').strip()
                if not text:
                    continue
                
                energy_score = 0
                words = text.split()
                
                # Calculate energy
                caps_words = sum(1 for word in words if word.isupper() and len(word) > 1)
                energy_score += caps_words * 10
                energy_score += text.count('!') * 15
                
                # High-energy words
                energy_words = ['yes', 'no', 'stop', 'go', 'now', 'amazing']
                for word in energy_words:
                    if word.lower() in text.lower():
                        energy_score += 10
                
                if energy_score >= 15:
                    energy_moments.append({
                        'start': segment['start'],
                        'end': segment['end'],
                        'text': text,
                        'energy_score': energy_score
                    })
            
            return sorted(energy_moments, key=lambda x: x['energy_score'], reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Error detecting energy: {str(e)}")
            return []
    
    async def test_api_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connection"""
        try:
            def _test():
                if CLIENT_TYPE == 'v1':
                    models = list(self.client.models.list())
                    whisper_models = [m for m in models if 'whisper' in m.id.lower()]
                    return {
                        "success": True,
                        "client_type": CLIENT_TYPE,
                        "models": len(models),
                        "whisper_available": len(whisper_models) > 0
                    }
                else:
                    raise ValueError("OpenAI v0.x not supported for production")
            
            return await asyncio.get_event_loop().run_in_executor(None, _test)
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "client_type": CLIENT_TYPE
            }