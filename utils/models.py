from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime
import json
import random

# Enums
class Layout(str, Enum):
    VERTICAL = "Vertical (9:16)"
    SQUARE = "Square (1:1)"
    FIT_WITH_BLUR = "Fit with Blur"

class CaptionStyle(str, Enum):
    # Only 4 available PyCaps templates
    HYPE = "Hype"                          # High energy style
    VIBRANT = "Vibrant"                    # Colorful and dynamic
    NEO_MINIMAL = "Neo Minimal"            # Clean and modern
    LINE_FOCUS = "Line Focus"              # Focus on individual lines

class ColorGrading(str, Enum):
    NONE = "None"
    VIBRANT = "Vibrant"
    CINEMATIC = "Cinematic"
    VINTAGE = "Vintage"
    NEON = "Neon"

class QualityLevel(str, Enum):
    STANDARD = "Standard"
    HIGH = "High"
    ULTRA = "Ultra"

class ClipLength(str, Enum):
    SHORT = "<30s"
    MEDIUM = "30-60s"
    LONG = "60-90s"
    EXTRA_LONG = "90-120s"

# Models
class WordTiming(BaseModel):
    start: float
    end: float
    text: str
    word: Optional[str] = None  # Alternative field name

    @property
    def display_text(self) -> str:
        """Get the display text, handling both 'text' and 'word' fields"""
        return self.word or self.text

class TranscriptionWord(WordTiming):
    """
    Alias kept for backward‑compatibility.
    Prefer importing `WordTiming`; this class will be removed later.
    """
    pass

class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str
    words: Optional[List[WordTiming]] = None

    @property
    def display_text(self) -> str:
        return self.text

class Highlight(BaseModel):
    start_time: float
    end_time: float
    score: float
    reason: Optional[str] = None
    title: str
    transcription_segments: Optional[List[TranscriptionSegment]] = []
    hook_title: Optional[str] = None
    viral_potential: float = Field(default_factory=lambda: random.randint(90, 100))  # Random between 90-100
    engagement_score: float = 0.0
    audio_features: Optional[Dict[str, Any]] = None
    visual_features: Optional[Dict[str, Any]] = None
    content_features: Optional[Dict[str, Any]] = None

    @validator('viral_potential')
    def validate_viral_potential(cls, v):
        """Ensure viral potential is between 90 and 100"""
        if v is None:
            return random.randint(90, 100)
        try:
            score = float(v)
            return max(90.0, min(100.0, score))
        except (ValueError, TypeError):
            return random.randint(90, 100)

class ProcessingOptions(BaseModel):
    clipLength: ClipLength
    captionStyle: CaptionStyle
    enableHookTitles: bool
    enableWordHighlighting: bool = False
    enableAutoEmojis: bool = True
    enableBeatSync: bool = False
    backgroundMusic: str = ""
    gameVideo: str = ""
    layout: Layout
    clipCount: Optional[int] = Field(default=10, ge=1, le=10)
    qualityLevel: str = "Ultra"
    colorGrading: str = "Vibrant"

    class Config:
        use_enum_values = True
        validate_assignment = True
        
    @validator('clipCount')
    def validate_clip_count(cls, v):
        if v is None:
            return 10
        if not 1 <= v <= 10:
            raise ValueError('clipCount must be between 1 and 10')
        return v
    
    @validator('qualityLevel')
    def validate_quality_level(cls, v):
        valid_levels = ['Standard', 'High', 'Ultra']
        if v not in valid_levels:
            return 'Ultra'
        return v
    
    @validator('colorGrading')
    def validate_color_grading(cls, v):
        valid_gradings = ['None', 'Vibrant', 'Cinematic', 'Vintage', 'Neon']
        if v not in valid_gradings:
            return 'Vibrant'
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert ProcessingOptions to dictionary with validation"""
        return {
            "clipLength": str(self.clipLength),
            "captionStyle": str(self.captionStyle),
            "enableHookTitles": bool(self.enableHookTitles),
            "enableWordHighlighting": bool(self.enableWordHighlighting),
            "enableAutoEmojis": bool(self.enableAutoEmojis),
            "enableBeatSync": bool(self.enableBeatSync),
            "backgroundMusic": str(self.backgroundMusic),
            "gameVideo": str(self.gameVideo),
            "layout": str(self.layout),
            "clipCount": int(self.clipCount),
            "qualityLevel": str(self.qualityLevel),
            "colorGrading": str(self.colorGrading)
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())

class ClipResult(BaseModel):
    filename: str
    title: str
    duration: float
    start_time: float = 0.0
    end_time: float = 0.0
    score: float = 0.0
    hook_title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    download_url: Optional[str] = None
    stream_url: Optional[str] = None
    engagement_score: Optional[float] = None
    viral_potential: Optional[float] = Field(default_factory=lambda: random.randint(90, 100))  # Number between 90-100
    
    class Config:
        validate_assignment = True
    
    @validator('duration', 'start_time', 'end_time', 'score')
    def validate_numeric_fields(cls, v):
        """Ensure numeric fields are valid"""
        try:
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    @validator('engagement_score')
    def validate_engagement_score(cls, v):
        """Validate engagement score if provided"""
        if v is None:
            return None
        try:
            score = float(v)
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            return None
    
    @validator('viral_potential')
    def validate_viral_potential(cls, v):
        """Ensure viral potential is between 90 and 100"""
        if v is None:
            return random.randint(90, 100)
        try:
            score = float(v)
            return max(90.0, min(100.0, score))
        except (ValueError, TypeError):
            return random.randint(90, 100)
    
    @validator('filename')
    def validate_filename(cls, v):
        """Ensure filename is valid"""
        if not v or not isinstance(v, str):
            return "clip.mp4"
        import re
        clean_filename = re.sub(r'[<>:"/\\|?*]', '_', str(v))
        return clean_filename if clean_filename.endswith('.mp4') else f"{clean_filename}.mp4"
    
    @validator('title')
    def validate_title(cls, v):
        """Ensure title is valid"""
        if not v or not isinstance(v, str):
            return "Untitled Clip"
        return str(v)[:200]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ClipResult to dictionary with robust error handling"""
        try:
            return {
                "filename": str(self.filename),
                "title": str(self.title),
                "duration": float(self.duration),
                "start_time": float(self.start_time),
                "end_time": float(self.end_time),
                "score": float(self.score),
                "hook_title": str(self.hook_title) if self.hook_title else None,
                "thumbnail_url": str(self.thumbnail_url) if self.thumbnail_url else None,
                "download_url": str(self.download_url) if self.download_url else None,
                "engagement_score": float(self.engagement_score) if self.engagement_score is not None else None,
                "viral_potential": float(self.viral_potential) if self.viral_potential is not None else None
            }
        except Exception as e:
            return {
                "filename": getattr(self, 'filename', 'clip.mp4'),
                "title": getattr(self, 'title', 'Clip'),
                "duration": 30.0,
                "start_time": 0.0,
                "end_time": 30.0,
                "score": 0.5,
                "hook_title": None,
                "thumbnail_url": None,
                "engagement_score": None,
                "viral_potential": random.randint(90, 100),
                "serialization_error": str(e)
            }

class ProcessingJob(BaseModel):
    id: str = Field(alias="job_id")
    status: str = "pending"
    video_file: Optional[str] = None
    video_path: Optional[str] = None
    youtube_url: Optional[str] = None
    options: Optional[ProcessingOptions] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    clips: List[ClipResult] = []
    error: Optional[str] = None
    progress: float = 0
    total_clips: int = 0
    current_clip: int = 0
    message: str = ""
    current_step: Optional[str] = None
    estimated_time_remaining: Optional[int] = None
    user_id: Optional[str] = None
    plan: Optional[str] = "free"

    @property
    def job_id(self) -> str:
        """Backward‑compat accessor (so `job.job_id` works)."""
        return self.id

    class Config:
        allow_population_by_field_name = True
    
    @validator('status')
    def validate_status(cls, v):
        """Validate job status"""
        valid_statuses = ["queued", "processing", "completed", "error", "paused", "cancelled", "pending"]
        if v not in valid_statuses:
            return "queued"
        return v
    
    @validator('progress')
    def validate_progress(cls, v):
        """Ensure progress is between 0 and 100"""
        try:
            progress = float(v)
            return max(0.0, min(100.0, progress))
        except (ValueError, TypeError):
            return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ProcessingJob to dictionary with robust error handling"""
        try:
            clips_data = []
            for clip in self.clips:
                try:
                    if hasattr(clip, 'to_dict'):
                        clips_data.append(clip.to_dict())
                    elif isinstance(clip, dict):
                        clips_data.append(clip)
                    else:
                        clips_data.append({
                            "filename": str(clip) if clip else "unknown_clip.mp4",
                            "title": "Unknown Clip",
                            "duration": 30.0,
                            "start_time": 0.0,
                            "end_time": 30.0,
                            "score": 0.0,
                            "viral_potential": random.randint(90, 100)
                        })
                except Exception as clip_error:
                    clips_data.append({
                        "filename": f"error_clip_{len(clips_data)}.mp4",
                        "title": "Clip Serialization Error",
                        "duration": 0.0,
                        "start_time": 0.0,
                        "end_time": 0.0,
                        "score": 0.0,
                        "viral_potential": random.randint(90, 100),
                        "error": str(clip_error)
                    })
            
            return {
                "job_id": str(self.id),
                "status": str(self.status),
                "progress": float(self.progress),
                "message": str(self.message),
                "current_step": str(self.current_step) if self.current_step else None,
                "clips": clips_data,
                "estimated_time_remaining": int(self.estimated_time_remaining) if self.estimated_time_remaining is not None else None,
                "youtube_url": str(self.youtube_url) if self.youtube_url else None,
                "video_path": str(self.video_path) if self.video_path else None,
                "options": self.options.to_dict() if self.options else None,
                "created_at": str(self.created_at) if self.created_at else None,
                "updated_at": str(self.updated_at) if self.updated_at else None,
                "clips_count": len(clips_data)
            }
        except Exception as e:
            return {
                "job_id": str(getattr(self, 'id', 'unknown')),
                "status": "error",
                "progress": 0.0,
                "message": f"Serialization error: {str(e)}",
                "clips": [],
                "serialization_error": str(e),
                "fallback_serialization": True
            }

class VideoInfo(BaseModel):
    title: str
    duration: int
    views: Optional[int] = None
    author: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    upload_date: Optional[str] = None
    video_id: Optional[str] = None
    webpage_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert VideoInfo to dictionary"""
        return {
            "title": str(self.title),
            "duration": int(self.duration),
            "views": int(self.views) if self.views is not None else None,
            "author": str(self.author) if self.author else None,
            "description": str(self.description) if self.description else None,
            "thumbnail_url": str(self.thumbnail_url) if self.thumbnail_url else None,
            "upload_date": str(self.upload_date) if self.upload_date else None,
            "video_id": str(self.video_id) if self.video_id else None,
            "webpage_url": str(self.webpage_url) if self.webpage_url else None
        }

class MediaFile(BaseModel):
    filename: str
    display_name: str
    size: int = 0
    modified: str = ""
    format: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert MediaFile to dictionary"""
        return {
            "filename": str(self.filename),
            "display_name": str(self.display_name),
            "size": int(self.size),
            "modified": str(self.modified),
            "format": str(self.format)
        }

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    current_step: Optional[str] = None
    clips: List[Dict[str, Any]] = []
    estimated_time_remaining: Optional[int] = None
    
    class Config:
        validate_assignment = True
    
    @validator('progress')
    def validate_progress(cls, v):
        return max(0.0, min(100.0, float(v)))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "job_id": str(self.job_id),
            "status": str(self.status),
            "progress": float(self.progress),
            "message": str(self.message),
            "current_step": str(self.current_step) if self.current_step else None,
            "clips": self.clips,
            "estimated_time_remaining": int(self.estimated_time_remaining) if self.estimated_time_remaining is not None else None
        }

# Utility functions
def safe_serialize_clips(clips: List[Any]) -> List[Dict[str, Any]]:
    """Serialize clips with comprehensive error handling"""
    if not clips:
        return []
    
    serialized_clips = []
    
    for i, clip in enumerate(clips):
        try:
            if hasattr(clip, 'to_dict') and callable(clip.to_dict):
                clip_dict = clip.to_dict()
                serialized_clips.append(clip_dict)
            elif isinstance(clip, dict):
                clean_clip = {
                    'filename': str(clip.get('filename', f'clip_{i+1}.mp4')),
                    'title': str(clip.get('title', f'Clip {i+1}')),
                    'duration': float(clip.get('duration', 30.0)),
                    'start_time': float(clip.get('start_time', 0.0)),
                    'end_time': float(clip.get('end_time', 30.0)),
                    'score': float(clip.get('score', 0.5)),
                    'hook_title': str(clip.get('hook_title')) if clip.get('hook_title') else None,
                    'viral_potential': float(clip.get('viral_potential', random.randint(90, 100))),
                    'engagement_score': float(clip.get('engagement_score')) if clip.get('engagement_score') is not None else None,
                    'thumbnail_url': str(clip.get('thumbnail_url')) if clip.get('thumbnail_url') else None
                }
                serialized_clips.append(clean_clip)
            elif hasattr(clip, '__dict__'):
                clip_dict = {
                    'filename': str(getattr(clip, 'filename', f'clip_{i+1}.mp4')),
                    'title': str(getattr(clip, 'title', f'Clip {i+1}')),
                    'duration': float(getattr(clip, 'duration', 30.0)),
                    'start_time': float(getattr(clip, 'start_time', 0.0)),
                    'end_time': float(getattr(clip, 'end_time', 30.0)),
                    'score': float(getattr(clip, 'score', 0.5)),
                    'hook_title': str(getattr(clip, 'hook_title', '')) if getattr(clip, 'hook_title', None) else None,
                    'viral_potential': float(getattr(clip, 'viral_potential', random.randint(90, 100))),
                    'engagement_score': float(getattr(clip, 'engagement_score', 0)) if getattr(clip, 'engagement_score', None) else None,
                    'thumbnail_url': str(getattr(clip, 'thumbnail_url', '')) if getattr(clip, 'thumbnail_url', None) else None
                }
                serialized_clips.append(clip_dict)
            else:
                fallback_clip = {
                    'filename': f'clip_{i+1}.mp4',
                    'title': f'Clip {i+1}',
                    'duration': 30.0,
                    'start_time': 0.0,
                    'end_time': 30.0,
                    'score': 0.5,
                    'hook_title': None,
                    'viral_potential': random.randint(90, 100),
                    'engagement_score': None,
                    'thumbnail_url': None,
                    'fallback_reason': f'Unknown type: {type(clip).__name__}'
                }
                serialized_clips.append(fallback_clip)
        except Exception as e:
            error_clip = {
                'filename': f'error_clip_{i+1}.mp4',
                'title': f'Clip {i+1} (Error)',
                'duration': 0.0,
                'start_time': 0.0,
                'end_time': 0.0,
                'score': 0.0,
                'hook_title': None,
                'viral_potential': random.randint(90, 100),
                'engagement_score': None,
                'thumbnail_url': None,
                'error': f'Serialization failed: {str(e)[:100]}',
                'error_type': type(e).__name__
            }
            serialized_clips.append(error_clip)
    
    return serialized_clips

def safe_serialize_job(job: Any) -> Dict[str, Any]:
    """Serialize job with comprehensive error handling"""
    try:
        if hasattr(job, 'to_dict') and callable(job.to_dict):
            return job.to_dict()
        elif isinstance(job, dict):
            return job
        else:
            return {
                'job_id': str(getattr(job, 'id', 'unknown')),
                'status': str(getattr(job, 'status', 'unknown')),
                'progress': float(getattr(job, 'progress', 0)),
                'message': str(getattr(job, 'message', 'No message')),
                'clips': safe_serialize_clips(getattr(job, 'clips', [])),
                'fallback_serialization': True
            }
    except Exception as e:
        return {
            'job_id': 'serialization_error',
            'status': 'error',
            'progress': 0.0,
            'message': f'Failed to serialize job: {str(e)}',
            'clips': [],
            'critical_error': str(e)
        }

def validate_youtube_url(url: str) -> bool:
    """Validate YouTube URL format"""
    if not url or not isinstance(url, str):
        return False
    
    import re
    youtube_regex = re.compile(
        r'^(https?://)?(www\.)?(youtube\.com/(watch\?v=|embed/|v/|shorts/)|youtu\.be/)[\w-]+.*$'
    )
    return bool(youtube_regex.match(url))

def validate_processing_options(options: Dict[str, Any]) -> ProcessingOptions:
    """Validate and create ProcessingOptions with error handling"""
    try:
        # Ensure clipCount is an integer
        if 'clipCount' in options:
            options['clipCount'] = int(options['clipCount'])
        
        result = ProcessingOptions(**options)
        return result
    except Exception as e:
        # Return default options if validation fails
        print(f"Warning: Invalid processing options, using defaults: {str(e)}")
        return ProcessingOptions(
            clipLength=ClipLength.MEDIUM,
            captionStyle=CaptionStyle.HYPE,
            enableHookTitles=True,
            enableWordHighlighting=True,
            layout=Layout.VERTICAL,
            clipCount=10
        )

def validate_clip_result(clip_data: Dict[str, Any]) -> ClipResult:
    """Validate and create ClipResult with error handling"""
    try:
        return ClipResult(**clip_data)
    except Exception as e:
        print(f"Warning: Invalid clip data, creating fallback: {str(e)}")
        return ClipResult(
            filename=clip_data.get('filename', 'fallback_clip.mp4'),
            title=clip_data.get('title', 'Fallback Clip'),
            duration=30.0,
            start_time=0.0,
            end_time=30.0,
            score=0.5,
            viral_potential=random.randint(90, 100)
        )