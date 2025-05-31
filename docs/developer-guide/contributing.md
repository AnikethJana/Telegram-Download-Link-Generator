---
title: Contributing to StreamBot
description: Guidelines for contributing to the StreamBot project
---

# Contributing to StreamBot

Thank you for considering contributing to StreamBot! 🎉

This guide outlines how to contribute effectively to the project and maintain code quality.

## Ways to Contribute

### 💻 Code Contributions
- Bug fixes and improvements
- New features and enhancements
- Performance optimizations
- Test coverage improvements

### 📚 Documentation
- Improve existing documentation
- Add examples and tutorials
- Fix typos and clarifications
- Translate documentation

### 🐛 Bug Reports
- Report bugs with detailed information
- Provide steps to reproduce issues
- Share system information and logs

### 💡 Feature Requests
- Suggest new features or improvements
- Discuss implementation approaches
- Share use cases and requirements

## Development Setup

### Prerequisites

- Python 3.8+
- MongoDB (local or cloud)
- Git
- Code editor (VS Code recommended)

### Quick Setup

```bash
# Fork and clone the repository
git clone https://github.com/your-username/StreamBot.git
cd StreamBot

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
# Edit .env with your configuration

# Run the application
python -m StreamBot
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

**Branch Naming Convention**:
- `feature/feature-name` - New features
- `fix/bug-description` - Bug fixes
- `docs/documentation-topic` - Documentation improvements
- `refactor/component-name` - Code refactoring

### 2. Make Changes

Follow these guidelines:

#### Code Style
- Use **Black** for code formatting: `black StreamBot/`
- Follow **PEP 8** style guidelines
- Use **type hints** for all functions
- Write **descriptive variable names**
- Keep functions **small and focused**

#### Documentation
- Add **docstrings** to all public functions
- Update **relevant documentation** files
- Include **code examples** where helpful
- Keep comments **concise and meaningful**

#### Testing
- Write **unit tests** for new functionality
- Ensure **existing tests pass**: `pytest`
- Aim for **>80% code coverage**
- Test **error conditions** and edge cases

### 3. Commit Changes

Use conventional commit format:

```bash
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples**:
```bash
git commit -m "feat(api): add bandwidth usage endpoint"
git commit -m "fix(bot): handle connection timeout errors"
git commit -m "docs(readme): update installation instructions"
```

### 4. Test Your Changes

```bash
# Run all tests
pytest

# Check code style
black --check StreamBot/
flake8 StreamBot/

# Type checking
mypy StreamBot/

# Test the application
python -m StreamBot
```

### 5. Submit Pull Request

1. Push your branch: `git push origin feature/your-feature-name`
2. Create a Pull Request on GitHub
3. Fill out the PR template with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots if applicable

## Code Quality Standards

### Formatting

Use Black for consistent formatting:

```bash
# Format all code
black StreamBot/

# Check formatting
black --check StreamBot/
```

### Linting

Use flake8 for code quality:

```bash
# Check code quality
flake8 StreamBot/
```

### Type Checking

Use mypy for type safety:

```bash
# Type checking
mypy StreamBot/
```

### Testing

Write comprehensive tests:

```python
import pytest
from unittest.mock import Mock, patch
from StreamBot.utils.utils import humanbytes

def test_humanbytes_conversion():
    """Test human-readable byte conversion."""
    assert humanbytes(1024) == "1.00 KB"
    assert humanbytes(1048576) == "1.00 MB"
    assert humanbytes(0) == "0 B"

@patch('StreamBot.database.database.user_data')
async def test_add_user(mock_collection):
    """Test user addition to database."""
    mock_collection.find_one.return_value = None
    mock_collection.insert_one.return_value = Mock()
    
    from StreamBot.database.database import add_user
    await add_user(12345)
    
    mock_collection.insert_one.assert_called_once()
```

## Project Structure

Understanding the codebase:

```
StreamBot/
├── StreamBot/              # Main application
│   ├── __main__.py        # Entry point
│   ├── config.py          # Configuration
│   ├── bot.py             # Bot handlers
│   ├── client_manager.py  # Multi-client management
│   ├── database/          # Database operations
│   ├── utils/            # Utility modules
│   └── web/              # Web server
├── tests/                # Test suite
├── docs/                 # Documentation
└── requirements.txt      # Dependencies
```

## Adding New Features

### Feature Development Process

1. **Discuss the feature** in GitHub Issues
2. **Design the implementation** with community input
3. **Create a branch** following naming conventions
4. **Implement the feature** with tests
5. **Update documentation** as needed
6. **Submit a pull request** for review

### Feature Guidelines

- **Follow existing patterns** in the codebase
- **Add appropriate error handling** and logging
- **Update configuration** if needed
- **Add tests** for new functionality
- **Update documentation** accordingly

## Bug Reports

### Creating Good Bug Reports

Include the following information:

```markdown
**Bug Description**
Clear description of the issue.

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What should happen.

**Actual Behavior**
What actually happens.

**Environment**
- OS: [e.g., Ubuntu 20.04]
- Python Version: [e.g., 3.9.5]
- StreamBot Version: [e.g., 1.0.0]

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

## Recognition

Contributors will be recognized in:
- **Contributors section** in README
- **Release notes** for significant contributions
- **Documentation** where applicable

## Getting Help

If you need help:

1. Check existing **documentation**
2. Search **GitHub Issues** for similar problems
3. Ask in **GitHub Discussions**
4. Reach out to **maintainers** if needed

Thank you for contributing to StreamBot! Every contribution helps make the project better. 🚀 