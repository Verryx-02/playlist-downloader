"""
Logging configuration for spot-downloader.

This module sets up the logging system with multiple outputs:
    - Console: Real-time progress with tqdm-compatible formatting
    - log_full.txt: Complete log of all events (DEBUG and above)
    - log_errors.txt: Only ERROR and CRITICAL level messages
    - report.txt: Failed track names with Spotify URLs (human-readable list)

The logging system follows the principle: everything to screen is also saved
to file, then filtered into specialized files.

Log File Locations:
    All log files are created in the output directory specified in config.yaml.
    Files are overwritten on each run (no rotation).

Usage:
    from spot_downloader.core.logger import setup_logging, get_logger
    
    setup_logging(output_dir)  # Call once at startup
    logger = get_logger(__name__)  # Get logger for each module
    
    logger.info("Starting download")
    logger.error("Download failed", extra={'track': 'Song Name', 'url': 'spotify:...'})
"""

import logging
import sys
from pathlib import Path
from typing import TextIO

from tqdm import tqdm


# Log file names (created in output directory)
LOG_FULL_FILENAME = "log_full.txt"
LOG_ERRORS_FILENAME = "log_errors.txt"
REPORT_FILENAME = "report.txt"

# Log format for file output (detailed with timestamp)
FILE_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log format for console output (compact, tqdm-friendly)
CONSOLE_LOG_FORMAT = "%(levelname)s: %(message)s"


class TqdmLoggingHandler(logging.Handler):
    """
    Custom logging handler that writes to console without breaking tqdm progress bars.
    
    tqdm progress bars write to stderr and use carriage returns to update in-place.
    Standard logging to stderr can interfere with this, causing visual glitches.
    This handler uses tqdm.write() which properly coordinates with active progress bars.
    
    Attributes:
        stream: The output stream (defaults to sys.stderr).
    
    Behavior:
        - Formats the log record using the handler's formatter
        - Writes using tqdm.write() to avoid progress bar corruption
        - Messages appear above any active progress bars
    
    Example:
        handler = TqdmLoggingHandler()
        handler.setFormatter(logging.Formatter(CONSOLE_LOG_FORMAT))
        logger.addHandler(handler)
    """
    
    def __init__(self, stream: TextIO = sys.stderr) -> None:
        """
        Initialize the tqdm-compatible handler.
        
        Args:
            stream: Output stream for log messages. Defaults to stderr
                    which is where tqdm also writes by default.
        """
        super().__init__()
        self.stream = stream
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record using tqdm.write() for proper progress bar compatibility.
        
        Args:
            record: The log record to emit.
        
        Behavior:
            1. Format the record using the handler's formatter
            2. Write to stream using tqdm.write()
            3. Handle any exceptions by calling handleError()
        
        Thread Safety:
            This method is thread-safe as tqdm.write() handles synchronization.
        """
        raise NotImplementedError("Contract only - implementation pending")


class FailedTrackHandler(logging.Handler):
    """
    Custom handler that captures failed track information for the report file.
    
    This handler listens for log records that contain track failure information
    and writes them to report.txt in a simple, human-readable format:
    
        Song Title - Artist Name
        https://open.spotify.com/track/xxxxx
        
        Another Song - Another Artist
        https://open.spotify.com/track/yyyyy
    
    The handler looks for specific extra fields in log records:
        - 'failed_track_name': The name of the track that failed
        - 'failed_track_artist': The artist name
        - 'failed_track_url': The Spotify URL
    
    Only records containing these fields are written to the report.
    
    Attributes:
        report_file: Open file handle for report.txt
    
    Usage:
        logger.error(
            "Download failed for track",
            extra={
                'failed_track_name': 'Song Title',
                'failed_track_artist': 'Artist Name', 
                'failed_track_url': 'https://open.spotify.com/track/xxx'
            }
        )
    """
    
    def __init__(self, report_path: Path) -> None:
        """
        Initialize the failed track handler.
        
        Args:
            report_path: Path to the report.txt file.
                         File will be created/overwritten.
        
        Raises:
            IOError: If the file cannot be opened for writing.
        """
        super().__init__()
        self.report_path = report_path
        self.report_file: TextIO | None = None
    
    def open(self) -> None:
        """
        Open the report file for writing.
        
        Called by setup_logging() after handler is created.
        File is opened in write mode (overwrites existing content).
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Write failed track info to report if present in the log record.
        
        Args:
            record: The log record to check and potentially write.
        
        Behavior:
            1. Check if record has 'failed_track_name' attribute
            2. If not present, ignore the record (return immediately)
            3. If present, extract track info and write to report file
            4. Format: "Track Name - Artist Name\\nSpotify URL\\n\\n"
        
        Thread Safety:
            Writes are NOT automatically thread-safe. The file should be
            protected by a lock if multiple threads may log simultaneously.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def close(self) -> None:
        """
        Close the report file handle.
        
        Called automatically when logging is shut down.
        Safe to call multiple times.
        """
        raise NotImplementedError("Contract only - implementation pending")


class ErrorOnlyFilter(logging.Filter):
    """
    Filter that only allows ERROR and CRITICAL level records.
    
    Used by the error log file handler to exclude DEBUG, INFO, and WARNING.
    
    Example:
        handler.addFilter(ErrorOnlyFilter())
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Check if the record should be logged.
        
        Args:
            record: The log record to check.
        
        Returns:
            True if record.levelno >= ERROR (40), False otherwise.
        """
        raise NotImplementedError("Contract only - implementation pending")


def setup_logging(output_dir: Path) -> None:
    """
    Configure the logging system for the application.
    
    This function should be called ONCE at application startup, after
    the configuration is loaded but before any other operations.
    
    Args:
        output_dir: Directory where log files will be created.
                    The directory will be created if it doesn't exist.
    
    Behavior:
        1. Create output_dir if it doesn't exist
        2. Configure root logger level to DEBUG
        3. Create and configure console handler (TqdmLoggingHandler)
           - Level: INFO
           - Format: Compact (no timestamp)
        4. Create and configure full log file handler
           - Path: output_dir/log_full.txt
           - Level: DEBUG
           - Format: Full with timestamp
        5. Create and configure error log file handler
           - Path: output_dir/log_errors.txt
           - Level: DEBUG (filtered to ERROR+ by ErrorOnlyFilter)
           - Format: Full with timestamp
        6. Create and configure failed track handler
           - Path: output_dir/report.txt
           - Custom format (track name, artist, URL)
        7. Add all handlers to root logger
    
    File Handling:
        - All log files are opened in write mode (overwrite existing)
        - Files use UTF-8 encoding
        - Files are closed automatically on program exit
    
    Thread Safety:
        This function is NOT thread-safe. Call it once from the main
        thread before starting any worker threads.
    
    Example:
        from spot_downloader.core.config import load_config
        from spot_downloader.core.logger import setup_logging
        
        config = load_config()
        setup_logging(config.output.directory)
    """
    raise NotImplementedError("Contract only - implementation pending")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    This is a convenience wrapper around logging.getLogger() that ensures
    consistent logger naming throughout the application.
    
    Args:
        name: The logger name, typically __name__ of the calling module.
              This creates a hierarchy like 'spot_downloader.core.config'.
    
    Returns:
        logging.Logger: A logger instance configured by setup_logging().
    
    Example:
        # In any module:
        from spot_downloader.core.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info("Module initialized")
        logger.error("Something failed", extra={'detail': 'value'})
    
    Note:
        Loggers obtained before setup_logging() is called will have no
        handlers and will not produce output. Always call setup_logging()
        first during application startup.
    """
    return logging.getLogger(name)


def log_failed_track(
    logger: logging.Logger,
    track_name: str,
    artist: str,
    spotify_url: str,
    error_message: str
) -> None:
    """
    Log a failed track with proper formatting for the report file.
    
    This is a convenience function that logs a track failure with the
    correct extra fields for the FailedTrackHandler to pick up.
    
    Args:
        logger: The logger to use for the message.
        track_name: The name of the track that failed.
        artist: The artist name.
        spotify_url: The Spotify URL for the track.
        error_message: Description of why the track failed.
    
    Behavior:
        Logs an ERROR level message with the error_message, and attaches
        extra fields that FailedTrackHandler will use to write to report.txt.
    
    Example:
        log_failed_track(
            logger,
            track_name="Song Title",
            artist="Artist Name",
            spotify_url="https://open.spotify.com/track/xxx",
            error_message="No matching YouTube video found"
        )
        
        # This will:
        # 1. Log "No matching YouTube video found" to console and log_full.txt
        # 2. Log to log_errors.txt (because it's ERROR level)
        # 3. Write to report.txt:
        #    "Song Title - Artist Name
        #     https://open.spotify.com/track/xxx"
    """
    raise NotImplementedError("Contract only - implementation pending")


def shutdown_logging() -> None:
    """
    Properly shut down the logging system.
    
    This function should be called at application exit to ensure all
    log handlers are properly flushed and closed.
    
    Behavior:
        1. Flush all handlers
        2. Close all file handlers
        3. Remove all handlers from root logger
    
    Note:
        This is typically called in a finally block or atexit handler.
        After calling this function, logging will no longer work.
    """
    raise NotImplementedError("Contract only - implementation pending")
