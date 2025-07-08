import os
import datetime
import logging
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# Create logger instance
logger = logging.getLogger(__name__)

# Media directory configuration
MEDIA_DIR = "media"

def init_media_dir():
    """Initialize media directory"""
    os.makedirs(MEDIA_DIR, exist_ok=True)
    logger.info(f"📁 Media storage: {os.path.abspath(MEDIA_DIR)}")

async def clean_old_media():
    """Removes media files older than 12 hours from the MEDIA_DIR."""
    logger.info("🧹 Starting old media cleanup...")
    now = datetime.datetime.now()
    twelve_hours_ago = now - datetime.timedelta(hours=12)
    
    deleted_count = 0
    for filename in os.listdir(MEDIA_DIR):
        file_path = os.path.join(MEDIA_DIR, filename)
        if os.path.isfile(file_path):
            try:
                # Get file modification time
                mod_timestamp = os.path.getmtime(file_path)
                mod_datetime = datetime.datetime.fromtimestamp(mod_timestamp)
                
                if mod_datetime < twelve_hours_ago:
                    os.remove(file_path)
                    logger.info(f"🗑️ Deleted old media file: {filename}")
                    deleted_count += 1
            except Exception as e:
                logger.error(f"❌ Error deleting file {filename}: {e}")
    
    logger.info(f"✅ Old media cleanup finished. Deleted {deleted_count} files.")

async def download_media(msg, progress_callback=None):
    """Download media from a message and return the file path"""
    if progress_callback is None:
        progress_callback = lambda current, total: logger.info(
            f"⬇️ Downloading: {current*100/total:.1f}%"
        )
    
    media_path = await msg.download_media(
        file=MEDIA_DIR,
        progress_callback=progress_callback
    )
    return media_path

def determine_media_type(msg):
    """Determine the type of media in a message"""
    if isinstance(msg.media, MessageMediaPhoto):
        return "photo"
    elif isinstance(msg.media, MessageMediaDocument):
        # Get file attributes
        attributes = msg.media.document.attributes
        file_name = next((attr.file_name for attr in attributes if hasattr(attr, 'file_name')), None)
        
        # Determine file type
        mime_type = msg.media.document.mime_type
        
        if mime_type.startswith('video'):
            return "video"
        elif mime_type.startswith('audio'):
            return "audio"
        elif mime_type == 'audio/ogg' or (file_name and file_name.endswith('.ogg')):
            return "voice"
        else:
            return "document"
    else:
        return "unknown"

async def process_single_media(msg, caption=""):
    """Process a single media message and return media info"""
    media_type = determine_media_type(msg)
    
    if media_type == "unknown":
        logger.warning(f"⚠️ Unsupported media type: {type(msg.media).__name__}")
        return None
    
    # Download media
    media_path = await download_media(msg)
    
    if media_type == "photo":
        logger.info(f"✅ Downloaded photo: \033[1;35m{media_path}\033[0m")
    elif media_type == "video":
        logger.info(f"🎥 Downloaded video: \033[1;35m{media_path}\033[0m")
    elif media_type == "audio":
        logger.info(f"🎵 Downloaded audio: \033[1;35m{media_path}\033[0m")
    elif media_type == "voice":
        logger.info(f"🎤 Downloaded voice: \033[1;35m{media_path}\033[0m")
    else:
        logger.warning(f"⚠️ Unsupported document type: {msg.media.document.mime_type}")
    
    return {
        "path": media_path,
        "type": media_type,
        "caption": caption
    }

async def process_media_group(messages):
    """Process a media group (album) and return list of media info"""
    media_group = []
    
    for i, msg in enumerate(messages):
        if msg.media:
            try:
                # Download media
                media_path = await download_media(
                    msg,
                    progress_callback=lambda current, total: logger.info(
                        f"⬇️ Downloading album item {i+1}/{len(messages)}: {current*100/total:.1f}%"
                    )
                )
                logger.info(f"✅ Downloaded album item: \033[1;35m{media_path}\033[0m")
                
                # Determine media type
                media_type = determine_media_type(msg)
                
                media_group.append({
                    "path": media_path,
                    "type": media_type
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to download album item {i+1}: {str(e)}")
        else:
            logger.info(f"📝 Album text message: {msg.text}")
    
    return media_group

def get_media_dir():
    """Get the media directory path"""
    return MEDIA_DIR