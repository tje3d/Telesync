import logging
import asyncio
import os
import sys
import json
import datetime
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

from bale import forward_to_bale, edit_bale_message, delete_bale_message, translate_text, MAX_RETRY_DELAY
from eitaa import forward_to_eitaa, edit_eitaa_message, delete_eitaa_message, get_eitaa_me
from database import (
    init_db, generate_content_hash, store_message_mapping, get_message_mapping,
    get_all_message_mappings, delete_message_mapping, delete_all_message_mappings,
    get_recent_message_mappings, update_message_hash, get_database_path, get_reply_message_id
)
from media import init_media_dir, clean_old_media, process_single_media, process_media_group, determine_media_type

# Load environment variables
load_dotenv()

# Configuration from .env
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_STRING = os.getenv('SESSION_STRING', '')
SOURCES = os.getenv('SOURCES')
BALE_TOKEN = os.getenv('BALE_TOKEN')
BALE_CHAT_IDS = os.getenv('BALE_CHAT_IDS')
EITAA_TOKEN = os.getenv('EITAA_TOKEN')
EITAA_CHAT_IDS = os.getenv('EITAA_CHAT_IDS')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '5'))  # Default 5 seconds
EDIT_DELETE_CHECK_INTERVAL = int(os.getenv('EDIT_DELETE_CHECK_INTERVAL', '30'))  # Default 30 seconds

# Parse multiple Bale chat IDs with optional translation languages
BALE_CHAT_CONFIGS = []
if BALE_CHAT_IDS:
    for item in BALE_CHAT_IDS.split(','):
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1)
            chat_id = parts[0].strip()
            lang = parts[1].strip().lower()
            BALE_CHAT_CONFIGS.append((chat_id, lang))
        else:
            BALE_CHAT_CONFIGS.append((item, None))

# Parse multiple Eitaa chat IDs with optional translation languages
EITAA_CHAT_CONFIGS = []
if EITAA_CHAT_IDS:
    for item in EITAA_CHAT_IDS.split(','):
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1)
            chat_id = parts[0].strip()
            lang = parts[1].strip().lower()
            EITAA_CHAT_CONFIGS.append((chat_id, lang))
        else:
            EITAA_CHAT_CONFIGS.append((item, None))

# Validate configuration
required_vars = [API_ID, API_HASH, SOURCES]
if not all(required_vars):
    print("❌ Missing required environment variables in .env file!")
    print("Please ensure all required variables are set")
    exit(1)

# Check if at least one messaging platform is configured
if not (BALE_TOKEN and BALE_CHAT_CONFIGS) and not (EITAA_TOKEN and EITAA_CHAT_CONFIGS):
    print("❌ No messaging platform configured!")
    print("Please configure either Bale (BALE_TOKEN + BALE_CHAT_IDS) or Eitaa (EITAA_TOKEN + EITAA_CHAT_IDS) or both")
    exit(1)

# Setup colorful console logging
logging.basicConfig(
    level=logging.INFO,
    format='\033[1;34m%(asctime)s\033[0m - \033[1;32m%(levelname)s\033[0m - \033[1;36m%(message)s\033[0m',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Create logger instance
logger = logging.getLogger(__name__)

# Log chat configurations
if BALE_CHAT_CONFIGS:
    logger.info(f"🤖 Forwarding to {len(BALE_CHAT_CONFIGS)} Bale chats:")
    for chat_id, lang in BALE_CHAT_CONFIGS:
        if lang:
            logger.info(f"   - Bale Chat ID: {chat_id} (Translation to: {lang})")
        else:
            logger.info(f"   - Bale Chat ID: {chat_id} (No translation)")

if EITAA_CHAT_CONFIGS:
    logger.info(f"📱 Forwarding to {len(EITAA_CHAT_CONFIGS)} Eitaa chats:")
    for chat_id, lang in EITAA_CHAT_CONFIGS:
        if lang:
            logger.info(f"   - Eitaa Chat ID: {chat_id} (Translation to: {lang})")
        else:
            logger.info(f"   - Eitaa Chat ID: {chat_id} (No translation)")

# Initialize media directory and database
init_media_dir()
init_db()


async def create_session():
    """Interactive session creation"""
    logger.info("Initial setup - generating session string...")
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start()
        session_str = client.session.save()
        logger.info(f"\033[1;33mSESSION_STRING = '{session_str}'\033[0m")
        logger.info("Add this to your .env file and restart")
        return session_str


async def main():
    # Create processing lock inside the event loop context
    processing_lock = asyncio.Lock()
    
    client = TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH
    )

    # Schedule hourly media cleanup
    async def hourly_cleanup_task():
        while True:
            await clean_old_media()
            await asyncio.sleep(60 * 60)  # Wait for 1 hour (3600 seconds)

    # Start the hourly cleanup task in the background
    asyncio.create_task(hourly_cleanup_task())

    # Parse sources
    sources_list = [src.strip() for src in SOURCES.split(',')]
    
    # Track album processing to prevent duplicate handling
    active_albums = set()
    
    # Long polling configuration
    last_message_ids = {}  # Track last seen message ID for each chat
    processed_messages = set()  # Track processed messages to avoid duplicates
    
    async def process_message(event):
        """Process a single message with locking mechanism"""
        async with processing_lock:
            msg = event.message
            
            # Skip if this message is part of an album we're already processing
            if msg.grouped_id and msg.grouped_id in active_albums:
                return
                
            chat = await event.get_chat()
            logger.info(f"📩 New message [ID: {msg.id}] in {chat.title} ({chat.id})")
            
            # Prepare caption (text content)
            caption = msg.text or ""
            
            # Check if this message is a reply
            reply_to_message_id = None
            if msg.reply_to_msg_id:
                logger.info(f"💬 Message is a reply to Telegram message ID: {msg.reply_to_msg_id}")
            
            try:
                # Handle text message
                if not msg.media:
                    logger.info(f"📝 Text message: {caption}")
                    
                    # Create tasks for concurrent forwarding
                    forwarding_tasks = []
                    
                    # Prepare Bale forwarding tasks
                    if BALE_TOKEN and BALE_CHAT_CONFIGS:
                        for chat_id, lang in BALE_CHAT_CONFIGS:
                            # Check if we need to set reply_to_message_id for Bale
                            bale_reply_id = None
                            if msg.reply_to_msg_id:
                                bale_reply_id = get_reply_message_id(msg.reply_to_msg_id, f"bale_{chat_id}")
                                if bale_reply_id:
                                    logger.info(f"🔗 Setting reply to Bale message ID: {bale_reply_id}")
                            
                            # Translate if language specified
                            translated_caption = caption
                            if lang:
                                translated_caption = await translate_text(caption, lang)
                            
                            # Create task for Bale forwarding
                            task = asyncio.create_task(
                                forward_to_bale(
                                    "text", 
                                    BALE_TOKEN,
                                    caption=translated_caption,
                                    chat_id=chat_id,
                                    reply_to_message_id=bale_reply_id
                                )
                            )
                            forwarding_tasks.append(('bale', chat_id, task))
                    
                    # Prepare Eitaa forwarding tasks
                    if EITAA_TOKEN and EITAA_CHAT_CONFIGS:
                        for chat_id, lang in EITAA_CHAT_CONFIGS:
                            # Check if we need to set reply_to_message_id for Eitaa
                            eitaa_reply_id = None
                            if msg.reply_to_msg_id:
                                eitaa_reply_id = get_reply_message_id(msg.reply_to_msg_id, f"eitaa_{chat_id}")
                                if eitaa_reply_id:
                                    logger.info(f"🔗 Setting reply to Eitaa message ID: {eitaa_reply_id}")
                            
                            # Translate if language specified
                            translated_caption = caption
                            if lang:
                                translated_caption = await translate_text(caption, lang)
                            
                            # Create task for Eitaa forwarding
                            task = asyncio.create_task(
                                forward_to_eitaa(
                                    "text", 
                                    EITAA_TOKEN,
                                    caption=translated_caption,
                                    chat_id=chat_id,
                                    reply_to_message_id=eitaa_reply_id
                                )
                            )
                            forwarding_tasks.append(('eitaa', chat_id, task))
                    
                    # Execute all forwarding tasks concurrently
                    if forwarding_tasks:
                        results = await asyncio.gather(*[task for _, _, task in forwarding_tasks], return_exceptions=True)
                        
                        # Process results and store mappings
                        for i, (platform, chat_id, _) in enumerate(forwarding_tasks):
                            result = results[i]
                            if isinstance(result, Exception):
                                logger.error(f"❌ {platform.capitalize()} forwarding failed for chat {chat_id}: {result}")
                                continue
                                
                            if result:  # result contains the message IDs
                                content_hash = generate_content_hash(msg)
                                store_message_mapping(
                                    msg.id, 
                                    f"{platform}_{chat_id}",
                                    result, 
                                    is_album=False,
                                    first_message=True,
                                    content_hash=content_hash,
                                    chat_id=chat.id
                                )
                
                # Handle media messages
                else:
                    # Check if part of media group
                    if msg.grouped_id:
                        logger.info("⏭️ Part of media group - will process as album")
                        return
                    
                    # Process single media using the media module
                    media_info = await process_single_media(msg, caption)
                    if media_info:
                        media_path = media_info["path"]
                        media_type = media_info["type"]
                        
                        # Create tasks for concurrent media forwarding
                        media_forwarding_tasks = []
                        
                        # Prepare Bale media forwarding tasks
                        if BALE_TOKEN and BALE_CHAT_CONFIGS:
                            for chat_id, lang in BALE_CHAT_CONFIGS:
                                # Check if we need to set reply_to_message_id for Bale
                                bale_reply_id = None
                                if msg.reply_to_msg_id:
                                    bale_reply_id = get_reply_message_id(msg.reply_to_msg_id, f"bale_{chat_id}")
                                    if bale_reply_id:
                                        logger.info(f"🔗 Setting reply to Bale message ID: {bale_reply_id}")
                                
                                # Translate if language specified
                                translated_caption = caption
                                if lang:
                                    translated_caption = await translate_text(caption, lang)
                                
                                # Use specific content type for videos and photos, media_group for others
                                if media_type in ["video", "photo"]:
                                    task = asyncio.create_task(
                                        forward_to_bale(
                                            media_type, 
                                            BALE_TOKEN,
                                            caption=translated_caption, 
                                            media_path=media_path,
                                            chat_id=chat_id,
                                            lang=lang,
                                            reply_to_message_id=bale_reply_id
                                        )
                                    )
                                else:
                                    task = asyncio.create_task(
                                        forward_to_bale(
                                            "media_group", 
                                            BALE_TOKEN,
                                            caption=translated_caption, 
                                            media_group=[{"path": media_path, "type": media_type}],
                                            chat_id=chat_id,
                                            lang=lang,
                                            reply_to_message_id=bale_reply_id
                                        )
                                    )
                                media_forwarding_tasks.append(('bale', chat_id, task))
                        
                        # Prepare Eitaa media forwarding tasks
                        if EITAA_TOKEN and EITAA_CHAT_CONFIGS:
                            for chat_id, lang in EITAA_CHAT_CONFIGS:
                                # Check if we need to set reply_to_message_id for Eitaa
                                eitaa_reply_id = None
                                if msg.reply_to_msg_id:
                                    eitaa_reply_id = get_reply_message_id(msg.reply_to_msg_id, f"eitaa_{chat_id}")
                                    if eitaa_reply_id:
                                        logger.info(f"🔗 Setting reply to Eitaa message ID: {eitaa_reply_id}")
                                
                                # Translate if language specified
                                translated_caption = caption
                                if lang:
                                    translated_caption = await translate_text(caption, lang)
                                
                                # Eitaa uses sendFile for all media types
                                task = asyncio.create_task(
                                    forward_to_eitaa(
                                        media_type, 
                                        EITAA_TOKEN,
                                        caption=translated_caption, 
                                        media_path=media_path,
                                        chat_id=chat_id,
                                        lang=lang,
                                        reply_to_message_id=eitaa_reply_id
                                    )
                                )
                                media_forwarding_tasks.append(('eitaa', chat_id, task))
                        
                        # Execute all media forwarding tasks concurrently
                        if media_forwarding_tasks:
                            results = await asyncio.gather(*[task for _, _, task in media_forwarding_tasks], return_exceptions=True)
                            
                            # Process results and store mappings
                            for i, (platform, chat_id, _) in enumerate(media_forwarding_tasks):
                                result = results[i]
                                if isinstance(result, Exception):
                                    logger.error(f"❌ {platform.capitalize()} media forwarding failed for chat {chat_id}: {result}")
                                    continue
                                    
                                if result:  # result contains the message IDs
                                    content_hash = generate_content_hash(msg)
                                    store_message_mapping(
                                        msg.id, 
                                        f"{platform}_{chat_id}",
                                        result, 
                                        is_album=False,
                                        first_message=True,
                                        content_hash=content_hash,
                                        chat_id=chat.id
                                    )
            
            except Exception as e:
                logger.error(f"❌ Processing failed: {str(e)}")

    async def process_album(event):
        """Process media group (album) with mixed media support"""
        # Skip if we're already processing this album
        album_id = event.messages[0].grouped_id
        if album_id in active_albums:
            return
            
        # Mark this album as being processed
        active_albums.add(album_id)
        
        async with processing_lock:
            try:
                chat = await event.get_chat()
                logger.info(f"🖼️ New media group [Count: {len(event.messages)}] in {chat.title} ({chat.id})")
                
                # Get caption from first message
                caption = event.messages[0].text or ""
                
                # Check if the first message is a reply
                first_msg = event.messages[0]
                
                # Process media group using the media module
                media_group = await process_media_group(event.messages)
                
                # Send to all configured chats
                if media_group:
                    # Create tasks for concurrent album forwarding
                    album_forwarding_tasks = []
                    
                    # Prepare Bale album forwarding tasks
                    if BALE_TOKEN and BALE_CHAT_CONFIGS:
                        for chat_id, lang in BALE_CHAT_CONFIGS:
                            # Check if we need to set reply_to_message_id for Bale
                            bale_reply_id = None
                            if first_msg.reply_to_msg_id:
                                bale_reply_id = get_reply_message_id(first_msg.reply_to_msg_id, f"bale_{chat_id}")
                                if bale_reply_id:
                                    logger.info(f"🔗 Setting album reply to Bale message ID: {bale_reply_id}")
                            
                            # Translate caption if needed
                            translated_caption = caption
                            if lang:
                                translated_caption = await translate_text(caption, lang)
                            
                            # Create task for Bale album forwarding
                            task = asyncio.create_task(
                                forward_to_bale(
                                    "media_group", 
                                    BALE_TOKEN,
                                    caption=translated_caption, 
                                    media_group=media_group,
                                    chat_id=chat_id,
                                    reply_to_message_id=bale_reply_id
                                )
                            )
                            album_forwarding_tasks.append(('bale', chat_id, task))
                    
                    # Prepare Eitaa album forwarding tasks
                    if EITAA_TOKEN and EITAA_CHAT_CONFIGS:
                        for chat_id, lang in EITAA_CHAT_CONFIGS:
                            # Check if we need to set reply_to_message_id for Eitaa
                            eitaa_reply_id = None
                            if first_msg.reply_to_msg_id:
                                eitaa_reply_id = get_reply_message_id(first_msg.reply_to_msg_id, f"eitaa_{chat_id}")
                                if eitaa_reply_id:
                                    logger.info(f"🔗 Setting album reply to Eitaa message ID: {eitaa_reply_id}")
                            
                            # Translate caption if needed
                            translated_caption = caption
                            if lang:
                                translated_caption = await translate_text(caption, lang)
                            
                            # Create task for Eitaa album forwarding
                            task = asyncio.create_task(
                                forward_to_eitaa(
                                    "media_group", 
                                    EITAA_TOKEN,
                                    caption=translated_caption, 
                                    media_group=media_group,
                                    chat_id=chat_id,
                                    reply_to_message_id=eitaa_reply_id
                                )
                            )
                            album_forwarding_tasks.append(('eitaa', chat_id, task))
                    
                    # Execute all album forwarding tasks concurrently
                    if album_forwarding_tasks:
                        results = await asyncio.gather(*[task for _, _, task in album_forwarding_tasks], return_exceptions=True)
                        
                        # Process results and store mappings
                        for i, (platform, chat_id, _) in enumerate(album_forwarding_tasks):
                            result = results[i]
                            if isinstance(result, Exception):
                                logger.error(f"❌ {platform.capitalize()} album forwarding failed for chat {chat_id}: {result}")
                                continue
                                
                            if result:  # result contains the message IDs
                                # Store mapping for all messages in the album
                                for j, msg in enumerate(event.messages):
                                    content_hash = generate_content_hash(msg)
                                    store_message_mapping(
                                        msg.id,
                                        f"{platform}_{chat_id}",
                                        result,
                                        is_album=True,
                                        first_message=(j == 0),
                                        content_hash=content_hash,
                                        chat_id=chat.id
                                    )
            except Exception as e:
                logger.error(f"❌ Album processing failed: {str(e)}")
            finally:
                # Remove album from active processing
                active_albums.discard(album_id)

    async def check_for_edits_and_deletes():
        """Periodically check for message edits and deletions"""
        logger.info(f"🔍 Starting edit/delete checker with {EDIT_DELETE_CHECK_INTERVAL}s interval...")
        
        while True:
            try:
                await asyncio.sleep(EDIT_DELETE_CHECK_INTERVAL)
                
                for source in sources_list:
                    try:
                        chat = await client.get_entity(source)
                        chat_id = chat.id
                        
                        # Get recent messages to check for edits
                        messages = await client.get_messages(chat, limit=20)
                        current_messages = {msg.id: msg for msg in messages}
                        
                        # Get stored message mappings for this chat that are less than 1 minute old
                        stored_messages = get_recent_message_mappings(chat_id, minutes_ago=1)
                        
                        # Check for edits
                        for telegram_id, bale_chat_id, bale_ids_json, stored_hash, is_album, first_message in stored_messages:
                            if telegram_id in current_messages:
                                current_msg = current_messages[telegram_id]
                                current_hash = generate_content_hash(current_msg)
                                
                                # Check if content changed
                                if stored_hash and current_hash != stored_hash:
                                    logger.info(f"✏️ Detected edit in message {telegram_id}")
                                    
                                    # Update Bale message
                                    bale_ids = json.loads(bale_ids_json)
                                    caption = current_msg.text or ""
                                    
                                    # Check if this is a Bale or Eitaa chat
                                    if bale_chat_id.startswith("bale_"):
                                        actual_chat_id = bale_chat_id[5:]  # Remove "bale_" prefix
                                        # Find the corresponding Bale chat config
                                        for chat_config_id, lang in BALE_CHAT_CONFIGS:
                                            if chat_config_id == actual_chat_id:
                                                # Only edit if this is the first message of an album or a single message
                                                if not is_album or first_message:
                                                    # Translate if needed
                                                    if lang:
                                                        caption = await translate_text(caption, lang)
                                                    
                                                    # Determine if text-only message
                                                    is_text = not current_msg.media
                                                    
                                                    await edit_bale_message(
                                                        bale_ids[0], 
                                                        caption, 
                                                        actual_chat_id, 
                                                        BALE_TOKEN,
                                                        lang,
                                                        is_text=is_text
                                                    )
                                                break
                                    elif bale_chat_id.startswith("eitaa_"):
                                        actual_chat_id = bale_chat_id[6:]  # Remove "eitaa_" prefix
                                        # Find the corresponding Eitaa chat config
                                        for chat_config_id, lang in EITAA_CHAT_CONFIGS:
                                            if chat_config_id == actual_chat_id:
                                                # Only edit if this is the first message of an album or a single message
                                                if not is_album or first_message:
                                                    # Translate if needed
                                                    if lang:
                                                        caption = await translate_text(caption, lang)
                                                    
                                                    # Determine if text-only message
                                                    is_text = not current_msg.media
                                                    
                                                    await edit_eitaa_message(
                                                        bale_ids[0], 
                                                        caption, 
                                                        actual_chat_id, 
                                                        EITAA_TOKEN,
                                                        lang,
                                                        is_text=is_text
                                                    )
                                                break
                                    
                                    # Update stored hash
                                    update_message_hash(telegram_id, bale_chat_id, current_hash)
                            
                            else:
                                # Message not found - it was deleted
                                logger.info(f"🗑️ Detected deletion of message {telegram_id}")
                                
                                # Delete from appropriate platform
                                bale_ids = json.loads(bale_ids_json)
                                if bale_chat_id.startswith("bale_"):
                                    actual_chat_id = bale_chat_id[5:]  # Remove "bale_" prefix
                                    for bale_id in bale_ids:
                                        await delete_bale_message(bale_id, actual_chat_id, BALE_TOKEN)
                                elif bale_chat_id.startswith("eitaa_"):
                                    actual_chat_id = bale_chat_id[6:]  # Remove "eitaa_" prefix
                                    for eitaa_id in bale_ids:
                                        await delete_eitaa_message(eitaa_id, actual_chat_id, EITAA_TOKEN)
                                
                                # Remove from database
                                delete_message_mapping(telegram_id, bale_chat_id)
                        
                    except Exception as e:
                        logger.error(f"❌ Error checking edits/deletes for {source}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Edit/delete check error: {str(e)}")
                await asyncio.sleep(EDIT_DELETE_CHECK_INTERVAL)

    async def poll_for_messages():
        """Long polling function to check for new messages"""
        logger.info(f"🔄 Starting long polling with {POLL_INTERVAL}s interval...")
        
        # Initialize last message IDs for all chats
        for source in sources_list:
            try:
                chat = await client.get_entity(source)
                # Get the most recent message to start from
                messages = await client.get_messages(chat, limit=1)
                if messages:
                    last_message_ids[chat.id] = messages[0].id
                    logger.info(f"📍 Starting from message ID {messages[0].id} in {chat.title}")
                else:
                    last_message_ids[chat.id] = 0
            except Exception as e:
                logger.error(f"❌ Error initializing chat {source}: {str(e)}")
                last_message_ids[source] = 0
        
        poll_count = 0
        while True:
            try:
                poll_count += 1
                if poll_count % 12 == 1:  # Log every minute (12 * 5s = 60s)
                    logger.info(f"🔍 Polling cycle #{poll_count}...")
                
                for source in sources_list:
                    try:
                        # Get the chat entity
                        chat = await client.get_entity(source)
                        chat_id = chat.id
                        
                        # Get last seen message ID for this chat
                        last_id = last_message_ids.get(chat_id, 0)
                        
                        # Get recent messages (limit to 50 to avoid overwhelming)
                        messages = await client.get_messages(chat, limit=50)
                        
                        # Process new messages in chronological order
                        new_messages = [msg for msg in reversed(messages) if msg.id > last_id]
                        
                        if new_messages:
                            logger.info(f"📥 Found {len(new_messages)} new messages in {chat.title}")
                            
                            # Group messages by grouped_id for album handling
                            albums = {}
                            single_messages = []
                            
                            for msg in new_messages:
                                if msg.grouped_id:
                                    if msg.grouped_id not in albums:
                                        albums[msg.grouped_id] = []
                                    albums[msg.grouped_id].append(msg)
                                else:
                                    single_messages.append(msg)
                            
                            # Process albums
                            for grouped_id, album_messages in albums.items():
                                if grouped_id not in processed_messages:
                                    # Create a mock event object for album processing
                                    class MockAlbumEvent:
                                        def __init__(self, messages):
                                            self.messages = messages
                                        
                                        async def get_chat(self):
                                            return chat
                                    
                                    await process_album(MockAlbumEvent(album_messages))
                                    processed_messages.add(grouped_id)
                            
                            # Process single messages
                            for msg in single_messages:
                                if msg.id not in processed_messages:
                                    # Create a mock event object for message processing
                                    class MockMessageEvent:
                                        def __init__(self, message):
                                            self.message = message
                                        
                                        async def get_chat(self):
                                            return chat
                                    
                                    await process_message(MockMessageEvent(msg))
                                    processed_messages.add(msg.id)
                            
                            # Update last seen message ID
                            last_message_ids[chat_id] = max(msg.id for msg in new_messages)
                            
                            # Clean up old processed messages to prevent memory growth
                            if len(processed_messages) > 10000:
                                # Keep only the most recent 5000 processed messages
                                recent_ids = sorted(processed_messages)[-5000:]
                                processed_messages.clear()
                                processed_messages.update(recent_ids)
                        
                    except Exception as e:
                        logger.error(f"❌ Error polling chat {source}: {str(e)}")
                        continue
                
                # Wait before next poll
                await asyncio.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt signal, stopping polling...")
                break
            except Exception as e:
                logger.error(f"❌ Polling error: {str(e)}")
                await asyncio.sleep(POLL_INTERVAL * 2)  # Wait longer on error

    try:
        await client.start()
        
        # Initialize last_message_ids for each chat
        for source in sources_list:
            try:
                chat = await client.get_entity(source)
                async for message in client.iter_messages(chat, limit=1):
                    last_message_ids[chat.id] = message.id
                    logger.info(f"Initialized last message ID for {chat.title}: {message.id}")
                    break
                else:
                    last_message_ids[chat.id] = 0
                    logger.info(f"No messages found in {chat.title}, starting from 0")
            except Exception as e:
                logger.error(f"Error initializing chat {source}: {e}")
                last_message_ids[source] = 0
        
        logger.info(f"👀 Long polling started for {len(sources_list)} sources:")
        for source in sources_list:
            logger.info(f"   - {source}")
        
        # Log platform configurations
        if BALE_CHAT_CONFIGS:
            logger.info(f"🤖 Bale forwarding configured to {len(BALE_CHAT_CONFIGS)} chats")
        if EITAA_CHAT_CONFIGS:
            logger.info(f"📱 Eitaa forwarding configured to {len(EITAA_CHAT_CONFIGS)} chats")
        logger.info(f"🔄 Retry configured: 2 hours max, {MAX_RETRY_DELAY}s max delay")
        logger.info(f"💾 Message mapping database: {get_database_path()}")
        logger.info(f"⏱️ Polling interval: {POLL_INTERVAL} seconds")
        logger.info(f"🔍 Edit/delete checks will run every {EDIT_DELETE_CHECK_INTERVAL}s")
        
        logger.info(f"Starting long polling with {POLL_INTERVAL}s interval...")
        
        # Start both polling tasks concurrently
        await asyncio.gather(
            poll_for_messages(),
            check_for_edits_and_deletes()
        )
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down gracefully...")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        await client.disconnect()
        logger.info("Client disconnected")


if __name__ == '__main__':
    if not SESSION_STRING:
        logger.info("🔑 No session string found. Creating new session...")
        new_session = asyncio.run(create_session())
        logger.info(f"🔒 Add this to your .env file as SESSION_STRING: \033[1;33m{new_session}\033[0m")
    else:
        logger.info("🚀 Starting monitoring...")
        asyncio.run(main())