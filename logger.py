import sys
import logging
from typing import Optional, Union

# Default log format
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_FILE = "tgdlbot.log"

def setup_logger(
    level: int = logging.INFO,
    log_file: str = DEFAULT_LOG_FILE,
    log_format: str = DEFAULT_LOG_FORMAT,
    add_stdout: bool = True
) -> None:
    """
    Configure the root logger with specified settings
    
    Args:
        level: Logging level (default: logging.INFO)
        log_file: Path to log file (default: tgdlbot.log)
        log_format: Log message format
        add_stdout: Whether to add stdout as a handler
    """
    handlers = []
    
    # Add file handler
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    # Add stdout handler if requested
    if add_stdout:
        handlers.append(logging.StreamHandler(sys.stdout))
    
    # Configure the root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers
    )
    
    # Set specific logger levels
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

# Function to log exceptions with additional context
def log_exception(
    logger: logging.Logger, 
    message: str, 
    exception: Optional[Exception] = None,
    exc_info: bool = True
) -> None:
    """
    Log an exception with additional context
    
    Args:
        logger: Logger instance
        message: Message to log
        exception: Exception object (optional)
        exc_info: Whether to include exception info in log
    """
    if exception:
        logger.error(f"{message}: {str(exception)}", exc_info=exc_info)
    else:
        logger.error(message, exc_info=exc_info) 