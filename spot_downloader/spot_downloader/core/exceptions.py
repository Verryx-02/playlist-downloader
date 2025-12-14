"""
Exception classes for spot-downloader.

This module defines all custom exceptions used throughout the application.
Each exception is designed to provide clear, actionable error messages
and to distinguish between different failure modes.

Exception Hierarchy:
    SpotDownloaderError (base)
        ConfigError - Configuration file issues
        DatabaseError - JSON database issues
        SpotifyError - Spotify API issues
        YouTubeError - YouTube matching/download issues
        DownloadError - Audio download issues
        MetadataError - Metadata embedding issues
"""


class SpotDownloaderError(Exception):
    """
    Base exception for all spot-downloader errors.
    
    All custom exceptions in this project inherit from this class,
    allowing callers to catch all spot-downloader errors with a single
    except clause if desired.
    
    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional context (e.g., track info, URLs).
    
    Example:
        try:
            # some operation
        except SpotDownloaderError as e:
            logger.error(f"Operation failed: {e.message}")
            if e.details:
                logger.debug(f"Details: {e.details}")
    """
    
    def __init__(self, message: str, details: dict | None = None) -> None:
        """
        Initialize the base exception.
        
        Args:
            message: Human-readable error description that will be shown to the user.
            details: Optional dictionary containing additional context about the error.
                     Useful for logging and debugging. Common keys include:
                     - 'track_id': Spotify track ID involved in the error
                     - 'url': URL that caused the error
                     - 'original_error': The underlying exception if wrapping another error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """Return the error message for display."""
        return self.message


class ConfigError(SpotDownloaderError):
    """
    Raised when there's an issue with the configuration file.
    
    This is a CRITICAL error that should stop program execution.
    
    Common causes:
        - config.yaml not found
        - config.yaml has invalid YAML syntax
        - Required fields missing (client_id, client_secret, output_dir)
        - Invalid field values (e.g., negative thread count)
    
    Example:
        raise ConfigError(
            "Missing required field 'client_id' in config.yaml",
            details={'file_path': '/path/to/config.yaml', 'missing_field': 'client_id'}
        )
    """
    pass


class DatabaseError(SpotDownloaderError):
    """
    Raised when there's an issue with the JSON database.
    
    This is a CRITICAL error that should stop program execution.
    
    Common causes:
        - database.json is corrupted (invalid JSON)
        - Permission denied when reading/writing
        - Disk full
        - Schema validation failed (unexpected structure)
    
    The database file stores all playlist and track state, so corruption
    means we cannot reliably track what has been downloaded.
    
    Example:
        raise DatabaseError(
            "Database file corrupted: invalid JSON syntax",
            details={'file_path': '/path/to/database.json', 'line': 42}
        )
    """
    pass


class SpotifyError(SpotDownloaderError):
    """
    Raised when there's an issue with the Spotify API.
    
    Can be CRITICAL (auth failure) or NON-CRITICAL (single track fetch failure).
    
    Common causes:
        - Invalid or expired credentials (CRITICAL)
        - Rate limiting (may be recoverable with retry)
        - Playlist/track not found or private
        - Network connectivity issues
        - API response parsing failure
    
    Attributes:
        is_auth_error: True if this is an authentication error (CRITICAL).
        is_rate_limit: True if this is a rate limit error (may retry).
    
    Example:
        raise SpotifyError(
            "Failed to fetch playlist: playlist is private",
            details={'playlist_url': url, 'status_code': 403}
        )
    """
    
    def __init__(
        self, 
        message: str, 
        details: dict | None = None,
        is_auth_error: bool = False,
        is_rate_limit: bool = False
    ) -> None:
        """
        Initialize Spotify error with additional flags.
        
        Args:
            message: Human-readable error description.
            details: Optional dictionary with additional context.
            is_auth_error: Set to True if this is an authentication failure.
                          Authentication errors are CRITICAL and should stop execution.
            is_rate_limit: Set to True if this is a rate limit error.
                          Rate limit errors may be recoverable with exponential backoff.
        """
        super().__init__(message, details)
        self.is_auth_error = is_auth_error
        self.is_rate_limit = is_rate_limit


class YouTubeError(SpotDownloaderError):
    """
    Raised when there's an issue with YouTube Music matching or access.
    
    This is typically a NON-CRITICAL error - the program should continue
    with other tracks if one fails to match.
    
    Common causes:
        - No matching video found for a track
        - YouTube Music API returned unexpected response
        - Video is region-locked or age-restricted
        - Network connectivity issues
    
    Example:
        raise YouTubeError(
            "No matching video found for track",
            details={
                'track_name': 'Song Title',
                'artist': 'Artist Name',
                'search_query': 'Artist Name - Song Title'
            }
        )
    """
    pass


class DownloadError(SpotDownloaderError):
    """
    Raised when there's an issue downloading audio from YouTube.
    
    This is typically a NON-CRITICAL error - the program should continue
    with other tracks if one fails to download.
    
    Common causes:
        - Video unavailable or removed
        - Download interrupted (network issue)
        - yt-dlp extraction failed
        - FFmpeg conversion failed
        - Disk full or permission denied
        - Cookie file invalid or expired (for premium quality)
    
    Example:
        raise DownloadError(
            "Failed to download audio: video unavailable",
            details={
                'youtube_url': 'https://youtube.com/watch?v=xxx',
                'track_name': 'Song Title',
                'yt_dlp_error': 'Video unavailable'
            }
        )
    """
    pass


class MetadataError(SpotDownloaderError):
    """
    Raised when there's an issue embedding metadata into audio file.
    
    This is typically a NON-CRITICAL error - the file may still be usable
    even without proper metadata.
    
    Common causes:
        - Audio file corrupted or not found
        - Unsupported audio format (should not happen as we only use M4A)
        - Cover art download failed
        - Mutagen library error
        - Disk full during write
    
    Example:
        raise MetadataError(
            "Failed to embed album cover: download failed",
            details={
                'file_path': '/path/to/song.m4a',
                'cover_url': 'https://i.scdn.co/image/xxx',
                'http_status': 404
            }
        )
    """
    pass


class LyricsError(SpotDownloaderError):
    """
    Raised when there's an issue fetching lyrics.
    
    This is a NON-CRITICAL error - lyrics are optional and failure
    should never prevent the track from being saved.
    
    Common causes:
        - Lyrics not found on any provider
        - Provider blocked the request (anti-bot)
        - Provider website structure changed (scraping broken)
        - Network timeout
    
    Note:
        Lyrics fetching is inherently fragile due to reliance on web scraping.
        This error should be logged but never propagated to stop execution.
    
    Example:
        raise LyricsError(
            "Lyrics not found on any provider",
            details={
                'track_name': 'Song Title',
                'artist': 'Artist Name',
                'providers_tried': ['genius', 'azlyrics', 'musixmatch']
            }
        )
    """
    pass
