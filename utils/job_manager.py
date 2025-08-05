import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

from .models import ProcessingJob, ClipResult, safe_serialize_clips, ProcessingStep

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self):
        # Use in-memory storage with enhanced error handling
        self.jobs: Dict[str, ProcessingJob] = {}
        self.job_logs: Dict[str, List[str]] = {}
        self.job_performance: Dict[str, Dict[str, Any]] = {}  # Performance tracking
        logger.info("🚀 ENHANCED JobManager initialized with ultra error handling")
    
    async def create_job(self, job: ProcessingJob) -> ProcessingJob:
        """ENHANCED: Create job with comprehensive validation and tracking"""
        try:
            # Validate job data
            if not job.job_id:
                raise ValueError("Job ID is required")
            
            if job.job_id in self.jobs:
                raise ValueError(f"Job {job.job_id} already exists")
            
            # Set timestamps
            if not job.created_at:
                job.created_at = datetime.now().isoformat()
            job.updated_at = datetime.now().isoformat()
            
            # Initialize tracking
            self.job_logs[job.job_id] = []
            self.job_performance[job.job_id] = {
                'start_time': datetime.now().timestamp(),
                'steps_completed': 0,
                'total_steps': 5,  # Default steps: download, analyze, process, thumbnails, complete
                'errors': [],
                'warnings': []
            }
            
            # Store job
            self.jobs[job.job_id] = job
            
            await self._log_job_event(job.job_id, f"✅ Job created: {job.message}")
            logger.info(f"✅ ENHANCED job created: {job.job_id}")
            return job
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR creating job: {str(e)}")
            raise Exception(f"Failed to create job: {str(e)}")
    
    async def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """ENHANCED: Get job with validation and performance tracking"""
        try:
            if not job_id:
                logger.warning("⚠️ Empty job_id requested")
                return None
            
            job = self.jobs.get(job_id)
            if job:
                logger.debug(f"📄 Retrieved job {job_id}: {job.status} ({job.progress}%)")
                
                # Update performance tracking
                if job_id in self.job_performance:
                    perf = self.job_performance[job_id]
                    perf['last_accessed'] = datetime.now().timestamp()
                    
                    # Calculate processing time if active
                    if job.status in ['processing', 'completed']:
                        elapsed = datetime.now().timestamp() - perf['start_time']
                        perf['elapsed_time'] = elapsed
                
                return job
            else:
                logger.warning(f"⚠️ Job {job_id} not found in {len(self.jobs)} jobs")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error getting job {job_id}: {str(e)}")
            return None
    
    async def update_job_status(self, job_id: str, status: str, progress: float, message: str, current_step: Optional[str] = None):
        """ENHANCED: Update job status with comprehensive validation and tracking"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.error(f"❌ Job {job_id} not found for status update")
                return False
            
            # Validate and sanitize inputs
            valid_statuses = ["queued", "processing", "completed", "error", "paused", "cancelled"]
            if status not in valid_statuses:
                logger.warning(f"⚠️ Invalid status '{status}' for job {job_id}, using 'processing'")
                status = "processing"
            
            # Validate progress
            progress = max(0.0, min(100.0, float(progress)))
            
            # Sanitize message
            if not message:
                message = f"Status: {status}"
            
            # Store previous values for logging
            old_status = job.status
            old_progress = job.progress
            
            # Update job
            job.status = status
            job.progress = progress
            job.message = str(message)
            job.current_step = str(current_step) if current_step else None
            job.updated_at = datetime.now().isoformat()
            
            # Enhanced time estimation
            if progress > 0 and progress < 100 and job.created_at:
                try:
                    created_time = datetime.fromisoformat(job.created_at)
                    elapsed_time = (datetime.now() - created_time).total_seconds()
                    
                    if progress > 5:  # Only estimate after 5% to avoid wild estimates
                        estimated_total = elapsed_time / (progress / 100)
                        job.estimated_time_remaining = max(0, int(estimated_total - elapsed_time))
                    else:
                        job.estimated_time_remaining = None
                        
                except Exception as time_error:
                    logger.warning(f"⚠️ Time estimation error: {str(time_error)}")
                    job.estimated_time_remaining = None
            elif progress >= 100:
                job.estimated_time_remaining = 0
            
            # Update performance tracking
            if job_id in self.job_performance:
                perf = self.job_performance[job_id]
                perf['last_update'] = datetime.now().timestamp()
                
                # Track step completion
                if status == "processing" and current_step:
                    step_map = {
                        "Video Download": 1,
                        "AI Analysis": 2, 
                        "Video Processing": 3,
                        "Thumbnail Generation": 4,
                        "Completed": 5
                    }
                    if current_step in step_map:
                        perf['steps_completed'] = step_map[current_step]
                
                # Track status changes
                if old_status != status:
                    if 'status_history' not in perf:
                        perf['status_history'] = []
                    perf['status_history'].append({
                        'from': old_status,
                        'to': status,
                        'timestamp': datetime.now().timestamp(),
                        'progress': progress
                    })
            
            # Store updated job
            self.jobs[job_id] = job
            
            # Enhanced logging
            progress_change = f" (+{progress - old_progress:.1f}%)" if progress > old_progress else ""
            await self._log_job_event(
                job_id, 
                f"📊 {old_status} → {status} ({progress:.1f}%{progress_change}) - {message}"
            )
            
            logger.info(f"📊 ENHANCED job update {job_id}: {status} - {progress:.1f}% - {message}")
            return True
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR updating job status: {str(e)}")
            await self._log_job_event(job_id, f"❌ ERROR updating status: {str(e)}")
            return False
    
    async def update_job_clips(self, job_id: str, clips: List[ClipResult]):
        """ENHANCED: Update job clips with comprehensive validation and serialization"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.error(f"❌ Job {job_id} not found for clips update")
                return False
            
            # Enhanced clips validation and conversion
            if not isinstance(clips, list):
                logger.error(f"❌ Clips must be a list, got {type(clips)} for job {job_id}")
                return False
            
            validated_clips = []
            conversion_errors = []
            
            for i, clip in enumerate(clips):
                try:
                    if isinstance(clip, ClipResult):
                        # Already a ClipResult, just validate
                        if not clip.filename or not clip.title:
                            logger.warning(f"⚠️ Clip {i} missing required fields")
                            clip.filename = clip.filename or f"clip_{i+1}.mp4"
                            clip.title = clip.title or f"Clip {i+1}"
                        validated_clips.append(clip)
                        
                    elif isinstance(clip, dict):
                        # Convert dict to ClipResult with enhanced error handling
                        try:
                            # Ensure required fields exist with defaults
                            clip_data = {
                                'filename': clip.get('filename', f'clip_{i+1}.mp4'),
                                'title': clip.get('title', f'Clip {i+1}'),
                                'duration': float(clip.get('duration', 0)),
                                'start_time': float(clip.get('start_time', 0)),
                                'end_time': float(clip.get('end_time', 0)),
                                'score': float(clip.get('score', 0)),
                                'hook_title': clip.get('hook_title'),
                                'engagement_score': float(clip.get('engagement_score', 0)) if clip.get('engagement_score') else None,
                                'viral_potential': clip.get('viral_potential'),
                                'thumbnail_url': clip.get('thumbnail_url')
                            }
                            
                            clip_result = ClipResult(**clip_data)
                            validated_clips.append(clip_result)
                            
                        except Exception as conversion_error:
                            error_msg = f"Failed to convert clip {i}: {str(conversion_error)}"
                            conversion_errors.append(error_msg)
                            logger.warning(f"⚠️ {error_msg}")
                            
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
                    else:
                        logger.warning(f"⚠️ Invalid clip type {type(clip)} at index {i}, creating fallback")
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
                    error_msg = f"Failed to process clip {i}: {str(clip_error)}"
                    conversion_errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    continue
            
            # Update job with validated clips
            job.clips = validated_clips
            job.updated_at = datetime.now().isoformat()
            
            # Store updated job
            self.jobs[job_id] = job
            
            # Enhanced logging
            if conversion_errors:
                await self._log_job_event(job_id, f"⚠️ Clips update with {len(conversion_errors)} conversion errors")
                for error in conversion_errors[:3]:  # Log first 3 errors
                    await self._log_job_event(job_id, f"   - {error}")
            
            await self._log_job_event(job_id, f"📹 Updated clips: {len(validated_clips)} clips successfully processed")
            logger.info(f"📹 ENHANCED clips update {job_id}: {len(validated_clips)} clips, {len(conversion_errors)} errors")
            
            # Update performance tracking
            if job_id in self.job_performance:
                perf = self.job_performance[job_id]
                perf['clips_generated'] = len(validated_clips)
                perf['clips_errors'] = len(conversion_errors)
                if validated_clips:
                    total_duration = sum(clip.duration for clip in validated_clips)
                    avg_score = sum(clip.score for clip in validated_clips) / len(validated_clips)
                    perf['total_clip_duration'] = total_duration
                    perf['average_clip_score'] = avg_score
            
            return True
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR updating job clips: {str(e)}")
            await self._log_job_event(job_id, f"❌ CRITICAL ERROR updating clips: {str(e)}")
            return False
    
    async def serialize_job_for_api(self, job_id: str) -> Optional[Dict[str, Any]]:
        """ENHANCED: Robust job serialization for API responses"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.warning(f"⚠️ Job {job_id} not found for API serialization")
                return None
            
            # Enhanced clips serialization
            serialized_clips = []
            serialization_errors = []
            
            for i, clip in enumerate(job.clips):
                try:
                    if hasattr(clip, 'to_dict') and callable(clip.to_dict):
                        clip_dict = clip.to_dict()
                    elif hasattr(clip, '__dict__'):
                        # Manual serialization with error handling
                        clip_dict = {
                            'filename': str(getattr(clip, 'filename', f'clip_{i+1}.mp4')),
                            'title': str(getattr(clip, 'title', f'Clip {i+1}')),
                            'duration': float(getattr(clip, 'duration', 0)),
                            'start_time': float(getattr(clip, 'start_time', 0)),
                            'end_time': float(getattr(clip, 'end_time', 0)),
                            'score': float(getattr(clip, 'score', 0)),
                            'hook_title': str(getattr(clip, 'hook_title', '')) if getattr(clip, 'hook_title', None) else None,
                            'viral_potential': str(getattr(clip, 'viral_potential', '')) if getattr(clip, 'viral_potential', None) else None,
                            'engagement_score': float(getattr(clip, 'engagement_score', 0)) if getattr(clip, 'engagement_score', None) else None,
                            'thumbnail_url': str(getattr(clip, 'thumbnail_url', '')) if getattr(clip, 'thumbnail_url', None) else None,
                            'stream_url': str(getattr(clip, 'stream_url', '')) if getattr(clip, 'stream_url', None) else None
                        }
                    elif isinstance(clip, dict):
                        # Already a dict, just clean it
                        clip_dict = {
                            'filename': str(clip.get('filename', f'clip_{i+1}.mp4')),
                            'title': str(clip.get('title', f'Clip {i+1}')),
                            'duration': float(clip.get('duration', 0)),
                            'start_time': float(clip.get('start_time', 0)),
                            'end_time': float(clip.get('end_time', 0)),
                            'score': float(clip.get('score', 0)),
                            'hook_title': clip.get('hook_title'),
                            'viral_potential': clip.get('viral_potential'),
                            'engagement_score': clip.get('engagement_score'),
                            'thumbnail_url': clip.get('thumbnail_url'),
                            'stream_url': clip.get('stream_url')
                        }
                    else:
                        # Unknown type, create fallback
                        clip_dict = {
                            'filename': f'clip_{i+1}.mp4',
                            'title': f'Clip {i+1}',
                            'duration': 30.0,
                            'start_time': 0.0,
                            'end_time': 30.0,
                            'score': 0.5,
                            'hook_title': None,
                            'viral_potential': None,
                            'engagement_score': None,
                            'thumbnail_url': None,
                            'stream_url': None
                        }
                    
                    serialized_clips.append(clip_dict)
                    
                except Exception as clip_error:
                    error_msg = f"Clip {i} serialization error: {str(clip_error)}"
                    serialization_errors.append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")
                    
                    # Add fallback clip
                    serialized_clips.append({
                        'filename': f'clip_{i+1}.mp4',
                        'title': f'Clip {i+1} (Error)',
                        'duration': 0.0,
                        'start_time': 0.0,
                        'end_time': 0.0,
                        'score': 0.0,
                        'error': f'Serialization failed: {str(clip_error)[:100]}'
                    })
            
            # Serialize steps information
            steps_data = []
            for step in job.steps:
                steps_data.append(step.to_dict())
            
            # Build enhanced API response
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
                "serialization_errors": len(serialization_errors),
                "user_id": getattr(job, 'user_id', None),  # Add user_id for clip fetching
                "plan": getattr(job, 'plan', 'free'),  # Add plan info
                "steps": steps_data  # Add step-based progress tracking
            }
            
            # Add performance data if available
            if job_id in self.job_performance:
                perf = self.job_performance[job_id]
                api_response["performance"] = {
                    "elapsed_time": perf.get('elapsed_time', 0),
                    "steps_completed": perf.get('steps_completed', 0),
                    "total_steps": perf.get('total_steps', 5),
                    "average_clip_score": perf.get('average_clip_score', 0)
                }
                
                # Add strategy results if available
                if 'strategy_results' in perf:
                    api_response["strategy_results"] = perf['strategy_results']
            
            if serialization_errors:
                logger.warning(f"⚠️ Job {job_id} API serialization had {len(serialization_errors)} errors")
            
            logger.debug(f"📄 ENHANCED API serialization complete for {job_id}: {len(serialized_clips)} clips")
            return api_response
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR serializing job {job_id} for API: {str(e)}")
            
            # Return minimal error response
            return {
                "job_id": job_id,
                "status": "error",
                "progress": 0.0,
                "message": f"Serialization error: {str(e)[:200]}",
                "clips": [],
                "error": True,
                "critical_error": str(e)
            }
    
    async def get_job_stats(self) -> Dict[str, Any]:
        """ENHANCED: Get comprehensive job statistics with performance metrics"""
        try:
            all_jobs = list(self.jobs.values())
            
            # Basic stats
            stats = {
                'total_jobs': len(all_jobs),
                'queued': len([j for j in all_jobs if j.status == 'queued']),
                'processing': len([j for j in all_jobs if j.status == 'processing']),
                'completed': len([j for j in all_jobs if j.status == 'completed']),
                'error': len([j for j in all_jobs if j.status == 'error']),
                'paused': len([j for j in all_jobs if j.status == 'paused']),
                'cancelled': len([j for j in all_jobs if j.status == 'cancelled']),
                'total_clips_generated': sum(len(j.clips) for j in all_jobs),
                'average_processing_time': 0,
                'success_rate': 0
            }
            
            # Enhanced performance calculations
            completed_jobs = [j for j in all_jobs if j.status == 'completed']
            if completed_jobs:
                processing_times = []
                total_clips = 0
                total_score = 0
                clip_count = 0
                
                for job in completed_jobs:
                    # Calculate processing time
                    if job.created_at and job.updated_at:
                        try:
                            created = datetime.fromisoformat(job.created_at)
                            updated = datetime.fromisoformat(job.updated_at)
                            processing_time = (updated - created).total_seconds()
                            processing_times.append(processing_time)
                        except:
                            continue
                    
                    # Calculate clip metrics
                    total_clips += len(job.clips)
                    for clip in job.clips:
                        try:
                            if hasattr(clip, 'score'):
                                total_score += float(clip.score)
                                clip_count += 1
                        except:
                            continue
                
                if processing_times:
                    stats['average_processing_time'] = sum(processing_times) / len(processing_times)
                    stats['fastest_processing_time'] = min(processing_times)
                    stats['slowest_processing_time'] = max(processing_times)
                
                if clip_count > 0:
                    stats['average_clip_score'] = total_score / clip_count
                
                # Success rate calculation
                total_finished = len(completed_jobs) + len([j for j in all_jobs if j.status == 'error'])
                if total_finished > 0:
                    stats['success_rate'] = len(completed_jobs) / total_finished
            
            # Performance tracking stats
            if self.job_performance:
                performance_data = list(self.job_performance.values())
                stats['performance_tracking'] = {
                    'jobs_tracked': len(performance_data),
                    'total_errors': sum(len(p.get('errors', [])) for p in performance_data),
                    'total_warnings': sum(len(p.get('warnings', [])) for p in performance_data)
                }
            
            # Memory usage
            stats['memory_usage'] = {
                'jobs_in_memory': len(self.jobs),
                'logs_in_memory': len(self.job_logs),
                'performance_data_in_memory': len(self.job_performance)
            }
            
            logger.debug(f"📊 ENHANCED job stats calculated: {stats['total_jobs']} jobs, {stats['success_rate']:.2f} success rate")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting enhanced job stats: {str(e)}")
            return {
                'total_jobs': len(self.jobs),
                'error': f'Stats calculation failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a processing job"""
        try:
            logger.info(f"🛑 Attempting to cancel job: {job_id}")
            
            if job_id not in self.jobs:
                logger.warning(f"⚠️ Job {job_id} not found for cancellation")
                return False
            
            job = self.jobs[job_id]
            
            # Check if job can be cancelled
            if job.status in ['completed', 'error', 'cancelled']:
                logger.warning(f"⚠️ Job {job_id} cannot be cancelled (status: {job.status})")
                return False
            
            # Prevent cancellation after 80% progress (clips are being finalized)
            if job.progress >= 80:
                logger.warning(f"⚠️ Job {job_id} cannot be cancelled (progress: {job.progress}% - clips being finalized)")
                return False
            
            # Update job status to cancelled
            job.status = 'cancelled'
            job.message = 'Job cancelled by user'
            job.updated_at = datetime.now()
            
            # Log the cancellation
            await self._log_job_event(job_id, "Job cancelled by user request")
            logger.info(f"✅ Job {job_id} cancelled successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cancelling job {job_id}: {str(e)}")
            return False

    async def set_job_error(self, job_id: str, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """ENHANCED: Set job to error status with detailed error tracking"""
        try:
            # Update job status
            await self.update_job_status(job_id, 'error', 0.0, f"Error: {error_message}")
            
            # Enhanced error logging
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
                
                # Keep only last 10 errors
                if len(perf['errors']) > 10:
                    perf['errors'] = perf['errors'][-10:]
            
            logger.error(f"❌ ENHANCED job error set for {job_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR setting job error status: {str(e)}")
    
    async def store_strategy_results(self, job_id: str, strategy_results: List[Dict[str, Any]]):
        """Store YouTube download strategy results for debugging and user feedback"""
        try:
            if job_id not in self.job_performance:
                logger.warning(f"⚠️ No performance tracking found for job {job_id}")
                return False
            
            # Store strategy results in performance data
            self.job_performance[job_id]['strategy_results'] = {
                'timestamp': datetime.now().isoformat(),
                'strategies': strategy_results,
                'summary': {
                    'total_strategies': len(strategy_results),
                    'successful': len([r for r in strategy_results if r['status'] == 'SUCCESS']),
                    'failed': len([r for r in strategy_results if r['status'] == 'FAILED']),
                    'timeout': len([r for r in strategy_results if r['status'] == 'TIMEOUT'])
                }
            }
            
            # Log strategy summary
            summary = self.job_performance[job_id]['strategy_results']['summary']
            await self._log_job_event(
                job_id, 
                f"📊 Strategy Results: ✅{summary['successful']} ❌{summary['failed']} ⏱️{summary['timeout']} (Total: {summary['total_strategies']})"
            )
            
            # Log individual strategies
            for i, result in enumerate(strategy_results, 1):
                status_emoji = {
                    'SUCCESS': '✅',
                    'FAILED': '❌', 
                    'TIMEOUT': '⏱️'
                }.get(result['status'], '❓')
                
                await self._log_job_event(
                    job_id,
                    f"  {i}. {status_emoji} {result['strategy']} ({result['time_taken']}) - {result.get('message', 'No message')}"
                )
            
            logger.info(f"📊 Stored strategy results for job {job_id}: {summary['successful']}/{summary['total_strategies']} successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing strategy results for job {job_id}: {str(e)}")
            return False
    
    async def set_strategy_results(self, job_id: str, strategy_results: List[Dict[str, Any]]):
        """Alias for store_strategy_results to maintain compatibility"""
        return await self.store_strategy_results(job_id, strategy_results)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a processing job"""
        try:
            logger.info(f"🛑 Attempting to cancel job: {job_id}")
            
            if job_id not in self.jobs:
                logger.warning(f"⚠️ Cannot cancel job {job_id}: job not found")
                return False
            
            job = self.jobs[job_id]
            
            # Check if job can be cancelled
            if job.status in ['completed', 'error', 'cancelled']:
                logger.warning(f"⚠️ Cannot cancel job {job_id}: already {job.status}")
                return False
            
            # Update job status to cancelled
            await self.update_job_status(job_id, 'cancelled', job.progress, 'Job cancelled by user')
            
            # Log the cancellation
            await self._log_job_event(job_id, "🛑 Job cancelled by user")
            logger.info(f"✅ Job {job_id} cancelled successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cancelling job {job_id}: {str(e)}")
            return False
    
    async def handle_job_error(self, job_id: str, error: Exception, context: Optional[Dict[str, Any]] = None):
        """ENHANCED: Comprehensive job error handling with context"""
        try:
            error_message = str(error)
            error_type = type(error).__name__
            
            # Enhanced error details
            error_details = {
                'error_type': error_type,
                'context': context or {},
                'timestamp': datetime.now().isoformat()
            }
            
            # Get traceback if available
            import traceback
            error_details['traceback'] = traceback.format_exc()
            
            await self.set_job_error(job_id, error_message, error_details)
            
            logger.error(f"❌ ENHANCED error handled for job {job_id}: {error_type} - {error_message}")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in enhanced error handling for {job_id}: {str(e)}")
    
    async def cleanup_old_jobs(self, max_age_hours: int = 24, keep_completed: bool = True):
        """ENHANCED: Intelligent cleanup with preservation options"""
        try:
            all_jobs = list(self.jobs.values())
            now = datetime.now()
            
            jobs_to_delete = []
            for job in all_jobs:
                try:
                    if not job.updated_at:
                        continue
                    
                    updated_time = datetime.fromisoformat(job.updated_at)
                    age_hours = (now - updated_time).total_seconds() / 3600
                    
                    # Cleanup logic
                    should_delete = False
                    
                    if job.status == 'error' and age_hours > (max_age_hours / 2):  # Delete errors faster
                        should_delete = True
                    elif job.status in ['cancelled', 'paused'] and age_hours > max_age_hours:
                        should_delete = True
                    elif job.status == 'completed':
                        if not keep_completed and age_hours > max_age_hours:
                            should_delete = True
                        elif age_hours > (max_age_hours * 3):  # Keep completed longer
                            should_delete = True
                    elif job.status in ['queued', 'processing'] and age_hours > (max_age_hours * 2):  # Stuck jobs
                        should_delete = True
                    
                    if should_delete:
                        jobs_to_delete.append(job.job_id)
                        
                except Exception as job_error:
                    logger.warning(f"⚠️ Error checking job {job.job_id} for cleanup: {str(job_error)}")
            
            # Delete old jobs
            cleanup_stats = {
                'deleted_jobs': 0,
                'cleaned_files': 0,
                'freed_space_mb': 0,
                'errors': []
            }
            
            for job_id in jobs_to_delete:
                try:
                    # Cleanup files first
                    freed_space = await self._cleanup_job_files(job_id)
                    cleanup_stats['freed_space_mb'] += freed_space
                    
                    # Delete job data
                    if job_id in self.jobs:
                        del self.jobs[job_id]
                    if job_id in self.job_logs:
                        del self.job_logs[job_id]
                    if job_id in self.job_performance:
                        del self.job_performance[job_id]
                    
                    cleanup_stats['deleted_jobs'] += 1
                    logger.debug(f"🗑️ Cleaned up job: {job_id}")
                    
                except Exception as cleanup_error:
                    error_msg = f"Failed to cleanup job {job_id}: {str(cleanup_error)}"
                    cleanup_stats['errors'].append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")
            
            if cleanup_stats['deleted_jobs'] > 0:
                logger.info(f"🗑️ ENHANCED cleanup complete: {cleanup_stats['deleted_jobs']} jobs, {cleanup_stats['freed_space_mb']:.1f}MB freed")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"❌ Error in enhanced cleanup: {str(e)}")
            return {'error': str(e)}
    
    async def _cleanup_job_files(self, job_id: str) -> float:
        """ENHANCED: Cleanup job files and return freed space in MB"""
        try:
            import shutil
            freed_space = 0
            
            # Cleanup output directory
            output_dir = f"output/{job_id}"
            if os.path.exists(output_dir):
                dir_size = self._get_directory_size(output_dir)
                shutil.rmtree(output_dir)
                freed_space += dir_size
            
            # Cleanup thumbnails
            thumbnails_dir = f"thumbnails/{job_id}"
            if os.path.exists(thumbnails_dir):
                dir_size = self._get_directory_size(thumbnails_dir)
                shutil.rmtree(thumbnails_dir)
                freed_space += dir_size
            
            # Cleanup temp files
            if os.path.exists("temp"):
                temp_files = [f for f in os.listdir("temp") if job_id in f]
                for temp_file in temp_files:
                    temp_path = os.path.join("temp", temp_file)
                    if os.path.exists(temp_path):
                        file_size = os.path.getsize(temp_path)
                        os.remove(temp_path)
                        freed_space += file_size
            
            # Cleanup archive
            archive_path = f"output/{job_id}_clips.zip"
            if os.path.exists(archive_path):
                file_size = os.path.getsize(archive_path)
                os.remove(archive_path)
                freed_space += file_size
            
            freed_mb = freed_space / (1024 * 1024)
            logger.debug(f"🗑️ Files cleaned for {job_id}: {freed_mb:.1f}MB")
            return freed_mb
            
        except Exception as e:
            logger.error(f"❌ Error cleaning job files for {job_id}: {str(e)}")
            return 0.0
    
    def _get_directory_size(self, directory: str) -> int:
        """Calculate directory size in bytes"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception as e:
            logger.warning(f"⚠️ Error calculating directory size for {directory}: {str(e)}")
        return total_size
    
    async def initialize_job_steps(self, job_id: str) -> bool:
        """Initialize processing steps for a job"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.error(f"❌ Job {job_id} not found for step initialization")
                return False
            
            # Define the standard processing steps
            steps = [
                ProcessingStep(
                    name="initialization",
                    description="Setting up job and validating inputs",
                    status="completed",
                    progress=100.0,
                    started_at=datetime.now(),
                    completed_at=datetime.now()
                ),
                ProcessingStep(
                    name="video_download",
                    description="Downloading video from YouTube",
                    status="pending"
                ),
                ProcessingStep(
                    name="ai_analysis",
                    description="Analyzing video content and generating transcription",
                    status="pending"
                ),
                ProcessingStep(
                    name="video_processing",
                    description="Creating clips with captions and effects",
                    status="pending"
                ),
                ProcessingStep(
                    name="thumbnail_generation",
                    description="Generating thumbnails for clips",
                    status="pending"
                ),
                ProcessingStep(
                    name="storage_upload",
                    description="Uploading clips to cloud storage",
                    status="pending"
                )
            ]
            
            job.steps = steps
            self.jobs[job_id] = job
            
            logger.info(f"✅ Initialized {len(steps)} processing steps for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing steps for job {job_id}: {str(e)}")
            return False
    
    async def update_step_status(self, job_id: str, step_name: str, status: str, progress: float = 0.0, message: str = None) -> bool:
        """Update status of a specific processing step"""
        try:
            job = await self.get_job(job_id)
            if not job:
                logger.error(f"❌ Job {job_id} not found for step update")
                return False
            
            # Find the step to update
            step_found = False
            for step in job.steps:
                if step.name == step_name:
                    old_status = step.status
                    step.status = status
                    step.progress = max(0.0, min(100.0, float(progress)))
                    
                    if message:
                        step.message = message
                    
                    # Update timestamps
                    if status == "processing" and old_status == "pending":
                        step.started_at = datetime.now()
                    elif status in ["completed", "error", "skipped"]:
                        step.completed_at = datetime.now()
                        if status == "completed":
                            step.progress = 100.0
                    
                    if status == "error" and message:
                        step.error_message = message
                    
                    step_found = True
                    break
            
            if not step_found:
                logger.warning(f"⚠️ Step '{step_name}' not found in job {job_id}")
                return False
            
            # Update overall job progress based on step completion
            completed_steps = len([s for s in job.steps if s.status == "completed"])
            total_steps = len(job.steps)
            overall_progress = (completed_steps / total_steps) * 100.0
            
            # Update job status
            if status == "processing":
                job.current_step = step_name.replace("_", " ").title()
            
            job.progress = overall_progress
            job.updated_at = datetime.now().isoformat()
            
            # Store updated job
            self.jobs[job_id] = job
            
            await self._log_job_event(job_id, f"📋 Step '{step_name}': {old_status} → {status} ({progress:.1f}%)")
            logger.info(f"📋 Updated step '{step_name}' for job {job_id}: {status} ({progress:.1f}%)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating step {step_name} for job {job_id}: {str(e)}")
            return False
    
    async def get_job_steps(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all processing steps for a job"""
        try:
            job = await self.get_job(job_id)
            if not job:
                return []
            
            steps_data = []
            for step in job.steps:
                steps_data.append(step.to_dict())
            
            return steps_data
            
        except Exception as e:
            logger.error(f"❌ Error getting steps for job {job_id}: {str(e)}")
            return []
    
    async def _log_job_event(self, job_id: str, message: str):
        """ENHANCED: Log job events with structured format"""
        try:
            if job_id not in self.job_logs:
                self.job_logs[job_id] = []
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds
            log_entry = f"[{timestamp}] {message}"
            
            self.job_logs[job_id].append(log_entry)
            
            # Keep only last 200 log entries per job (increased from 100)
            if len(self.job_logs[job_id]) > 200:
                self.job_logs[job_id] = self.job_logs[job_id][-200:]
            
            # Also log warnings to performance tracking
            if job_id in self.job_performance and ('⚠️' in message or 'WARNING' in message.upper()):
                perf = self.job_performance[job_id]
                if 'warnings' not in perf:
                    perf['warnings'] = []
                perf['warnings'].append({
                    'message': message,
                    'timestamp': datetime.now().timestamp()
                })
                
                # Keep only last 20 warnings
                if len(perf['warnings']) > 20:
                    perf['warnings'] = perf['warnings'][-20:]
                
        except Exception as e:
            logger.error(f"❌ Failed to log event for job {job_id}: {str(e)}")
    
    async def get_job_logs(self, job_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """ENHANCED: Get structured job logs with filtering"""
        try:
            if job_id not in self.job_logs:
                logger.warning(f"⚠️ No logs found for job {job_id}")
                return []
            
            raw_logs = self.job_logs[job_id][-limit:]  # Get last N entries
            structured_logs = []
            
            for log_entry in raw_logs:
                try:
                    # Parse log entry
                    if ']' in log_entry:
                        timestamp_str = log_entry.split(']')[0].replace('[', '')
                        message = log_entry.split('] ', 1)[1] if '] ' in log_entry else log_entry
                    else:
                        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        message = log_entry
                    
                    # Determine log level
                    level = 'INFO'
                    if '❌' in message or 'ERROR' in message.upper():
                        level = 'ERROR'
                    elif '⚠️' in message or 'WARNING' in message.upper():
                        level = 'WARNING'
                    elif '✅' in message or 'SUCCESS' in message.upper():
                        level = 'SUCCESS'
                    elif '📊' in message or 'UPDATE' in message.upper():
                        level = 'UPDATE'
                    
                    structured_logs.append({
                        'timestamp': timestamp_str,
                        'level': level,
                        'message': message,
                        'raw_entry': log_entry
                    })
                    
                except Exception as parse_error:
                    # Fallback for unparseable logs
                    structured_logs.append({
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'level': 'INFO',
                        'message': str(log_entry),
                        'parse_error': str(parse_error)
                    })
            
            logger.debug(f"📄 Retrieved {len(structured_logs)} logs for job {job_id}")
            return structured_logs
            
        except Exception as e:
            logger.error(f"❌ Error getting enhanced job logs for {job_id}: {str(e)}")
            return [{
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'level': 'ERROR',
                'message': f'Failed to retrieve logs: {str(e)}'
            }]
    
    def __len__(self) -> int:
        """Return number of jobs"""
        return len(self.jobs)
    
    def __contains__(self, job_id: str) -> bool:
        """Check if job exists"""
        return job_id in self.jobs
    
    def __repr__(self) -> str:
        """Enhanced string representation"""
        stats = {
            'total': len(self.jobs),
            'processing': len([j for j in self.jobs.values() if j.status == 'processing']),
            'completed': len([j for j in self.jobs.values() if j.status == 'completed']),
            'errors': len([j for j in self.jobs.values() if j.status == 'error'])
        }
        return f"EnhancedJobManager(total={stats['total']}, processing={stats['processing']}, completed={stats['completed']}, errors={stats['errors']})"