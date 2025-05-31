---
title: StreamBot Documentation
description: A high-performance Telegram file to link generator
---

# StreamBot

<div class="grid cards" markdown>

- :material-send-circle:{ .lg .middle } **Telegram File to Link Generator**

    ---

    Instantly convert Telegram files to direct download links with StreamBot.

    [:octicons-arrow-right-24: Get started](#getting-started)

- :material-rocket-launch:{ .lg .middle } **High Performance Architecture**

    ---

    Built with a multi-client architecture for maximum speed and reliability.

    [:octicons-arrow-right-24: Architecture](developer-guide/architecture.md)

- :material-cloud-download:{ .lg .middle } **Powerful Features**

    ---

    Rate limiting, bandwidth management, and force subscription built-in.

    [:octicons-arrow-right-24: Features](user-guide/overview.md)

- :material-api:{ .lg .middle } **REST API**

    ---

    Integrate StreamBot's capabilities with your applications.

    [:octicons-arrow-right-24: API Reference](api/overview.md)

</div>

## What is StreamBot?

StreamBot is a high-performance Telegram bot that generates direct download links for files sent to it. It's built with a modern asynchronous Python architecture featuring multi-client support, bandwidth management, and rate limiting.

Whether you're sharing media, documents, or any other files, StreamBot makes it simple to distribute content via direct links without requiring recipients to use Telegram.

## Key Features

- **🔗 Direct Download Links** - Convert Telegram files to direct download URLs
- **⚡ High Performance** - Multi-client architecture with load balancing
- **📊 Bandwidth Management** - Built-in bandwidth tracking and limits
- **🛡️ Rate Limiting** - User-based rate limiting with configurable quotas
- **🔒 Force Subscription** - Optional channel subscription requirement
- **📱 Web Interface** - RESTful API with real-time status monitoring
- **🧹 Auto Cleanup** - Automatic cleanup of expired links and resources
- **📈 Admin Tools** - Advanced logging, memory monitoring, and broadcast features

## Getting Started

Getting started with StreamBot is easy:

```bash
# Clone the repository
git clone https://github.com/yourusername/StreamBot.git
cd StreamBot

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
2. **Bot processes the file** and stores it securely
3. **Direct download link is generated** and sent to the user
4. **Recipients can download the file** directly via the link without needing Telegram

## Project Status

StreamBot is actively maintained and regularly updated with new features and improvements.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](about/license.md)
[![MongoDB](https://img.shields.io/badge/Database-MongoDB-green.svg)](https://mongodb.com)

## Support & Community

- **GitHub Issues**: [Report bugs or request features](https://github.com/yourusername/StreamBot/issues)
- **GitHub Discussions**: [Ask questions and share ideas](https://github.com/yourusername/StreamBot/discussions)
- **Telegram Channel**: [Get updates and announcements](https://t.me/yourstreambot) 