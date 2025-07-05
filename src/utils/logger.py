"""
Logging configuration and utilities for Playlist-Downloader
Provides colored console output and file logging with separation between user and technical messages
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import colorama
from colorama import Fore, Back, Style

from ..config.settings import get_settings


# Initialize colorama for Windows compatibility
colorama.init()


class ConsoleMessageFilter(logging.Filter):
    """Filter to allow only user-facing messages to console"""
    
    def filter(self, record):
        # Allow all WARNING+ messages
        if record.levelno >= logging.WARNING:
            return True
        
        # Allow messages explicitly marked for console
        if hasattr(record, 'console_output') and record.console_output:
            return True
        
        # Allow messages from specific console loggers
        if record.name.endswith('.console') or record.name.endswith('.user'):
            return True
        
        # Block everything else (DEBUG/INFO technical messages)
        return False


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output for console"""
    
    # Color mapping for log levels
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Back.WHITE + Style.BRIGHT,
    }
    
    def __init__(self, fmt: Optional[str] = None, use_colors: bool = True):
        """
        Initialize colored formatter
        
        Args:
            fmt: Log format string
            use_colors: Whether to use colored output
        """
        super().__init__()
        self.use_colors = use_colors
        # Simpler format for console (user-facing)
        self.fmt = fmt or '%(message)s'
        
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors"""
        if self.use_colors and record.levelname in self.COLORS:
            # Color the level name
            colored_levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
            
            # Create a copy of the record to avoid modifying the original
            record_copy = logging.makeLogRecord(record.__dict__)
            record_copy.levelname = colored_levelname
            
            # Format with colored level
            formatter = logging.Formatter(self.fmt)
            return formatter.format(record_copy)
        else:
            # No colors, standard formatting
            formatter = logging.Formatter(self.fmt)
            return formatter.format(record)


class ProgressHandler(logging.Handler):
    """Custom handler that doesn't interfere with progress bars"""
    
    def __init__(self, stream=None):
        """Initialize progress-friendly handler"""
        super().__init__()
        self.stream = stream or sys.stderr
        
    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record without interfering with progress bars"""
        try:
            msg = self.format(record)
            # Clear current line and print log message
            self.stream.write(f'\r{" " * 80}\r{msg}\n')
            self.stream.flush()
        except Exception:
            self.handleError(record)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
    colored_output: bool = True,
    max_size: str = "10MB",
    backup_count: int = 3
) -> None:
    """
    Setup application logging configuration with separated console/file output
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None to disable file logging)
        console_output: Enable console logging
        colored_output: Enable colored console output
        max_size: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    # Convert level string to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, filter at handler level
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler - only user-facing messages (WARNING+ or explicitly marked)
    if console_output:
        console_handler = ProgressHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)  # Let filter decide what to show
        
        # Add filter to show only user-facing messages
        console_filter = ConsoleMessageFilter()
        console_handler.addFilter(console_filter)
        
        # Use simple colored formatter for console
        console_formatter = ColoredFormatter(
            fmt='%(message)s',  # Very simple format for users
            use_colors=colored_output
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with full detail logging
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parse max_size
        size_bytes = parse_size(max_size)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=size_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Capture everything for file
        
        # Detailed formatter for file (technical details)
        file_formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)-30s | %(levelname)-8s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Disable all external library logging more aggressively
    external_libs = [
        'spotipy', 'urllib3', 'requests', 'yt_dlp', 'ytmusicapi',
        'syncedlyrics', 'musixmatch', 'megalobiz', 'httpx', 'httpcore',
        'urllib3.connectionpool', 'requests.packages.urllib3.connectionpool'
    ]

    for lib in external_libs:
        logger = logging.getLogger(lib)
        logger.setLevel(logging.CRITICAL)
        logger.disabled = True
        logger.propagate = False
        
    # Log startup message (to file only)
    logger = logging.getLogger('playlist-downloader')
    logger.info(f"Logging initialized - Level: {level}, Console: {console_output}, File: {log_file}")


def reconfigure_logging_for_playlist(
    playlist_directory: Path,
    level: str = "INFO",
    max_size: str = "50MB",
    backup_count: int = 3
) -> None:
    """
    Reconfigure logging to write to playlist-specific log file
    Maintains console/file separation
    
    Args:
        playlist_directory: Directory of the playlist
        level: Logging level
        max_size: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    try:
        # Create logs directory in playlist folder
        logs_directory = playlist_directory / "logs"
        logs_directory.mkdir(parents=True, exist_ok=True)
        
        # Define log file path
        log_file_path = logs_directory / "playlist-dl.log"
        
        # Get root logger
        root_logger = logging.getLogger()
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        
        # Parse max_size to bytes
        size_bytes = parse_size(max_size)
        
        # Create new file handler with rotation (full detail)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=size_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Set logging level
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        root_logger.setLevel(logging.DEBUG)
        file_handler.setLevel(logging.DEBUG)  # Capture everything for file
        
        # Create console handler with filter for user messages only
        console_handler = ProgressHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # Add filter for console
        console_filter = ConsoleMessageFilter()
        console_handler.addFilter(console_filter)
        
        # Set formatters
        file_formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)-30s | %(levelname)-8s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = ColoredFormatter(
            fmt='%(message)s',  # Simple format for users
            use_colors=True
        )
        
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Disable all external library logging more aggressively
        external_libs = [
            'spotipy', 'urllib3', 'requests', 'yt_dlp', 'ytmusicapi',
            'syncedlyrics', 'musixmatch', 'megalobiz', 'httpx', 'httpcore',
            'urllib3.connectionpool', 'requests.packages.urllib3.connectionpool'
        ]

        for lib in external_libs:
            logger = logging.getLogger(lib)
            logger.setLevel(logging.CRITICAL)
            logger.disabled = True
            logger.propagate = False
                
        # Log the reconfiguration (to file only)
        logger = logging.getLogger('playlist-downloader.logging')
        logger.info(f"Logging reconfigured for playlist: {log_file_path}")
        logger.info(f"Log rotation: {max_size} max size, {backup_count} backups")
        
    except Exception as e:
        # Fallback to console logging
        print(f"Failed to reconfigure logging: {e}")
        setup_logging(level=level, console_output=True, log_file=None)


def get_current_log_file() -> Optional[Path]:
    """
    Get the current log file path from active file handlers
    
    Returns:
        Path to current log file or None if no file logging
    """
    try:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                return Path(handler.baseFilename)
        return None
    except Exception:
        return None
    
def parse_size(size_str: str) -> int:
    """
    Parse size string to bytes
    
    Args:
        size_str: Size string like "10MB", "1GB", "500KB"
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
    }
    
    # Extract number and unit
    import re
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B)$', size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")
    
    number, unit = match.groups()
    return int(float(number) * multipliers[unit])


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance for a module
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance with enhanced methods
    """
    logger = logging.getLogger(name)
    
    # Add console logging methods
    def console_info(message: str):
        """Log message that should appear on console for user"""
        record = logger.makeRecord(
            logger.name, logging.INFO, '', 0, message, (), None
        )
        record.console_output = True
        logger.handle(record)
    
    def console_warning(message: str):
        """Log warning that should appear on console"""
        logger.warning(message)  # Warnings already go to console
    
    def console_error(message: str):
        """Log error that should appear on console"""
        logger.error(message)  # Errors already go to console
    
    def progress_update(message: str):
        """Log progress update for console"""
        record = logger.makeRecord(
            logger.name, logging.INFO, '', 0, message, (), None
        )
        record.console_output = True
        logger.handle(record)
    
    # Attach methods to logger
    logger.console_info = console_info
    logger.console_warning = console_warning
    logger.console_error = console_error
    logger.progress_update = progress_update
    
    return logger


def get_console_logger(name: str) -> logging.Logger:
    """
    Get a logger specifically for console output
    All messages from this logger will appear on console
    
    Args:
        name: Logger name
        
    Returns:
        Console logger instance
    """
    console_name = f"{name}.console"
    return logging.getLogger(console_name)


def configure_from_settings() -> None:
    """Configure logging from application settings"""
    settings = get_settings()
    
    # Determine log file path
    log_file_path = None
    if settings.logging.file:
        if Path(settings.logging.file).is_absolute():
            log_file_path = settings.logging.file
        else:
            log_file_path = settings.get_config_directory() / settings.logging.file
    
    setup_logging(
        level=settings.logging.level,
        log_file=str(log_file_path) if log_file_path else None,
        console_output=settings.logging.console_output,
        colored_output=settings.logging.colored_output,
        max_size=settings.logging.max_size,
        backup_count=settings.logging.backup_count
    )


class LogContext:
    """Context manager for temporary log level changes"""
    
    def __init__(self, logger: logging.Logger, level: str):
        """
        Initialize log context
        
        Args:
            logger: Logger to modify
            level: Temporary log level
        """
        self.logger = logger
        self.new_level = getattr(logging, level.upper())
        self.old_level = logger.level
    
    def __enter__(self):
        """Enter context - set new log level"""
        self.logger.setLevel(self.new_level)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore old log level"""
        self.logger.setLevel(self.old_level)


class OperationLogger:
    """Logger for tracking long-running operations with animated progress bar"""
    
    def __init__(self, logger: logging.Logger, operation_name: str):
        """
        Initialize operation logger
        
        Args:
            logger: Base logger instance
            operation_name: Name of the operation
        """
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None
        self.progress_bar = None
        
    def start(self, message: Optional[str] = None) -> None:
        """Start tracking operation - show to user"""
        import time
        self.start_time = time.time()
        console_msg = message or f"🚀 Starting {self.operation_name}"
        
        # To console (user-facing)
        self.logger.console_info(console_msg)
        
        # To file (technical detail)
        self.logger.info(f"Operation started: {self.operation_name}")
    
    def progress(self, message: str, current: Optional[int] = None, total: Optional[int] = None) -> None:
        """Log progress update with animated progress bar"""
        if current is not None and total is not None:
            # To file (detailed)
            self.logger.info(f"{self.operation_name}: {message} ({current}/{total}, {(current/total)*100:.1f}%)")
            
            # To console - create or update progress bar
            if self.progress_bar is None:
                from tqdm import tqdm
                self.progress_bar = tqdm(
                    total=total,
                    desc="⚡ Downloading",
                    bar_format="{desc} {n}/{total} {bar} {percentage:3.0f}%",
                    ncols=100,
                    colour='cyan',
                    ascii=False
                )
            
            # Update progress bar
            self.progress_bar.n = current
            self.progress_bar.refresh()
            
        else:
            # To file
            self.logger.info(f"{self.operation_name}: {message}")
            
            # To console (simple) - only for non-numeric progress
            if not self.progress_bar:
                self.logger.progress_update(f"⏳ {message}")
    
    def complete(self, message: Optional[str] = None) -> None:
        """Mark operation as complete - close progress bar"""
        if self.progress_bar:
            self.progress_bar.close()
            self.progress_bar = None
        
        if self.start_time:
            import time
            duration = time.time() - self.start_time
            
            # To console (user-friendly)
            console_msg = message or f"✅ {self.operation_name} completed"
            self.logger.console_info(console_msg)
            
            # To file (technical detail)
            self.logger.info(f"Operation completed: {self.operation_name} in {duration:.2f}s")
        else:
            console_msg = message or f"✅ {self.operation_name} completed"
            self.logger.console_info(console_msg)
            self.logger.info(f"Operation completed: {self.operation_name}")
    
    def error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log operation error - close progress bar first"""
        if self.progress_bar:
            self.progress_bar.close()
            self.progress_bar = None
            
        console_msg = f"❌ {self.operation_name} failed: {message}"
        
        # To console (user-facing)
        self.logger.console_error(console_msg)
        
        # To file (detailed with exception)
        if exception:
            self.logger.error(f"Operation failed: {self.operation_name} - {message}", exc_info=exception)
        else:
            self.logger.error(f"Operation failed: {self.operation_name} - {message}")
    
    def warning(self, message: str) -> None:
        """Log operation warning - show to user"""
        # To file
        self.logger.warning(f"{self.operation_name}: {message}")

def create_operation_logger(name: str, operation: str) -> OperationLogger:
    """
    Create operation logger for tracking long-running tasks
    
    Args:
        name: Logger name
        operation: Operation description
        
    Returns:
        OperationLogger instance
    """
    logger = get_logger(name)
    return OperationLogger(logger, operation)


# Performance logging utilities
def log_performance(func):
    """Decorator to log function performance (to file only)"""
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"⚡ {func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.debug(f"💥 {func.__name__} failed after {duration:.3f}s: {e}")
            raise
    
    return wrapper


def log_method_calls(cls):
    """Class decorator to log all method calls (to file only)"""
    import functools
    
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if callable(attr) and not attr_name.startswith('_'):
            setattr(cls, attr_name, log_performance(attr))
    
    return cls


# Initialize logging when module is imported
try:
    configure_from_settings()
except Exception:
    # Fallback to basic logging if settings fail
    setup_logging(level="INFO", console_output=True)