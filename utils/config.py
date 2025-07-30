import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Environment
    NODE_ENV = os.getenv("NODE_ENV", "development")
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Stripe
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID")
    STRIPE_CREATOR_PRICE_ID = os.getenv("STRIPE_CREATOR_PRICE_ID")
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    
    # Frontend
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # CORS Origins
    CORS_ORIGINS = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://www.topclip.ai",
        "https://topclip.ai",
    ]
    
    # File Configuration
    TEMP_DIR = os.getenv("TEMP_DIR", "temp")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
    THUMBNAILS_DIR = os.getenv("THUMBNAILS_DIR", "thumbnails")
    MUSIC_DIR = os.getenv("MUSIC_DIR", "music")
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 100))
    
    # Processing
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", 5))
    JOB_CLEANUP_HOURS = int(os.getenv("JOB_CLEANUP_HOURS", 24))
    DISABLE_AI_ANALYZER = os.getenv("DISABLE_AI_ANALYZER", "false").lower() == "true"
    
    # FFmpeg
    FFMPEG_PRESET = os.getenv("FFMPEG_PRESET", "medium")
    FFMPEG_CRF = int(os.getenv("FFMPEG_CRF", 23))
    FFMPEG_MAXRATE = os.getenv("FFMPEG_MAXRATE", "6M")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def is_development(self) -> bool:
        return self.NODE_ENV == "development"
    
    @property
    def is_production(self) -> bool:
        return self.NODE_ENV == "production"
    
    def add_production_cors_origin(self, origin: str):
        """Add production CORS origin"""
        if origin not in self.CORS_ORIGINS:
            self.CORS_ORIGINS.append(origin)

# Global config instance
config = Config()

# Add production CORS if in production
if config.is_production and config.FRONTEND_URL:
    config.add_production_cors_origin(config.FRONTEND_URL)