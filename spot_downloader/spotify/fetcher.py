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
    3. Batch fetch additional artist/album data for all tracks
    4. Convert to Track objects
    5. Store in database
    6. Return tracks for PHASE 2

Sync Mode:
    When --sync is used, this module compares fetched tracks against
    the database and returns only tracks that are new (not already
    in the database).

Batch Optimization:
    Instead of making N+2 API calls per track (1 artist + 1 album),
    this module collects unique artist and album IDs and fetches them
    in batches:
    - Artists: up to 50 per request
    - Albums: up to 20 per request
    
    For 100 tracks with 50 unique artists and 40 unique albums:
    - Old approach: 200+ API calls
    - Batch approach: ~4 API calls

Usage:
    from spot_downloader.spotify.fetcher import SpotifyFetcher
    
    fetcher = SpotifyFetcher(database)
    
    # Fetch playlist
    playlist, new_tracks = fetcher.fetch_playlist(playlist_url, sync_mode=True)
    
    # Fetch liked songs
    liked, new_tracks = fetcher.fetch_liked_songs(sync_mode=True)
"""

from dataclasses import replace
from typing import Any

from spot_downloader.core.database import Database, LIKED_SONGS_KEY
from spot_downloader.core.exceptions import SpotifyError
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
        if not SpotifyClient.is_initialized():
            raise SpotifyError(
                "SpotifyClient not initialized. Call SpotifyClient.init() first.",
                is_auth_error=True
            )
        
        self._client = SpotifyClient()
        self._database = database
    
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
        """
        logger.info(f"Fetching playlist: {playlist_url}")
        
        # 1. Fetch playlist metadata
        playlist_data = self._client.playlist(playlist_url)
        playlist_id = playlist_data["id"]
        playlist_name = playlist_data.get("name", "Unknown Playlist")
        
        logger.info(f"Playlist: {playlist_name}")
        
        # 2. Fetch all track items
        track_items = self._client.playlist_all_items(playlist_url)
        logger.info(f"Found {len(track_items)} track items")
        
        # 3. Filter valid tracks and collect IDs for batch fetching
        valid_items: list[dict[str, Any]] = []
        artist_ids: set[str] = set()
        album_ids: set[str] = set()
        skipped_count = 0
        
        for item in track_items:
            if not self._is_valid_track(item):
                skipped_count += 1
                continue
            
            track_data = item["track"]
            valid_items.append(item)
            
            # Collect primary artist ID (for genres)
            if track_data.get("artists"):
                artist_id = track_data["artists"][0].get("id")
                if artist_id:
                    artist_ids.add(artist_id)
            
            # Collect album ID (for publisher/copyright)
            album_id = track_data.get("album", {}).get("id")
            if album_id:
                album_ids.add(album_id)
        
        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} invalid tracks (local files, unavailable, etc.)")
        
        logger.debug(f"Unique artists to fetch: {len(artist_ids)}")
        logger.debug(f"Unique albums to fetch: {len(album_ids)}")
        
        # 4. Batch fetch artists for genres
        artist_map: dict[str, dict[str, Any]] = {}
        if artist_ids:
            logger.debug("Batch fetching artist data for genres...")
            artist_list = list(artist_ids)
            artists_data = self._client.artists(artist_list)
            for artist_data in artists_data:
                if artist_data:
                    artist_map[artist_data["id"]] = artist_data
        
        # 5. Batch fetch albums for publisher/copyright
        album_map: dict[str, dict[str, Any]] = {}
        if album_ids:
            logger.debug("Batch fetching album data for metadata...")
            album_list = list(album_ids)
            albums_data = self._client.albums(album_list)
            for album_data in albums_data:
                if album_data:
                    album_map[album_data["id"]] = album_data
        
        # 6. Create Track objects with full metadata
        tracks: list[Track] = []
        for item in valid_items:
            track_data = item["track"]
            added_at = item.get("added_at")
            
            # Get artist data for this track
            artist_data = None
            if track_data.get("artists"):
                primary_artist_id = track_data["artists"][0].get("id")
                if primary_artist_id:
                    artist_data = artist_map.get(primary_artist_id)
            
            # Get album data for this track
            album_data = None
            album_id = track_data.get("album", {}).get("id")
            if album_id:
                album_data = album_map.get(album_id)
            
            track = Track.from_spotify_api(
                track_data=track_data,
                artist_data=artist_data,
                album_data=album_data,
                added_at=added_at
            )
            tracks.append(track)
            logger.debug(f"Processed: {track.artist} - {track.name}")
        
        logger.info(f"Successfully parsed {len(tracks)} tracks")
        
        # 7. Assign track numbers
        if sync_mode:
            existing_max = self._database.get_max_assigned_number(playlist_id)
        else:
            existing_max = 0
        
        tracks = _assign_track_numbers(tracks, existing_max)
        
        # 8. Create/update playlist in database
        self._database.add_playlist(
            playlist_id=playlist_id,
            spotify_url=playlist_data.get("external_urls", {}).get("spotify", playlist_url),
            name=playlist_name
        )
        
        # 9. Store tracks in database
        self._store_tracks_in_database(tracks, playlist_id)
        
        # 10. Filter for sync mode if needed
        if sync_mode:
            tracks = self._filter_new_tracks(tracks, playlist_id)
            logger.info(f"Sync mode: {len(tracks)} new tracks to process")
        
        # 11. Create Playlist object
        playlist = Playlist.from_spotify_api(playlist_data, tracks)
        
        return playlist, tracks
    
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
        """
        logger.info("Fetching Liked Songs...")
        
        # Check user auth
        if not self._client.has_user_auth:
            raise SpotifyError(
                "User authentication required to access Liked Songs. "
                "Initialize SpotifyClient with user_auth=True.",
                is_auth_error=True
            )
        
        # 1. Fetch all saved tracks
        saved_items = self._client.current_user_all_saved_tracks()
        total_count = len(saved_items)
        logger.info(f"Found {total_count} liked songs")
        
        # 2. Filter valid tracks and collect IDs for batch fetching
        valid_items: list[dict[str, Any]] = []
        artist_ids: set[str] = set()
        album_ids: set[str] = set()
        skipped_count = 0
        
        for item in saved_items:
            if not self._is_valid_track(item):
                skipped_count += 1
                continue
            
            track_data = item["track"]
            valid_items.append(item)
            
            # Collect primary artist ID
            if track_data.get("artists"):
                artist_id = track_data["artists"][0].get("id")
                if artist_id:
                    artist_ids.add(artist_id)
            
            # Collect album ID
            album_id = track_data.get("album", {}).get("id")
            if album_id:
                album_ids.add(album_id)
        
        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} invalid tracks")
        
        # 3. Batch fetch artists
        artist_map: dict[str, dict[str, Any]] = {}
        if artist_ids:
            logger.debug("Batch fetching artist data...")
            artists_data = self._client.artists(list(artist_ids))
            for artist_data in artists_data:
                if artist_data:
                    artist_map[artist_data["id"]] = artist_data
        
        # 4. Batch fetch albums
        album_map: dict[str, dict[str, Any]] = {}
        if album_ids:
            logger.debug("Batch fetching album data...")
            albums_data = self._client.albums(list(album_ids))
            for album_data in albums_data:
                if album_data:
                    album_map[album_data["id"]] = album_data
        
        # 5. Create Track objects
        tracks: list[Track] = []
        for item in valid_items:
            track_data = item["track"]
            added_at = item.get("added_at")
            
            artist_data = None
            if track_data.get("artists"):
                primary_artist_id = track_data["artists"][0].get("id")
                if primary_artist_id:
                    artist_data = artist_map.get(primary_artist_id)
            
            album_data = None
            album_id = track_data.get("album", {}).get("id")
            if album_id:
                album_data = album_map.get(album_id)
            
            track = Track.from_spotify_api(
                track_data=track_data,
                artist_data=artist_data,
                album_data=album_data,
                added_at=added_at
            )
            tracks.append(track)
        
        logger.info(f"Successfully parsed {len(tracks)} tracks")
        
        # 6. Assign track numbers
        if sync_mode:
            existing_max = self._database.get_max_assigned_number(LIKED_SONGS_KEY)
        else:
            existing_max = 0
        
        tracks = _assign_track_numbers(tracks, existing_max)
        
        # 7. Ensure liked_songs section exists in database
        self._database.ensure_liked_songs_exists()
        
        # 8. Store tracks in database
        self._store_tracks_in_database(tracks, LIKED_SONGS_KEY)
        
        # 9. Filter for sync mode
        if sync_mode:
            tracks = self._filter_new_tracks(tracks, LIKED_SONGS_KEY)
            logger.info(f"Sync mode: {len(tracks)} new tracks to process")
        
        # 10. Create LikedSongs object
        liked_songs = LikedSongs.from_spotify_api(tracks, total_count)
        
        return liked_songs, tracks
    
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
        if playlist_id == LIKED_SONGS_KEY:
            existing_ids = self._database.get_liked_songs_track_ids()
        else:
            existing_ids = self._database.get_playlist_track_ids(playlist_id)
        
        new_tracks = [t for t in tracks if t.spotify_id not in existing_ids]
        return new_tracks
    
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
            - Deduplicates tracks by spotify_id (keeps first occurrence)
            - Converts each Track to database format
            - Uses batch add for efficiency
            - Preserves existing youtube_url and downloaded status
        """
        if not tracks:
            return
        
        # Deduplicate tracks by spotify_id (keep first occurrence)
        seen_ids: set[str] = set()
        unique_tracks: list[Track] = []
        duplicate_count = 0
        
        for track in tracks:
            if track.spotify_id not in seen_ids:
                seen_ids.add(track.spotify_id)
                unique_tracks.append(track)
            else:
                duplicate_count += 1
        
        if duplicate_count > 0:
            logger.warning(
                f"Skipped {duplicate_count} duplicate tracks in playlist "
                f"(same song added multiple times)"
            )
        
        # Build batch data from unique tracks
        batch_data: list[tuple[str, dict[str, Any]]] = []
        for track in unique_tracks:
            batch_data.append((track.spotify_id, track.to_database_dict()))
        
        self._database.add_tracks_batch(playlist_id, batch_data)
        logger.debug(f"Stored {len(unique_tracks)} tracks in database")
    
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
            - Tracks with empty name
        """
        # None item
        if track_item is None:
            return False
        
        # Check if it's a dict
        if not isinstance(track_item, dict):
            return False
        
        # Check for track object
        track = track_item.get("track")
        if track is None:
            return False
        
        # Local file check
        if track.get("is_local", False):
            return False
        
        # Type check (must be 'track', not 'episode')
        if track.get("type") != "track":
            return False
        
        # Must have ID
        if not track.get("id"):
            return False
        
        # Must have duration
        if track.get("duration_ms", 0) == 0:
            return False
        
        # Must have name (not empty)
        if not track.get("name", "").strip():
            return False
        
        return True


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