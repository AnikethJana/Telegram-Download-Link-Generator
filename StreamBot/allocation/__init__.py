"""
Intelligent client allocation module for StreamBot.

This module provides size-based client allocation for download tasks,
segregating small and large files to optimize resource utilization.
"""

from .intelligent_allocator import IntelligentClientAllocator

__all__ = ["IntelligentClientAllocator"] 