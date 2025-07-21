"""
Spotify integration package - Central hub for Spotify Web API communication and data management

This package provides a comprehensive interface for interacting with the Spotify Web API,
handling authentication, data retrieval, and model definitions for the Playlist-Downloader
application. It implements a clean separation of concerns with dedicated modules for
client operations and data models.

Architecture Overview:

The package is organized into two main components:

1. Client Module (client.py):
   - Manages Spotify Web API authentication and communication
   - Implements rate limiting and error handling for API requests
   - Provides high-level methods for playlist and track operations
   - Handles OAuth flow and token management

2. Models Module (models.py):
   - Defines data classes for Spotify entities (playlists, tracks, artists, albums)
   - Provides enums for status tracking and configuration
   - Implements data validation and serialization logic
   - Supports both Spotify data and download operation metadata

Key Components:

Client Infrastructure:
- SpotifyClient: Main client class for API communication
- get_spotify_client(): Factory function implementing singleton pattern
- reset_spotify_client(): Utility for testing and configuration changes

Data Models:
- SpotifyPlaylist, SpotifyTrack, SpotifyArtist, SpotifyAlbum: Core Spotify entities
- PlaylistTrack: Enhanced track model with download metadata
- TrackStatus, LyricsStatus: Enums for operation state tracking
- LyricsSource: Configuration for lyrics provider selection
- AudioFormat: Output format specifications
- DownloadStats: Progress and performance monitoring

Design Patterns:

1. Singleton Pattern:
   - Single client instance shared across the application
   - Prevents multiple authentication flows and API quota waste
   - Enables centralized configuration and connection management

2. Factory Pattern:
   - get_spotify_client() provides controlled instance creation
   - Allows for dependency injection and testing flexibility
   - Supports configuration-based client initialization

3. Data Transfer Object (DTO) Pattern:
   - Models serve as DTOs for API response data
   - Provide type safety and validation for external data
   - Enable clean separation between API layer and business logic

Integration Points:

- Configuration System: Reads API credentials and settings
- Lyrics Package: Provides source enums and status tracking
- Audio Package: Uses format specifications and download models
- Download Engine: Consumes track and playlist models
- Progress Tracking: Uses status enums and statistics models

Usage Example:

    from spotify import get_spotify_client, SpotifyPlaylist
    
    # Get authenticated client instance
    client = get_spotify_client()
    
    # Retrieve playlist data
    playlist = client.get_playlist("playlist_id")
    
    # Access structured data
    for track in playlist.tracks:
        print(f"{track.artist} - {track.title}")

Error Handling:

The package implements comprehensive error handling for:
- Network connectivity issues
- API rate limiting and quota management
- Authentication token expiration
- Invalid playlist or track IDs
- Service unavailability scenarios

Thread Safety:

All components are designed for concurrent access in multi-threaded
download operations, with appropriate synchronization for shared resources
and stateful operations like token refresh.

Dependencies:

- Spotify Web API: External service for data retrieval
- requests: HTTP client for API communication
- dataclasses: Type-safe model definitions
- enum: Status and configuration constants
- typing: Type hints for better code documentation
"""

# Core client functionality for Spotify Web API communication
# These components handle authentication, request management, and API interaction
from .client import get_spotify_client, reset_spotify_client, SpotifyClient

# Data models and enums for Spotify entities and download operations
# This comprehensive set covers all data structures used throughout the application
from .models import (
    # Core Spotify entity models representing API response data
    SpotifyPlaylist,   # Complete playlist metadata with tracks and ownership info
    SpotifyTrack,      # Individual track with audio features and metadata
    SpotifyArtist,     # Artist information including popularity and genres
    SpotifyAlbum,      # Album details with release info and track listings
    
    # Enhanced models for download operations with additional metadata
    PlaylistTrack,     # Track with download status, file paths, and processing info
    
    # Status tracking enums for operation state management
    TrackStatus,       # Download states: pending, downloading, completed, failed, skipped
    LyricsStatus,      # Lyrics retrieval states: found, not_found, instrumental, error
    
    # Configuration enums for service selection and output formatting
    LyricsSource,      # Lyrics provider selection: genius, syncedlyrics, etc.
    AudioFormat,       # Output format specification: mp3, flac, m4a with quality settings
    
    # Statistics and monitoring models for progress tracking
    DownloadStats      # Performance metrics, success rates, and operation summaries
)

# Public API definition - Controls what components are available when importing the package
# This list defines the complete public interface and ensures clean API boundaries
__all__ = [
    # === CLIENT COMPONENTS ===
    # Factory function for obtaining configured client instances
    'get_spotify_client',
    # Utility function for resetting client state (useful for testing and config changes)
    'reset_spotify_client', 
    # Main client class for direct instantiation when needed
    'SpotifyClient',
    
    # === CORE SPOTIFY DATA MODELS ===
    # Primary entities representing Spotify Web API responses
    'SpotifyPlaylist',   # Playlist container with metadata and track collections
    'SpotifyTrack',      # Individual track with full metadata and audio features
    'SpotifyArtist',     # Artist profile with biographical and statistical data
    'SpotifyAlbum',      # Album information with track listings and release details
    
    # === ENHANCED DOWNLOAD MODELS ===
    # Extended models that include download operation metadata
    'PlaylistTrack',     # Track enhanced with download status and file information
    
    # === STATUS AND CONFIGURATION ENUMS ===
    # State management for download and processing operations
    'TrackStatus',       # Track download operation states and outcomes
    'LyricsStatus',      # Lyrics retrieval operation results and error states
    'LyricsSource',      # Available lyrics provider services and preferences
    'AudioFormat',       # Supported output formats with quality and encoding options
    
    # === MONITORING AND STATISTICS ===
    # Progress tracking and performance analysis models
    'DownloadStats'      # Comprehensive statistics for operation monitoring and reporting
]