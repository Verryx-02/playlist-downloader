"""
Genius API integration for lyrics retrieval
Primary lyrics source with intelligent search and quality validation
"""

import time
import re
from typing import Optional, Dict, Any, List, Tuple
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
from ..spotify.models import LyricsSource


@dataclass
class GeniusSearchResult:
    """Genius search result with scoring"""
    song_id: int
    title: str
    artist: str
    album: Optional[str]
    url: str
    lyrics: Optional[str] = None
    
    # Match scoring
    title_score: float = 0.0
    artist_score: float = 0.0
    total_score: float = 0.0
    
    # Metadata
    view_count: Optional[int] = None
    release_date: Optional[str] = None
    featured_artists: List[str] = None
    
    def __post_init__(self):
        if self.featured_artists is None:
            self.featured_artists = []


class GeniusLyricsProvider:
    """Genius API lyrics provider with intelligent search"""
    
    def __init__(self):
        """Initialize Genius lyrics provider"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # API configuration
        self.api_key = self.settings.lyrics.genius_api_key
        self.timeout = self.settings.lyrics.timeout
        self.max_attempts = self.settings.lyrics.max_attempts
        self.similarity_threshold = self.settings.lyrics.similarity_threshold
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests (Genius limit: 60/hour)
        
        # Genius client
        self._genius_client: Optional[lyricsgenius.Genius] = None
        
        # Search optimization
        self.max_search_results = 5
        self.score_threshold = 70.0  # Minimum score for accepting results
    
    @property
    def genius_client(self) -> lyricsgenius.Genius:
        """Get authenticated Genius client"""
        if not self._genius_client:
            if not self.api_key:
                raise Exception("Genius API key not configured")
            
            try:
                self._genius_client = lyricsgenius.Genius(
                    access_token=self.api_key,
                    timeout=self.timeout,
                    retries=self.max_attempts,
                    remove_section_headers=False,  # We'll clean manually
                    skip_non_songs=True,
                    excluded_terms=["(Remix)", "(Live)", "(Cover)", "(Karaoke)"],
                    verbose=False
                )
                
                self.logger.info("Genius API client initialized")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize Genius client: {e}")
                raise Exception(f"Genius API initialization failed: {e}")
        
        return self._genius_client
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between API requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def search_lyrics(self, artist: str, title: str, album: Optional[str] = None) -> Optional[str]:
        """
        Search for lyrics using Genius API
        
        Args:
            artist: Artist name
            title: Track title
            album: Album name (optional for better matching)
            
        Returns:
            Lyrics text or None if not found
        """
        try:
            self.logger.info(f"Searching Genius for: {artist} - {title}")
            
            # Apply rate limiting
            self._rate_limit()
            
            # Search for songs
            search_results = self._search_songs(artist, title)
            
            if not search_results:
                self.logger.info(f"No Genius results found for: {artist} - {title}")
                return None
            
            # Score and rank results
            scored_results = self._score_search_results(search_results, artist, title, album)
            
            # Get lyrics from best match
            best_result = scored_results[0]
            
            if best_result.total_score < self.score_threshold:
                self.logger.info(
                    f"Best Genius match score too low: {best_result.total_score:.1f} "
                    f"(threshold: {self.score_threshold})"
                )
                return None
            
            # Fetch lyrics
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
        Search for songs on Genius
        
        Args:
            artist: Artist name
            title: Track title
            
        Returns:
            List of search results
        """
        search_queries = self._generate_search_queries(artist, title)
        all_results = []
        seen_song_ids = set()
        
        for query in search_queries:
            try:
                self.logger.debug(f"Genius search query: '{query}'")
                
                # Apply rate limiting
                self._rate_limit()
                
                # Perform search
                search_response = self.genius_client.search_songs(query, per_page=self.max_search_results)
                
                if search_response and 'hits' in search_response:
                    for hit in search_response['hits']:
                        result = hit.get('result', {})
                        song_id = result.get('id')
                        
                        if song_id and song_id not in seen_song_ids:
                            seen_song_ids.add(song_id)
                            all_results.append(result)
                
                # Early exit if we have enough good results
                if len(all_results) >= self.max_search_results * 2:
                    break
                    
            except Exception as e:
                self.logger.debug(f"Genius search query '{query}' failed: {e}")
                continue
        
        return all_results[:self.max_search_results * 2]  # Limit total results
    
    def _generate_search_queries(self, artist: str, title: str) -> List[str]:
        """
        Generate multiple search queries for better matching
        
        Args:
            artist: Artist name
            title: Track title
            
        Returns:
            List of search queries
        """
        queries = []
        
        # Normalize inputs
        norm_artist = normalize_artist_name(artist)
        norm_title = normalize_track_title(title)
        
        # Primary query: "Artist Title"
        queries.append(f"{norm_artist} {norm_title}")
        
        # Alternative queries
        queries.append(f"{artist} {title}")  # Original formatting
        queries.append(norm_title)  # Title only
        
        # Remove featuring information for cleaner search
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
        Score and rank search results
        
        Args:
            results: Raw search results from Genius
            target_artist: Target artist name
            target_title: Target track title
            target_album: Target album name
            
        Returns:
            List of scored results sorted by score
        """
        scored_results = []
        
        for result in results:
            try:
                # Extract result information
                genius_result = self._extract_result_info(result)
                
                # Calculate similarity scores
                self._calculate_similarity_scores(
                    genius_result, target_artist, target_title, target_album
                )
                
                scored_results.append(genius_result)
                
            except Exception as e:
                self.logger.debug(f"Failed to score Genius result: {e}")
                continue
        
        # Sort by total score (highest first)
        scored_results.sort(key=lambda x: x.total_score, reverse=True)
        
        return scored_results
    
    def _extract_result_info(self, result: Dict[str, Any]) -> GeniusSearchResult:
        """
        Extract information from Genius search result
        
        Args:
            result: Raw Genius search result
            
        Returns:
            GeniusSearchResult object
        """
        # Basic information
        song_id = result.get('id', 0)
        title = result.get('title', '')
        url = result.get('url', '')
        
        # Primary artist
        primary_artist = result.get('primary_artist', {})
        artist = primary_artist.get('name', '') if primary_artist else ''
        
        # Album information
        album = None
        if result.get('album'):
            album = result['album'].get('name')
        
        # Featured artists
        featured_artists = []
        for featured_artist in result.get('featured_artists', []):
            if featured_artist.get('name'):
                featured_artists.append(featured_artist['name'])
        
        # Stats
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
        Calculate similarity scores for search result
        
        Args:
            result: GeniusSearchResult to score
            target_artist: Target artist name
            target_title: Target track title
            target_album: Target album name
        """
        # Normalize for comparison
        norm_target_artist = normalize_artist_name(target_artist)
        norm_target_title = normalize_track_title(target_title)
        norm_result_artist = normalize_artist_name(result.artist)
        norm_result_title = normalize_track_title(result.title)
        
        # Title similarity (60 points max)
        title_similarity = calculate_similarity(norm_target_title, norm_result_title)
        result.title_score = title_similarity * 60
        
        # Artist similarity (40 points max)
        artist_similarity = calculate_similarity(norm_target_artist, norm_result_artist)
        
        # Check featured artists if primary artist doesn't match well
        if artist_similarity < 0.8 and result.featured_artists:
            for featured_artist in result.featured_artists:
                norm_featured = normalize_artist_name(featured_artist)
                featured_similarity = calculate_similarity(norm_target_artist, norm_featured)
                if featured_similarity > artist_similarity:
                    artist_similarity = featured_similarity
                    break
        
        result.artist_score = artist_similarity * 40
        
        # Album bonus (if available and matches)
        album_bonus = 0
        if target_album and result.album:
            album_similarity = calculate_similarity(
                target_album.lower().strip(),
                result.album.lower().strip()
            )
            if album_similarity > 0.8:
                album_bonus = 5
        
        # Popularity bonus (based on view count)
        popularity_bonus = 0
        if result.view_count and result.view_count > 100000:  # 100k+ views
            popularity_bonus = min(3, result.view_count / 1000000)  # Max 3 points
        
        # Calculate total score
        result.total_score = (
            result.title_score + 
            result.artist_score + 
            album_bonus + 
            popularity_bonus
        )
    
    @retry_on_failure(max_attempts=2, delay=1.0)
    def _fetch_lyrics(self, result: GeniusSearchResult) -> Optional[str]:
        """
        Fetch lyrics for a specific song
        
        Args:
            result: GeniusSearchResult to fetch lyrics for
            
        Returns:
            Lyrics text or None
        """
        try:
            self.logger.debug(f"Fetching lyrics for: {result.artist} - {result.title}")
            
            # Apply rate limiting
            self._rate_limit()
            
            # Fetch song details including lyrics
            song = self.genius_client.song(result.song_id)
            
            if song and hasattr(song, 'lyrics') and song.lyrics:
                # Clean and validate lyrics
                cleaned_lyrics = clean_lyrics_text(song.lyrics)
                
                if validate_lyrics_content(cleaned_lyrics, self.settings.lyrics.min_length):
                    return cleaned_lyrics
                else:
                    self.logger.debug(f"Lyrics validation failed for: {result.title}")
                    return None
            else:
                self.logger.debug(f"No lyrics content found for: {result.title}")
                return None
                
        except Exception as e:
            self.logger.debug(f"Failed to fetch lyrics from Genius: {e}")
            return None
    
    def get_song_info(self, song_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed song information from Genius
        
        Args:
            song_id: Genius song ID
            
        Returns:
            Song information dictionary or None
        """
        try:
            self._rate_limit()
            
            song = self.genius_client.song(song_id)
            
            if song:
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
        Search for songs by a specific artist
        
        Args:
            artist_name: Artist name to search for
            max_songs: Maximum number of songs to return
            
        Returns:
            List of song information dictionaries
        """
        try:
            self.logger.info(f"Searching Genius for artist: {artist_name}")
            
            self._rate_limit()
            
            # Search for artist
            artist = self.genius_client.search_artist(artist_name, max_songs=max_songs)
            
            if artist and hasattr(artist, 'songs'):
                songs = []
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
        Validate Genius API access
        
        Returns:
            True if API is accessible
        """
        try:
            if not self.api_key:
                self.logger.debug("Genius API key not configured")
                return False
            
            # Test API with a simple search
            self._rate_limit()
            test_response = self.genius_client.search_songs("test", per_page=1)
            
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
        Get API status and configuration
        
        Returns:
            Dictionary with API status information
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


# Global Genius provider instance
_genius_provider: Optional[GeniusLyricsProvider] = None


def get_genius_provider() -> GeniusLyricsProvider:
    """Get global Genius lyrics provider instance"""
    global _genius_provider
    if not _genius_provider:
        _genius_provider = GeniusLyricsProvider()
    return _genius_provider


def reset_genius_provider() -> None:
    """Reset global Genius lyrics provider instance"""
    global _genius_provider
    _genius_provider = None