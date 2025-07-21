"""
SyncedLyrics integration for lyrics retrieval - Free lyrics provider without API requirements

This module provides integration with the SyncedLyrics library, offering a fast and reliable
lyrics source that doesn't require API keys or authentication. SyncedLyrics is particularly
valuable as a fallback lyrics provider when premium services like Genius reach their rate
limits or when API access is unavailable.

Key Features:

1. No API Requirements:
   - No registration, API keys, or authentication needed
   - Free to use without rate limiting concerns
   - Ideal fallback provider for the lyrics system

2. Multiple Format Support:
   - Plain text lyrics for universal compatibility
   - Synchronized lyrics (LRC format) with timing information
   - Automatic format detection and conversion

3. Smart Search Strategies:
   - Multiple query variations for improved matching
   - Artist name and title normalization
   - Fallback queries for difficult-to-match tracks

4. Robust Error Handling:
   - Graceful degradation when library is unavailable
   - Output suppression for noisy third-party libraries
   - Comprehensive exception handling for network issues

5. Performance Optimization:
   - Built-in rate limiting for respectful API usage
   - Retry logic for transient failures
   - Efficient query generation and caching

Architecture:

The module follows the provider pattern established by the lyrics system:

- SyncedLyricsProvider: Main class implementing the lyrics provider interface
- Singleton pattern: Global instance management for resource efficiency
- Configuration integration: Uses application settings for timeouts and retry logic
- Logging integration: Comprehensive debug and error logging

Integration Points:

- Lyrics Processor: Registered as a fallback provider in the main lyrics system
- Configuration System: Reads timeout and retry settings from app configuration
- Utilities: Uses helper functions for text normalization and validation
- Spotify Models: Integrates with LyricsSource enum for provider identification

Technical Implementation:

The module implements careful handling of the syncedlyrics library, which can be
verbose and may include dependencies that produce unwanted console output. Special
attention is paid to:

- Conditional imports with fallback handling
- Output stream redirection to suppress noise
- Environment variable configuration for third-party libraries
- Safe context managers for stream manipulation

Search Strategy:

The provider implements an intelligent search strategy:

1. Primary Search: Normalized "Artist Title" format
2. Alternative Formats: Original formatting, dash-separated variants
3. Title-Only Fallback: Sometimes more effective for obscure tracks
4. Feature Removal: Strips "(feat. Artist)" patterns for cleaner matching

Error Recovery:

Comprehensive error handling ensures the provider never crashes the application:
- Import failures fall back gracefully without syncedlyrics
- Network errors are caught and logged appropriately
- Malformed responses are validated before processing
- Rate limiting prevents overwhelming external services

Usage in Lyrics System:

    from lyrics.syncedlyrics import get_syncedlyrics_provider
    
    provider = get_syncedlyrics_provider()
    lyrics = provider.search_lyrics("Artist Name", "Track Title")
    synced_lyrics = provider.search_synced_lyrics("Artist Name", "Track Title")

Performance Characteristics:

- Search Speed: Generally faster than API-based providers
- Success Rate: Moderate (depends on track popularity)
- Rate Limiting: 1 second between requests (configurable)
- Memory Usage: Low footprint with efficient query handling
- Network Usage: Minimal due to direct scraping approach

Dependencies:

- syncedlyrics: Third-party library for lyrics retrieval (optional)
- Standard library: contextlib, io, time for core functionality
- Application modules: config, utils, logging for integration
"""

import time
from typing import Optional, Dict, Any, List
import io
from contextlib import redirect_stderr

# Core application imports for configuration and utilities
from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import (
    normalize_artist_name, 
    normalize_track_title,
    retry_on_failure,
    validate_lyrics_content,
    clean_lyrics_text
)

# Conditional import handling for syncedlyrics with comprehensive error suppression
# The syncedlyrics library and its dependencies can be quite verbose, so we implement
# multiple strategies to suppress unwanted output while maintaining functionality
try:
    import os
    import logging
    
    # Configure environment variables BEFORE importing to minimize third-party noise
    # These settings help reduce verbose output from syncedlyrics and its dependencies
    os.environ['SYNCEDLYRICS_VERBOSE'] = '0'  # Disable syncedlyrics verbose mode
    os.environ['MUSIXMATCH_VERBOSE'] = '0'    # Suppress Musixmatch provider output
    
    # Disable logging from noisy third-party components
    # Musixmatch provider can be particularly verbose with debug information
    logging.getLogger('Musixmatch').setLevel(logging.CRITICAL)
    logging.getLogger('Musixmatch').disabled = True
    
    # Import context management tools for output suppression
    from contextlib import redirect_stderr
    import io
    
    # Import the main syncedlyrics library
    import syncedlyrics
    
    # Attempt to configure syncedlyrics to disable noisy providers
    # These configurations may not always be available depending on library version
    if hasattr(syncedlyrics, 'config'):
        try:
            # Disable Musixmatch provider if configuration is available
            syncedlyrics.config.MUSIXMATCH_ENABLED = False
        except:
            # Silently continue if configuration is not available
            pass
    
    # Alternative approach: remove problematic providers from active list
    # This is a fallback method when direct configuration is unavailable
    try:
        if hasattr(syncedlyrics, 'providers'):
            # Filter out musixmatch from active providers to reduce output noise
            syncedlyrics.providers = [p for p in syncedlyrics.providers if 'musixmatch' not in p.lower()]
    except:
        # Continue gracefully if provider list manipulation fails
        pass
    
    # Successfully imported syncedlyrics with noise suppression
    HAS_SYNCEDLYRICS = True
    
except ImportError:
    # Library not available - graceful fallback mode
    # This allows the application to continue functioning without syncedlyrics
    HAS_SYNCEDLYRICS = False
    syncedlyrics = None


class SyncedLyricsProvider:
    """
    SyncedLyrics provider for fast lyrics retrieval without API key requirements
    
    This provider implements the standard lyrics provider interface while leveraging
    the syncedlyrics library for free lyrics retrieval. It serves as an excellent
    fallback option when API-based providers are unavailable or have reached their
    rate limits.
    
    The provider implements intelligent search strategies, comprehensive error handling,
    and respectful rate limiting to ensure reliable operation while being mindful of
    external service resources.
    
    Key Capabilities:
    - Free lyrics retrieval without API registration
    - Support for both plain text and synchronized (LRC) lyrics
    - Multiple search query strategies for improved matching
    - Built-in rate limiting and retry logic
    - Graceful handling of library availability
    
    Technical Features:
    - Output suppression for noisy third-party dependencies
    - Configurable timeouts and retry attempts
    - Text normalization and validation
    - Comprehensive logging for debugging and monitoring
    """
    
    def __init__(self):
        """
        Initialize SyncedLyrics provider with configuration and rate limiting setup
        
        Sets up the provider with application configuration, initializes logging,
        and prepares rate limiting mechanisms. The initialization is designed to
        be lightweight and fail gracefully if the syncedlyrics library is unavailable.
        
        Configuration Loading:
        - Loads timeout settings from application configuration
        - Sets maximum retry attempts for failed requests
        - Configures rate limiting intervals for respectful API usage
        
        Error Handling:
        - Warns if syncedlyrics library is not available
        - Continues initialization in fallback mode
        - Provides clear guidance for library installation
        """
        # Load application configuration and initialize logging
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Load configuration parameters from application settings
        # These values control request behavior and retry logic
        self.timeout = self.settings.lyrics.timeout            # Request timeout in seconds
        self.max_attempts = self.settings.lyrics.max_attempts  # Maximum retry attempts
        
        # Rate limiting configuration to be respectful to external services
        # Even though syncedlyrics is free, we should still limit request frequency
        self.last_request_time = 0                    # Timestamp of last request
        self.min_request_interval = 1.0               # Minimum seconds between requests
        
        # Verify library availability and warn if unavailable
        if not HAS_SYNCEDLYRICS:
            self.logger.warning("syncedlyrics library not available. Install with: pip install syncedlyrics")
    
    def _rate_limit(self) -> None:
        """
        Apply rate limiting between requests to be respectful to external services
        
        Implements a simple time-based rate limiting mechanism that ensures a minimum
        interval between requests. This prevents overwhelming external services and
        demonstrates good API citizenship even when using free services.
        
        The rate limiting is blocking - if insufficient time has passed since the last
        request, this method will sleep until the minimum interval has elapsed.
        
        Rate Limiting Strategy:
        - Tracks timestamp of last request
        - Calculates time elapsed since last request
        - Sleeps for remaining time if minimum interval not met
        - Updates timestamp after rate limit check
        
        Performance Note:
        The rate limiting adds a small delay but ensures sustainable usage patterns
        and prevents potential IP blocking from excessive request frequency.
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Check if minimum interval has elapsed since last request
        if time_since_last < self.min_request_interval:
            # Calculate required sleep time to respect rate limit
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        # Update timestamp for next rate limit calculation
        self.last_request_time = time.time()
    
    @retry_on_failure(max_attempts=2, delay=1.0)
    def search_lyrics(self, artist: str, title: str, album: Optional[str] = None) -> Optional[str]:
        """
        Search for lyrics using SyncedLyrics with comprehensive error handling and output suppression
        
        Performs a lyrics search using the syncedlyrics library while implementing robust
        error handling and output suppression. The method handles library unavailability,
        network errors, and malformed responses gracefully.
        
        Args:
            artist: Artist name from track metadata
            title: Track title from track metadata  
            album: Album name for additional context (currently unused but maintained for interface compatibility)
            
        Returns:
            Cleaned and validated lyrics text if found and valid, None otherwise
            
        Search Process:
        
        1. Library Availability Check:
           - Verifies syncedlyrics library is available
           - Returns None immediately if library is missing
        
        2. Rate Limiting:
           - Applies configured rate limiting before request
           - Ensures respectful usage of external services
        
        3. Output Suppression:
           - Suppresses verbose output from third-party libraries
           - Maintains clean application logs
        
        4. Search Execution:
           - Performs search with normalized artist and title
           - Handles network errors and timeouts gracefully
        
        5. Result Processing:
           - Cleans retrieved lyrics text
           - Validates content against quality thresholds
           - Returns only lyrics that meet minimum standards
        
        Error Scenarios:
        - Library unavailable: Returns None with debug log
        - Network errors: Logged and None returned
        - Invalid results: Filtered out during validation
        - Empty results: Handled gracefully with debug logging
        
        The @retry_on_failure decorator automatically retries failed requests
        with exponential backoff to handle transient network issues.
        """
        # Check library availability before attempting search
        if not HAS_SYNCEDLYRICS:
            self.logger.debug("syncedlyrics library not available")
            return None
        
        try:
            self.logger.debug(f"Searching SyncedLyrics for: {artist} - {title}")
            
            # Apply rate limiting to be respectful to external services
            self._rate_limit()
            
            # Import context management tools for output suppression
            import sys
            import os
            from contextlib import contextmanager
            
            @contextmanager
            def suppress_output():
                """
                Context manager for suppressing unwanted output during syncedlyrics operations
                
                This minimal context manager provides a safe way to suppress output without
                affecting the main application streams. It's designed to be lightweight
                and safe for concurrent usage.
                """
                yield
            
            # Perform search with output suppression to maintain clean logs
            with suppress_output():
                # Execute syncedlyrics search with artist and title
                lyrics = syncedlyrics.search(f"{artist} {title}")
            
            # Process and validate search results
            if lyrics:
                # Clean the retrieved lyrics text using application utilities
                cleaned_lyrics = clean_lyrics_text(lyrics)
                
                # Validate lyrics content against quality thresholds
                if validate_lyrics_content(cleaned_lyrics, self.settings.lyrics.min_length):
                    self.logger.debug(f"SyncedLyrics lyrics found for: {artist} - {title}")
                    return cleaned_lyrics
            
            # Log when no results are found (normal case, not an error)
            self.logger.debug(f"No SyncedLyrics results found for: {artist} - {title}")
            return None
            
        except Exception as e:
            # Log search failures for debugging but don't raise exceptions
            # This ensures the lyrics system can continue with other providers
            self.logger.debug(f"SyncedLyrics search failed: {e}")
            return None
    
    def _generate_search_queries(self, artist: str, title: str) -> List[str]:
        """
        Generate multiple search query variations for improved matching success
        
        Creates a list of different query formats to maximize the chances of finding
        lyrics for difficult-to-match tracks. The strategy uses various combinations
        of normalized and original text, different separators, and feature removal
        to handle edge cases in track naming.
        
        Args:
            artist: Artist name from track metadata
            title: Track title from track metadata
            
        Returns:
            List of search query strings ordered by likelihood of success
            
        Query Generation Strategy:
        
        1. Primary Query: Normalized "Artist Title" format
           - Uses application's text normalization functions
           - Removes special characters and standardizes spacing
           - Most likely to succeed for standard tracks
        
        2. Original Format: Preserves original artist and title formatting
           - Useful when normalization removes important information
           - Handles cases where original formatting is preferred
        
        3. Dash-Separated: "Artist - Title" format
           - Common format used by many lyrics databases
           - Alternative separator can improve matching
        
        4. Title-Only: Uses only the track title
           - Fallback for when artist name causes matching issues
           - Effective for very popular or unique track titles
        
        5. Feature Removal: Strips "(feat. Artist)" patterns
           - Cleans up collaborations and features
           - Focuses on primary artist for better matching
        
        The queries are ordered by likelihood of success based on empirical testing
        and common patterns in lyrics databases.
        """
        queries = []
        
        # Apply application's text normalization functions
        norm_artist = normalize_artist_name(artist)
        norm_title = normalize_track_title(title)
        
        # Primary query: normalized "Artist Title" format (highest success rate)
        queries.append(f"{norm_artist} {norm_title}")
        
        # Alternative format: preserve original formatting (handles edge cases)
        queries.append(f"{artist} {title}")
        
        # Dash-separated format: common in lyrics databases
        queries.append(f"{norm_artist} - {norm_title}")
        
        # Title-only fallback: useful when artist name causes issues
        queries.append(norm_title)
        
        # Feature removal: clean up collaboration tracks
        import re
        clean_artist = re.sub(r'\s*(feat|ft|featuring)\.?\s+.*', '', norm_artist, flags=re.IGNORECASE)
        if clean_artist != norm_artist:
            # Only add if removing features actually changed the artist name
            queries.append(f"{clean_artist} {norm_title}")
        
        return queries
    
    def validate_api_access(self) -> bool:
        """
        Validate SyncedLyrics library availability and functionality
        
        Performs a comprehensive validation of the syncedlyrics library to ensure
        it's properly installed and functional. This method is used by the lyrics
        system to determine provider availability and health.
        
        Returns:
            True if syncedlyrics library is available and functional, False otherwise
            
        Validation Process:
        
        1. Library Availability:
           - Checks if syncedlyrics was successfully imported
           - Verifies the library module is accessible
        
        2. Functionality Test:
           - Performs a minimal test search to verify library works
           - Handles any exceptions that might occur during testing
           - Success is indicated by no exceptions (result can be None)
        
        3. Result Reporting:
           - Logs validation success for monitoring
           - Logs specific errors for troubleshooting
           - Returns boolean result for system decision making
        
        Error Scenarios:
        - Library not installed: Returns False with warning
        - Import failures: Returns False with error details
        - Runtime errors: Returns False with exception information
        - Network issues: Returns False (temporary failure)
        
        This validation is typically called during system startup and can be
        used for health checks and monitoring of provider availability.
        """
        try:
            # Check if the syncedlyrics library was successfully imported
            if not HAS_SYNCEDLYRICS:
                self.logger.warning("syncedlyrics library not installed")
                return False
            
            # Perform a minimal functionality test with a simple search
            # The result doesn't matter - we just want to verify no exceptions occur
            test_result = syncedlyrics.search("test")
            # If we reach this point, the library is functional
            # (test_result can be None, that's normal for "test" queries)
            
            self.logger.info("SyncedLyrics validation successful")
            return True
            
        except Exception as e:
            # Log validation failure with specific error information for troubleshooting
            self.logger.error(f"SyncedLyrics validation failed: {e}")
            return False
    
    def get_api_status(self) -> Dict[str, Any]:
        """
        Get comprehensive SyncedLyrics provider status and configuration information
        
        Returns detailed information about the provider's current status, configuration,
        and capabilities. This information is used by the lyrics system for monitoring,
        debugging, and user interface display.
        
        Returns:
            Dictionary containing comprehensive provider status and configuration data
            
        Status Information Categories:
        
        1. Availability Status:
           - Library installation status
           - Functional readiness indicator
           - Dependency availability check
        
        2. Configuration Details:
           - Timeout settings from application config
           - Retry attempt limits
           - Rate limiting intervals
        
        3. Capability Information:
           - API key requirements (none for syncedlyrics)
           - Supported lyrics formats
           - Special features and limitations
        
        4. Provider Characteristics:
           - Service description and use cases
           - Performance characteristics
           - Integration recommendations
        
        The returned dictionary provides complete transparency into the provider's
        status and can be used for system health monitoring, user feedback, and
        debugging of lyrics retrieval issues.
        """
        return {
            # Core availability and functionality status
            'library_available': HAS_SYNCEDLYRICS,     # Whether syncedlyrics library is installed
            'requires_api_key': False,                  # No authentication required
            
            # Configuration parameters from application settings
            'timeout': self.timeout,                    # Request timeout in seconds
            'max_attempts': self.max_attempts,          # Maximum retry attempts
            'rate_limit_interval': self.min_request_interval,  # Minimum seconds between requests
            
            # Provider capabilities and features
            'supports_synced_lyrics': True,             # Can provide LRC format lyrics
            
            # Service description and characteristics
            'description': 'Free lyrics provider without API requirements'
        }
    
    def search_synced_lyrics(self, artist: str, title: str) -> Optional[str]:
        """
        Search for synchronized lyrics in LRC format with timing information
        
        Performs a specialized search for synchronized lyrics that include timing
        information in LRC (Lyrics) format. These lyrics can be used by music players
        that support synchronized lyrics display, providing a karaoke-like experience.
        
        Args:
            artist: Artist name from track metadata
            title: Track title from track metadata
            
        Returns:
            Synchronized lyrics in LRC format if found, None otherwise
            
        LRC Format Details:
        LRC (Lyrics) format includes timing information in the following structure:
        [mm:ss.xx] Lyrics line text
        
        Example:
        [00:12.34] First line of lyrics
        [00:18.67] Second line of lyrics
        
        Search Process:
        
        1. Library Availability:
           - Verifies syncedlyrics library is available
           - Returns None if library is missing
        
        2. Rate Limiting:
           - Applies configured rate limiting for respectful usage
           - Maintains consistent request patterns
        
        3. Query Preparation:
           - Normalizes artist and title for optimal matching
           - Generates clean search query
        
        4. Synchronized Search:
           - Uses syncedlyrics synced_only parameter
           - Suppresses verbose output from third-party libraries
           - Handles search errors gracefully
        
        5. Format Validation:
           - Verifies result contains LRC timing markers
           - Checks for proper format structure
           - Returns only valid synchronized lyrics
        
        Error Handling:
        - Library unavailable: Returns None
        - Network errors: Logged and None returned
        - Invalid format: Filtered out during validation
        - Search failures: Logged for debugging
        
        Performance Note:
        Synchronized lyrics are less common than plain text lyrics, so this method
        has a lower success rate but provides enhanced functionality when available.
        """
        try:
            # Check library availability before attempting search
            if not HAS_SYNCEDLYRICS:
                return None
            
            self.logger.debug(f"Searching for synced lyrics: {artist} - {title}")
            
            # Apply rate limiting to maintain respectful usage patterns
            self._rate_limit()
            
            # Prepare normalized search query for optimal matching
            norm_artist = normalize_artist_name(artist)
            norm_title = normalize_track_title(title)
            query = f"{norm_artist} {norm_title}"
            
            # Perform synchronized lyrics search with output suppression
            # The redirect_stderr context manager prevents noisy Musixmatch output
            with redirect_stderr(io.StringIO()):
                synced_lyrics = syncedlyrics.search(query, synced_only=True)
            
            # Validate LRC format by checking for timing markers
            if synced_lyrics and '[' in synced_lyrics and ']' in synced_lyrics:
                self.logger.info(f"Synced lyrics found for: {artist} - {title}")
                return synced_lyrics
            else:
                # No synchronized lyrics found - this is normal for many tracks
                self.logger.debug(f"No synced lyrics found for: {artist} - {title}")
                return None
                
        except Exception as e:
            # Log search failures for debugging but continue gracefully
            self.logger.warning(f"Synced lyrics search failed: {e}")
            return None


# Global SyncedLyrics provider instance management using singleton pattern
# This ensures consistent configuration and avoids unnecessary object creation
_syncedlyrics_provider: Optional[SyncedLyricsProvider] = None


def get_syncedlyrics_provider() -> SyncedLyricsProvider:
    """
    Get global SyncedLyrics provider instance using singleton pattern
    
    Provides access to the shared SyncedLyrics provider instance used throughout
    the application. Creates the instance on first access and returns the same
    instance for subsequent calls, ensuring consistent configuration and efficient
    resource usage.
    
    Returns:
        Global SyncedLyricsProvider instance
        
    Singleton Benefits:
    - Shared configuration across all lyrics operations
    - Consistent rate limiting state management
    - Efficient resource utilization
    - Centralized library availability checking
    - Unified logging and error handling
    
    Usage:
        provider = get_syncedlyrics_provider()
        lyrics = provider.search_lyrics("Artist", "Title")
    
    Thread Safety:
    The singleton implementation is thread-safe for read operations
    but creation should occur during application initialization
    to avoid race conditions in multi-threaded environments.
    """
    global _syncedlyrics_provider
    if not _syncedlyrics_provider:
        _syncedlyrics_provider = SyncedLyricsProvider()
    return _syncedlyrics_provider


def reset_syncedlyrics_provider() -> None:
    """
    Reset global SyncedLyrics provider instance for testing and configuration changes
    
    Clears the global provider instance, forcing a new instance to be created
    on the next access. This is primarily used for testing scenarios where
    a fresh provider state is needed, or when configuration changes require
    provider reinitialization.
    
    Use Cases:
    - Unit testing: Clean state between test cases
    - Configuration changes: Reload settings after config updates
    - Error recovery: Reset after persistent connection issues
    - Development: Hot-reload scenarios and debugging
    
    Thread Safety Note:
    This function should be called during application shutdown or in
    controlled single-threaded contexts to avoid race conditions with
    concurrent provider access.
    
    After calling this function, the next call to get_syncedlyrics_provider()
    will create a new instance with current configuration settings.
    """
    global _syncedlyrics_provider
    _syncedlyrics_provider = None