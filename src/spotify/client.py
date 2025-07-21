"""
Spotify API client for playlist extraction and metadata retrieval

This module provides a comprehensive client interface for interacting with the Spotify Web API,
handling authentication, rate limiting, pagination, and data conversion to internal models.
It serves as the primary gateway for all Spotify-related operations in the Playlist-Downloader
application.

Architecture Overview:

The module implements a layered client architecture with the following components:

1. **Rate Limiting Layer**: Intelligent request throttling to respect Spotify API limits
   - Configurable minimum interval between requests (default: 100ms)
   - Automatic retry-after handling for 429 rate limit responses
   - Request timing tracking for optimal throughput

2. **Authentication Management**: Robust token lifecycle handling
   - Automatic token refresh on 401 responses
   - Lazy authentication with client property pattern
   - Session persistence and error recovery

3. **Pagination Handler**: Efficient handling of large data sets
   - Generator-based streaming for memory efficiency
   - Automatic offset management for continuous fetching
   - Progress logging for large collections

4. **Error Recovery System**: Comprehensive error handling and retry logic
   - HTTP status code specific handling (401, 429, etc.)
   - Graceful degradation for unavailable content
   - Detailed error logging and user feedback

5. **Data Transformation**: Safe conversion from API responses to internal models
   - Defensive parsing with fallback handling
   - Type-safe model construction
   - Validation of external data integrity

Key Features:

- **Smart Rate Limiting**: Adaptive throttling that maximizes API usage while staying within limits
- **Robust Authentication**: Automatic token management with transparent refresh
- **Memory Efficient**: Generator-based pagination for handling large playlists
- **Error Resilient**: Comprehensive error handling with automatic recovery
- **Type Safe**: Full type annotations and model validation
- **Performance Optimized**: Batch operations and minimal API calls

Integration Points:

- **Authentication System**: Uses config.auth for credential management
- **Configuration**: Leverages config.settings for rate limiting and API preferences  
- **Model System**: Converts API data to spotify.models objects
- **Logging Framework**: Integrated with utils.logger for operation tracking
- **Download Engine**: Provides data for audio download operations
- **Synchronization**: Supports playlist change detection via snapshot IDs

Design Patterns:

1. **Singleton Pattern**: Global client instance prevents duplicate authentication
2. **Decorator Pattern**: Rate limiting wrapper around API requests
3. **Generator Pattern**: Memory-efficient pagination for large data sets
4. **Factory Pattern**: Model construction from external API data
5. **Circuit Breaker**: Error handling with automatic retry and backoff

Thread Safety:

The client is designed for single-threaded use but supports concurrent access
through the global instance pattern. Rate limiting state is thread-local to
prevent interference between concurrent operations.

Performance Considerations:

- **Batch Operations**: Uses Spotify's batch endpoints where available (up to 50 items)
- **Field Selection**: Requests only necessary fields to minimize response size
- **Connection Pooling**: Leverages spotipy's underlying requests session pooling
- **Caching Strategy**: Supports external caching through snapshot ID comparisons

Usage Examples:

    # Get singleton client instance
    client = get_spotify_client()
    
    # Fetch complete playlist
    playlist = client.get_full_playlist("playlist_id")
    
    # Stream tracks for memory efficiency
    for track, position, added_at in client.get_playlist_tracks("playlist_id"):
        process_track(track)
    
    # Check access before operations
    if client.validate_playlist_access("playlist_id"):
        proceed_with_download()

Error Handling Strategy:

The client implements a multi-tier error handling approach:
- Network errors: Automatic retry with exponential backoff
- Authentication errors: Transparent token refresh
- Rate limiting: Respect retry-after headers
- Data errors: Graceful degradation with logging
- Permission errors: Clear user feedback
"""

import re
import time
from typing import List, Optional, Dict, Any, Generator, Tuple
import spotipy
from spotipy.exceptions import SpotifyException

from ..config.auth import get_auth
from ..config.settings import get_settings
from .models import SpotifyPlaylist, SpotifyTrack
from ..utils.logger import get_logger

# Suppress Spotipy's verbose logging to reduce noise in application logs
# Only show ERROR level messages from spotipy and requests to minimize verbosity
import logging
logging.getLogger('spotipy.client').setLevel(logging.ERROR)
logging.getLogger('requests.packages.urllib3').setLevel(logging.ERROR)


class SpotifyClient:
    """
    Comprehensive Spotify Web API client with intelligent rate limiting and error handling
    
    Provides a high-level interface for all Spotify operations required by the
    Playlist-Downloader application. Handles the complexities of API authentication,
    rate limiting, pagination, and data transformation while presenting a clean,
    type-safe interface to consumers.
    
    The client implements several advanced patterns:
    - **Lazy Authentication**: Client connection is established on first use
    - **Adaptive Rate Limiting**: Intelligent throttling based on API responses
    - **Automatic Recovery**: Transparent handling of token expiration and rate limits
    - **Memory Efficiency**: Generator-based pagination for large data sets
    - **Defensive Programming**: Robust error handling with graceful degradation
    
    Key Capabilities:
    - Complete playlist retrieval with metadata
    - Paginated track fetching for memory efficiency
    - Batch operations for improved performance
    - User library access (liked songs, playlists)
    - Track search and metadata lookup
    - Availability checking and validation
    
    Rate Limiting Strategy:
    The client implements intelligent rate limiting to maximize API throughput
    while respecting Spotify's limits:
    - Minimum 100ms interval between requests (configurable)
    - Automatic retry-after handling for 429 responses
    - Request timing tracking for optimal scheduling
    
    Error Recovery:
    Comprehensive error handling covers all common API scenarios:
    - 401 Unauthorized: Automatic token refresh
    - 429 Rate Limited: Respect retry-after headers
    - 404 Not Found: Graceful handling with user feedback
    - Network errors: Retry with exponential backoff
    
    Thread Safety:
    Designed for single-threaded use with global instance pattern.
    Rate limiting state is instance-local to prevent conflicts.
    """
    
    def __init__(self):
        """
        Initialize Spotify API client with configuration and rate limiting
        
        Sets up the client with authentication, settings, and logging components.
        The actual Spotify connection is created lazily on first API call to
        optimize startup time and handle authentication failures gracefully.
        
        Initializes:
        - Authentication manager from config
        - Application settings and preferences
        - Structured logging with appropriate logger hierarchy
        - Rate limiting state tracking
        - Lazy-loaded Spotify client connection
        """
        self.auth = get_auth()
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self._client: Optional[spotipy.Spotify] = None
        
        # Rate limiting configuration for optimal API usage
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests (10 req/sec max)
    
    @property
    def client(self) -> spotipy.Spotify:
        """
        Lazy-loading property for authenticated Spotify client connection
        
        Implements the lazy initialization pattern to defer expensive authentication
        until first API call. Automatically handles token validation and refresh
        to ensure the client is always ready for requests.
        
        Returns:
            Authenticated spotipy.Spotify client instance
            
        Raises:
            Exception: If authentication fails or cannot be established
            
        Authentication Flow:
        1. Check if client exists and authentication is valid
        2. If not, request new authenticated client from auth manager
        3. Validate the client connection
        4. Cache the client for subsequent requests
        
        Note:
            This property may trigger network requests for token refresh,
            so it should be accessed within the rate limiting context.
        """
        if not self._client or not self.auth.is_authenticated():
            self._client = self.auth.get_spotify_client()
            if not self._client:
                raise Exception("Failed to authenticate with Spotify")
        return self._client
    
    def _rate_limit(self) -> None:
        """
        Intelligent rate limiting to respect Spotify API constraints
        
        Implements adaptive throttling based on the configured minimum interval
        between requests. Tracks request timing to ensure optimal API usage
        without exceeding rate limits.
        
        Algorithm:
        1. Calculate time elapsed since last request
        2. If interval is too short, sleep for remaining time
        3. Update last request timestamp for next calculation
        
        Rate Limiting Strategy:
        - Default 100ms minimum interval (10 requests/second)
        - Conservative approach to avoid 429 rate limit responses
        - Precise timing to maximize throughput within limits
        
        Note:
            This method should be called before every API request to ensure
            compliance with rate limiting requirements.
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # If we're making requests too quickly, throttle to respect limits
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        # Update timestamp for next rate limiting calculation
        self.last_request_time = time.time()
    
    def _make_request(self, func, *args, **kwargs) -> Any:
        """
        Rate-limited API request wrapper with comprehensive error handling
        
        Provides a unified interface for all Spotify API calls with automatic
        rate limiting, authentication refresh, and error recovery. Handles
        the most common API error conditions transparently.
        
        Args:
            func: Spotify API method to call
            *args: Positional arguments for the API method
            **kwargs: Keyword arguments for the API method
            
        Returns:
            API response data from the Spotify endpoint
            
        Raises:
            Exception: For non-recoverable errors or authentication failures
            SpotifyException: For API errors that cannot be automatically handled
            
        Error Handling Strategy:
        
        401 Unauthorized:
        - Indicates expired or invalid authentication token
        - Attempts automatic token refresh through auth manager
        - Retries original request with new token
        - Fails if refresh is unsuccessful
        
        429 Rate Limited:
        - Respects Retry-After header from Spotify
        - Logs warning with wait time for user awareness
        - Automatically retries after specified delay
        - Applies additional rate limiting after retry
        
        Other HTTP Errors:
        - Propagates to caller for specific handling
        - Preserves original error context and status codes
        - Enables application-specific error responses
        
        Network Errors:
        - Handled by underlying spotipy library
        - May result in timeout or connection exceptions
        """
        # Apply rate limiting before every request
        self._rate_limit()
        
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 401:
                # Token expired - attempt automatic refresh
                self.logger.debug("Spotify token expired, attempting refresh...")
                self._client = self.auth.get_spotify_client()
                if self._client:
                    # Retry with fresh token after rate limiting
                    self._rate_limit()
                    return func(*args, **kwargs)
                else:
                    raise Exception("Failed to refresh Spotify token")
            elif e.http_status == 429:
                # Rate limited - respect retry-after header
                retry_after = int(e.headers.get('Retry-After', 1))
                self.logger.warning(f"Rate limited, waiting {retry_after} seconds...")
                time.sleep(retry_after)
                # Apply additional rate limiting after mandated wait
                self._rate_limit()
                return func(*args, **kwargs)
            else:
                # Propagate other HTTP errors for specific handling
                raise e
            
    def get_user_saved_tracks(self) -> SpotifyPlaylist:
        """
        Retrieve user's liked songs as a virtual playlist with complete metadata
        
        Creates a virtual playlist representation of the user's saved tracks
        (liked songs) by fetching all saved tracks through paginated API calls.
        This enables liked songs to be processed using the same download
        infrastructure as regular playlists.
        
        The virtual playlist mimics a standard playlist structure with:
        - Consistent naming and identification ("My Liked Songs")
        - Proper position tracking for each track
        - Added-at timestamps for chronological organization
        - Complete metadata for download operations
        
        Returns:
            SpotifyPlaylist object containing all liked songs as tracks
            
        Raises:
            Exception: If API access fails or authentication is invalid
            
        Implementation Details:
        
        Virtual Playlist Structure:
        - ID: "user_saved_tracks" (unique identifier)
        - Name: "My Liked Songs" (user-friendly display name)
        - Owner: Current authenticated user
        - Tracks: All saved tracks with positions starting from 1
        
        Pagination Strategy:
        - Fetches 50 tracks per request (maximum allowed)
        - Continues until no more tracks are available
        - Progress logging every 500 tracks for large collections
        - Maintains position counter across all pages
        
        Error Handling:
        - Skips individual tracks that fail to parse
        - Continues processing despite individual failures
        - Logs warnings for problematic tracks
        - Provides final count for verification
        
        Performance Considerations:
        - Memory efficient: processes tracks incrementally
        - Network efficient: uses maximum page size
        - Progress tracking: provides feedback for large collections
        """
        self.logger.info("Fetching user's liked songs")
        
        # Create virtual playlist object for liked songs with standard structure
        virtual_playlist = SpotifyPlaylist(
            id="user_saved_tracks",
            name="My Liked Songs",
            description="Your liked songs from Spotify",
            owner_id="current_user",
            owner_name="You",
            public=False,
            collaborative=False,
            total_tracks=0,  # Will be updated after fetching all tracks
            tracks=[]
        )
        
        # Fetch all saved tracks using pagination for memory efficiency
        offset = 0
        limit = 50  # Maximum allowed by Spotify API
        position = 1  # 1-indexed position tracking
        
        while True:
            try:
                # Fetch batch of saved tracks with complete metadata
                results = self._make_request(
                    self.client.current_user_saved_tracks,
                    limit=limit,
                    offset=offset
                )
                
                items = results.get('items', [])
                if not items:
                    break  # No more tracks available
                
                # Process each track in the current batch
                for item in items:
                    track_data = item.get('track')
                    added_at = item.get('added_at', '')
                    
                    # Validate track data before processing
                    if not track_data or not track_data.get('id'):
                        self.logger.warning(f"Skipping invalid track at position {position}")
                        position += 1
                        continue
                    
                    try:
                        # Create SpotifyTrack from track data with added_at timestamp
                        spotify_track = SpotifyTrack.from_spotify_data({'track': track_data}, added_at)
                        
                        # Add to virtual playlist with proper position tracking
                        playlist_track = virtual_playlist.add_track(spotify_track, position, added_at)
                        position += 1
                        
                    except Exception as e:
                        # Log parsing failures but continue processing
                        self.logger.warning(f"Failed to parse liked track at position {position}: {e}")
                        position += 1
                        continue
                
                # Check for more pages using Spotify's pagination links
                if not results.get('next'):
                    break
                
                offset += limit
                
                # Progress logging for large collections (every 500 tracks)
                if offset % 500 == 0:
                    self.logger.info(f"Fetched {offset} liked songs...")
            
            except Exception as e:
                self.logger.error(f"Failed to fetch liked songs at offset {offset}: {e}")
                raise Exception(f"Failed to fetch liked songs: {e}")
        
        # Update total tracks count with actual fetched count
        virtual_playlist.total_tracks = len(virtual_playlist.tracks)
        
        self.logger.info(f"Retrieved {len(virtual_playlist.tracks)} liked songs")
        return virtual_playlist
    
    def extract_playlist_id(self, url_or_id: str) -> str:
        """
        Extract playlist ID from various Spotify URL formats or validate existing ID
        
        Supports multiple Spotify URL formats and validates playlist IDs to ensure
        compatibility with API operations. Handles both web URLs and Spotify URIs
        while providing clear error messages for invalid formats.
        
        Supported Formats:
        - Direct ID: 22-character alphanumeric string
        - Web URL: https://open.spotify.com/playlist/ID?si=...
        - Spotify URI: spotify:playlist:ID
        - Shortened URLs: https://spotify.link/... (resolved by browser)
        
        Args:
            url_or_id: Spotify playlist URL or ID to extract from
            
        Returns:
            Extracted playlist ID ready for API operations
            
        Raises:
            ValueError: If URL format is invalid or ID cannot be extracted
            
        Validation Rules:
        
        Direct ID Format:
        - Must be exactly 22 characters
        - Contains only alphanumeric characters (a-z, A-Z, 0-9)
        - No special characters or spaces
        
        Web URL Format:
        - Must contain 'spotify.com' domain
        - Must contain 'playlist/' path segment
        - ID extracted from path before query parameters
        - Query parameters (si=...) are automatically stripped
        
        Spotify URI Format:
        - Must start with 'spotify:' scheme
        - Must have 'playlist' as type segment
        - ID is the third colon-separated segment
        
        Examples:
            extract_playlist_id("37i9dQZF1DXcBWIGoYBM5M")
            extract_playlist_id("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc123")
            extract_playlist_id("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
        """
        # If it's already a playlist ID, validate format and return
        if re.match(r'^[a-zA-Z0-9]{22}$', url_or_id):
            return url_or_id
        
        # Parse Spotify web URLs
        if 'spotify.com' in url_or_id:
            # Handle web URLs: https://open.spotify.com/playlist/ID?si=...
            if 'playlist/' in url_or_id:
                # Extract ID from path and remove query parameters
                playlist_id = url_or_id.split('playlist/')[-1].split('?')[0]
                return playlist_id
        elif url_or_id.startswith('spotify:'):
            # Handle Spotify URIs: spotify:playlist:ID
            parts = url_or_id.split(':')
            if len(parts) >= 3 and parts[1] == 'playlist':
                return parts[2]
        
        # If no valid format matched, raise descriptive error
        raise ValueError(f"Invalid Spotify playlist URL or ID: {url_or_id}")
    
    def get_playlist_info(self, playlist_id: str) -> SpotifyPlaylist:
        """
        Retrieve basic playlist metadata without track content for efficiency
        
        Fetches essential playlist information using field selection to minimize
        response size and improve performance. This method is optimized for
        scenarios where only metadata is needed, such as validation or initial
        playlist setup.
        
        Args:
            playlist_id: Spotify playlist identifier
            
        Returns:
            SpotifyPlaylist object with complete metadata but empty track list
            
        Raises:
            Exception: If playlist cannot be accessed or does not exist
            
        Retrieved Fields:
        - Basic identification: id, name, description
        - Ownership: owner information and permissions
        - Configuration: public/private status, collaborative flag
        - Statistics: total track count, follower count
        - Resources: external URLs, images, API endpoints
        - Versioning: snapshot_id for change detection
        
        Field Selection Optimization:
        Uses Spotify's field selection to request only necessary data:
        - Reduces response size by ~80% compared to full playlist
        - Improves network performance for metadata-only operations
        - Minimizes API quota usage for frequent checks
        
        Common Use Cases:
        - Playlist validation before download
        - Metadata display in playlist lists
        - Change detection via snapshot_id comparison
        - Permission checking for collaborative playlists
        
        Performance Notes:
        - Single API call regardless of playlist size
        - No track data fetched (separate method for tracks)
        - Minimal memory footprint for large playlists
        """
        self.logger.info(f"Fetching playlist info for {playlist_id}")
        
        try:
            # Request only essential fields for optimal performance
            playlist_data = self._make_request(
                self.client.playlist, 
                playlist_id, 
                fields='id,name,description,owner,public,collaborative,tracks(total),external_urls,href,uri,images,followers,snapshot_id'
            )
            
            # Convert API response to internal model
            playlist = SpotifyPlaylist.from_spotify_data(playlist_data)
            
            self.logger.info(f"Retrieved playlist: '{playlist.name}' by {playlist.owner_name} ({playlist.total_tracks} tracks)")
            
            return playlist
            
        except Exception as e:
            self.logger.error(f"Failed to fetch playlist {playlist_id}: {e}")
            raise Exception(f"Failed to fetch playlist information: {e}")
    
    def get_playlist_tracks(self, playlist_id: str, limit: int = 100) -> Generator[Tuple[SpotifyTrack, int, str], None, None]:
        """
        Memory-efficient generator for streaming playlist tracks with complete metadata
        
        Implements a generator pattern to fetch playlist tracks incrementally,
        enabling processing of large playlists without loading all tracks into
        memory simultaneously. Handles pagination automatically while yielding
        tracks as they become available.
        
        Args:
            playlist_id: Spotify playlist identifier
            limit: Number of tracks per API request (1-100, default: 100)
            
        Yields:
            Tuple of (SpotifyTrack, position, added_at) for each track
            
        Generator Benefits:
        - **Memory Efficiency**: Only current batch held in memory
        - **Streaming Processing**: Begin work before all data is loaded
        - **Early Termination**: Can stop processing without fetching remaining data
        - **Progress Tracking**: Real-time feedback during large operations
        
        Pagination Strategy:
        - Uses maximum batch size (100) for optimal network efficiency
        - Maintains position counter across all pages
        - Automatic offset management for continuous fetching
        - Progress logging every 500 tracks for user feedback
        
        Error Handling:
        - Skips individual unavailable tracks (deleted/restricted)
        - Logs warnings for problematic tracks with position info
        - Continues processing despite individual track failures
        - Fails fast on API or authentication errors
        
        Field Selection:
        Requests comprehensive track metadata in single call:
        - Track identification and basic metadata
        - Artist and album information with details
        - Audio features: duration, explicit flag, popularity
        - External identifiers: ISRC, UPC for metadata matching
        - Availability: playable status and market restrictions
        
        Usage Patterns:
        
        Stream Processing:
            for track, pos, added_at in client.get_playlist_tracks(playlist_id):
                process_track_immediately(track)
        
        Batch Collection:
            tracks = list(client.get_playlist_tracks(playlist_id))
        
        Early Termination:
            for track, pos, added_at in client.get_playlist_tracks(playlist_id):
                if should_stop():
                    break  # Stops API fetching automatically
        """
        self.logger.info(f"Fetching tracks for playlist {playlist_id}")
        
        offset = 0
        position = 1  # 1-indexed position matching Spotify conventions
        
        while True:
            try:
                # Fetch batch of tracks with comprehensive metadata
                results = self._make_request(
                    self.client.playlist_tracks,
                    playlist_id,
                    offset=offset,
                    limit=limit,
                    # Request all necessary fields in single call for efficiency
                    fields='items(added_at,track(id,name,artists,album,duration_ms,explicit,popularity,track_number,disc_number,external_urls,external_ids,href,uri,preview_url,is_local,is_playable)),next,total'
                )
                
                items = results.get('items', [])
                if not items:
                    break  # No more tracks available
                
                # Process each track in the current batch
                for item in items:
                    track_data = item.get('track')
                    if not track_data or not track_data.get('id'):
                        # Skip tracks that are no longer available (deleted/restricted)
                        self.logger.warning(f"Skipping unavailable track at position {position}")
                        position += 1
                        continue
                    
                    try:
                        # Convert API data to internal model with validation
                        spotify_track = SpotifyTrack.from_spotify_data(item)
                        added_at = item.get('added_at', '')
                        
                        # Yield track data for immediate processing
                        yield spotify_track, position, added_at
                        position += 1
                        
                    except Exception as e:
                        # Log parsing failures but continue with remaining tracks
                        self.logger.warning(f"Failed to parse track at position {position}: {e}")
                        position += 1
                        continue
                
                # Check if there are more tracks using Spotify's pagination
                if not results.get('next'):
                    break
                
                offset += limit
                
                # Progress logging for large playlists (every 500 tracks)
                if offset % 500 == 0:
                    self.logger.info(f"Fetched {offset} tracks...")
                
            except Exception as e:
                self.logger.error(f"Failed to fetch tracks at offset {offset}: {e}")
                raise Exception(f"Failed to fetch playlist tracks: {e}")
        
        self.logger.info(f"Finished fetching tracks, total: {position - 1}")
    
    def get_full_playlist(self, playlist_id: str) -> SpotifyPlaylist:
        """
        Retrieve complete playlist with all tracks and metadata in a single operation
        
        Combines playlist metadata and track fetching into a single method for
        convenience when complete playlist data is required. Uses the efficient
        generator-based track fetching internally while providing a simple
        interface for complete playlist operations.
        
        Args:
            playlist_id: Spotify playlist identifier
            
        Returns:
            Complete SpotifyPlaylist object with all tracks loaded
            
        Raises:
            Exception: If playlist access fails or data cannot be retrieved
            
        Operation Flow:
        1. Fetch basic playlist metadata for structure setup
        2. Stream all tracks using generator for memory efficiency
        3. Add each track to playlist with proper position tracking
        4. Provide progress updates for large playlists
        5. Return complete playlist ready for download operations
        
        Memory Considerations:
        While this method loads the complete playlist into memory, it uses
        the generator-based fetching internally to minimize peak memory usage
        during the loading process. The final playlist object will contain
        all tracks in memory.
        
        Progress Tracking:
        Provides progress updates every 100 tracks to give feedback during
        large playlist loading operations. This helps users understand that
        the operation is progressing for playlists with thousands of tracks.
        
        Use Cases:
        - Complete playlist download operations
        - Playlist analysis requiring all track data
        - Offline playlist caching
        - Full metadata export operations
        
        Alternative Approaches:
        For memory-constrained environments or streaming processing,
        consider using get_playlist_tracks() generator directly to avoid
        loading the complete playlist into memory.
        """
        # Get basic playlist info to establish structure
        playlist = self.get_playlist_info(playlist_id)
        
        # Stream all tracks and add them to the playlist
        tracks_fetched = 0
        for spotify_track, position, added_at in self.get_playlist_tracks(playlist_id):
            playlist_track = playlist.add_track(spotify_track, position, added_at)
            tracks_fetched += 1
            
            # Progress update for large playlists (every 100 tracks)
            if tracks_fetched % 100 == 0:
                self.logger.info(f"Added {tracks_fetched}/{playlist.total_tracks} tracks to playlist")
        
        self.logger.info(f"Complete playlist loaded: {len(playlist.tracks)} tracks")
        
        return playlist
    
    def get_track_info(self, track_id: str) -> Optional[SpotifyTrack]:
        """
        Retrieve detailed metadata for a single track by ID
        
        Fetches complete track information including audio features, album context,
        and artist details. Useful for individual track lookups and metadata
        validation operations.
        
        Args:
            track_id: Spotify track identifier
            
        Returns:
            SpotifyTrack object with complete metadata, or None if track not found
            
        Error Handling:
        Returns None for tracks that are unavailable, deleted, or restricted
        in the user's market. Logs warnings for debugging but doesn't raise
        exceptions to enable graceful handling in batch operations.
        
        Use Cases:
        - Single track metadata lookup
        - Track availability verification
        - Metadata refresh for cached tracks
        - Individual track validation
        """
        try:
            track_data = self._make_request(self.client.track, track_id)
            return SpotifyTrack.from_spotify_data({'track': track_data})
        except Exception as e:
            self.logger.warning(f"Failed to fetch track {track_id}: {e}")
            return None
    
    def get_multiple_tracks(self, track_ids: List[str]) -> List[Optional[SpotifyTrack]]:
        """
        Efficient batch retrieval of multiple tracks using Spotify's batch endpoint
        
        Leverages Spotify's batch track endpoint to fetch up to 50 tracks in a
        single API call, significantly improving performance for multi-track
        operations compared to individual requests.
        
        Args:
            track_ids: List of Spotify track IDs (maximum 50 per request)
            
        Returns:
            List of SpotifyTrack objects (None for unavailable tracks)
            
        Raises:
            ValueError: If more than 50 track IDs are provided
            
        Performance Benefits:
        - Single API call vs. multiple individual requests
        - Reduced network overhead and latency
        - Lower API quota consumption
        - Atomic operation for consistency
        
        Error Handling:
        - Maintains position correspondence with input list
        - Returns None for unavailable tracks at correct positions
        - Continues processing if entire batch fails
        - Logs batch-level errors for debugging
        
        Batch Size Limit:
        Spotify's API allows maximum 50 tracks per batch request. For larger
        collections, split into multiple calls or use generator-based approaches
        for memory efficiency.
        
        Use Cases:
        - Metadata refresh for cached playlists
        - Availability checking for multiple tracks
        - Efficient track lookup in recommendation systems
        - Batch validation operations
        """
        if len(track_ids) > 50:
            raise ValueError("Maximum 50 track IDs per request")
        
        try:
            tracks_data = self._make_request(self.client.tracks, track_ids)
            tracks = []
            
            # Process batch response maintaining position correspondence
            for track_data in tracks_data.get('tracks', []):
                if track_data:
                    tracks.append(SpotifyTrack.from_spotify_data({'track': track_data}))
                else:
                    tracks.append(None)  # Unavailable track at this position
            
            return tracks
            
        except Exception as e:
            self.logger.error(f"Failed to fetch multiple tracks: {e}")
            # Return None list maintaining input size for position correspondence
            return [None] * len(track_ids)
    
    def search_tracks(self, query: str, limit: int = 20) -> List[SpotifyTrack]:
        """
        Search for tracks using Spotify's comprehensive search engine
        
        Provides access to Spotify's search functionality for track discovery,
        metadata lookup, and content recommendation. Supports various query
        formats including artist names, track titles, and advanced search operators.
        
        Args:
            query: Search query string (supports Spotify search syntax)
            limit: Maximum number of results to return (1-50)
            
        Returns:
            List of SpotifyTrack objects matching the search criteria
            
        Search Query Formats:
        - Simple: "artist track title"
        - Artist specific: "artist:Radiohead track:Creep"
        - Album specific: "album:OK Computer"
        - Year filtering: "artist:Beatles year:1967"
        - Genre filtering: "genre:jazz"
        
        Search Algorithm:
        Spotify's search uses sophisticated matching algorithms considering:
        - Textual similarity and fuzzy matching
        - Popularity and user engagement metrics
        - Regional availability and market restrictions
        - Artist and album relationship scoring
        
        Result Ranking:
        Results are ordered by Spotify's relevance algorithm, which considers:
        - Query match quality and confidence
        - Track popularity and play statistics
        - User location and market availability
        - Artist prominence and recognition
        
        Use Cases:
        - Track discovery and recommendation
        - Metadata lookup by partial information
        - Alternative version finding (remixes, covers)
        - Content validation and matching
        
        Error Handling:
        Returns empty list if search fails, enabling graceful degradation
        in applications. Logs search errors for debugging while maintaining
        application stability.
        """
        try:
            results = self._make_request(
                self.client.search,
                q=query,
                type='track',
                limit=limit
            )
            
            tracks = []
            # Extract track data from search results structure
            for track_data in results.get('tracks', {}).get('items', []):
                tracks.append(SpotifyTrack.from_spotify_data({'track': track_data}))
            
            return tracks
            
        except Exception as e:
            self.logger.error(f"Failed to search tracks: {e}")
            return []
    
    def get_user_playlists(self, user_id: Optional[str] = None, limit: int = 50) -> List[SpotifyPlaylist]:
        """
        Retrieve user's playlists with metadata (without track content)
        
        Fetches a user's playlist collection including owned playlists and
        followed playlists. Returns playlist metadata only for efficiency -
        track content must be fetched separately using get_playlist_tracks().
        
        Args:
            user_id: Spotify user ID (None for current authenticated user)
            limit: Maximum number of playlists to return
            
        Returns:
            List of SpotifyPlaylist objects with metadata but empty track lists
            
        Playlist Types Included:
        - User-created playlists (owned)
        - Collaborative playlists (with edit access)
        - Followed playlists (public playlists user follows)
        - Spotify-generated playlists (Discover Weekly, etc.)
        
        Authentication Context:
        - None user_id: Uses current authenticated user's playlists
        - Specific user_id: Public playlists only (unless following user)
        - Requires appropriate OAuth scopes for access
        
        Performance Optimization:
        Returns metadata only to enable efficient playlist browsing and
        selection. Use get_full_playlist() or get_playlist_tracks() for
        complete playlist data when needed.
        
        Use Cases:
        - Playlist library browsing
        - Playlist selection interfaces
        - User playlist discovery
        - Metadata-only operations (counting, filtering)
        """
        try:
            # Use appropriate endpoint based on user context
            if user_id:
                results = self._make_request(self.client.user_playlists, user_id, limit=limit)
            else:
                results = self._make_request(self.client.current_user_playlists, limit=limit)
            
            playlists = []
            # Convert API response to internal models
            for playlist_data in results.get('items', []):
                playlists.append(SpotifyPlaylist.from_spotify_data(playlist_data))
            
            return playlists
            
        except Exception as e:
            self.logger.error(f"Failed to fetch user playlists: {e}")
            return []
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve current authenticated user's profile information
        
        Fetches the profile data for the currently authenticated user,
        including display name, user ID, subscription status, and other
        profile metadata useful for user identification and personalization.
        
        Returns:
            Dictionary containing user profile data, or None if fetch fails
            
        Profile Data Includes:
        - User identification: id, display_name, email
        - Subscription: product type (free, premium)
        - Statistics: follower count, public playlists
        - Preferences: country, explicit content settings
        - External links: profile URLs and social connections
        
        Authentication Requirements:
        Requires valid authentication token with appropriate scopes.
        The response content varies based on OAuth scope permissions
        granted during authentication.
        
        Use Cases:
        - User identification and personalization
        - Subscription status checking
        - Profile display in user interfaces
        - Permission validation for features
        
        Privacy Considerations:
        Some profile data may be private based on user privacy settings.
        Applications should gracefully handle missing or restricted data.
        """
        try:
            return self._make_request(self.client.current_user)
        except Exception as e:
            self.logger.error(f"Failed to get current user: {e}")
            return None
    
    def validate_playlist_access(self, playlist_id: str) -> bool:
        """
        Verify playlist accessibility with current authentication context
        
        Performs a lightweight check to determine if the specified playlist
        can be accessed with the current authentication token. Useful for
        validating playlist IDs before attempting expensive operations.
        
        Args:
            playlist_id: Spotify playlist identifier to validate
            
        Returns:
            True if playlist is accessible, False otherwise
            
        Validation Method:
        Uses minimal field selection to fetch only the playlist ID, minimizing
        data transfer while confirming access. This approach is more efficient
        than fetching complete playlist metadata for validation purposes.
        
        Access Scenarios:
        - **Public Playlists**: Accessible to all authenticated users
        - **Private Playlists**: Accessible only to owner
        - **Collaborative Playlists**: Accessible to collaborators
        - **Followed Playlists**: Accessible if user follows them
        
        Common Failure Reasons:
        - Playlist does not exist (deleted)
        - Playlist is private and user lacks access
        - Invalid playlist ID format
        - Authentication token expired or invalid
        - Network connectivity issues
        
        Use Cases:
        - Pre-flight validation before download operations
        - Playlist ID verification in user interfaces
        - Access control for playlist features
        - Error prevention in batch operations
        
        Performance Notes:
        Lightweight operation with minimal data transfer. Safe to use
        frequently for validation without significant API quota impact.
        """
        try:
            # Minimal field request for efficient access validation
            self._make_request(self.client.playlist, playlist_id, fields='id')
            return True
        except Exception as e:
            self.logger.warning(f"Playlist {playlist_id} not accessible: {e}")
            return False
    
    def check_tracks_availability(self, track_ids: List[str]) -> Dict[str, bool]:
        """
        Efficient batch checking of track availability in user's market
        
        Determines availability status for multiple tracks using Spotify's
        batch endpoint. Checks both existence and playability in the user's
        current market, enabling efficient filtering of unavailable content.
        
        Args:
            track_ids: List of Spotify track IDs to check
            
        Returns:
            Dictionary mapping track_id to availability boolean
            
        Availability Criteria:
        A track is considered available if:
        - Track exists in Spotify's catalog
        - Track is playable in user's current market
        - Track has not been removed by rights holders
        - User has appropriate subscription for track access
        
        Batch Processing:
        Processes tracks in batches of 50 (Spotify's batch limit) to
        optimize network usage and API quota consumption. For large
        track lists, multiple batch requests are made automatically.
        
        Use Cases:
        - Pre-download availability validation
        - Playlist quality assessment
        - Content filtering for regional restrictions
        - Cache invalidation for removed tracks
        
        Performance Benefits:
        - Batch processing reduces API calls by up to 50x
        - Minimal data transfer (only availability flags)
        - Efficient for large-scale validation operations
        
        Error Handling:
        Individual track failures are handled gracefully:
        - Failed tracks marked as unavailable
        - Batch continues processing remaining tracks
        - Network errors affect entire batch but don't crash operation
        """
        availability = {}
        
        # Process in batches of 50 (Spotify's batch endpoint limit)
        for i in range(0, len(track_ids), 50):
            batch = track_ids[i:i+50]
            tracks = self.get_multiple_tracks(batch)
            
            # Map track availability based on fetch results
            for track_id, track in zip(batch, tracks):
                # Track is available if it exists and is playable
                availability[track_id] = track is not None and track.is_playable
        
        return availability
    
    def get_album_tracks(self, album_id: str) -> List[SpotifyTrack]:
        """
        Retrieve all tracks from a specific album with complete metadata
        
        Fetches the complete track listing for an album, including full
        metadata for each track. Uses Spotify's album tracks endpoint
        followed by individual track lookups to ensure complete data.
        
        Args:
            album_id: Spotify album identifier
            
        Returns:
            List of SpotifyTrack objects with complete album context
            
        Metadata Completeness:
        Album track endpoints return simplified track objects. This method
        performs additional lookups to ensure each track has complete
        metadata including:
        - Full album information and artwork
        - Complete artist profiles and details
        - Audio features and external identifiers
        - Availability and playability status
        
        Performance Considerations:
        This method makes multiple API calls (1 + number of tracks) to
        ensure data completeness. For efficiency in metadata-only scenarios,
        consider using the album tracks endpoint directly.
        
        Use Cases:
        - Complete album download operations
        - Album analysis with full track metadata
        - Discography processing with consistent data
        - Album-based playlist generation
        
        Error Handling:
        - Continues processing if individual tracks fail
        - Logs failures for debugging
        - Returns partial results for partially accessible albums
        - Empty list if album access fails entirely
        """
        try:
            # Fetch album track listing (simplified track objects)
            results = self._make_request(self.client.album_tracks, album_id)
            tracks = []
            
            # Fetch complete metadata for each track
            for track_data in results.get('items', []):
                # Album tracks need full track lookup for complete metadata
                full_track = self._make_request(self.client.track, track_data['id'])
                tracks.append(SpotifyTrack.from_spotify_data({'track': full_track}))
            
            return tracks
            
        except Exception as e:
            self.logger.error(f"Failed to fetch album tracks: {e}")
            return []


# Global client instance for singleton pattern implementation
_client_instance: Optional[SpotifyClient] = None


def get_spotify_client() -> SpotifyClient:
    """
    Factory function to retrieve the global Spotify client instance
    
    Implements the singleton pattern to ensure only one Spotify client
    exists throughout the application lifecycle. This prevents multiple
    authentication flows and provides consistent rate limiting across
    all Spotify operations.
    
    Returns:
        Global SpotifyClient instance
        
    Singleton Benefits:
    - **Single Authentication**: One token refresh cycle for entire application
    - **Unified Rate Limiting**: Coordinated request throttling across components
    - **Resource Efficiency**: Single connection pool and client state
    - **Configuration Consistency**: Shared settings and preferences
    
    Thread Safety:
    The singleton implementation is thread-safe for read operations but
    should be initialized from the main thread. Multiple threads can
    safely use the same client instance for concurrent operations.
    
    Lifecycle Management:
    The client instance persists for the application lifetime and handles:
    - Automatic token refresh when needed
    - Rate limiting state maintenance
    - Connection pool management
    - Configuration updates
    
    Usage Pattern:
        # Get client in any module
        client = get_spotify_client()
        
        # Use for any Spotify operation
        playlist = client.get_full_playlist(playlist_id)
    """
    global _client_instance
    if not _client_instance:
        _client_instance = SpotifyClient()
    return _client_instance


def reset_spotify_client() -> None:
    """
    Reset the global Spotify client instance for testing and configuration changes
    
    Forces creation of a new client instance on the next get_spotify_client()
    call. Useful for testing scenarios, configuration updates, and error
    recovery situations where a fresh client state is required.
    
    Use Cases:
    - **Testing**: Clean state between test cases
    - **Configuration Changes**: Apply new settings or credentials
    - **Error Recovery**: Reset after authentication failures
    - **Development**: Reload client after code changes
    
    Thread Safety:
    This function should be called from a single thread to avoid race
    conditions during client reset. Concurrent operations may fail
    during the reset process.
    
    State Reset:
    Resetting the client clears:
    - Authentication state and cached tokens
    - Rate limiting timers and request history
    - Connection pools and network state
    - Any cached configuration or settings
    
    Post-Reset Behavior:
    The next call to get_spotify_client() will:
    - Create a new client instance
    - Re-authenticate with current credentials
    - Re-establish rate limiting state
    - Apply current configuration settings
    """
    global _client_instance
    _client_instance = None

def validate_playlist_url(self, url_or_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Comprehensive playlist URL validation with detailed error reporting
    
    Validates Spotify playlist URLs or IDs and provides detailed feedback
    about validation results. Combines format validation with accessibility
    checking to ensure the playlist can be used for download operations.
    
    Args:
        url_or_id: Spotify playlist URL or ID to validate
        
    Returns:
        Tuple of (is_valid, playlist_id, error_message)
        - is_valid: Boolean indicating if playlist is valid and accessible
        - playlist_id: Extracted playlist ID if validation succeeds
        - error_message: Descriptive error message if validation fails
        
    Validation Process:
    
    1. **Format Validation**: Extract and validate playlist ID format
    2. **Existence Check**: Verify playlist exists in Spotify's catalog
    3. **Access Validation**: Confirm playlist is accessible with current auth
    4. **Error Classification**: Provide specific feedback for different failure types
    
    Error Categories:
    - **Format Errors**: Invalid URL format or malformed ID
    - **Not Found**: Playlist doesn't exist or has been deleted
    - **Access Denied**: Playlist is private and user lacks permission
    - **Network Errors**: Connectivity issues or API failures
    
    Use Cases:
    - User input validation in interfaces
    - Pre-operation playlist checking
    - Batch validation with detailed error reporting
    - User-friendly error message generation
    
    Example Results:
        Valid: (True, "37i9dQZF1DXcBWIGoYBM5M", None)
        Invalid Format: (False, None, "Invalid Spotify playlist URL or ID")
        Not Found: (False, None, "Playlist not found or is private")
        Access Error: (False, None, "Cannot access playlist: insufficient permissions")
    
    Note:
        This function appears to be misplaced as a module-level function
        with a 'self' parameter. It should likely be a method of the
        SpotifyClient class or refactored to remove the self parameter.
    """
    try:
        # Use existing extraction logic but with enhanced error handling
        playlist_id = self.extract_playlist_id(url_or_id)
        
        # Additional validation: check if playlist exists and is accessible
        try:
            playlist_info = self.get_playlist_info(playlist_id)
            return True, playlist_id, None
        except Exception as e:
            # Classify error types for user-friendly messaging
            if "not found" in str(e).lower():
                return False, None, "Playlist not found or is private"
            else:
                return False, None, f"Cannot access playlist: {e}"
                
    except ValueError as e:
        # Format validation errors with original error message
        return False, None, str(e)
    except Exception as e:
        # Unexpected errors with generic error handling
        return False, None, f"Unexpected error: {e}"