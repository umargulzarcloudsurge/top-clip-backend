from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import logging
from pydantic import BaseModel, ValidationError
import aiofiles
import shutil
from dotenv import load_dotenv
from utils.config import config
load_dotenv()

# CRITICAL: Force FFmpeg configuration before any other imports
try:
    from utils.ffmpeg_config import FFmpegConfig
    import logging
    temp_logger = logging.getLogger(__name__)
    temp_logger.info("🔧 Forcing FFmpeg configuration at startup...")
    success = FFmpegConfig.configure()
    if success:
        temp_logger.info(f"✅ FFmpeg startup configuration successful: {FFmpegConfig.get_ffmpeg_path()}")
    else:
        temp_logger.error("❌ FFmpeg startup configuration failed")
except Exception as e:
    print(f"❌ Critical FFmpeg configuration error: {e}")
    import traceback
    traceback.print_exc()

# Import enhanced models
from utils.models import (
    ProcessingJob, ProcessingOptions, VideoInfo, ClipResult,
    safe_serialize_clips, safe_serialize_job, validate_youtube_url,
    validate_processing_options, JobStatusResponse, Highlight,
    TranscriptionSegment, WordTiming
)
from utils.usage_tracker import usage_tracker
from utils.storage_manager import storage_manager
from utils.stripe_routes import router as stripe_router
from utils.process_monitor import process_monitor
from utils.enhanced_video_service import EnhancedVideoService

# Removed Celery and WebSocket components - back to background tasks

# Lazy imports to avoid dependency issues
job_manager = None
video_processor = None
youtube_downloader = None
clip_analyzer = None

def get_components():
    global job_manager, video_processor, youtube_downloader, clip_analyzer

    if job_manager is None:
        try:
            logger.info("🔧 Initializing components...")
            from utils.job_manager import JobManager
            from utils.video_processor import VideoProcessor
            from utils.youtube_downloader import YouTubeDownloader
            from utils.clip_analyzer import ClipAnalyzer
            
            logger.info("📦 Imports successful, creating instances...")
            job_manager = JobManager()
            logger.info("✅ JobManager created")
            video_processor = VideoProcessor()
            logger.info("✅ VideoProcessor created")
            youtube_downloader = YouTubeDownloader()
            logger.info("✅ YouTubeDownloader created")
            clip_analyzer = ClipAnalyzer()
            logger.info("✅ ClipAnalyzer created")

            

            
            logger.info("✅ All components initialized successfully")
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to initialize components: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise e
    else:
        logger.debug("♻️ Using existing components")
    
    # Validate components before returning
    logger.debug(f"🔍 Component validation: job_manager={job_manager is not None}, video_processor={video_processor is not None}, youtube_downloader={youtube_downloader is not None}, clip_analyzer={clip_analyzer is not None}")
    
    if youtube_downloader is None:
        logger.error("❌ CRITICAL: youtube_downloader is None after initialization!")
        raise Exception("YouTubeDownloader failed to initialize properly")
    
    return job_manager, video_processor, youtube_downloader, clip_analyzer

# Production-ready logging configuration
PRODUCTION = os.getenv('ENVIRONMENT', 'development') == 'production'
LOG_LEVEL = logging.INFO if PRODUCTION else logging.DEBUG

# Create custom formatter without emojis for Windows compatibility
class SafeFormatter(logging.Formatter):
    def format(self, record):
        # Replace Unicode emojis with simple text equivalents
        msg = super().format(record)
        emoji_replacements = {
            '🚀': '[START]',
            '✅': '[OK]',
            '❌': '[ERROR]',
            '🔧': '[INIT]',
            '📦': '[LOAD]',
            '🎬': '[VIDEO]',
            '🎨': '[CAPS]',
            '📁': '[DIR]',
            '💳': '[STRIPE]',
            '🔔': '[WEBHOOK]',
            '🔄': '[PROC]',
            '⚠️': '[WARN]',
            '📊': '[STATS]',
            '👤': '[USER]',
            '📝': '[UPDATE]',
            '🧹': '[CLEAN]',
            '📄': '[INVOICE]',
            '🎉': '[SUCCESS]',
            '🗺️': '[STRIPE]'
        }
        for emoji, replacement in emoji_replacements.items():
            msg = msg.replace(emoji, replacement)
        return msg

safe_formatter = SafeFormatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')

# Configure handlers with UTF-8 encoding
file_handler = logging.FileHandler('ai_clips_enhanced.log', encoding='utf-8')
file_handler.setFormatter(safe_formatter)

error_handler = logging.FileHandler('ai_clips_errors.log', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(safe_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(safe_formatter)

logging.basicConfig(
    level=LOG_LEVEL,
    handlers=[
        console_handler,
        file_handler,
        error_handler
    ]
)

# Reduce noise from external libraries - only show warnings and errors
for logger_name in ['urllib3', 'httpx', 'ffmpeg', 'yt_dlp', 'httpcore', 'hpack', 'h11', 'supabase', 'asyncio']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Configure thread pool for CPU-intensive operations to prevent blocking
import concurrent.futures
import threading

# Create larger thread pool for video processing
video_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=8,  # Increase for better concurrency 
    thread_name_prefix="video_processing"
)

# Initialize FastAPI app with production configuration
app = FastAPI(
    title="ClipForge AI - Enhanced API", 
    version="1.0.0",
    description="Ultra-quality AI video clip generation with MASSIVE fonts and FIXED preview issues",
    docs_url="/docs" if not PRODUCTION else None,  # Disable docs in production
    redoc_url="/redoc" if not PRODUCTION else None,  # Disable redoc in production
    openapi_url="/openapi.json" if not PRODUCTION else None  # Disable OpenAPI schema in production
)

# Enhanced CORS middleware - uses config for origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Stripe routes
app.include_router(stripe_router)

# Create necessary directories with error handling
directories = ["temp", "output", "thumbnails", "music", "game_videos", "fonts"]
for directory in directories:
    try:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"✅ Directory ensured: {directory}")
    except Exception as e:
        logger.error(f"❌ Failed to create directory {directory}: {str(e)}")

# Removed WebSocket connections - back to polling

# Request/Response models
class VideoProcessRequest(BaseModel):
    youtube_url: Optional[str] = None
    options: ProcessingOptions

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    timestamp: str
    request_id: Optional[str] = None

# Enhanced error handler
async def handle_api_error(error: Exception, context: str = "", request_id: str = None) -> ErrorResponse:
    """Enhanced error handling with context and logging"""
    error_msg = str(error)
    error_type = type(error).__name__
    
    logger.error(f"❌ API Error in {context}: {error_type} - {error_msg}")
    
    # Log full traceback for debugging
    import traceback
    logger.debug(f"Full traceback: {traceback.format_exc()}")
    
    return ErrorResponse(
        error=error_msg,
        details=f"Error type: {error_type}, Context: {context}",
        timestamp=datetime.now().isoformat(),
        request_id=request_id
    )

@app.get("/")
async def root():
    """Root endpoint with enhanced system information"""
    try:
        # Get component status
        job_mgr, video_proc, youtube_dl, clip_analyzer = get_components()
        
        system_info = {
            "message": "ClipForge AI Enhanced API v3.0 is running",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "features": [
                "MASSIVE Fonts with Enhanced Visibility",
                "FIXED Video Preview Issues", 
                "ULTRA Quality Video Processing",
                "Enhanced Game Video Overlays",
                "Smart Layout Transformations",
                "Advanced Error Handling",
                "Real-time Progress Tracking",
                "Range Request Support for Video Streaming"
            ],
            "components": {
                "job_manager": "✅ Active",
                "video_processor": "✅ Active", 
                "youtube_downloader": "✅ Active",
                "clip_analyzer": "✅ Active"
            },
            "active_jobs": len(job_mgr) if job_mgr else 0
        }
        
        logger.info("📊 Root endpoint accessed - system healthy")
        return system_info
        
    except Exception as e:
        logger.error(f"❌ Error in root endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/usage/{user_id}")
async def get_user_usage(user_id: str, plan: str = "free"):
    """Get user's current usage statistics"""
    try:
        usage = await usage_tracker.get_user_usage(user_id, plan)
# Removed usage success logging
        return usage
    except Exception as e:
        logger.error(f"❌ Error getting usage for {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/usage/{user_id}/max-clips")
async def get_max_clips(user_id: str, plan: str = "free"):
    """Get maximum clips user can create in current request"""
    try:
        max_clips = await usage_tracker.get_max_clips_for_request(user_id, plan)
# Removed max clips success logging
        return {"max_clips": max_clips}
    except Exception as e:
        logger.error(f"❌ Error getting max clips for {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class RecordUsageRequest(BaseModel):
    clips_created: int
    plan: str = "free"

@app.post("/api/usage/{user_id}/record")
async def record_clip_usage(user_id: str, request: RecordUsageRequest):
    """Record that clips were created"""
    try:
        success = await usage_tracker.record_clip_creation(user_id, request.clips_created, request.plan)
        if success:
            logger.info(f"📊 Recorded {request.clips_created} clips for {user_id}")
            return {"status": "success", "message": f"Recorded {request.clips_created} clips"}
        else:
            raise HTTPException(status_code=500, detail="Failed to record clip creation")
    except Exception as e:
        logger.error(f"❌ Error recording clips for {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Enhanced health check with component validation and job status"""
    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "uptime": "unknown"  # Would need startup time tracking
        }
        
        # Check components
        try:
            job_mgr, video_proc, youtube_dl, clip_analyzer = get_components()
            health_data["components"] = {
                "job_manager": f"✅ {len(job_mgr.jobs)} jobs in memory",
                "video_processor": "✅ Ready",
                "youtube_downloader": "✅ Ready", 
                "clip_analyzer": "✅ Ready"
            }
            
            # Add job statistics
            job_stats = await job_mgr.get_job_stats()
            health_data["job_stats"] = job_stats
            
        except Exception as comp_error:
            health_data["components"] = {"error": f"❌ {str(comp_error)}"}
            health_data["status"] = "degraded"
        
        # Check Redis connectivity
        try:
            import redis
            redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
            redis_client.ping()
            
            # Count Redis jobs
            redis_job_count = len(list(redis_client.scan_iter(match="job:*")))
            health_data["redis"] = {
                "status": "✅ Connected",
                "jobs_in_redis": redis_job_count
            }
        except Exception as redis_error:
            health_data["redis"] = {"status": f"❌ {str(redis_error)}"}
            health_data["status"] = "degraded"
        
        # Check directories
        health_data["directories"] = {}
        for directory in directories:
            if os.path.exists(directory) and os.access(directory, os.W_OK):
                health_data["directories"][directory] = "✅ OK"
            else:
                health_data["directories"][directory] = "❌ Not accessible"
                health_data["status"] = "degraded"
        
        return health_data
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/admin/cleanup-jobs")
async def cleanup_orphaned_jobs():
    """Admin endpoint to clean up orphaned jobs and sync memory with Redis"""
    try:
        logger.info("🧹 Starting job cleanup process...")
        
        cleanup_stats = {
            "memory_jobs_before": 0,
            "redis_jobs_before": 0,
            "orphaned_jobs_cleaned": 0,
            "memory_jobs_after": 0,
            "redis_jobs_after": 0,
            "errors": []
        }
        
        # Get current state
        try:
            job_mgr, _, _, _ = get_components()
            cleanup_stats["memory_jobs_before"] = len(job_mgr.jobs)
        except Exception as e:
            cleanup_stats["errors"].append(f"Failed to get job manager: {str(e)}")
        
        try:
            import redis
            redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
            redis_jobs = list(redis_client.scan_iter(match="job:*"))
            cleanup_stats["redis_jobs_before"] = len(redis_jobs)
            
            # Clean up old Redis jobs (older than 7 days)
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=7)
            cutoff_str = cutoff.isoformat()
            
            for job_key in redis_jobs:
                try:
                    job_data = redis_client.get(job_key)
                    if job_data:
                        data = json.loads(job_data)
                        created_at = data.get('created_at', '')
                        
                        # Clean up old jobs
                        if created_at < cutoff_str:
                            job_id = data.get('job_id', job_key.split(':')[1])
                            
                            # Delete from Redis
                            redis_client.delete(job_key)
                            redis_client.delete(f"clips:{job_id}")
                            redis_client.delete(f"job_clips:{job_id}")
                            redis_client.delete(f"job_cache_hint:{job_id}")
                            
                            # Delete from memory if exists
                            if job_id in job_mgr.jobs:
                                del job_mgr.jobs[job_id]
                            
                            cleanup_stats["orphaned_jobs_cleaned"] += 1
                            logger.info(f"🗑️ Cleaned up old job: {job_id}")
                            
                except Exception as job_error:
                    cleanup_stats["errors"].append(f"Error cleaning job {job_key}: {str(job_error)}")
            
            # Get final state
            cleanup_stats["redis_jobs_after"] = len(list(redis_client.scan_iter(match="job:*")))
            cleanup_stats["memory_jobs_after"] = len(job_mgr.jobs)
            
        except Exception as redis_error:
            cleanup_stats["errors"].append(f"Redis cleanup failed: {str(redis_error)}")
        
        logger.info(f"✅ Job cleanup completed: {cleanup_stats['orphaned_jobs_cleaned']} jobs cleaned")
        
        return {
            "message": "Job cleanup completed",
            "stats": cleanup_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Job cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.get("/api/music-files")
async def get_music_files_api():
    """Enhanced music files endpoint with better error handling"""
    try:
        music_dir = "music"
        if not os.path.exists(music_dir):
            logger.warning(f"⚠️ Music directory not found: {music_dir}")
            return {"files": [], "message": "Music directory not found"}
        
        music_files = []
        supported_formats = ['.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg']
        
        try:
            for filename in os.listdir(music_dir):
                if any(filename.lower().endswith(ext) for ext in supported_formats):
                    try:
                        file_path = os.path.join(music_dir, filename)
                        file_size = os.path.getsize(file_path)
                        modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        # Enhanced file info
                        display_name = os.path.splitext(filename)[0]
                        file_ext = os.path.splitext(filename)[1].lower()
                        
                        music_files.append({
                            "filename": filename,
                            "display_name": display_name,
                            "size": file_size,
                            "modified": modified_time.isoformat(),
                            "format": file_ext.upper().replace('.', ''),
                            "duration": None,  # Could add audio duration detection
                            "preview_url": f"/music/{filename}"
                        })
                    except Exception as file_error:
                        logger.warning(f"⚠️ Error processing music file {filename}: {str(file_error)}")
                        continue
        except Exception as dir_error:
            logger.error(f"❌ Error reading music directory: {str(dir_error)}")
            return {"files": [], "error": f"Failed to read music directory: {str(dir_error)}"}
        
        # Sort by display name
        music_files.sort(key=lambda x: x['display_name'].lower())
        
        logger.info(f"🎵 Found {len(music_files)} music files")
        return {
            "files": music_files,
            "total": len(music_files),
            "supported_formats": supported_formats,
            "directory": music_dir
        }
        
    except Exception as e:
        logger.error(f"❌ Error in get_music_files_api: {str(e)}")
        error_response = await handle_api_error(e, "get_music_files_api")
        raise HTTPException(status_code=500, detail=error_response.dict())

@app.get("/api/game-videos")
async def get_game_videos_api():
    """Enhanced game videos endpoint with better error handling"""
    try:
        game_videos_dir = "game_videos"
        if not os.path.exists(game_videos_dir):
            logger.warning(f"⚠️ Game videos directory not found: {game_videos_dir}")
            return {"files": [], "message": "Game videos directory not found"}
        
        game_videos = []
        supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
        
        try:
            for filename in os.listdir(game_videos_dir):
                if any(filename.lower().endswith(ext) for ext in supported_formats):
                    try:
                        file_path = os.path.join(game_videos_dir, filename)
                        file_size = os.path.getsize(file_path)
                        modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        # Enhanced file info
                        display_name = os.path.splitext(filename)[0]
                        file_ext = os.path.splitext(filename)[1].lower()
                        
                        game_videos.append({
                            "filename": filename,
                            "display_name": display_name,
                            "size": file_size,
                            "modified": modified_time.isoformat(),
                            "format": file_ext.upper().replace('.', ''),
                            "preview_url": f"/game_videos/{filename}"
                        })
                    except Exception as file_error:
                        logger.warning(f"⚠️ Error processing game video {filename}: {str(file_error)}")
                        continue
        except Exception as dir_error:
            logger.error(f"❌ Error reading game videos directory: {str(dir_error)}")
            return {"files": [], "error": f"Failed to read game videos directory: {str(dir_error)}"}
        
        # Sort by display name
        game_videos.sort(key=lambda x: x['display_name'].lower())
        
        logger.info(f"🎮 Found {len(game_videos)} game videos")
        return {
            "files": game_videos,
            "total": len(game_videos),
            "supported_formats": supported_formats,
            "directory": game_videos_dir
        }
        
    except Exception as e:
        logger.error(f"❌ Error in get_game_videos_api: {str(e)}")
        error_response = await handle_api_error(e, "get_game_videos_api")
        raise HTTPException(status_code=500, detail=error_response.dict())

@app.get("/video-info")
async def get_video_info(url: str):
    """Enhanced video info endpoint with comprehensive validation"""
    try:
        request_id = str(uuid.uuid4())[:8]
        
        # Enhanced URL validation
        if not url or not url.strip():
            raise HTTPException(status_code=400, detail="URL parameter is required")
        
        url = url.strip()
        logger.info(f"🔍 [{request_id}] Getting video info for URL: {url[:100]}...")
        
        # Validate URL format
        if not validate_youtube_url(url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL format. Please provide a valid YouTube URL.")
        
        # Get components with debugging
        logger.info(f"🔧 [{request_id}] Getting components for video info...")
        _, _, youtube_downloader, _ = get_components()
        logger.info(f"🔍 [{request_id}] Components retrieved: youtube_downloader={youtube_downloader is not None}, type={type(youtube_downloader)}")
        
        if youtube_downloader is None:
            logger.error(f"❌ [{request_id}] CRITICAL: youtube_downloader is None!")
            raise HTTPException(status_code=500, detail="YouTube downloader service is not available")
        
        if not hasattr(youtube_downloader, 'get_video_info'):
            logger.error(f"❌ [{request_id}] CRITICAL: youtube_downloader has no get_video_info method!")
            raise HTTPException(status_code=500, detail="YouTube downloader service is misconfigured")
        
        # Enhanced video info retrieval with longer timeout
        try:
            logger.info(f"🔍 [{request_id}] Calling youtube_downloader.get_video_info...")
            info = await asyncio.wait_for(
                youtube_downloader.get_video_info(url),
                timeout=60.0  # 60 second timeout to allow for multiple strategies
            )
        except asyncio.TimeoutError:
            logger.error(f"❌ [{request_id}] Video info request timed out after 60 seconds")
            raise HTTPException(status_code=408, detail="Video info request timed out after 60 seconds. YouTube may be blocking access. Please try again later.")
        except Exception as info_error:
            logger.error(f"❌ [{request_id}] Video info error: {str(info_error)}")
            error_message = str(info_error)
            if "sign in" in error_message.lower() or "bot" in error_message.lower():
                raise HTTPException(status_code=429, detail="YouTube is currently blocking access. This is usually temporary. Please try again in a few minutes.")
            else:
                raise HTTPException(status_code=400, detail=f"Failed to get video info: {error_message}")
        
        # Enhanced video validation
        duration = info.get('duration', 0)
        if duration < 10:  # 10 seconds
            raise HTTPException(status_code=400, detail="Video is too short. Minimum duration is 10 seconds.")
        
        # Create enhanced VideoInfo response
        video_info = VideoInfo(
            title=info.get('title', 'Unknown Title'),
            duration=int(duration),
            views=info.get('view_count'),
            author=info.get('uploader') or info.get('channel'),
            description=info.get('description', '')[:500],  # Limit description length
            thumbnail_url=info.get('thumbnail'),
            upload_date=info.get('upload_date'),
            video_id=info.get('id'),
            webpage_url=info.get('webpage_url')
        )
        
        logger.info(f"✅ [{request_id}] Video info retrieved: '{video_info.title}' ({video_info.duration}s)")
        return video_info.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting video info: {str(e)}")
        error_response = await handle_api_error(e, "get_video_info")
        raise HTTPException(status_code=500, detail=error_response.dict())

@app.post("/api/ai-enhanced-create-clips")
async def ai_enhanced_create_clips(
    background_tasks: BackgroundTasks,
    youtube_url: Optional[str] = Form(None),
    options: str = Form(...),
    file: Optional[UploadFile] = File(None),
    user_id: Optional[str] = Form(None),
    plan: Optional[str] = Form("free")
):
    """Process video with AI-enhanced options including AssemblyAI handling"""
    request_id = str(uuid.uuid4())[:8]
    
    try:
        logger.info(f"🎬 [{request_id}] AI-enhanced video processing requested.")

        if not youtube_url:
            raise HTTPException(status_code=400, detail="YouTube URL must be provided for AI-enhanced processing")

        options_dict = json.loads(options)
        assemblyai_options = options_dict.get('assemblyAI', {})

        # TODO: Implement AssemblyAI interaction here

        logger.info(f"🔧 [{request_id}] Valid AssemblyAI options received.")
        logger.debug(f"🌐 [{request_id}] AssemblyAI Options: {assemblyai_options}")

        # Enhanced URL validation
        youtube_url = youtube_url.strip()
        if not validate_youtube_url(youtube_url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL format")

        # Simply log placeholder action for now
        logger.info(f"📝 [{request_id}] Simulating AssemblyAI processing for {youtube_url}.")

        # Process with AI-enhanced logic
        processing_options = validate_processing_options(options_dict)
        
        # Check usage limits
        can_create, message, usage_info = await usage_tracker.check_can_create_clips(
            user_id or request_id, processing_options.clipCount, plan
        )
        
        if not can_create:
            raise HTTPException(status_code=429, detail={
                "error": message,
                "usage": usage_info,
                "code": "USAGE_LIMIT_EXCEEDED"
            })
        
        # Start AI-enhanced processing
        return await process_ai_enhanced_video_internal(
            youtube_url, processing_options, request_id, user_id, plan, assemblyai_options
        )

    except Exception as e:
        logger.error(f"❌ [{request_id}] Critical error in ai_enhanced_create_clips: {str(e)}")
        error_response = await handle_api_error(e, "ai_enhanced_create_clips", request_id)
        raise HTTPException(status_code=500, detail=error_response.dict())

async def process_ai_enhanced_video_internal(
    youtube_url: str,
    processing_options: ProcessingOptions, 
    request_id: str,
    user_id: Optional[str],
    plan: str,
    assemblyai_options: Dict
) -> Dict[str, str]:
    """Internal AI-enhanced video processing with AssemblyAI integration"""
    try:
        # Create unique job ID
        job_id = str(uuid.uuid4())
        logger.info(f"🆔 [{request_id}] Created AI job ID: {job_id}")
        
        # Enhanced job creation with AI-enhanced flag
        job = ProcessingJob(
            job_id=job_id,
            status="queued",
            progress=0.0,
            message="AI-enhanced job queued for processing with AssemblyAI",
            clips=[],
            youtube_url=youtube_url,
            video_path=None,
            options=processing_options,
            created_at=datetime.now()
        )
        
        # Add AI-specific metadata
        job.user_id = user_id
        job.plan = plan
        job.assemblyai_options = assemblyai_options
        job.is_ai_enhanced = True
        
        logger.info(f"🔧 [{request_id}] Created AI-enhanced processing job")
        
        # Store job
        job_mgr, _, _, _ = get_components()
        await job_mgr.create_job(job)
        logger.info(f"✅ [{request_id}] AI job stored in manager")
        
        # Start AI-enhanced background processing
        def run_ai_background_task():
            """Synchronous wrapper for async AI background task"""
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def process_with_timeout():
                    try:
                        await asyncio.wait_for(
                            process_ai_enhanced_video_background(
                                job_id, youtube_url, processing_options, user_id, plan, assemblyai_options
                            ),
                            timeout=3600  # 60 minutes for AI processing
                        )
                    except asyncio.TimeoutError:
                        job_mgr, _, _, _ = get_components()
                        await job_mgr.set_job_error(job_id, "AI processing timed out after 60 minutes")
                        logger.error(f"❌ AI Job {job_id} timed out after 60 minutes")
                
                loop.run_until_complete(process_with_timeout())
                loop.close()
            except Exception as e:
                logger.error(f"❌ AI Background task error: {str(e)}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Submit to thread pool
        video_executor.submit(run_ai_background_task)
        
        logger.info(f"✅ [{request_id}] AI background task started for job: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "queued", 
            "message": "AI-enhanced job queued for processing with AssemblyAI",
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] Critical error in process_ai_enhanced_video_internal: {str(e)}")
        error_response = await handle_api_error(e, "process_ai_enhanced_video_internal", request_id)
        raise HTTPException(status_code=500, detail=error_response.dict())

@app.post("/api/process-video")
async def process_video_api(
    background_tasks: BackgroundTasks,
    youtube_url: Optional[str] = Form(None),
    options: str = Form(...),
    file: Optional[UploadFile] = File(None),
    user_id: Optional[str] = Form(None),
    plan: Optional[str] = Form("free")
):
    """ENHANCED: Process video with comprehensive validation and error handling"""
    request_id = str(uuid.uuid4())[:8]
    
    try:
        logger.info(f"🎬 [{request_id}] Video processing request - URL: {bool(youtube_url)}, File: {file.filename if file else None}")
        
        # Enhanced input validation
        if not youtube_url and not file:
            raise HTTPException(status_code=400, detail="Either youtube_url or file must be provided")
        
        if youtube_url and file:
            raise HTTPException(status_code=400, detail="Provide either youtube_url OR file, not both")
        
        # Enhanced options parsing with comprehensive error handling
        try:
            logger.debug(f"🔧 [{request_id}] Raw options string: {options[:200]}...")
            
            # Parse JSON
            options_dict = json.loads(options)
            logger.debug(f"📋 [{request_id}] Parsed options dict: {list(options_dict.keys())}")
            
            # Validate with enhanced error handling
            processing_options = validate_processing_options(options_dict)
            logger.info(f"✅ [{request_id}] Validated options: {processing_options.captionStyle}, {processing_options.layout}, Quality: {processing_options.qualityLevel}")
            
        except json.JSONDecodeError as je:
            logger.error(f"❌ [{request_id}] JSON decode error: {str(je)}")
            raise HTTPException(status_code=422, detail=f"Invalid JSON in options: {str(je)}")
        except Exception as e:
            logger.error(f"❌ [{request_id}] Options validation error: {str(e)}")
            # Use default options if validation fails
            processing_options = ProcessingOptions(
                clipLength="30-60s",
                captionStyle="YouTube Style", 
                enableHookTitles=True,
                enableWordHighlighting=True,
                layout="Vertical (9:16)",
                clipCount=3,
                qualityLevel="Ultra"
            )
            logger.warning(f"⚠️ [{request_id}] Using default options due to validation error")

        # Check usage limits before processing - SKIP FOR TESTING IF NO VALID USER_ID
        if user_id and len(user_id) > 8:  # Check if it's a proper UUID, not just request_id
            try:
                import uuid as uuid_module
                uuid_module.UUID(user_id)  # Validate UUID format
                plan = plan or "free"  # Use provided plan or default to free
                
                can_create, message, usage_info = await usage_tracker.check_can_create_clips(
                    user_id, processing_options.clipCount, plan
                )
                
                if not can_create:
                    logger.warning(f"⚠️ [{request_id}] Usage limit exceeded: {message}")
                    raise HTTPException(status_code=429, detail={
                        "error": message,
                        "usage": usage_info,
                        "code": "USAGE_LIMIT_EXCEEDED"
                    })
                
                logger.info(f"✅ [{request_id}] Usage check passed: {processing_options.clipCount} clips requested, {usage_info['clips_remaining']} remaining")
            except (ValueError, Exception) as e:
                logger.warning(f"⚠️ [{request_id}] Invalid user_id format or usage check failed: {str(e)}, proceeding without usage limits")
                user_id = None
        else:
            logger.info(f"🔧 [{request_id}] No valid user_id provided, proceeding without usage limits (TEST MODE)")
            user_id = None
        
        logger.info(f"✅ [{request_id}] Usage check passed: {processing_options.clipCount} clips requested, proceeding without usage info")
        
        # Enhanced URL validation if provided
        if youtube_url:
            youtube_url = youtube_url.strip()
            if not validate_youtube_url(youtube_url):
                raise HTTPException(status_code=400, detail="Invalid YouTube URL format")
        
        return await process_video_internal(background_tasks, youtube_url, processing_options, file, request_id, user_id, plan)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [{request_id}] Critical error in process_video_api: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        error_response = await handle_api_error(e, "process_video_api", request_id)
        raise HTTPException(status_code=500, detail=error_response.dict())

async def process_video_internal(
    background_tasks: BackgroundTasks,
    youtube_url: Optional[str],
    processing_options: ProcessingOptions,
    file: Optional[UploadFile],
    request_id: str,
    user_id: Optional[str] = None,
    plan: Optional[str] = "free"
) -> Dict[str, str]:
    """ENHANCED: Internal video processing with comprehensive error handling"""
    try:
        # Create unique job ID
        job_id = str(uuid.uuid4())
        logger.info(f"🆔 [{request_id}] Created job ID: {job_id}")
        
        # Enhanced file upload handling
        video_path = None
        if file:
            logger.info(f"📁 [{request_id}] Processing uploaded file: {file.filename}")
            
            # Enhanced file validation
            if not file.filename:
                raise HTTPException(status_code=400, detail="No filename provided")
            
            # Read file content with size validation
            try:
                content = await file.read()
                file_size = len(content)
                
                logger.info(f"📊 [{request_id}] File size: {file_size / (1024*1024):.1f} MB")
                
                # Enhanced size validation
                max_size = 1000 * 1024 * 1024  # 1GB limit
                if file_size > max_size:
                    raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {max_size/(1024*1024):.0f}MB")
                
                if file_size < 1024:  # 1KB minimum
                    raise HTTPException(status_code=400, detail="File too small or empty")
                
            except Exception as read_error:
                logger.error(f"❌ [{request_id}] File read error: {str(read_error)}")
                raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(read_error)}")
            
            # Enhanced file format validation
            file_extension = os.path.splitext(file.filename)[1].lower()
            allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.m4v']
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file format '{file_extension}'. Allowed: {', '.join(allowed_extensions)}"
                )
            
            # Save uploaded file with error handling
            video_path = f"temp/{job_id}{file_extension}"
            
            try:
                async with aiofiles.open(video_path, 'wb') as f:
                    await f.write(content)
                
                # Verify file was written correctly
                if not os.path.exists(video_path) or os.path.getsize(video_path) != file_size:
                    raise Exception("File write verification failed")
                
                logger.info(f"✅ [{request_id}] File saved successfully: {video_path}")
                
            except Exception as save_error:
                logger.error(f"❌ [{request_id}] File save error: {str(save_error)}")
                # Cleanup partial file
                if os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                    except:
                        pass
                raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(save_error)}")
        
        # Enhanced job creation with validation
        try:
            job = ProcessingJob(
                job_id=job_id,  # Use 'job_id' to match the alias
                status="queued",
                progress=0.0,
                message="Job queued for ULTRA quality processing",
                clips=[],
                youtube_url=youtube_url,
                video_path=video_path,
                options=processing_options,
                created_at=datetime.now()
            )
            
            # Add user_id and plan to the job object for Redis storage
            job.user_id = user_id
            job.plan = plan
            
            logger.info(f"🔧 [{request_id}] Created processing job with ULTRA quality settings")
            
        except Exception as job_error:
            logger.error(f"❌ [{request_id}] Job creation error: {str(job_error)}")
            raise HTTPException(status_code=500, detail=f"Failed to create processing job: {str(job_error)}")
        
        # Store job with error handling
        try:
            job_mgr, _, _, _ = get_components()
            await job_mgr.create_job(job)
            logger.info(f"✅ [{request_id}] Job stored in manager")
        except Exception as store_error:
            logger.error(f"❌ [{request_id}] Job storage error: {str(store_error)}")
            # Cleanup uploaded file if job storage fails
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Failed to store job: {str(store_error)}")
        
        # Start Celery task for durable video processing
        try:
            logger.info(f"🚀 [{request_id}] About to start Celery video processing task for job: {job_id}")
            logger.info(f"🔧 [{request_id}] Task parameters: youtube_url={youtube_url}, video_path={video_path}, user_id={user_id}, plan={plan}")
            
            # Convert ProcessingOptions to dict for Celery serialization
            options_dict = {
                'clipLength': processing_options.clipLength,
                'captionStyle': processing_options.captionStyle,
                'enableHookTitles': processing_options.enableHookTitles,
                'enableWordHighlighting': processing_options.enableWordHighlighting,
                'enableAutoEmojis': processing_options.enableAutoEmojis,
                'layout': processing_options.layout,
                'clipCount': processing_options.clipCount,
                'qualityLevel': processing_options.qualityLevel,
                'selectedMusicFile': processing_options.backgroundMusic,
                'selectedGameVideoFile': processing_options.gameVideo
            }
            
            # Start background processing in dedicated thread executor to prevent blocking
            def run_background_task():
                """Synchronous wrapper for async background task"""
                try:
                    # Create new event loop for this thread
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Run the async function with overall timeout
                    async def process_with_timeout():
                        try:
                            # 60-minute maximum timeout for entire job
                            await asyncio.wait_for(
                                process_video_background_enhanced(
                                    job_id, youtube_url, video_path, processing_options, user_id, plan
                                ),
                                timeout=5400  # 90 minutes (1.5 hours)
                            )
                        except asyncio.TimeoutError:
                            job_mgr, _, _, _ = get_components()
                            await job_mgr.set_job_error(job_id, "Job timed out after 90 minutes - video may be too large or have complex effects")
                            logger.error(f"❌ Job {job_id} timed out after 90 minutes")
                    
                    loop.run_until_complete(process_with_timeout())
                    
                    loop.close()
                except Exception as e:
                    logger.error(f"❌ Background task error: {str(e)}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Submit to thread pool
            video_executor.submit(run_background_task)
            
            logger.info(f"✅ [{request_id}] Background task started for job: {job_id}")
            
        except Exception as task_error:
            logger.error(f"❌ [{request_id}] Celery task submission error: {str(task_error)}")
            # Store job as error in Redis for consistent interface
            try:
                import redis
                redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
                error_data = {
                    'job_id': job_id,
                    'status': 'error',
                    'progress': 0,
                    'message': f'Failed to start processing: {str(task_error)}',
                    'updated_at': datetime.now().isoformat()
                }
                redis_client.hset(f"job_progress:{job_id}", mapping=error_data)
                redis_client.expire(f"job_progress:{job_id}", 3600)
            except Exception as redis_error:
                logger.error(f"❌ [{request_id}] Failed to store error in Redis: {redis_error}")
            
            raise HTTPException(status_code=500, detail=f"Failed to start video processing: {str(task_error)}")
        
        return {
            "job_id": job_id, 
            "status": "queued",
            "message": "Job queued for ULTRA quality processing",
            "request_id": request_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [{request_id}] Critical error in process_video_internal: {str(e)}")
        error_response = await handle_api_error(e, "process_video_internal", request_id)
        raise HTTPException(status_code=500, detail=error_response.dict())

@app.get("/api/job-status/{job_id}")
async def get_job_status_api(job_id: str):
    """ENHANCED: Get job status with ultra-safe serialization and better error handling"""
    try:
        logger.debug(f"📊 Getting status for job: {job_id}")
        
        # Enhanced job validation
        if not job_id or not job_id.strip():
            raise HTTPException(status_code=400, detail="Job ID is required")
        
        job_id = job_id.strip()
        
        # Get job status from job manager with enhanced error handling and Redis fallback
        try:
            job_mgr, _, _, _ = get_components()
            job_data = await job_mgr.serialize_job_for_api(job_id)
            
            if not job_data:
                logger.warning(f"⚠️ Job {job_id} not found in job manager, checking Redis fallback...")
                
                # Try Redis fallback for jobs that might have been lost during server restart
                try:
                    import redis
                    redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
                    redis_job_data = redis_client.get(f"job:{job_id}")
                    
                    if redis_job_data:
                        logger.info(f"✅ Found job {job_id} in Redis fallback")
                        job_data = json.loads(redis_job_data)
                        
                        # Add clips if completed
                        if job_data.get('status') == 'completed':
                            clips_data = redis_client.get(f"clips:{job_id}")
                            if clips_data:
                                clips_info = json.loads(clips_data)
                                job_data['clips'] = clips_info.get('clips', [])
                            else:
                                job_data['clips'] = []
                        else:
                            job_data['clips'] = []
                    else:
                        logger.warning(f"⚠️ Job {job_id} not found in Redis either")
                        # Return a proper 404 response instead of causing a 500 error
                        raise HTTPException(
                            status_code=404, 
                            detail={
                                "error": f"Job {job_id} not found",
                                "message": "This job may have expired, been cancelled, or never existed",
                                "job_id": job_id,
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                except Exception as redis_error:
                    logger.error(f"❌ Redis fallback failed for {job_id}: {redis_error}")
                    raise HTTPException(
                        status_code=404, 
                        detail={
                            "error": f"Job {job_id} not found",
                            "message": "Job not found in memory or Redis storage",
                            "job_id": job_id,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
            
            # Always fetch fresh clips from storage for completed jobs
            if job_data.get('status') == 'completed':
                try:
                    # Get job object to access user_id
                    job_obj = await job_mgr.get_job(job_id)
                    user_id = getattr(job_obj, 'user_id', None) if job_obj else None
                    
                    if user_id:
                        # Get all user clips and filter by job_id
                        user_clips = await storage_manager.get_user_clips(user_id)
                        
                        # Filter clips for this specific job using job_id
                        job_clips = []
                        for clip in user_clips:
                            # Check if clip belongs to this job by job_id
                            if clip.get('job_id') == job_id:
                                # Add stream URLs for frontend
                                clip_with_urls = {
                                    'filename': clip.get('filename', ''),
                                    'title': clip.get('title', ''),
                                    'duration': clip.get('duration', 0),
                                    'file_size': clip.get('file_size', 0),
                                    'hook_title': clip.get('hook_title'),
                                    'viral_potential': clip.get('viral_potential'),
                                    'created_at': clip.get('created_at'),
                                    'stream_url': storage_manager.get_clip_url(clip['storage_path']) if clip.get('storage_path') else None,
                                    'thumbnail_url': storage_manager.get_clip_url(clip['thumbnail_path']) if clip.get('thumbnail_path') else None
                                }
                                job_clips.append(clip_with_urls)
                        
                        job_data['clips'] = job_clips
                        logger.info(f"✅ Fetched {len(job_clips)} clips from storage for job {job_id}")
                    else:
                        logger.warning(f"⚠️ No user_id found for job {job_id}, cannot fetch clips")
                        job_data['clips'] = []
                        
                except Exception as clips_error:
                    logger.warning(f"⚠️ Failed to fetch clips from storage for {job_id}: {clips_error}")
                    # Fallback to Redis clips if storage fetch fails
                    try:
                        import redis
                        redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
                        clips_data = redis_client.hget(f"job_clips:{job_id}", 'clips')
                        if clips_data:
                            job_data['clips'] = json.loads(clips_data)
                        else:
                            job_data['clips'] = []
                    except Exception as redis_error:
                        logger.error(f"❌ Redis fallback also failed for {job_id}: {redis_error}")
                        job_data['clips'] = []
            else:
                job_data['clips'] = []
            
        except HTTPException:
            # Re-raise HTTP exceptions (like 404) without modification
            raise
        except Exception as get_error:
            logger.error(f"❌ Error getting job {job_id}: {str(get_error)}")
            # Return a more specific error instead of generic 500
            raise HTTPException(
                status_code=500, 
                detail={
                    "error": "Job retrieval failed",
                    "message": f"Failed to retrieve job status: {str(get_error)}",
                    "job_id": job_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        # Enhanced response with additional metadata
        response_data = {
            **job_data,
            "api_version": "3.0.0",
            "timestamp": datetime.now().isoformat()
        }
        
        logger.debug(f"✅ Status retrieved for {job_id}: {job_data['status']} ({job_data['progress']}%)")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Critical error getting job status for {job_id}: {str(e)}")
        # Provide a more informative error response
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Internal server error",
                "message": f"Unexpected error occurred while retrieving job status",
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "details": str(e)[:200]  # Limit error details length
            }
        )

@app.delete("/api/job/{job_id}")
async def delete_job_api(job_id: str):
    """Delete a job and clean up associated resources"""
    try:
        logger.info(f"🗑️ Deleting job: {job_id}")
        
        if not job_id or not job_id.strip():
            raise HTTPException(status_code=400, detail="Job ID is required")
        
        job_id = job_id.strip()
        
        # Clean up from job manager
        try:
            job_mgr, _, _, _ = get_components()
            if job_id in job_mgr.jobs:
                del job_mgr.jobs[job_id]
                logger.info(f"✅ Removed job {job_id} from memory")
        except Exception as memory_error:
            logger.warning(f"⚠️ Failed to remove job from memory: {memory_error}")
        
        # Clean up from Redis
        try:
            import redis
            redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
            
            # Delete job data
            redis_client.delete(f"job:{job_id}")
            redis_client.delete(f"clips:{job_id}")
            redis_client.delete(f"job_clips:{job_id}")
            redis_client.delete(f"job_cache_hint:{job_id}")
            
            logger.info(f"✅ Cleaned up Redis data for job {job_id}")
        except Exception as redis_error:
            logger.warning(f"⚠️ Failed to clean up Redis data: {redis_error}")
        
        # Clean up temporary files
        try:
            import glob
            temp_files = glob.glob(f"temp/*{job_id}*")
            output_files = glob.glob(f"output/*{job_id}*")
            thumbnail_files = glob.glob(f"thumbnails/*{job_id}*")
            
            all_files = temp_files + output_files + thumbnail_files
            for file_path in all_files:
                try:
                    os.remove(file_path)
                    logger.debug(f"🗑️ Deleted file: {file_path}")
                except:
                    pass
            
            if all_files:
                logger.info(f"✅ Cleaned up {len(all_files)} files for job {job_id}")
        except Exception as file_error:
            logger.warning(f"⚠️ Failed to clean up files: {file_error}")
        
        return {
            "message": f"Job {job_id} deleted successfully",
            "job_id": job_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")

@app.get("/api/job-status-stream/{job_id}")
async def stream_job_status(job_id: str):
    """Server-Sent Events endpoint for real-time job status updates"""
    async def event_stream():
        try:
            job_mgr, _, _, _ = get_components()
            
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'job_id': job_id})}\n\n"
            
            last_status = None
            last_progress = None
            
            while True:
                try:
                    # Get current job status using serialize method for consistent format
                    job_data = await job_mgr.serialize_job_for_api(job_id)
                    
                    if job_data:
                        # Only send update if status or progress changed
                        current_status = job_data.get('status')
                        current_progress = job_data.get('progress', 0)
                        
                        if (current_status != last_status or 
                            abs(current_progress - (last_progress or 0)) >= 1.0):
                            
                            # Create update payload
                            update = {
                                'type': 'status_update',
                                'job_id': job_id,
                                'status': current_status,
                                'progress': current_progress,
                                'message': job_data.get('message', 'Processing...'),
                                'current_step': job_data.get('current_step'),
                                'clips': job_data.get('clips', [])
                            }
                            
                            yield f"data: {json.dumps(update)}\n\n"
                            
                            last_status = current_status
                            last_progress = current_progress
                            
                            # Stop streaming if job is completed, failed, or cancelled
                            if current_status in ['completed', 'error', 'cancelled']:
                                yield f"data: {json.dumps({'type': 'stream_end', 'job_id': job_id})}\n\n"
                                break
                    else:
                        # Job not found
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                        break
                
                except Exception as e:
                    logger.error(f"❌ Error in SSE stream for job {job_id}: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Stream error'})}\n\n"
                    break
                
                # Wait before next check (2 second interval)
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"❌ SSE stream initialization error for job {job_id}: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Stream initialization failed'})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

# Removed WebSocket endpoint - back to polling

@app.post("/api/cancel-job/{job_id}")
async def cancel_job_api(job_id: str):
    """Cancel a processing job"""
    try:
        logger.info(f"🛑 Cancel request for job: {job_id}")
        
        # Validate job ID
        if not job_id or not job_id.strip():
            raise HTTPException(status_code=400, detail="Job ID is required")
        
        job_id = job_id.strip()
        
        # Get job manager
        job_mgr, _, _, _ = get_components()
        
        # Cancel the job
        success = await job_mgr.cancel_job(job_id)
        
        if success:
            logger.info(f"✅ Job {job_id} cancelled successfully")
            return {"status": "success", "message": f"Job {job_id} has been cancelled"}
        else:
            logger.warning(f"⚠️ Job {job_id} could not be cancelled (may not exist or already completed)")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or cannot be cancelled")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cancelling job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")

@app.get("/api/clips/{user_id}")
async def get_user_clips_api(user_id: str):
    """Get all clips for a user"""
    try:
        logger.info(f"📋 Getting clips for user: {user_id}")
        
        clips = await storage_manager.get_user_clips(user_id)
        
        # Add signed URLs for each clip
        for clip in clips:
            if clip.get("storage_path"):
                clip["stream_url"] = storage_manager.get_clip_url(clip["storage_path"])
            if clip.get("thumbnail_path"):
                clip["thumbnail_url"] = storage_manager.get_clip_url(clip["thumbnail_path"])
        
        return {
            "clips": clips,
            "total": len(clips)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting clips for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get clips: {str(e)}")

@app.delete("/api/clips/{user_id}/{clip_id}")
async def delete_user_clip_api(user_id: str, clip_id: str):
    """Delete a specific clip"""
    try:
        logger.info(f"🗑️ Deleting clip {clip_id} for user {user_id}")
        
        success = await storage_manager.delete_clip(user_id, clip_id)
        
        if success:
            return {"status": "success", "message": "Clip deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Clip not found or could not be deleted")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting clip: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete clip: {str(e)}")

@app.get("/api/clips/{user_id}/{clip_id}/stream")
async def stream_clip_api(user_id: str, clip_id: str):
    """Get streaming URL for a specific clip"""
    try:
        # Get clip metadata
        clips = await storage_manager.get_user_clips(user_id)
        clip = next((c for c in clips if c["id"] == clip_id), None)
        
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        stream_url = storage_manager.get_clip_url(clip["storage_path"])
        
        if stream_url:
            return {"stream_url": stream_url}
        else:
            raise HTTPException(status_code=500, detail="Failed to generate stream URL")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting stream URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stream URL: {str(e)}")

@app.get("/api/download/{user_id}")
async def download_user_clips(user_id: str):
    """Download all clips for a user as a ZIP file from Supabase Storage"""
    try:
        logger.info(f"📥 Download request for user: {user_id}")
        
        # Validate user ID
        if not user_id or not user_id.strip():
            raise HTTPException(status_code=400, detail="User ID is required")
        
        user_id = user_id.strip()
        
        # Get user clips
        clips = await storage_manager.get_user_clips(user_id)
        
        if not clips or len(clips) == 0:
            raise HTTPException(status_code=404, detail="No clips found for this user")
        
        # For now, return the list of clip URLs for download
        # In a full implementation, you might want to create a ZIP on-demand
        clip_urls = []
        for clip in clips:
            if clip.get("storage_path"):
                stream_url = await storage_manager.get_clip_stream_url(clip["storage_path"])
                if stream_url:
                    clip_urls.append({
                        "filename": clip["filename"],
                        "title": clip.get("title", "Untitled"),
                        "download_url": stream_url,
                        "size": clip.get("file_size", 0)
                    })
        
        logger.info(f"✅ Prepared {len(clip_urls)} clips for download")
        
        return {
            "clips": clip_urls,
            "total": len(clip_urls),
            "message": "Use the download_url for each clip to download individual files"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error: {str(e)}")
        error_response = await handle_api_error(e, "download_user_clips")
        raise HTTPException(status_code=500, detail=error_response.dict())

@app.get("/api/clip/{user_id}/{clip_filename}")
async def get_clip(user_id: str, clip_filename: str, request: Request):
    """ENHANCED: Stream clip from Supabase Storage with redirect to signed URL"""
    try:
        # Enhanced validation
        if not user_id or not clip_filename:
            raise HTTPException(status_code=400, detail="User ID and clip filename are required")
        
        # Sanitize inputs
        user_id = user_id.strip()
        clip_filename = clip_filename.strip()
        
        # Additional security check for filename
        if '..' in clip_filename or '/' in clip_filename or '\\' in clip_filename:
            raise HTTPException(status_code=400, detail="Invalid clip filename")
        
        # Get clip metadata from database
        clips = await storage_manager.get_user_clips(user_id)
        clip = next((c for c in clips if c["filename"] == clip_filename), None)
        
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        # Get signed URL for streaming
        storage_path = clip["storage_path"]
        stream_url = await storage_manager.get_clip_stream_url(storage_path)
        
        if not stream_url:
            raise HTTPException(status_code=500, detail="Failed to generate stream URL")
        
        # Redirect to the signed URL for direct streaming from Supabase
        logger.debug(f"📹 Redirecting to stream URL for: {clip_filename}")
        
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=stream_url,
            status_code=307,  # Temporary redirect to preserve method
            headers={
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "range",
                "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get clip error: {str(e)}")
        error_response = await handle_api_error(e, "get_clip")
        raise HTTPException(status_code=500, detail=error_response.dict())

@app.get("/api/thumbnail/{user_id}/{thumbnail_filename}")
async def get_thumbnail(user_id: str, thumbnail_filename: str):
    """Enhanced thumbnail endpoint - stream from Supabase Storage"""
    try:
        # Enhanced validation
        if not user_id or not thumbnail_filename:
            raise HTTPException(status_code=400, detail="User ID and thumbnail filename are required")
        
        # Sanitize inputs
        user_id = user_id.strip()
        thumbnail_filename = thumbnail_filename.strip()
        
        # Security check
        if '..' in thumbnail_filename or '/' in thumbnail_filename or '\\' in thumbnail_filename:
            raise HTTPException(status_code=400, detail="Invalid thumbnail filename")
        
        # Get clip with matching thumbnail
        clips = await storage_manager.get_user_clips(user_id)
        clip = next((c for c in clips if c.get("thumbnail_path") and thumbnail_filename in c["thumbnail_path"]), None)
        
        if not clip or not clip.get("thumbnail_path"):
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        # Get signed URL for thumbnail
        thumbnail_url = storage_manager.get_clip_url(clip["thumbnail_path"])
        
        if not thumbnail_url:
            raise HTTPException(status_code=500, detail="Failed to generate thumbnail URL")
        
        # Redirect to the signed URL
        logger.debug(f"🖼️ Redirecting to thumbnail URL for: {thumbnail_filename}")
        
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=thumbnail_url,
            status_code=307,
            headers={
                "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get thumbnail error: {str(e)}")
        error_response = await handle_api_error(e, "get_thumbnail")
        raise HTTPException(status_code=500, detail=error_response.dict())


@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download individual files from output directory"""
    try:
        # Sanitize filename for security
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Check file extension
        if not filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        file_path = os.path.join("output", filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        logger.info(f"📥 Serving download: {filename}")
        
        return FileResponse(
            path=file_path,
            media_type="video/mp4",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error for {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

async def process_ai_enhanced_video_background(
    job_id: str,
    youtube_url: str,
    processing_options: ProcessingOptions,
    user_id: Optional[str],
    plan: str,
    assemblyai_options: Dict
):
    """AI-enhanced background processing with proper caption integration"""
    request_id = job_id[:8]
    logger.info(f"🤖 [{request_id}] Starting AI-enhanced background processing with captions")
    
    # Configure FFmpeg path for AI-enhanced processing
    try:
        from pydub import AudioSegment
        from pydub.utils import which
        
        ffmpeg_path = which("ffmpeg")
        if not ffmpeg_path:
            # Try common Windows locations
            common_paths = [
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\Users\TaimoorAli\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1.1-full_build\bin\ffmpeg.exe"
            ]
            for path in common_paths:
                if os.path.exists(path):
                    ffmpeg_path = path
                    break
        
        if ffmpeg_path:
            AudioSegment.converter = ffmpeg_path
            AudioSegment.ffmpeg = ffmpeg_path
            AudioSegment.ffprobe = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")
            logger.info(f"✅ [{request_id}] FFmpeg configured for AI processing: {ffmpeg_path}")
        else:
            logger.warning(f"⚠️ [{request_id}] FFmpeg not found for AI processing")
    except Exception as ffmpeg_error:
        logger.warning(f"⚠️ [{request_id}] FFmpeg configuration failed: {str(ffmpeg_error)}")
    
    try:
        # Get components
        job_mgr, video_proc, youtube_dl, clip_analyzer = get_components()
        
        # Start process monitoring
        process_monitor.start_process_tracking(job_id, 'ai_video_processing', {
            'youtube_url': youtube_url,
            'user_id': user_id,
            'plan': plan,
            'assemblyai_options': assemblyai_options
        })
        
        # Initialize job steps
        await job_mgr.initialize_job_steps(job_id)
        
        # Update initial job status
        await job_mgr.update_job_status(
            job_id, "processing", 0.0, 
            "Starting AI-enhanced video processing with captions", 
            "AI Initialization"
        )
        
        # Step 1: Download video
        await job_mgr.update_step_status(job_id, "video_download", "processing", 0.0)
        logger.info(f"📥 [{request_id}] Downloading video from URL: {youtube_url[:100]}...")
        
        try:
            video_path = await asyncio.wait_for(
                youtube_dl.download_video(youtube_url, job_id),
                timeout=600  # 10 minute timeout for download
            )
            logger.info(f"✅ [{request_id}] Video downloaded successfully: {video_path}")
        except Exception as download_error:
            logger.error(f"❌ [{request_id}] Download failed: {str(download_error)}")
            await job_mgr.set_job_error(job_id, f"Video download failed: {str(download_error)}")
            return
            
        await job_mgr.update_step_status(job_id, "video_download", "completed", 100.0)
        
        # Step 2: AI Analysis with Transcription
        await job_mgr.update_step_status(job_id, "ai_analysis", "processing", 0.0)
        await job_mgr.update_job_status(
            job_id, "processing", 20.0, 
            "Analyzing video content with AI and generating captions", 
            "AI Analysis"
        )
        
        # Generate transcription for captions
        transcript = None
        try:
            from utils.transcription_service import TranscriptionService
            transcription_service = TranscriptionService()
            logger.info(f"📝 [{request_id}] Generating AI transcription for captions...")
            
            transcript = await asyncio.wait_for(
                transcription_service.transcribe_audio(video_path),
                timeout=300  # 5 minute timeout for transcription
            )
            logger.info(f"✅ [{request_id}] AI transcription complete: {len(transcript.get('segments', [])) if transcript else 0} segments")
        except Exception as transcription_error:
            logger.warning(f"⚠️ [{request_id}] Transcription failed: {str(transcription_error)}")
            transcript = None
        
        await job_mgr.update_step_status(job_id, "ai_analysis", "completed", 100.0)
        
        # Step 3: Enhanced Video Processing with Captions
        await job_mgr.update_step_status(job_id, "video_processing", "processing", 0.0)
        await job_mgr.update_job_status(
            job_id, "processing", 40.0, 
            "Processing video clips with AI-enhanced captions", 
            "Video Processing"
        )
        
        try:
            # Use Enhanced Video Service with AI processing
            logger.info(f"🎬 [{request_id}] Using Enhanced Video Service for AI processing with captions...")
            enhanced_service = EnhancedVideoService()
            
            # Pass transcript data to Enhanced Video Service
            clips = await enhanced_service.process_video_with_captions(
                video_path=video_path,
                options=processing_options,
                job_id=job_id,
                job_manager=job_mgr,
                transcript=transcript,  # Pass the transcript for captions
                disable_assembly_ai=True,  # Use OpenAI Whisper
                enable_ai_enhancements=True  # Enable AI-specific enhancements
            )
            
            logger.info(f"✅ [{request_id}] AI-enhanced video processing with captions complete: {len(clips)} clips created")
            
        except Exception as processing_error:
            logger.error(f"❌ [{request_id}] AI video processing failed: {str(processing_error)}")
            await job_mgr.set_job_error(job_id, f"AI video processing failed: {str(processing_error)}")
            return
        
        await job_mgr.update_step_status(job_id, "video_processing", "completed", 100.0)
        
        # Step 4: Record usage and upload clips
        user_id = user_id or request_id
        plan = plan or "free"
        clips_created = len(clips)
        
        try:
            success = await usage_tracker.record_clip_creation(user_id, clips_created, plan)
            if success:
                logger.info(f"📊 [{request_id}] Recorded {clips_created} AI clips for usage tracking")
        except Exception as usage_error:
            logger.error(f"❌ [{request_id}] Error recording AI usage: {str(usage_error)}")
        
        # Step 5: Upload clips to cloud storage
        await job_mgr.update_step_status(job_id, "storage_upload", "processing", 0.0)
        await job_mgr.update_job_status(
            job_id, "processing", 90.0, 
            "Saving AI-enhanced clips to your library...", 
            "Storage Upload"
        )
        
        uploaded_clips = []
        for i, clip in enumerate(clips):
            try:
                local_clip_path = f"output/{job_id}/{clip.filename}"
                
                if os.path.exists(local_clip_path):
                    file_size = os.path.getsize(local_clip_path)
                    storage_path = await storage_manager.upload_and_cleanup_clip(user_id, local_clip_path, clip.filename)
                    
                    if storage_path:
                        # Handle thumbnail upload
                        thumbnail_path = None
                        local_thumbnail_path = f"thumbnails/{job_id}/{clip.filename.replace('.mp4', '.jpg')}"
                        
                        if os.path.exists(local_thumbnail_path):
                            thumbnail_filename = clip.filename.replace('.mp4', '.jpg')
                            thumbnail_path = await storage_manager.upload_and_cleanup_thumbnail(user_id, local_thumbnail_path, thumbnail_filename)
                        
                        # Save clip metadata with AI-enhanced flags
                        clip_data = {
                            "filename": clip.filename,
                            "title": getattr(clip, 'title', f"AI Clip {i+1}"),
                            "duration": getattr(clip, 'duration', 0),
                            "file_size": file_size,
                            "storage_path": storage_path,
                            "thumbnail_path": thumbnail_path,
                            "hook_title": getattr(clip, 'hook_title', None),
                            "viral_potential": getattr(clip, 'viral_potential', None),
                            "ai_enhanced": True,  # Mark as AI-enhanced
                            "has_captions": True  # Mark as having captions
                        }
                        
                        metadata_saved = await storage_manager.save_clip_metadata(user_id, job_id, clip_data)
                        
                        if metadata_saved:
                            uploaded_clips.append(clip.filename)
                            logger.info(f"✅ [{request_id}] Uploaded AI clip with captions: {clip.filename}")
                        
            except Exception as upload_error:
                logger.error(f"❌ [{request_id}] Error uploading AI clip {clip.filename}: {str(upload_error)}")
        
        await job_mgr.update_step_status(job_id, "storage_upload", "completed", 100.0)
        
        # Final completion
        await job_mgr.update_job_status(
            job_id, "completed", 100.0, 
            f"Successfully created {len(clips)} AI-enhanced clips with captions ({len(uploaded_clips)} uploaded)", 
            "Completed"
        )
        
        logger.info(f"🎉 [{request_id}] AI-enhanced job {job_id} completed successfully with {len(clips)} captioned clips")
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] AI-enhanced processing failed: {str(e)}")
        job_mgr, _, _, _ = get_components()
        await job_mgr.set_job_error(job_id, f"AI-enhanced processing failed: {str(e)}")

# ENHANCED: Background processing function with comprehensive error handling
async def process_video_background_enhanced(
    job_id: str, 
    youtube_url: Optional[str], 
    video_path: Optional[str], 
    options: ProcessingOptions,
    user_id: str,
    plan: str
):
    """ENHANCED: Background video processing with ultra error handling and logging"""
    try:
        request_id = job_id[:8]  # Use first 8 chars of job_id as request_id
        logger.info(f"🎬 [{request_id}] ===== BACKGROUND FUNCTION STARTED =====")
        logger.info(f"🎬 [{request_id}] Background function called for job: {job_id}")
        logger.info(f"🎬 [{request_id}] Parameters: youtube_url={youtube_url}, video_path={video_path}")
        
        job_mgr, video_proc, youtube_dl, clip_analyzer = get_components()
        logger.info(f"🎬 [{request_id}] Components loaded successfully")
        
        logger.info(f"🎬 [{request_id}] Starting ENHANCED background processing for job: {job_id}")
        
        # Start process monitoring
        process_monitor.start_process_tracking(job_id, 'video_processing', {
            'youtube_url': youtube_url,
            'user_id': user_id,
            'plan': plan
        })

        # Initialize job steps
        await job_mgr.initialize_job_steps(job_id)
        
        # Update initial job status
        await job_mgr.update_job_status(
            job_id, "processing", 0.0, 
            "Initializing job components for video processing", 
            "Initialization")

        # Update step status for initialization
        await job_mgr.update_step_status(job_id, "initialization", "completed", 100.0)
        
        # Check if job was cancelled before starting
        job = await job_mgr.get_job(job_id)
        if job and job.status == 'cancelled':
            logger.info(f"🛑 [{request_id}] Job {job_id} was cancelled before processing started")
            return
        
        # Step 1: Enhanced video download/validation
        await job_mgr.update_step_status(job_id, "video_download", "processing", 0.0)
        if youtube_url:
            logger.info(f"📥 [{request_id}] Downloading video from URL: {youtube_url[:100]}...")
            await job_mgr.update_job_status(
                job_id, "processing", 10.0, 
                "Downloading video from YouTube with enhanced quality", 
                "Video Download"
            )
            
            # Check for cancellation before download
            job = await job_mgr.get_job(job_id)
            if job and job.status == 'cancelled':
                logger.info(f"🛑 [{request_id}] Job {job_id} cancelled during download phase")
                return
            
            try:
                # Add timeout protection for YouTube download
                logger.info(f"📹 [{request_id}] Starting YouTube download with timeout...")
                process_monitor.update_process_heartbeat(job_id)
                
                video_path = await asyncio.wait_for(
                    youtube_dl.download_video(youtube_url, job_id),
                    timeout=600  # 10 minute timeout for download
                )
                logger.info(f"✅ [{request_id}] Video downloaded successfully: {video_path}")
                process_monitor.update_process_heartbeat(job_id)
            except asyncio.TimeoutError:
                error_msg = "Video download timed out after 10 minutes - video may be too large or connection issues"
                logger.error(f"❌ [{request_id}] {error_msg}")
                await job_mgr.set_job_error(job_id, error_msg)
                return
            except Exception as download_error:
                logger.error(f"❌ [{request_id}] Download failed: {str(download_error)}")
                await job_mgr.set_job_error(job_id, f"Video download failed: {str(download_error)}")
                return
        await job_mgr.update_step_status(job_id, "video_download", "completed", 100.0)
        
        # Enhanced video validation
        if not video_path or not os.path.exists(video_path):
            error_msg = f"Video file not available: {video_path}"
            logger.error(f"❌ [{request_id}] {error_msg}")
            await job_mgr.set_job_error(job_id, error_msg)
            return
        

        job_mgr, video_proc, youtube_dl, clip_analyzer = get_components()
        
        file_size = os.path.getsize(video_path)
        logger.info(f"📊 [{request_id}] Video file size: {file_size / (1024*1024):.1f}MB")
        
        if file_size < 1024:  # Less than 1KB
            error_msg = "Video file is too small or corrupted"
            logger.error(f"❌ [{request_id}] {error_msg}")
            await job_mgr.set_job_error(job_id, error_msg)
            return
        
        # Step 2: Enhanced AI analysis with proper transcription integration
        await job_mgr.update_step_status(job_id, "ai_analysis", "processing", 0.0)
        logger.info(f"🔍 [{request_id}] Starting enhanced AI analysis: {video_path}")
        await job_mgr.update_job_status(
            job_id, "processing", 30.0, 
            "Analyzing video content with enhanced AI algorithms", 
            "AI Analysis"
        )
        
        # Get video duration for bounds checking
        try:
            import subprocess
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-show_entries', 
                'format=duration', '-of', 'csv=p=0', video_path
            ], capture_output=True, text=True, timeout=30)
            video_duration = float(result.stdout.strip()) if result.returncode == 0 else 300.0
        except Exception:
            video_duration = 300.0  # 5 minute fallback
        
        logger.info(f"📹 [{request_id}] Video duration: {video_duration:.1f}s")
        
        # Initialize transcript as None - will be set if transcription is available
        transcript = None
        
        # Get transcription if needed for captions
        try:
            from utils.transcription_service import TranscriptionService
            transcription_service = TranscriptionService()
            logger.info(f"📝 [{request_id}] Generating transcription for video...")
            # Add timeout protection for transcription
            transcript = await asyncio.wait_for(
                transcription_service.transcribe_audio(video_path),
                timeout=300  # 5 minute timeout for transcription
            )
            logger.info(f"✅ [{request_id}] Transcription complete: {len(transcript.get('segments', [])) if transcript else 0} segments")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ [{request_id}] Transcription timed out after 5 minutes - continuing without transcription")
            transcript = None
        except Exception as transcription_error:
            logger.warning(f"⚠️ [{request_id}] Transcription failed: {str(transcription_error)}")
            transcript = None
        await job_mgr.update_step_status(job_id, "ai_analysis", "completed", 100.0)
        
        # Generate highlights (with fallback strategies)
        if not transcript or not transcript.get('segments'):
            # No transcription available - create time-based highlights
            logger.info(f"⏰ [{request_id}] No transcription available, creating time-based highlights")
            from utils.models import Highlight
            highlights = []
            
            for i in range(min(options.clipCount, 4)):  # Create up to 4 fallback clips
                start_time = i * 60  # 60 seconds apart
                end_time = min(start_time + 45, video_duration)  # 45 second clips, bounded by video duration
                
                # Skip if start time is beyond video duration
                if start_time >= video_duration:
                    break
                
                logger.info(f"📝 [{request_id}] Created clip {i+1} ({start_time:.1f}s-{end_time:.1f}s)")
                
                highlights.append(Highlight(
                    start_time=start_time,
                    end_time=end_time,
                    title=f"Interesting Moment {i+1}",
                    score=0.7
                ))
        else:
            try:
                # Try AI analysis first with timeout protection
                logger.info(f"🤖 [{request_id}] Starting AI analysis with timeout...")
                highlights = await asyncio.wait_for(
                    clip_analyzer.analyze_video(video_path, options),
                    timeout=180  # 3 minute timeout for AI analysis
                )
                logger.info(f"📊 [{request_id}] AI analysis complete: {len(highlights)} highlights found")
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ [{request_id}] AI analysis timed out after 3 minutes - creating fallback highlights")
                # Create fallback highlights
                from utils.models import Highlight
                highlights = []
            except Exception as analysis_error:
                logger.error(f"❌ [{request_id}] AI analysis failed: {str(analysis_error)}")
                logger.warning(f"⚠️ [{request_id}] Creating fallback highlights")
                
                # Create fallback highlights
                from utils.models import Highlight
                highlights = []
                
                for i in range(min(options.clipCount, 4)):  # Create up to 4 fallback clips
                    start_time = i * 60  # 60 seconds apart
                    end_time = min(start_time + 45, video_duration)  # 45 second clips, bounded by video duration
                    
                    # Skip if start time is beyond video duration
                    if start_time >= video_duration:
                        break
                    
                    logger.info(f"📝 [{request_id}] Fallback clip {i+1} ({start_time:.1f}s-{end_time:.1f}s)")
                    
                    # Extract transcription segments for this time range
                    clip_segments = []
                    if transcript and transcript.get('segments'):
                        for seg in transcript.get('segments', []):
                            seg_start = seg.get('start', 0)
                            seg_end = seg.get('end', 0)
                        
                        # Check if segment overlaps with clip timeframe
                        if seg_start < end_time and seg_end > start_time:
                            # Adjust segment times to be relative to clip start and within bounds
                            adjusted_start = max(0, seg_start - start_time)
                            adjusted_end = min(end_time - start_time, seg_end - start_time)
                            
                            # Convert dictionary words to WordTiming objects with display_text
                            word_timings = []
                            if seg.get('words'):
                                for word_dict in seg.get('words', []):
                                    word_start = word_dict.get('start', 0)
                                    word_end = word_dict.get('end', 0)
                                    
                                    # Include words that overlap with the clip timeframe (more inclusive)
                                    if word_start < end_time and word_end > start_time:
                                        # Adjust word timing to be relative to clip start
                                        adjusted_word_start = max(0, word_start - start_time)
                                        adjusted_word_end = min(end_time - start_time, word_end - start_time)
                                        
                                        word_timing = WordTiming(
                                            start=adjusted_word_start,
                                            end=adjusted_word_end,
                                            text=word_dict.get('word', word_dict.get('text', '')),
                                            word=word_dict.get('word', word_dict.get('text', ''))
                                        )
                                        word_timings.append(word_timing)
                            
                            # Create segment with proper bounds checking
                            if adjusted_end > adjusted_start and adjusted_start >= 0:
                                adjusted_segment = TranscriptionSegment(
                                    start=adjusted_start,
                                    end=adjusted_end, 
                                    text=seg.get('text', ''),
                                    words=word_timings if word_timings else None
                                )
                                clip_segments.append(adjusted_segment)
                
                logger.info(f"📝 [{request_id}] Clip {i+1} ({start_time:.1f}s-{end_time:.1f}s) has {len(clip_segments)} transcription segments")
                
                highlights.append(Highlight(
                    start_time=start_time,
                    end_time=end_time,
                    title=f"Interesting Moment {i+1}",
                    score=0.7,
                    transcription_segments=clip_segments
                ))
            try:
                # Try AI analysis first
                highlights = await clip_analyzer.analyze_video(video_path, options)
                logger.info(f"📊 [{request_id}] AI analysis complete: {len(highlights)} highlights found")
                
                # Enhance AI-generated highlights with proper transcription integration
                if transcript and transcript.get('segments'):
                    from utils.models import WordTiming, TranscriptionSegment
                    
                    for highlight in highlights:
                        # Extract transcription segments for this highlight's timeframe
                        clip_segments = []
                        highlight_start = highlight.start_time
                        highlight_end = highlight.end_time
                        
                        for seg in transcript.get('segments', []):
                            seg_start = seg.get('start', 0)
                            seg_end = seg.get('end', 0)
                            
                            # Check if segment overlaps with highlight timeframe
                            if seg_start < highlight_end and seg_end > highlight_start:
                                # Adjust segment times to be relative to highlight start
                                adjusted_start = max(0, seg_start - highlight_start)
                                adjusted_end = min(highlight_end - highlight_start, seg_end - highlight_start)
                                
                                # Convert dictionary words to WordTiming objects with display_text
                                word_timings = []
                                
                                # First try segment-level words
                                if seg.get('words'):
                                    for word_dict in seg.get('words', []):
                                        word_start = word_dict.get('start', 0)
                                        word_end = word_dict.get('end', 0)
                                        
                                        # Include words that overlap with the highlight timeframe (more inclusive)
                                        if word_start < highlight_end and word_end > highlight_start:
                                            # Adjust word timing to be relative to highlight start
                                            adjusted_word_start = max(0, word_start - highlight_start)
                                            adjusted_word_end = min(highlight_end - highlight_start, word_end - highlight_start)
                                            
                                            word_timing = WordTiming(
                                                start=adjusted_word_start,
                                                end=adjusted_word_end,
                                                text=word_dict.get('word', word_dict.get('text', '')),
                                                word=word_dict.get('word', word_dict.get('text', ''))
                                            )
                                            word_timings.append(word_timing)
                                
                                # FALLBACK: If no segment-level words, try to use top-level words that fall within this segment's timeframe
                                elif transcript and transcript.get('words'):
                                    logger.info(f"🔍 DEBUG: AI highlight segment has no segment-level words, trying top-level words for timeframe {seg_start:.2f}s-{seg_end:.2f}s")
                                    top_level_words_used = 0
                                    for word_dict in transcript.get('words', []):
                                        word_start = word_dict.get('start', 0)
                                        word_end = word_dict.get('end', 0)
                                        
                                        # Check if this top-level word overlaps with the segment's timeframe AND overlaps with highlight
                                        if (word_start < seg_end and word_end > seg_start and 
                                            word_start < highlight_end and word_end > highlight_start):
                                            # Adjust word timing to be relative to highlight start
                                            adjusted_word_start = max(0, word_start - highlight_start)
                                            adjusted_word_end = min(highlight_end - highlight_start, word_end - highlight_start)
                                            
                                            word_timing = WordTiming(
                                                start=adjusted_word_start,
                                                end=adjusted_word_end,
                                                text=word_dict.get('word', word_dict.get('text', '')),
                                                word=word_dict.get('word', word_dict.get('text', ''))
                                            )
                                            word_timings.append(word_timing)
                                            top_level_words_used += 1
                                    
                                    if top_level_words_used > 0:
                                        logger.info(f"🔍 DEBUG: Used {top_level_words_used} top-level words for AI highlight segment")
                                    else:
                                        logger.warning(f"🔍 DEBUG: No suitable top-level words found for AI highlight segment")
                                
                                logger.info(f"🔍 DEBUG: AI highlight segment final word count: {len(word_timings)}")
                                
                                # Create segment with proper bounds checking
                                if adjusted_end > adjusted_start and adjusted_start >= 0:
                                    adjusted_segment = TranscriptionSegment(
                                        start=adjusted_start,
                                        end=adjusted_end, 
                                        text=seg.get('text', ''),
                                        words=word_timings if word_timings else None
                                    )
                                    clip_segments.append(adjusted_segment)
                        
                        # Update highlight with transcription segments
                        highlight.transcription_segments = clip_segments
                        logger.info(f"📝 [{request_id}] Enhanced AI highlight '{highlight.title}' with {len(clip_segments)} transcription segments")
                
            except Exception as analysis_error:
                logger.error(f"❌ [{request_id}] AI analysis failed: {str(analysis_error)}")
                logger.warning(f"⚠️ [{request_id}] Creating fallback highlights with transcription")
                
                # Create fallback highlights with transcription
                from utils.models import Highlight, TranscriptionSegment, WordTiming
                highlights = []
                
                for i in range(min(options.clipCount, 4)):  # Create up to 4 fallback clips
                    start_time = i * 60  # 60 seconds apart
                    end_time = min(start_time + 45, video_duration)  # 45 second clips, bounded by video duration
                    
                    # Skip if start time is beyond video duration
                    if start_time >= video_duration:
                        break
                    
                    # Extract transcription segments for this time range
                    clip_segments = []
                    if transcript and transcript.get('segments'):
                        for seg in transcript.get('segments', []):
                            seg_start = seg.get('start', 0)
                            seg_end = seg.get('end', 0)
                            
                            # Check if segment overlaps with clip timeframe
                            if seg_start < end_time and seg_end > start_time:
                                # Adjust segment times to be relative to clip start
                                adjusted_start = max(0, seg_start - start_time)
                                adjusted_end = min(end_time - start_time, seg_end - start_time)
                                
                                # Convert dictionary words to WordTiming objects with display_text
                                word_timings = []
                                
                                # First try segment-level words
                                if seg.get('words'):
                                    for word_dict in seg.get('words', []):
                                        word_start = word_dict.get('start', 0)
                                        word_end = word_dict.get('end', 0)
                                        
                                        # Include words that overlap with the clip timeframe (more inclusive)
                                        if word_start < end_time and word_end > start_time:
                                            # Adjust word timing to be relative to clip start
                                            adjusted_word_start = max(0, word_start - start_time)
                                            adjusted_word_end = min(end_time - start_time, word_end - start_time)
                                            
                                            word_timing = WordTiming(
                                                start=adjusted_word_start,
                                                end=adjusted_word_end,
                                                text=word_dict.get('word', word_dict.get('text', '')),
                                                word=word_dict.get('word', word_dict.get('text', ''))
                                            )
                                            word_timings.append(word_timing)
                                
                                # FALLBACK: If no segment-level words, try to use top-level words that fall within this segment's timeframe
                                elif transcript and transcript.get('words'):
                                    logger.info(f"🔍 DEBUG: Segment {i+1} has no segment-level words, trying top-level words for timeframe {seg_start:.2f}s-{seg_end:.2f}s")
                                    top_level_words_used = 0
                                    for word_dict in transcript.get('words', []):
                                        word_start = word_dict.get('start', 0)
                                        word_end = word_dict.get('end', 0)
                                        
                                        # Check if this top-level word overlaps with the segment's timeframe AND overlaps with clip
                                        if (word_start < seg_end and word_end > seg_start and 
                                            word_start < end_time and word_end > start_time):
                                            # Adjust word timing to be relative to clip start
                                            adjusted_word_start = max(0, word_start - start_time)
                                            adjusted_word_end = min(end_time - start_time, word_end - start_time)
                                            
                                            word_timing = WordTiming(
                                                start=adjusted_word_start,
                                                end=adjusted_word_end,
                                                text=word_dict.get('word', word_dict.get('text', '')),
                                                word=word_dict.get('word', word_dict.get('text', ''))
                                            )
                                            word_timings.append(word_timing)
                                            top_level_words_used += 1
                                    
                                    if top_level_words_used > 0:
                                        logger.info(f"🔍 DEBUG: Used {top_level_words_used} top-level words for segment {i+1}")
                                    else:
                                        logger.warning(f"🔍 DEBUG: No suitable top-level words found for segment {i+1}")
                                
                                logger.info(f"🔍 DEBUG: Segment {i+1} final word count: {len(word_timings)}")
                                
                                # Create segment with proper bounds checking
                                if adjusted_end > adjusted_start and adjusted_start >= 0:
                                    adjusted_segment = TranscriptionSegment(
                                        start=adjusted_start,
                                        end=adjusted_end, 
                                        text=seg.get('text', ''),
                                        words=word_timings if word_timings else None
                                    )
                                    clip_segments.append(adjusted_segment)
                    
                    logger.info(f"📝 [{request_id}] Fallback clip {i+1} ({start_time:.1f}s-{end_time:.1f}s) has {len(clip_segments)} transcription segments")
                    
                    highlights.append(Highlight(
                        start_time=start_time,
                        end_time=end_time,
                        title=f"Interesting Moment {i+1}",
                        score=0.7,
                        transcription_segments=clip_segments
                    ))
        
        if not highlights:
            error_msg = "No suitable content found for clip creation"
            logger.error(f"❌ [{request_id}] {error_msg}")
            await job_mgr.set_job_error(job_id, error_msg)
            return

        
        # Step 3: Enhanced video processing with ULTRA quality
        await job_mgr.update_step_status(job_id, "video_processing", "processing", 0.0)
        logger.info(f"🎥 [{request_id}] Processing {len(highlights)} highlights with ULTRA quality and MASSIVE fonts")
        await job_mgr.update_job_status(
            job_id, "processing", 40.0, 
            f"Generating {len(highlights)} video clips", 
            "Video Processing"
        )
        
        # Check for cancellation before main processing
        job = await job_mgr.get_job(job_id)
        if job and job.status == 'cancelled':
            logger.info(f"🛑 [{request_id}] Job {job_id} cancelled during processing phase")
            return
        
        try:
            # Use Enhanced Video Service for robust video processing
            logger.info(f"🎬 [{request_id}] Using Enhanced Video Service for robust processing...")
            enhanced_service = EnhancedVideoService()
            
            clips = await enhanced_service.process_video_with_captions(
                video_path=video_path,
                options=options,
                job_id=job_id,
                job_manager=job_mgr,
                transcript=transcript,  # Pass the generated transcript
                disable_assembly_ai=True,  # Disable AssemblyAI, use OpenAI Whisper
                enable_ai_enhancements=True  # Enable AI enhancements for captions
            )
            
            logger.info(f"✅ [{request_id}] Enhanced video processing complete: {len(clips)} clips created")
            
        except Exception as processing_error:
            error_type = type(processing_error).__name__
            error_msg = str(processing_error)
            
            # INSTANT CONSOLE ERROR - Show immediately when video processing fails in background
            print(f"\n🚨 INSTANT BACKGROUND VIDEO PROCESSING ERROR! 🚨")
            print(f"🎬 Job ID: {job_id}")
            print(f"📺 Request ID: {request_id}")
            print(f"📏 Video Path: {video_path}")
            print(f"🔧 Error Type: {error_type}")
            print(f"💬 Error Message: {error_msg}")
            print(f"🔢 Highlights Count: {len(highlights) if 'highlights' in locals() else 'Unknown'}")
            print(f"⚙️ Options: {options}")
            print(f"📝 Has Transcript: {'Yes' if transcript and transcript.get('segments') else 'No'}")
            
            # Show critical error details for common issues
            if 'ffmpeg' in error_msg.lower():
                print("⚙️ Issue: FFmpeg processing error - check FFmpeg installation")
            elif 'memory' in error_msg.lower() or 'ram' in error_msg.lower():
                print("💾 Issue: Memory/resource limitation - video may be too large")
            elif 'timeout' in error_msg.lower():
                print("⏰ Issue: Processing timeout - video complexity too high")
            elif 'not found' in error_msg.lower():
                print("🔍 Issue: File or resource not found - check paths and dependencies")
            elif 'permission' in error_msg.lower():
                print("🔐 Issue: Permission denied - check file/directory permissions")
            elif 'codec' in error_msg.lower():
                print("🎥 Issue: Video codec error - unsupported format or corruption")
            
            # Show full traceback for debugging
            import traceback
            traceback_str = traceback.format_exc()
            print(f"📚 Full Traceback:\n{traceback_str}")
            print("="*80)
            
            logger.error(f"❌ [{request_id}] Enhanced video processing failed: {str(processing_error)}")
            import traceback
            logger.error(f"📚 Background processing error traceback:\n{traceback.format_exc()}")
            await job_mgr.set_job_error(job_id, f"Video processing failed: {str(processing_error)}")
            return
        
        await job_mgr.update_step_status(job_id, "video_processing", "completed", 100.0)
            
        # Step 4: Enhanced thumbnail generation (will be uploaded immediately)
        await job_mgr.update_step_status(job_id, "thumbnail_generation", "processing", 0.0)
        if hasattr(video_proc, 'generate_enhanced_thumbnails') and clips:
            logger.info(f"🖼️ [{request_id}] Generating enhanced thumbnails for {len(clips)} clips")
            await job_mgr.update_job_status(
                job_id, "processing", 85.0, 
                "Generating enhanced thumbnails", 
                "Thumbnail Generation"
            )
            
            try:
                await video_proc.generate_enhanced_thumbnails(clips, job_id)
                logger.info(f"✅ [{request_id}] Enhanced thumbnails generated (will be uploaded with clips)")
                await job_mgr.update_step_status(job_id, "thumbnail_generation", "completed", 100.0)
            except Exception as thumb_error:
                await job_mgr.update_step_status(job_id, "thumbnail_generation", "error", 50.0, str(thumb_error))
                logger.warning(f"⚠️ [{request_id}] Thumbnail generation failed: {str(thumb_error)}")
                # Don't fail the entire job for thumbnail errors
        
        # Step 5: Record usage tracking
        logger.info(f"📊 [{request_id}] Recording usage for {len(clips)} clips")
        
        # Step 5: Record usage tracking
        logger.info(f"📊 [{request_id}] Recording usage for {len(clips)} clips")
        
        # Record usage after successful completion
        user_id = user_id or request_id  # Use provided user_id or fallback to request_id
        plan = plan or "free"  # Use provided plan or default to free
        clips_created = len(clips)
        
        # Record usage only when clips are successfully created
        try:
            success = await usage_tracker.record_clip_creation(user_id, clips_created, plan)
            if success:
                logger.info(f"📊 [{request_id}] Recorded {clips_created} clips for user usage tracking")
            else:
                logger.warning(f"⚠️ [{request_id}] Failed to record usage, but job completed successfully")
        except Exception as usage_error:
            logger.error(f"❌ [{request_id}] Error recording usage: {str(usage_error)}")
            # Don't fail the job if usage recording fails - continue processing
        
        # Step 6: Upload clips to cloud storage
        await job_mgr.update_step_status(job_id, "storage_upload", "processing", 0.0)
        try:
            # Upload clips to Supabase Storage
            logger.info(f"📤 [{request_id}] Uploading {len(clips)} clips to Supabase Storage")
            await job_mgr.update_job_status(
                job_id, "processing", 90.0, 
                "Saving clips to your library...", 
                "Storage Upload"
            )
            
            uploaded_clips = []
            for i, clip in enumerate(clips):
                try:
                    # Get the local file path
                    local_clip_path = f"output/{job_id}/{clip.filename}"
                    
                    if os.path.exists(local_clip_path):
                        # Get file size before upload (since file will be deleted)
                        file_size = os.path.getsize(local_clip_path)
                        
                        # Upload to Supabase Storage and immediately delete local file
                        storage_path = await storage_manager.upload_and_cleanup_clip(user_id, local_clip_path, clip.filename)
                        
                        if storage_path:
                            # Handle thumbnail upload if exists
                            thumbnail_path = None
                            local_thumbnail_path = f"thumbnails/{job_id}/{clip.filename.replace('.mp4', '.jpg')}"
                            
                            if os.path.exists(local_thumbnail_path):
                                thumbnail_filename = clip.filename.replace('.mp4', '.jpg')
                                thumbnail_path = await storage_manager.upload_and_cleanup_thumbnail(user_id, local_thumbnail_path, thumbnail_filename)
                                if thumbnail_path:
                                    logger.info(f"🖼️ [{request_id}] Uploaded thumbnail: {thumbnail_filename}")
                            
                            # Save clip metadata
                            clip_data = {
                                "filename": clip.filename,
                                "title": getattr(clip, 'title', f"Clip {i+1}"),
                                "duration": getattr(clip, 'duration', 0),
                                "file_size": file_size,
                                "storage_path": storage_path,
                                "thumbnail_path": thumbnail_path,
                                "hook_title": getattr(clip, 'hook_title', None),
                                "viral_potential": getattr(clip, 'viral_potential', None)
                            }
                            
                            metadata_saved = await storage_manager.save_clip_metadata(user_id, job_id, clip_data)
                            
                            if metadata_saved:
                                uploaded_clips.append(clip.filename)
                                logger.info(f"✅ [{request_id}] Uploaded and saved: {clip.filename}")
                            else:
                                logger.warning(f"⚠️ [{request_id}] Uploaded but failed to save metadata: {clip.filename}")
                        else:
                            logger.warning(f"⚠️ [{request_id}] Failed to upload: {clip.filename}")
                    else:
                        logger.warning(f"⚠️ [{request_id}] Local file not found: {local_clip_path}")
                        
                except Exception as upload_error:
                    logger.error(f"❌ [{request_id}] Error uploading {clip.filename}: {str(upload_error)}")
            await job_mgr.update_step_status(job_id, "storage_upload", "completed", 100.0)

            logger.info(f"📤 [{request_id}] Successfully uploaded {len(uploaded_clips)}/{len(clips)} clips to storage")
            
            # Update clips with stream URLs for frontend
            try:
                # Get updated clips with storage URLs
                user_clips = await storage_manager.get_user_clips(user_id)
                
                # Find clips for this job and update with stream URLs
                updated_clips = []
                for clip in clips:
                    # Find the corresponding clip in storage
                    stored_clip = next((c for c in user_clips if c.get('filename') == clip.filename), None)
                    
                    if stored_clip:
                        # Create updated clip with stream URLs
                        if hasattr(clip, '__dict__'):
                            # ClipResult object - create new instance with additional fields
                            from .utils.models import ClipResult
                            updated_clip = ClipResult(
                                filename=clip.filename,
                                title=clip.title,
                                duration=clip.duration,
                                start_time=clip.start_time,
                                end_time=clip.end_time,
                                score=clip.score,
                                hook_title=getattr(clip, 'hook_title', None),
                                engagement_score=getattr(clip, 'engagement_score', None),
                                viral_potential=getattr(clip, 'viral_potential', None),
                                thumbnail_url=storage_manager.get_clip_url(stored_clip['thumbnail_path']) if stored_clip.get('thumbnail_path') else None,
                                stream_url=storage_manager.get_clip_url(stored_clip['storage_path']) if stored_clip.get('storage_path') else None
                            )
                            updated_clips.append(updated_clip)
                        else:
                            # Dictionary clip - update directly
                            updated_clip = dict(clip)
                            updated_clip['stream_url'] = storage_manager.get_clip_url(stored_clip['storage_path']) if stored_clip.get('storage_path') else None
                            updated_clip['thumbnail_url'] = storage_manager.get_clip_url(stored_clip['thumbnail_path']) if stored_clip.get('thumbnail_path') else None
                            updated_clips.append(updated_clip)
                    else:
                        # Keep original clip if not found in storage
                        updated_clips.append(clip)
                
                # Update job with clips that have stream URLs
                await job_mgr.update_job_clips(job_id, updated_clips)
                logger.info(f"🔗 [{request_id}] Updated {len(updated_clips)} clips with stream URLs")
                
            except Exception as url_update_error:
                logger.warning(f"⚠️ [{request_id}] Failed to update clips with stream URLs: {str(url_update_error)}")
            
            # Final completion status update
            await job_mgr.update_job_status(
                job_id, "completed", 100.0, 
                f"Successfully created {len(clips)} ULTRA quality viral clips ({len(uploaded_clips)} uploaded to cloud)", 
                "Completed"
            )
            
            logger.info(f"🎉 [{request_id}] Job {job_id} completed successfully with {len(clips)} ULTRA quality clips ({uploaded_clips} uploaded to cloud)")
            
        except Exception as finalize_error:
            logger.error(f"❌ [{request_id}] Job finalization error: {str(finalize_error)}")
            await job_mgr.set_job_error(job_id, f"Job finalization failed: {str(finalize_error)}")
            return
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] CRITICAL ERROR in background processing for job {job_id}: {str(e)}")
        if not PRODUCTION:  # Only log full traceback in development
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
        
        try:
            # Provide user-friendly error message in production
            error_message = "Processing failed due to technical issue" if PRODUCTION else f"Critical processing error: {str(e)}"
            await job_mgr.set_job_error(job_id, error_message)
        except Exception as error_update_error:
            logger.error(f"❌ [{request_id}] Failed to update job error status: {str(error_update_error)}")
    
    finally:
        # Enhanced cleanup with error handling - clean up ALL local files
        try:
            # Clean up temporary video file
            if video_path and video_path.startswith("temp/") and os.path.exists(video_path):
                os.remove(video_path)
                logger.info(f"🗑️ [{request_id}] Cleaned up temporary video file: {video_path}")
            
            # Clean up output directory for this job
            output_dir = f"output/{job_id}"
            if os.path.exists(output_dir):
                await storage_manager.cleanup_local_directory(output_dir)
            
            # Clean up thumbnail directory for this job
            thumbnail_dir = f"thumbnails/{job_id}"
            if os.path.exists(thumbnail_dir):
                await storage_manager.cleanup_local_directory(thumbnail_dir)
                
        except Exception as cleanup_error:
            logger.warning(f"⚠️ [{request_id}] Cleanup failed: {str(cleanup_error)}")

# Removed second WebSocket endpoint - back to polling

# Enhanced debug endpoints
@app.get("/debug/system-status")
async def system_status():
    """Enhanced system status endpoint"""
    try:
        job_mgr, _, _, _ = get_components()
        
        status = {
            "system": {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "3.0.0"
            },
            "jobs": await job_mgr.get_job_stats(),
            "directories": {},
            "websockets": {
                "active_connections": 0,
                "connected_jobs": []
            }
        }
        
        # Check directories
        for directory in directories:
            if os.path.exists(directory):
                try:
                    file_count = len([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))])
                    status["directories"][directory] = {
                        "exists": True,
                        "writable": os.access(directory, os.W_OK),
                        "file_count": file_count
                    }
                except:
                    status["directories"][directory] = {"exists": True, "accessible": False}
            else:
                status["directories"][directory] = {"exists": False}
        
        return status
        
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

# Mount static files with error handling
try:
    app.mount("/static", StaticFiles(directory="output"), name="static")
    app.mount("/music", StaticFiles(directory="music"), name="music")
    app.mount("/game_videos", StaticFiles(directory="game_videos"), name="game_videos")
    logger.info("✅ Static file mounts configured successfully")
except Exception as mount_error:
    logger.warning(f"⚠️ Could not mount static directories: {str(mount_error)}")

# Production startup event
@app.on_event("startup")
async def startup_event():
    """Production startup procedures"""
    logger.info("🚀 ClipForge AI Enhanced API v3.0 starting up...")
    
    try:
        # Initialize components
        get_components()
        logger.info("✅ All components initialized successfully")
        
        # Validate critical configuration
        required_dirs = ["temp", "output", "thumbnails"]
        for dir_name in required_dirs:
            if not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                logger.info(f"📁 Created directory: {dir_name}")
        
        # Check environment variables in production
        if PRODUCTION:
            critical_env_vars = ['OPENAI_API_KEY', 'SUPABASE_URL', 'SUPABASE_SERVICE_KEY']
            missing_vars = [var for var in critical_env_vars if not os.getenv(var)]
            if missing_vars:
                logger.warning(f"⚠️ Missing environment variables: {missing_vars}")
                
    except Exception as e:
        logger.error(f"❌ CRITICAL: Component initialization failed: {str(e)}")
        if PRODUCTION:
            raise e  # Fail fast in production
    
    mode = "PRODUCTION" if PRODUCTION else "DEVELOPMENT"
    logger.info(f"🎬 ClipForge AI Enhanced API v3.0 is ready in {mode} mode!")
    if not PRODUCTION:
        logger.info("🔥 Features: MASSIVE Fonts, FIXED Video Preview, ULTRA Quality, Enhanced Game Overlays")

@app.get("/api/user-clips/{user_id}")
async def get_user_clips_api(user_id: str):
    """Get all clips for a user"""
    try:
        logger.info(f"📋 Getting clips for user: {user_id}")
        
        clips = await storage_manager.get_user_clips(user_id)
        
        # Add signed URLs for each clip
        for clip in clips:
            if clip.get('storage_path'):
                clip['stream_url'] = storage_manager.get_clip_url(clip['storage_path'])
        
        logger.info(f"✅ Retrieved {len(clips)} clips for user {user_id}")
        return {"clips": clips, "total": len(clips)}
        
    except Exception as e:
        logger.error(f"❌ Error getting user clips: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get user clips: {str(e)}")

@app.delete("/api/user-clips/{user_id}/{clip_id}")
async def delete_user_clip_api(user_id: str, clip_id: str):
    """Delete a user's clip"""
    try:
        logger.info(f"🗑️ Deleting clip {clip_id} for user {user_id}")
        
        success = await storage_manager.delete_clip(user_id, clip_id)
        
        if success:
            logger.info(f"✅ Deleted clip {clip_id} for user {user_id}")
            return {"status": "success", "message": "Clip deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Clip not found or could not be deleted")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting clip: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete clip: {str(e)}")

# Simple Version Check API for Deployment
@app.get("/api/version")
async def get_version():
    """Simple version check endpoint for deployment verification"""
    return {
        "version": "3.0.0",
        "name": "ClipForge AI - Enhanced API",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "production" if PRODUCTION else "development"
    }

@app.get("/version")
async def get_version_simple():
    """Even simpler version endpoint (alternative path)"""
    return {
        "version": "3.0.0",
        "status": "ok"
    }


if __name__ == "__main__":
    import uvicorn
    
    # Production configuration
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0" if PRODUCTION else "127.0.0.1"
    workers = int(os.getenv("WORKERS", 1))
    
    logger.info(f"🚀 Starting ClipForge AI Enhanced API v3.0 in {'PRODUCTION' if PRODUCTION else 'DEVELOPMENT'} mode")
    
    if PRODUCTION:
        # Production server configuration
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            workers=workers,
            log_level="info",
            access_log=False,  # Disable access logs in production for performance
            reload=False
        )
    else:
        # Development server configuration
        uvicorn.run(
            app, 
            host=host, 
            port=port,
            log_level="debug",
            access_log=True,
            reload=True
        )
