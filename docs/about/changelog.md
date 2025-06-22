---
title: Changelog
description: Version history and updates for StreamBot
---

# Changelog

All notable changes to StreamBot are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2024-01-15

### Added - Video Streaming Release 🎬

- **Advanced Video Streaming Support**: Complete video streaming infrastructure with range request support
- **Cricster Frontend Integration**: Default video player frontend (https://cricster.pages.dev)
- **Range Request Support**: Full HTTP range request implementation for video seeking
- **Progressive Video Loading**: Stream videos while downloading for optimal user experience
- **Multiple Video Format Support**: MP4, MKV, AVI, WebM, MOV with automatic detection
- **Custom Video Frontend Support**: Build and integrate your own video player frontends
- **Video-Specific Bot Responses**: Enhanced file upload responses for video files with streaming options
- **Streaming Analytics**: Track video streaming usage and performance
- **Video Frontend Configuration**: Environment variable `VIDEO_FRONTEND_URL` with smart defaults

### Enhanced

- **Python Version Requirement**: Now requires Python 3.11+ for optimal performance
- **Video Frontend URL Parameter**: `{VIDEO_FRONTEND_URL}?stream={encoded_stream_url}` format
- **Bot Commands**: Updated `/info` and `/stats` commands to include video streaming information
- **API Endpoints**: Enhanced `/api/info` with streaming service status and capabilities
- **Memory Management**: Improved memory handling for video streaming operations
- **Stream Cleanup**: Automated cleanup of stale video streams every 10 minutes
- **Bandwidth Tracking**: Separate tracking for download and streaming bandwidth usage

### Changed

- **Default VIDEO_FRONTEND_URL**: Now defaults to `https://cricster.pages.dev` instead of `None`
- **Disable Video Frontend**: Set `VIDEO_FRONTEND_URL=false` to disable (case-insensitive)
- **Enhanced File Processing**: Video files now get both download and streaming links
- **Improved User Experience**: Video files show "🎬 Play Video" button for direct streaming
- **Documentation**: Comprehensive update of all documentation including video streaming guides

### Technical Improvements

- **Streaming Handler**: New dedicated streaming service in `StreamBot/web/streaming.py`
- **Video Detection**: Automatic video file detection and processing
- **CORS Configuration**: Enhanced CORS support for video streaming frontends
- **Range Request Validation**: Proper validation and error handling for range requests
- **Stream Session Management**: Track and manage active video streaming sessions
- **Performance Optimization**: Optimized video streaming performance and resource usage

### Security

- **Video Streaming Security**: Secure encoding for streaming URLs
- **Range Request Protection**: Prevent abuse of range requests
- **CORS Restrictions**: Controlled cross-origin access for video frontends
- **Stream Rate Limiting**: Per-user video streaming quotas and limits

## [2.0.5] - 2024-01-10

### Fixed

- **Database Connection**: Improved MongoDB connection stability and error handling
- **Memory Leaks**: Fixed memory leaks in long-running bot sessions
- **Rate Limiting**: More accurate rate limiting calculations
- **Bandwidth Cleanup**: Fixed bandwidth data cleanup to preserve current month data
- **Error Handling**: Better error messages and graceful failure handling

### Enhanced

- **Logging System**: Improved structured logging with better error tracking
- **Performance Monitoring**: Enhanced system monitoring and health checks
- **Resource Management**: Better memory and connection pool management
- **Admin Commands**: Improved admin command responses and error handling

## [2.0.0] - 2024-01-01

### Added - Major Release

- **Multi-Client Architecture**: Support for multiple Telegram client sessions
- **Advanced Bandwidth Management**: Monthly bandwidth tracking with automatic cleanup
- **Enhanced Security**: Comprehensive security middleware and rate limiting
- **Admin Dashboard**: Advanced admin commands for system monitoring
- **Health Checks**: Comprehensive health check endpoints
- **Database Optimization**: Improved MongoDB operations and indexing
- **Memory Management**: Advanced memory monitoring and cleanup systems
- **Stream Cleanup Scheduler**: Automated cleanup of old and stale streams

### Technical Improvements

- **Async Architecture**: Fully asynchronous design for better performance
- **Connection Pooling**: Optimized connection pooling for database and Telegram
- **Error Recovery**: Improved error recovery and graceful degradation
- **Resource Monitoring**: Real-time monitoring of system resources
- **Scalability**: Enhanced architecture for horizontal scaling

## [1.5.0] - 2023-12-15

### Added

- **Force Subscription**: Optional channel subscription requirement
- **Link Expiry**: Configurable link expiration functionality
- **Bandwidth Limits**: Monthly bandwidth usage limits
- **User Statistics**: Personal usage tracking and statistics
- **Admin Commands**: System administration and monitoring commands

### Enhanced

- **File Processing**: Improved file upload and processing speed
- **Database Performance**: Optimized database queries and operations
- **Error Messages**: More descriptive and helpful error messages
- **User Interface**: Enhanced bot interaction and user experience

## [1.4.0] - 2023-12-01

### Added

- **MongoDB Integration**: Complete database integration for user and file management
- **Rate Limiting**: Daily rate limits for users
- **User Management**: User registration and activity tracking
- **System Statistics**: Bot usage and performance statistics
- **Configuration Management**: Centralized configuration system

### Changed

- **Storage Backend**: Migrated from file-based to database storage
- **User Interface**: Improved bot command responses and interactions
- **Performance**: Significant performance improvements across all operations

## [1.3.0] - 2023-11-15

### Added

- **Range Request Support**: HTTP range requests for partial file downloads
- **File Metadata**: Enhanced file information and metadata display
- **Download Statistics**: Basic download tracking and statistics
- **Error Recovery**: Improved error handling and recovery mechanisms

### Fixed

- **Large File Handling**: Better support for large file downloads
- **Memory Usage**: Optimized memory usage for file operations
- **Connection Stability**: Improved Telegram connection stability

## [1.2.0] - 2023-11-01

### Added

- **Web Interface**: HTTP web server for file downloads
- **Direct Links**: Generate direct download links for files
- **File Validation**: Basic file validation and security checks
- **Logging System**: Comprehensive logging and monitoring

### Enhanced

- **Bot Commands**: Expanded command set and functionality
- **File Processing**: Improved file upload and processing
- **User Experience**: Better user interactions and feedback

## [1.1.0] - 2023-10-15

### Added

- **Multi-File Support**: Support for various file types and formats
- **Bot Commands**: Basic bot commands and user interaction
- **File Upload**: File upload handling via Telegram
- **Basic Security**: Initial security measures and validation

### Changed

- **Architecture**: Improved code organization and structure
- **Performance**: Basic performance optimizations

## [1.0.0] - 2023-10-01

### Added - Initial Release

- **Basic Bot Functionality**: Core Telegram bot implementation
- **File to Link Conversion**: Convert Telegram files to downloadable links
- **Simple Web Server**: Basic HTTP server for file serving
- **Configuration System**: Environment-based configuration
- **Documentation**: Initial documentation and setup guides

---

## Repository Information

**GitHub Repository**: [https://github.com/AnikethJana/Telegram-Download-Link-Generator](https://github.com/AnikethJana/Telegram-Download-Link-Generator)

**Contributors**: Thank you to all contributors who have helped improve StreamBot!

## Support

For support and questions:
- **Telegram**: [@ajmods_bot](https://t.me/ajmods_bot)
- **Issues**: [GitHub Issues](https://github.com/AnikethJana/Telegram-Download-Link-Generator/issues)
- **Documentation**: [Full Documentation](../index.md)

---

## Upgrade Guide

### Upgrading to 2.1.0 (Video Streaming)

1. **Update Python**: Ensure you're running Python 3.11 or higher
2. **Update Dependencies**: Run `pip install -r requirements.txt`
3. **Environment Variables**: 
   - `VIDEO_FRONTEND_URL` now defaults to `https://cricster.pages.dev`
   - Set to `false` if you want to disable video frontend
4. **Test Video Streaming**: Upload a video file to test new streaming capabilities
5. **Update Documentation**: Review updated API endpoints and features

### Upgrading to 2.0.0

1. **Database Migration**: Ensure MongoDB is properly configured
2. **Environment Update**: Review and update environment variables
3. **Admin Configuration**: Set up admin users in `ADMINS` environment variable
4. **Resource Monitoring**: Check system resources and scaling requirements

For detailed upgrade instructions, see the [Installation Guide](../getting-started/installation.md). 