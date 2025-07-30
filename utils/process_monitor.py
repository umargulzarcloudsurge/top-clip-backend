import asyncio
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import psutil
import os

logger = logging.getLogger(__name__)

class ProcessMonitor:
    """Monitor for detecting and handling hanging processes"""
    
    def __init__(self):
        self.active_processes: Dict[str, Dict[str, Any]] = {}
        self.process_timeouts = {
            'transcription': 300,  # 5 minutes
            'video_processing': 600,  # 10 minutes
            'youtube_download': 600,  # 10 minutes
            'ai_analysis': 180,  # 3 minutes
            'caption_processing': 180,  # 3 minutes
        }
        logger.info("🔍 Process Monitor initialized")
    
    def start_process_tracking(self, process_id: str, process_type: str, metadata: Optional[Dict] = None):
        """Start tracking a process"""
        self.active_processes[process_id] = {
            'type': process_type,
            'start_time': time.time(),
            'timeout': self.process_timeouts.get(process_type, 300),
            'metadata': metadata or {},
            'last_heartbeat': time.time(),
            'status': 'running'
        }
        logger.info(f"🔍 Started tracking {process_type} process: {process_id}")
    
    def update_process_heartbeat(self, process_id: str):
        """Update process heartbeat to indicate it's still alive"""
        if process_id in self.active_processes:
            self.active_processes[process_id]['last_heartbeat'] = time.time()
            logger.debug(f"💓 Heartbeat updated for process: {process_id}")
    
    def stop_process_tracking(self, process_id: str):
        """Stop tracking a process"""
        if process_id in self.active_processes:
            process_info = self.active_processes.pop(process_id)
            duration = time.time() - process_info['start_time']
            logger.info(f"✅ Stopped tracking {process_info['type']} process: {process_id} (duration: {duration:.1f}s)")
    
    def get_hanging_processes(self) -> Dict[str, Dict[str, Any]]:
        """Get list of processes that appear to be hanging"""
        hanging = {}
        current_time = time.time()
        
        for process_id, info in self.active_processes.items():
            elapsed = current_time - info['start_time']
            heartbeat_age = current_time - info['last_heartbeat']
            
            # Consider hanging if:
            # 1. Process has exceeded its timeout
            # 2. No heartbeat for more than 60 seconds
            if elapsed > info['timeout'] or heartbeat_age > 60:
                hanging[process_id] = {
                    **info,
                    'elapsed_time': elapsed,
                    'heartbeat_age': heartbeat_age,
                    'is_timeout': elapsed > info['timeout'],
                    'is_stale': heartbeat_age > 60
                }
        
        return hanging
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Process count
            process_count = len(psutil.pids())
            
            # Check for high resource usage
            alerts = []
            if cpu_percent > 90:
                alerts.append(f"High CPU usage: {cpu_percent:.1f}%")
            if memory_percent > 90:
                alerts.append(f"High memory usage: {memory_percent:.1f}%")
            if disk_percent > 90:
                alerts.append(f"High disk usage: {disk_percent:.1f}%")
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent,
                'process_count': process_count,
                'alerts': alerts,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking system resources: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def kill_hanging_processes(self) -> Dict[str, Any]:
        """Attempt to kill hanging processes"""
        hanging = self.get_hanging_processes()
        killed = []
        failed = []
        
        for process_id, info in hanging.items():
            try:
                # Try to find and kill the actual system process
                # This is a simplified approach - in production you'd want more sophisticated process tracking
                logger.warning(f"⚠️ Attempting to clean up hanging process: {process_id}")
                
                # For now, just remove from tracking
                self.stop_process_tracking(process_id)
                killed.append(process_id)
                
            except Exception as e:
                logger.error(f"❌ Failed to kill process {process_id}: {str(e)}")
                failed.append({'process_id': process_id, 'error': str(e)})
        
        return {
            'killed': killed,
            'failed': failed,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_process_stats(self) -> Dict[str, Any]:
        """Get statistics about tracked processes"""
        current_time = time.time()
        stats = {
            'active_processes': len(self.active_processes),
            'process_types': {},
            'longest_running': None,
            'average_duration': 0
        }
        
        if not self.active_processes:
            return stats
        
        durations = []
        longest_duration = 0
        longest_process = None
        
        for process_id, info in self.active_processes.items():
            process_type = info['type']
            duration = current_time - info['start_time']
            durations.append(duration)
            
            # Track by type
            if process_type not in stats['process_types']:
                stats['process_types'][process_type] = 0
            stats['process_types'][process_type] += 1
            
            # Track longest running
            if duration > longest_duration:
                longest_duration = duration
                longest_process = {
                    'process_id': process_id,
                    'type': process_type,
                    'duration': duration
                }
        
        stats['longest_running'] = longest_process
        stats['average_duration'] = sum(durations) / len(durations) if durations else 0
        
        return stats

# Global process monitor instance
process_monitor = ProcessMonitor()