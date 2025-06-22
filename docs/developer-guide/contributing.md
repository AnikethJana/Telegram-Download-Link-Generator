---
title: Contributing to StreamBot
description: Guidelines for contributing to the StreamBot project with video streaming capabilities
---

# Contributing to StreamBot

Thank you for considering contributing to StreamBot! 🎉

This guide outlines how to contribute effectively to the project and maintain code quality while working with both file sharing and advanced video streaming features.

## Ways to Contribute

### 💻 Code Contributions
- Bug fixes and improvements
- New features and enhancements (including video streaming features)
- Performance optimizations
- Test coverage improvements
- Video frontend integrations

### 📚 Documentation
- Improve existing documentation
- Add examples and tutorials (especially for video streaming)
- Fix typos and clarifications
- Translate documentation

### 🐛 Bug Reports
- Report bugs with detailed information
- Provide steps to reproduce issues
- Share system information and logs
- Test video streaming functionality

### 💡 Feature Requests
- Suggest new features or improvements
- Discuss implementation approaches
- Share use cases and requirements
- Propose video streaming enhancements

## Development Setup

### Prerequisites

- **Python 3.11+** (required for optimal performance)
- **MongoDB** (local or cloud)
- **Git**
- **Code editor** (VS Code recommended with Python extension)
- **FFmpeg** (optional, for video testing)

### Quick Setup

```bash
# Fork and clone the repository
git clone https://github.com/your-username/Telegram-Download-Link-Generator.git
cd Telegram-Download-Link-Generator

# Set up virtual environment with Python 3.11+
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt  # If exists

# Copy environment configuration
cp .env.example .env
# Edit .env with your configuration including video frontend settings

# Run the application
python -m StreamBot
```

### Development Environment Configuration

```env
# Development-specific settings
API_ID=your_dev_api_id
API_HASH=your_dev_api_hash
BOT_TOKEN=your_dev_bot_token
LOG_CHANNEL=-1001234567890
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=StreamBotDev
BASE_URL=http://localhost:8080
PORT=8080
BIND_ADDRESS=127.0.0.1

# Video streaming development
VIDEO_FRONTEND_URL=https://cricster.pages.dev
# Or use local frontend for testing: http://localhost:3000

# Development features
DEBUG=true
LOG_LEVEL=DEBUG
DEVELOPMENT_MODE=true
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
# or
git checkout -b video/streaming-enhancement
```

**Branch Naming Convention**:
- `feature/feature-name` - New features
- `fix/bug-description` - Bug fixes
- `video/streaming-feature` - Video streaming specific features
- `docs/documentation-topic` - Documentation improvements
- `refactor/component-name` - Code refactoring
- `perf/optimization-area` - Performance improvements

### 2. Make Changes

Follow these guidelines:

#### Code Style

**Python Code Standards**:
```bash
# Use Black for code formatting
black StreamBot/

# Use isort for import sorting
isort StreamBot/

# Use flake8 for linting
flake8 StreamBot/
```

**Code Quality Requirements**:
- Follow **PEP 8** style guidelines
- Use **type hints** for all functions and methods
- Write **descriptive variable and function names**
- Keep functions **small and focused** (max 50 lines)
- Use **async/await** for I/O operations
- Handle **exceptions appropriately**

#### Video Streaming Development

**Video Feature Guidelines**:
```python
# Example: Adding a new video streaming feature
async def process_video_stream(
    file_id: str, 
    range_header: Optional[str] = None,
    quality: str = "auto"
) -> StreamingResponse:
    """
    Process video streaming request with range support.
    
    Args:
        file_id: Encoded file identifier
        range_header: HTTP range header for seeking
        quality: Video quality preference
        
    Returns:
        StreamingResponse with video data
        
    Raises:
        FileNotFoundError: If file doesn't exist
        RangeNotSatisfiableError: If range is invalid
    """
    # Implementation here
```

**Video Testing Requirements**:
- Test with multiple video formats (MP4, MKV, WebM)
- Verify range request functionality
- Test seeking capabilities
- Validate frontend integration
- Check performance with large files

#### Documentation

**Documentation Standards**:
- Add **docstrings** to all public functions and classes
- Update **relevant documentation** files
- Include **code examples** where helpful
- Keep comments **concise and meaningful**
- Document **video streaming features** thoroughly

**Example Documentation**:
```python
class VideoStreamingHandler:
    """
    Handles video streaming requests with range support.
    
    This class provides advanced video streaming capabilities including:
    - HTTP range request processing
    - Video seeking support
    - Multiple format handling
    - Frontend integration
    
    Example:
        ```python
        handler = VideoStreamingHandler()
        response = await handler.stream_video(file_id, range_header)
        ```
    """
```

#### Testing

**Testing Requirements**:
- Write **unit tests** for new functionality
- Ensure **existing tests pass**: `pytest`
- Aim for **>80% code coverage**
- Test **error conditions** and edge cases
- Include **video streaming tests**

**Video Streaming Tests**:
```python
import pytest
from unittest.mock import Mock, patch
from StreamBot.web.streaming import VideoStreamingHandler

class TestVideoStreaming:
    
    async def test_range_request_processing(self):
        """Test HTTP range request handling."""
        handler = VideoStreamingHandler()
        range_header = "bytes=0-1023"
        
        result = await handler.process_range_request(
            file_id="test_video",
            range_header=range_header
        )
        
        assert result.status_code == 206
        assert "Content-Range" in result.headers
    
    async def test_video_seeking_functionality(self):
        """Test video seeking capabilities."""
        handler = VideoStreamingHandler()
        
        # Test seeking to specific timestamp
        result = await handler.seek_to_timestamp(
            file_id="test_video",
            timestamp=30.5
        )
        
        assert result is not None
        assert result.content_length > 0
    
    async def test_frontend_integration(self):
        """Test video frontend URL generation."""
        from StreamBot.utils.video import generate_frontend_url
        
        stream_url = "https://example.com/stream/abc123"
        frontend_url = generate_frontend_url(
            stream_url, 
            "https://cricster.pages.dev"
        )
        
        assert "cricster.pages.dev" in frontend_url
        assert "stream=" in frontend_url
```

### 3. Commit Changes

Use conventional commit format:

```bash
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

**Examples**:
```bash
git commit -m "feat(video): add seeking support for video streaming"
git commit -m "fix(api): handle range request edge cases"
git commit -m "docs(streaming): update video frontend integration guide"
git commit -m "perf(streaming): optimize video chunk processing"
git commit -m "test(video): add comprehensive streaming test suite"
```

### 4. Test Your Changes

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=StreamBot --cov-report=html

# Run specific test categories
pytest -m "video_streaming"  # Video streaming tests
pytest -m "api"              # API tests
pytest -m "integration"      # Integration tests

# Check code style
black --check StreamBot/
isort --check-only StreamBot/
flake8 StreamBot/

# Type checking
mypy StreamBot/

# Test the application manually
python -m StreamBot
```

**Video Streaming Manual Testing**:
```bash
# Test video upload and streaming
# 1. Start StreamBot
# 2. Upload various video formats to bot
# 3. Test download links
# 4. Test streaming links with seeking
# 5. Verify frontend integration
```

### 5. Submit Pull Request

1. **Push your branch**: `git push origin feature/your-feature-name`
2. **Create a Pull Request** on GitHub
3. **Fill out the PR template** with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots/videos if applicable (especially for video features)
   - Testing performed

**Pull Request Template**:
```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Video streaming enhancement
- [ ] Documentation update
- [ ] Performance improvement

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests passed
- [ ] Manual testing performed
- [ ] Video streaming functionality tested

## Video Streaming (if applicable)
- [ ] Range requests working
- [ ] Seeking functionality tested
- [ ] Frontend integration verified
- [ ] Multiple formats tested

## Screenshots/Videos
Include screenshots or videos demonstrating the changes.
```

## Code Quality Standards

### Formatting and Linting

**Automated Code Quality**:
```bash
# Setup pre-commit hooks (recommended)
pip install pre-commit
pre-commit install

# This will run automatically on git commit:
# - Black formatting
# - isort import sorting
# - flake8 linting
# - mypy type checking
```

**Manual Quality Checks**:
```bash
# Format all code
black StreamBot/

# Sort imports
isort StreamBot/

# Check code quality
flake8 StreamBot/ --max-line-length=88 --extend-ignore=E203,W503

# Type checking
mypy StreamBot/ --ignore-missing-imports
```

### Performance Guidelines

**General Performance**:
- Use **async/await** for I/O operations
- Implement **proper caching** strategies
- Optimize **database queries**
- Use **connection pooling**
- Monitor **memory usage**

**Video Streaming Performance**:
```python
# Example: Optimized video streaming
async def stream_video_optimized(
    file_id: str,
    range_header: Optional[str] = None
) -> AsyncIterator[bytes]:
    """Optimized video streaming with proper buffering."""
    
    chunk_size = 1024 * 1024  # 1MB chunks
    
    async with get_file_stream(file_id) as stream:
        if range_header:
            start, end = parse_range_header(range_header)
            await stream.seek(start)
            remaining = end - start + 1
        else:
            remaining = await stream.get_size()
        
        while remaining > 0:
            chunk_size_to_read = min(chunk_size, remaining)
            chunk = await stream.read(chunk_size_to_read)
            
            if not chunk:
                break
                
            yield chunk
            remaining -= len(chunk)
```

## Project Structure

Understanding the codebase:

```
StreamBot/
├── StreamBot/              # Main application
│   ├── __main__.py        # Entry point
│   ├── config.py          # Configuration management
│   ├── bot.py             # Bot handlers and logic
│   ├── client_manager.py  # Multi-client management
│   ├── database/          # Database operations
│   │   ├── __init__.py
│   │   └── database.py
│   ├── security/          # Security middleware
│   │   ├── __init__.py
│   │   ├── middleware.py
│   │   ├── rate_limiter.py
│   │   └── validator.py
│   ├── utils/            # Utility modules
│   │   ├── __init__.py
│   │   ├── bandwidth.py
│   │   ├── cleanup_scheduler.py
│   │   ├── custom_dl.py
│   │   ├── exceptions.py
│   │   ├── file_properties.py
│   │   ├── memory_manager.py
│   │   ├── smart_logger.py
│   │   ├── stream_cleanup.py
│   │   └── utils.py
│   └── web/              # Web server and streaming
│       ├── __init__.py
│       ├── streaming.py  # Video streaming handler
│       └── web.py        # Main web server
├── tests/                # Test suite
├── docs/                 # Documentation
├── requirements.txt      # Dependencies
├── .env.example         # Environment template
├── Dockerfile           # Container configuration
└── docker-compose.yml  # Multi-service setup
```

## Adding New Features

### Feature Development Process

1. **Discuss the feature** in GitHub Issues or Discussions
2. **Design the implementation** with community input
3. **Create a branch** following naming conventions
4. **Implement the feature** with comprehensive tests
5. **Update documentation** as needed
6. **Submit a pull request** for review

### Feature Guidelines

**General Guidelines**:
- **Follow existing patterns** in the codebase
- **Add appropriate error handling** and logging
- **Update configuration** if needed
- **Add tests** for new functionality
- **Update documentation** accordingly

**Video Streaming Feature Guidelines**:
- **Maintain compatibility** with existing video frontends
- **Support range requests** for seeking functionality
- **Optimize for performance** and memory usage
- **Test with multiple video formats**
- **Document frontend integration** requirements

### Example: Adding a New Video Feature

```python
# StreamBot/web/video_transcoding.py
from typing import Optional, Dict, Any
import asyncio
from .streaming import VideoStreamingHandler

class VideoTranscodingService:
    """
    Service for video transcoding and quality optimization.
    
    This service provides:
    - Multiple quality transcoding
    - Format conversion
    - Adaptive bitrate preparation
    """
    
    def __init__(self, streaming_handler: VideoStreamingHandler):
        self.streaming_handler = streaming_handler
        self.supported_qualities = ["240p", "480p", "720p", "1080p"]
    
    async def transcode_video(
        self, 
        file_id: str, 
        target_quality: str = "720p"
    ) -> Dict[str, Any]:
        """
        Transcode video to specified quality.
        
        Args:
            file_id: Source video file identifier
            target_quality: Target quality (240p, 480p, 720p, 1080p)
            
        Returns:
            Dict containing transcoded file information
            
        Raises:
            UnsupportedQualityError: If quality not supported
            TranscodingError: If transcoding fails
        """
        if target_quality not in self.supported_qualities:
            raise UnsupportedQualityError(f"Quality {target_quality} not supported")
        
        # Implementation here
        pass
```

## Bug Reports

### Creating Good Bug Reports

Include the following information:

```markdown
**Bug Description**
Clear description of the issue.

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. Upload video file
4. See error

**Expected Behavior**
What should happen.

**Actual Behavior**
What actually happens.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python Version: [e.g., 3.11.5]
- StreamBot Version: [e.g., 2.1.0]
- Browser (for video streaming): [e.g., Chrome 118]

**Video Streaming Specific (if applicable)**
- Video format: [e.g., MP4, MKV]
- Video size: [e.g., 500MB]
- Frontend used: [e.g., Cricster, Custom]
- Range request working: [Yes/No]

**Logs**
```
[Paste relevant log entries]
```

**Additional Context**
Any other relevant information.
```

## Community Guidelines

### Be Respectful
- Use inclusive language
- Be patient with newcomers
- Provide constructive feedback
- Celebrate contributions of all sizes

### Communication
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Pull Requests**: Code review and discussion
- **Telegram**: [@ajmods_bot](https://t.me/ajmods_bot) for direct support

### Video Streaming Community
- Share video frontend integrations
- Discuss performance optimizations
- Help test new video features
- Contribute to video streaming documentation

## Recognition

Contributors will be recognized in:
- **Contributors section** in README
- **Release notes** for significant contributions
- **Documentation** where applicable
- **Hall of Fame** for major contributions

## Development Resources

### Useful Tools

**Python Development**:
- **VS Code** with Python extension
- **PyCharm** Professional/Community
- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking

**Video Development**:
- **FFmpeg** for video testing and analysis
- **VLC** for video format testing
- **Browser DevTools** for streaming debugging
- **Postman** for API testing

**Testing Tools**:
- **pytest** for unit testing
- **pytest-asyncio** for async testing
- **pytest-cov** for coverage reporting
- **locust** for load testing

### Learning Resources

**Python & AsyncIO**:
- [Real Python AsyncIO Tutorial](https://realpython.com/async-io-python/)
- [Python Type Hints Guide](https://docs.python.org/3/library/typing.html)

**Video Streaming**:
- [HTTP Range Requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests)
- [Video Streaming Fundamentals](https://developer.mozilla.org/en-US/docs/Web/Guide/Audio_and_video_delivery)

**Telegram Bot Development**:
- [Pyrogram Documentation](https://docs.pyrogram.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

## Getting Help

If you need help:

1. Check existing **documentation**
2. Search **GitHub Issues** for similar problems
3. Ask in **GitHub Discussions**
4. Contact **maintainers** via [Telegram](https://t.me/ajmods_bot)

### Development Support

For development-specific help:
- **Architecture questions**: Review [Architecture Guide](architecture.md)
- **Setup issues**: Check [Installation Guide](../getting-started/installation.md)
- **Video streaming**: Review [API Documentation](../api/overview.md)
- **Configuration**: See [Configuration Guide](../getting-started/configuration.md)

## Release Process

### Version Numbering

StreamBot follows [Semantic Versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes
- **Minor** (X.Y.0): New features, video streaming enhancements
- **Patch** (X.Y.Z): Bug fixes, security updates

### Release Checklist

- [ ] All tests passing
- [ ] Documentation updated
- [ ] Video streaming features tested
- [ ] Performance benchmarks verified
- [ ] Security review completed
- [ ] Changelog updated
- [ ] Version bumped appropriately

Thank you for contributing to StreamBot! Every contribution helps make the project better and brings advanced video streaming capabilities to more users. 🚀 