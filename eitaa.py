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

def get_eitaa_api_url(method, eitaa_token):
    """Get Eitaa API URL for a specific method"""
    return f"https://eitaayar.ir/api/{eitaa_token}/{method}"

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
                # Form data request for file uploads
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

async def forward_to_eitaa(content_type, eitaa_token, caption=None, media_path=None, media_group=None, 
                          chat_id=None, lang=None, reply_to_message_id=None):
    """Forward content to Eitaa Messenger for a specific chat"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            # Translate caption if needed
            if lang and caption:
                caption = await translate_text(caption, lang)
            
            if content_type == "text":
                payload = {
                    "chat_id": chat_id,
                    "text": caption
                }
                if reply_to_message_id:
                    payload["reply_to_message_id"] = reply_to_message_id
                send_url = get_eitaa_api_url("sendMessage", eitaa_token)
                response = await send_with_retry(session, send_url, payload=payload)
                if response and response.get("ok"):
                    eitaa_id = response['result']['message_id']
                    logger.info(f"✅ Text forwarded to Eitaa chat {chat_id}")
                    return [eitaa_id]
                else:
                    logger.error(f"❌ Eitaa text send failed for chat {chat_id}: {response}")
                    return []
            
            elif content_type in ["photo", "video", "document"] or content_type == "media_group":
                # For single media or media groups, use sendFile method
                if content_type == "media_group":
                    # For media groups, send each file separately as Eitaa doesn't support media groups
                    eitaa_ids = []
                    for i, item in enumerate(media_group):
                        path = item['path']
                        
                        form_data = aiohttp.FormData()
                        form_data.add_field('chat_id', chat_id)
                        form_data.add_field(
                            'file', 
                            open(path, 'rb'),
                            filename=os.path.basename(path)
                        )
                        # Add caption only to the first file
                        if i == 0 and caption:
                            form_data.add_field('caption', caption)
                        # Add reply_to_message_id only to the first file
                        if i == 0 and reply_to_message_id:
                            form_data.add_field('reply_to_message_id', str(reply_to_message_id))
                        
                        send_url = get_eitaa_api_url("sendFile", eitaa_token)
                        response = await send_with_retry(session, send_url, files=form_data)
                        if response and response.get("ok"):
                            eitaa_id = response['result']['message_id']
                            eitaa_ids.append(eitaa_id)
                            logger.info(f"✅ Media file {i+1}/{len(media_group)} forwarded to Eitaa chat {chat_id}")
                        else:
                            logger.error(f"❌ Eitaa media file {i+1} send failed for chat {chat_id}: {response}")
                    
                    if eitaa_ids:
                        logger.info(f"✅ Media group ({len(eitaa_ids)} files) forwarded to Eitaa chat {chat_id}")
                    return eitaa_ids
                else:
                    # Single media file
                    form_data = aiohttp.FormData()
                    form_data.add_field('chat_id', chat_id)
                    form_data.add_field(
                        'file', 
                        open(media_path, 'rb'),
                        filename=os.path.basename(media_path)
                    )
                    if caption:
                        form_data.add_field('caption', caption)
                    if reply_to_message_id:
                        form_data.add_field('reply_to_message_id', str(reply_to_message_id))
                    
                    send_url = get_eitaa_api_url("sendFile", eitaa_token)
                    response = await send_with_retry(session, send_url, files=form_data)
                    if response and response.get("ok"):
                        eitaa_id = response['result']['message_id']
                        logger.info(f"✅ {content_type.capitalize()} forwarded to Eitaa chat {chat_id}")
                        return [eitaa_id]
                    else:
                        logger.error(f"❌ Eitaa {content_type} send failed for chat {chat_id}: {response}")
                        return []
    
    except Exception as e:
        logger.error(f"❌ Eitaa forwarding error for chat {chat_id}: {str(e)}")
        return []

async def edit_eitaa_message(eitaa_id, new_content, chat_id, eitaa_token, lang=None, is_text=False):
    """Edit an existing Eitaa message - Note: Eitaa API doesn't support message editing"""
    logger.warning(f"⚠️ Eitaa API doesn't support message editing. Cannot edit message {eitaa_id} in chat {chat_id}")
    return False

async def delete_eitaa_message(eitaa_id, chat_id, eitaa_token):
    """Delete an Eitaa message - Note: Eitaa API doesn't support message deletion"""
    logger.warning(f"⚠️ Eitaa API doesn't support message deletion. Cannot delete message {eitaa_id} in chat {chat_id}")
    return False

async def get_eitaa_me(eitaa_token):
    """Get information about the Eitaa bot using getMe method"""
    try:
        async with aiohttp.ClientSession() as session:
            url = get_eitaa_api_url("getMe", eitaa_token)
            response = await send_with_retry(session, url, payload={})
            if response and response.get("ok"):
                logger.info(f"✅ Eitaa bot info retrieved: {response['result']}")
                return response['result']
            else:
                logger.error(f"❌ Failed to get Eitaa bot info: {response}")
                return None
    except Exception as e:
        logger.error(f"❌ Error getting Eitaa bot info: {str(e)}")
        return None