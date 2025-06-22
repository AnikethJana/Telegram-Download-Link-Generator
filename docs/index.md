---
title: StreamBot Documentation
description: A high-performance Telegram file to link generator with video streaming capabilities
---

# StreamBot - Telegram File Download & Streaming Link Generator

<div class="grid cards" markdown>

- :material-send-circle:{ .lg .middle } **Telegram File to Link Generator**

    ---

    Instantly convert Telegram files to direct download links and streaming URLs with StreamBot.

    [:octicons-arrow-right-24: Get started](#getting-started)

- :material-rocket-launch:{ .lg .middle } **High Performance Architecture**

    ---

    Built with a multi-client architecture for maximum speed and reliability with video streaming support.

    [:octicons-arrow-right-24: Architecture](developer-guide/architecture.md)

- :material-play-circle:{ .lg .middle } **Video Streaming**

    ---

    Advanced video streaming with seeking support and custom frontend integration.

    [:octicons-arrow-right-24: Features](user-guide/overview.md)

- :material-api:{ .lg .middle } **REST API**

    ---

    Integrate StreamBot's capabilities with your applications.

    [:octicons-arrow-right-24: API Reference](api/overview.md)

</div>

## What is StreamBot?

StreamBot is a high-performance Telegram bot that generates direct download links and streaming URLs for files sent to it. It's built with a modern asynchronous Python architecture featuring multi-client support, bandwidth management, video streaming with seeking support, and rate limiting.

Whether you're sharing media, documents, or any other files, StreamBot makes it simple to distribute content via direct links without requiring recipients to use Telegram. The bot now includes advanced video streaming capabilities with custom frontend integration.

## Key Features

- **🔗 Direct Download Links** - Convert Telegram files to direct download URLs
- **🎬 Video Streaming** - Advanced video streaming with seeking support and custom player integration
- **⚡ High Performance** - Multi-client architecture with load balancing
- **📊 Bandwidth Management** - Built-in bandwidth tracking and limits
- **🛡️ Rate Limiting** - User-based rate limiting with configurable quotas
- **🔒 Force Subscription** - Optional channel subscription requirement
- **📱 Web Interface** - RESTful API with real-time status monitoring
- **🧹 Auto Cleanup** - Automatic cleanup of expired links and resources
- **📈 Admin Tools** - Advanced logging, memory monitoring, and broadcast features
- **🎯 Frontend Integration** - Custom video player frontend support with default Cricster integration

## Getting Started

Getting started with StreamBot is easy:

```bash
# Clone the repository
git clone https://github.com/AnikethJana/Telegram-Download-Link-Generator.git
cd Telegram-Download-Link-Generator

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Run the bot
python -m StreamBot
```

For complete setup instructions, see the [Installation Guide](getting-started/installation.md).

## How It Works

1. **User sends a file** to the StreamBot Telegram bot
2. **Bot processes the file** and stores it securely in Telegram's cloud
3. **Direct download and streaming links are generated** and sent to the user
4. **Recipients can download or stream the file** directly via the link without needing Telegram
5. **For videos**, users get both download and streaming options with seeking support

## Video Streaming Features

StreamBot now includes advanced video streaming capabilities:

- **Direct Video Streaming** - Stream videos directly in browsers with seeking support
- **Custom Frontend Integration** - Integrates with video player frontends (defaults to Cricster)
- **Range Request Support** - Full HTTP range request support for video seeking
- **Multiple Video Formats** - Supports MP4, WebM, MKV, AVI, and more
- **Seamless Experience** - One-click video playback with enhanced UI

## Project Status

StreamBot is actively maintained and regularly updated with new features and improvements.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](about/license.md)
[![MongoDB](https://img.shields.io/badge/Database-MongoDB-green.svg)](https://mongodb.com)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black.svg)](https://github.com/AnikethJana/Telegram-Download-Link-Generator)

## Support & Community

- **GitHub Issues**: [Report bugs or request features](https://github.com/AnikethJana/Telegram-Download-Link-Generator/issues)
- **GitHub Discussions**: [Ask questions and share ideas](https://github.com/AnikethJana/Telegram-Download-Link-Generator/discussions)
- **Telegram Support**: [Contact developer](https://t.me/ajmods_bot) 