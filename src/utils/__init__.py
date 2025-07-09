# src/utils/__init__.py
"""
Utilities package
Common helpers, logging, and utility functions
"""

from .logger import (
    get_logger, 
    configure_from_settings, 
    setup_logging,
    OperationLogger,
    create_operation_logger,
    log_performance,
    get_current_log_file
)
from .helpers import (
    sanitize_filename,
    format_duration,
    format_file_size,
    calculate_similarity,
    normalize_artist_name,
    normalize_track_title,
    create_search_query,
    clean_lyrics_text,
    validate_lyrics_content,
    retry_on_failure,
    ensure_directory,
    safe_path_join,
    get_file_extension,
    parse_duration_string,
    get_current_timestamp,
    format_timestamp,
    create_backup_filename
)

__all__ = [
    # Logger exports
    'get_logger',
    'configure_from_settings',
    'setup_logging', 
    'OperationLogger',
    'create_operation_logger',
    'log_performance',
    
    # Helper exports
    'sanitize_filename',
    'format_duration',
    'format_file_size',
    'calculate_similarity',
    'normalize_artist_name',
    'normalize_track_title',
    'create_search_query',
    'clean_lyrics_text',
    'validate_lyrics_content',
    'retry_on_failure',
    'ensure_directory',
    'safe_path_join',
    'get_file_extension', 
    'parse_duration_string',
    'get_current_timestamp',
    'format_timestamp',
    'create_backup_filename'

    'reconfigure_logging_for_playlist',
    'get_current_log_file'
]