import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from supabase import create_client, Client
from dotenv import load_dotenv
import time

load_dotenv()

logger = logging.getLogger(__name__)

class UsageTracker:
    def __init__(self):
        self.plan_limits = {
            "pro": 50,
            "creator": 200
        }
        
        # PRODUCTION: In-memory cache to prevent Supabase spam
        self.usage_cache: Dict[str, Dict] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.CACHE_DURATION = 300  # 5 minutes cache
        
        # Initialize Supabase client (required)
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            raise Exception("SUPABASE_URL and SUPABASE_SERVICE_KEY are required in environment variables")
        
        try:
            self.supabase: Client = create_client(supabase_url, supabase_key)
            logger.info("✅ Supabase client initialized for usage tracking")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {str(e)}")
            raise Exception(f"Failed to connect to Supabase: {str(e)}")
        
        logger.info("🔢 Usage Tracker initialized with in-memory cache")
    
    def _get_current_month_key(self) -> str:
        """Get current month key for tracking"""
        return datetime.now().strftime("%Y-%m")
    
    async def get_user_usage(self, user_id: str, plan: str = None) -> Dict:
        """Get current usage for a user - cached for production performance"""
        try:
            # Check cache first
            cache_key = f"{user_id}:{plan}:{self._get_current_month_key()}"
            current_time = time.time()
            
            if (cache_key in self.usage_cache and 
                cache_key in self.cache_timestamps and
                current_time - self.cache_timestamps[cache_key] < self.CACHE_DURATION):
                
                logger.info(f"📋 Cache HIT for user {user_id} (age: {int(current_time - self.cache_timestamps[cache_key])}s)")
                return self.usage_cache[cache_key]
            
            # Cache miss - fetch from Supabase
            logger.info(f"📋 Cache MISS for user {user_id} - fetching from Supabase")
            usage_data = await self._get_usage_from_supabase(user_id, plan)
            
            # Store in cache
            self.usage_cache[cache_key] = usage_data
            self.cache_timestamps[cache_key] = current_time
            
            return usage_data
            
        except Exception as e:
            logger.error(f"❌ Error getting user usage: {str(e)}")
            raise Exception(f"Failed to get usage data: {str(e)}")
    
    async def _get_usage_from_supabase(self, user_id: str, plan: str) -> Dict:
        """Get usage from Supabase database"""
        try:
            month_key = self._get_current_month_key()
            logger.info(f"🔍 SUPABASE QUERY for user: {user_id}, plan: {plan}")
            
            # Get user profile to determine plan
            profile_response = self.supabase.table("user_profiles").select("plan").eq("id", user_id).execute()
            
            if profile_response.data:
                actual_plan = profile_response.data[0]["plan"]
            else:
                actual_plan = plan or None
                logger.warning(f"⚠️ No profile found for user {user_id}, using plan: {actual_plan}")
            
            # Get or create usage record
            usage_response = self.supabase.rpc("ensure_current_month_usage", {
                "user_uuid": user_id,
                "user_plan": actual_plan
            }).execute()
            # Only log if there's an issue with the response
            if not usage_response.data:
                logger.warning(f"⚠️ No usage data returned for user {user_id}")
                return None
                
            usage_data = usage_response.data[0]
            # Use the actual limit from the database, not hardcoded limits
            limit = usage_data.get("clips_limit", self.plan_limits.get(actual_plan.lower() if actual_plan else None, 0))
            remaining = max(0, limit - usage_data["clips_created"])
            
            result = {
                "clips_created": usage_data["clips_created"],
                "clips_remaining": remaining,
                "clips_limit": limit,
                "plan": actual_plan,
                "month": month_key,
                "can_create_clips": remaining > 0
            }
            return result
                
        except Exception as e:
            logger.error(f"❌ Supabase usage query failed: {str(e)}")
            raise Exception(f"Failed to get usage from Supabase: {str(e)}")
    

    
    async def check_can_create_clips(self, user_id: str, requested_clips: int, plan: str = None) -> Tuple[bool, str, Dict]:
        """Check if user can create the requested number of clips"""
        try:
            usage = await self.get_user_usage(user_id, plan)
            
            if not usage["can_create_clips"]:
                return False, "Monthly clip limit reached. Please upgrade your plan or wait for next month.", usage
            
            if requested_clips > usage["clips_remaining"]:
                return False, f"Cannot create {requested_clips} clips. You have {usage['clips_remaining']} clips remaining this month.", usage
            
            return True, "OK", usage
            
        except Exception as e:
            logger.error(f"❌ Error checking clip creation: {str(e)}")
            raise Exception(f"Failed to check usage limits: {str(e)}")
    
    def _invalidate_user_cache(self, user_id: str):
        """Clear cache for a specific user when their data changes"""
        keys_to_remove = [key for key in self.usage_cache.keys() if key.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self.usage_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
        logger.info(f"🗑️ Cleared cache for user {user_id}")

    async def record_clip_creation(self, user_id: str, clips_created: int, plan: str = None) -> bool:
        """Record that clips were created and clear cache"""
        try:
            result = await self._record_clips_supabase(user_id, clips_created, plan)
            if result:
                # Clear cache so next request gets fresh data
                self._invalidate_user_cache(user_id)
            return result
        except Exception as e:
            logger.error(f"❌ Error recording clip creation: {str(e)}")
            raise Exception(f"Failed to record clip creation: {str(e)}")
    
    async def _record_clips_supabase(self, user_id: str, clips_created: int, plan: str) -> bool:
        """Record clips in Supabase"""
        try:
            response = self.supabase.rpc("record_clip_creation", {
                "clips_count": clips_created,
                "user_plan": plan,
                "user_uuid": user_id
            }).execute()

            
            if response.data:
                logger.info(f"📊 Recorded {clips_created} clips for user {user_id} in Supabase")
                return True
            else:
                logger.error("⚠️ Supabase record failed - no data returned")
                raise Exception("Failed to record clips in Supabase")
                
        except Exception as e:
            logger.error(f"❌ Supabase record failed: {str(e)}")
            raise Exception(f"Failed to record clips in Supabase: {str(e)}")
    

    
    async def get_max_clips_for_request(self, user_id: str, plan: str = None) -> int:
        """Get maximum clips user can create in a single request - uses cached data"""
        try:
            # This will use cached data if available, no extra Supabase call
            usage = await self.get_user_usage(user_id, plan)
            return min(4, usage["clips_remaining"])  # Max 4 clips per request, or remaining clips
        except Exception as e:
            logger.error(f"❌ Error getting max clips: {str(e)}")
            raise Exception(f"Failed to get max clips: {str(e)}")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics for monitoring"""
        current_time = time.time()
        active_entries = 0
        
        for timestamp in self.cache_timestamps.values():
            if current_time - timestamp < self.CACHE_DURATION:
                active_entries += 1
        
        return {
            "total_cached_users": len(self.usage_cache),
            "active_cached_users": active_entries,
            "cache_duration_minutes": self.CACHE_DURATION / 60,
            "cache_hit_ratio": "tracking not implemented"  # Could add hit/miss counters
        }


# Global usage tracker instance
usage_tracker = UsageTracker()