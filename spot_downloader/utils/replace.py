"""
Track replacement utility for spot-downloader.

This module provides functionality to replace the audio in an existing
M4A file while preserving all metadata. This is useful when the automatic
YouTube matching selects the wrong version of a song.

Usage:
    from spot_downloader.utils.replace import replace_track_audio
    
    replace_track_audio(
        m4a_path=Path("~/Music/01-Song-Artist.m4a"),
        youtube_url="https://www.youtube.com/watch?v=correct_id",
        cookie_file=Path("~/cookies.txt")  # Optional
    )

Workflow:
    1. Read and store all metadata from the existing M4A file
    2. Download audio from the provided YouTube URL
    3. Convert to M4A format
    4. Re-embed the stored metadata into the new file
    5. Replace the original file with the new one

Note:
    This operation is completely independent from the database.
    It can be used on any M4A file, not just files managed by spot-downloader.
"""

from pathlib import Path
from typing import Any

from spot_downloader.core.exceptions import DownloadError, MetadataError
from spot_downloader.core.logger import get_logger

logger = get_logger(__name__)


def replace_track_audio(
    m4a_path: Path,
    youtube_url: str,
    cookie_file: Path | None = None
) -> None:
    """
    Replace the audio in an M4A file while preserving metadata.
    
    This function allows users to manually correct cases where the
    automatic YouTube matching selected the wrong song.
    
    Args:
        m4a_path: Path to the existing M4A file to replace.
                  Must exist and be a valid M4A file.
        youtube_url: YouTube URL to download the correct audio from.
                     Can be a regular YouTube URL or YouTube Music URL.
        cookie_file: Optional path to cookies.txt for Premium quality.
    
    Raises:
        FileNotFoundError: If m4a_path doesn't exist.
        MetadataError: If the file is not a valid M4A or metadata
                       cannot be read/written.
        DownloadError: If the YouTube download fails.
    
    Behavior:
        1. Validate m4a_path exists and is readable
        2. Extract all metadata from the existing M4A file:
           - Title, artist, album, album artist
           - Track number, disc number
           - Year, genre, copyright
           - Cover art (as bytes)
           - Lyrics (if present)
           - ISRC, explicit flag
        3. Download audio from youtube_url to a temp file
        4. Convert to M4A format
        5. Write all extracted metadata to the new M4A
        6. Atomically replace the original file
        7. Clean up temp files
    
    Atomicity:
        The replacement is atomic - if any step fails, the original
        file is left untouched. The new file is written to a temp
        location and only moved to the final path on success.
    
    Example:
        # User found the correct version on YouTube
        replace_track_audio(
            Path("~/Music/SpotDownloader/42-Wrong Song-Artist.m4a"),
            "https://www.youtube.com/watch?v=correct_video_id"
        )
    """
    raise NotImplementedError("Contract only - implementation pending")


def extract_m4a_metadata(m4a_path: Path) -> dict[str, Any]:
    """
    Extract all metadata from an M4A file.
    
    Args:
        m4a_path: Path to the M4A file.
    
    Returns:
        Dictionary containing all extractable metadata:
        - title: str
        - artist: str
        - artists: list[str]
        - album: str
        - album_artist: str
        - track_number: int
        - disc_number: int
        - year: int
        - genre: str
        - cover_art: bytes | None
        - lyrics: str | None
        - isrc: str | None
        - explicit: bool
        - copyright: str | None
    
    Raises:
        MetadataError: If file is not a valid M4A or cannot be read.
    
    Note:
        This function uses mutagen to read M4A tags.
        All M4A-specific tag names are translated to generic names.
    """
    raise NotImplementedError("Contract only - implementation pending")


def apply_m4a_metadata(m4a_path: Path, metadata: dict[str, Any]) -> None:
    """
    Apply metadata to an M4A file.
    
    Args:
        m4a_path: Path to the M4A file.
        metadata: Dictionary of metadata (as returned by extract_m4a_metadata).
    
    Raises:
        MetadataError: If metadata cannot be written.
    
    Note:
        This overwrites all existing metadata in the file.
    """
    raise NotImplementedError("Contract only - implementation pending")