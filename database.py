import sqlite3
import json
import hashlib
import datetime
import os

# Database configuration
DB_FILE = "message_mappings.db"

def init_db():
    """Initialize the database and create tables if they don't exist"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (telegram_id INTEGER,
                  bale_chat_id TEXT,
                  bale_ids TEXT,
                  is_album BOOLEAN,
                  first_message BOOLEAN,
                  content_hash TEXT,
                  last_check TIMESTAMP,
                  chat_id INTEGER,
                  PRIMARY KEY (telegram_id, bale_chat_id))''')
    
    # Add new columns to existing tables if they don't exist
    try:
        c.execute('ALTER TABLE messages ADD COLUMN content_hash TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE messages ADD COLUMN last_check TIMESTAMP')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        c.execute('ALTER TABLE messages ADD COLUMN chat_id INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

def generate_content_hash(message):
    """Generate a hash of message content for change detection"""
    content = f"{message.text or ''}{message.media.__class__.__name__ if message.media else ''}"
    return hashlib.md5(content.encode()).hexdigest()

def store_message_mapping(telegram_id, bale_chat_id, bale_ids, is_album=False, first_message=False, 
                         content_hash=None, chat_id=None):
    """Store message mapping in database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    bale_ids_json = json.dumps(bale_ids)
    current_time = datetime.datetime.now().isoformat()
    c.execute('''INSERT OR REPLACE INTO messages 
                 (telegram_id, bale_chat_id, bale_ids, is_album, first_message, content_hash, last_check, chat_id) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (telegram_id, bale_chat_id, bale_ids_json, is_album, first_message, content_hash, current_time, chat_id))
    conn.commit()
    conn.close()

def get_message_mapping(telegram_id, bale_chat_id):
    """Get message mapping from database for specific chat"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT bale_ids, is_album, first_message 
                 FROM messages WHERE telegram_id = ? AND bale_chat_id = ?''', 
              (telegram_id, bale_chat_id))
    row = c.fetchone()
    conn.close()
    
    if row:
        bale_ids = json.loads(row[0])
        return bale_ids, row[1], row[2]
    return None, None, None

def get_all_message_mappings(telegram_id):
    """Get all message mappings for a Telegram message ID"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT bale_chat_id, bale_ids, is_album, first_message 
                 FROM messages WHERE telegram_id = ?''', (telegram_id,))
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        bale_ids = json.loads(row[1])
        results.append((row[0], bale_ids, row[2], row[3]))
    return results

def delete_message_mapping(telegram_id, bale_chat_id):
    """Delete specific message mapping from database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''DELETE FROM messages WHERE telegram_id = ? AND bale_chat_id = ?''', 
              (telegram_id, bale_chat_id))
    conn.commit()
    conn.close()

def delete_all_message_mappings(telegram_id):
    """Delete all mappings for a Telegram message ID"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''DELETE FROM messages WHERE telegram_id = ?''', (telegram_id,))
    conn.commit()
    conn.close()

def get_recent_message_mappings(chat_id, minutes_ago=1):
    """Get stored message mappings for a chat that are less than specified minutes old"""
    time_threshold = datetime.datetime.now() - datetime.timedelta(minutes=minutes_ago)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT telegram_id, bale_chat_id, bale_ids, content_hash, is_album, first_message 
                 FROM messages WHERE chat_id = ? AND last_check > ?''', 
              (chat_id, time_threshold.isoformat()))
    stored_messages = c.fetchall()
    conn.close()
    return stored_messages

def update_message_hash(telegram_id, bale_chat_id, new_hash):
    """Update the content hash and last_check timestamp for a message"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''UPDATE messages SET content_hash = ?, last_check = ? 
                 WHERE telegram_id = ? AND bale_chat_id = ?''',
              (new_hash, datetime.datetime.now().isoformat(), telegram_id, bale_chat_id))
    conn.commit()
    conn.close()

def get_database_path():
    """Get the absolute path to the database file"""
    return os.path.abspath(DB_FILE)

def get_reply_message_id(telegram_reply_id, bale_chat_id):
    """Get the Bale message ID for a Telegram message that was replied to"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT bale_ids FROM messages 
                 WHERE telegram_id = ? AND bale_chat_id = ?''', 
              (telegram_reply_id, bale_chat_id))
    row = c.fetchone()
    conn.close()
    
    if row:
        bale_ids = json.loads(row[0])
        # Return the first message ID (for albums, this is the first message)
        return bale_ids[0] if bale_ids else None
    return None