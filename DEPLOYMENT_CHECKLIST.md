# Quick Deployment Checklist - 404 Fix

## Pre-Deployment

### ✅ Files Modified/Added
- [x] Created: `utils/enhanced_job_manager.py` (new job manager with Redis)
- [x] Modified: `main.py` (updated to use EnhancedJobManager)
- [x] Modified: `.env` (added Redis configuration)
- [x] Created: `REDIS_SETUP.md` (installation guide)
- [x] Created: `FIX_SUMMARY.md` (detailed analysis)

### ✅ Prerequisites Check
- [ ] **Redis installed and running** (`redis-cli ping` returns `PONG`)
- [ ] **Python dependencies up-to-date** (redis package in requirements.txt)
- [ ] **Backup current system** (in case rollback needed)

## Deployment Steps

## Step 1: Install Redis

### For AWS Ubuntu (Recommended):
```bash
# Use the automated deployment script
chmod +x deploy-aws.sh
./deploy-aws.sh

# OR install manually:
sudo apt update
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### For Local Development:
```bash
# Option A: Windows
# Download and install from: https://github.com/MicrosoftArchive/redis/releases

# Option B: Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Option C: WSL2/Linux
sudo apt install redis-server && sudo service redis-server start
```

### Step 2: Verify Redis
```bash
redis-cli ping
# Expected output: PONG
```

### Step 3: Deploy Code Changes
```bash
# The main.py and enhanced_job_manager.py files are already in place
# .env file has been updated with REDIS_URL

# Verify .env contains:
# REDIS_URL=redis://localhost:6379/0
```

### Step 4: Restart Backend
```bash
# Stop current backend (Ctrl+C if running in terminal)
# Or restart service/container

# Start backend
python main.py
# Or: uvicorn main:app --host 0.0.0.0 --port 8000
```

### Step 5: Verify Deployment
```bash
# 1. Check logs for Redis connection
# Look for: "[OK] Redis connected: redis://localhost:6379/0"

# 2. Check health endpoint
curl http://localhost:8000/health
# Should show Redis status

# 3. Test job creation and persistence
curl -X POST http://localhost:8000/api/process-video \
  -F "youtube_url=https://youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "options={\"clipLength\":\"30-60s\",\"captionStyle\":\"Hype\",\"enableHookTitles\":true,\"layout\":\"Vertical (9:16)\",\"clipCount\":3}"

# Note the job_id from response

# 4. Restart backend server again

# 5. Check job status (should not return 404)
curl http://localhost:8000/api/job-status/{job_id}
```

## Success Indicators

### ✅ Log Messages (Good)
```
[OK] Redis connected: redis://localhost:6379/0
[OK] EnhancedJobManager created with Redis persistence
💾 Saved job {job_id} to Redis
📥 Loaded job {job_id} from Redis fallback
```

### ❌ Warning Messages (Still Works, But Degraded)
```
⚠️ Redis connection failed, using in-memory only
⚠️ Redis connection failed, using in-memory only: [Errno 61] Connection refused
```

## Testing Scenarios

### Test 1: Normal Operation
- [x] Create job → Should work
- [x] Check job status → Should return job data
- [x] Verify Redis has job data: `redis-cli KEYS "job:*"`

### Test 2: Server Restart (The Critical Test)
- [x] Create job and note job_id
- [x] Restart backend server
- [x] Check job status → Should still work (from Redis)
- [x] No 404 errors for valid job IDs

### Test 3: Redis Failure Handling
- [x] Stop Redis: `redis-cli shutdown` or stop Docker container
- [x] Backend should still work but log warnings
- [x] Start Redis again → Should reconnect automatically

## Troubleshooting

### Problem: Redis Connection Failed
```bash
# Check if Redis is running
redis-cli ping

# Check port
netstat -an | grep 6379

# Check Redis logs (Docker)
docker logs redis

# Check Redis config
redis-cli CONFIG GET port
```

### Problem: Import Errors
```bash
# Verify file exists
ls utils/enhanced_job_manager.py

# Check Python path
python -c "from utils.enhanced_job_manager import EnhancedJobManager; print('✅ Import works')"
```

### Problem: Still Getting 404s
```bash
# Check if old JobManager is still being used
grep -n "JobManager" main.py | grep -v Enhanced

# Check Redis job data
redis-cli KEYS "job:*"
redis-cli HGETALL "job:your-job-id"

# Check logs for job retrieval
# Should see: "📥 Loaded job {job_id} from Redis fallback"
```

## Rollback Procedure (If Needed)

### Option 1: Quick Revert
```python
# In main.py, change line ~62:
# from utils.enhanced_job_manager import EnhancedJobManager
from utils.job_manager import JobManager

# Change line ~68:
# job_manager = EnhancedJobManager()
job_manager = JobManager()
```

### Option 2: Disable Redis
```bash
# Comment out in .env:
# REDIS_URL=redis://localhost:6379/0

# Restart backend - will work as before
```

## Performance Monitoring

### Redis Memory Usage
```bash
redis-cli INFO memory
redis-cli MEMORY USAGE job:some-job-id
```

### Job Statistics
```bash
# Check via API
curl http://localhost:8000/health

# Direct Redis check
redis-cli KEYS "job:*" | wc -l
redis-cli KEYS "clips:*" | wc -l
```

## Production Notes

### For Production Deployment:
1. **Use managed Redis** (AWS ElastiCache, Azure Cache, etc.)
2. **Configure Redis authentication** 
3. **Set up Redis persistence** (RDB snapshots + AOF)
4. **Monitor Redis memory usage**
5. **Set up alerts** for Redis connection failures

### Example Production .env:
```env
REDIS_URL=redis://:password@production-redis-cluster:6379/0
```

## Expected Results

After successful deployment:
- ✅ Zero 404 errors for valid job IDs
- ✅ Jobs persist across server restarts  
- ✅ Better error messages for invalid job IDs
- ✅ Health endpoint shows Redis status
- ✅ System degrades gracefully if Redis is unavailable

The fix is backward-compatible and provides enterprise-grade job persistence while maintaining all existing functionality.
