"""
Thread-safe SQLite database for spot-downloader.

This module provides persistent storage for playlist and track state,
enabling features like:
    - Resume interrupted downloads
    - Sync mode (download only new tracks)
    - Track download status and metadata
    - Track lyrics fetch status
    - Track metadata embedding status

Database Structure:
    The database uses SQLite with the following schema:
    
    playlists:
        - id: INTEGER PRIMARY KEY
        - spotify_id: TEXT UNIQUE (playlist ID or "__liked_songs__")
        - spotify_url: TEXT
        - name: TEXT
        - last_synced: TEXT (ISO format timestamp)
    
    tracks:
        - id: INTEGER PRIMARY KEY
        - playlist_id: INTEGER (FK to playlists)
        - spotify_id: TEXT
        - name, artist, artists, album, duration_ms, spotify_url
        - youtube_url, downloaded, download_timestamp, file_path
        - lyrics_fetched, lyrics_text, lyrics_synced, lyrics_source
        - metadata_embedded, lyrics_embedded
        - assigned_number, added_at, isrc, cover_url, release_date
        - track_number, disc_number, year, genres, publisher, copyright
        - explicit, popularity, preview_url
        - metadata: TEXT (JSON blob for full Spotify metadata)

Track Fields:
    lyrics_fetched: bool - True if we attempted to fetch lyrics (success or not)
    lyrics_text: str|null - The lyrics text, or null if not found
    lyrics_synced: bool - True if lyrics are in LRC format with timestamps
    lyrics_source: str|null - Provider name ("synced", "genius", etc.) or null
    metadata_embedded: bool - True if metadata has been written to the M4A file
    lyrics_embedded: bool - True if lyrics have been written to the M4A file

Thread Safety:
    All public methods acquire a threading.Lock before executing.
    SQLite is configured with WAL mode for better concurrency.
    
File Safety:
    SQLite handles atomic writes internally with journaling.
    WAL mode provides crash recovery and prevents corruption.

Usage:
    from spot_downloader.core.database import Database
    
    db = Database(output_dir / "database.db")
    
    # Add tracks from Spotify fetch
    db.add_playlist(playlist_id, spotify_url, name)
    
    # Update after YouTube match
    db.set_youtube_url(playlist_id, track_id, youtube_url)
    
    # Mark as downloaded
    db.mark_downloaded(playlist_id, track_id, file_path)
"""

import json
import sqlite3
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


# SQL Schema
_SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Playlists (includes liked_songs as spotify_id = "__liked_songs__")
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id TEXT UNIQUE NOT NULL,
    spotify_url TEXT,
    name TEXT,
    last_synced TEXT
);

-- Tracks
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL,
    spotify_id TEXT NOT NULL,
    name TEXT,
    artist TEXT,
    artists TEXT,
    album TEXT,
    duration_ms INTEGER,
    spotify_url TEXT,
    youtube_url TEXT,
    downloaded INTEGER DEFAULT 0,
    download_timestamp TEXT,
    file_path TEXT,
    lyrics_fetched INTEGER DEFAULT 0,
    lyrics_text TEXT,
    lyrics_synced INTEGER DEFAULT 0,
    lyrics_source TEXT,
    metadata_embedded INTEGER DEFAULT 0,
    lyrics_embedded INTEGER DEFAULT 0,
    assigned_number INTEGER,
    added_at TEXT,
    isrc TEXT,
    cover_url TEXT,
    release_date TEXT,
    track_number INTEGER,
    disc_number INTEGER,
    year INTEGER,
    genres TEXT,
    publisher TEXT,
    copyright TEXT,
    explicit INTEGER,
    popularity INTEGER,
    preview_url TEXT,
    metadata TEXT,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id),
    UNIQUE(playlist_id, spotify_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tracks_playlist ON tracks(playlist_id);
CREATE INDEX IF NOT EXISTS idx_tracks_youtube_url ON tracks(youtube_url);
CREATE INDEX IF NOT EXISTS idx_tracks_downloaded ON tracks(downloaded);
CREATE INDEX IF NOT EXISTS idx_tracks_spotify_id ON tracks(spotify_id);
"""


class Database:
    """
    Thread-safe SQLite database for persistent storage.
    
    This class manages all read/write operations to the database.db file,
    providing a clean interface for storing and retrieving playlist and
    track information.
    
    Attributes:
        db_path: Path to the database.db file.
        _lock: Threading lock for thread-safe operations.
    
    Thread Safety:
        All public methods are thread-safe. The internal _lock is acquired
        before any read or write operation.
    
    Persistence:
        SQLite handles persistence automatically with WAL mode enabled
        for better concurrency and crash recovery.
    
    Example:
        db = Database(Path("/path/to/database.db"))
        
        # Check what tracks need to be downloaded
        new_tracks = db.get_tracks_without_youtube_url(playlist_id)
        
        # After matching
        db.set_youtube_url(playlist_id, track_id, youtube_url)
        
        # After download
        db.mark_downloaded(playlist_id, track_id, file_path)
    """
    
    def __init__(self, db_path: Path) -> None:
        """
        Initialize the database, creating tables if needed.
        
        Args:
            db_path: Path where the database.db file is/will be stored.
                     Parent directory must exist.
        
        Raises:
            DatabaseError: If the parent directory doesn't exist or
                          database cannot be initialized.
        
        Behavior:
            1. Store the path and create threading lock
            2. Create database file if it doesn't exist
            3. Initialize schema (create tables)
            4. Enable WAL mode for better concurrency
            5. Validate/set schema version
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        
        # Check parent directory exists
        if not db_path.parent.exists():
            raise DatabaseError(
                f"Parent directory does not exist: {db_path.parent}",
                details={"path": str(db_path.parent)}
            )
        
        # Initialize database
        try:
            self._init_database()
        except sqlite3.Error as e:
            raise DatabaseError(
                f"Failed to initialize database: {e}",
                details={"path": str(db_path), "original_error": str(e)}
            ) from e
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a SQLite connection with proper settings.
        
        Returns:
            Configured SQLite connection.
        
        Note:
            Creates a new connection each time for thread safety.
            SQLite connections should not be shared between threads.
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def _init_database(self) -> None:
        """
        Initialize database schema and settings.
        
        Creates tables if they don't exist and sets up WAL mode.
        """
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Create schema
            conn.executescript(_SCHEMA_SQL)
            
            # Check/set version
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", 
                           (DATABASE_VERSION,))
            elif row[0] != DATABASE_VERSION:
                raise DatabaseError(
                    f"Database version mismatch: expected {DATABASE_VERSION}, got {row[0]}",
                    details={"expected": DATABASE_VERSION, "actual": row[0]}
                )
            
            conn.commit()
    
    def _now_iso(self) -> str:
        """Get current UTC time as ISO format string."""
        return datetime.now(timezone.utc).isoformat()
    
    def _get_playlist_db_id(self, conn: sqlite3.Connection, spotify_id: str) -> int | None:
        """
        Get internal database ID for a playlist by its Spotify ID.
        
        Args:
            conn: Active database connection.
            spotify_id: Spotify playlist ID or LIKED_SONGS_KEY.
        
        Returns:
            Internal database ID or None if not found.
        """
        cursor = conn.execute(
            "SELECT id FROM playlists WHERE spotify_id = ?",
            (spotify_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    
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
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM playlists WHERE spotify_id = ?",
                    (playlist_id,)
                )
                return cursor.fetchone() is not None
    
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
            - If playlist doesn't exist, create new entry
            - If playlist exists, update name and URL (preserve existing tracks)
            - Update last_synced timestamp to current UTC time
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO playlists (spotify_id, spotify_url, name, last_synced)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(spotify_id) DO UPDATE SET
                        spotify_url = excluded.spotify_url,
                        name = excluded.name,
                        last_synced = excluded.last_synced
                """, (playlist_id, spotify_url, name, self._now_iso()))
                conn.commit()
    
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
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return set()
                
                cursor = conn.execute(
                    "SELECT spotify_id FROM tracks WHERE playlist_id = ?",
                    (db_id,)
                )
                return {row[0] for row in cursor.fetchall()}
    
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
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT spotify_url, name, last_synced FROM playlists WHERE spotify_id = ?",
                    (playlist_id,)
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "spotify_url": row["spotify_url"],
                    "name": row["name"],
                    "last_synced": row["last_synced"]
                }
    
    def get_active_playlist_id(self) -> str | None:
        """
        Get the most recently synced playlist ID.
        
        Used when running phases 2-5 without --url to determine
        which playlist to process.
        
        Returns:
            The playlist_id with the most recent last_synced timestamp,
            or None if no playlists exist in the database.
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT spotify_id FROM playlists 
                    WHERE last_synced IS NOT NULL
                    ORDER BY last_synced DESC 
                    LIMIT 1
                """)
                row = cursor.fetchone()
                return row[0] if row else None
    
    # =========================================================================
    # Track Operations
    # =========================================================================
    
    def _track_data_to_row(self, track_data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert track_data dict to database row values.
        
        Handles JSON serialization of complex fields.
        """
        row = dict(track_data)
        
        # Serialize list/dict fields to JSON
        if "artists" in row and isinstance(row["artists"], (list, tuple)):
            row["artists"] = json.dumps(row["artists"])
        if "genres" in row and isinstance(row["genres"], (list, tuple)):
            row["genres"] = json.dumps(row["genres"])
        if "metadata" in row and isinstance(row["metadata"], dict):
            row["metadata"] = json.dumps(row["metadata"])
        
        # Convert booleans to integers
        for bool_field in ["downloaded", "lyrics_fetched", "lyrics_synced", 
                          "metadata_embedded", "lyrics_embedded", "explicit"]:
            if bool_field in row and row[bool_field] is not None:
                row[bool_field] = 1 if row[bool_field] else 0
        
        return row
    
    def _row_to_track_data(self, row: sqlite3.Row) -> dict[str, Any]:
        """
        Convert database row to track_data dict.
        
        Handles JSON deserialization and boolean conversion.
        """
        data = dict(row)
        
        # Deserialize JSON fields
        for json_field in ["artists", "genres", "metadata"]:
            if json_field in data and data[json_field] is not None:
                try:
                    data[json_field] = json.loads(data[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # Convert integers to booleans
        for bool_field in ["downloaded", "lyrics_fetched", "lyrics_synced",
                          "metadata_embedded", "lyrics_embedded", "explicit"]:
            if bool_field in data and data[bool_field] is not None:
                data[bool_field] = bool(data[bool_field])
        
        return data
    
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
            track_data: Dictionary containing track information.
        
        Behavior:
            - If track already exists, update metadata but preserve:
              youtube_url, downloaded, file_path, download_timestamp,
              lyrics_fetched, lyrics_text, lyrics_synced, lyrics_source,
              metadata_embedded, lyrics_embedded
            - If track is new, add with default values for download fields
        
        Raises:
            DatabaseError: If playlist doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                row = self._track_data_to_row(track_data)
                
                # Check if track exists
                cursor = conn.execute(
                    "SELECT id FROM tracks WHERE playlist_id = ? AND spotify_id = ?",
                    (db_id, track_id)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update metadata, preserve download state
                    conn.execute("""
                        UPDATE tracks SET
                            name = ?, artist = ?, artists = ?, album = ?,
                            duration_ms = ?, spotify_url = ?, assigned_number = ?,
                            added_at = ?, isrc = ?, cover_url = ?, release_date = ?,
                            track_number = ?, disc_number = ?, year = ?, genres = ?,
                            publisher = ?, copyright = ?, explicit = ?, popularity = ?,
                            preview_url = ?, metadata = ?
                        WHERE id = ?
                    """, (
                        row.get("name"), row.get("artist"), row.get("artists"),
                        row.get("album"), row.get("duration_ms"), row.get("spotify_url"),
                        row.get("assigned_number"), row.get("added_at"), row.get("isrc"),
                        row.get("cover_url"), row.get("release_date"), row.get("track_number"),
                        row.get("disc_number"), row.get("year"), row.get("genres"),
                        row.get("publisher"), row.get("copyright"), row.get("explicit"),
                        row.get("popularity"), row.get("preview_url"), row.get("metadata"),
                        existing[0]
                    ))
                else:
                    # Insert new track
                    conn.execute("""
                        INSERT INTO tracks (
                            playlist_id, spotify_id, name, artist, artists, album,
                            duration_ms, spotify_url, youtube_url, downloaded,
                            download_timestamp, file_path, lyrics_fetched, lyrics_text,
                            lyrics_synced, lyrics_source, metadata_embedded, lyrics_embedded,
                            assigned_number, added_at, isrc, cover_url, release_date,
                            track_number, disc_number, year, genres, publisher, copyright,
                            explicit, popularity, preview_url, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        db_id, track_id, row.get("name"), row.get("artist"),
                        row.get("artists"), row.get("album"), row.get("duration_ms"),
                        row.get("spotify_url"), None, 0, None, None, 0, None, 0, None,
                        0, 0, row.get("assigned_number"), row.get("added_at"),
                        row.get("isrc"), row.get("cover_url"), row.get("release_date"),
                        row.get("track_number"), row.get("disc_number"), row.get("year"),
                        row.get("genres"), row.get("publisher"), row.get("copyright"),
                        row.get("explicit"), row.get("popularity"), row.get("preview_url"),
                        row.get("metadata")
                    ))
                
                conn.commit()
    
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
        
        Behavior:
            Same as add_track() but batched for efficiency.
            Uses a single transaction for all inserts/updates.
        
        Raises:
            DatabaseError: If playlist doesn't exist.
        
        Thread Safety:
            Acquires _lock once for the entire batch.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                # Get existing tracks
                cursor = conn.execute(
                    "SELECT spotify_id, id FROM tracks WHERE playlist_id = ?",
                    (db_id,)
                )
                existing_tracks = {row[0]: row[1] for row in cursor.fetchall()}
                
                for track_id, track_data in tracks:
                    row = self._track_data_to_row(track_data)
                    
                    if track_id in existing_tracks:
                        # Update metadata, preserve download state
                        conn.execute("""
                            UPDATE tracks SET
                                name = ?, artist = ?, artists = ?, album = ?,
                                duration_ms = ?, spotify_url = ?, assigned_number = ?,
                                added_at = ?, isrc = ?, cover_url = ?, release_date = ?,
                                track_number = ?, disc_number = ?, year = ?, genres = ?,
                                publisher = ?, copyright = ?, explicit = ?, popularity = ?,
                                preview_url = ?, metadata = ?
                            WHERE id = ?
                        """, (
                            row.get("name"), row.get("artist"), row.get("artists"),
                            row.get("album"), row.get("duration_ms"), row.get("spotify_url"),
                            row.get("assigned_number"), row.get("added_at"), row.get("isrc"),
                            row.get("cover_url"), row.get("release_date"), row.get("track_number"),
                            row.get("disc_number"), row.get("year"), row.get("genres"),
                            row.get("publisher"), row.get("copyright"), row.get("explicit"),
                            row.get("popularity"), row.get("preview_url"), row.get("metadata"),
                            existing_tracks[track_id]
                        ))
                    else:
                        # Insert new track
                        conn.execute("""
                            INSERT INTO tracks (
                                playlist_id, spotify_id, name, artist, artists, album,
                                duration_ms, spotify_url, youtube_url, downloaded,
                                download_timestamp, file_path, lyrics_fetched, lyrics_text,
                                lyrics_synced, lyrics_source, metadata_embedded, lyrics_embedded,
                                assigned_number, added_at, isrc, cover_url, release_date,
                                track_number, disc_number, year, genres, publisher, copyright,
                                explicit, popularity, preview_url, metadata
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            db_id, track_id, row.get("name"), row.get("artist"),
                            row.get("artists"), row.get("album"), row.get("duration_ms"),
                            row.get("spotify_url"), None, 0, None, None, 0, None, 0, None,
                            0, 0, row.get("assigned_number"), row.get("added_at"),
                            row.get("isrc"), row.get("cover_url"), row.get("release_date"),
                            row.get("track_number"), row.get("disc_number"), row.get("year"),
                            row.get("genres"), row.get("publisher"), row.get("copyright"),
                            row.get("explicit"), row.get("popularity"), row.get("preview_url"),
                            row.get("metadata")
                        ))
                
                conn.commit()
    
    def get_track(self, playlist_id: str, track_id: str) -> dict[str, Any] | None:
        """
        Get a single track's data.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
        
        Returns:
            Dictionary with track data, or None if not found.
        
        Thread Safety:
            Acquires _lock and returns a copy.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return None
                
                cursor = conn.execute(
                    "SELECT * FROM tracks WHERE playlist_id = ? AND spotify_id = ?",
                    (db_id, track_id)
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_track_data(row)
    
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
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return []
                
                cursor = conn.execute(
                    "SELECT * FROM tracks WHERE playlist_id = ? AND youtube_url IS NULL",
                    (db_id,)
                )
                result = []
                for row in cursor.fetchall():
                    track = self._row_to_track_data(row)
                    track["track_id"] = row["spotify_id"]
                    result.append(track)
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
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return []
                
                cursor = conn.execute("""
                    SELECT * FROM tracks 
                    WHERE playlist_id = ? 
                    AND youtube_url IS NOT NULL 
                    AND youtube_url != ?
                    AND downloaded = 0
                """, (db_id, YOUTUBE_MATCH_FAILED))
                
                result = []
                for row in cursor.fetchall():
                    track = self._row_to_track_data(row)
                    track["track_id"] = row["spotify_id"]
                    result.append(track)
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
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                cursor = conn.execute(
                    "UPDATE tracks SET youtube_url = ? WHERE playlist_id = ? AND spotify_id = ?",
                    (youtube_url, db_id, track_id)
                )
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Track not found: {track_id}",
                        details={"playlist_id": playlist_id, "track_id": track_id}
                    )
                conn.commit()
    
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
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                cursor = conn.execute("""
                    UPDATE tracks SET 
                        downloaded = 1, 
                        file_path = ?, 
                        download_timestamp = ?
                    WHERE playlist_id = ? AND spotify_id = ?
                """, (str(file_path), self._now_iso(), db_id, track_id))
                
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Track not found: {track_id}",
                        details={"playlist_id": playlist_id, "track_id": track_id}
                    )
                conn.commit()
    
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
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                cursor = conn.execute(
                    "UPDATE tracks SET youtube_url = ? WHERE playlist_id = ? AND spotify_id = ?",
                    (YOUTUBE_MATCH_FAILED, db_id, track_id)
                )
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Track not found: {track_id}",
                        details={"playlist_id": playlist_id, "track_id": track_id}
                    )
                conn.commit()
    
    # =========================================================================
    # Liked Songs Operations
    # =========================================================================
    
    def ensure_liked_songs_exists(self) -> None:
        """
        Ensure the liked_songs entry exists in the database.
        
        Behavior:
            - If liked_songs doesn't exist, create it
            - Update last_synced timestamp to current UTC time
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO playlists (spotify_id, spotify_url, name, last_synced)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(spotify_id) DO UPDATE SET
                        last_synced = excluded.last_synced
                """, (LIKED_SONGS_KEY, None, "Liked Songs", self._now_iso()))
                conn.commit()
    
    def get_liked_songs_track_ids(self) -> set[str]:
        """
        Get all track IDs in the liked songs section.
        
        Returns:
            Set of Spotify track IDs in liked songs.
            Empty set if liked_songs doesn't exist.
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        """
        return self.get_playlist_track_ids(LIKED_SONGS_KEY)
    
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
            source: Provider name ("synced", "genius", etc.).
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                cursor = conn.execute("""
                    UPDATE tracks SET 
                        lyrics_text = ?,
                        lyrics_synced = ?,
                        lyrics_source = ?,
                        lyrics_fetched = 1
                    WHERE playlist_id = ? AND spotify_id = ?
                """, (lyrics_text, 1 if is_synced else 0, source, db_id, track_id))
                
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Track not found: {track_id}",
                        details={"playlist_id": playlist_id, "track_id": track_id}
                    )
                conn.commit()
    
    def mark_lyrics_fetched(
        self,
        playlist_id: str,
        track_id: str
    ) -> None:
        """
        Mark a track as having had lyrics fetch attempted.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
            track_id: The Spotify track ID.
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                cursor = conn.execute(
                    "UPDATE tracks SET lyrics_fetched = 1 WHERE playlist_id = ? AND spotify_id = ?",
                    (db_id, track_id)
                )
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Track not found: {track_id}",
                        details={"playlist_id": playlist_id, "track_id": track_id}
                    )
                conn.commit()
    
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
        
        Thread Safety:
            Acquires _lock and returns copies of track data.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return []
                
                cursor = conn.execute("""
                    SELECT * FROM tracks 
                    WHERE playlist_id = ? AND downloaded = 1 AND lyrics_fetched = 0
                """, (db_id,))
                
                result = []
                for row in cursor.fetchall():
                    track = self._row_to_track_data(row)
                    track["track_id"] = row["spotify_id"]
                    result.append(track)
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
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                if new_file_path is not None:
                    cursor = conn.execute("""
                        UPDATE tracks SET metadata_embedded = 1, file_path = ?
                        WHERE playlist_id = ? AND spotify_id = ?
                    """, (str(new_file_path), db_id, track_id))
                else:
                    cursor = conn.execute("""
                        UPDATE tracks SET metadata_embedded = 1
                        WHERE playlist_id = ? AND spotify_id = ?
                    """, (db_id, track_id))
                
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Track not found: {track_id}",
                        details={"playlist_id": playlist_id, "track_id": track_id}
                    )
                conn.commit()
    
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
        
        Raises:
            DatabaseError: If playlist or track doesn't exist.
        
        Thread Safety:
            Acquires _lock for the entire operation.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    raise DatabaseError(
                        f"Playlist not found: {playlist_id}",
                        details={"playlist_id": playlist_id}
                    )
                
                cursor = conn.execute(
                    "UPDATE tracks SET lyrics_embedded = 1 WHERE playlist_id = ? AND spotify_id = ?",
                    (db_id, track_id)
                )
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Track not found: {track_id}",
                        details={"playlist_id": playlist_id, "track_id": track_id}
                    )
                conn.commit()
    
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
        
        Thread Safety:
            Acquires _lock and returns copies of track data.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return []
                
                cursor = conn.execute("""
                    SELECT * FROM tracks 
                    WHERE playlist_id = ? AND downloaded = 1 AND metadata_embedded = 0
                """, (db_id,))
                
                result = []
                for row in cursor.fetchall():
                    track = self._row_to_track_data(row)
                    track["track_id"] = row["spotify_id"]
                    result.append(track)
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
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return {
                        "total": 0,
                        "matched": 0,
                        "downloaded": 0,
                        "failed_match": 0,
                        "pending_match": 0,
                        "pending_download": 0
                    }
                
                # Total tracks
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tracks WHERE playlist_id = ?",
                    (db_id,)
                )
                total = cursor.fetchone()[0]
                
                # Downloaded
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tracks WHERE playlist_id = ? AND downloaded = 1",
                    (db_id,)
                )
                downloaded = cursor.fetchone()[0]
                
                # Failed match
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tracks WHERE playlist_id = ? AND youtube_url = ?",
                    (db_id, YOUTUBE_MATCH_FAILED)
                )
                failed_match = cursor.fetchone()[0]
                
                # Pending match (youtube_url is NULL)
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tracks WHERE playlist_id = ? AND youtube_url IS NULL",
                    (db_id,)
                )
                pending_match = cursor.fetchone()[0]
                
                # Matched (has youtube_url that isn't MATCH_FAILED)
                matched = total - pending_match - failed_match
                
                # Pending download (matched but not downloaded)
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
        
        Thread Safety:
            Acquires _lock for the duration of the read.
        """
        with self._lock:
            with self._get_connection() as conn:
                db_id = self._get_playlist_db_id(conn, playlist_id)
                if db_id is None:
                    return 0
                
                cursor = conn.execute(
                    "SELECT MAX(assigned_number) FROM tracks WHERE playlist_id = ?",
                    (db_id,)
                )
                row = cursor.fetchone()
                return row[0] if row[0] is not None else 0
    
    def get_next_track_number(self, playlist_id: str) -> int:
        """
        Get the next track number for file naming.
        
        Args:
            playlist_id: The Spotify playlist ID (or LIKED_SONGS_KEY).
        
        Returns:
            The next track number to use (1-indexed).
            This is get_max_assigned_number() + 1.
        
        Thread Safety:
            Acquires _lock for the duration of the calculation.
        """
        return self.get_max_assigned_number(playlist_id) + 1