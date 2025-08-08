# Redis Setup Guide for TopClip Backend

## Problem
The TopClip backend was experiencing 404 errors in the `/api/job-status/{job_id}` endpoint because jobs are stored in-memory and lost when the server restarts. This Redis setup provides persistent job storage.

## Redis Installation on Windows

### Option 1: Using Redis for Windows (Recommended)

1. **Download Redis for Windows**
   - Go to https://github.com/MicrosoftArchive/redis/releases
   - Download `Redis-x64-3.2.100.msi`
   - Install with default settings

2. **Start Redis Service**
   ```bash
   # Open Command Prompt as Administrator
   redis-server
   ```

### Option 2: Using Docker (Alternative)

1. **Install Docker Desktop**
   - Download from https://www.docker.com/products/docker-desktop
   
2. **Run Redis Container**
   ```bash
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   ```

### Option 3: Using WSL2 (Windows Subsystem for Linux)

1. **Install WSL2 and Ubuntu**
   ```bash
   wsl --install -d Ubuntu
   ```

2. **Install Redis in Ubuntu**
   ```bash
   sudo apt update
   sudo apt install redis-server
   sudo service redis-server start
   ```

## Configuration

The backend is already configured to use Redis. The configuration is in the `.env` file:

```env
# Redis Configuration (for job persistence across server restarts)
REDIS_URL=redis://localhost:6379/0
```

## Testing Redis Connection

1. **Test Redis is Running**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

2. **Check Backend Connection**
   - Start your FastAPI backend
   - Look for this log message:
     ```
     [OK] Redis connected: redis://localhost:6379/0
     ```

## How the Fix Works

### Enhanced Job Manager (`utils/enhanced_job_manager.py`)

The new `EnhancedJobManager` provides:

1. **Dual Storage**: Jobs are stored both in-memory (fast access) and Redis (persistence)
2. **Automatic Fallback**: If a job isn't found in memory, it checks Redis
3. **Smart Cleanup**: Old jobs are cleaned up from both memory and Redis
4. **Connection Handling**: Gracefully handles Redis connection failures

### Key Features

- **Job Persistence**: Jobs survive server restarts
- **Fallback System**: Works even if Redis is temporarily unavailable
- **Performance**: In-memory access for active jobs, Redis for persistence
- **Cleanup**: Automatic cleanup of old jobs (default: 1 week)

## Troubleshooting

### Redis Not Starting

```bash
# Windows: Check if port 6379 is in use
netstat -an | findstr 6379

# If port is in use by another service, change Redis port:
# In redis.conf (or redis.windows.conf):
# port 6380

# Update .env file:
# REDIS_URL=redis://localhost:6380/0
```

### Connection Issues

1. **Check Redis is running:**
   ```bash
   redis-cli ping
   ```

2. **Check firewall:** Make sure port 6379 is open

3. **Check logs:** Look for Redis connection messages in your backend logs

### Performance Considerations

- **Memory Usage**: Redis will use memory to store job data
- **Persistence**: Redis data persists across reboots (depending on configuration)
- **Cleanup**: Old jobs are automatically cleaned up to prevent memory bloat

## Production Recommendations

For production environments:

1. **Use Redis Cluster** for high availability
2. **Configure Redis persistence** (RDB + AOF)
3. **Set up monitoring** for Redis memory usage
4. **Use Redis AUTH** for security
5. **Configure proper backup strategy**

Example production Redis URL:
```env
REDIS_URL=redis://:password@redis-server:6379/0
```

## Benefits After Implementation

✅ **No More 404 Errors**: Jobs persist across server restarts
✅ **Better Performance**: Smart caching with fallback
✅ **Scalability**: Can handle multiple server instances
✅ **Monitoring**: Better job tracking and debugging
✅ **Reliability**: Graceful degradation if Redis is unavailable

## Verification

After setting up Redis and updating the backend:

1. **Create a job** via the API
2. **Restart the backend server**
3. **Query the job status** - it should still return the job data (from Redis)
4. **Check health endpoint**: `/health` should show Redis status

The system will now maintain job state across server restarts, eliminating the 404 errors users were experiencing.
