import logging
import asyncio
import os
import sys
import random
import time
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import aiohttp

# Load environment variables
load_dotenv()

# Configuration from .env
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_STRING = os.getenv('SESSION_STRING', '')
SOURCES = os.getenv('SOURCES')
BALE_TOKEN = os.getenv('BALE_TOKEN')
BALE_CHAT_ID = os.getenv('BALE_CHAT_ID')

# Validate configuration
required_vars = [API_ID, API_HASH, SOURCES, BALE_TOKEN, BALE_CHAT_ID]
if not all(required_vars):
    print("❌ Missing required environment variables in .env file!")
    print("Please ensure all required variables are set")
    exit(1)

# Setup colorful console logging
logging.basicConfig(
    level=logging.INFO,
    format='\033[1;34m%(asctime)s\033[0m - \033[1;32m%(levelname)s\033[0m - \033[1;36m%(message)s\033[0m',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Create logger instance
logger = logging.getLogger(__name__)

# Create media directory if not exists
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)
logger.info(f"📁 Media storage: {os.path.abspath(MEDIA_DIR)}")

# Bale API endpoints
BALE_API_URL = "https://tapi.bale.ai/bot{token}/{method}"
BALE_SEND_MESSAGE_URL = BALE_API_URL.format(token=BALE_TOKEN, method="sendMessage")
BALE_SEND_PHOTO_URL = BALE_API_URL.format(token=BALE_TOKEN, method="sendPhoto")
BALE_SEND_MEDIA_GROUP_URL = BALE_API_URL.format(token=BALE_TOKEN, method="sendMediaGroup")
BALE_SEND_VIDEO_URL = BALE_API_URL.format(token=BALE_TOKEN, method="sendVideo")
BALE_SEND_AUDIO_URL = BALE_API_URL.format(token=BALE_TOKEN, method="sendAudio")
BALE_SEND_VOICE_URL = BALE_API_URL.format(token=BALE_TOKEN, method="sendVoice")

# Retry configuration
MAX_RETRY_TIME = 2 * 60 * 60  # 2 hours in seconds
MAX_RETRY_DELAY = 60  # Max delay between retries in seconds
INITIAL_RETRY_DELAY = 1  # Initial retry delay in seconds
RETRY_EXPONENT = 2  # Exponential backoff factor

async def create_session():
    """Interactive session creation"""
    logger.info("Initial setup - generating session string...")
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start()
        session_str = client.session.save()
        logger.info(f"\033[1;33mSESSION_STRING = '{session_str}'\033[0m")
        logger.info("Add this to your .env file and restart")
        return session_str

async def send_with_retry(session, url, payload=None, files=None):
    """Send request with retry mechanism for server errors and network issues"""
    start_time = time.monotonic()
    attempt = 0
    delay = INITIAL_RETRY_DELAY
    
    while time.monotonic() - start_time < MAX_RETRY_TIME:
        attempt += 1
        try:
            if files:
                # Form data request
                async with session.post(url, data=files) as resp:
                    if resp.status >= 500:
                        error = f"Server error ({resp.status})"
                        raise aiohttp.ClientError(error)
                    response = await resp.json()
            else:
                # JSON payload request
                async with session.post(url, json=payload) as resp:
                    if resp.status >= 500:
                        error = f"Server error ({resp.status})"
                        raise aiohttp.ClientError(error)
                    response = await resp.json()
            
            return response
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # Calculate next delay with jitter
            jitter = random.uniform(0.5, 1.5)
            actual_delay = min(delay * jitter, MAX_RETRY_DELAY)
            
            logger.warning(
                f"⚠️ Attempt {attempt} failed: {str(e)}. "
                f"Retrying in {actual_delay:.1f} seconds..."
            )
            
            await asyncio.sleep(actual_delay)
            delay = min(delay * RETRY_EXPONENT, MAX_RETRY_DELAY)
        except Exception as e:
            logger.error(f"❌ Non-retryable error: {str(e)}")
            return None
    
    logger.error(f"🔥 Forwarding failed after {attempt} attempts over {MAX_RETRY_TIME/60:.1f} minutes")
    return None

async def forward_to_bale(content_type, caption=None, media_path=None, media_group=None):
    """Forward content to Bale Messenger with robust retry mechanism"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            if content_type == "text":
                payload = {
                    "chat_id": BALE_CHAT_ID,
                    "text": caption,
                    "parse_mode": "HTML"
                }
                response = await send_with_retry(session, BALE_SEND_MESSAGE_URL, payload=payload)
                if response and response.get("ok"):
                    logger.info("✅ Text forwarded to Bale")
                else:
                    logger.error(f"❌ Bale text send failed: {response}")
            
            elif content_type == "photo":
                with open(media_path, 'rb') as file:
                    form_data = aiohttp.FormData()
                    form_data.add_field('chat_id', BALE_CHAT_ID)
                    form_data.add_field('photo', file, filename=os.path.basename(media_path))
                    if caption:
                        form_data.add_field('caption', caption)
                        form_data.add_field('parse_mode', 'HTML')
                    
                    response = await send_with_retry(session, BALE_SEND_PHOTO_URL, files=form_data)
                    if response and response.get("ok"):
                        logger.info("✅ Photo forwarded to Bale")
                    else:
                        logger.error(f"❌ Bale photo send failed: {response}")
            
            elif content_type == "media_group":
                media_data = []
                form_data = aiohttp.FormData()
                
                for i, path in enumerate(media_group):
                    with open(path, 'rb') as file:
                        media_type = "photo"
                        media_dict = {
                            "type": media_type,
                            "media": f"attach://media_{i}",
                            "parse_mode": "HTML"
                        }
                        if i == 0 and caption:
                            media_dict["caption"] = caption
                        media_data.append(media_dict)
                        form_data.add_field(f'media_{i}', file, filename=os.path.basename(path))
                
                form_data.add_field('chat_id', BALE_CHAT_ID)
                form_data.add_field('media', str(media_data).replace("'", '"'))
                
                response = await send_with_retry(session, BALE_SEND_MEDIA_GROUP_URL, files=form_data)
                if response and response.get("ok"):
                    logger.info("✅ Media group forwarded to Bale")
                else:
                    logger.error(f"❌ Bale media group send failed: {response}")
            
            elif content_type == "video":
                with open(media_path, 'rb') as file:
                    form_data = aiohttp.FormData()
                    form_data.add_field('chat_id', BALE_CHAT_ID)
                    form_data.add_field('video', file, filename=os.path.basename(media_path))
                    if caption:
                        form_data.add_field('caption', caption)
                        form_data.add_field('parse_mode', 'HTML')
                    
                    response = await send_with_retry(session, BALE_SEND_VIDEO_URL, files=form_data)
                    if response and response.get("ok"):
                        logger.info("✅ Video forwarded to Bale")
                    else:
                        logger.error(f"❌ Bale video send failed: {response}")
            
            elif content_type == "audio":
                with open(media_path, 'rb') as file:
                    form_data = aiohttp.FormData()
                    form_data.add_field('chat_id', BALE_CHAT_ID)
                    form_data.add_field('audio', file, filename=os.path.basename(media_path))
                    if caption:
                        form_data.add_field('caption', caption)
                        form_data.add_field('parse_mode', 'HTML')
                    
                    response = await send_with_retry(session, BALE_SEND_AUDIO_URL, files=form_data)
                    if response and response.get("ok"):
                        logger.info("✅ Audio forwarded to Bale")
                    else:
                        logger.error(f"❌ Bale audio send failed: {response}")
            
            elif content_type == "voice":
                with open(media_path, 'rb') as file:
                    form_data = aiohttp.FormData()
                    form_data.add_field('chat_id', BALE_CHAT_ID)
                    form_data.add_field('voice', file, filename=os.path.basename(media_path))
                    
                    response = await send_with_retry(session, BALE_SEND_VOICE_URL, files=form_data)
                    if response and response.get("ok"):
                        logger.info("✅ Voice forwarded to Bale")
                    else:
                        logger.error(f"❌ Bale voice send failed: {response}")
    
    except Exception as e:
        logger.error(f"❌ Bale forwarding error: {str(e)}")

async def main():
    # Create processing lock inside the event loop context
    processing_lock = asyncio.Lock()
    
    client = TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH
    )

    # Parse sources
    sources_list = [src.strip() for src in SOURCES.split(',')]
    
    async def process_message(event):
        """Process a single message with locking mechanism"""
        async with processing_lock:
            msg = event.message
            chat = await event.get_chat()
            logger.info(f"📩 New message [ID: {msg.id}] in {chat.title} ({chat.id})")
            
            # Prepare caption (text content)
            caption = msg.text or ""
            
            try:
                # Handle text message
                if not msg.media:
                    logger.info(f"📝 Text message: {caption}")
                    await forward_to_bale("text", caption=caption)
                
                # Handle media messages
                else:
                    # Handle photo (single or album)
                    if isinstance(msg.media, MessageMediaPhoto):
                        # Check if part of media group
                        if msg.grouped_id:
                            logger.info("⏭️ Part of media group - will process as album")
                            return
                        
                        # Single photo
                        media_path = await msg.download_media(
                            file=MEDIA_DIR,
                            progress_callback=lambda current, total: logger.info(
                                f"⬇️ Downloading: {current*100/total:.1f}%"
                            )
                        )
                        logger.info(f"✅ Downloaded photo: \033[1;35m{media_path}\033[0m")
                        await forward_to_bale("photo", caption=caption, media_path=media_path)
                    
                    # Handle documents (could be video, audio, voice, etc.)
                    elif isinstance(msg.media, MessageMediaDocument):
                        # Get file attributes
                        attributes = msg.media.document.attributes
                        file_name = next((attr.file_name for attr in attributes if hasattr(attr, 'file_name')), None)
                        
                        # Download the file
                        media_path = await msg.download_media(
                            file=MEDIA_DIR,
                            progress_callback=lambda current, total: logger.info(
                                f"⬇️ Downloading: {current*100/total:.1f}%"
                            )
                        )
                        
                        # Determine file type
                        mime_type = msg.media.document.mime_type
                        if mime_type.startswith('video'):
                            logger.info(f"🎥 Downloaded video: \033[1;35m{media_path}\033[0m")
                            await forward_to_bale("video", caption=caption, media_path=media_path)
                        elif mime_type.startswith('audio'):
                            logger.info(f"🎵 Downloaded audio: \033[1;35m{media_path}\033[0m")
                            await forward_to_bale("audio", caption=caption, media_path=media_path)
                        elif mime_type == 'audio/ogg' or (file_name and file_name.endswith('.ogg')):
                            logger.info(f"🎤 Downloaded voice: \033[1;35m{media_path}\033[0m")
                            await forward_to_bale("voice", media_path=media_path)
                        else:
                            logger.warning(f"⚠️ Unsupported document type: {mime_type}")
                    else:
                        logger.warning(f"⚠️ Unsupported media type: {type(msg.media).__name__}")
            
            except Exception as e:
                logger.error(f"❌ Processing failed: {str(e)}")

    async def process_album(event):
        """Process media group (album)"""
        async with processing_lock:
            chat = await event.get_chat()
            logger.info(f"🖼️ New media group [Count: {len(event.messages)}] in {chat.title} ({chat.id})")
            
            # Get caption from first message
            caption = event.messages[0].text or ""
            
            try:
                # Download all media in the group
                media_paths = []
                for msg in event.messages:
                    if msg.media and isinstance(msg.media, MessageMediaPhoto):
                        media_path = await msg.download_media(
                            file=MEDIA_DIR,
                            progress_callback=lambda current, total: logger.info(
                                f"⬇️ Downloading album item: {current*100/total:.1f}%"
                            )
                        )
                        media_paths.append(media_path)
                        logger.info(f"✅ Downloaded album photo: \033[1;35m{media_path}\033[0m")
                
                if media_paths:
                    await forward_to_bale("media_group", caption=caption, media_group=media_paths)
                else:
                    logger.warning("⚠️ No valid photos found in media group")
            
            except Exception as e:
                logger.error(f"❌ Album processing failed: {str(e)}")

    # Register handlers
    @client.on(events.Album(chats=sources_list))
    async def album_handler(event):
        await process_album(event)
    
    @client.on(events.NewMessage(chats=sources_list))
    async def message_handler(event):
        # Skip if part of an album (handled separately)
        if event.message.grouped_id:
            return
        await process_message(event)

    await client.start()
    logger.info(f"👀 Monitoring started for {len(sources_list)} sources:")
    for source in sources_list:
        logger.info(f"   - {source}")
    
    # Log Bale configuration
    logger.info(f"🤖 Bale forwarding configured to chat: {BALE_CHAT_ID}")
    logger.info(f"🔄 Retry configured: 2 hours max, {MAX_RETRY_DELAY}s max delay")
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    if not SESSION_STRING:
        logger.info("🔑 No session string found. Creating new session...")
        new_session = asyncio.run(create_session())
        logger.info(f"🔒 Add this to your .env file as SESSION_STRING: \033[1;33m{new_session}\033[0m")
    else:
        logger.info("🚀 Starting monitoring...")
        asyncio.run(main())