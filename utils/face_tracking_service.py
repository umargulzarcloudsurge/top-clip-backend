"""
Face Detection and Tracking Service for Video Processing
Uses MediaPipe for fast and accurate face detection and tracking
"""
import cv2
import numpy as np
import logging
import asyncio
import os
import tempfile
from typing import List, Dict, Tuple, Optional, Any
import mediapipe as mp
from dataclasses import dataclass
from collections import deque
import math

logger = logging.getLogger(__name__)

@dataclass
class FaceDetection:
    """Face detection result with bounding box and confidence"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    center_x: int
    center_y: int
    
    @classmethod
    def from_mediapipe_detection(cls, detection, frame_width: int, frame_height: int):
        """Create FaceDetection from MediaPipe detection"""
        bbox = detection.location_data.relative_bounding_box
        
        x = int(bbox.xmin * frame_width)
        y = int(bbox.ymin * frame_height)
        width = int(bbox.width * frame_width)
        height = int(bbox.height * frame_height)
        
        center_x = x + width // 2
        center_y = y + height // 2
        confidence = detection.score[0] if detection.score else 0.0
        
        return cls(x, y, width, height, confidence, center_x, center_y)

@dataclass
class FaceTrackingData:
    """Face tracking data for a video segment"""
    faces_per_frame: List[List[FaceDetection]]
    average_face_center: Tuple[int, int]
    confidence_score: float
    frame_count: int
    has_faces: bool

class FaceTrackingService:
    """Service for detecting and tracking faces in video clips for optimal framing"""
    
    def __init__(self):
        """Initialize MediaPipe face detection optimized for CPU-only processing"""
        try:
            # Set CPU-only processing for MediaPipe (no GPU acceleration)
            import os
            os.environ['MEDIAPIPE_DISABLE_GPU'] = '1'
            
            # Initialize MediaPipe Face Detection
            self.mp_face_detection = mp.solutions.face_detection
            self.mp_drawing = mp.solutions.drawing_utils
            
            # Configure face detection optimized for CPU processing on Ubuntu
            self.face_detection = self.mp_face_detection.FaceDetection(
                model_selection=0,  # 0 for short range model (faster on CPU, good for most video content)
                min_detection_confidence=0.4  # Slightly higher threshold for better CPU performance
            )
            
            # Enhanced face tracking parameters for video processing
            self.smoothing_window = 15  # Increased for smoother face position tracking
            self.min_confidence = 0.3  # Lower threshold for better detection
            self.max_faces_to_track = 5  # Track up to 5 faces simultaneously
            
            # Cache for face positions (for smoothing)
            self.face_position_cache = deque(maxlen=self.smoothing_window)
            
            logger.info("✅ Face tracking service initialized with MediaPipe - Enhanced for video clips")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize face tracking service: {str(e)}")
            self.face_detection = None
            raise
    
    async def analyze_video_faces(self, video_path: str, start_time: float = 0.0, end_time: float = None) -> FaceTrackingData:
        """
        Analyze faces in a video segment and return tracking data
        
        Args:
            video_path: Path to the video file
            start_time: Start time in seconds
            end_time: End time in seconds (None for full video)
            
        Returns:
            FaceTrackingData with face positions and statistics
        """
        try:
            logger.info(f"🎯 Analyzing faces in video: {video_path} ({start_time}s - {end_time or 'end'}s)")
            
            # Run face analysis in executor to avoid blocking
            return await asyncio.get_event_loop().run_in_executor(
                None, self._analyze_video_faces_sync, video_path, start_time, end_time
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing video faces: {str(e)}")
            # Return empty tracking data on error
            return FaceTrackingData(
                faces_per_frame=[],
                average_face_center=(0, 0),
                confidence_score=0.0,
                frame_count=0,
                has_faces=False
            )
    
    def _analyze_video_faces_sync(self, video_path: str, start_time: float, end_time: float) -> FaceTrackingData:
        """Synchronous face analysis implementation"""
        faces_per_frame = []
        all_face_centers = []
        total_confidence = 0.0
        confident_detections = 0
        
        # Validate inputs
        if not video_path or not os.path.exists(video_path):
            logger.error(f"❌ Video file does not exist: {video_path}")
            return FaceTrackingData([], (0, 0), 0.0, 0, False)
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"❌ Failed to open video: {video_path}")
            return FaceTrackingData([], (0, 0), 0.0, 0, False)
        
        try:
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            logger.info(f"📹 Video info: {frame_width}x{frame_height}, {fps}fps, {total_frames} frames")
            
            # Calculate frame range
            start_frame = int(start_time * fps)
            end_frame = int(end_time * fps) if end_time else total_frames
            end_frame = min(end_frame, total_frames)
            
            # Set start position
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Analyze frames (optimized for CPU performance)
            frame_skip = max(1, int(fps / 3))  # Analyze ~3 frames per second for better CPU performance
            current_frame = start_frame
            
            while current_frame < end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Skip frames for performance
                if (current_frame - start_frame) % frame_skip == 0:
                    # Detect faces in this frame
                    frame_faces = self._detect_faces_in_frame(frame)
                    faces_per_frame.append(frame_faces)
                    
                    # Collect face centers for averaging
                    for face in frame_faces:
                        if face.confidence >= self.min_confidence:
                            all_face_centers.append((face.center_x, face.center_y))
                            total_confidence += face.confidence
                            confident_detections += 1
                
                current_frame += 1
            
            # Calculate statistics
            frame_count = len(faces_per_frame)
            has_faces = confident_detections > 0
            avg_confidence = total_confidence / confident_detections if confident_detections > 0 else 0.0
            
            # Calculate average face center
            if all_face_centers:
                avg_x = sum(center[0] for center in all_face_centers) / len(all_face_centers)
                avg_y = sum(center[1] for center in all_face_centers) / len(all_face_centers)
                average_face_center = (int(avg_x), int(avg_y))
            else:
                # Fallback to upper-middle of frame
                average_face_center = (frame_width // 2, frame_height // 3)
            
            logger.info(f"🎯 Face analysis complete: {confident_detections} confident detections in {frame_count} frames")
            logger.info(f"📊 Average face center: {average_face_center}, confidence: {avg_confidence:.2f}")
            
            return FaceTrackingData(
                faces_per_frame=faces_per_frame,
                average_face_center=average_face_center,
                confidence_score=avg_confidence,
                frame_count=frame_count,
                has_faces=has_faces
            )
            
        finally:
            cap.release()
    
    def _detect_faces_in_frame(self, frame: np.ndarray) -> List[FaceDetection]:
        """Detect faces in a single frame with CPU optimization"""
        if self.face_detection is None:
            return []
        
        try:
            # Validate frame data
            if frame is None or frame.size == 0:
                logger.warning("⚠️ Received empty or None frame, skipping face detection")
                return []
            
            # Check frame dimensions
            if len(frame.shape) != 3 or frame.shape[2] != 3:
                logger.warning(f"⚠️ Invalid frame shape {frame.shape}, expected (H, W, 3)")
                return []
            
            original_height, original_width = frame.shape[:2]
            if original_width <= 0 or original_height <= 0:
                logger.warning(f"⚠️ Invalid frame dimensions: {original_width}x{original_height}")
                return []
            
            # CPU optimization: Downsample large frames for faster processing
            scale_factor = 1.0
            if original_width > 1280:  # Downsample if frame is larger than 1280px
                scale_factor = 1280.0 / original_width
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            frame_height, frame_width = frame.shape[:2]
            
            # Ensure frame is contiguous in memory
            if not frame.flags['C_CONTIGUOUS']:
                frame = np.ascontiguousarray(frame)
            
            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Validate RGB frame
            if rgb_frame is None or rgb_frame.size == 0:
                logger.warning("⚠️ Failed to convert frame to RGB, skipping face detection")
                return []
            
            # Ensure RGB frame is writable and contiguous
            rgb_frame.flags.writeable = False  # MediaPipe expects non-writable images
            
            # Process frame with MediaPipe
            results = self.face_detection.process(rgb_frame)
            
            # Reset writeable flag after processing
            rgb_frame.flags.writeable = True
            
            faces = []
            if results and results.detections:
                for detection in results.detections:
                    try:
                        face = FaceDetection.from_mediapipe_detection(detection, frame_width, frame_height)
                        
                        # Scale coordinates back to original frame size if we downsampled
                        if scale_factor < 1.0:
                            face.x = int(face.x / scale_factor)
                            face.y = int(face.y / scale_factor)
                            face.width = int(face.width / scale_factor)
                            face.height = int(face.height / scale_factor)
                            face.center_x = int(face.center_x / scale_factor)
                            face.center_y = int(face.center_y / scale_factor)
                        
                        if face.confidence >= self.min_confidence:
                            faces.append(face)
                    except Exception as det_e:
                        logger.warning(f"⚠️ Error processing individual face detection: {str(det_e)}")
                        continue
                
                # Sort by confidence and keep top faces
                faces.sort(key=lambda f: f.confidence, reverse=True)
                faces = faces[:self.max_faces_to_track]
            
            return faces
            
        except Exception as e:
            logger.error(f"❌ Error detecting faces in frame: {str(e)}")
            return []
    
    def get_optimal_crop_region(self, tracking_data: FaceTrackingData, 
                              original_width: int, original_height: int,
                              target_width: int, target_height: int) -> Tuple[int, int, int, int]:
        """
        Calculate optimal crop region to center faces in vertical format
        
        Returns:
            (x, y, width, height) crop region
        """
        if not tracking_data.has_faces:
            # Fallback to upper-third crop if no faces detected
            logger.info("⚠️ No faces detected, using upper-third crop")
            return self._get_fallback_crop_region(original_width, original_height, target_width, target_height)
        
        face_center_x, face_center_y = tracking_data.average_face_center
        
        # Calculate target aspect ratio
        target_aspect = target_width / target_height
        original_aspect = original_width / original_height
        
        if original_aspect > target_aspect:
            # Original is wider - crop horizontally, center on face X
            crop_height = original_height
            crop_width = int(crop_height * target_aspect)
            
            # Center crop on face X position, but constrain to frame bounds
            crop_x = max(0, min(face_center_x - crop_width // 2, original_width - crop_width))
            crop_y = 0
            
        else:
            # Original is taller - crop vertically, center on face Y  
            crop_width = original_width
            crop_height = int(crop_width / target_aspect)
            
            # Center crop on face Y position, with slight upward bias
            bias_offset = int(crop_height * 0.1)  # 10% upward bias
            ideal_y = face_center_y - crop_height // 2 - bias_offset
            crop_y = max(0, min(ideal_y, original_height - crop_height))
            crop_x = 0
        
        logger.info(f"🎯 Face-centered crop region: ({crop_x}, {crop_y}, {crop_width}, {crop_height})")
        logger.info(f"📊 Face center: ({face_center_x}, {face_center_y}), Confidence: {tracking_data.confidence_score:.2f}")
        
        return crop_x, crop_y, crop_width, crop_height
    
    def _get_fallback_crop_region(self, original_width: int, original_height: int,
                                 target_width: int, target_height: int) -> Tuple[int, int, int, int]:
        """Get fallback crop region when no faces are detected"""
        target_aspect = target_width / target_height
        original_aspect = original_width / original_height
        
        if original_aspect > target_aspect:
            # Original is wider - crop horizontally, center
            crop_height = original_height
            crop_width = int(crop_height * target_aspect)
            crop_x = (original_width - crop_width) // 2
            crop_y = 0
        else:
            # Original is taller - crop vertically with upper bias
            crop_width = original_width
            crop_height = int(crop_width / target_aspect)
            crop_x = 0
            # Position crop in upper third of frame
            crop_y = int(original_height * 0.1)  # Start 10% from top
            crop_y = min(crop_y, original_height - crop_height)
        
        return crop_x, crop_y, crop_width, crop_height
    
    def apply_face_tracking_crop(self, video_stream, tracking_data: FaceTrackingData,
                               original_width: int, original_height: int,
                               target_width: int, target_height: int):
        """
        Apply face-centered crop to FFmpeg video stream
        
        Args:
            video_stream: FFmpeg video stream
            tracking_data: Face tracking data
            original_width/height: Original video dimensions
            target_width/height: Target dimensions
            
        Returns:
            Cropped and scaled video stream
        """
        try:
            # Get optimal crop region
            crop_x, crop_y, crop_width, crop_height = self.get_optimal_crop_region(
                tracking_data, original_width, original_height, target_width, target_height
            )
            
            # Apply crop
            video = video_stream.filter('crop', crop_width, crop_height, crop_x, crop_y)
            
            # Scale to target size
            video = video.filter('scale', target_width, target_height)
            
            logger.info(f"✅ Applied face-centered crop and scale: {crop_width}x{crop_height} → {target_width}x{target_height}")
            
            return video
            
        except Exception as e:
            logger.error(f"❌ Error applying face tracking crop: {str(e)}")
            # Fallback to simple center crop
            return video_stream.filter('scale', target_width, target_height, force_original_aspect_ratio='increase').filter('crop', target_width, target_height)
    
    def create_debug_visualization(self, video_path: str, tracking_data: FaceTrackingData, 
                                 output_path: str, start_time: float = 0.0, duration: float = 5.0):
        """
        Create a debug video showing detected faces (for testing purposes)
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return False
            
            # Get video properties
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
            
            # Set start position
            start_frame = int(start_time * fps)
            end_frame = start_frame + int(duration * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            frame_idx = 0
            current_frame = start_frame
            
            while current_frame < end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Draw faces if we have tracking data for this frame
                if frame_idx < len(tracking_data.faces_per_frame):
                    faces = tracking_data.faces_per_frame[frame_idx]
                    
                    for face in faces:
                        # Draw bounding box
                        cv2.rectangle(frame, (face.x, face.y), 
                                    (face.x + face.width, face.y + face.height), 
                                    (0, 255, 0), 2)
                        
                        # Draw confidence
                        cv2.putText(frame, f'{face.confidence:.2f}', 
                                  (face.x, face.y - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                                  0.5, (0, 255, 0), 1)
                        
                        # Draw center point
                        cv2.circle(frame, (face.center_x, face.center_y), 5, (0, 0, 255), -1)
                
                # Draw average face center
                if tracking_data.has_faces:
                    avg_center = tracking_data.average_face_center
                    cv2.circle(frame, avg_center, 10, (255, 0, 0), 3)
                    cv2.putText(frame, 'AVG', (avg_center[0] - 15, avg_center[1] - 15), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                out.write(frame)
                frame_idx += 1
                current_frame += 1
            
            cap.release()
            out.release()
            
            logger.info(f"✅ Debug visualization created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating debug visualization: {str(e)}")
            return False
    
    def __del__(self):
        """Cleanup MediaPipe resources"""
        try:
            if hasattr(self, 'face_detection') and self.face_detection:
                self.face_detection.close()
        except:
            pass
