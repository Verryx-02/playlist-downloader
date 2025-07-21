"""
YouTube Music integration package for Playlist-Downloader with comprehensive search and download capabilities

This package provides a complete integration layer between the Playlist-Downloader application
and YouTube Music services, offering sophisticated search algorithms and high-quality audio
download functionality. The package is architected around two primary components that work
in tandem to deliver a seamless music discovery and acquisition experience.

Package Architecture:

The package follows a clean separation of concerns design pattern, dividing functionality
into two specialized modules:

1. **Search Module (searcher.py)**:
   - Intelligent track matching using multiple search strategies
   - Advanced scoring algorithms for result ranking and quality assessment
   - Fallback mechanisms for difficult-to-match tracks
   - Query optimization and refinement techniques

2. **Download Module (downloader.py)**:
   - High-quality audio extraction from YouTube Music content
   - Multiple format support (MP3, M4A, FLAC) with configurable quality settings
   - Progress tracking and download state management
   - Error handling and retry mechanisms for network resilience

Core Components:

**Search System:**
- YouTubeMusicSearcher: Main search engine with intelligent matching capabilities
- SearchResult: Data model representing search results with metadata and scoring
- Factory pattern implementation via get_ytmusic_searcher() for singleton access

**Download System:**
- YouTubeMusicDownloader: Robust downloader with format conversion and quality control
- DownloadResult: Comprehensive result model with status, metadata, and file information
- Factory pattern implementation via get_downloader() for efficient resource management

Integration Points:

This package seamlessly integrates with other Playlist-Downloader components:
- Spotify package: Receives track metadata for search queries
- Audio package: Provides downloaded content for post-processing
- Config package: Retrieves user preferences and quality settings
- Utils package: Utilizes logging, helpers, and validation functions

Performance Considerations:

**Memory Efficiency:**
- Singleton pattern ensures single instances of searcher and downloader
- Lazy initialization reduces startup overhead
- Efficient resource cleanup and garbage collection

**Network Optimization:**
- Connection pooling for multiple download operations
- Intelligent retry strategies with exponential backoff
- Rate limiting compliance with YouTube Music API restrictions

**Concurrent Operations:**
- Thread-safe implementations for parallel processing
- Async/await support for non-blocking operations
- Resource locking mechanisms to prevent conflicts

Usage Patterns:

The package is designed for both simple and advanced use cases:

Basic Usage:
    from ytmusic import get_ytmusic_searcher, get_downloader
    
    # Search for a track
    searcher = get_ytmusic_searcher()
    results = searcher.search_track("Artist Name", "Song Title")
    
    # Download the best match
    downloader = get_downloader()
    download_result = downloader.download_track(results[0])

Advanced Usage:
    # Custom search parameters
    results = searcher.search_track(
        artist="Artist Name",
        title="Song Title", 
        album="Album Name",
        duration=180,
        max_results=10
    )
    
    # Filtered downloads with quality preferences
    download_result = downloader.download_track(
        result=best_result,
        format="m4a",
        quality="high",
        output_path="/custom/path"
    )

Error Handling:

The package implements comprehensive error handling strategies:
- Network connectivity issues with automatic retry
- YouTube Music API changes and rate limiting
- Audio format conversion failures
- File system permission and storage errors

Quality Assurance:

**Testing Strategy:**
- Unit tests for individual component functionality
- Integration tests for cross-module interactions
- Performance tests for large-scale operations
- Mock testing for external API dependencies

**Monitoring and Logging:**
- Detailed operation logging for troubleshooting
- Performance metrics collection and analysis
- User feedback integration for continuous improvement
- Health checks for service availability validation

Security Considerations:

**API Security:**
- Secure handling of YouTube Music API credentials
- Request signing and authentication token management
- Protection against API abuse and rate limit violations

**Data Privacy:**
- No storage of personal user data or listening history
- Temporary file cleanup after download operations
- Secure handling of search queries and metadata

Thread Safety:

All components are designed for safe concurrent operation:
- Thread-safe singleton implementations
- Proper synchronization for shared resources
- Deadlock prevention through consistent lock ordering
- Race condition prevention in critical sections

Dependencies and Requirements:

**Core Dependencies:**
- yt-dlp: Primary YouTube content extraction engine
- mutagen: Audio metadata handling and tag management
- requests: HTTP client for API communications
- asyncio: Asynchronous operation support

**Optional Dependencies:**
- ffmpeg: Advanced audio format conversion capabilities
- librosa: Audio analysis and feature extraction
- numpy: Numerical processing for audio algorithms

Future Extensibility:

The package architecture supports future enhancements:
- Additional streaming service integrations
- Machine learning-based search improvements
- Advanced audio processing capabilities
- Cloud-based processing and storage options
"""

# Import search functionality from the searcher module
# This module provides intelligent track matching and search result ranking
from .searcher import get_ytmusic_searcher, reset_ytmusic_searcher, YouTubeMusicSearcher, SearchResult

# Import download functionality from the downloader module  
# This module handles audio extraction, format conversion, and file management
from .downloader import get_downloader, reset_downloader, YouTubeMusicDownloader, DownloadResult

# Public API definition for the YouTube Music integration package
# This list defines the complete public interface and ensures clean API boundaries
# Following the explicit interface pattern for better maintainability and documentation
__all__ = [
    # === SEARCH COMPONENTS ===
    # Factory function for obtaining configured searcher instances with singleton pattern
    'get_ytmusic_searcher',
    # Utility function for resetting searcher state (useful for testing and configuration changes)
    'reset_ytmusic_searcher',
    # Main searcher class for direct instantiation when factory pattern is not suitable
    'YouTubeMusicSearcher',
    # Data model representing search results with metadata, scoring, and match quality information
    'SearchResult',
    
    # === DOWNLOAD COMPONENTS ===
    # Factory function for obtaining configured downloader instances with resource management
    'get_downloader',
    # Utility function for resetting downloader state (useful for cleanup and testing)
    'reset_downloader', 
    # Main downloader class for direct instantiation and advanced configuration scenarios
    'YouTubeMusicDownloader',
    # Data model representing download results with status, file information, and error details
    'DownloadResult'
]