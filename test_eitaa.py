#!/usr/bin/env python3
"""
Test script for Eitaa API integration
"""

import asyncio
import os
from dotenv import load_dotenv
from eitaa import get_eitaa_me, forward_to_eitaa

# Load environment variables
load_dotenv()

async def test_eitaa():
    """Test Eitaa API functionality"""
    
    # Get configuration
    eitaa_token = os.getenv('EITAA_TOKEN')
    eitaa_chat_ids = os.getenv('EITAA_CHAT_IDS')
    
    if not eitaa_token:
        print("❌ EITAA_TOKEN not found in .env file")
        return
    
    if not eitaa_chat_ids:
        print("❌ EITAA_CHAT_IDS not found in .env file")
        return
    
    # Parse chat IDs
    chat_configs = []
    for item in eitaa_chat_ids.split(','):
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1)
            chat_id = parts[0].strip()
            lang = parts[1].strip().lower()
            chat_configs.append((chat_id, lang))
        else:
            chat_configs.append((item, None))
    
    print(f"🧪 Testing Eitaa API with token: {eitaa_token[:10]}...")
    print(f"📱 Chat configurations: {chat_configs}")
    
    # Test 1: Get bot info
    print("\n1️⃣ Testing getMe method...")
    bot_info = await get_eitaa_me(eitaa_token)
    if bot_info:
        print(f"✅ Bot info retrieved: {bot_info}")
    else:
        print("❌ Failed to get bot info")
        return
    
    # Test 2: Send text message
    print("\n2️⃣ Testing sendMessage method...")
    for chat_id, lang in chat_configs:
        print(f"📤 Sending test message to chat {chat_id} (lang: {lang})")
        
        test_message = "🧪 Test message from TeleSync-Py Eitaa integration"
        
        result = await forward_to_eitaa(
            "text",
            eitaa_token,
            caption=test_message,
            chat_id=chat_id,
            lang=lang
        )
        
        if result:
            print(f"✅ Message sent successfully. Message IDs: {result}")
        else:
            print(f"❌ Failed to send message to chat {chat_id}")
    
    print("\n🎉 Eitaa API test completed!")

if __name__ == "__main__":
    print("🚀 Starting Eitaa API test...")
    asyncio.run(test_eitaa())