import os
import logging
import asyncio
from typing import Optional, Dict, List
from supabase import create_client, Client
from dotenv import load_dotenv
import aiofiles
from pathlib import Path

load_dotenv()

logger = logging.getLogger(__name__)

class StorageManager:
    def __init__(self):
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            raise Exception("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for storage")
        
        try:
            self.supabase: Client = create_client(supabase_url, supabase_key)
            self.bucket_name = "user-clips"
            logger.info("✅ Storage Manager initialized with Supabase")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Storage Manager: {str(e)}")
            raise e
    
    async def upload_thumbnail(self, user_id: str, local_file_path: str, thumbnail_filename: str) -> Optional[str]:
        """Upload a thumbnail file to Supabase Storage"""
        try:
            # Create storage path: user_id/thumbnails/thumbnail_filename
            storage_path = f"{user_id}/thumbnails/{thumbnail_filename}"
            
            logger.info(f"🖼️ Uploading thumbnail to storage: {storage_path}")
            
            # Read file content
            async with aiofiles.open(local_file_path, 'rb') as file:
                file_content = await file.read()
            
            # Upload to Supabase Storage
            response = self.supabase.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            
            # Check if upload was successful
            if hasattr(response, 'error') and response.error:
                logger.error(f"❌ Thumbnail upload error: {response.error}")
                return None
            else:
                logger.info(f"✅ Successfully uploaded thumbnail: {storage_path}")
                return storage_path
                
        except Exception as e:
            logger.error(f"❌ Error uploading thumbnail: {str(e)}")
            return None
    
    async def upload_clip(self, user_id: str, local_file_path: str, clip_filename: str) -> Optional[str]:
        """Upload a clip file to Supabase Storage"""
        try:
            # Create storage path: user_id/clip_filename
            storage_path = f"{user_id}/{clip_filename}"
            
            logger.info(f"📤 Uploading clip to storage: {storage_path}")
            
            # Read file content
            async with aiofiles.open(local_file_path, 'rb') as file:
                file_content = await file.read()
            
            # Upload to Supabase Storage with retry logic and exponential backoff
            max_retries = 5
            base_delay = 2  # Start with 2 seconds
            
            for attempt in range(max_retries):
                try:
                    print(f"🔄 Upload attempt {attempt + 1}/{max_retries} for {storage_path}")
                    
                    response = self.supabase.storage.from_(self.bucket_name).upload(
                        path=storage_path,
                        file=file_content,
                        file_options={"content-type": "video/mp4", "upsert": "true"}
                    )
                    
                    # Check if upload was successful
                    if hasattr(response, 'error') and response.error:
                        logger.error(f"❌ Supabase upload error (attempt {attempt + 1}): {response.error}")
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            print(f"⏳ Waiting {delay}s before retry...")
                            await asyncio.sleep(delay)
                            continue
                        return None
                    else:
                        logger.info(f"✅ Successfully uploaded clip: {storage_path}")
                        print(f"✅ Upload successful on attempt {attempt + 1}")
                        return storage_path
                        
                except Exception as upload_error:
                    error_msg = str(upload_error)
                    logger.error(f"❌ Upload attempt {attempt + 1} failed: {error_msg}")
                    print(f"❌ Upload attempt {attempt + 1} failed: {error_msg}")
                    
                    # Check if it's a network-related error
                    if "Broken pipe" in error_msg or "Connection" in error_msg:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            print(f"🔌 Network error detected. Waiting {delay}s before retry...")
                            await asyncio.sleep(delay)
                            continue
                    
                    if attempt == max_retries - 1:
                        raise upload_error
                    
                    # Wait before next attempt
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Error uploading clip: {str(e)}")
            return None
    
    async def upload_and_cleanup_clip(self, user_id: str, local_file_path: str, clip_filename: str) -> Optional[str]:
        """Upload clip to storage and immediately delete local file"""
        try:
            # Upload the clip
            storage_path = await self.upload_clip(user_id, local_file_path, clip_filename)
            
            if storage_path:
                # Immediately delete local file to save disk space
                try:
                    os.remove(local_file_path)
                    logger.info(f"🗑️ Deleted local clip file: {local_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Failed to delete local file {local_file_path}: {str(cleanup_error)}")
                
                return storage_path
            else:
                logger.error(f"❌ Failed to upload clip, keeping local file: {local_file_path}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in upload_and_cleanup_clip: {str(e)}")
            return None
    
    async def upload_and_cleanup_thumbnail(self, user_id: str, local_file_path: str, thumbnail_filename: str) -> Optional[str]:
        """Upload thumbnail to storage and immediately delete local file"""
        try:
            # Upload the thumbnail
            storage_path = await self.upload_thumbnail(user_id, local_file_path, thumbnail_filename)
            
            if storage_path:
                # Immediately delete local file to save disk space
                try:
                    os.remove(local_file_path)
                    logger.info(f"🗑️ Deleted local thumbnail file: {local_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Failed to delete local thumbnail file {local_file_path}: {str(cleanup_error)}")
                
                return storage_path
            else:
                logger.error(f"❌ Failed to upload thumbnail, keeping local file: {local_file_path}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in upload_and_cleanup_thumbnail: {str(e)}")
            return None
    
    async def save_clip_metadata(self, user_id: str, job_id: str, clip_data: Dict) -> bool:
        """Save clip metadata to the database"""
        try:
            clip_record = {
                "user_id": user_id,
                "job_id": job_id,
                "filename": clip_data["filename"],
                "title": clip_data.get("title", "Untitled Clip"),
                "duration": clip_data.get("duration", 0),
                "file_size": clip_data.get("file_size", 0),
                "storage_path": clip_data["storage_path"],
                "thumbnail_path": clip_data.get("thumbnail_path"),
                "hook_title": clip_data.get("hook_title"),
                "viral_potential": clip_data.get("viral_potential")
            }
            
            logger.info(f"💾 Saving clip metadata: {clip_record}")
            response = self.supabase.table("user_clips").insert(clip_record).execute()
            
            if response.data:
                logger.info(f"✅ Saved clip metadata for {clip_data['filename']}")
                return True
            else:
                logger.error(f"❌ Failed to save clip metadata: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error saving clip metadata: {str(e)}")
            return False
    
    async def get_user_clips(self, user_id: str) -> List[Dict]:
        """Get all clips for a user"""
        try:
            response = self.supabase.table("user_clips").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            
            if response.data:
                logger.info(f"📋 Retrieved {len(response.data)} clips for user {user_id}")
                return response.data
            else:
                logger.info(f"📋 No clips found for user {user_id}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error getting user clips: {str(e)}")
            return []
    
    async def get_clip_stream_url(self, storage_path: str) -> str:
        """Get a signed URL for streaming a clip (longer expiry for video streaming)"""
        try:
            # Create a signed URL that expires in 4 hours for video streaming
            response = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path,
                expires_in=14400  # 4 hours
            )
            
            if response.get('signedURL'):
                return response['signedURL']
            else:
                logger.error(f"❌ Failed to create signed URL for {storage_path}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Error creating signed URL: {str(e)}")
            return ""
    
    def get_clip_url(self, storage_path: str) -> str:
        """Get a signed URL for accessing a clip"""
        try:
            # Create a signed URL that expires in 1 hour
            response = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path,
                expires_in=3600  # 1 hour
            )
            
            if response.get('signedURL'):
                return response['signedURL']
            else:
                logger.error(f"❌ Failed to create signed URL for {storage_path}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Error creating signed URL: {str(e)}")
            return ""
    
    async def cleanup_local_directory(self, directory_path: str) -> bool:
        """Clean up entire local directory and its contents"""
        try:
            if os.path.exists(directory_path):
                import shutil
                shutil.rmtree(directory_path)
                logger.info(f"🗑️ Cleaned up local directory: {directory_path}")
                return True
            else:
                logger.info(f"📁 Directory already cleaned: {directory_path}")
                return True
        except Exception as e:
            logger.error(f"❌ Error cleaning up directory {directory_path}: {str(e)}")
            return False
    
    async def delete_clip(self, user_id: str, clip_id: str) -> bool:
        """Delete a clip and its metadata"""
        try:
            # First get the clip metadata
            response = self.supabase.table("user_clips").select("storage_path").eq("id", clip_id).eq("user_id", user_id).execute()
            
            if not response.data:
                logger.warning(f"⚠️ Clip {clip_id} not found for user {user_id}")
                return False
            
            storage_path = response.data[0]["storage_path"]
            
            # Delete from storage
            storage_response = self.supabase.storage.from_(self.bucket_name).remove([storage_path])
            
            # Delete metadata from database
            db_response = self.supabase.table("user_clips").delete().eq("id", clip_id).eq("user_id", user_id).execute()
            
            if db_response.data:
                logger.info(f"✅ Deleted clip {clip_id} for user {user_id}")
                return True
            else:
                logger.error(f"❌ Failed to delete clip metadata")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting clip: {str(e)}")
            return False

# Global storage manager instance
storage_manager = StorageManager()