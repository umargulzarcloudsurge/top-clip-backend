import os
import logging
import asyncio
import subprocess
from typing import Optional
from .models import CaptionStyle

logger = logging.getLogger(__name__)

class PyCapsService:
    """PyCaps caption service for adding captions to videos"""
    
    def __init__(self):
        self.temp_dir = os.getenv('TEMP_DIR', 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info("🎨 PyCaps Service initialized")
    
    def _get_pycaps_template(self, caption_style: CaptionStyle) -> str:
        """Map caption styles to PyCaps templates"""
        template_mapping = {
            CaptionStyle.HYPE: "hype",
            CaptionStyle.VIBRANT: "vibrant",
            CaptionStyle.NEO_MINIMAL: "neo-minimal",
            CaptionStyle.LINE_FOCUS: "line-focus"
        }
        return template_mapping.get(caption_style, "hype")
    
    async def add_captions_to_video(
        self, 
        input_video: str, 
        output_video: str,
        caption_style: CaptionStyle
    ) -> bool:
        """Add captions using PyCaps"""
        try:
            logger.info(f"🎨 Adding {caption_style} captions using PyCaps")
            
            # Get PyCaps template
            template = self._get_pycaps_template(caption_style)
            logger.info(f"🎨 Using PyCaps template: {template}")
            
            # Run PyCaps command
            success = await self._run_pycaps(input_video, output_video, template)
            
            if success:
                logger.info("✅ PyCaps caption application successful")
            else:
                logger.error("❌ PyCaps caption application failed")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ PyCaps service error: {str(e)}")
            return False
    
    async def _run_pycaps(self, input_video: str, output_video: str, template: str) -> bool:
        """Run PyCaps command"""
        try:
            def _process():
                cmd = [
                    'pycaps', 'render',
                    '--input', input_video,
                    '--template', template,
                    '--output', output_video
                ]
                
                cmd_str = ' '.join(cmd)
                logger.info(f"🎬 Running PyCaps command: {cmd_str}")
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    timeout=180  # Reduced to 3 minute timeout
                )
                
                logger.info(f"🎬 PyCaps return code: {result.returncode}")
                if result.stdout:
                    logger.info(f"🎬 PyCaps stdout: {result.stdout}")
                if result.stderr:
                    logger.info(f"🎬 PyCaps stderr: {result.stderr}")
                
                if result.returncode == 0:
                    logger.info("✅ PyCaps completed successfully")
                    return True
                else:
                    logger.error(f"❌ PyCaps failed with code {result.returncode}")
                    logger.error(f"❌ PyCaps stderr: {result.stderr}")
                    return False
            
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, _process),
                timeout=200  # 3.3 minute timeout (slightly more than subprocess timeout)
            )
            
        except asyncio.TimeoutError:
            logger.error(f"❌ PyCaps timed out after 3+ minutes")
            return False
        except Exception as e:
            logger.error(f"❌ Error running PyCaps: {str(e)}")
            return False