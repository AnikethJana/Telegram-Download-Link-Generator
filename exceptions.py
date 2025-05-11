import logging
import traceback
import functools
from typing import Callable, Any, TypeVar, Optional, Type, Union, List, cast

from logger import log_exception, get_logger

# Initialize logger for this module
logger = get_logger(__name__)

# Type variable for function return types
T = TypeVar('T')

# Custom exceptions
class BotError(Exception):
    """Base exception for all bot-related errors"""
    pass

class ConfigError(BotError):
    """Exception raised for configuration errors"""
    pass

class DatabaseError(BotError):
    """Exception raised for database errors"""
    pass  

class MediaError(BotError):
    """Exception raised for media processing errors"""
    pass

class RateLimitError(BotError):
    """Exception raised when rate limits are hit"""
    pass

class AuthError(BotError):
    """Exception raised for authentication errors"""
    pass

# Exception handler decorator
def handle_exceptions(
    reraise: bool = False,
    log_level: int = logging.ERROR,
    fallback_return: Optional[Any] = None,
    handled_exceptions: Optional[List[Type[Exception]]] = None
) -> Callable[[Callable[..., T]], Callable[..., Union[T, Any]]]:
    """
    Decorator to handle exceptions in functions
    
    Args:
        reraise: Whether to reraise the exception after handling
        log_level: Logging level for exceptions
        fallback_return: Value to return if an exception occurs
        handled_exceptions: List of exception types to handle (None = handle all)
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, Any]]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Union[T, Any]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Skip handling if exception is not in handled_exceptions
                if handled_exceptions and not any(isinstance(e, exc_type) for exc_type in handled_exceptions):
                    raise

                # Get function name for logging
                func_name = getattr(func, "__qualname__", func.__name__)
                
                # Log the exception
                exc_message = f"Exception in {func_name}: {str(e)}"
                log_args = {
                    "msg": exc_message,
                    "exc_info": True,
                }
                
                # Log at appropriate level
                logger_method = getattr(logger, logging.getLevelName(log_level).lower(), logger.error)
                logger_method(**log_args)
                
                # Reraise if requested
                if reraise:
                    raise
                
                # Return fallback value
                return fallback_return
        return wrapper
    return decorator

# Async version of exception handler
def handle_async_exceptions(
    reraise: bool = False,
    log_level: int = logging.ERROR,
    fallback_return: Optional[Any] = None,
    handled_exceptions: Optional[List[Type[Exception]]] = None
) -> Callable[[Callable[..., T]], Callable[..., Union[T, Any]]]:
    """
    Decorator to handle exceptions in async functions
    
    Args:
        reraise: Whether to reraise the exception after handling
        log_level: Logging level for exceptions
        fallback_return: Value to return if an exception occurs
        handled_exceptions: List of exception types to handle (None = handle all)
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, Any]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Union[T, Any]:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Skip handling if exception is not in handled_exceptions
                if handled_exceptions and not any(isinstance(e, exc_type) for exc_type in handled_exceptions):
                    raise

                # Get function name for logging
                func_name = getattr(func, "__qualname__", func.__name__)
                
                # Log the exception
                exc_message = f"Exception in {func_name}: {str(e)}"
                log_args = {
                    "msg": exc_message,
                    "exc_info": True,
                }
                
                # Log at appropriate level
                logger_method = getattr(logger, logging.getLevelName(log_level).lower(), logger.error)
                logger_method(**log_args)
                
                # Reraise if requested
                if reraise:
                    raise
                
                # Return fallback value
                return fallback_return
        return wrapper
    return decorator

# Utility function to get exception details as string
def get_exception_details(exception: Exception) -> str:
    """
    Get detailed information about an exception
    
    Args:
        exception: The exception to analyze
        
    Returns:
        Formatted string with exception details
    """
    tb_str = traceback.format_exception(type(exception), exception, exception.__traceback__)
    return "".join(tb_str) 