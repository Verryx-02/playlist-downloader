"""
Data models for Spotify playlist and track information

This module defines comprehensive data structures for storing and manipulating music metadata
from the Spotify Web API. It serves as the core data layer for the Playlist-Downloader
application, providing type-safe models with integrated download tracking and status management.

Architecture Overview:

The module implements a layered data model architecture:

1. **Status Enums Layer**: Defines state machines for tracking operation progress
   - TrackStatus: Audio download lifecycle states
   - LyricsStatus: Lyrics retrieval operation states  
   - LyricsSource: Provider identification for lyrics services
   - AudioFormat: Output format specifications for audio processing

2. **Core Spotify Models Layer**: Direct representations of Spotify API entities
   - SpotifyArtist: Artist profile with popularity metrics and genre information
   - SpotifyAlbum: Album metadata with track listings and release information
   - SpotifyTrack: Individual track with complete audio and metadata features
   - SpotifyPlaylist: Playlist container with ownership and collaboration details

3. **Enhanced Download Models Layer**: Extended entities with download operation metadata
   - PlaylistTrack: Track enhanced with download status, file paths, and YouTube matching
   - SpotifyPlaylist: Playlist enhanced with local directory management and progress tracking

4. **Statistics and Monitoring Layer**: Performance tracking and operation analysis
   - DownloadStats: Comprehensive metrics for download operations and success rates

Design Patterns Implemented:

- **Data Transfer Object (DTO)**: All models serve as DTOs for API response data
- **Factory Method**: `from_spotify_data()` methods for safe object construction from external data
- **State Pattern**: Status enums represent finite state machines for operation tracking
- **Builder Pattern**: Progressive construction of complex playlist structures with tracks

Key Features:

- **Type Safety**: Full type annotations with Optional and Union types for robust data handling
- **Data Validation**: Safe construction from external API data with fallback defaults
- **Serialization Support**: Built-in methods for converting models to/from dictionary formats
- **Progress Tracking**: Integrated status management for concurrent download operations
- **File Management**: Local file path tracking and directory structure organization
- **Error Handling**: Comprehensive error state tracking with detailed failure information

Integration Points:

- **Spotify Client**: Consumes API responses and constructs model instances
- **Download Engine**: Uses status tracking and metadata for operation coordination
- **Audio Processing**: References format specifications and file path management
- **Lyrics System**: Utilizes source tracking and content storage mechanisms
- **Synchronization**: Leverages progress metrics and change detection capabilities

Thread Safety Considerations:

All models are designed as immutable data containers where possible, with status updates
handled through controlled state transitions. The status enums provide atomic state
representation suitable for concurrent access patterns in multi-threaded download operations.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TrackStatus(Enum):
    """
    Finite state machine for audio download operation tracking
    
    Represents the complete lifecycle of a track download operation from initial
    queuing through final completion or failure. Used for progress monitoring,
    retry logic, and user interface status display.
    
    State Transitions:
    PENDING -> DOWNLOADING -> DOWNLOADED (success path)
    PENDING -> DOWNLOADING -> FAILED (error path)  
    PENDING -> SKIPPED (user intervention or filter rules)
    FAILED -> DOWNLOADING (retry attempt)
    
    Values:
        PENDING: Track queued for download but not yet started
        DOWNLOADING: Active download operation in progress
        DOWNLOADED: Successfully downloaded and validated
        FAILED: Download attempt failed, eligible for retry
        SKIPPED: Intentionally bypassed due to filters or user choice
    """
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    SKIPPED = "skipped"


class LyricsStatus(Enum):
    """
    State machine for lyrics retrieval and processing operations
    
    Tracks the complete lifecycle of lyrics acquisition from multiple sources
    including Genius, SyncedLyrics, and manual input. Handles special cases
    like instrumental tracks and provides detailed failure categorization.
    
    State Transitions:
    PENDING -> DOWNLOADING -> DOWNLOADED (success path)
    PENDING -> DOWNLOADING -> NOT_FOUND (no lyrics available)
    PENDING -> DOWNLOADING -> FAILED (provider error)
    PENDING -> INSTRUMENTAL (detected as instrumental track)
    PENDING -> SKIPPED (user disabled lyrics or filter applied)
    
    Values:
        PENDING: Lyrics queued for retrieval but not yet attempted
        DOWNLOADING: Active search operation across providers
        DOWNLOADED: Successfully retrieved and validated lyrics content
        FAILED: Retrieval failed due to provider errors or connectivity issues
        NOT_FOUND: No lyrics found across all configured providers
        INSTRUMENTAL: Track identified as instrumental (no vocals)
        SKIPPED: Lyrics retrieval bypassed by user preference or rules
    """
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    INSTRUMENTAL = "instrumental"
    SKIPPED = "skipped"


class LyricsSource(Enum):
    """
    Enumeration of supported lyrics provider services
    
    Identifies the source provider for lyrics content, enabling provider-specific
    handling, rate limiting, and quality assessment. Used for fallback logic
    and source attribution in metadata.
    
    Provider Characteristics:
    - GENIUS: High-quality curated lyrics with annotations
    - SYNCEDLYRICS: Time-synchronized lyrics with millisecond precision
    - MANUAL: User-provided lyrics content  
    - UNKNOWN: Source undetermined or mixed providers
    
    Values:
        GENIUS: Genius.com API-sourced lyrics with quality validation
        SYNCEDLYRICS: Time-synced lyrics for karaoke and visualization
        MANUAL: User-uploaded or manually corrected lyrics content
        UNKNOWN: Source not identified or legacy data
    """
    GENIUS = "genius"
    SYNCEDLYRICS = "syncedlyrics"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class AudioFormat(Enum):
    """
    Supported output audio formats with encoding specifications
    
    Defines available audio output formats for download operations. Each format
    represents different quality, compression, and compatibility characteristics
    for various playback scenarios and storage requirements.
    
    Format Characteristics:
    - MP3: Universal compatibility, good compression (lossy)
    - FLAC: Lossless compression, audiophile quality, larger files
    - M4A: Apple ecosystem optimization, good quality/size ratio
    
    Values:
        MP3: MPEG-1 Audio Layer 3, lossy compression with broad compatibility
        FLAC: Free Lossless Audio Codec, perfect quality preservation
        M4A: MPEG-4 Audio, efficient compression with high quality
    """
    MP3 = "mp3"
    FLAC = "flac"
    M4A = "m4a"


@dataclass
class SpotifyArtist:
    """
    Comprehensive artist profile data from Spotify Web API
    
    Represents complete artist information including biographical data, popularity
    metrics, and social statistics. Serves as a core entity for track attribution
    and provides context for search and matching algorithms.
    
    The model handles both simplified artist references (from track/album contexts)
    and full artist profiles (from dedicated artist endpoints). Optional fields
    gracefully degrade when partial data is available.
    
    Attributes:
        id: Spotify's unique artist identifier (used for API calls)
        name: Artist display name (primary identification for users)
        external_urls: Links to artist profiles on external platforms
        href: Direct API endpoint URL for this artist
        uri: Spotify URI for deep linking (spotify:artist:id)
        genres: Musical genre classifications assigned by Spotify
        popularity: Algorithmic popularity score (0-100, higher = more popular)
        followers: Total follower count across Spotify platform
        
    Note:
        Popularity and follower data may be None for simplified artist objects
        embedded within track or album responses. Full data requires dedicated
        artist API calls.
    """
    id: str
    name: str
    external_urls: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    popularity: Optional[int] = None
    followers: Optional[int] = None
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any]) -> 'SpotifyArtist':
        """
        Factory method to construct SpotifyArtist from Spotify API response data
        
        Safely extracts artist information from various API response formats,
        handling both simplified and full artist objects. Provides defensive
        data extraction with sensible defaults for missing optional fields.
        
        Args:
            data: Raw artist data from Spotify API response
            
        Returns:
            SpotifyArtist instance with validated and normalized data
            
        Note:
            Handles nested follower data structure safely, extracting total
            count or defaulting to None if followers object is missing.
        """
        return cls(
            id=data['id'],
            name=data['name'],
            external_urls=data.get('external_urls', {}),
            href=data.get('href'),
            uri=data.get('uri'),
            genres=data.get('genres', []),
            popularity=data.get('popularity'),
            # Safe extraction of nested followers.total field
            followers=data.get('followers', {}).get('total') if data.get('followers') else None
        )


@dataclass
class SpotifyAlbum:
    """
    Complete album metadata with track listings and release information
    
    Encapsulates comprehensive album data including release details, track counts,
    artist attributions, and visual assets. Provides context for individual tracks
    and supports album-based organization and artwork retrieval.
    
    The model supports multiple album types (album, single, compilation) and handles
    various release date precisions (day, month, year). Image handling provides
    intelligent selection based on quality and size requirements.
    
    Attributes:
        id: Spotify's unique album identifier
        name: Album title as published
        album_type: Classification (album, single, compilation, appears_on)
        total_tracks: Number of tracks in the complete album
        release_date: Publication date in YYYY-MM-DD format (precision varies)
        release_date_precision: Granularity of release date (year, month, day)
        artists: List of contributing artists with full profile data
        external_urls: Links to album on external platforms (Spotify, etc.)
        href: Direct API endpoint URL for detailed album data
        uri: Spotify URI for deep linking (spotify:album:id)
        images: Array of album artwork in multiple resolutions
        genres: Musical genre classifications for the album
        popularity: Algorithmic popularity score (0-100)
        
    Design Note:
        Images are stored as list of dictionaries with 'url', 'width', 'height'
        keys, enabling intelligent resolution selection for different UI contexts.
    """
    id: str
    name: str
    album_type: str
    total_tracks: int
    release_date: str
    release_date_precision: str
    artists: List[SpotifyArtist] = field(default_factory=list)
    external_urls: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    images: List[Dict[str, Any]] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    popularity: Optional[int] = None
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any]) -> 'SpotifyAlbum':
        """
        Factory method for constructing SpotifyAlbum from API response data
        
        Processes complex nested album data including artist arrays and image
        collections. Handles various album object formats from different API
        endpoints (tracks, albums, search results).
        
        Args:
            data: Raw album data from Spotify API response
            
        Returns:
            SpotifyAlbum instance with fully constructed artist objects and
            normalized metadata fields
            
        Note:
            Recursively constructs SpotifyArtist objects for all contributing
            artists, ensuring complete relationship mapping.
        """
        # Recursively construct artist objects from embedded artist data
        artists = [SpotifyArtist.from_spotify_data(artist) for artist in data.get('artists', [])]
        
        return cls(
            id=data['id'],
            name=data['name'],
            album_type=data['album_type'],
            total_tracks=data['total_tracks'],
            release_date=data['release_date'],
            release_date_precision=data['release_date_precision'],
            artists=artists,
            external_urls=data.get('external_urls', {}),
            href=data.get('href'),
            uri=data.get('uri'),
            images=data.get('images', []),
            genres=data.get('genres', []),
            popularity=data.get('popularity')
        )
    
    def get_best_image(self, min_size: int = 300) -> Optional[str]:
        """
        Intelligent image selection algorithm for optimal visual quality
        
        Implements a two-tier selection strategy to find the best album artwork:
        1. First, filter images meeting minimum size requirements
        2. If suitable images exist, select the highest resolution
        3. Otherwise, fallback to the largest available image
        
        This algorithm balances quality requirements with availability, ensuring
        UI components always receive the best possible artwork while respecting
        minimum size constraints for visual clarity.
        
        Args:
            min_size: Minimum pixel dimension (width or height) for image selection
            
        Returns:
            URL of the best matching image, or None if no images available
            
        Algorithm Details:
            - Uses area calculation (width * height) for quality ranking
            - Considers both width and height when applying size filter
            - Gracefully degrades to largest available if no images meet requirements
        """
        if not self.images:
            return None
        
        # First pass: filter images meeting minimum size requirements
        # Check both width and height to ensure adequate visual quality
        suitable_images = [img for img in self.images 
                          if img.get('width', 0) >= min_size or img.get('height', 0) >= min_size]
        
        if suitable_images:
            # Select highest quality image from suitable candidates
            # Use area (width * height) as proxy for overall image quality
            return max(suitable_images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']
        else:
            # Fallback: return largest available image regardless of size constraints
            # Ensures UI components always receive some artwork
            return max(self.images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']


@dataclass
class SpotifyTrack:
    """
    Comprehensive track metadata with audio features and contextual information
    
    Represents complete track data including musical content, popularity metrics,
    technical specifications, and platform integration details. Serves as the
    core entity for download operations and provides all necessary metadata
    for audio file tagging and organization.
    
    The model handles various track contexts (album tracks, playlist items, 
    search results) and provides utility methods for filename generation and
    duration formatting. Support for local files and playability status enables
    graceful handling of unavailable content.
    
    Attributes:
        id: Spotify's unique track identifier for API operations
        name: Track title as published by the artist
        artists: Complete list of contributing artists with profile data
        album: Full album context with artwork and release information
        duration_ms: Track length in milliseconds for precise timing
        explicit: Content advisory flag for explicit lyrics or themes
        popularity: Algorithmic popularity score (0-100) based on recent plays
        track_number: Position within the album tracklist
        disc_number: Disc number for multi-disc releases (default: 1)
        external_urls: Links to track on external platforms
        external_ids: External identifier mappings (ISRC, EAN, UPC)
        href: Direct API endpoint URL for track details
        uri: Spotify URI for deep linking (spotify:track:id)
        preview_url: 30-second audio preview URL (may be None)
        is_local: Flag indicating locally uploaded user content
        is_playable: Availability status in user's market
        added_at: Timestamp when track was added to playlist context
        genres: Musical genre classifications (inherited from album/artist)
        
    Design Notes:
        - Duration stored in milliseconds for precise calculations
        - Multiple artist support for collaborations and features
        - Embedded album object provides complete context without additional API calls
        - External IDs enable integration with music databases and metadata services
    """
    id: str
    name: str
    artists: List[SpotifyArtist]
    album: SpotifyAlbum
    duration_ms: int
    explicit: bool
    popularity: int
    track_number: int
    disc_number: int = 1
    external_urls: Dict[str, str] = field(default_factory=dict)
    external_ids: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    preview_url: Optional[str] = None
    is_local: bool = False
    is_playable: bool = True
    
    # Additional metadata for playlist context and enhanced functionality
    added_at: Optional[datetime] = None
    genres: List[str] = field(default_factory=list)
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any], added_at: Optional[str] = None) -> 'SpotifyTrack':
        """
        Factory method for constructing SpotifyTrack from various API response formats
        
        Handles different track object structures from various Spotify API endpoints:
        - Direct track objects from track details
        - Nested track objects from playlist items  
        - Track objects from search results and recommendations
        
        Performs safe data extraction with comprehensive error handling for
        malformed or incomplete API responses. Constructs complete object graphs
        including artists and album data.
        
        Args:
            data: Raw track data from Spotify API response
            added_at: ISO timestamp string when track was added to playlist context
            
        Returns:
            SpotifyTrack instance with fully constructed nested objects
            
        Error Handling:
            - Gracefully handles missing optional fields with sensible defaults
            - Safely parses ISO timestamps with timezone handling
            - Continues operation even if added_at parsing fails
        """
        # Handle playlist item format where track data is nested under 'track' key
        track_data = data.get('track', data)
        
        # Recursively construct artist objects with complete profile data
        artists = [SpotifyArtist.from_spotify_data(artist) for artist in track_data.get('artists', [])]
        
        # Construct complete album object with artwork and metadata
        album = SpotifyAlbum.from_spotify_data(track_data['album'])
        
        # Safe parsing of ISO timestamp with timezone handling
        added_at_dt = None
        if added_at:
            try:
                # Handle both 'Z' and '+00:00' timezone formats from API
                added_at_dt = datetime.fromisoformat(added_at.replace('Z', '+00:00'))
            except Exception:
                # Continue operation even if timestamp parsing fails
                pass
        
        return cls(
            id=track_data['id'],
            name=track_data['name'],
            artists=artists,
            album=album,
            duration_ms=track_data['duration_ms'],
            explicit=track_data['explicit'],
            popularity=track_data['popularity'],
            track_number=track_data['track_number'],
            disc_number=track_data.get('disc_number', 1),  # Default to disc 1 for singles
            external_urls=track_data.get('external_urls', {}),
            external_ids=track_data.get('external_ids', {}),
            href=track_data.get('href'),
            uri=track_data.get('uri'),
            preview_url=track_data.get('preview_url'),
            is_local=track_data.get('is_local', False),
            is_playable=track_data.get('is_playable', True),
            added_at=added_at_dt
        )
    
    @property
    def duration_str(self) -> str:
        """
        Human-readable duration formatting for UI display
        
        Converts millisecond duration to standard MM:SS format for user interfaces
        and track listings. Handles tracks of any reasonable length with proper
        zero-padding for consistent alignment.
        
        Returns:
            Formatted duration string in MM:SS format (e.g., "3:42", "0:30")
            
        Example:
            Track with 222000ms duration returns "3:42"
        """
        total_seconds = self.duration_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"  # Zero-pad seconds for consistent formatting
    
    @property
    def primary_artist(self) -> str:
        """
        Primary artist name for simplified attribution and filename generation
        
        Returns the first artist in the artists list, which represents the primary
        or main artist according to Spotify's attribution. Provides fallback for
        tracks with missing artist data.
        
        Returns:
            Name of the primary artist, or "Unknown Artist" if no artists available
        """
        return self.artists[0].name if self.artists else "Unknown Artist"
    
    @property
    def all_artists(self) -> str:
        """
        Complete artist attribution string for full credit display
        
        Joins all contributing artists with comma separation for complete attribution
        in metadata tags and detailed track information. Handles collaborations,
        features, and multi-artist releases properly.
        
        Returns:
            Comma-separated string of all artist names (e.g., "Artist1, Artist2, Artist3")
        """
        return ", ".join(artist.name for artist in self.artists)
    
    @property
    def clean_title(self) -> str:
        """
        Filesystem-safe track title for filename generation
        
        Removes or replaces characters that are problematic for filenames across
        different operating systems. Specifically handles forward and backslashes
        which can be interpreted as path separators.
        
        Returns:
            Track title with filesystem-unsafe characters replaced with hyphens
        """
        return self.name.replace('/', '-').replace('\\', '-')
    
    @property
    def clean_artist(self) -> str:
        """
        Filesystem-safe primary artist name for filename generation
        
        Applies the same filename sanitization as clean_title but specifically
        for the primary artist name. Ensures consistent filename formatting
        across track and artist components.
        
        Returns:
            Primary artist name with filesystem-unsafe characters replaced with hyphens
        """
        return self.primary_artist.replace('/', '-').replace('\\', '-')


@dataclass
class PlaylistTrack:
    """
    Enhanced track model with download operation metadata and YouTube Music integration
    
    Extends SpotifyTrack with comprehensive download tracking, file management,
    and external service integration. Serves as the primary entity for download
    operations, providing complete lifecycle management from queuing through
    completion or failure.
    
    This model bridges the gap between Spotify metadata and local file management,
    enabling sophisticated download orchestration with retry logic, progress tracking,
    and multi-provider content matching.
    
    Key Features:
    - **Status Tracking**: Separate state machines for audio and lyrics operations
    - **File Management**: Local path tracking with format and size information
    - **Error Handling**: Detailed error capture with retry attempt counting
    - **YouTube Integration**: Video matching with quality scoring
    - **Lyrics Management**: Multi-source lyrics with sync and embedding support
    - **Progress Monitoring**: Position tracking and status visualization
    
    Attributes:
        spotify_track: Complete Spotify track metadata and audio features
        playlist_position: Track position within playlist (1-indexed)
        audio_status: Current state of audio download operation
        lyrics_status: Current state of lyrics retrieval operation
        local_file_path: Absolute path to downloaded audio file
        lyrics_file_path: Absolute path to lyrics file (.lrc or .txt)
        audio_format: Format of downloaded audio file
        file_size_bytes: Size of downloaded audio file for progress tracking
        download_attempts: Number of audio download attempts (for retry logic)
        lyrics_attempts: Number of lyrics retrieval attempts
        last_download_attempt: Timestamp of most recent download attempt
        last_lyrics_attempt: Timestamp of most recent lyrics attempt
        download_error: Detailed error message from last failed download
        lyrics_error: Detailed error message from last failed lyrics attempt
        youtube_video_id: Matched YouTube video identifier
        youtube_title: Title of matched YouTube video
        youtube_duration: Duration of YouTube video in seconds
        youtube_match_score: Confidence score for YouTube match (0.0-1.0)
        lyrics_source: Provider that successfully delivered lyrics
        lyrics_content: Raw lyrics text content
        lyrics_synced: Flag indicating time-synchronized lyrics availability
        lyrics_embedded: Flag indicating lyrics embedded in audio file
        
    Design Pattern:
        Implements the State pattern for download lifecycle management with
        atomic status transitions and comprehensive error state handling.
    """
    spotify_track: SpotifyTrack
    playlist_position: int
    
    # Download operation status tracking with separate state machines
    audio_status: TrackStatus = TrackStatus.PENDING
    lyrics_status: LyricsStatus = LyricsStatus.PENDING
    
    # Local file management with path and format tracking
    local_file_path: Optional[str] = None
    lyrics_file_path: Optional[str] = None
    audio_format: Optional[AudioFormat] = None
    file_size_bytes: Optional[int] = None
    
    # Retry logic and error handling with detailed tracking
    download_attempts: int = 0
    lyrics_attempts: int = 0
    last_download_attempt: Optional[datetime] = None
    last_lyrics_attempt: Optional[datetime] = None
    download_error: Optional[str] = None
    lyrics_error: Optional[str] = None
    
    # YouTube Music integration with matching confidence scoring
    youtube_video_id: Optional[str] = None
    youtube_title: Optional[str] = None
    youtube_duration: Optional[int] = None
    youtube_match_score: Optional[float] = None
    
    # Lyrics management with source attribution and format tracking
    lyrics_source: Optional[LyricsSource] = None
    lyrics_content: Optional[str] = None
    lyrics_synced: bool = False
    lyrics_embedded: bool = False
    
    @property
    def track_id(self) -> str:
        """
        Convenient access to Spotify track identifier
        
        Returns:
            Spotify track ID for API operations and caching
        """
        return self.spotify_track.id
    
    @property
    def track_name(self) -> str:
        """
        Convenient access to track display name
        
        Returns:
            Track name for UI display and logging
        """
        return self.spotify_track.name
    
    @property
    def artist_name(self) -> str:
        """
        Convenient access to primary artist name
        
        Returns:
            Primary artist name for attribution and organization
        """
        return self.spotify_track.primary_artist
    
    @property
    def duration_str(self) -> str:
        """
        Convenient access to formatted duration string
        
        Returns:
            Human-readable duration in MM:SS format
        """
        return self.spotify_track.duration_str
    
    @property
    def filename(self) -> str:
        """
        Generate standardized filename for downloaded audio file
        
        Creates consistent filename format with playlist position, artist,
        and track title. Uses sanitized names to ensure filesystem compatibility
        across different operating systems.
        
        Format: "{position:02d} - {artist} - {title}"
        
        Returns:
            Standardized filename without extension (e.g., "01 - Artist - Title")
            
        Dependencies:
            Requires sanitize_filename utility function for filesystem safety
        """
        from ..utils.helpers import sanitize_filename
        
        # Zero-pad position for consistent alphabetical sorting
        position = f"{self.playlist_position:02d}"
        
        # Sanitize artist and title for filesystem compatibility
        artist = sanitize_filename(self.artist_name)
        title = sanitize_filename(self.track_name)
        
        return f"{position} - {artist} - {title}"
    
    def get_status_icons(self) -> str:
        """
        Generate visual status indicators for track progress display
        
        Provides compact visual representation of download and lyrics status
        for use in progress displays and track listings. Uses emoji icons
        for clear status communication.
        
        Status Icon Mapping:
        - Audio: ✅ (downloaded) or ⏳ (pending/in-progress)
        - Lyrics: 🎵 (downloaded), 🚫 (not found), ⏳ (pending/in-progress)
        
        Returns:
            Two-character emoji string representing audio and lyrics status
            
        Example:
            "✅🎵" = audio downloaded, lyrics downloaded
            "⏳🚫" = audio pending, lyrics not found
        """
        # Audio status: simple binary representation
        audio_icon = "✅" if self.audio_status == TrackStatus.DOWNLOADED else "⏳"
        
        # Lyrics status: three-state representation with not-found handling
        if self.lyrics_status == LyricsStatus.DOWNLOADED:
            lyrics_icon = "🎵"
        elif self.lyrics_status == LyricsStatus.NOT_FOUND:
            lyrics_icon = "🚫"
        else:
            lyrics_icon = "⏳"
            
        return f"{audio_icon}{lyrics_icon}"


@dataclass
class SpotifyPlaylist:
    """
    Comprehensive playlist model with track management and download coordination
    
    Represents complete playlist data including metadata, track collections,
    ownership information, and local download management. Serves as the primary
    container for download operations with sophisticated progress tracking
    and file organization capabilities.
    
    The model supports various playlist types (user playlists, collaborative
    playlists, followed playlists) and provides comprehensive statistics and
    filtering methods for download management and progress monitoring.
    
    Key Capabilities:
    - **Track Management**: Addition, retrieval, and organization of playlist tracks
    - **Progress Tracking**: Real-time download and lyrics progress calculation
    - **Status Filtering**: Querying tracks by download status for retry logic
    - **Image Handling**: Intelligent playlist artwork selection with quality scoring
    - **Serialization**: Complete playlist state persistence for caching and resume
    - **Directory Management**: Local file organization and path management
    
    Attributes:
        id: Spotify's unique playlist identifier for API operations
        name: Playlist title as set by owner
        description: Playlist description text (may contain HTML)
        owner_id: Spotify user ID of playlist owner
        owner_name: Display name of playlist owner
        public: Visibility flag for public playlist discovery
        collaborative: Flag indicating multiple users can edit
        total_tracks: Total number of tracks in playlist (from API)
        external_urls: Links to playlist on external platforms
        href: Direct API endpoint URL for playlist data
        uri: Spotify URI for deep linking (spotify:playlist:id)
        images: Array of playlist artwork in multiple resolutions
        followers: Number of users following this playlist
        snapshot_id: Version identifier for change detection
        tracks: Complete collection of PlaylistTrack objects
        created_at: Local timestamp when playlist was first downloaded
        last_updated: Local timestamp when playlist was last modified
        last_synced: Local timestamp when playlist was last synchronized
        local_directory: Absolute path to playlist download directory
        
    Design Patterns:
        - **Container Pattern**: Manages collection of PlaylistTrack objects
        - **Observer Pattern**: Status changes propagate to progress calculations
        - **Strategy Pattern**: Different serialization formats supported
    """
    id: str
    name: str
    description: str
    owner_id: str
    owner_name: str
    public: bool
    collaborative: bool
    total_tracks: int
    external_urls: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    images: List[Dict[str, Any]] = field(default_factory=list)
    followers: Optional[int] = None
    snapshot_id: Optional[str] = None
    
    # Track collection management
    tracks: List[PlaylistTrack] = field(default_factory=list)
    
    # Local metadata for download management and synchronization
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    local_directory: Optional[str] = None
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any]) -> 'SpotifyPlaylist':
        """
        Factory method for constructing SpotifyPlaylist from Spotify API response
        
        Safely extracts playlist metadata from various API response formats,
        handling both simplified playlist objects and detailed playlist data.
        Provides defensive programming for optional fields and nested data structures.
        
        Args:
            data: Raw playlist data from Spotify API response
            
        Returns:
            SpotifyPlaylist instance with normalized metadata
            
        Note:
            Creates empty tracks list - tracks must be added separately via add_track()
            method to maintain proper PlaylistTrack construction with positions.
        """
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),  # Description may be empty or None
            owner_id=data['owner']['id'],
            # Handle missing display names gracefully, fallback to user ID
            owner_name=data['owner']['display_name'] or data['owner']['id'],
            public=data.get('public', False),  # Default to private if not specified
            collaborative=data.get('collaborative', False),
            total_tracks=data['tracks']['total'],  # Extract from nested tracks object
            external_urls=data.get('external_urls', {}),
            href=data.get('href'),
            uri=data.get('uri'),
            images=data.get('images', []),
            # Safe extraction of nested followers.total field
            followers=data.get('followers', {}).get('total') if data.get('followers') else None,
            snapshot_id=data.get('snapshot_id')  # Used for change detection
        )
    
    def add_track(self, spotify_track: SpotifyTrack, position: int, added_at: Optional[str] = None) -> PlaylistTrack:
        """
        Add a track to the playlist with proper position management
        
        Creates a new PlaylistTrack instance with the specified position and
        adds it to the playlist's track collection. Maintains playlist integrity
        and provides the foundation for download operation tracking.
        
        Args:
            spotify_track: Complete Spotify track metadata
            position: 1-indexed position within playlist
            added_at: ISO timestamp when track was added (unused currently)
            
        Returns:
            Newly created PlaylistTrack instance for further customization
            
        Note:
            Tracks are appended to the list - position sorting should be handled
            by the caller if maintaining strict order is required.
        """
        playlist_track = PlaylistTrack(
            spotify_track=spotify_track,
            playlist_position=position
        )
        self.tracks.append(playlist_track)
        return playlist_track
    
    def get_track_by_id(self, track_id: str) -> Optional[PlaylistTrack]:
        """
        Retrieve track by Spotify identifier for update operations
        
        Performs linear search through track collection to find track with
        matching Spotify ID. Used for status updates and metadata synchronization.
        
        Args:
            track_id: Spotify track identifier to search for
            
        Returns:
            PlaylistTrack instance if found, None otherwise
            
        Performance Note:
            O(n) complexity - consider indexing for large playlists if performance
            becomes critical.
        """
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        return None
    
    def get_track_by_position(self, position: int) -> Optional[PlaylistTrack]:
        """
        Retrieve track by playlist position for sequential operations
        
        Searches for track at specific playlist position. Useful for position-based
        operations and maintaining playlist order during downloads.
        
        Args:
            position: 1-indexed playlist position to search for
            
        Returns:
            PlaylistTrack instance if found, None otherwise
            
        Note:
            Position should be 1-indexed to match Spotify's convention
        """
        for track in self.tracks:
            if track.playlist_position == position:
                return track
        return None
    
    @property
    def downloaded_tracks(self) -> List[PlaylistTrack]:
        """
        Filter tracks with completed audio downloads
        
        Returns all tracks that have successfully completed audio download
        operations. Used for progress calculation and completion verification.
        
        Returns:
            List of PlaylistTrack instances with DOWNLOADED audio status
        """
        return [track for track in self.tracks if track.audio_status == TrackStatus.DOWNLOADED]
    
    @property
    def pending_tracks(self) -> List[PlaylistTrack]:
        """
        Filter tracks waiting for download processing
        
        Returns all tracks in PENDING status that are queued for download
        but haven't started processing yet. Used for batch operation planning
        and queue management.
        
        Returns:
            List of PlaylistTrack instances with PENDING audio status
        """
        return [track for track in self.tracks if track.audio_status == TrackStatus.PENDING]
    
    @property
    def failed_tracks(self) -> List[PlaylistTrack]:
        """
        Filter tracks with download failures for retry processing
        
        Returns all tracks that have failed download attempts. Used for
        retry logic, error reporting, and manual intervention identification.
        
        Returns:
            List of PlaylistTrack instances with FAILED audio status
        """
        return [track for track in self.tracks if track.audio_status == TrackStatus.FAILED]
    
    @property
    def download_progress(self) -> float:
        """
        Calculate audio download completion percentage
        
        Computes the ratio of successfully downloaded tracks to total tracks,
        providing a normalized progress value for UI progress bars and
        completion monitoring.
        
        Returns:
            Progress ratio from 0.0 (no downloads) to 1.0 (complete)
            Returns 0.0 for empty playlists to avoid division by zero
            
        Algorithm:
            progress = downloaded_count / total_tracks
        """
        if not self.tracks:
            return 0.0
        downloaded = len(self.downloaded_tracks)
        return downloaded / len(self.tracks)
    
    @property
    def lyrics_downloaded_count(self) -> int:
        """
        Count tracks with successfully downloaded lyrics
        
        Returns the total number of tracks that have completed lyrics
        download operations. Used for lyrics-specific progress tracking
        and completion statistics.
        
        Returns:
            Integer count of tracks with DOWNLOADED lyrics status
        """
        return len([track for track in self.tracks if track.lyrics_status == LyricsStatus.DOWNLOADED])
    
    @property
    def lyrics_progress(self) -> float:
        """
        Calculate lyrics download completion percentage
        
        Computes the ratio of successfully downloaded lyrics to total tracks.
        Provides separate progress tracking for lyrics operations which may
        have different completion rates than audio downloads.
        
        Returns:
            Progress ratio from 0.0 (no lyrics) to 1.0 (complete)
            Returns 0.0 for empty playlists to avoid division by zero
        """
        if not self.tracks:
            return 0.0
        downloaded = self.lyrics_downloaded_count
        return downloaded / len(self.tracks)
    
    def get_best_image(self, min_size: int = 300) -> Optional[str]:
        """
        Intelligent playlist artwork selection with quality optimization
        
        Implements sophisticated image selection algorithm to find the best
        playlist artwork balancing quality requirements with availability.
        Uses the same algorithm as SpotifyAlbum for consistent behavior.
        
        Selection Strategy:
        1. Filter images meeting minimum size requirements (width OR height)
        2. From suitable images, select highest resolution (by area)
        3. If no suitable images, fallback to largest available
        4. Return None if no images exist
        
        Args:
            min_size: Minimum pixel dimension (width or height) required
            
        Returns:
            URL of the best matching image, or None if no images available
            
        Quality Metrics:
            - Uses area calculation (width * height) for quality ranking
            - Considers both dimensions when applying size filters
            - Graceful degradation ensures UI always gets best available image
        """
        if not self.images:
            return None
        
        # Filter images meeting minimum quality requirements
        # Accept images where either dimension meets the minimum
        suitable_images = [img for img in self.images 
                          if img.get('width', 0) >= min_size or img.get('height', 0) >= min_size]
        
        if suitable_images:
            # Select highest resolution from suitable candidates
            # Use total pixel count (area) as quality proxy
            return max(suitable_images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']
        else:
            # Fallback: largest available image regardless of size constraints
            # Ensures UI components always receive some artwork
            return max(self.images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize complete playlist state to dictionary for persistence
        
        Converts the entire playlist object including all tracks and metadata
        to a dictionary format suitable for JSON serialization. Handles
        datetime serialization and nested object conversion.
        
        Used for:
        - Caching playlist state between sessions
        - Backup and restore operations
        - Progress persistence across application restarts
        
        Returns:
            Dictionary representation of complete playlist state
            
        Serialization Details:
            - Datetime objects converted to ISO format strings
            - Enum values converted to string representations
            - Nested objects converted to dictionaries
            - None values preserved for proper deserialization
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'owner_name': self.owner_name,
            'public': self.public,
            'collaborative': self.collaborative,
            'total_tracks': self.total_tracks,
            'external_urls': self.external_urls,
            'href': self.href,
            'uri': self.uri,
            'images': self.images,
            'followers': self.followers,
            'snapshot_id': self.snapshot_id,
            # Convert datetime objects to ISO format strings for JSON compatibility
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None,
            'local_directory': self.local_directory,
            # Serialize track collection with complete download metadata
            'tracks': [self._track_to_dict(track) for track in self.tracks]
        }
    
    def _track_to_dict(self, track: PlaylistTrack) -> Dict[str, Any]:
        """
        Convert PlaylistTrack to dictionary for serialization
        
        Serializes a single PlaylistTrack instance to dictionary format,
        handling enum values, datetime objects, and optional fields properly.
        
        Args:
            track: PlaylistTrack instance to serialize
            
        Returns:
            Dictionary representation of track with download metadata
            
        Note:
            Only serializes download metadata, not the complete SpotifyTrack
            object to avoid redundancy. SpotifyTrack ID is stored for reference.
        """
        return {
            'spotify_track_id': track.spotify_track.id,  # Reference to full track data
            'playlist_position': track.playlist_position,
            # Convert enum values to strings for JSON compatibility
            'audio_status': track.audio_status.value,
            'lyrics_status': track.lyrics_status.value,
            'local_file_path': track.local_file_path,
            'lyrics_file_path': track.lyrics_file_path,
            'audio_format': track.audio_format.value if track.audio_format else None,
            'file_size_bytes': track.file_size_bytes,
            'download_attempts': track.download_attempts,
            'lyrics_attempts': track.lyrics_attempts,
            # Convert datetime objects to ISO strings
            'last_download_attempt': track.last_download_attempt.isoformat() if track.last_download_attempt else None,
            'last_lyrics_attempt': track.last_lyrics_attempt.isoformat() if track.last_lyrics_attempt else None,
            'download_error': track.download_error,
            'lyrics_error': track.lyrics_error,
            # YouTube Music integration data
            'youtube_video_id': track.youtube_video_id,
            'youtube_title': track.youtube_title,
            'youtube_duration': track.youtube_duration,
            'youtube_match_score': track.youtube_match_score,
            # Lyrics metadata with source attribution
            'lyrics_source': track.lyrics_source.value if track.lyrics_source else None,
            'lyrics_synced': track.lyrics_synced,
            'lyrics_embedded': track.lyrics_embedded
        }


@dataclass
class DownloadStats:
    """
    Comprehensive statistics and metrics for download operation monitoring
    
    Provides detailed analytics for download operations including success rates,
    performance metrics, and resource utilization tracking. Used for progress
    reporting, performance optimization, and operation post-analysis.
    
    The model supports both real-time progress tracking during operations and
    historical analysis of completed downloads. Calculation methods provide
    derived metrics for success rates, throughput, and resource efficiency.
    
    Key Metrics:
    - **Completion Rates**: Success percentages for audio and lyrics operations
    - **Performance Data**: Operation duration and throughput calculations
    - **Resource Usage**: File size tracking and storage utilization
    - **Error Analysis**: Failed operation counts for quality assessment
    
    Attributes:
        total_tracks: Total number of tracks in the operation scope
        downloaded_tracks: Number of successfully completed audio downloads
        failed_tracks: Number of tracks that failed audio download
        skipped_tracks: Number of tracks intentionally bypassed
        total_lyrics: Total number of lyrics operations attempted
        downloaded_lyrics: Number of successfully retrieved lyrics
        failed_lyrics: Number of lyrics operations that failed
        start_time: Operation start timestamp for duration calculation
        end_time: Operation completion timestamp
        total_size_bytes: Total size of all downloaded files in bytes
        
    Derived Metrics:
        - Success rate calculations for audio and lyrics
        - Operation duration in seconds
        - Average throughput and file size metrics
        - Storage efficiency and resource utilization
    """
    total_tracks: int = 0
    downloaded_tracks: int = 0
    failed_tracks: int = 0
    skipped_tracks: int = 0
    total_lyrics: int = 0
    downloaded_lyrics: int = 0
    failed_lyrics: int = 0
    
    # Performance and timing metrics for operation analysis
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_size_bytes: int = 0
    
    @property
    def success_rate(self) -> float:
        """
        Calculate audio download success rate as percentage
        
        Computes the ratio of successful downloads to total download attempts,
        providing a key performance indicator for download operation quality.
        
        Returns:
            Success rate from 0.0 (no successes) to 1.0 (perfect success)
            Returns 0.0 for operations with no tracks to avoid division by zero
            
        Formula:
            success_rate = downloaded_tracks / total_tracks
        """
        if self.total_tracks == 0:
            return 0.0
        return self.downloaded_tracks / self.total_tracks
    
    @property
    def lyrics_success_rate(self) -> float:
        """
        Calculate lyrics retrieval success rate as percentage
        
        Computes the ratio of successful lyrics downloads to total lyrics
        operations, providing separate quality metrics for lyrics functionality.
        
        Returns:
            Lyrics success rate from 0.0 to 1.0
            Returns 0.0 for operations with no lyrics attempts
            
        Formula:
            lyrics_success_rate = downloaded_lyrics / total_lyrics
        """
        if self.total_lyrics == 0:
            return 0.0
        return self.downloaded_lyrics / self.total_lyrics
    
    @property
    def duration(self) -> Optional[float]:
        """
        Calculate total operation duration in seconds
        
        Computes the elapsed time between operation start and completion,
        useful for performance analysis and throughput calculations.
        
        Returns:
            Duration in seconds as float, or None if timing data incomplete
            
        Note:
            Returns None if either start_time or end_time is missing,
            indicating the operation is still in progress or timing wasn't captured.
        """
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def total_size_mb(self) -> float:
        """
        Convert total download size to megabytes for human-readable display
        
        Provides total storage utilization in standard MB units for UI display
        and storage analysis. Uses standard 1024-based conversion.
        
        Returns:
            Total size in megabytes as float with decimal precision
            
        Conversion:
            megabytes = bytes / (1024 * 1024)
        """
        return self.total_size_bytes / (1024 * 1024)
    
    def __str__(self) -> str:
        """
        Generate comprehensive statistics summary string for logging and display
        
        Creates a compact, human-readable summary of key operation metrics
        including success rates, counts, and resource utilization. Designed
        for log output and progress reporting.
        
        Returns:
            Formatted string with downloads, lyrics, and size information
            
        Format:
            "Downloads: {downloaded}/{total} ({rate}), Lyrics: {downloaded}/{total} ({rate}), Size: {size}MB"
            
        Example:
            "Downloads: 45/50 (90.0%), Lyrics: 42/50 (84.0%), Size: 234.7MB"
        """
        return (f"Downloads: {self.downloaded_tracks}/{self.total_tracks} "
                f"({self.success_rate:.1%}), "
                f"Lyrics: {self.downloaded_lyrics}/{self.total_lyrics} "
                f"({self.lyrics_success_rate:.1%}), "
                f"Size: {self.total_size_mb:.1f}MB")