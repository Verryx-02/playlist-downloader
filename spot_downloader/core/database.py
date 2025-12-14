"""
Thread-safe JSON database for spot-downloader.

This module provides persistent storage for playlist and track state,
enabling features like:
    - Resume interrupted downloads
    - Sync mode (download only new tracks)
    - Track download status and metadata

Database Structure:
    The database is a JSON file with the following structure:
    
    {
        "version": 1,
        "playlists": {
            "<playlist_id>": {
                "spotify_url": "https://open.spotify.com/playlist/...",
                "name": "Playlist Name",
                "last_synced": "2024-01-15T10:30:00Z",
                "tracks": {
                    "<track_spotify_id>": {
                        "name": "Track Name",
                        "artist": "Artist Name",
                        "album": "Album Name",
                        "duration_ms": 180000,
                        "spotify_url": "https://open.spotify.com/track/...",
                        "youtube_url": "https://music.youtube.com/watch?v=...",
                        "downloaded": true,
                        "download_timestamp": "2024-01-15T10:35:00Z",
                        "file_path": "/path/to/file.m4a",
                        "metadata": { ... full spotify metadata ... }
                    }
                }
            }
        },
        "liked_songs": {
            "last_synced": "2024-01-15T10:30:00Z",
            "tracks": { ... same structure as playlist tracks ... }
        }
    }

Thread Safety:
    All public methods acquire a threading.Lock before reading or writing.
    This ensures safe concurrent access from multiple download threads.
    
File Safety:
    Writes use atomic rename pattern: write to temp file, then rename.
    This prevents corruption if the program crashes during write.

Usage:
    from spot_downloader.core.database import Database
    
    db = Database(output_dir / "database.json")
    
    # Add tracks from Spotify fetch
    db.add_playlist(playlist_id, playlist_data)
    
    # Update after YouTube match
    db.set_youtube_url(playlist_id, track_id, youtube_url)
    
    # Mark as downloaded
    db.mark_downloaded(playlist_id, track_id, file_path)
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spot_downloader.core.exceptions import DatabaseError


# Current database schema version (for future migrations)
DATABASE_VERSION = 1

# Special key for liked songs (not a real playlist ID)
LIKED_SONGS_KEY = "__liked_songs__"


class Database:
    """
    Thread-safe JSON database for persistent storage.
    
    This class manages all read/write operations to the database.json file,
    providing a clean interface for storing and retrieving playlist and
    track information.
    
    Attributes:
        db_path: Path to the database.json file.
        _lock: Threading lock for thread-safe operations.
        _data: In-memory copy of the database contents.
    
    Thread Safety:
        All public methods are thread-safe. The internal _lock is acquired
        before any read or write operation.
    
    Persistence:
        Changes are written to disk immediately after each modification.
        The _save() method uses atomic writes to prevent corruption.
    
    Example:
        db = Database(Path("/path/to/database.json"))
        
        # Check what tracks need to be downloaded
        new_tracks = db.get_tracks_without_youtube_url(playlist_id)
        
        # After matching
        db.set_youtube_url(playlist_id, track_id, youtube_url)
        
        # After download
        db.mark_downloaded(playlist_id, track_id, file_path)
    """
    
    def __init__(self, db_path: Path) -> None:
        """
        Initialize the database, loading existing data or creating new file.
        
        Args:
            db_path: Path where the database.json file is/will be stored.
                     Parent directory must exist.
        
        Raises:
            DatabaseError: If the database file exists but is corrupted,
                          or if the parent directory doesn't exist.
        
        Behavior:
            1. Store the path and create threading lock
            2. If file exists, load and validate it
            3. If file doesn't exist, create empty database structure
            4. Validate schema version matches DATABASE_VERSION
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _load(self) -> dict[str, Any]:
        """
        Load database from disk.
        
        Returns:
            The parsed JSON data as a dictionary.
        
        Raises:
            DatabaseError: If file cannot be read or contains invalid JSON.
        
        Note:
            This is an internal method. Callers must hold _lock.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _save(self) -> None:
        """
        Save database to disk using atomic write.
        
        Behavior:
            1. Serialize _data to JSON with indentation
            2. Write to temporary file (db_path.tmp)
            3. Atomic rename temp file to db_path
            4. This ensures the file is never partially written
        
        Raises:
            DatabaseError: If write fails (disk full, permissions, etc.)
        
        Note:
            This is an internal method. Callers must hold _lock.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _create_empty_database(self) -> dict[str, Any]:
        """
        Create the initial empty database structure.
        
        Returns:
            Dictionary with empty playlists and liked_songs sections.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    # =========================================================================
    # Playlist Operations
    # =========================================================================
    
    def playlist_exists(self, playlist_id: str) -> bool:
        """
        Check if a playlist exists in the database.
        
        Args:
            playlist_id: The Spotify playlist ID.
        
        Returns:
            True if the playlist exists, False otherwise.
        
        Thread Safety:
            Acquires _lock for the duration of the check.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def add_playlist(
        self,
        playlist_id: str,
        spotify_url: str,
        name: str
    ) -> None:
        """
        Add a new playlist to the database or update existing.
        
        Args:
            playlist_id: The Spotify playlist ID.
            spotify_url: Full Spotify URL for the playlist.
            name: Display name of the playlist.
        
        Behavior:
            - If playlist doesn't exist, create new entry with empty tracks
            - If playlist exists, update name and URL (preserve existing tracks)
            - Update last_synced timestamp to current UTC time
            - Save to disk
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def get_playlist_track_ids(self, playlist_id: str) -> set[str]:
        """
        Get all track IDs currently in a playlist.
        
        Args:
            playlist_id: The Spotify playlist ID.
        
        Returns:
            Set of Spotify track IDs in this playlist.
            Empty set if playlist doesn't exist.
        
        Use Case:
            Used in sync mode to compare against fresh Spotify fetch
            and determine which tracks are new.
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def get_playlist_info(self, playlist_id: str) -> dict[str, Any] | None:
        """
        Get playlist metadata (not including tracks).
        
        Args:
            playlist_id: The Spotify playlist ID.
        
        Returns:
            Dictionary with playlist info, or None if not found.
            Keys: spotify_url, name, last_synced
        
        Thread Safety:
            Acquires _lock and returns a copy of the data.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    # =========================================================================
    # Track Operations
    # =========================================================================
    
    def add_track(
        self,
        playlist_id: str,
        track_id: str,
        track_data: dict[str, Any]
    ) -> None:
        """
        Add a track to a playlist in the database.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
            track_data: Dictionary containing track information:
                - name: Track title
                - artist: Primary artist name
                - artists: List of all artist names
                - album: Album name
                - duration_ms: Duration in milliseconds
                - spotify_url: Full Spotify URL
                - isrc: International Standard Recording Code (if available)
                - cover_url: Album cover URL
                - release_date: Release date string
                - track_number: Position in album
                - metadata: Full Spotify API response (for later use)
        
        Behavior:
            - If track already exists, update metadata but preserve
              youtube_url, downloaded status, and file_path
            - If track is new, add with youtube_url=None, downloaded=False
            - Save to disk
        
        Raises:
            DatabaseError: If playlist doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def add_tracks_batch(
        self,
        playlist_id: str,
        tracks: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Add multiple tracks to a playlist in a single operation.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            tracks: List of (track_id, track_data) tuples.
                    See add_track() for track_data structure.
        
        Behavior:
            Same as add_track() but batched for efficiency.
            Only one disk write at the end.
        
        Raises:
            DatabaseError: If playlist doesn't exist.
        
        Thread Safety:
            Acquires _lock once for the entire batch.
        
        Performance:
            Use this instead of multiple add_track() calls when adding
            many tracks (e.g., after fetching a playlist from Spotify).
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def get_track(self, playlist_id: str, track_id: str) -> dict[str, Any] | None:
        """
        Get a single track's data.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
        
        Returns:
            Dictionary with track data, or None if not found.
            Returns a copy to prevent accidental modification.
        
        Thread Safety:
            Acquires _lock and returns a copy.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def get_tracks_without_youtube_url(
        self,
        playlist_id: str
    ) -> list[dict[str, Any]]:
        """
        Get all tracks that don't have a YouTube URL yet.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            List of track data dictionaries where youtube_url is None.
            Each dict includes 'track_id' key for reference.
        
        Use Case:
            Used in PHASE 2 to determine which tracks need YouTube matching.
        
        Thread Safety:
            Acquires _lock and returns copies of track data.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def get_tracks_not_downloaded(
        self,
        playlist_id: str
    ) -> list[dict[str, Any]]:
        """
        Get all tracks that have YouTube URL but aren't downloaded yet.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            List of track data dictionaries where:
            - youtube_url is not None
            - downloaded is False
            Each dict includes 'track_id' key for reference.
        
        Use Case:
            Used in PHASE 3 to determine which tracks need downloading.
        
        Thread Safety:
            Acquires _lock and returns copies of track data.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def set_youtube_url(
        self,
        playlist_id: str,
        track_id: str,
        youtube_url: str
    ) -> None:
        """
        Set the YouTube URL for a track after successful matching.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
            youtube_url: The matched YouTube Music URL.
        
        Behavior:
            - Update the track's youtube_url field
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def mark_downloaded(
        self,
        playlist_id: str,
        track_id: str,
        file_path: Path
    ) -> None:
        """
        Mark a track as successfully downloaded.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
            file_path: Absolute path to the downloaded M4A file.
        
        Behavior:
            - Set downloaded = True
            - Set file_path to the provided path (as string)
            - Set download_timestamp to current UTC time
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def mark_youtube_match_failed(
        self,
        playlist_id: str,
        track_id: str
    ) -> None:
        """
        Mark a track as failed to match on YouTube.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
        
        Behavior:
            - Set youtube_url = "" (empty string, not None)
            - This distinguishes "not yet matched" from "match failed"
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        
        Note:
            Tracks with youtube_url = "" will NOT be returned by
            get_tracks_without_youtube_url() (which checks for None).
            This prevents repeatedly trying to match unmatchable tracks.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    # =========================================================================
    # Liked Songs Operations
    # =========================================================================
    
    def ensure_liked_songs_exists(self) -> None:
        """
        Ensure the liked_songs section exists in the database.
        
        Behavior:
            - If liked_songs section doesn't exist, create it
            - Initialize with empty tracks dict and current timestamp
            - Save to disk
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def get_liked_songs_track_ids(self) -> set[str]:
        """
        Get all track IDs in the liked songs section.
        
        Returns:
            Set of Spotify track IDs in liked songs.
            Empty set if liked_songs section doesn't exist.
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_playlist_stats(self, playlist_id: str) -> dict[str, int]:
        """
        Get download statistics for a playlist.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            Dictionary with counts:
            - total: Total number of tracks
            - matched: Tracks with youtube_url (not None and not "")
            - downloaded: Tracks with downloaded=True
            - failed_match: Tracks with youtube_url="" (match failed)
            - pending_match: Tracks with youtube_url=None
            - pending_download: Tracks matched but not downloaded
        
        Thread Safety:
            Acquires _lock and computes stats from current data.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    # =========================================================================
    # Utility
    # =========================================================================
    
    def get_next_track_number(self, playlist_id: str) -> int:
        """
        Get the next track number for file naming.
        
        The track number is based on download order, not playlist position.
        Tracks downloaded earlier get lower numbers.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            The next track number to use (1-indexed).
            This is max(existing_numbers) + 1, or 1 if no tracks downloaded.
        
        Behavior:
            - Examines all tracks with downloaded=True
            - Finds the highest track number from file names
            - Returns that number + 1
            - If no tracks downloaded, returns 1
        
        Thread Safety:
            Acquires _lock for the duration of the calculation.
        
        Note:
            Track numbers are embedded in filenames: {num}-{title}-{artist}.m4a
            This method parses existing filenames to determine the next number.
        """
        raise NotImplementedError("Contract only - implementation pending")
