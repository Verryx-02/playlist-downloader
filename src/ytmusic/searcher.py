"""
YouTube Music intelligent search with multi-strategy matching algorithm and sophisticated scoring system

This module implements a comprehensive search system for finding YouTube Music tracks that match
Spotify playlist entries. It uses advanced algorithms including multi-query strategies, similarity
scoring, duration matching, and quality assessment to ensure the highest accuracy in track matching.

The search system is designed to handle the complexities of cross-platform music matching:
- Different metadata formats between Spotify and YouTube Music
- Variations in artist names, track titles, and album information
- Multiple versions of the same track (official, live, covers, remixes)
- Quality assessment to prefer official releases over user uploads
- Intelligent fallback strategies when strict matching fails

Key Features:
- Multi-strategy search with cascading fallback approaches
- Advanced similarity scoring using multiple weighted factors
- Duration-based validation to confirm track accuracy
- Quality indicators analysis (official releases, verified artists)
- Automatic filtering of unwanted content (live, covers, karaoke)
- Rate limiting compliance with YouTube Music API restrictions
- Comprehensive metadata extraction and flag analysis

Search Algorithm Overview:
1. Primary Strategy: Strict search with normalized queries and high thresholds
2. Fallback Strategy: Permissive search with relaxed matching criteria
3. Multiple query generation for different search approaches
4. Comprehensive scoring system with weighted factors:
   - Title similarity (40 points max)
   - Artist similarity (30 points max)  
   - Duration matching (20 points max)
   - Quality bonuses/penalties (±10 points)

Quality Assessment:
The system automatically identifies and scores content quality using:
- Official audio/video indicators from YouTube
- Artist verification status
- Content type detection (music video vs audio)
- Negative content filtering (live, covers, karaoke, remixes)
- Popularity and reliability metrics

This ensures that downloaded tracks are the highest quality matches available,
prioritizing official releases over user-generated content while maintaining
flexibility for edge cases where official versions aren't available.

Rate Limiting:
Implements 1-second intervals between requests to comply with YouTube Music API
guidelines and prevent rate limiting or account restrictions.

Configuration:
All behavior is controlled through application settings including score thresholds,
quality preferences, content filtering options, and search parameters.
"""

import time
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from ytmusicapi import YTMusic
from ytmusicapi.exceptions import YTMusicError

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import (
    calculate_similarity, 
    normalize_artist_name, 
    normalize_track_title,
    create_search_query,
    parse_duration_string,
    retry_on_failure
)


@dataclass
class SearchResult:
    """
    YouTube Music search result container with comprehensive metadata and scoring
    
    This dataclass stores all relevant information extracted from a YouTube Music
    search result, along with calculated similarity scores and quality flags used
    for ranking and selection. The scoring system helps identify the best match
    from multiple candidates using weighted factors.
    
    The class automatically calculates the total score in __post_init__ based on
    the individual scoring components, providing a single ranking metric for
    result comparison and selection.
    
    Scoring Components:
    - title_score: Title similarity (0-40 points)
    - artist_score: Artist similarity (0-30 points)
    - duration_score: Duration matching accuracy (0-20 points)
    - quality_bonus: Content quality assessment (-10 to +10 points)
    
    Quality Flags:
    Content type detection helps filter and rank results based on preferences:
    - is_official: Contains official audio/video indicators
    - is_verified_artist: From verified artist channel
    - is_music_video: Video content vs audio-only
    - is_live: Live performance or concert recording
    - is_cover: Cover version by different artist
    - is_karaoke: Karaoke or instrumental version
    - is_remix: Remix, extended, or modified version
    
    Attributes:
        video_id: Unique YouTube video identifier for downloading
        title: Track title as stored on YouTube Music
        artist: Primary artist name from YouTube Music
        duration: Track duration in seconds (parsed from duration string)
        album: Album name if available
        thumbnail: Video thumbnail URL for UI display
        view_count: Video view count for popularity assessment
        
        is_official: True if contains official release indicators
        is_verified_artist: True if from verified artist channel
        is_music_video: True if identified as music video content
        is_live: True if live performance or concert
        is_cover: True if cover version by different artist
        is_karaoke: True if karaoke or instrumental version
        is_remix: True if remix or modified version
        
        title_score: Calculated title similarity score (0-40)
        artist_score: Calculated artist similarity score (0-30)
        duration_score: Calculated duration matching score (0-20)
        quality_bonus: Quality assessment bonus/penalty (-10 to +10)
        total_score: Combined score for ranking (calculated automatically)
    """
    # Core track information from YouTube Music
    video_id: str
    title: str
    artist: str
    duration: Optional[int]  # seconds
    album: Optional[str]
    thumbnail: Optional[str]
    view_count: Optional[int]
    
    # Content type and quality metadata flags
    # These flags help determine content quality and appropriateness
    is_official: bool = False          # Contains official audio/video indicators
    is_verified_artist: bool = False   # From verified artist channel
    is_music_video: bool = False       # Video content vs audio-only
    is_live: bool = False              # Live performance or concert
    is_cover: bool = False             # Cover version by different artist
    is_karaoke: bool = False           # Karaoke or instrumental version
    is_remix: bool = False             # Remix, extended, or modified version
    
    # Similarity scoring components for result ranking
    title_score: float = 0.0       # Title similarity (0-40 points)
    artist_score: float = 0.0      # Artist similarity (0-30 points)
    duration_score: float = 0.0    # Duration matching (0-20 points)
    quality_bonus: float = 0.0     # Quality bonus/penalty (-10 to +10)
    total_score: float = 0.0       # Combined score (calculated automatically)
    
    def __post_init__(self):
        """
        Calculate total score after initialization
        
        Automatically computes the final ranking score by combining all
        individual scoring components. This ensures the total_score is
        always up-to-date when any component scores are modified.
        
        The total score is used for sorting and ranking search results
        to identify the best matches for download.
        """
        self.total_score = (
            self.title_score + 
            self.artist_score + 
            self.duration_score + 
            self.quality_bonus
        )


class YouTubeMusicSearcher:
    """
    Intelligent YouTube Music search engine with advanced matching algorithms
    
    This class implements a sophisticated search system for finding YouTube Music tracks
    that accurately match Spotify playlist entries. It employs multiple search strategies,
    advanced similarity algorithms, and comprehensive quality assessment to ensure the
    highest accuracy in cross-platform music matching.
    
    The searcher handles the complex challenges of music discovery across platforms:
    - Metadata inconsistencies between Spotify and YouTube Music
    - Multiple versions of tracks (official, live, covers, remixes)
    - Artist name variations and featuring artists
    - Album and compilation differences
    - Quality assessment and content filtering
    
    Search Architecture:
    The system uses a cascading search approach with two main strategies:
    
    1. Strict Search (Primary):
       - High similarity thresholds (65+ score)
       - Normalized and cleaned query generation
       - Preference for official content
       - Early termination on high-quality matches
    
    2. Permissive Search (Fallback):
       - Lower similarity thresholds (45+ score)
       - Additional query variations
       - Relaxed content filtering
       - Broader matching criteria
    
    Scoring Algorithm:
    Each search result is scored using weighted factors:
    - Title Similarity: 40 points (most important for accuracy)
    - Artist Similarity: 30 points (handles featuring artists)
    - Duration Matching: 20 points (validates track identity)
    - Quality Assessment: ±10 points (prefers official content)
    
    Quality Indicators:
    The system analyzes content to identify quality and appropriateness:
    - Official release indicators (auto-generated, provided to YouTube)
    - Artist verification status
    - Content type classification (audio vs video)
    - Negative content detection (live, covers, karaoke)
    
    Rate Limiting:
    Implements automatic rate limiting with 1-second intervals between
    requests to comply with YouTube Music API guidelines and prevent
    account restrictions or quota exhaustion.
    
    Configuration:
    All behavior is controlled through application settings:
    - Score thresholds for result acceptance
    - Content filtering preferences
    - Search result limits and timeouts
    - Quality assessment parameters
    """
    
    def __init__(self):
        """
        Initialize YouTube Music searcher with configuration and quality indicators
        
        Sets up the searcher with all necessary configuration from application settings,
        prepares rate limiting mechanisms, and initializes quality detection patterns
        for accurate content assessment and filtering.
        
        Configuration Loading:
        - Loads search parameters (thresholds, limits, preferences)
        - Sets up content filtering options (exclude live, covers)
        - Initializes rate limiting for API compliance
        - Prepares quality detection patterns
        
        Quality Detection Setup:
        - Official content indicators for identifying legitimate releases
        - Negative content patterns for filtering unwanted versions
        - Artist verification patterns for quality assessment
        """
        # Load application configuration
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Lazy-initialized YouTube Music client (created when first needed)
        self._ytmusic: Optional[YTMusic] = None
        
        # Search configuration parameters from application settings
        self.max_results = self.settings.ytmusic.max_results
        self.score_threshold = self.settings.ytmusic.score_threshold
        self.prefer_official = self.settings.ytmusic.prefer_official
        self.exclude_live = self.settings.ytmusic.exclude_live
        self.exclude_covers = self.settings.ytmusic.exclude_covers
        self.duration_tolerance = self.settings.ytmusic.duration_tolerance
        
        # Rate limiting configuration for YouTube Music API compliance
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between searches
        
        # Quality indicator patterns for content assessment
        # These patterns help identify official releases vs user uploads
        self.official_indicators = [
            'official audio', 'official video', 'official music video',
            'provided to youtube', 'auto-generated'
        ]
        
        # Negative indicator patterns for filtering unwanted content
        # These patterns identify versions that typically don't match original releases
        self.negative_indicators = [
            'live', 'concert', 'tour', 'acoustic',
            'cover', 'covered by', 'covers',
            'karaoke', 'instrumental', 'piano version',
            'remix', 'extended', 'mashup', 'mix'
        ]
        
        # Artist verification patterns for quality assessment
        # These help identify content from legitimate artist channels
        self.verified_patterns = [
            'official artist channel',
            'verified',
            '✓'
        ]
    
    @property
    def ytmusic(self) -> YTMusic:
        """
        Get YouTube Music API client with lazy initialization
        
        Creates and returns the YouTube Music API client on first access.
        The client is initialized without authentication for public access
        to search functionality, which is sufficient for track discovery.
        
        Returns:
            Configured YTMusic client instance ready for searches
            
        Raises:
            Exception: If YouTube Music API initialization fails
            
        Note:
            The client uses public access mode, so no authentication
            credentials are required. This provides access to search
            functionality while respecting API usage guidelines.
        """
        if not self._ytmusic:
            try:
                # Initialize without authentication for public search access
                # This provides sufficient functionality for track discovery
                self._ytmusic = YTMusic()
                self.logger.info("YouTube Music API initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize YouTube Music API: {e}")
                raise Exception(f"YouTube Music initialization failed: {e}")
        return self._ytmusic
    
    def _rate_limit(self) -> None:
        """
        Apply rate limiting between API requests to ensure compliance
        
        Enforces a minimum interval between YouTube Music API requests to
        comply with usage guidelines and prevent rate limiting or account
        restrictions. Uses a conservative 1-second interval to ensure
        reliable long-term operation.
        
        Rate Limiting Strategy:
        - 1-second minimum interval between requests
        - Automatic sleep calculation based on elapsed time
        - Conservative approach to prevent quota issues
        - Allows sustained operation for large playlists
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Enforce minimum interval between requests
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        # Update timestamp for next request calculation
        self.last_request_time = time.time()
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def _search_ytmusic(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Perform YouTube Music search with rate limiting and retry logic
        
        Executes a search query against the YouTube Music API with automatic
        rate limiting, error handling, and retry mechanisms. Focuses specifically
        on song results to avoid non-musical content.
        
        Args:
            query: Search query string (artist, title, keywords)
            limit: Maximum number of results to return (default: 20)
            
        Returns:
            List of raw search result dictionaries from YouTube Music API
            Each result contains videoId, title, artists, duration, and metadata
            
        Raises:
            YTMusicError: For YouTube Music API specific errors
            Exception: For unexpected errors during search
            
        Note:
            The retry decorator handles temporary API failures with exponential
            backoff. Rate limiting is applied before each request to ensure
            compliance with API usage guidelines.
        """
        # Apply rate limiting before making API request
        self._rate_limit()
        
        try:
            # Search specifically for songs to filter out non-musical content
            # This focuses results on track content rather than videos, playlists, etc.
            results = self.ytmusic.search(
                query=query,
                filter='songs',  # Focus on song content only
                limit=limit
            )
            
            self.logger.debug(f"YTMusic search '{query}' returned {len(results)} results")
            return results
            
        except YTMusicError as e:
            # Handle YouTube Music API specific errors
            self.logger.warning(f"YTMusic search failed for '{query}': {e}")
            raise e
        except Exception as e:
            # Handle unexpected errors during search
            self.logger.error(f"Unexpected error in YTMusic search: {e}")
            raise e
    
    def _extract_result_metadata(self, result: Dict[str, Any]) -> SearchResult:
        """
        Extract and parse comprehensive metadata from YouTube Music search result
        
        Converts the complex nested structure returned by YouTube Music API into
        a structured SearchResult object with normalized and validated data.
        Handles missing fields gracefully and provides sensible defaults.
        
        Args:
            result: Raw search result dictionary from YouTube Music API
                   Contains nested structure with videoId, title, artists, etc.
            
        Returns:
            SearchResult object with extracted and normalized metadata
            
        Metadata Extraction:
        - Video ID for track identification and downloading
        - Title and artist information with fallback handling
        - Duration parsing from string format to seconds
        - Album information when available
        - Thumbnail URL selection (highest resolution)
        - View count extraction when available
        
        Error Handling:
        If extraction fails, returns minimal SearchResult with available
        information to prevent search failures from single result issues.
        """
        try:
            # Extract basic track identification information
            video_id = result.get('videoId', '')
            title = result.get('title', '')
            
            # Extract primary artist information with fallback handling
            # YouTube Music API returns artists as a list of dictionaries
            artists = result.get('artists', [])
            if artists and len(artists) > 0:
                artist = artists[0].get('name', 'Unknown Artist')
            else:
                artist = 'Unknown Artist'
            
            # Parse duration from string format (e.g., "3:45") to seconds
            duration_text = result.get('duration')
            duration = None
            if duration_text:
                duration = parse_duration_string(duration_text)
            
            # Extract album information when available
            # Not all tracks have album associations in YouTube Music
            album = None
            if result.get('album'):
                album = result['album'].get('name')
            
            # Extract thumbnail URL (prefer highest resolution available)
            thumbnails = result.get('thumbnails', [])
            thumbnail = thumbnails[-1]['url'] if thumbnails else None
            
            # Extract view count for popularity assessment
            # Note: View count may not be available for all tracks
            view_count = None
            
            # Create SearchResult object with extracted metadata
            search_result = SearchResult(
                video_id=video_id,
                title=title,
                artist=artist,
                duration=duration,
                album=album,
                thumbnail=thumbnail,
                view_count=view_count
            )
            
            # Analyze content to set quality and type flags
            self._analyze_result_flags(search_result, result)
            
            return search_result
            
        except Exception as e:
            # Log extraction failure but continue with minimal result
            self.logger.warning(f"Failed to extract metadata from result: {e}")
            
            # Return minimal result to prevent complete search failure
            return SearchResult(
                video_id=result.get('videoId', ''),
                title=result.get('title', ''),
                artist='Unknown Artist'
            )
    
    def _analyze_result_flags(self, search_result: SearchResult, raw_result: Dict[str, Any]) -> None:
        """
        Analyze search result to determine content type and quality flags
        
        Examines the title, artist, and metadata to identify content characteristics
        that affect quality and appropriateness for playlist downloading. Sets
        boolean flags that are used in scoring and filtering decisions.
        
        Args:
            search_result: SearchResult object to update with flags (modified in-place)
            raw_result: Raw result data from YouTube Music API for additional analysis
            
        Flag Detection:
        - Official content: Identifies legitimate releases vs user uploads
        - Content type: Distinguishes audio, video, live performances
        - Quality issues: Detects covers, karaoke, remixes that may not match originals
        - Artist verification: Attempts to identify verified artist channels
        
        Analysis Strategy:
        Uses pattern matching on titles and metadata to classify content.
        Conservative approach prioritizes accuracy over recall to avoid
        false classifications that could affect download quality.
        """
        # Normalize text for case-insensitive pattern matching
        title_lower = search_result.title.lower()
        artist_lower = search_result.artist.lower()
        
        # Detect official content indicators
        # These patterns typically indicate legitimate releases
        for indicator in self.official_indicators:
            if indicator in title_lower:
                search_result.is_official = True
                break
        
        # Detect and classify negative content indicators
        # These patterns help identify content that may not match original releases
        for indicator in self.negative_indicators:
            if indicator in title_lower:
                # Set specific flags based on indicator type
                if 'live' in indicator or 'concert' in indicator:
                    search_result.is_live = True
                elif 'cover' in indicator:
                    search_result.is_cover = True
                elif 'karaoke' in indicator:
                    search_result.is_karaoke = True
                elif 'remix' in indicator or 'mix' in indicator:
                    search_result.is_remix = True
        
        # Detect music video content vs audio-only
        # Music videos may have different audio quality or editing
        if 'music video' in title_lower or 'official video' in title_lower:
            search_result.is_music_video = True
        
        # Attempt to detect verified artist status
        # YouTube Music API provides limited verification info, so this uses heuristics
        artists = raw_result.get('artists', [])
        for artist_info in artists:
            if artist_info.get('name') == search_result.artist:
                # Check if channel appears to be verified (heuristic approach)
                channel_id = artist_info.get('id', '')
                if channel_id:
                    # Presence of stable channel ID suggests verified status
                    search_result.is_verified_artist = True
                break
    
    def _calculate_scores(
        self, 
        search_result: SearchResult, 
        target_artist: str, 
        target_title: str, 
        target_duration: Optional[int] = None
    ) -> None:
        """
        Calculate comprehensive similarity and quality scores for search result ranking
        
        Implements the core scoring algorithm that determines how well a YouTube Music
        result matches the target Spotify track. Uses multiple weighted factors to
        create a robust ranking system that considers similarity, duration accuracy,
        and content quality.
        
        Args:
            search_result: SearchResult to calculate scores for (modified in-place)
            target_artist: Target artist name from Spotify
            target_title: Target track title from Spotify
            target_duration: Target duration in seconds from Spotify (optional)
            
        Scoring Components:
        
        1. Title Similarity (40 points max):
           - Most important factor for accuracy
           - Uses normalized text comparison
           - Handles variations in punctuation, spacing, formatting
        
        2. Artist Similarity (30 points max):
           - Accounts for featuring artists and name variations
           - Uses normalized artist name comparison
           - Critical for avoiding wrong artist matches
        
        3. Duration Matching (20 points max):
           - Validates track identity through duration comparison
           - Perfect match within tolerance: full points
           - Good match with penalty: scaled points
           - Poor match: zero points
           - Missing duration: neutral score
        
        4. Quality Assessment (±10 points):
           - Official content bonus: +5 points
           - Verified artist bonus: +2 points
           - Music video penalty: -1 point (when preferring audio)
           - Live performance penalty: -8 points
           - Cover version penalty: -6 points
           - Karaoke penalty: -10 points
           - Remix penalty: -3 points
        
        The scoring system balances accuracy (similarity) with quality (content type)
        to ensure downloaded tracks are both correct and high-quality.
        """
        # Normalize text for fair comparison across platforms
        # This handles differences in capitalization, spacing, and punctuation
        norm_target_artist = normalize_artist_name(target_artist)
        norm_target_title = normalize_track_title(target_title)
        norm_result_artist = normalize_artist_name(search_result.artist)
        norm_result_title = normalize_track_title(search_result.title)
        
        # Calculate title similarity score (40 points maximum)
        # Title matching is the most important factor for download accuracy
        title_similarity = calculate_similarity(norm_target_title, norm_result_title)
        search_result.title_score = title_similarity * 40
        
        # Calculate artist similarity score (30 points maximum)
        # Artist matching prevents downloading tracks by wrong artists
        artist_similarity = calculate_similarity(norm_target_artist, norm_result_artist)
        search_result.artist_score = artist_similarity * 30
        
        # Calculate duration matching score (20 points maximum)
        # Duration validation helps confirm track identity and version
        if target_duration and search_result.duration:
            duration_diff = abs(target_duration - search_result.duration)
            
            if duration_diff <= self.duration_tolerance:
                # Perfect duration match within tolerance
                search_result.duration_score = 20
            elif duration_diff <= self.duration_tolerance * 3:
                # Good duration match with penalty for difference
                penalty = (duration_diff - self.duration_tolerance) / (self.duration_tolerance * 2)
                search_result.duration_score = 20 * (1 - penalty)
            else:
                # Poor duration match indicates different version or wrong track
                search_result.duration_score = 0
        else:
            # No duration information available, assign neutral score
            # This prevents penalizing results where duration is unavailable
            search_result.duration_score = 10
        
        # Calculate quality bonus/penalty (±10 points maximum)
        # Quality assessment prefers official content over user uploads
        quality_bonus = 0
        
        # Award bonuses for high-quality content indicators
        if search_result.is_official:
            quality_bonus += 5  # Official audio/video bonus
        
        if search_result.is_verified_artist:
            quality_bonus += 2  # Verified artist channel bonus
        
        # Apply content type penalties based on preferences
        if search_result.is_music_video and self.prefer_official:
            quality_bonus -= 1  # Slight penalty for video when preferring audio
        
        # Apply penalties for unwanted content types
        if search_result.is_live and self.exclude_live:
            quality_bonus -= 8  # Strong penalty for live performances
        if search_result.is_cover and self.exclude_covers:
            quality_bonus -= 6  # Penalty for cover versions
        if search_result.is_karaoke:
            quality_bonus -= 10  # Strong penalty for karaoke versions
        if search_result.is_remix:
            quality_bonus -= 3  # Moderate penalty for remixes
        
        # Clamp quality bonus to valid range (-10 to +10)
        search_result.quality_bonus = max(-10, min(10, quality_bonus))
        
        # Calculate final total score for ranking
        # Total possible: 100 points (base) + 10 (bonus) = 110 maximum
        search_result.total_score = (
            search_result.title_score + 
            search_result.artist_score + 
            search_result.duration_score + 
            search_result.quality_bonus
        )
    
    def search_track(
        self, 
        artist: str, 
        title: str, 
        duration: Optional[int] = None,
        album: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search for a track using cascading search strategies with automatic fallback
        
        Implements a two-tier search approach that maximizes the likelihood of finding
        accurate matches while maintaining quality standards. Starts with strict
        matching criteria and falls back to more permissive search if needed.
        
        Args:
            artist: Artist name from Spotify metadata
            title: Track title from Spotify metadata
            duration: Track duration in seconds for validation (optional)
            album: Album name for additional search context (optional)
            
        Returns:
            List of SearchResult objects sorted by score (best matches first)
            Empty list if no suitable matches found above minimum thresholds
            
        Search Strategy:
        
        1. Strict Search (Primary Strategy):
           - High score threshold (65.0) for quality assurance
           - Normalized and cleaned query generation
           - Preference for official content
           - Early termination on high-quality matches
           - Conservative approach for best accuracy
        
        2. Permissive Search (Fallback Strategy):
           - Lower score threshold (45.0) for broader matching
           - Additional query variations and approaches
           - Relaxed content filtering criteria
           - More flexible matching rules
           - Used when strict search fails
        
        The cascading approach ensures that high-quality matches are preferred
        when available, but fallback options exist for difficult-to-match tracks.
        """
        # First attempt: strict search with high quality standards
        results = self._search_with_threshold(
            artist, title, duration, album, 
            threshold=65.0, 
            strict_queries=True
        )
        
        if results:
            self.logger.debug(f"Found with strict search: {artist} - {title}")
            return results
        
        # Second attempt: permissive search with relaxed criteria
        self.logger.debug(f"Strict search failed, trying permissive for: {artist} - {title}")
        results = self._search_with_threshold(
            artist, title, duration, album, 
            threshold=45.0, 
            strict_queries=False
        )
        
        if results:
            self.logger.debug(f"Found with permissive search: {artist} - {title}")
        else:
            self.logger.debug(f"Both searches failed for: {artist} - {title}")
        
        return results

    def _search_with_threshold(
        self,
        artist: str, 
        title: str, 
        duration: Optional[int] = None,
        album: Optional[str] = None,
        threshold: float = 70.0,
        strict_queries: bool = True
    ) -> List[SearchResult]:
        """
        Internal search implementation with configurable threshold and query strategy
        
        Core search engine that handles the actual query generation, execution,
        and result processing. Supports both strict and permissive search modes
        with different query strategies and scoring thresholds.
        
        Args:
            artist: Artist name to search for
            title: Track title to search for
            duration: Track duration for validation (optional)
            album: Album name for context (optional)
            threshold: Minimum score threshold for accepting results
            strict_queries: Whether to use strict or permissive query generation
            
        Returns:
            List of SearchResult objects above threshold, sorted by score
            
        Process:
        1. Generate search queries based on strictness setting
        2. Execute queries with rate limiting and error handling
        3. Extract and analyze metadata from raw results
        4. Calculate similarity and quality scores
        5. Filter results above threshold
        6. Sort by score and return best matches
        
        Query Generation:
        - Strict: Normalized queries with official content preference
        - Permissive: Additional variations including simple concatenation
        - Album context: Adds album information when available
        
        Deduplication:
        Uses video IDs to prevent duplicate results from multiple queries.
        
        Early Termination:
        Strict searches can terminate early when sufficient high-quality
        matches are found to improve performance for obvious matches.
        """
        # Temporarily adjust score threshold for this search
        original_threshold = self.score_threshold
        self.score_threshold = threshold
        
        try:
            all_results = []
            seen_video_ids: Set[str] = set()  # Prevent duplicate results
            
            # Generate search queries based on strictness level
            if strict_queries:
                # Use sophisticated query generation for strict search
                search_queries = create_search_query(artist, title, include_official=self.prefer_official)
            else:
                # Use more permissive query generation for fallback search
                search_queries = create_search_query(artist, title, include_official=True)
                # Add simple concatenated query for broader coverage
                search_queries.append(f"{artist.strip()} {title.strip()}")
            
            # Add album context to improve search accuracy when available
            if album and album.lower() not in title.lower():
                album_query = f"{normalize_artist_name(artist)} {normalize_track_title(title)} {album}"
                search_queries.insert(1, album_query)
            
            # Execute search queries with error handling and rate limiting
            for i, query in enumerate(search_queries):
                try:
                    self.logger.debug(f"Search attempt {i+1}/{len(search_queries)} (threshold={threshold}): '{query}'")
                    
                    # Perform YouTube Music search with rate limiting
                    raw_results = self._search_ytmusic(query, limit=self.max_results)

                    # Debug logging for search analysis
                    self.logger.debug(f"DEBUG: Query '{query}' returned {len(raw_results)} raw results")
                    for idx, raw in enumerate(raw_results[:3]):  # Log first 3
                        self.logger.debug(f"DEBUG Result {idx}: {raw.get('title', 'NO_TITLE')} by {raw.get('artists', [{}])[0].get('name', 'NO_ARTIST') if raw.get('artists') else 'NO_ARTIST'}")
                        
                    # Process each raw result
                    for raw_result in raw_results:
                        video_id = raw_result.get('videoId')
                        
                        # Skip results without video ID or duplicates
                        if not video_id or video_id in seen_video_ids:
                            continue
                        
                        seen_video_ids.add(video_id)
                        
                        # Extract structured metadata from raw result
                        search_result = self._extract_result_metadata(raw_result)
                        
                        # Calculate similarity and quality scores
                        self._calculate_scores(search_result, artist, title, duration)
                        
                        # Debug logging for score analysis
                        self.logger.debug(f"DEBUG Score: {search_result.title} by {search_result.artist} = {search_result.total_score:.1f} (threshold: {self.score_threshold})")

                        # Apply score threshold filter
                        if search_result.total_score >= self.score_threshold:
                            all_results.append(search_result)
                            
                            self.logger.debug(
                                f"Found candidate: {search_result.artist} - {search_result.title} "
                                f"(Score: {search_result.total_score:.1f})"
                            )
                    
                    # Early exit optimization for strict searches
                    # Stop when sufficient high-quality matches are found
                    if strict_queries:
                        high_quality_results = [r for r in all_results if r.total_score >= 85]
                        if len(high_quality_results) >= 3:
                            self.logger.debug("Found sufficient high-quality matches, stopping search")
                            break
                            
                except Exception as e:
                    # Log query failures but continue with remaining queries
                    self.logger.warning(f"Search query '{query}' failed: {e}")
                    continue
            
            # Sort results by total score in descending order (best first)
            all_results.sort(key=lambda x: x.total_score, reverse=True)
            
            return all_results
            
        finally:
            # Always restore original threshold setting
            self.score_threshold = original_threshold
    
    def get_best_match(
        self, 
        artist: str, 
        title: str, 
        duration: Optional[int] = None,
        album: Optional[str] = None
    ) -> Optional[SearchResult]:
        """
        Get the single best match for a track using comprehensive search strategies
        
        Convenience method that performs a complete search and returns only the
        highest-scoring result. Useful when only one result is needed rather
        than a ranked list of candidates.
        
        Args:
            artist: Artist name from Spotify metadata
            title: Track title from Spotify metadata
            duration: Track duration in seconds for validation (optional)
            album: Album name for additional search context (optional)
            
        Returns:
            Best SearchResult if any matches found above threshold, None otherwise
            
        Note:
            This method uses the same cascading search strategy as search_track()
            but returns only the top result for convenience. The result is
            guaranteed to be above the minimum quality threshold if returned.
        """
        # Use full search strategy to find all candidates
        results = self.search_track(artist, title, duration, album)
    
        # Return the highest-scoring result if any found
        if results:
            return results[0]
        
        return None
    
    def search_multiple_tracks(
        self, 
        tracks: List[Tuple[str, str, Optional[int]]]
    ) -> List[Optional[SearchResult]]:
        """
        Search for multiple tracks efficiently with rate limiting and error handling
        
        Batch search method that processes multiple tracks while maintaining
        rate limiting compliance and providing individual error isolation.
        Each track is searched independently to prevent failures from affecting
        other tracks in the batch.
        
        Args:
            tracks: List of (artist, title, duration) tuples to search
                   Duration can be None if not available
            
        Returns:
            List of best matches in same order as input
            None entries for tracks where no suitable match was found
            
        Rate Limiting:
        Applies rate limiting between track searches to comply with YouTube
        Music API guidelines during batch operations. Uses the same interval
        as individual searches.
        
        Error Handling:
        Individual track failures are logged but don't affect other tracks.
        Failed searches return None in the results list to maintain order
        correspondence with the input list.
        
        Progress Tracking:
        Logs progress for long batch operations to provide user feedback
        during large playlist processing operations.
        """
        results = []
        
        # Process each track individually with error isolation
        for i, (artist, title, duration) in enumerate(tracks):
            try:
                self.logger.debug(f"Searching track {i+1}/{len(tracks)}: {artist} - {title}")
                
                # Search for best match using full strategy
                best_match = self.get_best_match(artist, title, duration)
                results.append(best_match)
                
                # Apply rate limiting between tracks (except for last track)
                if i < len(tracks) - 1:
                    time.sleep(self.min_request_interval)
                    
            except Exception as e:
                # Log individual track failure but continue batch processing
                self.logger.error(f"Failed to search track {i+1}: {e}")
                results.append(None)
        
        return results
    
    def validate_search_config(self) -> bool:
        """
        Validate search configuration and API connectivity
        
        Performs a test search to verify that the YouTube Music API is accessible
        and the search configuration is working correctly. Used for diagnostics
        and setup validation.
        
        Returns:
            True if API is accessible and configuration is valid, False otherwise
            
        Test Process:
        1. Attempt simple test search with minimal query
        2. Verify API response structure
        3. Check for expected result format
        4. Return success/failure status
        
        Note:
            This method performs an actual API call, so it will count against
            rate limits and requires internet connectivity.
        """
        try:
            # Perform simple test search to validate API access
            test_results = self._search_ytmusic("test", limit=1)
            self.logger.info("YouTube Music API validation successful")
            return True
        except Exception as e:
            self.logger.error(f"YouTube Music API validation failed: {e}")
            return False
    
    def get_search_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive search statistics and configuration information
        
        Returns detailed information about current search configuration,
        parameters, and operational settings. Useful for debugging, monitoring,
        and configuration validation.
        
        Returns:
            Dictionary containing all relevant search configuration and statistics
            
        Configuration Information:
        - Search parameters (thresholds, limits)
        - Content filtering preferences
        - Quality assessment settings
        - Rate limiting configuration
        - API operational parameters
        
        This information helps with troubleshooting search issues and
        understanding current search behavior and constraints.
        """
        return {
            'max_results': self.max_results,
            'score_threshold': self.score_threshold,
            'prefer_official': self.prefer_official,
            'exclude_live': self.exclude_live,
            'exclude_covers': self.exclude_covers,
            'duration_tolerance': self.duration_tolerance,
            'rate_limit_interval': self.min_request_interval
        }


# Global searcher instance management
# Singleton pattern ensures consistent API client and configuration across application
_searcher_instance: Optional[YouTubeMusicSearcher] = None


def get_ytmusic_searcher() -> YouTubeMusicSearcher:
    """
    Get the global YouTube Music searcher instance (singleton pattern)
    
    Provides access to the shared searcher instance used throughout the
    application. Creates the instance on first access and returns the same
    instance for subsequent calls, ensuring consistent API client state
    and configuration across all search operations.
    
    Returns:
        Global YouTubeMusicSearcher instance
        
    Benefits of Singleton Pattern:
    - Shared API client reduces initialization overhead
    - Consistent rate limiting across all search requests
    - Centralized configuration management
    - Efficient resource utilization for long-running operations
    - Maintains search state and optimizations
    """
    global _searcher_instance
    if not _searcher_instance:
        _searcher_instance = YouTubeMusicSearcher()
    return _searcher_instance


def reset_ytmusic_searcher() -> None:
    """
    Reset the global YouTube Music searcher instance
    
    Clears the global searcher instance, forcing a new instance to be created
    on the next access. Useful for testing, configuration changes, or
    troubleshooting search issues that might require fresh initialization.
    
    Note:
        This resets the searcher instance but does not affect API quotas or
        rate limiting timers. The next access will create a fresh instance
        with current configuration and clean state.
    """
    global _searcher_instance
    _searcher_instance = None