# Telesync 🚀

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](Dockerfile)

A powerful, feature-rich Telegram to Bale Messenger forwarding bot with real-time synchronization, automatic translation, and intelligent media handling.

## ✨ Features

### 🔄 **Real-time Message Forwarding**

- Instant forwarding from Telegram channels/groups to Bale Messenger
- Support for multiple source channels and destination chats
- Configurable polling intervals for optimal performance

### 🌍 **Multi-language Support**

- Automatic translation using Google Translate
- Per-chat language configuration
- Preserves original formatting and structure

### 📱 **Comprehensive Media Support**

- **Photos**: Single images and photo albums
- **Videos**: All video formats with streaming support
- **Documents**: Files, PDFs, and other document types
- **Audio**: Music files and voice messages
- **Media Groups**: Intelligent album handling with proper grouping

### 🔧 **Advanced Message Management**

- **Edit Detection**: Automatically updates forwarded messages when originals are edited
- **Delete Synchronization**: Removes forwarded messages when originals are deleted
- **Duplicate Prevention**: Smart filtering to avoid message duplication
- **Album Processing**: Handles media groups as cohesive units

### 🛡️ **Reliability & Performance**

- **Retry Mechanism**: Exponential backoff with configurable limits
- **Error Recovery**: Graceful handling of network issues and API limits
- **Database Persistence**: SQLite-based message mapping for reliability
- **Memory Management**: Automatic cleanup of old media files
- **Concurrent Processing**: Async/await for optimal performance

### 🐳 **Deployment Ready**

- Docker containerization with multi-stage builds
- Docker Compose for easy orchestration
- Environment-based configuration
- Timezone support

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Telegram API credentials ([Get them here](https://my.telegram.org/apps))
- Bale Bot token ([Create a bot](https://ble.ir/newbot))

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/tje3d/Telesync.git
   cd Telesync
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

### Docker Deployment

```bash
# Using Docker Compose (Recommended)
docker-compose up -d

# Or using Docker directly
docker build -t Telesync .
docker run -d --name telegram-forwarder Telesync
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# Telegram API Configuration
API_ID=your_api_id_here
API_HASH=your_api_hash_here
SESSION_STRING=your_session_string_here
SOURCES=@channel1,@channel2,@group1

# Bale Messenger Configuration
BALE_TOKEN=your_bale_bot_token
BALE_CHAT_IDS=chat_id1,chat_id2:en,chat_id3:fa

# Performance Tuning
POLL_INTERVAL=5                    # Polling frequency (seconds)
EDIT_DELETE_CHECK_INTERVAL=30      # Edit/delete check frequency (seconds)
```

### Chat Configuration

The `BALE_CHAT_IDS` supports per-chat language settings:

- `chat_id1` - No translation (original language)
- `chat_id2:en` - Translate to English
- `chat_id3:fa` - Translate to Persian/Farsi

**Supported Languages**: Any language code supported by Google Translate (en, fa, ar, fr, de, es, etc.)

### Source Configuration

Specify Telegram sources in `SOURCES`:

- `@channel_username` - Public channels
- `@group_username` - Public groups
- `-1001234567890` - Private channels/groups (use chat ID)

## 🏗️ Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram      │───▶│   Telesync    │───▶│   Bale          │
│   Channels      │    │                  │    │   Messenger     │
│   Groups        │    │  ┌─────────────┐ │    │   Chats         │
└─────────────────┘    │  │ Message     │ │    └─────────────────┘
                       │  │ Processor   │ │
                       │  └─────────────┘ │
                       │  ┌─────────────┐ │
                       │  │ Media       │ │
                       │  │ Handler     │ │
                       │  └─────────────┘ │
                       │  ┌─────────────┐ │
                       │  │ Translation │ │
                       │  │ Engine      │ │
                       │  └─────────────┘ │
                       │  ┌─────────────┐ │
                       │  │ Database    │ │
                       │  │ Manager     │ │
                       │  └─────────────┘ │
                       └──────────────────┘
```

### Database Schema

SQLite database stores message mappings for edit/delete synchronization:

```sql
CREATE TABLE messages (
    telegram_id INTEGER,
    bale_chat_id TEXT,
    bale_ids TEXT,           -- JSON array of Bale message IDs
    is_album BOOLEAN,        -- Whether message is part of media group
    first_message BOOLEAN,   -- First message in album (has caption)
    content_hash TEXT,       -- Hash for edit detection
    last_check TIMESTAMP,    -- Last edit/delete check
    chat_id INTEGER,         -- Source Telegram chat ID
    PRIMARY KEY (telegram_id, bale_chat_id)
);
```

## 🔧 Advanced Features

### Retry Mechanism

- **Exponential Backoff**: Intelligent retry with increasing delays
- **Maximum Retry Time**: 5 minutes total retry duration
- **Jitter**: Random delay variation to prevent thundering herd
- **Server Error Handling**: Automatic retry on 5xx HTTP errors

### Media Management

- **Automatic Cleanup**: Removes media files older than 12 hours
- **Progress Tracking**: Real-time download progress indicators
- **Type Detection**: Intelligent media type classification
- **Album Preservation**: Maintains media group integrity

### Performance Optimizations

- **Async Processing**: Non-blocking I/O operations
- **Connection Pooling**: Efficient HTTP session management
- **Memory Management**: Automatic cleanup of processed messages
- **Batch Operations**: Efficient database transactions

## 📊 Monitoring & Logging

The application provides comprehensive logging with color-coded output:

- 🔵 **Info**: General operation status
- 🟢 **Success**: Successful operations
- 🟡 **Warning**: Non-critical issues
- 🔴 **Error**: Critical errors requiring attention

### Log Examples

```
2024-01-15 10:30:45 - INFO - 🚀 Starting monitoring...
2024-01-15 10:30:46 - INFO - 📩 New message [ID: 12345] in Channel Name (123456789)
2024-01-15 10:30:47 - INFO - ✅ Text forwarded to Bale chat 987654321
2024-01-15 10:30:48 - INFO - ✏️ Detected edit in message 12345
2024-01-15 10:30:49 - INFO - 🗑️ Detected deletion of message 12346
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/tje3d/Telesync/issues) page
2. Create a new issue with detailed information
3. Include logs and configuration (remove sensitive data)

## 🙏 Acknowledgments

- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram client library
- [aiohttp](https://github.com/aio-libs/aiohttp) - Async HTTP client/server
- [Google Translate](https://github.com/ssut/py-googletrans) - Translation service
- [Bale Messenger](https://bale.ai) - Iranian messaging platform

---

<div align="center">
  <strong>Made with ❤️ for seamless cross-platform messaging</strong>
</div>
