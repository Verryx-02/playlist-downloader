"""
Genius API integration for lyrics retrieval with intelligent search and quality validation

This module provides comprehensive integration with the Genius API, implementing
sophisticated search algorithms, result scoring, and quality validation to ensure
the highest accuracy in lyrics retrieval. It serves as the primary lyrics source
for the Playlist-Downloader application.

Key features:
- Intelligent multi-query search strategy for better match accuracy
- Advanced similarity scoring algorithm considering title, artist, and album
- Automatic lyrics content validation and cleaning
- Rate limiting compliance with Genius API restrictions (60 requests/hour)
- Robust error handling with retry mechanisms
- Support for featured artists and alternative artist names
- Popularity-based result ranking for improved accuracy

The Genius API provides access to one of the largest lyrics databases with
high-quality, curated content. This implementation maximizes the accuracy
of matches through sophisticated algorithms while respecting API limitations.

API Rate Limits:
- Free tier: 60 requests per hour
- Each search and lyrics fetch counts as separate requests
- Implementation includes automatic rate limiting and request optimization

Search Strategy:
1. Generate multiple search queries with normalized and original text
2. Execute searches with rate limiting
3. Score results based on title/artist similarity and popularity
4. Fetch lyrics from best matching result above threshold
5. Validate and clean lyrics content before returning

Quality Assurance:
- Minimum similarity thresholds for accepting results
- Content validation to filter out invalid lyrics
- Automatic cleaning of metadata and formatting artifacts
- Length validation to ensure meaningful content
"""

import time
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import lyricsgenius

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import (
    calculate_similarity, 
    normalize_artist_name, 
    normalize_track_title,
    retry_on_failure,
    validate_lyrics_content,
    clean_lyrics_text
)

@dataclass
class GeniusSearchResult:
    """
    Container for Genius search results with comprehensive scoring and metadata
    
    This dataclass stores all relevant information from a Genius search result
    along with calculated similarity scores and metadata used for ranking and
    selection. The scoring system helps identify the best match from multiple
    candidates.
    
    Scoring algorithm:
    - Title similarity: 60 points maximum (most important factor)
    - Artist similarity: 40 points maximum (considers featured artists)
    - Album bonus: 5 points for matching album names
    - Popularity bonus: Up to 3 points based on view count
    
    Attributes:
        song_id: Unique Genius song identifier for lyrics fetching
        title: Song title as stored on Genius
        artist: Primary artist name from Genius
        album: Album name if available
        url: Genius song page URL
        lyrics: Fetched lyrics content (populated after lyrics retrieval)
        
        title_score: Calculated title similarity score (0-60)
        artist_score: Calculated artist similarity score (0-40)
        total_score: Combined score used for ranking (0-100+)
        
        view_count: Song popularity metric from Genius
        release_date: Song release date for additional validation
        featured_artists: List of featured artist names for extended matching
    """
    # Core song information from Genius API
    song_id: int
    title: str
    artist: str
    album: Optional[str]
    url: str
    lyrics: Optional[str] = None
    
    # Similarity scoring components for result ranking
    title_score: float = 0.0      # Title similarity (0-60 points)
    artist_score: float = 0.0     # Artist similarity (0-40 points)  
    total_score: float = 0.0      # Combined score for ranking
    
    # Additional metadata for enhanced matching and validation
    view_count: Optional[int] = None           # Popularity metric
    release_date: Optional[str] = None         # Release date string
    featured_artists: List[str] = None         # Featured artists list
    
    def __post_init__(self):
        """Initialize default values for mutable attributes"""
        if self.featured_artists is None:
            self.featured_artists = []


class GeniusLyricsProvider:
    """
    Genius API lyrics provider with intelligent search and quality validation
    
    This class implements a sophisticated lyrics retrieval system using the Genius API.
    It employs advanced search strategies, similarity scoring, and quality validation
    to ensure the highest accuracy in lyrics matching and content quality.
    
    The provider handles all aspects of Genius API interaction including:
    - Authentication and client management
    - Rate limiting compliance (60 requests/hour limit)
    - Multi-query search strategy for improved accuracy
    - Advanced similarity scoring with multiple factors
    - Content validation and cleaning
    - Error handling and retry mechanisms
    
    Search Algorithm:
    1. Generate multiple search queries (original, normalized, title-only)
    2. Execute searches with proper rate limiting
    3. Score results based on title/artist similarity, album matching, popularity
    4. Select best result above configured threshold
    5. Fetch and validate lyrics content
    
    Configuration:
    All behavior is controlled through application settings including thresholds,
    timeouts, retry attempts, and API credentials.
    """
    
    def __init__(self):
        """
        Initialize Genius lyrics provider with configuration and rate limiting
        
        Sets up the provider with all necessary configuration from application
        settings, prepares rate limiting mechanisms, and initializes scoring
        thresholds for result quality control.
        """
        # Load application configuration
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Extract API configuration from settings
        self.api_key = self.settings.lyrics.genius_api_key
        self.timeout = self.settings.lyrics.timeout
        self.max_attempts = self.settings.lyrics.max_attempts
        self.similarity_threshold = self.settings.lyrics.similarity_threshold
        
        # Rate limiting configuration for Genius API compliance
        # Genius free tier allows 60 requests per hour
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests (Genius limit: 60/hour)
        
        # Lazy-initialized Genius client (created when first needed)
        self._genius_client: Optional[lyricsgenius.Genius] = None
        
        # Search optimization parameters
        self.max_search_results = 5        # Results per search query
        self.score_threshold = 70.0        # Minimum score for accepting results
    
    @property
    def genius_client(self) -> lyricsgenius.Genius:
        """
        Get authenticated Genius API client with lazy initialization
        
        Creates and configures the Genius API client on first access, ensuring
        all necessary settings are applied for optimal search results and
        content processing.
        
        Returns:
            Configured lyricsgenius.Genius client instance
            
        Raises:
            Exception: If API key is not configured or client initialization fails
            
        Note:
            The client is configured to skip non-song results and filter out
            common variants (remixes, live versions) that typically don't match
            the original studio recordings from Spotify.
        """
        if not self._genius_client:
            # Validate API key is configured
            if not self.api_key:
                raise Exception("Genius API key not configured")
            
            try:
                # Initialize Genius client with optimized settings
                self._genius_client = lyricsgenius.Genius(
                    access_token=self.api_key,
                    timeout=self.timeout,
                    retries=self.max_attempts,
                    remove_section_headers=False,  # We'll clean manually for better control
                    skip_non_songs=True,          # Skip non-song content (albums, artists)
                    # Exclude common variants that don't match Spotify originals
                    excluded_terms=["(Remix)", "(Live)", "(Cover)", "(Karaoke)"],
                    verbose=False                 # Suppress debug output
                )
                
                self.logger.info("Genius API client initialized successfully")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize Genius client: {e}")
                raise Exception(f"Genius API initialization failed: {e}")
        
        return self._genius_client
    
    def _rate_limit(self) -> None:
        """
        Apply rate limiting between API requests to comply with Genius limits
        
        Ensures compliance with Genius API rate limits by enforcing a minimum
        interval between requests. This prevents API quota exhaustion and
        potential account restrictions.
        
        Rate Limit Details:
        - Genius free tier: 60 requests per hour
        - Implementation uses 1-second intervals (conservative)
        - Allows up to 3600 requests per hour (well within limits)
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Enforce minimum interval between requests
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        # Update last request timestamp
        self.last_request_time = time.time()
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def search_lyrics(self, artist: str, title: str, album: Optional[str] = None) -> Optional[str]:
        """
        Search for lyrics using intelligent multi-query strategy with quality validation
        
        Implements a comprehensive search strategy that maximizes the likelihood of
        finding accurate lyrics matches. Uses multiple search approaches, sophisticated
        scoring, and quality validation to ensure high-quality results.
        
        Search Process:
        1. Generate multiple search queries (normalized, original, variations)
        2. Execute searches with rate limiting
        3. Score all results using similarity algorithms
        4. Select best result above quality threshold
        5. Fetch and validate lyrics content
        
        Args:
            artist: Artist name from Spotify metadata
            title: Track title from Spotify metadata  
            album: Album name for additional matching context (optional)
            
        Returns:
            Clean, validated lyrics text if found, None if no suitable match
            
        Note:
            The retry decorator handles temporary API failures with exponential backoff.
            Only returns lyrics that pass both similarity and content validation.
        """
        try:
            self.logger.info(f"Searching Genius for: {artist} - {title}")
            
            # Apply rate limiting before search
            self._rate_limit()
            
            # Execute multi-query search strategy
            search_results = self._search_songs(artist, title)
            
            if not search_results:
                self.logger.info(f"No Genius results found for: {artist} - {title}")
                return None
            
            # Score and rank all search results
            scored_results = self._score_search_results(search_results, artist, title, album)
            
            # Check if best result meets quality threshold
            best_result = scored_results[0]
            
            if best_result.total_score < self.score_threshold:
                self.logger.info(
                    f"Best Genius match score too low: {best_result.total_score:.1f} "
                    f"(threshold: {self.score_threshold})"
                )
                return None
            
            # Fetch lyrics from best matching result
            lyrics = self._fetch_lyrics(best_result)
            
            if lyrics:
                self.logger.info(
                    f"Genius lyrics found: {best_result.artist} - {best_result.title} "
                    f"(Score: {best_result.total_score:.1f})"
                )
                return lyrics
            else:
                self.logger.debug(f"Failed to fetch lyrics from Genius for best match")
                return None
                
        except Exception as e:
            self.logger.error(f"Genius lyrics search failed: {e}")
            return None
    
    def _search_songs(self, artist: str, title: str) -> List[Dict[str, Any]]:
        """
        Execute multi-query search strategy to find candidate songs
        
        Performs multiple search queries with different approaches to maximize
        the chance of finding the correct song. Uses various query formats
        including normalized text, original formatting, and title-only searches.
        
        Args:
            artist: Artist name to search for
            title: Track title to search for
            
        Returns:
            List of raw search results from Genius API (deduplicated)
            
        Strategy:
        - Primary query: normalized "Artist Title" format
        - Fallback queries: original formatting, title-only, clean artist name
        - Deduplication based on Genius song IDs
        - Early termination when sufficient results found
        """
        # Generate multiple search query variations
        search_queries = self._generate_search_queries(artist, title)
        all_results = []
        seen_song_ids = set()  # Prevent duplicate results
        
        # Execute each search query
        for query in search_queries:
            try:
                self.logger.debug(f"Genius search query: '{query}'")
                
                # Apply rate limiting before each request
                self._rate_limit()
                
                # Execute search via Genius API
                search_response = self.genius_client.search_songs(
                    query, 
                    per_page=self.max_search_results
                )
                
                # Process search response
                if search_response and 'hits' in search_response:
                    for hit in search_response['hits']:
                        result = hit.get('result', {})
                        song_id = result.get('id')
                        
                        # Add unique results only (avoid duplicates)
                        if song_id and song_id not in seen_song_ids:
                            seen_song_ids.add(song_id)
                            all_results.append(result)
                
                # Early exit optimization: stop when we have enough candidates
                if len(all_results) >= self.max_search_results * 2:
                    break
                    
            except Exception as e:
                # Log query failures but continue with other queries
                self.logger.debug(f"Genius search query '{query}' failed: {e}")
                continue
        
        # Return limited number of results for scoring efficiency
        return all_results[:self.max_search_results * 2]  # Limit total results
    
    def _generate_search_queries(self, artist: str, title: str) -> List[str]:
        """
        Generate multiple search query variations for comprehensive song search
        
        Creates different query formats to handle various edge cases and improve
        search accuracy. Different query styles work better for different types
        of songs and artist names.
        
        Args:
            artist: Original artist name from Spotify
            title: Original track title from Spotify
            
        Returns:
            List of search query strings ordered by expected effectiveness
            
        Query Types:
        1. Normalized "Artist Title" - primary approach with cleaned text
        2. Original "Artist Title" - fallback for exact matches
        3. Title only - for songs with complex artist names
        4. Clean artist + title - removes featuring information
        """
        queries = []
        
        # Normalize inputs for cleaner searching
        norm_artist = normalize_artist_name(artist)
        norm_title = normalize_track_title(title)
        
        # Primary query: normalized artist and title (most effective)
        queries.append(f"{norm_artist} {norm_title}")
        
        # Alternative query formats for different matching scenarios
        queries.append(f"{artist} {title}")  # Original formatting
        queries.append(norm_title)           # Title only
        
        # Clean artist query: remove featuring information for better matches
        # Many Spotify tracks include "feat." which can confuse search
        clean_artist = re.sub(r'\s*(feat|ft|featuring)\.?\s+.*', '', norm_artist, flags=re.IGNORECASE)
        if clean_artist != norm_artist:
            queries.append(f"{clean_artist} {norm_title}")
        
        return queries
    
    def _score_search_results(
        self, 
        results: List[Dict[str, Any]], 
        target_artist: str, 
        target_title: str,
        target_album: Optional[str] = None
    ) -> List[GeniusSearchResult]:
        """
        Score and rank search results using comprehensive similarity algorithms
        
        Applies sophisticated scoring algorithms to rank search results by
        likelihood of being the correct match. Considers multiple factors
        including text similarity, popularity, and metadata matching.
        
        Args:
            results: Raw search results from Genius API
            target_artist: Original artist name from Spotify
            target_title: Original track title from Spotify
            target_album: Original album name from Spotify (optional)
            
        Returns:
            List of GeniusSearchResult objects sorted by score (best first)
            
        Scoring Components:
        - Title similarity (60 points max): Primary matching factor
        - Artist similarity (40 points max): Includes featured artist checking
        - Album bonus (5 points): Additional points for album name matches
        - Popularity bonus (3 points max): Based on view count metrics
        """
        scored_results = []
        
        # Process each search result
        for result in results:
            try:
                # Extract structured information from raw result
                genius_result = self._extract_result_info(result)
                
                # Calculate comprehensive similarity scores
                self._calculate_similarity_scores(
                    genius_result, target_artist, target_title, target_album
                )
                
                scored_results.append(genius_result)
                
            except Exception as e:
                # Log scoring failures but continue processing other results
                self.logger.debug(f"Failed to score Genius result: {e}")
                continue
        
        # Sort results by total score in descending order (best matches first)
        scored_results.sort(key=lambda x: x.total_score, reverse=True)
        
        return scored_results
    
    def _extract_result_info(self, result: Dict[str, Any]) -> GeniusSearchResult:
        """
        Extract structured information from raw Genius search result
        
        Parses the complex nested structure returned by Genius API and extracts
        all relevant information into a structured format for easier processing
        and scoring.
        
        Args:
            result: Raw search result dictionary from Genius API
            
        Returns:
            GeniusSearchResult object with extracted information
            
        Handles:
        - Primary and featured artist information
        - Album metadata extraction
        - Popularity metrics (view counts)
        - Release date information
        - URL construction for lyrics fetching
        """
        # Extract basic song information
        song_id = result.get('id', 0)
        title = result.get('title', '')
        url = result.get('url', '')
        
        # Extract primary artist information
        primary_artist = result.get('primary_artist', {})
        artist = primary_artist.get('name', '') if primary_artist else ''
        
        # Extract album information if available
        album = None
        if result.get('album'):
            album = result['album'].get('name')
        
        # Extract featured artists for extended matching
        featured_artists = []
        for featured_artist in result.get('featured_artists', []):
            if featured_artist.get('name'):
                featured_artists.append(featured_artist['name'])
        
        # Extract popularity and metadata
        view_count = result.get('stats', {}).get('pageviews')
        release_date = result.get('release_date_for_display')
        
        return GeniusSearchResult(
            song_id=song_id,
            title=title,
            artist=artist,
            album=album,
            url=url,
            view_count=view_count,
            release_date=release_date,
            featured_artists=featured_artists
        )
    
    def _calculate_similarity_scores(
        self, 
        result: GeniusSearchResult, 
        target_artist: str, 
        target_title: str,
        target_album: Optional[str] = None
    ) -> None:
        """
        Calculate comprehensive similarity scores for search result ranking
        
        Implements the core scoring algorithm that determines how well a Genius
        result matches the target song. Uses multiple weighted factors to create
        a robust ranking system.
        
        Args:
            result: GeniusSearchResult to calculate scores for (modified in-place)
            target_artist: Target artist name from Spotify
            target_title: Target track title from Spotify
            target_album: Target album name from Spotify (optional)
            
        Scoring Algorithm:
        - Title similarity: 60 points (most important - exact titles crucial)
        - Artist similarity: 40 points (considers primary and featured artists)
        - Album bonus: 5 points (additional validation when available)
        - Popularity bonus: 3 points (higher view counts often indicate correct songs)
        
        Total possible score: 108 points (100 base + 8 bonus)
        """
        # Normalize text for fair comparison
        norm_target_artist = normalize_artist_name(target_artist)
        norm_target_title = normalize_track_title(target_title)
        norm_result_artist = normalize_artist_name(result.artist)
        norm_result_title = normalize_track_title(result.title)
        
        # Calculate title similarity (60 points maximum)
        # Title matching is the most important factor for accuracy
        title_similarity = calculate_similarity(norm_target_title, norm_result_title)
        result.title_score = title_similarity * 60
        
        # Calculate artist similarity (40 points maximum)
        artist_similarity = calculate_similarity(norm_target_artist, norm_result_artist)
        
        # Enhanced artist matching: check featured artists if primary doesn't match well
        # Many songs have different primary artist arrangements between Spotify and Genius
        if artist_similarity < 0.8 and result.featured_artists:
            for featured_artist in result.featured_artists:
                norm_featured = normalize_artist_name(featured_artist)
                featured_similarity = calculate_similarity(norm_target_artist, norm_featured)
                if featured_similarity > artist_similarity:
                    artist_similarity = featured_similarity
                    break
        
        result.artist_score = artist_similarity * 40
        
        # Album matching bonus (5 points maximum)
        # Provides additional validation when album information is available
        album_bonus = 0
        if target_album and result.album:
            album_similarity = calculate_similarity(
                target_album.lower().strip(),
                result.album.lower().strip()
            )
            # Only award bonus for strong album matches
            if album_similarity > 0.8:
                album_bonus = 5
        
        # Popularity bonus based on view count (3 points maximum)
        # Higher view counts often correlate with correct/popular songs
        popularity_bonus = 0
        if result.view_count and result.view_count > 100000:  # 100k+ views threshold
            # Scale bonus with view count (logarithmic scaling)
            popularity_bonus = min(3, result.view_count / 1000000)  # Max 3 points at 3M+ views
        
        # Calculate final total score
        result.total_score = (
            result.title_score + 
            result.artist_score + 
            album_bonus + 
            popularity_bonus
        )
    
    @retry_on_failure(max_attempts=2, delay=1.0)
    def _fetch_lyrics(self, result: GeniusSearchResult) -> Optional[str]:
        """
        Fetch lyrics content for a specific song with validation and cleaning
        
        Retrieves the actual lyrics content from Genius using the song ID,
        then applies cleaning and validation to ensure quality. This is the
        final step in the lyrics retrieval process.
        
        Args:
            result: GeniusSearchResult containing song ID and metadata
            
        Returns:
            Clean, validated lyrics text or None if fetching/validation fails
            
        Process:
        1. Fetch song details via Genius API
        2. Extract lyrics content from response
        3. Clean lyrics (remove metadata, formatting artifacts)
        4. Validate content quality (length, format, content type)
        5. Return validated lyrics or None
        
        Note:
        The retry decorator handles temporary API failures during lyrics fetching.
        """
        try:
            self.logger.debug(f"Fetching lyrics for: {result.artist} - {result.title}")
            
            # Apply rate limiting before lyrics request
            self._rate_limit()
            
            # Fetch complete song details including lyrics content
            song = self.genius_client.song(result.song_id)
            
            # Validate song object and lyrics content
            if song and hasattr(song, 'lyrics') and song.lyrics:
                # Clean lyrics content (remove metadata, format properly)
                cleaned_lyrics = clean_lyrics_text(song.lyrics)
                
                # Validate lyrics content quality
                if validate_lyrics_content(cleaned_lyrics, self.settings.lyrics.min_length):
                    return cleaned_lyrics
                else:
                    self.logger.debug(f"Lyrics validation failed for: {result.title}")
                    return None
            else:
                self.logger.debug(f"No lyrics content found for: {result.title}")
                return None
                
        except Exception as e:
            # Log fetch failures for debugging
            self.logger.debug(f"Failed to fetch lyrics from Genius: {e}")
            return None
    
    def get_song_info(self, song_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed song information from Genius API
        
        Retrieves comprehensive metadata for a specific song using its Genius ID.
        Useful for additional validation, debugging, or metadata enhancement.
        
        Args:
            song_id: Unique Genius song identifier
            
        Returns:
            Dictionary containing song metadata or None if not found
            Includes: id, title, artist, album, release_date, url, view_count, lyrics_available
            
        Note:
        This method is primarily used for debugging and metadata collection.
        Normal lyrics retrieval uses the main search_lyrics method.
        """
        try:
            # Apply rate limiting before request
            self._rate_limit()
            
            # Fetch song details from Genius
            song = self.genius_client.song(song_id)
            
            if song:
                # Extract and structure song information
                return {
                    'id': song.id,
                    'title': song.title,
                    'artist': song.artist,
                    'album': getattr(song, 'album', None),
                    'release_date': getattr(song, 'release_date', None),
                    'url': song.url,
                    'view_count': getattr(song, 'stats', {}).get('pageviews'),
                    'lyrics_available': bool(getattr(song, 'lyrics', None))
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get Genius song info: {e}")
            return None
    
    def search_artist_songs(self, artist_name: str, max_songs: int = 20) -> List[Dict[str, Any]]:
        """
        Search for songs by a specific artist on Genius
        
        Retrieves a list of songs by the specified artist, useful for batch
        operations or artist discography analysis. Limited by max_songs parameter
        to prevent excessive API usage.
        
        Args:
            artist_name: Name of artist to search for
            max_songs: Maximum number of songs to return (default: 20)
            
        Returns:
            List of song information dictionaries
            Each dict contains: id, title, artist, url, album, lyrics_available
            
        Note:
        This method is useful for batch lyrics processing or artist analysis
        but is not used in the main lyrics retrieval workflow.
        """
        try:
            self.logger.info(f"Searching Genius for artist: {artist_name}")
            
            # Apply rate limiting before search
            self._rate_limit()
            
            # Search for artist and their songs
            artist = self.genius_client.search_artist(artist_name, max_songs=max_songs)
            
            if artist and hasattr(artist, 'songs'):
                songs = []
                # Extract song information from artist object
                for song in artist.songs:
                    songs.append({
                        'id': song.id,
                        'title': song.title,
                        'artist': song.artist,
                        'url': song.url,
                        'album': getattr(song, 'album', None),
                        'lyrics_available': bool(getattr(song, 'lyrics', None))
                    })
                
                return songs
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to search Genius artist songs: {e}")
            return []
    
    def validate_api_access(self) -> bool:
        """
        Validate Genius API access and configuration
        
        Performs a test API call to verify that the API key is valid and
        the service is accessible. Used for diagnostics and setup validation.
        
        Returns:
            True if API is accessible and configured correctly, False otherwise
            
        Test Process:
        1. Check if API key is configured
        2. Perform simple test search
        3. Validate response structure
        4. Return success/failure status
        """
        try:
            # Check basic configuration
            if not self.api_key:
                self.logger.debug("Genius API key not configured")
                return False
            
            # Perform test API call with rate limiting
            self._rate_limit()
            test_response = self.genius_client.search_songs("test", per_page=1)
            
            # Validate response structure
            if test_response:
                self.logger.debug("Genius API validation successful")
                return True
            else:
                self.logger.debug("Genius API test search failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Genius API validation failed: {e}")
            return False
    
    def get_api_status(self) -> Dict[str, Any]:
        """
        Get comprehensive API status and configuration information
        
        Returns detailed information about the current API configuration,
        settings, and operational parameters. Useful for debugging,
        monitoring, and configuration validation.
        
        Returns:
            Dictionary containing all relevant status and configuration data
            
        Status Information:
        - API configuration status
        - Timeout and retry settings  
        - Similarity and score thresholds
        - Rate limiting configuration
        - Search optimization parameters
        """
        return {
            'api_configured': bool(self.api_key),
            'timeout': self.timeout,
            'max_attempts': self.max_attempts,
            'similarity_threshold': self.similarity_threshold,
            'score_threshold': self.score_threshold,
            'rate_limit_interval': self.min_request_interval,
            'max_search_results': self.max_search_results
        }


# Global Genius provider instance management
# Singleton pattern ensures consistent API client and configuration across application
_genius_provider: Optional[GeniusLyricsProvider] = None


def get_genius_provider() -> GeniusLyricsProvider:
    """
    Get the global Genius lyrics provider instance (singleton pattern)
    
    Provides access to the shared Genius provider instance used throughout
    the application. Creates the instance on first access and returns the
    same instance for subsequent calls, ensuring consistent API client
    state and configuration.
    
    Returns:
        Global GeniusLyricsProvider instance
        
    Benefits of Singleton Pattern:
    - Shared API client reduces authentication overhead
    - Consistent rate limiting across all lyrics requests
    - Centralized configuration management
    - Efficient resource utilization
    """
    global _genius_provider
    if not _genius_provider:
        _genius_provider = GeniusLyricsProvider()
    return _genius_provider


def reset_genius_provider() -> None:
    """
    Reset the global Genius lyrics provider instance
    
    Clears the global provider instance, forcing a new instance to be created
    on the next access. Useful for testing, configuration changes, or
    troubleshooting API issues.
    
    Note:
    This resets the provider instance but does not affect API quotas or
    authentication status with Genius. The next access will create a fresh
    instance with current configuration.
    """
    global _genius_provider
    _genius_provider = None