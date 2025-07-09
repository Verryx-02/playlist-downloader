"""
YouTube Music intelligent search with multi-strategy matching algorithm
Implements sophisticated scoring system for finding best track matches
"""

import re
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
    """YouTube Music search result with scoring"""
    video_id: str
    title: str
    artist: str
    duration: Optional[int]  # seconds
    album: Optional[str]
    thumbnail: Optional[str]
    view_count: Optional[int]
    
    # Metadata flags
    is_official: bool = False
    is_verified_artist: bool = False
    is_music_video: bool = False
    is_live: bool = False
    is_cover: bool = False
    is_karaoke: bool = False
    is_remix: bool = False
    
    # Scoring
    title_score: float = 0.0
    artist_score: float = 0.0
    duration_score: float = 0.0
    quality_bonus: float = 0.0
    total_score: float = 0.0
    
    def __post_init__(self):
        """Calculate total score after initialization"""
        self.total_score = (
            self.title_score + 
            self.artist_score + 
            self.duration_score + 
            self.quality_bonus
        )


class YouTubeMusicSearcher:
    """Intelligent YouTube Music search with advanced matching"""
    
    def __init__(self):
        """Initialize YouTube Music searcher"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self._ytmusic: Optional[YTMusic] = None
        
        # Search configuration
        self.max_results = self.settings.ytmusic.max_results
        self.score_threshold = self.settings.ytmusic.score_threshold
        self.prefer_official = self.settings.ytmusic.prefer_official
        self.exclude_live = self.settings.ytmusic.exclude_live
        self.exclude_covers = self.settings.ytmusic.exclude_covers
        self.duration_tolerance = self.settings.ytmusic.duration_tolerance
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between searches
        
        # Quality indicators
        self.official_indicators = [
            'official audio', 'official video', 'official music video',
            'provided to youtube', 'auto-generated'
        ]
        
        self.negative_indicators = [
            'live', 'concert', 'tour', 'acoustic',
            'cover', 'covered by', 'covers',
            'karaoke', 'instrumental', 'piano version',
            'remix', 'extended', 'mashup', 'mix'
        ]
        
        # Artist verification patterns
        self.verified_patterns = [
            'official artist channel',
            'verified',
            '✓'
        ]
    
    @property
    def ytmusic(self) -> YTMusic:
        """Get YouTube Music API client"""
        if not self._ytmusic:
            try:
                # Initialize without authentication (public access)
                self._ytmusic = YTMusic()
                self.logger.info("YouTube Music API initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize YouTube Music API: {e}")
                raise Exception(f"YouTube Music initialization failed: {e}")
        return self._ytmusic
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def _search_ytmusic(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Perform YouTube Music search with rate limiting and retry
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of search results
        """
        self._rate_limit()
        
        try:
            # Search for songs specifically
            results = self.ytmusic.search(
                query=query,
                filter='songs',
                limit=limit
            )
            
            self.logger.debug(f"YTMusic search '{query}' returned {len(results)} results")
            return results
            
        except YTMusicError as e:
            self.logger.warning(f"YTMusic search failed for '{query}': {e}")
            raise e
        except Exception as e:
            self.logger.error(f"Unexpected error in YTMusic search: {e}")
            raise e
    
    def _extract_result_metadata(self, result: Dict[str, Any]) -> SearchResult:
        """
        Extract and parse metadata from YTMusic search result
        
        Args:
            result: Raw YTMusic search result
            
        Returns:
            Parsed SearchResult object
        """
        try:
            # Basic information
            video_id = result.get('videoId', '')
            title = result.get('title', '')
            
            # Artist information
            artists = result.get('artists', [])
            if artists and len(artists) > 0:
                artist = artists[0].get('name', 'Unknown Artist')
            else:
                artist = 'Unknown Artist'
            
            # Duration parsing
            duration_text = result.get('duration')
            duration = None
            if duration_text:
                duration = parse_duration_string(duration_text)
            
            # Album information
            album = None
            if result.get('album'):
                album = result['album'].get('name')
            
            # Thumbnail
            thumbnails = result.get('thumbnails', [])
            thumbnail = thumbnails[-1]['url'] if thumbnails else None
            
            # View count (if available)
            view_count = None
            
            # Create SearchResult object
            search_result = SearchResult(
                video_id=video_id,
                title=title,
                artist=artist,
                duration=duration,
                album=album,
                thumbnail=thumbnail,
                view_count=view_count
            )
            
            # Analyze metadata flags
            self._analyze_result_flags(search_result, result)
            
            return search_result
            
        except Exception as e:
            self.logger.warning(f"Failed to extract metadata from result: {e}")
            # Return minimal result
            return SearchResult(
                video_id=result.get('videoId', ''),
                title=result.get('title', ''),
                artist='Unknown Artist'
            )
    
    def _analyze_result_flags(self, search_result: SearchResult, raw_result: Dict[str, Any]) -> None:
        """
        Analyze result to set metadata flags
        
        Args:
            search_result: SearchResult to update
            raw_result: Raw YTMusic result data
        """
        title_lower = search_result.title.lower()
        artist_lower = search_result.artist.lower()
        
        # Check for official indicators
        for indicator in self.official_indicators:
            if indicator in title_lower:
                search_result.is_official = True
                break
        
        # Check for negative indicators
        for indicator in self.negative_indicators:
            if indicator in title_lower:
                if 'live' in indicator or 'concert' in indicator:
                    search_result.is_live = True
                elif 'cover' in indicator:
                    search_result.is_cover = True
                elif 'karaoke' in indicator:
                    search_result.is_karaoke = True
                elif 'remix' in indicator or 'mix' in indicator:
                    search_result.is_remix = True
        
        # Check if it's a music video
        if 'music video' in title_lower or 'official video' in title_lower:
            search_result.is_music_video = True
        
        # Check for verified artist (limited info from YTMusic API)
        artists = raw_result.get('artists', [])
        for artist_info in artists:
            if artist_info.get('name') == search_result.artist:
                # Check if channel seems verified (heuristic)
                channel_id = artist_info.get('id', '')
                if channel_id:
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
        Calculate matching scores for search result
        
        Args:
            search_result: SearchResult to score
            target_artist: Target artist name
            target_title: Target track title
            target_duration: Target duration in seconds
        """
        # Normalize for comparison
        norm_target_artist = normalize_artist_name(target_artist)
        norm_target_title = normalize_track_title(target_title)
        norm_result_artist = normalize_artist_name(search_result.artist)
        norm_result_title = normalize_track_title(search_result.title)
        
        # Title similarity (40 points max)
        title_similarity = calculate_similarity(norm_target_title, norm_result_title)
        search_result.title_score = title_similarity * 40
        
        # Artist similarity (30 points max)
        artist_similarity = calculate_similarity(norm_target_artist, norm_result_artist)
        search_result.artist_score = artist_similarity * 30
        
        # Duration similarity (20 points max)
        if target_duration and search_result.duration:
            duration_diff = abs(target_duration - search_result.duration)
            if duration_diff <= self.duration_tolerance:
                # Perfect match
                search_result.duration_score = 20
            elif duration_diff <= self.duration_tolerance * 3:
                # Good match with penalty
                penalty = (duration_diff - self.duration_tolerance) / (self.duration_tolerance * 2)
                search_result.duration_score = 20 * (1 - penalty)
            else:
                # Poor duration match
                search_result.duration_score = 0
        else:
            # No duration info, give neutral score
            search_result.duration_score = 10
        
        # Quality bonus (10 points max)
        quality_bonus = 0
        
        # Official audio bonus
        if search_result.is_official:
            quality_bonus += 5
        
        # Verified artist bonus
        if search_result.is_verified_artist:
            quality_bonus += 2
        
        # Music video penalty (prefer audio)
        if search_result.is_music_video and self.prefer_official:
            quality_bonus -= 1
        
        # Negative content penalties
        if search_result.is_live and self.exclude_live:
            quality_bonus -= 8
        if search_result.is_cover and self.exclude_covers:
            quality_bonus -= 6
        if search_result.is_karaoke:
            quality_bonus -= 10
        if search_result.is_remix:
            quality_bonus -= 3
        
        search_result.quality_bonus = max(-10, min(10, quality_bonus))
        
        # Calculate total score
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
        Search for a track using cascading strategies
        
        Args:
            artist: Artist name
            title: Track title
            duration: Track duration in seconds
            album: Album name (optional context)
            
        Returns:
            List of SearchResult objects sorted by score
        """
        # First attempt: strict search
        results = self._search_with_threshold(artist, title, duration, album, threshold=65.0, strict_queries=True)
        
        if results:
            self.logger.debug(f"Found with strict search: {artist} - {title}")
            return results
        
        # Second attempt: permissive search
        self.logger.debug(f"Strict search failed, trying permissive for: {artist} - {title}")
        results = self._search_with_threshold(artist, title, duration, album, threshold=45.0, strict_queries=False)
        
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
        """Internal search with specific threshold and query strategy"""
        
        # Temporarily change threshold
        original_threshold = self.score_threshold
        self.score_threshold = threshold
        
        try:
            all_results = []
            seen_video_ids: Set[str] = set()
            
            # Generate search queries based on strictness
            if strict_queries:
                search_queries = create_search_query(artist, title, include_official=self.prefer_official)
            else:
                # More permissive queries for fallback
                search_queries = create_search_query(artist, title, include_official=True)
                # Add simple concatenated query
                search_queries.append(f"{artist.strip()} {title.strip()}")
            
            # Add album context if available
            if album and album.lower() not in title.lower():
                album_query = f"{normalize_artist_name(artist)} {normalize_track_title(title)} {album}"
                search_queries.insert(1, album_query)
            
            # Execute searches
            for i, query in enumerate(search_queries):
                try:
                    self.logger.debug(f"Search attempt {i+1}/{len(search_queries)} (threshold={threshold}): '{query}'")
                    
                    # Perform search
                    raw_results = self._search_ytmusic(query, limit=self.max_results)

                    # DEBUG: Log raw results
                    self.logger.debug(f"DEBUG: Query '{query}' returned {len(raw_results)} raw results")
                    for idx, raw in enumerate(raw_results[:3]):  # Log first 3
                        self.logger.debug(f"DEBUG Result {idx}: {raw.get('title', 'NO_TITLE')} by {raw.get('artists', [{}])[0].get('name', 'NO_ARTIST') if raw.get('artists') else 'NO_ARTIST'}")
                        
                        # Process results
                    for raw_result in raw_results:
                        video_id = raw_result.get('videoId')
                        if not video_id or video_id in seen_video_ids:
                            continue
                        
                        seen_video_ids.add(video_id)
                        
                        # Extract metadata
                        search_result = self._extract_result_metadata(raw_result)
                        
                        # Calculate scores
                        self._calculate_scores(search_result, artist, title, duration)
                        
                        # DEBUG: Log scores
                        self.logger.debug(f"DEBUG Score: {search_result.title} by {search_result.artist} = {search_result.total_score:.1f} (threshold: {self.score_threshold})")

                        # Apply score threshold
                        if search_result.total_score >= self.score_threshold:
                            all_results.append(search_result)
                            
                            self.logger.debug(
                                f"Found candidate: {search_result.artist} - {search_result.title} "
                                f"(Score: {search_result.total_score:.1f})"
                            )
                    
                    # Early exit if we found high-quality matches (only for strict search)
                    if strict_queries:
                        high_quality_results = [r for r in all_results if r.total_score >= 85]
                        if len(high_quality_results) >= 3:
                            self.logger.debug("Found sufficient high-quality matches, stopping search")
                            break
                            
                except Exception as e:
                    self.logger.warning(f"Search query '{query}' failed: {e}")
                    continue
            
            # Sort by score (highest first)
            all_results.sort(key=lambda x: x.total_score, reverse=True)
            
            return all_results
            
        finally:
            # Restore original threshold
            self.score_threshold = original_threshold
    
    def get_best_match(
        self, 
        artist: str, 
        title: str, 
        duration: Optional[int] = None,
        album: Optional[str] = None
    ) -> Optional[SearchResult]:
        """
        Get the best match for a track
        
        Args:
            artist: Artist name
            title: Track title
            duration: Track duration in seconds
            album: Album name (optional context)
            
        Returns:
            Best SearchResult or None if no good match found
        """
        results = self.search_track(artist, title, duration, album)
    
        if results:
            return results[0]
        
        return None
    
    def search_multiple_tracks(
        self, 
        tracks: List[Tuple[str, str, Optional[int]]]
    ) -> List[Optional[SearchResult]]:
        """
        Search for multiple tracks efficiently
        
        Args:
            tracks: List of (artist, title, duration) tuples
            
        Returns:
            List of best matches (None for tracks with no good match)
        """
        results = []
        
        for i, (artist, title, duration) in enumerate(tracks):
            try:
                self.logger.debug(f"Searching track {i+1}/{len(tracks)}: {artist} - {title}")
                
                best_match = self.get_best_match(artist, title, duration)
                results.append(best_match)
                
                # Rate limiting between tracks
                if i < len(tracks) - 1:
                    time.sleep(self.min_request_interval)
                    
            except Exception as e:
                self.logger.error(f"Failed to search track {i+1}: {e}")
                results.append(None)
        
        return results
    
    def validate_search_config(self) -> bool:
        """
        Validate search configuration
        
        Returns:
            True if configuration is valid
        """
        try:
            # Test API connectivity
            test_results = self._search_ytmusic("test", limit=1)
            self.logger.info("YouTube Music API validation successful")
            return True
        except Exception as e:
            self.logger.error(f"YouTube Music API validation failed: {e}")
            return False
    
    def get_search_stats(self) -> Dict[str, Any]:
        """
        Get search statistics and configuration
        
        Returns:
            Dictionary with search stats
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


# Global searcher instance
_searcher_instance: Optional[YouTubeMusicSearcher] = None


def get_ytmusic_searcher() -> YouTubeMusicSearcher:
    """Get global YouTube Music searcher instance"""
    global _searcher_instance
    if not _searcher_instance:
        _searcher_instance = YouTubeMusicSearcher()
    return _searcher_instance


def reset_ytmusic_searcher() -> None:
    """Reset global YouTube Music searcher instance"""
    global _searcher_instance
    _searcher_instance = None