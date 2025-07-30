# AI Clips Backend

A high-performance backend for generating viral TikTok/YouTube Shorts clips from long-form videos using AI-powered highlight detection and automated video processing.
  
## Features

- **YouTube Video Processing**: Download and process videos from YouTube URLs
- **AI Highlight Detection**: Multi-modal analysis using audio, visual, and content features
- **Speech-to-Text**: OpenAI Whisper API integration for transcription
- **Video Enhancement**: Automatic captions, aspect ratio conversion, and viral styling
- **Real-time Progress**: WebSocket support for live processing updates
- **Professional Hooks**: AI-generated viral hooks and titles
- **Multiple Output Formats**: Support for TikTok (9:16), YouTube Shorts, and Instagram Reels

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   YouTube URL   │───▶│  Video Download │───▶│  AI Analysis    │
│   File Upload   │    │    (yt-dlp)     │    │  (Multi-modal)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Clip Output   │◀───│ Video Processing│◀───│ Highlight Extract│
│   (MP4 Files)   │    │    (FFmpeg)     │    │   (Top Moments) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- FFmpeg installed
- OpenAI API key
- Redis (optional, for job persistence)

### Installation

1. **Clone and navigate to backend:**
   ```bash
   cd backend
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

4. **Run the server:**
   ```bash
   python main.py
   ```

The API will be available at `http://localhost:8000`

### Docker Setup (Optional)

```bash
docker build -t ai-clips-backend .
docker run -p 8000:8000 --env-file .env ai-clips-backend
```

## API Documentation

### Core Endpoints

#### Process Video
```http
POST /api/process-video
Content-Type: multipart/form-data

{
  "youtube_url": "https://youtube.com/watch?v=...",
  "options": {
    "clipLength": "30-60s",
    "captionStyle": "TikTok Style",
    "enableHookTitles": true,
    "backgroundMusic": "trending-beat.mp3",
    "layout": "Vertical (9:16)",
    "clipCount": 5
  }
}
```

#### Get Job Status
```http
GET /api/job-status/{job_id}
```

#### Download Results
```http
GET /api/download/{job_id}
```

#### Get Available Music Files
```http
GET /api/music-files
```

#### Get Available Game Videos
```http
GET /api/game-videos
```

#### Get Combined Media Info
```http
GET /api/media-info
```

### Media Files Response Format

```json
{
  "files": [
    {
      "filename": "Aurora on the Boulevard - National Sweetheart.mp3",
      "display_name": "Aurora on the Boulevard - National Sweetheart",
      "size": 5242880,
      "modified": "2023-01-15T10:30:00",
      "format": ".mp3"
    }
  ]
}
```

### Combined Media Info Response Format

```json
{
  "music_files": [...],
  "game_videos": [...],
  "total_music": 3,
  "total_game_videos": 1
}
```

#### WebSocket Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/{job_id}');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Progress:', update.progress);
};
```

### Response Format

```json
{
  "job_id": "uuid-string",
  "status": "processing",
  "progress": 75.5,
  "message": "Processing video clips",
  "current_step": "processing",
  "clips": [
    {
      "filename": "clip_01_hook_moment.mp4",
      "title": "Hook Moment",
      "duration": 30.5,
      "start_time": 120.0,
      "end_time": 150.5,
      "score": 0.85,
      "hook_title": "This will blow your mind!",
      "thumbnail_url": "/api/thumbnail/job_id/clip_01.jpg",
      "engagement_score": 0.9,
      "viral_potential": "high"
    }
  ],
  "estimated_time_remaining": 45
}
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional
REDIS_URL=redis://localhost:6379
PORT=8000
HOST=0.0.0.0
MAX_FILE_SIZE_MB=100
MAX_CONCURRENT_JOBS=5
```

### Processing Options

- **Clip Length**: `<30s`, `30-60s`, `60-90s`
- **Caption Styles**: `TikTok Style`, `YouTube Shorts`, `Modern Glow`, etc.
- **Layouts**: `Vertical (9:16)`, `Square (1:1)`, `Horizontal (16:9)`, `Fit with Blur`
- **Background Music**: Custom audio files from `/music` directory

## AI Features

### Multi-Modal Analysis

The system analyzes videos using three approaches:

1. **Audio Analysis**:
   - Energy detection using RMS
   - Onset detection for sudden changes
   - Tempo and beat tracking
   - Spectral analysis for content type

2. **Visual Analysis**:
   - Scene change detection
   - Motion intensity analysis
   - Face detection and tracking
   - Brightness and contrast analysis

3. **Content Analysis**:
   - Speech-to-text using OpenAI Whisper
   - Sentiment analysis
   - Quotable moment detection
   - Keyword extraction

### Highlight Scoring

Each potential clip is scored based on:
- **Audio Energy** (25%): High-energy segments
- **Visual Interest** (25%): Motion, faces, scene changes
- **Content Quality** (20%): Quotable moments, emotional content
- **Viral Potential** (30%): AI-predicted engagement

### Professional Hook Generation

AI-generated hooks optimized for social media:
- Platform-specific optimization (TikTok, YouTube Shorts)
- Emotional trigger analysis
- Curiosity gap creation
- Viral keyword integration

## File Structure

```
backend/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── utils/
│   ├── __init__.py
│   ├── models.py          # Pydantic models
│   ├── youtube_downloader.py  # YouTube video download
│   ├── video_processor.py     # FFmpeg video processing
│   ├── clip_analyzer.py       # AI highlight detection
│   ├── transcription.py       # OpenAI Whisper integration
│   ├── job_manager.py         # Job state management
│   └── professional_hook_generator.py  # Viral hook generation
├── temp/                  # Temporary files
├── output/               # Generated clips
├── thumbnails/           # Clip thumbnails
└── music/               # Background music files
```

## Performance

### Benchmarks

- **Processing Speed**: ~2-5 minutes for 10-minute source video
- **Concurrent Jobs**: Up to 10 simultaneous processing jobs
- **Memory Usage**: ~500MB per active job
- **Output Quality**: 1080p, optimized for mobile viewing

### Optimization Tips

1. **Use GPU acceleration** for FFmpeg if available
2. **Enable Redis** for job persistence across restarts
3. **Adjust clip count** based on source video length
4. **Use SSD storage** for temp files
5. **Monitor memory usage** with long videos

## Troubleshooting

### Common Issues

1. **FFmpeg not found**:
   ```bash
   # Install FFmpeg
   brew install ffmpeg  # macOS
   apt-get install ffmpeg  # Ubuntu
   ```

2. **OpenAI API errors**:
   - Check API key validity
   - Monitor rate limits
   - Verify account balance

3. **YouTube download failures**:
   - Update yt-dlp: `pip install --upgrade yt-dlp`
   - Check for geo-restrictions
   - Verify URL format

4. **Memory issues**:
   - Reduce concurrent jobs
   - Lower video quality settings
   - Clean temp files regularly

### Logging

Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python main.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/your-repo/issues)
- Documentation: [Full docs](https://docs.your-domain.com)
- Email: support@your-domain.com

---

**Built with**: FastAPI, OpenAI, FFmpeg, Redis, and modern AI techniques for viral content generation.
