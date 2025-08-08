import asyncio
import json
import logging
import os
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from .models import ProcessingJob, ClipResult, safe_serialize_clips, ProcessingStep

logger = logging.getLogger(__name__)

class EnhancedJobManager:
    def __init__(self):
        # Use in-memory storage with Redis persistence
        self.jobs: Dict[str, ProcessingJob] = {}
        self.job_logs: Dict[str, List[str]] = {}
        self.job_performance: Dict[str, Dict[str, Any]] = {}
        
        # Initialize Redis connection with fallback
        self.redis_client = None
        self.redis_enabled = False
        self._init_redis()
        
        logger.info(f"🚀 EnhancedJobManager initialized - Redis: {'✅ Enabled' if self.redis_enabled else '❌ Disabled (in-memory only)'}")
    
    def _init_redis(self):
        """Initialize Redis connection with error handling for AWS/Ubuntu"""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            
            # Enhanced connection with AWS/Ubuntu specific settings
            self.redis_client = redis.from_url(
                redis_url, 
                decode_responses=True,
                socket_connect_timeout=10,  # 10 second connection timeout
                socket_timeout=5,           # 5 second operation timeout
                retry_on_timeout=True,      # Retry on timeout
                health_check_interval=30    # Health check every 30 seconds
            )
            
            # Test connection with retry logic for AWS
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.redis_client.ping()
                    self.redis_enabled = True
                    logger.info(f"✅ Redis connected on attempt {attempt + 1}: {redis_url}")
                    break
                except redis.ConnectionError as conn_err:
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ Redis connection attempt {attempt + 1} failed, retrying...")
                        import time
                        time.sleep(2)  # Wait 2 seconds before retry
                        continue
                    else:
                        raise conn_err
            
        except Exception as redis_error:
            logger.warning(f"⚠️ Redis connection failed, using in-memory only: {redis_error}")
            self.redis_client = None
            self.redis_enabled = False
    
    async def _save_job_to_redis(self, job: ProcessingJob):
        """Save job to Redis for persistence"""
        if not self.redis_enabled:
            return
        
        try:
            job_data = {
                'job_id': job.job_id,
                'status': job.status,
                'progress': job.progress,
                'message': job.message,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'updated_at': job.updated_at.isoformat() if job.updated_at else None,
                'current_step': job.current_step,
                'estimated_time_remaining': job.estimated_time_remaining,
                'user_id': getattr(job, 'user_id', None),
                'plan': getattr(job, 'plan', 'free'),
                'youtube_url': job.youtube_url,
                'clips_count': len(job.clips)
            }
            
            # Save job metadata
            self.redis_client.hset(f"job:{job.job_id}", mapping=job_data)
            self.redis_client.expire(f"job:{job.job_id}", 604800)  # 1 week expiry
            
            # Save clips if completed
            if job.status == 'completed' and job.clips:
                clips_data = safe_serialize_clips(job.clips)
                self.redis_client.set(f"clips:{job.job_id}", json.dumps({'clips': clips_data}))
                self.redis_client.expire(f"clips:{job.job_id}", 604800)  # 1 week expiry
            
            logger.debug(f"💾 Saved job {job.job_id} to Redis")
            
        except Exception as e:
            logger.error(f"❌ Failed to save job {job.job_id} to Redis: {e}")
    
    async def _load_job_from_redis(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load job data from Redis"""
        if not self.redis_enabled:
            return None
        
        try:
            job_data = self.redis_client.hgetall(f"job:{job_id}")
            if not job_data:
                return None
            
            # Convert back to proper types
            if job_data.get('progress'):
                job_data['progress'] = float(job_data['progress'])
            if job_data.get('estimated_time_remaining'):
                job_data['estimated_time_remaining'] = int(job_data['estimated_time_remaining'])
            if job_data.get('clips_count'):
                job_data['clips_count'] = int(job_data['clips_count'])
            
            # Load clips if available
            if job_data.get('status') == 'completed':
                clips_data = self.redis_client.get(f"clips:{job_id}")
                if clips_data:
                    clips_info = json.loads(clips_data)
                    job_data['clips'] = clips_info.get('clips', [])
                else:
                    job_data['clips'] = []
            else:
                job_data['clips'] = []
            
            logger.debug(f"📥 Loaded job {job_id} from Redis")
            return job_data
            
        except Exception as e:
            logger.error(f"❌ Failed to load job {job_id} from Redis: {e}")
            return None
    
    async def create_job(self, job: ProcessingJob) -> ProcessingJob:
        """Enhanced job creation with Redis persistence"""
        try:
            # Validate job data
            if not job.job_id:
                raise ValueError("Job ID is required")
            
            if job.job_id in self.jobs:
                raise ValueError(f"Job {job.job_id} already exists")
            
            # Set timestamps
            if not job.created_at:
                job.created_at = datetime.now()
            job.updated_at = datetime.now()
            
            # Initialize tracking
            self.job_logs[job.job_id] = []
            self.job_performance[job.job_id] = {
                'start_time': datetime.now().timestamp(),
                'steps_completed': 0,
                'total_steps': 5,
                'errors': [],
                'warnings': []
            }
            
            # Store job in memory and Redis
            self.jobs[job.job_id] = job
            await self._save_job_to_redis(job)
            
            await self._log_job_event(job.job_id, f"✅ Job created: {job.message}")
            logger.info(f"✅ Enhanced job created: {job.job_id}")
            return job
            
        except Exception as e:
            logger.error(f"❌ Error creating job: {str(e)}")
            raise Exception(f"Failed to create job: {str(e)}")
    
    async def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Get job with Redis fallback"""
        try:
            if not job_id:
                logger.warning("⚠️ Empty job_id requested")
                return None
            
            # First try in-memory
            job = self.jobs.get(job_id)
            if job:
                logger.debug(f"📄 Retrieved job {job_id} from memory: {job.status} ({job.progress}%)")
                return job
            
            # Fallback to Redis if not in memory
            logger.debug(f"🔍 Job {job_id} not in memory, checking Redis...")
            redis_data = await self._load_job_from_redis(job_id)
            if redis_data:
                logger.info(f"📥 Loaded job {job_id} from Redis fallback")
                return redis_data  # Return dict instead of ProcessingJob for API compatibility
            
            logger.warning(f"⚠️ Job {job_id} not found in memory or Redis")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting job {job_id}: {str(e)}")
            return None
    
    async def update_job_status(self, job_id: str, status: str, progress: float, message: str, current_step: Optional[str] = None):
        """Update job status with Redis persistence"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.error(f"❌ Job {job_id} not found for status update")
                return False
            
            # Handle both ProcessingJob objects and dicts from Redis
            if isinstance(job, dict):
                # Update dict directly
                job['status'] = status
                job['progress'] = max(0.0, min(100.0, float(progress)))
                job['message'] = str(message)
                job['current_step'] = str(current_step) if current_step else None
                job['updated_at'] = datetime.now().isoformat()
                
                # Create a minimal ProcessingJob-like object for Redis saving
                from types import SimpleNamespace
                redis_job = SimpleNamespace(**job)
                redis_job.clips = []  # Will be loaded separately
                await self._save_job_to_redis(redis_job)
            else:
                # Update ProcessingJob object
                job.status = status
                job.progress = max(0.0, min(100.0, float(progress)))
                job.message = str(message)
                job.current_step = str(current_step) if current_step else None
                job.updated_at = datetime.now()
                
                # Store updated job in memory and Redis
                self.jobs[job_id] = job
                await self._save_job_to_redis(job)
            
            # Enhanced logging
            await self._log_job_event(job_id, f"📊 Status: {status} ({progress:.1f}%) - {message}")
            logger.info(f"📊 Enhanced job update {job_id}: {status} - {progress:.1f}% - {message}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating job status: {str(e)}")
            await self._log_job_event(job_id, f"❌ ERROR updating status: {str(e)}")
            return False
    
    async def update_job_clips(self, job_id: str, clips: List[ClipResult]):
        """Update job clips with Redis persistence"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.error(f"❌ Job {job_id} not found for clips update")
                return False
            
            # Validate and serialize clips
            validated_clips = []
            for i, clip in enumerate(clips):
                try:
                    if isinstance(clip, ClipResult):
                        validated_clips.append(clip)
                    elif isinstance(clip, dict):
                        # Convert dict to ClipResult
                        clip_result = ClipResult(**clip)
                        validated_clips.append(clip_result)
                    else:
                        # Create fallback clip
                        fallback_clip = ClipResult(
                            filename=f"clip_{i+1}.mp4",
                            title=f"Clip {i+1}",
                            duration=30.0,
                            start_time=0.0,
                            end_time=30.0,
                            score=0.5
                        )
                        validated_clips.append(fallback_clip)
                except Exception as clip_error:
                    logger.warning(f"⚠️ Failed to process clip {i}: {clip_error}")
                    continue
            
            # Update job
            if isinstance(job, dict):
                job['clips'] = validated_clips
                job['updated_at'] = datetime.now().isoformat()
                # Save clips to Redis
                clips_data = safe_serialize_clips(validated_clips)
                if self.redis_enabled:
                    try:
                        self.redis_client.set(f"clips:{job_id}", json.dumps({'clips': clips_data}))
                        self.redis_client.expire(f"clips:{job_id}", 604800)
                    except Exception as redis_error:
                        logger.error(f"❌ Failed to save clips to Redis: {redis_error}")
            else:
                job.clips = validated_clips
                job.updated_at = datetime.now()
                self.jobs[job_id] = job
                await self._save_job_to_redis(job)
            
            await self._log_job_event(job_id, f"📹 Updated clips: {len(validated_clips)} clips processed")
            logger.info(f"📹 Enhanced clips update {job_id}: {len(validated_clips)} clips")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating job clips: {str(e)}")
            return False
    
    async def serialize_job_for_api(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Enhanced job serialization with Redis fallback"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.warning(f"⚠️ Job {job_id} not found for API serialization")
                return None
            
            # Handle both ProcessingJob objects and dicts from Redis
            if isinstance(job, dict):
                # Already serialized from Redis
                api_response = {
                    "job_id": str(job.get('job_id', job_id)),
                    "status": str(job.get('status', 'unknown')),
                    "progress": float(job.get('progress', 0)),
                    "message": str(job.get('message', 'No message')),
                    "current_step": job.get('current_step'),
                    "clips": job.get('clips', []),
                    "estimated_time_remaining": job.get('estimated_time_remaining'),
                    "created_at": job.get('created_at'),
                    "updated_at": job.get('updated_at'),
                    "clips_count": len(job.get('clips', [])),
                    "user_id": job.get('user_id'),
                    "plan": job.get('plan', 'free'),
                    "from_redis": True  # Flag to indicate Redis source
                }
            else:
                # Serialize ProcessingJob object
                serialized_clips = safe_serialize_clips(job.clips)
                
                api_response = {
                    "job_id": str(job.job_id),
                    "status": str(job.status),
                    "progress": float(job.progress),
                    "message": str(job.message),
                    "current_step": str(job.current_step) if job.current_step else None,
                    "clips": serialized_clips,
                    "estimated_time_remaining": int(job.estimated_time_remaining) if job.estimated_time_remaining else None,
                    "created_at": str(job.created_at) if job.created_at else None,
                    "updated_at": str(job.updated_at) if job.updated_at else None,
                    "clips_count": len(serialized_clips),
                    "user_id": getattr(job, 'user_id', None),
                    "plan": getattr(job, 'plan', 'free'),
                    "from_memory": True  # Flag to indicate memory source
                }
            
            logger.debug(f"📄 Enhanced API serialization complete for {job_id}")
            return api_response
            
        except Exception as e:
            logger.error(f"❌ Error serializing job {job_id} for API: {str(e)}")
            return {
                "job_id": job_id,
                "status": "error",
                "progress": 0.0,
                "message": f"Serialization error: {str(e)[:200]}",
                "clips": [],
                "error": True,
                "critical_error": str(e)
            }
    
    async def set_job_error(self, job_id: str, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """Set job to error status with Redis persistence"""
        try:
            await self.update_job_status(job_id, 'error', 0.0, f"Error: {error_message}")
            await self._log_job_event(job_id, f"❌ ERROR: {error_message}")
            
            # Track error in performance data
            if job_id in self.job_performance:
                perf = self.job_performance[job_id]
                if 'errors' not in perf:
                    perf['errors'] = []
                
                error_entry = {
                    'message': error_message,
                    'timestamp': datetime.now().timestamp(),
                    'details': error_details or {}
                }
                perf['errors'].append(error_entry)
            
            logger.error(f"❌ Enhanced job error set for {job_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"❌ Error setting job error status: {str(e)}")
    
    async def cleanup_old_jobs(self, max_age_hours: int = 168):  # 1 week default
        """Enhanced cleanup with Redis support"""
        try:
            cleanup_stats = {
                'deleted_jobs': 0,
                'memory_cleaned': 0,
                'redis_cleaned': 0,
                'errors': []
            }
            
            now = datetime.now()
            jobs_to_delete = []
            
            # Clean up memory jobs
            for job_id, job in list(self.jobs.items()):
                try:
                    if hasattr(job, 'updated_at') and job.updated_at:
                        if isinstance(job.updated_at, str):
                            updated_time = datetime.fromisoformat(job.updated_at)
                        else:
                            updated_time = job.updated_at
                        
                        age_hours = (now - updated_time).total_seconds() / 3600
                        
                        if age_hours > max_age_hours:
                            jobs_to_delete.append(job_id)
                            
                except Exception as job_error:
                    logger.warning(f"⚠️ Error checking job {job_id} for cleanup: {job_error}")
            
            # Delete old jobs from memory
            for job_id in jobs_to_delete:
                try:
                    if job_id in self.jobs:
                        del self.jobs[job_id]
                    if job_id in self.job_logs:
                        del self.job_logs[job_id]
                    if job_id in self.job_performance:
                        del self.job_performance[job_id]
                    
                    cleanup_stats['memory_cleaned'] += 1
                    
                except Exception as cleanup_error:
                    cleanup_stats['errors'].append(f"Memory cleanup failed for {job_id}: {cleanup_error}")
            
            # Clean up Redis if enabled
            if self.redis_enabled:
                try:
                    # Get all job keys from Redis
                    job_keys = self.redis_client.keys("job:*")
                    
                    for key in job_keys:
                        try:
                            job_data = self.redis_client.hgetall(key)
                            if job_data.get('updated_at'):
                                updated_time = datetime.fromisoformat(job_data['updated_at'])
                                age_hours = (now - updated_time).total_seconds() / 3600
                                
                                if age_hours > max_age_hours:
                                    job_id = key.replace("job:", "")
                                    self.redis_client.delete(key)
                                    self.redis_client.delete(f"clips:{job_id}")
                                    cleanup_stats['redis_cleaned'] += 1
                                    
                        except Exception as redis_job_error:
                            cleanup_stats['errors'].append(f"Redis job cleanup failed for {key}: {redis_job_error}")
                            
                except Exception as redis_error:
                    cleanup_stats['errors'].append(f"Redis cleanup failed: {redis_error}")
            
            cleanup_stats['deleted_jobs'] = cleanup_stats['memory_cleaned'] + cleanup_stats['redis_cleaned']
            
            if cleanup_stats['deleted_jobs'] > 0:
                logger.info(f"🗑️ Enhanced cleanup complete: {cleanup_stats['deleted_jobs']} jobs (Memory: {cleanup_stats['memory_cleaned']}, Redis: {cleanup_stats['redis_cleaned']})")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"❌ Error in enhanced cleanup: {str(e)}")
            return {'error': str(e)}
    
    async def _log_job_event(self, job_id: str, message: str):
        """Enhanced logging with timestamps"""
        try:
            if job_id not in self.job_logs:
                self.job_logs[job_id] = []
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            log_entry = f"[{timestamp}] {message}"
            
            self.job_logs[job_id].append(log_entry)
            
            # Keep only last 200 log entries per job
            if len(self.job_logs[job_id]) > 200:
                self.job_logs[job_id] = self.job_logs[job_id][-200:]
                
        except Exception as e:
            logger.error(f"❌ Failed to log event for job {job_id}: {str(e)}")
    
    def __len__(self) -> int:
        return len(self.jobs)
    
    def __contains__(self, job_id: str) -> bool:
        return job_id in self.jobs
    
    def __repr__(self) -> str:
        stats = {
            'total': len(self.jobs),
            'processing': len([j for j in self.jobs.values() if j.status == 'processing']),
            'completed': len([j for j in self.jobs.values() if j.status == 'completed']),
            'errors': len([j for j in self.jobs.values() if j.status == 'error'])
        }
        redis_status = "Redis enabled" if self.redis_enabled else "Memory only"
        return f"EnhancedJobManager(total={stats['total']}, processing={stats['processing']}, completed={stats['completed']}, errors={stats['errors']}, {redis_status})"
