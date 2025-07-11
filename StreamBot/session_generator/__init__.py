# StreamBot/session_generator/__init__.py
"""
Session Generator module for StreamBot.

This module provides web-based Telegram login integration for automatic
session generation and management.
"""

from .session_manager import SessionManager
from .telegram_auth import TelegramAuth

__all__ = [
    "SessionManager", 
    "TelegramAuth"
] 