"""
Spotify API client for playlist extraction and metadata retrieval
Handles pagination, rate limiting, and data conversion to internal models
"""

import re
import time
from typing import List, Optional, Dict, Any, Generator, Tuple
from urllib.parse import urlparse, parse_qs
import spotipy
from spotipy.exceptions import SpotifyException

from ..config.auth import get_auth
from ..config.settings import get_settings
from .models import SpotifyPlaylist, SpotifyTrack, PlaylistTrack
from ..utils.logger import get_logger


class SpotifyClient:
    """Spotify API client wrapper"""
    
    def __init__(self):
        """Initialize Spotify client"""
        self.auth = get_auth()
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self._client: Optional[spotipy.Spotify] = None
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
    
    @property
    def client(self) -> spotipy.Spotify:
        """Get authenticated Spotify client"""
        if not self._client or not self.auth.is_authenticated():
            self._client = self.auth.get_spotify_client()
            if not self._client:
                raise Exception("Failed to authenticate with Spotify")
        return self._client
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, func, *args, **kwargs) -> Any:
        """Make rate-limited API request with error handling"""
        self._rate_limit()
        
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 401:
                # Token expired, try to refresh (no warning to console)
                self.logger.debug("Spotify token expired, attempting refresh...")
                self._client = self.auth.get_spotify_client()
                if self._client:
                    self._rate_limit()
                    return func(*args, **kwargs)
                else:
                    raise Exception("Failed to refresh Spotify token")
            elif e.http_status == 429:
                # Rate limited
                retry_after = int(e.headers.get('Retry-After', 1))
                self.logger.warning(f"Rate limited, waiting {retry_after} seconds...")
                time.sleep(retry_after)
                self._rate_limit()
                return func(*args, **kwargs)
            else:
                raise e
    
    def extract_playlist_id(self, url_or_id: str) -> str:
        """
        Extract playlist ID from Spotify URL or return ID if already provided
        
        Args:
            url_or_id: Spotify playlist URL or ID
            
        Returns:
            Playlist ID
            
        Raises:
            ValueError: If URL format is invalid
        """
        # If it's already a playlist ID (no slashes or special chars)
        if re.match(r'^[a-zA-Z0-9]{22}$', url_or_id):
            return url_or_id
        
        # Parse Spotify URL
        if 'spotify.com' in url_or_id:
            # Handle web URLs: https://open.spotify.com/playlist/ID?si=...
            if 'playlist/' in url_or_id:
                playlist_id = url_or_id.split('playlist/')[-1].split('?')[0]
                return playlist_id
        elif url_or_id.startswith('spotify:'):
            # Handle Spotify URIs: spotify:playlist:ID
            parts = url_or_id.split(':')
            if len(parts) >= 3 and parts[1] == 'playlist':
                return parts[2]
        
        raise ValueError(f"Invalid Spotify playlist URL or ID: {url_or_id}")
    
    def get_playlist_info(self, playlist_id: str) -> SpotifyPlaylist:
        """
        Get playlist information without tracks
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            SpotifyPlaylist object with basic info
        """
        self.logger.info(f"Fetching playlist info for {playlist_id}")
        
        try:
            playlist_data = self._make_request(self.client.playlist, playlist_id, fields='id,name,description,owner,public,collaborative,tracks(total),external_urls,href,uri,images,followers,snapshot_id')
            
            playlist = SpotifyPlaylist.from_spotify_data(playlist_data)
            
            self.logger.info(f"Retrieved playlist: '{playlist.name}' by {playlist.owner_name} ({playlist.total_tracks} tracks)")
            
            return playlist
            
        except Exception as e:
            self.logger.error(f"Failed to fetch playlist {playlist_id}: {e}")
            raise Exception(f"Failed to fetch playlist information: {e}")
    
    def get_playlist_tracks(self, playlist_id: str, limit: int = 100) -> Generator[Tuple[SpotifyTrack, int, str], None, None]:
        """
        Get all tracks from a playlist with pagination
        
        Args:
            playlist_id: Spotify playlist ID
            limit: Number of tracks per request (max 100)
            
        Yields:
            Tuple of (SpotifyTrack, position, added_at)
        """
        self.logger.info(f"Fetching tracks for playlist {playlist_id}")
        
        offset = 0
        position = 1
        
        while True:
            try:
                # Fetch batch of tracks
                results = self._make_request(
                    self.client.playlist_tracks,
                    playlist_id,
                    offset=offset,
                    limit=limit,
                    fields='items(added_at,track(id,name,artists,album,duration_ms,explicit,popularity,track_number,disc_number,external_urls,external_ids,href,uri,preview_url,is_local,is_playable)),next,total'
                )
                
                items = results.get('items', [])
                if not items:
                    break
                
                for item in items:
                    track_data = item.get('track')
                    if not track_data or not track_data.get('id'):
                        # Skip tracks that are no longer available
                        self.logger.warning(f"Skipping unavailable track at position {position}")
                        position += 1
                        continue
                    
                    try:
                        spotify_track = SpotifyTrack.from_spotify_data(item)
                        added_at = item.get('added_at', '')
                        
                        yield spotify_track, position, added_at
                        position += 1
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to parse track at position {position}: {e}")
                        position += 1
                        continue
                
                # Check if there are more tracks
                if not results.get('next'):
                    break
                
                offset += limit
                
                # Progress logging
                if offset % 500 == 0:
                    self.logger.info(f"Fetched {offset} tracks...")
                
            except Exception as e:
                self.logger.error(f"Failed to fetch tracks at offset {offset}: {e}")
                raise Exception(f"Failed to fetch playlist tracks: {e}")
        
        self.logger.info(f"Finished fetching tracks, total: {position - 1}")
    
    def get_full_playlist(self, playlist_id: str) -> SpotifyPlaylist:
        """
        Get complete playlist with all tracks
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            Complete SpotifyPlaylist object with all tracks
        """
        # Get basic playlist info
        playlist = self.get_playlist_info(playlist_id)
        
        # Get all tracks
        tracks_fetched = 0
        for spotify_track, position, added_at in self.get_playlist_tracks(playlist_id):
            playlist_track = playlist.add_track(spotify_track, position, added_at)
            tracks_fetched += 1
            
            # Progress update for large playlists
            if tracks_fetched % 100 == 0:
                self.logger.info(f"Added {tracks_fetched}/{playlist.total_tracks} tracks to playlist")
        
        self.logger.info(f"Complete playlist loaded: {len(playlist.tracks)} tracks")
        
        return playlist
    
    def get_track_info(self, track_id: str) -> Optional[SpotifyTrack]:
        """
        Get detailed information for a single track
        
        Args:
            track_id: Spotify track ID
            
        Returns:
            SpotifyTrack object or None if not found
        """
        try:
            track_data = self._make_request(self.client.track, track_id)
            return SpotifyTrack.from_spotify_data({'track': track_data})
        except Exception as e:
            self.logger.warning(f"Failed to fetch track {track_id}: {e}")
            return None
    
    def get_multiple_tracks(self, track_ids: List[str]) -> List[Optional[SpotifyTrack]]:
        """
        Get multiple tracks efficiently using batch API
        
        Args:
            track_ids: List of Spotify track IDs (max 50)
            
        Returns:
            List of SpotifyTrack objects (None for unavailable tracks)
        """
        if len(track_ids) > 50:
            raise ValueError("Maximum 50 track IDs per request")
        
        try:
            tracks_data = self._make_request(self.client.tracks, track_ids)
            tracks = []
            
            for track_data in tracks_data.get('tracks', []):
                if track_data:
                    tracks.append(SpotifyTrack.from_spotify_data({'track': track_data}))
                else:
                    tracks.append(None)
            
            return tracks
            
        except Exception as e:
            self.logger.error(f"Failed to fetch multiple tracks: {e}")
            return [None] * len(track_ids)
    
    def search_tracks(self, query: str, limit: int = 20) -> List[SpotifyTrack]:
        """
        Search for tracks using Spotify search API
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of SpotifyTrack objects
        """
        try:
            results = self._make_request(
                self.client.search,
                q=query,
                type='track',
                limit=limit
            )
            
            tracks = []
            for track_data in results.get('tracks', {}).get('items', []):
                tracks.append(SpotifyTrack.from_spotify_data({'track': track_data}))
            
            return tracks
            
        except Exception as e:
            self.logger.error(f"Failed to search tracks: {e}")
            return []
    
    def get_user_playlists(self, user_id: Optional[str] = None, limit: int = 50) -> List[SpotifyPlaylist]:
        """
        Get user's playlists
        
        Args:
            user_id: Spotify user ID (None for current user)
            limit: Maximum number of playlists
            
        Returns:
            List of SpotifyPlaylist objects (without tracks)
        """
        try:
            if user_id:
                results = self._make_request(self.client.user_playlists, user_id, limit=limit)
            else:
                results = self._make_request(self.client.current_user_playlists, limit=limit)
            
            playlists = []
            for playlist_data in results.get('items', []):
                playlists.append(SpotifyPlaylist.from_spotify_data(playlist_data))
            
            return playlists
            
        except Exception as e:
            self.logger.error(f"Failed to fetch user playlists: {e}")
            return []
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get current user information
        
        Returns:
            User information dictionary
        """
        try:
            return self._make_request(self.client.current_user)
        except Exception as e:
            self.logger.error(f"Failed to get current user: {e}")
            return None
    
    def validate_playlist_access(self, playlist_id: str) -> bool:
        """
        Check if playlist is accessible with current token
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            True if accessible
        """
        try:
            self._make_request(self.client.playlist, playlist_id, fields='id')
            return True
        except Exception as e:
            self.logger.warning(f"Playlist {playlist_id} not accessible: {e}")
            return False
    
    def check_tracks_availability(self, track_ids: List[str]) -> Dict[str, bool]:
        """
        Check availability of multiple tracks
        
        Args:
            track_ids: List of Spotify track IDs
            
        Returns:
            Dictionary mapping track_id to availability status
        """
        availability = {}
        
        # Process in batches of 50
        for i in range(0, len(track_ids), 50):
            batch = track_ids[i:i+50]
            tracks = self.get_multiple_tracks(batch)
            
            for track_id, track in zip(batch, tracks):
                availability[track_id] = track is not None and track.is_playable
        
        return availability
    
    def get_album_tracks(self, album_id: str) -> List[SpotifyTrack]:
        """
        Get all tracks from an album
        
        Args:
            album_id: Spotify album ID
            
        Returns:
            List of SpotifyTrack objects
        """
        try:
            results = self._make_request(self.client.album_tracks, album_id)
            tracks = []
            
            for track_data in results.get('items', []):
                # Album tracks need album info added
                full_track = self._make_request(self.client.track, track_data['id'])
                tracks.append(SpotifyTrack.from_spotify_data({'track': full_track}))
            
            return tracks
            
        except Exception as e:
            self.logger.error(f"Failed to fetch album tracks: {e}")
            return []


# Global client instance
_client_instance: Optional[SpotifyClient] = None


def get_spotify_client() -> SpotifyClient:
    """Get global Spotify client instance"""
    global _client_instance
    if not _client_instance:
        _client_instance = SpotifyClient()
    return _client_instance


def reset_spotify_client() -> None:
    """Reset global Spotify client instance"""
    global _client_instance
    _client_instance = None

def validate_playlist_url(self, url_or_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and extract playlist ID from URL
    
    Args:
        url_or_id: Spotify playlist URL or ID
        
    Returns:
        Tuple of (is_valid, playlist_id, error_message)
    """
    try:
        # Use existing extraction logic but with better error handling
        playlist_id = self.extract_playlist_id(url_or_id)
        
        # Additional validation: check if playlist exists and is accessible
        try:
            playlist_info = self.get_playlist_info(playlist_id)
            return True, playlist_id, None
        except Exception as e:
            if "not found" in str(e).lower():
                return False, None, "Playlist not found or is private"
            else:
                return False, None, f"Cannot access playlist: {e}"
                
    except ValueError as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, f"Unexpected error: {e}"