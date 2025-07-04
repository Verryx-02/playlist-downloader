"""
Musixmatch API integration for lyrics retrieval
Fallback lyrics source with high-quality commercial lyrics database
"""

import time
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

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
class MusixmatchTrack:
    """Musixmatch track information"""
    track_id: int
    track_name: str
    artist_name: str
    album_name: Optional[str]
    has_lyrics: bool
    has_synced_lyrics: bool
    instrumental: bool
    explicit: bool
    
    # Match scoring
    title_score: float = 0.0
    artist_score: float = 0.0
    total_score: float = 0.0


class MusixmatchLyricsProvider:
    """Musixmatch API lyrics provider"""
    
    def __init__(self):
        """Initialize Musixmatch lyrics provider"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # API configuration
        self.api_key = self.settings.lyrics.musixmatch_api_key
        self.timeout = self.settings.lyrics.timeout
        self.max_attempts = self.settings.lyrics.max_attempts
        self.similarity_threshold = self.settings.lyrics.similarity_threshold
        
        # API endpoints
        self.base_url = "https://api.musixmatch.com/ws/1.1"
        
        # Rate limiting (free tier: 2000 requests/day, ~1.4 requests/minute)
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms between requests
        
        # HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.settings.network.user_agent
        })
        
        # Search configuration
        self.max_search_results = 5
        self.score_threshold = 70.0
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between API requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_api_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make API request to Musixmatch
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Response data or None if failed
        """
        if not self.api_key:
            self.logger.warning("Musixmatch API key not configured")
            return None
        
        # Apply rate limiting
        self._rate_limit()
        
        # Add API key to parameters
        params['apikey'] = self.api_key
        
        try:
            url = f"{self.base_url}/{endpoint}"
            
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check API response status
            if data.get('message', {}).get('header', {}).get('status_code') != 200:
                error_msg = data.get('message', {}).get('header', {}).get('hint', 'Unknown error')
                self.logger.warning(f"Musixmatch API error: {error_msg}")
                return None
            
            return data.get('message', {}).get('body', {})
            
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Musixmatch API request failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in Musixmatch API request: {e}")
            return None
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def search_lyrics(self, artist: str, title: str, album: Optional[str] = None) -> Optional[str]:
        """
        Search for lyrics using Musixmatch API
        
        Args:
            artist: Artist name
            title: Track title
            album: Album name (optional)
            
        Returns:
            Lyrics text or None if not found
        """
        try:
            self.logger.info(f"Searching Musixmatch for: {artist} - {title}")
            
            # Search for tracks
            tracks = self._search_tracks(artist, title)
            
            if not tracks:
                self.logger.info(f"No Musixmatch tracks found for: {artist} - {title}")
                return None
            
            # Score and rank results
            scored_tracks = self._score_search_results(tracks, artist, title, album)
            
            # Get lyrics from best match
            best_track = scored_tracks[0]
            
            if best_track.total_score < self.score_threshold:
                self.logger.info(
                    f"Best Musixmatch match score too low: {best_track.total_score:.1f} "
                    f"(threshold: {self.score_threshold})"
                )
                return None
            
            # Check if track has lyrics
            if not best_track.has_lyrics:
                self.logger.info(f"Musixmatch track has no lyrics: {best_track.track_name}")
                return None
            
            if best_track.instrumental:
                self.logger.info(f"Musixmatch track is instrumental: {best_track.track_name}")
                return None
            
            # Fetch lyrics
            lyrics = self._fetch_lyrics(best_track.track_id)
            
            if lyrics:
                self.logger.info(
                    f"Musixmatch lyrics found: {best_track.artist_name} - {best_track.track_name} "
                    f"(Score: {best_track.total_score:.1f})"
                )
                return lyrics
            else:
                self.logger.warning(f"Failed to fetch lyrics from Musixmatch for best match")
                return None
                
        except Exception as e:
            self.logger.error(f"Musixmatch lyrics search failed: {e}")
            return None
    
    def _search_tracks(self, artist: str, title: str) -> List[Dict[str, Any]]:
        """
        Search for tracks on Musixmatch
        
        Args:
            artist: Artist name
            title: Track title
            
        Returns:
            List of track results
        """
        search_queries = self._generate_search_queries(artist, title)
        all_tracks = []
        seen_track_ids = set()
        
        for query_artist, query_title in search_queries:
            try:
                self.logger.debug(f"Musixmatch search: '{query_artist}' - '{query_title}'")
                
                # Search tracks
                response = self._make_api_request('track.search', {
                    'q_artist': query_artist,
                    'q_track': query_title,
                    'page_size': self.max_search_results,
                    'page': 1,
                    's_track_rating': 'desc'  # Sort by rating
                })
                
                if response and 'track_list' in response:
                    for track_item in response['track_list']:
                        track = track_item.get('track', {})
                        track_id = track.get('track_id')
                        
                        if track_id and track_id not in seen_track_ids:
                            seen_track_ids.add(track_id)
                            all_tracks.append(track)
                
                # Early exit if we have enough results
                if len(all_tracks) >= self.max_search_results * 2:
                    break
                    
            except Exception as e:
                self.logger.warning(f"Musixmatch search failed for '{query_artist} - {query_title}': {e}")
                continue
        
        return all_tracks[:self.max_search_results * 2]
    
    def _generate_search_queries(self, artist: str, title: str) -> List[tuple]:
        """
        Generate search query variations
        
        Args:
            artist: Artist name
            title: Track title
            
        Returns:
            List of (artist, title) tuples
        """
        queries = []
        
        # Normalize inputs
        norm_artist = normalize_artist_name(artist)
        norm_title = normalize_track_title(title)
        
        # Primary query
        queries.append((norm_artist, norm_title))
        
        # Original formatting
        queries.append((artist.strip(), title.strip()))
        
        # Remove featuring information
        import re
        clean_artist = re.sub(r'\s*(feat|ft|featuring)\.?\s+.*', '', norm_artist, flags=re.IGNORECASE)
        if clean_artist != norm_artist:
            queries.append((clean_artist, norm_title))
        
        return queries
    
    def _score_search_results(
        self, 
        tracks: List[Dict[str, Any]], 
        target_artist: str, 
        target_title: str,
        target_album: Optional[str] = None
    ) -> List[MusixmatchTrack]:
        """
        Score and rank search results
        
        Args:
            tracks: Raw track results from Musixmatch
            target_artist: Target artist name
            target_title: Target track title
            target_album: Target album name
            
        Returns:
            List of scored tracks sorted by score
        """
        scored_tracks = []
        
        for track in tracks:
            try:
                # Extract track information
                musix_track = self._extract_track_info(track)
                
                # Calculate similarity scores
                self._calculate_similarity_scores(
                    musix_track, target_artist, target_title, target_album
                )
                
                scored_tracks.append(musix_track)
                
            except Exception as e:
                self.logger.warning(f"Failed to score Musixmatch track: {e}")
                continue
        
        # Sort by total score (highest first)
        scored_tracks.sort(key=lambda x: x.total_score, reverse=True)
        
        return scored_tracks
    
    def _extract_track_info(self, track: Dict[str, Any]) -> MusixmatchTrack:
        """
        Extract track information from Musixmatch response
        
        Args:
            track: Raw track data from API
            
        Returns:
            MusixmatchTrack object
        """
        return MusixmatchTrack(
            track_id=track.get('track_id', 0),
            track_name=track.get('track_name', ''),
            artist_name=track.get('artist_name', ''),
            album_name=track.get('album_name'),
            has_lyrics=bool(track.get('has_lyrics', 0)),
            has_synced_lyrics=bool(track.get('has_subtitles', 0)),
            instrumental=bool(track.get('instrumental', 0)),
            explicit=bool(track.get('explicit', 0))
        )
    
    def _calculate_similarity_scores(
        self, 
        track: MusixmatchTrack, 
        target_artist: str, 
        target_title: str,
        target_album: Optional[str] = None
    ) -> None:
        """
        Calculate similarity scores for track
        
        Args:
            track: MusixmatchTrack to score
            target_artist: Target artist name
            target_title: Target track title
            target_album: Target album name
        """
        # Normalize for comparison
        norm_target_artist = normalize_artist_name(target_artist)
        norm_target_title = normalize_track_title(target_title)
        norm_track_artist = normalize_artist_name(track.artist_name)
        norm_track_title = normalize_track_title(track.track_name)
        
        # Title similarity (60 points max)
        title_similarity = calculate_similarity(norm_target_title, norm_track_title)
        track.title_score = title_similarity * 60
        
        # Artist similarity (40 points max)
        artist_similarity = calculate_similarity(norm_target_artist, norm_track_artist)
        track.artist_score = artist_similarity * 40
        
        # Album bonus (if available and matches)
        album_bonus = 0
        if target_album and track.album_name:
            album_similarity = calculate_similarity(
                target_album.lower().strip(),
                track.album_name.lower().strip()
            )
            if album_similarity > 0.8:
                album_bonus = 5
        
        # Quality bonuses
        quality_bonus = 0
        if track.has_lyrics:
            quality_bonus += 3
        if track.has_synced_lyrics:
            quality_bonus += 2
        
        # Penalties
        if track.instrumental:
            quality_bonus -= 10
        
        # Calculate total score
        track.total_score = (
            track.title_score + 
            track.artist_score + 
            album_bonus + 
            quality_bonus
        )
    
    @retry_on_failure(max_attempts=2, delay=1.0)
    def _fetch_lyrics(self, track_id: int) -> Optional[str]:
        """
        Fetch lyrics for a specific track
        
        Args:
            track_id: Musixmatch track ID
            
        Returns:
            Lyrics text or None
        """
        try:
            self.logger.debug(f"Fetching lyrics for track ID: {track_id}")
            
            # Get lyrics
            response = self._make_api_request('track.lyrics.get', {
                'track_id': track_id
            })
            
            if response and 'lyrics' in response:
                lyrics_data = response['lyrics']
                lyrics_body = lyrics_data.get('lyrics_body', '')
                
                if lyrics_body:
                    # Clean Musixmatch footer
                    if '******* This Lyrics is NOT for Commercial use *******' in lyrics_body:
                        lyrics_body = lyrics_body.replace(
                            '******* This Lyrics is NOT for Commercial use *******', ''
                        ).strip()
                    
                    # Remove character limit warning
                    if '(1409618976710)' in lyrics_body:
                        lyrics_body = lyrics_body.replace('(1409618976710)', '').strip()
                    
                    # Clean and validate
                    cleaned_lyrics = clean_lyrics_text(lyrics_body)
                    
                    if validate_lyrics_content(cleaned_lyrics, self.settings.lyrics.min_length):
                        return cleaned_lyrics
                    else:
                        self.logger.debug(f"Musixmatch lyrics validation failed for track {track_id}")
                        return None
                else:
                    self.logger.debug(f"Empty lyrics body for track {track_id}")
                    return None
            else:
                self.logger.debug(f"No lyrics data in response for track {track_id}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Failed to fetch lyrics from Musixmatch: {e}")
            return None
    
    def get_synced_lyrics(self, track_id: int) -> Optional[str]:
        """
        Get synchronized lyrics for a track
        
        Args:
            track_id: Musixmatch track ID
            
        Returns:
            Synced lyrics in LRC format or None
        """
        try:
            self.logger.debug(f"Fetching synced lyrics for track ID: {track_id}")
            
            response = self._make_api_request('track.subtitle.get', {
                'track_id': track_id,
                'subtitle_format': 'lrc'
            })
            
            if response and 'subtitle' in response:
                subtitle_data = response['subtitle']
                subtitle_body = subtitle_data.get('subtitle_body', '')
                
                if subtitle_body:
                    # Validate LRC format
                    if '[' in subtitle_body and ']' in subtitle_body:
                        return subtitle_body
                    else:
                        self.logger.debug(f"Invalid LRC format for track {track_id}")
                        return None
                else:
                    self.logger.debug(f"Empty subtitle body for track {track_id}")
                    return None
            else:
                self.logger.debug(f"No subtitle data for track {track_id}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Failed to fetch synced lyrics: {e}")
            return None
    
    def search_track_by_isrc(self, isrc: str) -> Optional[Dict[str, Any]]:
        """
        Search for track by ISRC code
        
        Args:
            isrc: International Standard Recording Code
            
        Returns:
            Track information or None
        """
        try:
            response = self._make_api_request('track.get', {
                'track_isrc': isrc
            })
            
            if response and 'track' in response:
                return response['track']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to search by ISRC: {e}")
            return None
    
    def validate_api_access(self) -> bool:
        """
        Validate Musixmatch API access
        
        Returns:
            True if API is accessible
        """
        try:
            if not self.api_key:
                self.logger.warning("Musixmatch API key not configured")
                return False
            
            # Test API with chart.tracks.get (simple request)
            response = self._make_api_request('chart.tracks.get', {
                'page': 1,
                'page_size': 1,
                'country': 'us'
            })
            
            if response and 'track_list' in response:
                self.logger.info("Musixmatch API validation successful")
                return True
            else:
                self.logger.warning("Musixmatch API test request failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Musixmatch API validation failed: {e}")
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
            'max_search_results': self.max_search_results,
            'base_url': self.base_url
        }


# Global Musixmatch provider instance
_musixmatch_provider: Optional[MusixmatchLyricsProvider] = None


def get_musixmatch_provider() -> MusixmatchLyricsProvider:
    """Get global Musixmatch lyrics provider instance"""
    global _musixmatch_provider
    if not _musixmatch_provider:
        _musixmatch_provider = MusixmatchLyricsProvider()
    return _musixmatch_provider


def reset_musixmatch_provider() -> None:
    """Reset global Musixmatch lyrics provider instance"""
    global _musixmatch_provider
    _musixmatch_provider = None