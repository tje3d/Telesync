import logging
import asyncio
import os
import json
import random
import time
import aiohttp
from googletrans import Translator

# Create logger instance for this module
logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRY_TIME = 5 * 60  # 5 minutes in seconds
MAX_RETRY_DELAY = 30  # Max delay between retries in seconds
INITIAL_RETRY_DELAY = 1  # Initial retry delay in seconds
RETRY_EXPONENT = 2  # Exponential backoff factor

def get_bale_api_url(method, bale_token):
    """Get Bale API URL for a specific method"""
    return f"https://tapi.bale.ai/bot{bale_token}/{method}"

async def translate_text(text, dest_lang):
    """Translate text using Google Translate (without API key)"""
    if not text or not dest_lang:
        return text
        
    try:
        translator = Translator()
        translation = translator.translate(text, dest=dest_lang)
        return translation.text
    except Exception as e:
        logger.error(f"❌ Translation failed: {str(e)}")
        return text  # Return original text on failure

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

async def forward_to_bale(content_type, bale_token, caption=None, media_path=None, media_group=None, 
                          chat_id=None, lang=None, reply_to_message_id=None):
    """Forward content to Bale Messenger for a specific chat"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            # Translate caption if needed
            if lang and caption:
                caption = await translate_text(caption, lang)
            
            if content_type == "text":
                payload = {
                    "chat_id": chat_id,
                    "text": caption,
                    "parse_mode": "Markdown"
                }
                if reply_to_message_id:
                    payload["reply_to_message_id"] = reply_to_message_id
                send_url = get_bale_api_url("sendMessage", bale_token)
                response = await send_with_retry(session, send_url, payload=payload)
                if response and response.get("ok"):
                    bale_id = response['result']['message_id']
                    logger.info(f"✅ Text forwarded to Bale chat {chat_id}")
                    return [bale_id]
                else:
                    logger.error(f"❌ Bale text send failed for chat {chat_id}: {response}")
                    return []
            
            elif content_type == "photo":
                form_data = aiohttp.FormData()
                form_data.add_field('chat_id', chat_id)
                form_data.add_field(
                    'photo', 
                    open(media_path, 'rb'),
                    filename=os.path.basename(media_path)
                )
                if caption:
                    form_data.add_field('caption', caption)
                    form_data.add_field('parse_mode', 'Markdown')
                if reply_to_message_id:
                    form_data.add_field('reply_to_message_id', str(reply_to_message_id))
                
                send_url = get_bale_api_url("sendPhoto", bale_token)
                response = await send_with_retry(session, send_url, files=form_data)
                if response and response.get("ok"):
                    bale_id = response['result']['message_id']
                    logger.info(f"✅ Photo forwarded to Bale chat {chat_id}")
                    return [bale_id]
                else:
                    logger.error(f"❌ Bale photo send failed for chat {chat_id}: {response}")
                    return []
            
            elif content_type == "video":
                form_data = aiohttp.FormData()
                form_data.add_field('chat_id', chat_id)
                form_data.add_field(
                    'video', 
                    open(media_path, 'rb'),
                    filename=os.path.basename(media_path)
                )
                if caption:
                    form_data.add_field('caption', caption)
                    form_data.add_field('parse_mode', 'Markdown')
                if reply_to_message_id:
                    form_data.add_field('reply_to_message_id', str(reply_to_message_id))
                form_data.add_field('supports_streaming', 'true')
                
                send_url = get_bale_api_url("sendVideo", bale_token)
                response = await send_with_retry(session, send_url, files=form_data)
                if response and response.get("ok"):
                    bale_id = response['result']['message_id']
                    logger.info(f"✅ Video forwarded to Bale chat {chat_id}")
                    return [bale_id]
                else:
                    logger.error(f"❌ Bale video send failed for chat {chat_id}: {response}")
                    return []
            
            elif content_type == "media_group":
                media_data = []
                form_data = aiohttp.FormData()
                
                for i, item in enumerate(media_group):
                    path = item['path']
                    media_type = item['type']
                    
                    # Add file to form data
                    form_data.add_field(
                        f'media_{i}', 
                        open(path, 'rb'),
                        filename=os.path.basename(path)
                    )
                    
                    # Create media object
                    media_dict = {
                        "type": media_type,
                        "media": f"attach://media_{i}",
                        "parse_mode": "Markdown"
                    }
                    
                    # Add caption to first item
                    if i == 0 and caption:
                        media_dict["caption"] = caption
                    
                    # Add additional parameters for video
                    if media_type == "video":
                        media_dict["supports_streaming"] = True
                    
                    media_data.append(media_dict)
                
                # Add chat ID and media array
                form_data.add_field('chat_id', chat_id)
                form_data.add_field('media', json.dumps(media_data))
                if reply_to_message_id:
                    form_data.add_field('reply_to_message_id', str(reply_to_message_id))
                
                send_url = get_bale_api_url("sendMediaGroup", bale_token)
                response = await send_with_retry(session, send_url, files=form_data)
                if response and response.get("ok"):
                    bale_ids = [msg['message_id'] for msg in response['result']]
                    logger.info(f"✅ Media group forwarded to Bale chat {chat_id}")
                    return bale_ids
                else:
                    logger.error(f"❌ Bale media group send failed for chat {chat_id}: {response}")
                    return []
    
    except Exception as e:
        logger.error(f"❌ Bale forwarding error for chat {chat_id}: {str(e)}")
        return []

async def edit_bale_message(bale_id, new_content, chat_id, bale_token, lang=None, is_text=False):
    """Edit an existing Bale message text or caption for a specific chat"""
    try:
        async with aiohttp.ClientSession() as session:
            # Translate content if needed
            if lang and new_content:
                new_content = await translate_text(new_content, lang)

            # Choose appropriate endpoint based on message type
            if is_text:
                url = get_bale_api_url("editMessageText", bale_token)
                payload_key = "text"
            else:
                url = get_bale_api_url("editMessageCaption", bale_token)
                payload_key = "caption"
            
            payload = {
                "chat_id": chat_id,
                "message_id": bale_id,
                payload_key: new_content,
                "parse_mode": "Markdown"
            }
            response = await send_with_retry(session, url, payload=payload)
            if response and response.get("ok"):
                logger.info(f"✏️ Edited Bale message {bale_id} in chat {chat_id}")
                return True
            else:
                logger.error(f"❌ Bale edit failed for chat {chat_id}: {response}")
                return False
    except Exception as e:
        logger.error(f"❌ Bale edit error for chat {chat_id}: {str(e)}")
        return False

async def delete_bale_message(bale_id, chat_id, bale_token):
    """Delete a Bale message in a specific chat"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "chat_id": chat_id,
                "message_id": bale_id
            }
            url = get_bale_api_url("deleteMessage", bale_token)
            response = await send_with_retry(session, url, payload=payload)
            if response and response.get("ok"):
                logger.info(f"🗑️ Deleted Bale message {bale_id} in chat {chat_id}")
                return True
            else:
                logger.error(f"❌ Bale delete failed for chat {chat_id}: {response}")
                return False
    except Exception as e:
        logger.error(f"❌ Bale delete error for chat {chat_id}: {str(e)}")
        return False