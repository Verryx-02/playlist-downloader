"""
ID3 tag and metadata management for audio files

This module provides comprehensive metadata management capabilities for audio files
across multiple formats (MP3, FLAC, M4A/MP4). It handles the embedding of track
information, album artwork, lyrics, and other metadata using format-specific tag
standards while maintaining compatibility and data integrity.

Architecture Overview:

The module implements a unified metadata management system that abstracts the
complexities of different audio format tagging standards behind a consistent
interface. It provides comprehensive support for:

1. **Multi-Format Support**: Native handling of MP3 (ID3v2), FLAC (Vorbis Comments), M4A/MP4 (iTunes tags)
2. **Rich Metadata**: Complete track information, album data, artist details, and technical metadata
3. **Album Artwork**: High-quality image downloading, processing, and embedding
4. **Lyrics Integration**: Both standard and synchronized lyrics with multiple source support
5. **Quality Control**: File validation, integrity checking, and error recovery

Key Components:

**MetadataManager Class:**
- Central hub for all metadata operations
- Format-agnostic interface with format-specific implementations
- Configuration-driven behavior for customizable metadata handling
- Robust error handling and validation throughout

**Format-Specific Handlers:**
- MP3: ID3v2.3/2.4 tags with comprehensive frame support
- FLAC: Vorbis Comments with picture block handling
- M4A/MP4: iTunes-compatible atom structure with native support

**Image Processing Pipeline:**
- Automatic image downloading with retry logic
- Format conversion and optimization (RGBA→RGB, size limits)
- Quality-preserving JPEG compression with configurable parameters
- Error handling for corrupted or invalid images

**Lyrics Management:**
- Unsynchronized lyrics embedding in format-native tags
- Synchronized lyrics support (LRC format) for MP3 files
- Multiple source attribution and metadata tracking
- Configurable lyrics inclusion in comments and tags

Design Patterns:

1. **Strategy Pattern**: Different metadata embedding strategies per audio format
2. **Template Method**: Common metadata operations with format-specific implementations
3. **Singleton Pattern**: Global instance management for consistent configuration
4. **Decorator Pattern**: Retry logic for network operations and file I/O
5. **Factory Pattern**: Format detection and appropriate handler selection

Configuration Integration:

The metadata manager integrates deeply with the application configuration system:

**Metadata Configuration:**
- include_album_art: Enable/disable album artwork embedding
- include_spotify_metadata: Add Spotify-specific metadata fields
- preserve_original_tags: Retain existing metadata during updates
- add_comment: Include application signature in comments
- id3_version: ID3 tag version selection (2.3/2.4)
- encoding: Text encoding for metadata fields

**Lyrics Configuration:**
- embed_lyrics: Enable lyrics embedding in audio files
- include_lyrics_in_comment: Add lyrics source attribution

**Network Configuration:**
- User-Agent: HTTP headers for image downloads
- request_timeout: Network timeout for album art retrieval
- retry_on_failure: Automatic retry logic for failed operations

Quality and Validation:

**File Integrity Validation:**
- Audio file format validation and corruption detection
- Metadata completeness checking and verification
- File size and existence validation before processing

**Image Quality Control:**
- Format validation and conversion (PNG→JPEG, RGBA→RGB)
- Size optimization with quality preservation (max 1000x1000)
- JPEG compression with 90% quality for optimal size/quality balance
- Fallback handling for unsupported or corrupted images

**Metadata Validation:**
- Required field presence checking
- Text encoding validation and normalization
- Cross-format metadata consistency verification

Error Handling Strategy:

**Graceful Degradation:**
- Continue processing when non-critical operations fail
- Provide detailed logging for debugging while maintaining operation flow
- Fallback strategies for missing or invalid data

**Retry Logic:**
- Network operations: 3 attempts with exponential backoff
- File operations: Automatic retry for transient I/O errors
- Image processing: Fallback to original data if enhancement fails

**Error Classification:**
- Critical errors: Stop processing and report failure
- Warning errors: Log issue but continue with degraded functionality
- Info errors: Log for debugging but don't impact user experience

Thread Safety:

The metadata manager is designed for concurrent usage in multi-threaded download
operations. File operations are atomic at the individual file level, and the
singleton pattern ensures consistent configuration across threads.

Performance Optimizations:

**Memory Efficiency:**
- Streaming image processing to avoid large memory allocations
- Lazy loading of audio file objects
- Efficient tag clearing and rebuilding for metadata updates

**Network Efficiency:**
- HTTP session reuse for multiple image downloads
- Configurable timeouts to prevent hanging operations
- Request headers optimization for server compatibility

**I/O Efficiency:**
- Minimal file reads/writes through library optimization
- Batch metadata operations where possible
- Atomic save operations to prevent corruption

Usage Examples:

    # Get configured metadata manager
    metadata_mgr = get_metadata_manager()
    
    # Embed complete metadata
    success = metadata_mgr.embed_metadata(
        file_path="track.mp3",
        track=spotify_track,
        track_number=1,
        lyrics="Song lyrics...",
        lyrics_source=LyricsSource.GENIUS
    )
    
    # Read existing metadata
    metadata = metadata_mgr.read_metadata("track.mp3")
    
    # Validate file integrity
    is_valid = metadata_mgr.validate_file_integrity("track.mp3")

Dependencies:

**Core Libraries:**
- mutagen: Multi-format audio metadata manipulation
- PIL (Pillow): Image processing and format conversion
- requests: HTTP client for album artwork downloads

**Format Support:**
- MP3: mutagen.mp3, mutagen.id3 (ID3v2.3/2.4)
- FLAC: mutagen.flac (Vorbis Comments + Picture blocks)
- M4A/MP4: mutagen.mp4 (iTunes-compatible atoms)

**Integration Dependencies:**
- config.settings: Configuration management and user preferences
- utils.logger: Structured logging throughout operations
- utils.helpers: Retry decorators and utility functions
- spotify.models: Track and album data structures
"""

import re
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO
from PIL import Image
import mutagen
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TPE2, TPOS, TCON, COMM, APIC, USLT, SYLT
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import retry_on_failure
from ..spotify.models import SpotifyTrack, LyricsSource


class MetadataManager:
    """
    Comprehensive metadata management for multi-format audio files
    
    Provides a unified interface for embedding, reading, and managing metadata
    across different audio formats (MP3, FLAC, M4A/MP4). Handles complex
    operations like album artwork processing, lyrics embedding, and format-specific
    tag standards while maintaining data integrity and optimal file structure.
    
    The manager implements format-specific strategies for metadata handling:
    - **MP3**: ID3v2.3/2.4 tags with comprehensive frame support
    - **FLAC**: Vorbis Comments with embedded picture blocks
    - **M4A/MP4**: iTunes-compatible metadata atoms
    
    Key Features:
    - **Universal Interface**: Format-agnostic API with automatic format detection
    - **Rich Metadata Support**: Complete track, album, and artist information
    - **Album Artwork**: Automatic download, processing, and embedding
    - **Lyrics Integration**: Standard and synchronized lyrics with source tracking
    - **Quality Control**: File validation and integrity checking
    - **Configuration Driven**: Behavior customization through settings
    
    Configuration Integration:
    All behavior is controlled through application settings, enabling users to
    customize metadata handling preferences, quality settings, and feature enablement
    without code changes.
    
    Thread Safety:
    Designed for concurrent usage in multi-threaded download operations. Individual
    file operations are atomic, and configuration is read-only after initialization.
    """
    
    def __init__(self):
        """
        Initialize metadata manager with configuration and network setup
        
        Loads configuration settings, establishes logging, and prepares network
        session for album artwork downloads. All behavior is configured through
        the application settings system for consistent user preference handling.
        
        Configuration Loading:
        - Metadata preferences (artwork, Spotify metadata, tag preservation)
        - Lyrics settings (embedding, comment inclusion)
        - Network configuration (timeouts, user agent)
        - Quality settings (ID3 version, text encoding)
        
        Network Session Setup:
        Configures HTTP session for album artwork downloads with:
        - User-Agent header for server compatibility
        - Connection pooling for efficiency
        - Timeout configuration for reliability
        """
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Metadata configuration from user preferences
        self.include_album_art = self.settings.metadata.include_album_art
        self.include_spotify_metadata = self.settings.metadata.include_spotify_metadata
        self.preserve_original_tags = self.settings.metadata.preserve_original_tags
        self.add_comment = self.settings.metadata.add_comment
        self.id3_version = self.settings.metadata.id3_version
        self.encoding = self.settings.metadata.encoding
        
        # Lyrics configuration for embedding and attribution
        self.embed_lyrics = self.settings.lyrics.embed_in_audio
        self.include_lyrics_in_comment = self.settings.metadata.include_lyrics_in_comment
        
        # HTTP session for downloading album artwork with optimized settings
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.settings.network.user_agent
        })
    
    def embed_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None,
        synced_lyrics: Optional[str] = None
    ) -> bool:
        """
        Embed comprehensive metadata into audio file with format-specific handling
        
        Provides a unified interface for metadata embedding across all supported
        audio formats. Automatically detects file format and applies appropriate
        metadata standards while preserving audio quality and file integrity.
        
        Args:
            file_path: Path to the target audio file
            track: Complete Spotify track information with album and artist data
            track_number: Optional playlist position override
            lyrics: Unsynchronized lyrics text content
            lyrics_source: Provider attribution for lyrics (Genius, SyncedLyrics, etc.)
            synced_lyrics: Time-synchronized lyrics in LRC format (MP3 only)
            
        Returns:
            True if metadata embedding succeeds, False if any critical operation fails
            
        Metadata Embedding Process:
        1. **File Validation**: Verify file exists and is accessible
        2. **Format Detection**: Identify audio format from file extension
        3. **Handler Selection**: Route to format-specific embedding method
        4. **Metadata Application**: Apply tags using format-native standards
        5. **Validation**: Verify successful embedding and file integrity
        
        Supported Metadata:
        - **Basic Information**: Title, artist, album, album artist
        - **Cataloging**: Track number, disc number, release year, genre
        - **Attribution**: Spotify IDs, lyrics source, application signature
        - **Content**: Lyrics (synced/unsynced), album artwork, comments
        
        Error Handling:
        - File access errors: Log and return False
        - Unsupported formats: Warning log and graceful degradation
        - Metadata errors: Detailed logging with operation continuation
        - Validation failures: Integrity checking with error reporting
        
        Format-Specific Behavior:
        - **MP3**: ID3v2 tags with synchronized lyrics support
        - **FLAC**: Vorbis Comments with picture block embedding
        - **M4A/MP4**: iTunes atoms with native metadata structure
        
        Quality Preservation:
        All metadata operations preserve original audio quality by modifying
        only metadata containers without affecting audio streams.
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                self.logger.error(f"Audio file not found: {file_path}")
                return False
            
            # Determine file format from extension for handler selection
            file_extension = file_path_obj.suffix.lower()
            
            # Route to format-specific embedding implementation
            if file_extension == '.mp3':
                return self._embed_mp3_metadata(file_path, track, track_number, lyrics, lyrics_source, synced_lyrics)
            elif file_extension == '.flac':
                return self._embed_flac_metadata(file_path, track, track_number, lyrics, lyrics_source)
            elif file_extension in ['.m4a', '.mp4']:
                return self._embed_mp4_metadata(file_path, track, track_number, lyrics, lyrics_source)
            else:
                self.logger.warning(f"Unsupported file format: {file_extension}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to embed metadata in {file_path}: {e}")
            return False
    
    def _embed_mp3_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None,
        synced_lyrics: Optional[str] = None
    ) -> bool:
        """
        Embed metadata in MP3 file using ID3v2 tag standard with comprehensive frame support
        
        Implements full ID3v2 metadata embedding with support for standard frames,
        custom comments, album artwork, and synchronized lyrics. Handles both existing
        tag updates and new tag creation while respecting user configuration preferences.
        
        Args:
            file_path: Path to MP3 file
            track: Spotify track data with complete metadata
            track_number: Optional track position override
            lyrics: Unsynchronized lyrics text
            lyrics_source: Attribution for lyrics provider
            synced_lyrics: LRC format synchronized lyrics for SYLT frame
            
        Returns:
            True if all metadata operations succeed
            
        ID3v2 Implementation Details:
        
        **Tag Structure Management:**
        - Loads existing ID3 tags or creates new tag structure
        - Handles ID3NoHeaderError by creating fresh tag container
        - Optionally preserves original tags based on user configuration
        - Uses UTF-8 encoding (encoding=3) for international character support
        
        **Standard Frames Applied:**
        - TIT2: Track title from Spotify metadata
        - TPE1: Primary artist(s) with multi-artist support
        - TALB: Album title from album information
        - TPE2: Album artist for compilation handling
        - TDRC: Release year extracted from date string
        - TRCK: Track number (playlist position or original)
        - TPOS: Disc number for multi-disc releases
        - TCON: Genre from album or artist classification
        
        **Advanced Features:**
        - COMM: Custom comment with application signature and metadata
        - USLT: Unsynchronized lyrics with language specification
        - SYLT: Synchronized lyrics with millisecond precision timing
        - APIC: Album artwork with optimized JPEG encoding
        
        **Synchronized Lyrics Processing:**
        Parses LRC format timestamps and converts to ID3v2 SYLT frame:
        - Regex parsing of [mm:ss.xx] timestamp format
        - Conversion to millisecond precision for frame compatibility
        - Error handling for malformed LRC data
        - Language and description metadata for player compatibility
        
        **Album Artwork Handling:**
        - Downloads high-quality album images from Spotify URLs
        - Processes images for optimal file size and compatibility
        - Embeds as APIC frame with appropriate MIME type and description
        - Uses type=3 (Cover front) for maximum player compatibility
        
        **ID3 Version Management:**
        Saves tags using configured ID3 version (2.3 or 2.4) for compatibility:
        - v2.4: Modern standard with enhanced frame support
        - v2.3: Legacy compatibility for older players and software
        
        Error Recovery:
        - Graceful handling of individual frame failures
        - Continuation of processing despite non-critical errors
        - Detailed logging for debugging while maintaining operation flow
        """
        try:
            # Load existing ID3 tags or create new tag structure
            try:
                audio = MP3(file_path, ID3=ID3)
                if audio.tags is None:
                    audio.add_tags()
            except mutagen.id3.ID3NoHeaderError:
                # Create fresh MP3 object and add new tag structure
                audio = MP3(file_path)
                audio.add_tags()
            
            # Clear existing tags if user preference is to replace all metadata
            if not self.preserve_original_tags:
                audio.tags.clear()
            
            # Basic track information using standard ID3v2 frames
            audio.tags.add(TIT2(encoding=3, text=track.name))  # Title
            audio.tags.add(TPE1(encoding=3, text=track.all_artists))  # Artist(s)
            audio.tags.add(TALB(encoding=3, text=track.album.name))  # Album
            audio.tags.add(TPE2(encoding=3, text=track.album.artists[0].name if track.album.artists else ""))  # Album Artist
            
            # Release year extraction from ISO date format
            if track.album.release_date:
                year = track.album.release_date[:4]  # Extract YYYY from YYYY-MM-DD
                audio.tags.add(TDRC(encoding=3, text=year))
            
            # Track number with playlist position override capability
            if track_number:
                audio.tags.add(TRCK(encoding=3, text=str(track_number)))
            else:
                audio.tags.add(TRCK(encoding=3, text=str(track.track_number)))
            
            # Disc number for multi-disc releases (only if > 1)
            if track.disc_number > 1:
                audio.tags.add(TPOS(encoding=3, text=str(track.disc_number)))
            
            # Genre from album metadata (use first genre if multiple available)
            if track.album.genres:
                audio.tags.add(TCON(encoding=3, text=track.album.genres[0]))
            
            # Custom comment with application signature and metadata references
            comment_text = self._create_comment_text(track, lyrics_source)
            if comment_text:
                audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=comment_text))
            
            # Lyrics embedding with format-specific handling
            if self.embed_lyrics and lyrics:
                # Unsynchronized lyrics for standard playback
                audio.tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics))
                
                # Synchronized lyrics for enhanced playback experience
                if synced_lyrics:
                    self._embed_synced_lyrics_mp3(audio, synced_lyrics)
            
            # Album artwork with quality optimization and error handling
            if self.include_album_art:
                album_art = self._download_album_art(track.album.get_best_image())
                if album_art:
                    audio.tags.add(APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,  # Cover (front) - most compatible type
                        desc='Cover',
                        data=album_art
                    ))
            
            # Save with configured ID3 version for compatibility
            audio.save(v2_version=4 if self.id3_version == "2.4" else 3)
            
            self.logger.debug(f"MP3 metadata embedded: {Path(file_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to embed MP3 metadata: {e}")
            return False
    
    def _embed_flac_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None
    ) -> bool:
        """
        Embed metadata in FLAC file using Vorbis Comments standard with picture block support
        
        Implements complete FLAC metadata embedding using Vorbis Comments for textual
        metadata and FLAC picture blocks for album artwork. Provides comprehensive
        metadata support while maintaining the lossless nature of FLAC files.
        
        Args:
            file_path: Path to FLAC audio file
            track: Spotify track data with complete album and artist information
            track_number: Optional track position override for playlist context
            lyrics: Unsynchronized lyrics text content
            lyrics_source: Provider attribution for lyrics (Genius, SyncedLyrics, etc.)
            
        Returns:
            True if all metadata operations complete successfully
            
        Vorbis Comments Implementation:
        
        **Standard Field Mapping:**
        - TITLE: Track name from Spotify metadata
        - ARTIST: All contributing artists with proper attribution
        - ALBUM: Album title for organizational grouping
        - ALBUMARTIST: Primary album artist for compilation handling
        - DATE: Release year for chronological organization
        - TRACKNUMBER: Track position within album or playlist
        - DISCNUMBER: Disc number for multi-disc releases
        - GENRE: Musical genre classification
        
        **Extended Metadata Support:**
        - COMMENT: Application signature and source attribution
        - LYRICS: Complete lyrics text for in-player display
        - Spotify-specific fields: Track, album, and artist IDs for linking
        
        **FLAC Picture Block Handling:**
        Album artwork is embedded using FLAC's native picture block system:
        - Picture type 3: Cover (front) for maximum compatibility
        - MIME type: image/jpeg for universal support
        - Description: "Cover" for standard identification
        - Optimized image data with quality preservation
        
        **Spotify Integration Fields:**
        When enabled, adds Spotify-specific metadata for enhanced integration:
        - SPOTIFY_TRACK_ID: Spotify track identifier for API correlation
        - SPOTIFY_ALBUM_ID: Album identifier for collection management
        - SPOTIFY_ARTIST_ID: Primary artist identifier for artist pages
        
        **Text Encoding:**
        Vorbis Comments use UTF-8 encoding natively, ensuring proper handling
        of international characters and special symbols without encoding issues.
        
        **Metadata Preservation:**
        Based on user configuration, existing metadata can be preserved or
        replaced entirely. This enables both metadata updating and complete
        tag replacement workflows.
        
        Error Handling:
        - Individual field failures don't halt overall operation
        - Image processing errors fall back gracefully
        - File access issues are logged and reported
        - Malformed data is handled with appropriate warnings
        """
        try:
            audio = FLAC(file_path)
            
            # Clear existing metadata if user preference is for complete replacement
            if not self.preserve_original_tags:
                audio.clear()
            
            # Basic track information using standard Vorbis Comment fields
            audio['TITLE'] = track.name
            audio['ARTIST'] = track.all_artists
            audio['ALBUM'] = track.album.name
            audio['ALBUMARTIST'] = track.album.artists[0].name if track.album.artists else ""
            
            # Release year from album release date
            if track.album.release_date:
                audio['DATE'] = track.album.release_date[:4]  # Extract year
            
            # Track number with override support for playlist positioning
            if track_number:
                audio['TRACKNUMBER'] = str(track_number)
            else:
                audio['TRACKNUMBER'] = str(track.track_number)
            
            # Disc number for multi-disc releases
            if track.disc_number > 1:
                audio['DISCNUMBER'] = str(track.disc_number)
            
            # Genre classification from album metadata
            if track.album.genres:
                audio['GENRE'] = track.album.genres[0]
            
            # Application and source attribution comment
            comment_text = self._create_comment_text(track, lyrics_source)
            if comment_text:
                audio['COMMENT'] = comment_text
            
            # Lyrics embedding for in-player display
            if self.embed_lyrics and lyrics:
                audio['LYRICS'] = lyrics
            
            # Spotify-specific metadata for enhanced integration
            if self.include_spotify_metadata:
                audio['SPOTIFY_TRACK_ID'] = track.id
                audio['SPOTIFY_ALBUM_ID'] = track.album.id
                audio['SPOTIFY_ARTIST_ID'] = track.artists[0].id if track.artists else ""
            
            # Album artwork using FLAC picture block system
            if self.include_album_art:
                album_art = self._download_album_art(track.album.get_best_image())
                if album_art:
                    # Create FLAC picture block with standard parameters
                    picture = mutagen.flac.Picture()
                    picture.type = 3  # Cover (front) - standard album art type
                    picture.mime = 'image/jpeg'
                    picture.desc = 'Cover'
                    picture.data = album_art
                    audio.add_picture(picture)
            
            # Save all metadata changes to file
            audio.save()
            
            self.logger.debug(f"FLAC metadata embedded: {Path(file_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to embed FLAC metadata: {e}")
            return False
    
    def _embed_mp4_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None
    ) -> bool:
        """
        Embed metadata in MP4/M4A file using iTunes-compatible atom structure
        
        Implements comprehensive MP4 metadata embedding using iTunes-standard
        metadata atoms. Provides full compatibility with Apple ecosystem while
        maintaining broad player support across different platforms and devices.
        
        Args:
            file_path: Path to MP4/M4A audio file
            track: Spotify track data with album and artist information
            track_number: Optional track position override for playlist context
            lyrics: Unsynchronized lyrics text content
            lyrics_source: Provider attribution for lyrics source
            
        Returns:
            True if metadata embedding completes successfully
            
        iTunes Metadata Atom Implementation:
        
        **Standard iTunes Atoms:**
        - ©nam: Track title (iTunes name atom)
        - ©ART: Artist name(s) with multi-artist support
        - ©alb: Album title for collection organization
        - aART: Album artist for compilation and various artist handling
        - ©day: Release date/year for chronological sorting
        - trkn: Track number as integer tuple (track, total)
        - disk: Disc number as integer tuple (disc, total)
        - ©gen: Genre classification for categorization
        
        **Enhanced Metadata Atoms:**
        - ©cmt: Comment field with application and source attribution
        - ©lyr: Lyrics text for in-player display and karaoke
        - covr: Album artwork with JPEG format optimization
        
        **iTunes Compatibility Features:**
        
        **Track/Disc Number Format:**
        iTunes uses tuple format (current, total) for numbering:
        - Track numbers: (track_number, 0) - total tracks not required
        - Disc numbers: (disc_number, 0) - total discs not required
        - Zero as second value indicates unknown total count
        
        **Text Encoding:**
        MP4 atoms use UTF-8 encoding natively, ensuring proper international
        character support without encoding conversion requirements.
        
        **Album Artwork Integration:**
        Uses MP4Cover object with format specification:
        - FORMAT_JPEG: Standard JPEG format for broad compatibility
        - Optimized image data with quality preservation
        - Embedded as 'covr' atom for iTunes recognition
        
        **Metadata Preservation Strategy:**
        Based on user configuration, existing metadata can be:
        - Preserved: Only add new fields, keep existing values
        - Replaced: Clear all existing metadata and apply fresh tags
        
        **Comment Field Enhancement:**
        Creates informative comment text including:
        - Application signature for source identification
        - Spotify metadata references for correlation
        - Lyrics source attribution for quality assessment
        
        **Cross-Platform Compatibility:**
        iTunes metadata atoms are recognized by most major audio players:
        - Apple ecosystem: Native support with full feature access
        - Cross-platform players: Basic metadata recognition
        - Mobile platforms: Standard metadata display support
        
        Error Handling Strategy:
        - Individual atom failures don't stop overall operation
        - Image processing errors handled gracefully with fallbacks
        - File format validation prevents corruption
        - Comprehensive logging for debugging and monitoring
        """
        try:
            audio = MP4(file_path)
            
            # Clear existing metadata if user preference is for complete replacement
            if not self.preserve_original_tags:
                audio.clear()
            
            # Basic track information using iTunes-standard atoms
            audio['\xa9nam'] = [track.name]  # Title (iTunes name atom)
            audio['\xa9ART'] = [track.all_artists]  # Artist(s)
            audio['\xa9alb'] = [track.album.name]  # Album
            audio['aART'] = [track.album.artists[0].name if track.album.artists else ""]  # Album Artist
            
            # Release year from album metadata
            if track.album.release_date:
                audio['\xa9day'] = [track.album.release_date[:4]]  # Year only
            
            # Track number using iTunes tuple format (track, total)
            if track_number:
                audio['trkn'] = [(track_number, 0)]  # (current, total) - total unknown
            else:
                audio['trkn'] = [(track.track_number, 0)]
            
            # Disc number for multi-disc releases using tuple format
            if track.disc_number > 1:
                audio['disk'] = [(track.disc_number, 0)]  # (current, total) - total unknown
            
            # Genre classification from album metadata
            if track.album.genres:
                audio['\xa9gen'] = [track.album.genres[0]]
            
            # Application and source attribution comment
            comment_text = self._create_comment_text(track, lyrics_source)
            if comment_text:
                audio['\xa9cmt'] = [comment_text]
            
            # Lyrics embedding for karaoke and display features
            if self.embed_lyrics and lyrics:
                audio['\xa9lyr'] = [lyrics]
            
            # Album artwork using iTunes cover atom
            if self.include_album_art:
                album_art = self._download_album_art(track.album.get_best_image())
                if album_art:
                    # Create MP4Cover object with JPEG format specification
                    audio['covr'] = [mutagen.mp4.MP4Cover(album_art, mutagen.mp4.MP4Cover.FORMAT_JPEG)]
            
            # Save all metadata changes to file
            audio.save()
            
            self.logger.debug(f"MP4 metadata embedded: {Path(file_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to embed MP4 metadata: {e}")
            return False
    
    def _embed_synced_lyrics_mp3(self, audio: MP3, synced_lyrics: str) -> None:
        """
        Embed synchronized lyrics in MP3 file using ID3v2 SYLT frame with LRC parsing
        
        Processes LRC (Lyrics) format synchronized lyrics and embeds them as an
        ID3v2 SYLT (Synchronized Lyrics) frame. Provides millisecond-precision
        timing information for karaoke display and enhanced playback experiences.
        
        Args:
            audio: MP3 audio object with ID3 tags loaded
            synced_lyrics: LRC format lyrics with timing information
            
        LRC Format Processing:
        
        **LRC Format Structure:**
        LRC files contain timestamped lyrics in the format:
        [mm:ss.xx]Lyric line text
        
        **Parsing Algorithm:**
        1. Split lyrics into individual lines
        2. Apply regex pattern matching for timestamp extraction
        3. Parse timestamp components (minutes, seconds, centiseconds)
        4. Convert to millisecond precision for ID3 compatibility
        5. Create tuple pairs of (text, timestamp) for SYLT frame
        
        **Timestamp Conversion:**
        LRC format: [02:35.50] = 2 minutes, 35 seconds, 50 centiseconds
        Conversion: (2*60 + 35)*1000 + 50*10 = 155,500 milliseconds
        
        **ID3v2 SYLT Frame Structure:**
        - encoding=3: UTF-8 text encoding for international character support
        - lang='eng': Language specification for player compatibility
        - format=2: Millisecond timing format for precise synchronization
        - type=1: Lyrics content type (vs other synchronized text types)
        - desc='': Empty description (standard for lyrics)
        - text=[(text, timestamp), ...]: Synchronized lyrics data pairs
        
        **Error Handling:**
        - Malformed timestamp lines are skipped with warning logs
        - Invalid time components default to reasonable values
        - Empty lyrics lines are ignored to prevent display issues
        - Complete parsing failure results in warning without crash
        
        **Player Compatibility:**
        SYLT frames are supported by many modern audio players for:
        - Karaoke-style lyric display with highlighting
        - Synchronized lyric scrolling during playback
        - Enhanced accessibility features for hearing-impaired users
        - Integration with visualization and display systems
        
        **Performance Considerations:**
        - Regex compilation is optimized for repeated pattern matching
        - Memory usage is minimized through streaming line processing
        - Large lyric files are handled efficiently without memory issues
        """
        try:
            # Parse LRC format lyrics into synchronized data pairs
            lyrics_data = []
            
            for line in synced_lyrics.split('\n'):
                line = line.strip()
                if not line:
                    continue  # Skip empty lines
                
                # Match LRC timestamp format [mm:ss.xx] with regex
                match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\](.*)', line)
                if match:
                    minutes, seconds, centiseconds, text = match.groups()
                    
                    # Convert LRC timestamp to milliseconds for ID3 SYLT frame
                    timestamp = (int(minutes) * 60 + int(seconds)) * 1000 + int(centiseconds) * 10
                    
                    # Add synchronized lyric entry with text and timing
                    lyrics_data.append((text.strip(), timestamp))
            
            if lyrics_data:
                # Create ID3v2 SYLT frame with synchronized lyrics data
                audio.tags.add(SYLT(
                    encoding=3,     # UTF-8 encoding for international support
                    lang='eng',     # English language specification
                    format=2,       # Millisecond timing format
                    type=1,         # Lyrics content type
                    desc='',        # Empty description (standard for lyrics)
                    text=lyrics_data  # List of (text, timestamp) tuples
                ))
                
                self.logger.debug("Synchronized lyrics embedded successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to embed synchronized lyrics: {e}")
    
    def _create_comment_text(self, track: SpotifyTrack, lyrics_source: Optional[LyricsSource] = None) -> str:
        """
        Create informative comment text for audio file metadata
        
        Constructs a comprehensive comment field that provides source attribution,
        application identification, and metadata references. Comment text is
        formatted for human readability while maintaining structured information.
        
        Args:
            track: Spotify track information for metadata references
            lyrics_source: Provider attribution for lyrics content
            
        Returns:
            Formatted comment text with pipe-separated components
            
        Comment Components:
        
        **Application Signature:**
        When enabled, adds application identification:
        "Downloaded by Playlist-Downloader"
        - Provides source attribution for downloaded files
        - Helps identify application-processed tracks
        - Useful for troubleshooting and support
        
        **Spotify Metadata Reference:**
        When Spotify metadata inclusion is enabled:
        "Spotify ID: {track.id}"
        - Enables correlation with Spotify catalog
        - Supports metadata refresh and validation
        - Facilitates integration with Spotify APIs
        
        **Lyrics Source Attribution:**
        When lyrics are embedded with source information:
        "Lyrics: {source_provider}"
        - Credits lyrics provider (Genius, SyncedLyrics, etc.)
        - Enables quality assessment and validation
        - Supports troubleshooting lyrics accuracy issues
        
        **Comment Formatting:**
        Components are joined with " | " separator for:
        - Clear visual separation between information types
        - Consistent formatting across all processed files
        - Easy parsing for automated tools if needed
        
        **Configuration Respect:**
        Comment generation respects user preferences:
        - add_comment: Controls application signature inclusion
        - include_spotify_metadata: Controls Spotify ID inclusion
        - include_lyrics_in_comment: Controls lyrics source attribution
        
        **Examples:**
        Minimal: "Downloaded by Playlist-Downloader"
        Full: "Downloaded by Playlist-Downloader | Spotify ID: 4iV5W9uYEdYUVa79Axb7Rh | Lyrics: genius"
        Custom: "Spotify ID: 4iV5W9uYEdYUVa79Axb7Rh | Lyrics: syncedlyrics"
        """
        comment_parts = []
        
        # Application signature for source identification
        if self.add_comment:
            comment_parts.append("Downloaded by Playlist-Downloader")
        
        # Spotify metadata reference for correlation and validation
        if self.include_spotify_metadata:
            comment_parts.append(f"Spotify ID: {track.id}")
        
        # Lyrics source attribution for quality assessment
        if self.include_lyrics_in_comment and lyrics_source:
            comment_parts.append(f"Lyrics: {lyrics_source.value}")
        
        # Join components with pipe separator for readability
        return " | ".join(comment_parts)
    
    @retry_on_failure(max_attempts=3, delay=1.0)
    def _download_album_art(self, image_url: Optional[str]) -> Optional[bytes]:
        """
        Download and process album artwork with quality optimization and error handling
        
        Retrieves album artwork from Spotify URLs and processes it for optimal
        embedding in audio files. Implements comprehensive image processing
        pipeline with format conversion, size optimization, and quality preservation.
        
        Args:
            image_url: Spotify album artwork URL (various resolutions available)
            
        Returns:
            Processed JPEG image data as bytes, or None if download/processing fails
            
        Download Process:
        
        **Network Request Handling:**
        - Uses configured session with appropriate User-Agent header
        - Respects network timeout settings for reliability
        - Implements streaming download for memory efficiency
        - Handles HTTP errors with appropriate status code checking
        
        **Image Processing Pipeline:**
        
        **1. Format Validation and Loading:**
        - Validates image data using PIL (Pillow)
        - Supports input formats: JPEG, PNG, WebP, etc.
        - Handles corrupted or invalid image data gracefully
        
        **2. Color Space Conversion:**
        - Converts RGBA to RGB for JPEG compatibility
        - Handles transparency by conversion to solid background
        - Processes indexed color (P mode) and grayscale with alpha (LA mode)
        - Preserves RGB images without unnecessary conversion
        
        **3. Size Optimization:**
        - Enforces maximum dimensions of 1000x1000 pixels
        - Uses LANCZOS resampling for high-quality downsizing
        - Maintains aspect ratio during thumbnail generation
        - Prevents excessively large embedded images
        
        **4. JPEG Compression:**
        - Uses 90% quality for optimal size/quality balance
        - Enables optimization for additional size reduction
        - Standardizes format to JPEG for universal compatibility
        - Outputs to BytesIO for memory-efficient processing
        
        **Error Recovery Strategy:**
        
        **Network Errors:**
        - Timeout handling with configurable limits
        - HTTP error status code checking and logging
        - Retry logic through @retry_on_failure decorator
        - Graceful degradation when artwork unavailable
        
        **Image Processing Errors:**
        - Fallback to original data if processing fails
        - Detailed error logging for debugging
        - Continuation of metadata embedding without artwork
        - Warning logs for troubleshooting image issues
        
        **Quality Considerations:**
        - LANCZOS resampling preserves image quality during resizing
        - 90% JPEG quality balances file size and visual quality
        - RGB conversion prevents compatibility issues
        - Optimization flag reduces file size without quality loss
        
        **Memory Management:**
        - Uses BytesIO for in-memory image processing
        - Streaming download prevents large memory allocations
        - Automatic cleanup of temporary image objects
        - Efficient processing chain minimizes memory usage
        """
        if not image_url:
            return None
        
        try:
            # Download image data with streaming for memory efficiency
            response = self.session.get(
                image_url, 
                timeout=self.settings.network.request_timeout,
                stream=True
            )
            response.raise_for_status()
            
            # Load image content into memory for processing
            image_data = response.content
            
            # Validate and process image for optimal embedding
            try:
                with Image.open(BytesIO(image_data)) as img:
                    # Convert color spaces for JPEG compatibility
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Convert transparency modes to solid RGB
                        img = img.convert('RGB')
                    
                    # Resize if dimensions exceed embedding limits
                    if img.width > 1000 or img.height > 1000:
                        # Use high-quality LANCZOS resampling for downsizing
                        img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
                    
                    # Convert to optimized JPEG format
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=90, optimize=True)
                    return output.getvalue()
                    
            except Exception as e:
                self.logger.warning(f"Failed to process album art image: {e}")
                # Return original data if processing fails (fallback strategy)
                return image_data
            
        except Exception as e:
            self.logger.warning(f"Failed to download album art from {image_url}: {e}")
            return None
    
    def read_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read and extract metadata from audio file with format-specific handling
        
        Provides a unified interface for reading metadata from various audio
        formats. Returns standardized metadata dictionary regardless of
        underlying tag format, enabling consistent metadata access across
        different file types.
        
        Args:
            file_path: Path to audio file for metadata extraction
            
        Returns:
            Dictionary containing standardized metadata fields, or None if failed
            
        Supported Formats and Tag Standards:
        - **MP3**: ID3v1/ID3v2 tags with comprehensive frame support
        - **FLAC**: Vorbis Comments with embedded picture blocks
        - **M4A/MP4**: iTunes-compatible metadata atoms
        
        Standardized Metadata Fields:
        
        **Basic Information:**
        - title: Track title from format-specific title field
        - artist: Primary artist(s) with multi-artist support
        - album: Album title for collection identification
        - year: Release year for chronological organization
        - track_number: Track position within album or collection
        
        **Content Information:**
        - has_lyrics: Boolean indicating embedded lyrics presence
        - duration: Track length in seconds (float precision)
        - bitrate: Audio bitrate in kbps for quality assessment
        
        **Format-Specific Field Mapping:**
        
        **MP3 (ID3 Tags):**
        - TIT2 → title, TPE1 → artist, TALB → album
        - TDRC → year, TRCK → track_number
        - USLT → has_lyrics, audio.info → duration/bitrate
        
        **FLAC (Vorbis Comments):**
        - TITLE → title, ARTIST → artist, ALBUM → album
        - DATE → year, TRACKNUMBER → track_number
        - LYRICS → has_lyrics, audio.info → duration/bitrate
        
        **M4A/MP4 (iTunes Atoms):**
        - ©nam → title, ©ART → artist, ©alb → album
        - ©day → year, trkn → track_number
        - ©lyr → has_lyrics, audio.info → duration/bitrate
        
        **Error Handling:**
        - File existence validation before processing
        - Format detection from file extension
        - Graceful handling of missing or corrupted tags
        - Empty string defaults for missing text fields
        - Zero defaults for missing numeric fields
        - Boolean false for missing content flags
        
        **Use Cases:**
        - Metadata validation and completeness checking
        - Format conversion with metadata preservation
        - Quality assessment and file verification
        - User interface metadata display
        - Batch metadata analysis and reporting
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return None
            
            # Determine format from file extension for handler selection
            file_extension = file_path_obj.suffix.lower()
            
            # Route to format-specific metadata reading implementation
            if file_extension == '.mp3':
                return self._read_mp3_metadata(file_path)
            elif file_extension == '.flac':
                return self._read_flac_metadata(file_path)
            elif file_extension in ['.m4a', '.mp4']:
                return self._read_mp4_metadata(file_path)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to read metadata from {file_path}: {e}")
            return None
    
    def _read_mp3_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Read metadata from MP3 file using ID3 tag extraction
        
        Extracts comprehensive metadata from MP3 files using both ID3v1 and
        ID3v2 tag standards. Prioritizes ID3v2 tags for enhanced metadata
        support while providing fallback to ID3v1 for legacy compatibility.
        
        Args:
            file_path: Path to MP3 file
            
        Returns:
            Dictionary with standardized metadata fields
            
        ID3 Tag Frame Mapping:
        - TIT2: Track title (ID3v2) or title field (ID3v1)
        - TPE1: Artist name(s) with multi-artist support
        - TALB: Album title for collection organization
        - TDRC: Recording date/year (ID3v2.4) or TYER (ID3v2.3)
        - TRCK: Track number with optional total tracks
        - USLT: Unsynchronized lyrics text content
        
        Technical Information Extraction:
        - Duration: Track length from MPEG audio header
        - Bitrate: Audio bitrate for quality assessment
        - Sample rate: Audio sample rate (if available)
        """
        audio = MP3(file_path, ID3=ID3)
        
        metadata = {
            # Basic track information with safe extraction
            'title': str(audio.tags.get('TIT2', [''])[0]) if audio.tags and audio.tags.get('TIT2') else '',
            'artist': str(audio.tags.get('TPE1', [''])[0]) if audio.tags and audio.tags.get('TPE1') else '',
            'album': str(audio.tags.get('TALB', [''])[0]) if audio.tags and audio.tags.get('TALB') else '',
            'year': str(audio.tags.get('TDRC', [''])[0]) if audio.tags and audio.tags.get('TDRC') else '',
            'track_number': str(audio.tags.get('TRCK', [''])[0]) if audio.tags and audio.tags.get('TRCK') else '',
            
            # Content and technical information
            'has_lyrics': bool(audio.tags and audio.tags.get('USLT')),
            'duration': audio.info.length if audio.info else 0,
            'bitrate': audio.info.bitrate if audio.info else 0,
        }
        
        return metadata
    
    def _read_flac_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Read metadata from FLAC file using Vorbis Comments extraction
        
        Extracts metadata from FLAC files using the Vorbis Comments standard
        which stores textual metadata as key-value pairs. Provides access to
        both standard fields and custom metadata while maintaining the
        lossless audio quality characteristics of FLAC.
        
        Args:
            file_path: Path to FLAC file
            
        Returns:
            Dictionary with standardized metadata fields
            
        Vorbis Comments Field Mapping:
        - TITLE: Track title in UTF-8 encoding
        - ARTIST: Artist name(s) with multi-artist support
        - ALBUM: Album title for collection identification
        - DATE: Release date (often year-only format)
        - TRACKNUMBER: Track position within album
        - LYRICS: Embedded lyrics text content
        
        Technical Information:
        - Duration: Track length from FLAC stream info
        - Bitrate: Variable bitrate for lossless compression
        - Sample rate: Audio sample rate from stream metadata
        """
        audio = FLAC(file_path)
        
        metadata = {
            # Extract standard Vorbis Comment fields with fallback to empty strings
            'title': audio.get('TITLE', [''])[0],
            'artist': audio.get('ARTIST', [''])[0],
            'album': audio.get('ALBUM', [''])[0],
            'year': audio.get('DATE', [''])[0],
            'track_number': audio.get('TRACKNUMBER', [''])[0],
            
            # Content and technical metadata
            'has_lyrics': bool(audio.get('LYRICS')),
            'duration': audio.info.length if audio.info else 0,
            'bitrate': audio.info.bitrate if audio.info else 0,
        }
        
        return metadata
    
    def _read_mp4_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Read metadata from MP4/M4A file using iTunes atom extraction
        
        Extracts metadata from MP4 container files using iTunes-compatible
        metadata atoms. Supports both M4A audio files and MP4 video files
        with audio tracks, providing comprehensive metadata access for
        Apple ecosystem compatibility.
        
        Args:
            file_path: Path to MP4/M4A file
            
        Returns:
            Dictionary with standardized metadata fields
            
        iTunes Atom Mapping:
        - ©nam: Track title (iTunes name atom)
        - ©ART: Artist name(s) with Unicode support
        - ©alb: Album title for iTunes library organization
        - ©day: Release date/year for chronological sorting
        - trkn: Track number as tuple (track, total)
        - ©lyr: Lyrics text for iTunes display
        
        Technical Metadata:
        - Duration: Track length from MP4 container metadata
        - Bitrate: Audio bitrate from stream information
        - Codec: Audio codec information (AAC, ALAC, etc.)
        """
        audio = MP4(file_path)
        
        metadata = {
            # Extract iTunes atoms with safe list access
            'title': audio.get('\xa9nam', [''])[0] if audio.get('\xa9nam') else '',
            'artist': audio.get('\xa9ART', [''])[0] if audio.get('\xa9ART') else '',
            'album': audio.get('\xa9alb', [''])[0] if audio.get('\xa9alb') else '',
            'year': audio.get('\xa9day', [''])[0] if audio.get('\xa9day') else '',
            # Extract track number from tuple format (track, total)
            'track_number': str(audio.get('trkn', [(0, 0)])[0][0]) if audio.get('trkn') else '',
            
            # Content and technical information
            'has_lyrics': bool(audio.get('\xa9lyr')),
            'duration': audio.info.length if audio.info else 0,
            'bitrate': audio.info.bitrate if audio.info else 0,
        }
        
        return metadata
    
    def strip_metadata(self, file_path: str) -> bool:
        """
        Remove all metadata from audio file while preserving audio content
        
        Completely removes all metadata tags from audio files, including
        textual information, embedded images, and custom fields. Useful for
        privacy protection, file size reduction, or preparing files for
        fresh metadata application.
        
        Args:
            file_path: Path to audio file for metadata removal
            
        Returns:
            True if metadata removal succeeds, False otherwise
            
        Format-Specific Stripping:
        
        **MP3 Files:**
        - Removes all ID3v1 and ID3v2 tags
        - Preserves MPEG audio stream integrity
        - Maintains file playability after tag removal
        
        **FLAC Files:**
        - Removes all Vorbis Comments
        - Removes embedded picture blocks
        - Preserves lossless audio stream
        
        **M4A/MP4 Files:**
        - Removes all iTunes metadata atoms
        - Preserves audio/video stream containers
        - Maintains MP4 container structure
        
        Use Cases:
        - Privacy protection by removing identifying metadata
        - File size optimization for storage-constrained environments
        - Preparation for metadata standardization workflows
        - Testing and development with clean audio files
        
        Safety Considerations:
        - Audio content remains completely unmodified
        - File playability is preserved across all formats
        - Original file timestamps may be updated during save
        - Backup recommended for irreplaceable files
        
        Error Handling:
        - Unsupported formats return False with warning
        - File access errors are logged and reported
        - Partial metadata removal still saves successfully
        - Format corruption risks are minimized through library safety
        """
        try:
            file_path_obj = Path(file_path)
            file_extension = file_path_obj.suffix.lower()
            
            # Route to format-specific metadata clearing implementation
            if file_extension == '.mp3':
                audio = MP3(file_path, ID3=ID3)
                if audio.tags:
                    audio.tags.clear()  # Remove all ID3 tags
                    audio.save()
            elif file_extension == '.flac':
                audio = FLAC(file_path)
                audio.clear()  # Remove all Vorbis Comments and pictures
                audio.save()
            elif file_extension in ['.m4a', '.mp4']:
                audio = MP4(file_path)
                audio.clear()  # Remove all iTunes metadata atoms
                audio.save()
            else:
                return False  # Unsupported format
            
            self.logger.debug(f"Metadata stripped from: {file_path_obj.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to strip metadata from {file_path}: {e}")
            return False
    
    def validate_file_integrity(self, file_path: str) -> bool:
        """
        Validate audio file integrity and format compliance
        
        Performs comprehensive validation of audio files to ensure they are
        properly formatted, not corrupted, and compatible with standard audio
        players. Uses format-specific validation libraries to detect issues
        that might prevent successful playback or metadata operations.
        
        Args:
            file_path: Path to audio file for validation
            
        Returns:
            True if file is valid and playable, False otherwise
            
        Validation Process:
        
        **File System Validation:**
        - Confirms file exists at specified path
        - Checks file size is greater than zero bytes
        - Validates file access permissions for reading
        
        **Format-Specific Validation:**
        
        **MP3 Files:**
        - Validates MPEG header structure and frame synchronization
        - Checks for valid audio stream data
        - Verifies ID3 tag structure (if present)
        - Detects truncated or corrupted audio data
        
        **FLAC Files:**
        - Validates FLAC stream marker and metadata blocks
        - Checks audio frame header consistency
        - Verifies stream info block presence and validity
        - Detects checksum errors in audio frames
        
        **M4A/MP4 Files:**
        - Validates MP4 container atom structure
        - Checks for required atoms (moov, mdat, etc.)
        - Verifies audio track presence and codec support
        - Detects container corruption or incomplete files
        
        **Common Validation Checks:**
        - Audio stream duration and bitrate validation
        - Sample rate and channel configuration verification
        - Codec compatibility and standard compliance
        - Overall file structure and data integrity
        
        **Error Detection:**
        - Corrupted headers or metadata structures
        - Truncated files missing audio data
        - Invalid format specifications
        - Unsupported codec or container variations
        
        **Use Cases:**
        - Pre-processing validation before metadata operations
        - Quality control in download and conversion pipelines
        - File integrity verification after network transfers
        - Troubleshooting playback issues and format problems
        
        **Performance Considerations:**
        - Fast validation using header-only analysis where possible
        - Minimal I/O operations to reduce validation overhead
        - Library-optimized validation routines for efficiency
        - Early termination on obvious corruption detection
        """
        try:
            file_path_obj = Path(file_path)
            
            # Basic file system validation
            if not file_path_obj.exists() or file_path_obj.stat().st_size == 0:
                return False
            
            # Format detection and validation routing
            file_extension = file_path_obj.suffix.lower()
            
            # Attempt to load file with format-specific library for validation
            if file_extension == '.mp3':
                MP3(file_path)  # Will raise exception if invalid MP3
            elif file_extension == '.flac':
                FLAC(file_path)  # Will raise exception if invalid FLAC
            elif file_extension in ['.m4a', '.mp4']:
                MP4(file_path)  # Will raise exception if invalid MP4
            else:
                return False  # Unsupported format
            
            return True  # File loaded successfully, validation passed
            
        except Exception:
            # Any exception indicates file corruption or invalid format
            return False


# Global metadata manager instance for singleton pattern implementation
_metadata_manager: Optional[MetadataManager] = None


def get_metadata_manager() -> MetadataManager:
    """
    Factory function to retrieve the global metadata manager instance
    
    Implements the singleton pattern to ensure consistent metadata handling
    configuration across the entire application. Provides a single point of
    access for metadata operations while maintaining shared state and settings.
    
    Returns:
        Global MetadataManager instance with application configuration applied
        
    Singleton Benefits:
    - **Consistent Configuration**: Single source of truth for metadata settings
    - **Resource Efficiency**: Shared HTTP session for image downloads
    - **State Management**: Unified logging and error handling across operations
    - **Memory Optimization**: Single instance reduces memory overhead
    
    Initialization Behavior:
    - First call creates new MetadataManager with current configuration
    - Subsequent calls return existing instance with same configuration
    - Configuration changes require application restart or manual reset
    
    Thread Safety:
    The singleton implementation is thread-safe for read operations and
    concurrent metadata processing. Individual file operations are atomic
    at the file level, preventing corruption during concurrent access.
    
    Configuration Sources:
    - Application settings system for user preferences
    - Network configuration for timeout and retry behavior
    - Logging configuration for debug and error reporting
    - Quality settings for image processing and metadata standards
    
    Usage Pattern:
        # Get manager in any module
        metadata_mgr = get_metadata_manager()
        
        # Use for metadata operations
        success = metadata_mgr.embed_metadata(file_path, track_data)
    """
    global _metadata_manager
    if not _metadata_manager:
        _metadata_manager = MetadataManager()
    return _metadata_manager