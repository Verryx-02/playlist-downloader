"""
Metadata embedding phase (PHASE 5) for spot-downloader.

This module provides the orchestration for embedding metadata and lyrics
into all downloaded M4A files that haven't been processed yet.

PHASE 5 Workflow:
    1. Query database for tracks where downloaded=True and metadata_embedded=False
    2. For each track:
       a. Load the M4A file from file_path
       b. Embed all Spotify metadata
       c. Embed lyrics (if available in database)
       d. Rename to final filename: {number}-{title}-{artist}.m4a
       e. Update database with new file_path and embedded flags
    3. Report statistics

Usage:
    from spot_downloader.download.embed_phase import embed_metadata_phase5
    
    stats = embed_metadata_phase5(database, playlist_id, output_dir)
    print(f"Embedded metadata in {stats.embedded}/{stats.total} tracks")
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spot_downloader.core.database import Database
from spot_downloader.core.logger import get_logger
from spot_downloader.download.metadata import MetadataEmbedder
from spot_downloader.download.lyrics import Lyrics
from spot_downloader.spotify.models import Track

logger = get_logger(__name__)


@dataclass
class EmbedStats:
    """
    Statistics from metadata embedding batch.
    
    Attributes:
        total: Total number of tracks to process.
        embedded: Successfully embedded metadata.
        with_lyrics: Tracks where lyrics were also embedded.
        failed: Failed to embed (file issues, etc.).
    """
    
    total: int = 0
    embedded: int = 0
    with_lyrics: int = 0
    failed: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.embedded / self.total) * 100


def embed_metadata_phase5(
    database: Database,
    playlist_id: str,
    output_dir: Path
) -> EmbedStats:
    """
    Embed metadata and lyrics into all M4A files that need processing.
    
    This is the main entry point for PHASE 5.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID to process.
        output_dir: Directory containing the M4A files.
    
    Returns:
        EmbedStats with embedding results.
    
    Behavior:
        1. Get tracks needing embedding from database
        2. Create MetadataEmbedder instance
        3. For each track:
           a. Load file from file_path in database
           b. Reconstruct Track object from database metadata
           c. Create Lyrics object if lyrics_text exists
           d. Call embedder.embed_metadata()
           e. Generate final filename: {assigned_number}-{title}-{artist}.m4a
           f. Rename file to final name
           g. Update database: file_path, metadata_embedded, lyrics_embedded
        4. Log summary statistics
        5. Return stats
    
    File Naming:
        Files are renamed from their temporary names (set in PHASE 3)
        to the final format: {assigned_number}-{title}-{artist}.m4a
        
        The assigned_number is determined in PHASE 1 based on the
        chronological order of when tracks were added to the playlist.
    
    Database Updates:
        - Updates file_path to the new renamed path
        - Sets metadata_embedded=True
        - Sets lyrics_embedded=True if lyrics were embedded
    
    Error Handling:
        - If a file is missing, log error and skip
        - If embedding fails, log error and skip
        - Continue processing other tracks
    """
    raise NotImplementedError("Contract only - implementation pending")


def _embed_single_track(
    embedder: MetadataEmbedder,
    track_data: dict[str, Any],
    output_dir: Path
) -> tuple[bool, Path | None, bool]:
    """
    Embed metadata into a single track's M4A file.
    
    Args:
        embedder: MetadataEmbedder instance.
        track_data: Track data from database.
        output_dir: Output directory for renamed files.
    
    Returns:
        Tuple of:
        - success: bool - True if embedding succeeded
        - new_path: Path | None - New file path after rename, or None if failed
        - had_lyrics: bool - True if lyrics were embedded
    
    Behavior:
        1. Check file exists at track_data['file_path']
        2. Reconstruct Track object from track_data
        3. Create Lyrics object if track_data['lyrics_text'] exists
        4. Call embedder.embed_metadata()
        5. Generate final filename
        6. Rename file
        7. Return results
    """
    raise NotImplementedError("Contract only - implementation pending")


def _generate_final_filename(
    assigned_number: int,
    title: str,
    artist: str,
    extension: str = "m4a"
) -> str:
    """
    Generate the final filename for a track.
    
    Args:
        assigned_number: Track number (from chronological playlist order).
        title: Track title (will be sanitized).
        artist: Artist name (will be sanitized).
        extension: File extension without dot.
    
    Returns:
        Filename in format: {number}-{title}-{artist}.{extension}
    
    Example:
        _generate_final_filename(42, "Hello: World", "AC/DC")
        # Returns: "42-Hello_ World-AC_DC.m4a"
    """
    raise NotImplementedError("Contract only - implementation pending")