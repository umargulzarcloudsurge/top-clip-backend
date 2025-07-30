#!/usr/bin/env python3

import uvicorn
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Configuration
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    
    print(f"🚀 Starting AI Clips Backend on {host}:{port}")
    print(f"📁 Working directory: {backend_dir}")
    print(f"🔗 API will be available at: http://{host}:{port}")
    print(f"📖 Interactive docs at: http://{host}:{port}/docs")
    
    # Check critical dependencies
    try:
        import ffmpeg
        print("✅ FFmpeg Python bindings found")
    except ImportError:
        print("❌ FFmpeg Python bindings not found. Install with: pip install ffmpeg-python")
    
    try:
        import openai
        if os.getenv("OPENAI_API_KEY"):
            print("✅ OpenAI API key configured")
        else:
            print("⚠️  OpenAI API key not found. Set OPENAI_API_KEY in .env")
    except ImportError:
        print("❌ OpenAI package not found. Install with: pip install openai")
    
    print("ℹ️  Using in-memory job storage (Redis disabled)")
    
    # Start the server with enhanced concurrency settings
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=[str(backend_dir)],
        log_level="info",
        workers=1,  # Single worker for development
        loop="asyncio",  # Use asyncio event loop
        access_log=True,
        limit_concurrency=100,  # Handle more concurrent requests
        limit_max_requests=1000,  # Maximum requests before restart
        timeout_keep_alive=30  # Keep connections alive longer
    )