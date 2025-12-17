"""
Thread-safe JSON database for spot-downloader.

This module provides persistent storage for playlist and track state,
enabling features like:
    - Resume interrupted downloads
    - Sync mode (download only new tracks)
    - Track download status and metadata
    - Track lyrics fetch status
    - Track metadata embedding status

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
                        "lyrics_fetched": true,
                        "lyrics_text": "[00:15.00]First line...",
                        "lyrics_synced": true,
                        "lyrics_source": "synced",
                        "metadata_embedded": true,
                        "lyrics_embedded": true,
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

New Fields:
    lyrics_fetched: bool - True if we attempted to fetch lyrics (success or not)
    lyrics_text: str|null - The lyrics text, or null if not found
    lyrics_synced: bool - True if lyrics are in LRC format with timestamps
    lyrics_source: str|null - Provider name ("synced", "genius", etc.) or null
    metadata_embedded: bool - True if metadata has been written to the M4A file
    lyrics_embedded: bool - True if lyrics have been written to the M4A file

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

# Special value for youtube_url when match failed (distinguishes from None = not yet matched)
YOUTUBE_MATCH_FAILED = "MATCH_FAILED"


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
        self.db_path = db_path
        self._lock = threading.Lock()
        
        # Check parent directory exists
        if not db_path.parent.exists():
            raise DatabaseError(
                f"Parent directory does not exist: {db_path.parent}",
                details={"path": str(db_path.parent)}
            )
        
        # Load existing or create new
        if db_path.exists():
            self._data = self._load()
            # Validate version
            if self._data.get("version") != DATABASE_VERSION:
                stored_version = self._data.get("version", "unknown")
                raise DatabaseError(
                    f"Database version mismatch: expected {DATABASE_VERSION}, got {stored_version}",
                    details={"expected": DATABASE_VERSION, "actual": stored_version}
                )
        else:
            self._data = self._create_empty_database()
            self._save()
    
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
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise DatabaseError(
                f"Database file contains invalid JSON: {e}",
                details={"path": str(self.db_path), "original_error": str(e)}
            ) from e
        except IOError as e:
            raise DatabaseError(
                f"Failed to read database file: {e}",
                details={"path": str(self.db_path), "original_error": str(e)}
            ) from e
    
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
        temp_path = self.db_path.with_suffix(".tmp")
        
        try:
            # Write to temp file
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_path.replace(self.db_path)
        except IOError as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise DatabaseError(
                f"Failed to save database: {e}",
                details={"path": str(self.db_path), "original_error": str(e)}
            ) from e
    
    def _create_empty_database(self) -> dict[str, Any]:
        """
        Create the initial empty database structure.
        
        Returns:
            Dictionary with empty playlists and liked_songs sections.
        """
        return {
            "version": DATABASE_VERSION,
            "playlists": {},
            "liked_songs": None  # Will be created on first use
        }
    
    def _get_tracks_container(self, playlist_id: str) -> dict[str, Any] | None:
        """
        Get the container (playlist or liked_songs) for a given ID.
        
        Internal helper to abstract playlist vs liked_songs handling.
        
        Args:
            playlist_id: The playlist ID or LIKED_SONGS_KEY.
        
        Returns:
            The container dict with 'tracks' key, or None if not found.
        """
        if playlist_id == LIKED_SONGS_KEY:
            return self._data.get("liked_songs")
        else:
            return self._data.get("playlists", {}).get(playlist_id)
    
    def _now_iso(self) -> str:
        """Get current UTC time as ISO format string."""
        return datetime.now(timezone.utc).isoformat()
    
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
        with self._lock:
            return playlist_id in self._data.get("playlists", {})
    
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
        with self._lock:
            playlists = self._data.setdefault("playlists", {})
            
            if playlist_id in playlists:
                # Update existing
                playlists[playlist_id]["spotify_url"] = spotify_url
                playlists[playlist_id]["name"] = name
                playlists[playlist_id]["last_synced"] = self._now_iso()
            else:
                # Create new
                playlists[playlist_id] = {
                    "spotify_url": spotify_url,
                    "name": name,
                    "last_synced": self._now_iso(),
                    "tracks": {}
                }
            
            self._save()
    
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
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return set()
            return set(container.get("tracks", {}).keys())
    
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
        with self._lock:
            playlist = self._data.get("playlists", {}).get(playlist_id)
            if playlist is None:
                return None
            return {
                "spotify_url": playlist.get("spotify_url"),
                "name": playlist.get("name"),
                "last_synced": playlist.get("last_synced")
            }
    
    def get_active_playlist_id(self) -> str | None:
        """
        Get the most recently synced playlist ID.
        
        Used when running phases 2-5 without --url to determine
        which playlist to process.
        
        Returns:
            The playlist_id with the most recent last_synced timestamp,
            or None if no playlists exist in the database.
        
        Behavior:
            1. Iterate through all playlists (including LIKED_SONGS_KEY if present)
            2. Compare last_synced timestamps
            3. Return the playlist_id with the newest timestamp
            4. If database has no playlists, return None
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        
        Use Case:
            When user runs `spot --2` or `spot --3` without specifying
            --url or --liked, this method determines which playlist
            to continue processing.
        
        Example:
            playlist_id = database.get_active_playlist_id()
            if playlist_id is None:
                raise click.UsageError("No playlist in database. Run --1 first.")
        """
        with self._lock:
            most_recent_id = None
            most_recent_time = ""
            
            # Check playlists
            for playlist_id, playlist_data in self._data.get("playlists", {}).items():
                last_synced = playlist_data.get("last_synced", "")
                if last_synced > most_recent_time:
                    most_recent_time = last_synced
                    most_recent_id = playlist_id
            
            # Check liked_songs
            liked = self._data.get("liked_songs")
            if liked is not None:
                last_synced = liked.get("last_synced", "")
                if last_synced > most_recent_time:
                    most_recent_time = last_synced
                    most_recent_id = LIKED_SONGS_KEY
            
            return most_recent_id
    
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
                - assigned_number: Track number for file naming
                - added_at: When track was added to playlist
                - metadata: Full Spotify API response (for later use)
        
        Behavior:
            - If track already exists, update metadata but preserve:
              youtube_url, downloaded, file_path, download_timestamp,
              lyrics_fetched, lyrics_text, lyrics_synced, lyrics_source,
              metadata_embedded, lyrics_embedded
            - If track is new, add with:
              youtube_url=None, downloaded=False, file_path=None,
              lyrics_fetched=False, lyrics_text=None, lyrics_synced=False,
              lyrics_source=None, metadata_embedded=False, lyrics_embedded=False
            - Save to disk
        
        Raises:
            DatabaseError: If playlist doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.setdefault("tracks", {})
            
            if track_id in tracks:
                # Update existing - preserve download state
                existing = tracks[track_id]
                track_data["youtube_url"] = existing.get("youtube_url")
                track_data["downloaded"] = existing.get("downloaded", False)
                track_data["file_path"] = existing.get("file_path")
                track_data["download_timestamp"] = existing.get("download_timestamp")
                track_data["lyrics_fetched"] = existing.get("lyrics_fetched", False)
                track_data["lyrics_text"] = existing.get("lyrics_text")
                track_data["lyrics_synced"] = existing.get("lyrics_synced", False)
                track_data["lyrics_source"] = existing.get("lyrics_source")
                track_data["metadata_embedded"] = existing.get("metadata_embedded", False)
                track_data["lyrics_embedded"] = existing.get("lyrics_embedded", False)
            else:
                # New track - initialize download fields
                track_data["youtube_url"] = None
                track_data["downloaded"] = False
                track_data["file_path"] = None
                track_data["download_timestamp"] = None
                track_data["lyrics_fetched"] = False
                track_data["lyrics_text"] = None
                track_data["lyrics_synced"] = False
                track_data["lyrics_source"] = None
                track_data["metadata_embedded"] = False
                track_data["lyrics_embedded"] = False
            
            tracks[track_id] = track_data
            self._save()
    
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
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks_dict = container.setdefault("tracks", {})
            
            for track_id, track_data in tracks:
                if track_id in tracks_dict:
                    # Update existing - preserve download state
                    existing = tracks_dict[track_id]
                    track_data["youtube_url"] = existing.get("youtube_url")
                    track_data["downloaded"] = existing.get("downloaded", False)
                    track_data["file_path"] = existing.get("file_path")
                    track_data["download_timestamp"] = existing.get("download_timestamp")
                    track_data["lyrics_fetched"] = existing.get("lyrics_fetched", False)
                    track_data["lyrics_text"] = existing.get("lyrics_text")
                    track_data["lyrics_synced"] = existing.get("lyrics_synced", False)
                    track_data["lyrics_source"] = existing.get("lyrics_source")
                    track_data["metadata_embedded"] = existing.get("metadata_embedded", False)
                    track_data["lyrics_embedded"] = existing.get("lyrics_embedded", False)
                else:
                    # New track - initialize download fields
                    track_data["youtube_url"] = None
                    track_data["downloaded"] = False
                    track_data["file_path"] = None
                    track_data["download_timestamp"] = None
                    track_data["lyrics_fetched"] = False
                    track_data["lyrics_text"] = None
                    track_data["lyrics_synced"] = False
                    track_data["lyrics_source"] = None
                    track_data["metadata_embedded"] = False
                    track_data["lyrics_embedded"] = False
                
                tracks_dict[track_id] = track_data
            
            self._save()
    
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
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return None
            track = container.get("tracks", {}).get(track_id)
            if track is None:
                return None
            return dict(track)  # Return a copy
    
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
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return []
            
            result = []
            for track_id, track_data in container.get("tracks", {}).items():
                if track_data.get("youtube_url") is None:
                    track_copy = dict(track_data)
                    track_copy["track_id"] = track_id
                    result.append(track_copy)
            
            return result
    
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
            - youtube_url is not None and not YOUTUBE_MATCH_FAILED
            - downloaded is False
            Each dict includes 'track_id' key for reference.
        
        Use Case:
            Used in PHASE 3 to determine which tracks need downloading.
        
        Thread Safety:
            Acquires _lock and returns copies of track data.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return []
            
            result = []
            for track_id, track_data in container.get("tracks", {}).items():
                youtube_url = track_data.get("youtube_url")
                if (youtube_url is not None 
                    and youtube_url != YOUTUBE_MATCH_FAILED
                    and not track_data.get("downloaded", False)):
                    track_copy = dict(track_data)
                    track_copy["track_id"] = track_id
                    result.append(track_copy)
            
            return result
    
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
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.get("tracks", {})
            if track_id not in tracks:
                raise DatabaseError(
                    f"Track not found: {track_id}",
                    details={"playlist_id": playlist_id, "track_id": track_id}
                )
            
            tracks[track_id]["youtube_url"] = youtube_url
            self._save()
    
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
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.get("tracks", {})
            if track_id not in tracks:
                raise DatabaseError(
                    f"Track not found: {track_id}",
                    details={"playlist_id": playlist_id, "track_id": track_id}
                )
            
            tracks[track_id]["downloaded"] = True
            tracks[track_id]["file_path"] = str(file_path)
            tracks[track_id]["download_timestamp"] = self._now_iso()
            self._save()
    
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
            - Set youtube_url = YOUTUBE_MATCH_FAILED
            - This distinguishes "not yet matched" (None) from "match failed"
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        
        Note:
            Tracks with youtube_url = YOUTUBE_MATCH_FAILED will NOT be
            returned by get_tracks_without_youtube_url() (which checks for None).
            This prevents repeatedly trying to match unmatchable tracks.
        
        See Also:
            YOUTUBE_MATCH_FAILED: The constant value used to mark failures.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.get("tracks", {})
            if track_id not in tracks:
                raise DatabaseError(
                    f"Track not found: {track_id}",
                    details={"playlist_id": playlist_id, "track_id": track_id}
                )
            
            tracks[track_id]["youtube_url"] = YOUTUBE_MATCH_FAILED
            self._save()
    
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
        with self._lock:
            if self._data.get("liked_songs") is None:
                self._data["liked_songs"] = {
                    "last_synced": self._now_iso(),
                    "tracks": {}
                }
                self._save()
            else:
                # Update last_synced timestamp
                self._data["liked_songs"]["last_synced"] = self._now_iso()
                self._save()
    
    def get_liked_songs_track_ids(self) -> set[str]:
        """
        Get all track IDs in the liked songs section.
        
        Returns:
            Set of Spotify track IDs in liked songs.
            Empty set if liked_songs section doesn't exist.
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        """
        with self._lock:
            liked = self._data.get("liked_songs")
            if liked is None:
                return set()
            return set(liked.get("tracks", {}).keys())
    
    # =========================================================================
    # Lyrics
    # =========================================================================
    
    def set_lyrics(
        self,
        playlist_id: str,
        track_id: str,
        lyrics_text: str,
        is_synced: bool,
        source: str
    ) -> None:
        """
        Store fetched lyrics for a track.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
            lyrics_text: The lyrics text (plain text or LRC format).
            is_synced: True if lyrics are in LRC format with timestamps.
            source: Name of the provider that returned lyrics
                    (e.g., "synced", "genius", "azlyrics", "musixmatch").
        
        Behavior:
            - Set lyrics_text to the provided text
            - Set lyrics_synced to is_synced
            - Set lyrics_source to source
            - Set lyrics_fetched to True
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        
        Example:
            db.set_lyrics(
                playlist_id,
                track_id,
                lyrics_text="[00:15.00]First line...",
                is_synced=True,
                source="synced"
            )
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.get("tracks", {})
            if track_id not in tracks:
                raise DatabaseError(
                    f"Track not found: {track_id}",
                    details={"playlist_id": playlist_id, "track_id": track_id}
                )
            
            tracks[track_id]["lyrics_text"] = lyrics_text
            tracks[track_id]["lyrics_synced"] = is_synced
            tracks[track_id]["lyrics_source"] = source
            tracks[track_id]["lyrics_fetched"] = True
            self._save()
    
    def mark_lyrics_fetched(
        self,
        playlist_id: str,
        track_id: str
    ) -> None:
        """
        Mark a track as having had lyrics fetch attempted.
        
        This should be called even when no lyrics were found, to avoid
        re-attempting the fetch on subsequent runs.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
        
        Behavior:
            - Set lyrics_fetched to True
            - Does NOT modify lyrics_text, lyrics_synced, or lyrics_source
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        
        Use Case:
            Call this after attempting to fetch lyrics, regardless of whether
            lyrics were found. This prevents the system from repeatedly trying
            to fetch lyrics for tracks that don't have any available.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.get("tracks", {})
            if track_id not in tracks:
                raise DatabaseError(
                    f"Track not found: {track_id}",
                    details={"playlist_id": playlist_id, "track_id": track_id}
                )
            
            tracks[track_id]["lyrics_fetched"] = True
            self._save()
    
    def get_tracks_needing_lyrics(
        self,
        playlist_id: str
    ) -> list[dict[str, Any]]:
        """
        Get all tracks that need lyrics fetching.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            List of track data dictionaries where:
            - downloaded is True
            - lyrics_fetched is False
            Each dict includes 'track_id' key for reference.
        
        Use Case:
            Used in PHASE 4 to determine which tracks need lyrics fetching.
        
        Thread Safety:
            Acquires _lock and returns copies of track data.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return []
            
            result = []
            for track_id, track_data in container.get("tracks", {}).items():
                if (track_data.get("downloaded", False) 
                    and not track_data.get("lyrics_fetched", False)):
                    track_copy = dict(track_data)
                    track_copy["track_id"] = track_id
                    result.append(track_copy)
            
            return result
    
    # =========================================================================
    # Metadata embedding
    # =========================================================================
    
    def mark_metadata_embedded(
        self,
        playlist_id: str,
        track_id: str,
        new_file_path: Path | None = None
    ) -> None:
        """
        Mark a track as having metadata successfully embedded.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
            new_file_path: Optional new file path if file was renamed.
                        If provided, updates file_path field.
        
        Behavior:
            - Set metadata_embedded to True
            - If new_file_path provided, update file_path
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        
        Use Case:
            Called after successfully embedding all metadata into an M4A file.
            If the file was renamed to its final name during embedding,
            pass the new path to update the database.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.get("tracks", {})
            if track_id not in tracks:
                raise DatabaseError(
                    f"Track not found: {track_id}",
                    details={"playlist_id": playlist_id, "track_id": track_id}
                )
            
            tracks[track_id]["metadata_embedded"] = True
            if new_file_path is not None:
                tracks[track_id]["file_path"] = str(new_file_path)
            self._save()
    
    def mark_lyrics_embedded(
        self,
        playlist_id: str,
        track_id: str
    ) -> None:
        """
        Mark a track as having lyrics successfully embedded.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
        
        Behavior:
            - Set lyrics_embedded to True
            - Save to disk
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        
        Note:
            This should only be called if the track actually has lyrics.
            Tracks without lyrics should have lyrics_embedded remain False.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                raise DatabaseError(
                    f"Playlist not found: {playlist_id}",
                    details={"playlist_id": playlist_id}
                )
            
            tracks = container.get("tracks", {})
            if track_id not in tracks:
                raise DatabaseError(
                    f"Track not found: {track_id}",
                    details={"playlist_id": playlist_id, "track_id": track_id}
                )
            
            tracks[track_id]["lyrics_embedded"] = True
            self._save()
    
    def get_tracks_needing_embedding(
        self,
        playlist_id: str
    ) -> list[dict[str, Any]]:
        """
        Get all tracks that need metadata embedding.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            List of track data dictionaries where:
            - downloaded is True
            - metadata_embedded is False
            Each dict includes 'track_id' key for reference.
        
        Use Case:
            Used in PHASE 5 to determine which tracks need metadata embedding.
        
        Thread Safety:
            Acquires _lock and returns copies of track data.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return []
            
            result = []
            for track_id, track_data in container.get("tracks", {}).items():
                if (track_data.get("downloaded", False) 
                    and not track_data.get("metadata_embedded", False)):
                    track_copy = dict(track_data)
                    track_copy["track_id"] = track_id
                    result.append(track_copy)
            
            return result
    
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
            - matched: Tracks with youtube_url set (not None and not YOUTUBE_MATCH_FAILED)
            - downloaded: Tracks with downloaded=True
            - failed_match: Tracks with youtube_url=YOUTUBE_MATCH_FAILED
            - pending_match: Tracks with youtube_url=None
            - pending_download: Tracks matched but not downloaded
        
        Thread Safety:
            Acquires _lock and computes stats from current data.
        
        See Also:
            YOUTUBE_MATCH_FAILED: The constant value used to identify failed matches.
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return {
                    "total": 0,
                    "matched": 0,
                    "downloaded": 0,
                    "failed_match": 0,
                    "pending_match": 0,
                    "pending_download": 0
                }
            
            tracks = container.get("tracks", {})
            
            total = len(tracks)
            matched = 0
            downloaded = 0
            failed_match = 0
            pending_match = 0
            
            for track_data in tracks.values():
                youtube_url = track_data.get("youtube_url")
                
                if youtube_url is None:
                    pending_match += 1
                elif youtube_url == YOUTUBE_MATCH_FAILED:
                    failed_match += 1
                else:
                    matched += 1
                    if track_data.get("downloaded", False):
                        downloaded += 1
            
            pending_download = matched - downloaded
            
            return {
                "total": total,
                "matched": matched,
                "downloaded": downloaded,
                "failed_match": failed_match,
                "pending_match": pending_match,
                "pending_download": pending_download
            }
    
    # =========================================================================
    # Utility
    # =========================================================================
    
    def get_max_assigned_number(self, playlist_id: str) -> int:
        """
        Get the highest assigned_number for tracks in a playlist.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            The maximum assigned_number across all tracks in the playlist.
            Returns 0 if no tracks exist or no tracks have assigned_number.
        
        Behavior:
            - Iterates through all tracks in the playlist
            - Finds the highest assigned_number value
            - Returns 0 if playlist is empty or no tracks have numbers
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        
        Use Case:
            Used in sync mode by _assign_track_numbers() to determine
            the starting number for newly added tracks.
        
        Example:
            max_num = database.get_max_assigned_number(playlist_id)
            # If max_num is 42, new tracks start from 43
        """
        with self._lock:
            container = self._get_tracks_container(playlist_id)
            if container is None:
                return 0
            
            max_num = 0
            for track_data in container.get("tracks", {}).values():
                assigned = track_data.get("assigned_number")
                if assigned is not None and assigned > max_num:
                    max_num = assigned
            
            return max_num
    
    def get_next_track_number(self, playlist_id: str) -> int:
        """
        Get the next track number for file naming.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            The next track number to use (1-indexed).
            This is get_max_assigned_number() + 1.
        
        Behavior:
            Returns get_max_assigned_number(playlist_id) + 1.
            Returns 1 if no tracks exist.
        
        Thread Safety:
            Acquires _lock for the duration of the calculation.
        
        Note:
            This is a convenience wrapper around get_max_assigned_number().
        """
        return self.get_max_assigned_number(playlist_id) + 1