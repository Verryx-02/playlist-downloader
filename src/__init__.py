"""
Playlist-Downloader: Download Spotify playlists with YouTube Music + Lyrics
A comprehensive tool for downloading Spotify playlists locally with high-quality audio and lyrics.

Playlist-Downloader is a sophisticated, full-featured application designed to bridge the gap between
streaming music discovery and local music ownership. It provides seamless integration between Spotify's
vast playlist ecosystem and YouTube Music's high-quality audio content, enhanced with comprehensive
lyrics support and intelligent metadata management.

## Project Overview

This application solves the fundamental challenge of music enthusiasts who want to maintain local
copies of their carefully curated Spotify playlists while preserving all metadata, lyrics, and
organizational structure. It combines the discovery power of Spotify with the content availability
of YouTube Music, creating a comprehensive solution for music archival and offline listening.

## Core Architecture

The application follows a modular, extensible architecture designed for maintainability, scalability,
and ease of contribution. Each component is designed with clear separation of concerns and well-defined
interfaces:

### Primary Modules:

**Configuration Management (`src/config/`)**
- Centralized settings management with YAML and environment variable support
- Secure authentication handling for Spotify OAuth2 flows
- Hot-reloading capabilities for dynamic configuration updates
- Hierarchical configuration with user, system, and default levels

**Spotify Integration (`src/spotify/`)**
- Complete Spotify Web API integration with OAuth2 authentication
- Playlist discovery, track metadata extraction, and user library access
- Rate limiting and API quota management
- Comprehensive data models for playlists, tracks, artists, and albums

**YouTube Music Integration (`src/ytmusic/`)**
- Intelligent search and matching algorithms for finding YouTube Music equivalents
- High-quality audio extraction with multiple format support (MP3, M4A, FLAC)
- Advanced scoring algorithms for optimal track matching
- Fallback strategies for difficult-to-match content

**Lyrics Management (`src/lyrics/`)**
- Multi-source lyrics aggregation (Genius, SyncedLyrics, and more)
- Quality validation and confidence scoring
- Support for both plain text and synchronized lyrics (LRC format)
- Intelligent matching and fallback mechanisms

**Audio Processing (`src/audio/`)**
- High-quality audio format conversion and optimization
- Comprehensive metadata tagging with album art support
- Audio analysis and quality validation
- Batch processing capabilities for playlist-scale operations

**Synchronization Engine (`src/sync/`)**
- Intelligent playlist synchronization with change detection
- Incremental updates to minimize bandwidth and processing time
- Conflict resolution for modified playlists
- Progress tracking and resumable operations

**Utilities and Helpers (`src/utils/`)**
- Comprehensive logging system with operation-specific log files
- File system utilities with cross-platform compatibility
- Network resilience and retry mechanisms
- Input validation and sanitization functions

### Design Patterns and Principles:

**Singleton Pattern**: Used for configuration and authentication managers to ensure
consistent state across the application and efficient resource usage.

**Factory Pattern**: Implemented for component instantiation, providing clean interfaces
and enabling easy testing and mocking.

**Observer Pattern**: Used for progress tracking and event notifications throughout
long-running operations.

**Strategy Pattern**: Applied to lyrics sources and download methods, allowing
runtime selection of optimal providers and techniques.

## Key Features

### Playlist Management
- Download complete Spotify playlists with all tracks and metadata
- Support for user's saved tracks ("Liked Songs") as special playlist
- Incremental synchronization for updated playlists
- Batch processing of multiple playlists
- Playlist organization preservation with folder structures

### Audio Quality
- Multiple output formats: MP3 (128-320 kbps), M4A (AAC), FLAC (lossless)
- Intelligent quality selection based on source availability
- Audio normalization and enhancement options
- Comprehensive metadata tagging with album artwork

### Lyrics Integration
- Multi-source lyrics aggregation for maximum coverage
- Quality validation and confidence scoring
- Support for synchronized lyrics with timing information
- Automatic lyrics embedding in audio file metadata

### User Experience
- Comprehensive command-line interface with intuitive commands
- Real-time progress tracking with detailed status information
- Colorized output with clear success/error indicators
- Extensive configuration options for customization

### Reliability
- Robust error handling with graceful degradation
- Network resilience with automatic retry mechanisms
- Resume capability for interrupted downloads
- Comprehensive logging for troubleshooting

## Installation and Setup

### Requirements
- Python 3.8 or higher
- Spotify Premium account (for high-quality audio access)
- Spotify Developer Application (for API access)
- Optional: Genius API key (for enhanced lyrics)

### Quick Start
```bash
# Install the package
pip install -e .

# Configure Spotify credentials
playlist-dl config set-spotify CLIENT_ID CLIENT_SECRET

# Authenticate with Spotify
playlist-dl auth login

# Download your first playlist
playlist-dl download "https://open.spotify.com/playlist/..."
```

### Advanced Configuration
```bash
# Set audio quality and format preferences
playlist-dl config set --format m4a --quality high

# Configure lyrics sources
playlist-dl config set --lyrics-source genius

# Set custom output directory
playlist-dl config set --output ~/Music/Playlists
```

## Usage Examples

### Basic Playlist Download
```bash
# Download a public playlist
playlist-dl download "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

# Download user's liked songs
playlist-dl download-liked
```

### Playlist Synchronization
```bash
# Update an existing playlist with new tracks
playlist-dl update "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

# Sync all previously downloaded playlists
playlist-dl update-all
```

### Lyrics Management
```bash
# Download lyrics for existing audio files
playlist-dl lyrics download --directory ~/Music/Playlists

# Validate lyrics source availability
playlist-dl lyrics sources
```

### System Management
```bash
# Run comprehensive system diagnostics
playlist-dl doctor

# Show current configuration
playlist-dl config show

# Reset authentication
playlist-dl auth logout
```

## Configuration Options

The application supports extensive configuration through YAML files and environment variables:

### Audio Settings
- `format`: Output audio format (mp3, m4a, flac)
- `quality`: Audio quality level (low, medium, high)
- `normalization`: Audio normalization settings
- `metadata`: Metadata tagging preferences

### Download Settings
- `output_directory`: Base directory for downloaded content
- `concurrency`: Number of parallel download operations
- `retry_attempts`: Network retry configuration
- `temp_directory`: Temporary file location

### Lyrics Settings
- `enabled`: Enable/disable lyrics downloading
- `primary_source`: Preferred lyrics provider
- `fallback_sources`: Backup lyrics sources
- `formats`: Lyrics output formats (txt, lrc, embedded)

## Performance Considerations

### Memory Usage
- Streaming downloads minimize memory footprint
- Efficient metadata caching reduces API calls
- Garbage collection optimization for long-running operations

### Network Efficiency
- Intelligent rate limiting respects API quotas
- Connection pooling for multiple operations
- Bandwidth-conscious downloading with progress tracking

### Storage Optimization
- Configurable temporary file management
- Atomic file operations prevent corruption
- Efficient disk space usage with cleanup utilities

## Security and Privacy

### API Security
- Secure OAuth2 token management with automatic refresh
- Encrypted credential storage
- API key validation and rotation support

### Privacy Protection
- No collection or transmission of personal listening data
- Local-only operation with user-controlled data
- Secure handling of authentication tokens

### File Security
- Safe file naming with sanitization
- Permission-aware file operations
- Secure temporary file handling

## Extensibility and Development

### Plugin Architecture
The application is designed to support future extensions:
- Additional streaming service integrations
- Custom lyrics sources
- Audio processing plugins
- Alternative download backends

### Testing Strategy
- Comprehensive unit test coverage
- Integration tests for API interactions
- Performance tests for large-scale operations
- Mock testing for external dependencies

### Contributing Guidelines
- Clean, documented code following PEP 8 standards
- Comprehensive testing for new features
- Backwards compatibility considerations
- Clear commit messages and pull request descriptions

## Troubleshooting and Support

### Common Issues
- Authentication problems: Check Spotify app configuration
- Download failures: Verify network connectivity and API quotas
- Audio quality issues: Review format and quality settings
- Lyrics missing: Validate lyrics source configuration

### Diagnostic Tools
- `playlist-dl doctor`: Comprehensive system health check
- Detailed logging with operation-specific log files
- Configuration validation and recommendations
- Network connectivity and API status verification

### Getting Help
- Comprehensive documentation and examples
- Issue tracking with detailed bug reports
- Community support and feature requests
- Regular updates and maintenance releases

## Future Development

### Planned Features
- Web-based user interface for remote management
- Advanced audio analysis and enhancement
- Machine learning-based search optimization
- Cloud storage integration options

### Performance Improvements
- Async/await implementation for better concurrency
- Database backend for large library management
- Streaming processing for memory efficiency
- Advanced caching strategies

This application represents a comprehensive solution for music enthusiasts who value both
the convenience of streaming discovery and the reliability of local music ownership.
Through its modular architecture and extensive feature set, it provides a robust
foundation for personal music library management while maintaining respect for
content creators and platform terms of service.
"""

# Version information for the Playlist-Downloader package
# Following semantic versioning (major.minor.patch) with beta designation
# This version indicates active development with feature completeness approaching v1.0
__version__ = "v0.9.0-beta"

# Package author information
# Primary developer and maintainer of the Playlist-Downloader project
__author__ = "Verryx-02"

# Contact information for support, bug reports, and contributions
# Secure contact method for project-related communications
__email__ = "verryx_github.untaken971@passinbox.com"

# Concise description of package functionality for package managers and documentation
# Used by setup.py and package distribution systems for project metadata
__description__ = "Download Spotify playlists locally with YouTube Music integration and lyrics support"

# Package metadata exported for external access and introspection
# These attributes provide programmatic access to package information
# Used by package managers, documentation generators, and version checking systems
__all__ = [
    "__version__",     # Semantic version string for compatibility checking and display
    "__author__",      # Author attribution for credits and contact information  
    "__email__",       # Contact method for support and development communications
    "__description__"  # Package description for automated documentation and catalogs
]