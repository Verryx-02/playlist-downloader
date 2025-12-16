"""
Spotify metadata fetcher for spot-downloader (PHASE 1).

This module handles fetching track metadata from Spotify playlists
and Liked Songs. It is responsible for:
    - Fetching all tracks from a playlist URL
    - Fetching user's Liked Songs
    - Converting Spotify API responses to Track objects
    - Filtering tracks for sync mode (only new tracks)

PHASE 1 Workflow:
    1. Parse input (playlist URL or --liked flag)
    2. Fetch playlist/liked songs metadata from Spotify
    3. For each track, fetch additional artist/album data if needed
    4. Convert to Track objects
    5. Store in database
    6. Return tracks for PHASE 2

Sync Mode:
    When --sync is used, this module compares fetched tracks against
    the database and returns only tracks that are new (not already
    in the database).

Usage:
    from spot_downloader.spotify.fetcher import SpotifyFetcher
    
    fetcher = SpotifyFetcher(database)
    
    # Fetch playlist
    playlist, new_tracks = fetcher.fetch_playlist(playlist_url, sync_mode=True)
    
    # Fetch liked songs
    liked, new_tracks = fetcher.fetch_liked_songs(sync_mode=True)
"""

from typing import Any

from spot_downloader.core.database import Database
from spot_downloader.core.logger import get_logger
from spot_downloader.spotify.client import SpotifyClient
from spot_downloader.spotify.models import LikedSongs, Playlist, Track

logger = get_logger(__name__)

def _assign_track_numbers(
    tracks: list[Track],
    existing_max_number: int = 0
) -> list[Track]:
    """
    Assign track numbers based on chronological order of addition.
    
    Tracks are sorted by added_at timestamp (oldest first) and assigned
    sequential numbers. This ensures that the oldest track gets number 1
    (or existing_max + 1 in sync mode) and the newest gets the highest number.
    
    Args:
        tracks: List of Track objects with added_at field set.
        existing_max_number: Highest track number already in database.
                            New tracks will start from this + 1.
                            Use 0 for initial fetch.
    
    Returns:
        New list of Track objects with assigned_number set.
        Original Track objects are not modified (they're frozen).
    
    Note:
        Tracks without added_at are sorted to the end.
    """
    from dataclasses import replace
    
    # Sort by added_at (oldest first, None values at end)
    sorted_tracks = sorted(
        tracks,
        key=lambda t: t.added_at or "9999-99-99T99:99:99Z"
    )
    
    # Assign numbers starting from existing_max + 1
    result = []
    for i, track in enumerate(sorted_tracks):
        new_track = replace(track, assigned_number=existing_max_number + i + 1)
        result.append(new_track)
    
    return result

class SpotifyFetcher:
    """
    Fetches and processes Spotify metadata for playlists and liked songs.
    
    This class encapsulates all PHASE 1 logic:
        - Communicating with Spotify API via SpotifyClient
        - Parsing API responses into Track objects
        - Storing tracks in the database
        - Filtering for sync mode
    
    Attributes:
        _client: SpotifyClient singleton instance.
        _database: Database instance for persistent storage.
    
    Thread Safety:
        Methods are generally NOT thread-safe and should be called
        from a single thread. Database operations are thread-safe.
    
    Example:
        fetcher = SpotifyFetcher(database)
        
        # Full fetch
        playlist, tracks = fetcher.fetch_playlist(url)
        print(f"Fetched {len(tracks)} tracks from {playlist.name}")
        
        # Sync mode - only new tracks
        playlist, new_tracks = fetcher.fetch_playlist(url, sync_mode=True)
        print(f"Found {len(new_tracks)} new tracks")
    """
    
    def __init__(self, database: Database) -> None:
        """
        Initialize the SpotifyFetcher.
        
        Args:
            database: Database instance for storing fetched tracks.
        
        Raises:
            SpotifyError: If SpotifyClient has not been initialized.
        
        Note:
            SpotifyClient.init() must be called before creating a
            SpotifyFetcher instance.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def fetch_playlist(
        self,
        playlist_url: str,
        sync_mode: bool = False
    ) -> tuple[Playlist, list[Track]]:
        """
        Fetch all tracks from a Spotify playlist.
        
        This is the main entry point for PHASE 1 when processing a playlist.
        
        Args:
            playlist_url: Full Spotify playlist URL.
                         Example: "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
            sync_mode: If True, only return tracks not already in database.
                       If False, return all tracks.
        
        Returns:
            Tuple of (Playlist, list[Track]):
                - Playlist: Metadata about the playlist itself
                - list[Track]: Tracks to process in subsequent phases
                  (all tracks if sync_mode=False, only new if sync_mode=True)
        
        Raises:
            SpotifyError: If playlist not found, private without access,
                         or network error.
        
        Behavior:
            1. Fetch playlist metadata (name, description, owner)
            2. Fetch all tracks using pagination
            3. For each track:
               a. Skip if track is None (removed from Spotify)
               b. Skip if track is local file (not on Spotify)
               c. Fetch additional artist data (for genres)
               d. Fetch additional album data (for detailed metadata)
               e. Create Track object
            4. Assign track numbers using _assign_track_numbers():
               - Sort tracks by added_at (oldest first)
               - In sync_mode: get existing max from database, start from max+1
               - In full fetch: start from 1
            5. Create/update playlist entry in database
            6. Add all tracks to database
            7. If sync_mode, filter to only new tracks
            8. Return Playlist and track list
        
        Database Changes:
            - Creates playlist entry if not exists
            - Updates playlist last_synced timestamp
            - Adds all tracks (preserves existing youtube_url and downloaded status)
        
        Logging:
            - INFO: Playlist name and total track count
            - INFO: Number of new tracks (in sync mode)
            - WARNING: Skipped tracks (local files, unavailable)
            - DEBUG: Individual track processing
        
        Example:
            playlist, tracks = fetcher.fetch_playlist(
                "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                sync_mode=True
            )
            logger.info(f"Processing {len(tracks)} new tracks from {playlist.name}")
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def fetch_liked_songs(
        self,
        sync_mode: bool = False
    ) -> tuple[LikedSongs, list[Track]]:
        """
        Fetch user's Liked Songs (saved tracks).
        
        This is the main entry point for PHASE 1 when using --liked flag.
        
        Args:
            sync_mode: If True, only return tracks not already in database.
                       If False, return all tracks.
        
        Returns:
            Tuple of (LikedSongs, list[Track]):
                - LikedSongs: Container with all liked song metadata
                - list[Track]: Tracks to process in subsequent phases
        
        Raises:
            SpotifyError: If user auth not enabled.
            SpotifyError: If authentication failed or network error.
        
        Behavior:
            1. Check that user authentication is enabled
            2. Fetch all saved tracks using pagination
            3. For each saved track:
               a. Extract track data from saved track object
               b. Fetch additional artist/album data
               c. Create Track object
            4. Assign track numbers based on added_at (oldest first)
            5. Ensure liked_songs section exists in database
            6. Add all tracks to database
            7. If sync_mode, filter to only new tracks
            8. Return LikedSongs and track list
        
        Database Changes:
            - Creates liked_songs section if not exists
            - Updates liked_songs last_synced timestamp
            - Adds all tracks (preserves existing youtube_url and downloaded status)
        
        Note:
            Liked Songs requires user authentication. When --liked flag
            is used, user_auth is automatically enabled by the CLI.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _fetch_track_full_metadata(
        self,
        track_data: dict[str, Any]
    ) -> Track | None:
        """
        Fetch complete metadata for a single track.
        
        This method fetches additional artist and album data to get
        complete metadata (genres, publisher, copyright, etc.)
        
        Args:
            track_data: Track object from Spotify API
                       (from playlist_items or saved_tracks response).
        
        Returns:
            Track object with full metadata, or None if track is invalid
            (local file, unavailable, etc.)
        
        Behavior:
            1. Validate track data (not None, not local, has required fields)
            2. Extract primary artist ID
            3. Fetch artist data for genres
            4. Extract album ID
            5. Fetch album data for publisher/copyright
            6. Create and return Track object
        
        Logging:
            - DEBUG: Track being processed
            - WARNING: Invalid or skipped tracks (with reason)
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _filter_new_tracks(
        self,
        tracks: list[Track],
        playlist_id: str
    ) -> list[Track]:
        """
        Filter tracks to only those not in the database.
        
        Used in sync mode to avoid re-processing existing tracks.
        
        Args:
            tracks: List of all Track objects fetched from Spotify.
            playlist_id: Playlist ID to check against in database.
        
        Returns:
            List of Track objects that are NOT in the database yet.
        
        Behavior:
            1. Get set of existing track IDs from database
            2. Filter tracks to only those with IDs not in the set
            3. Return filtered list
        
        Performance:
            Uses set lookup for O(1) membership testing.
            Efficient even for large playlists.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _store_tracks_in_database(
        self,
        tracks: list[Track],
        playlist_id: str
    ) -> None:
        """
        Store fetched tracks in the database.
        
        Args:
            tracks: List of Track objects to store.
            playlist_id: Playlist ID (or LIKED_SONGS_KEY for liked songs).
        
        Behavior:
            - Converts each Track to database format
            - Uses batch add for efficiency
            - Preserves existing youtube_url and downloaded status
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    @staticmethod
    def _is_valid_track(track_item: dict[str, Any] | None) -> bool:
        """
        Check if a playlist track item is valid and processable.
        
        Args:
            track_item: Track item from playlist_items response.
                       May be None for removed tracks.
        
        Returns:
            True if track can be processed, False otherwise.
        
        Invalid tracks:
            - None (track removed from Spotify)
            - Local files (track['is_local'] = True)
            - Missing track object (track['track'] = None)
            - Podcast episodes (track['track']['type'] != 'track')
            - Tracks with no duration (duration_ms = 0)
        """
        raise NotImplementedError("Contract only - implementation pending")


def fetch_playlist_phase1(
    database: Database,
    playlist_url: str,
    sync_mode: bool = False
) -> tuple[Playlist, list[Track]]:
    """
    Convenience function for PHASE 1 playlist processing.
    
    This is the main entry point called by the CLI for playlist downloads.
    
    Args:
        database: Database instance.
        playlist_url: Spotify playlist URL.
        sync_mode: Whether to filter to new tracks only.
    
    Returns:
        Tuple of (Playlist, list[Track]) for subsequent phases.
    
    Raises:
        SpotifyError: If fetch fails.
    
    Example:
        playlist, tracks = fetch_playlist_phase1(db, url, sync_mode=True)
    """
    fetcher = SpotifyFetcher(database)
    return fetcher.fetch_playlist(playlist_url, sync_mode)


def fetch_liked_songs_phase1(
    database: Database,
    sync_mode: bool = False
) -> tuple[LikedSongs, list[Track]]:
    """
    Convenience function for PHASE 1 liked songs processing.
    
    This is the main entry point called by the CLI for --liked downloads.
    
    Args:
        database: Database instance.
        sync_mode: Whether to filter to new tracks only.
    
    Returns:
        Tuple of (LikedSongs, list[Track]) for subsequent phases.
    
    Raises:
        SpotifyError: If user auth not enabled or fetch fails.
    
    Example:
        liked, tracks = fetch_liked_songs_phase1(db, sync_mode=True)
    """
    fetcher = SpotifyFetcher(database)
    return fetcher.fetch_liked_songs(sync_mode)
