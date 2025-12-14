"""
Metadata embedding for spot-downloader.

This module handles embedding ID3/M4A metadata tags into downloaded
audio files. It supports:
    - Basic metadata (title, artist, album, year, genre)
    - Album artwork (cover image)
    - Lyrics (plain text and synced LRC)
    - Extended metadata (copyright, publisher, ISRC)

Supported Format:
    Only M4A (AAC) format is supported. The application always
    downloads and converts to M4A, so no other formats are handled.

M4A Tag Mapping:
    Spotify Field      -> M4A Tag
    ----------------   ---------
    name               -> \xa9nam (title)
    artist             -> \xa9ART (artist)
    artists            -> \xa9ART (all artists joined)
    album              -> \xa9alb (album)
    album_artist       -> aART (album artist)
    year               -> \xa9day (year/date)
    genre              -> \xa9gen (genre)
    track_number       -> trkn (track number/total)
    disc_number        -> disk (disc number/total)
    cover_url          -> covr (cover art)
    lyrics             -> \xa9lyr (lyrics)
    explicit           -> rtng (rating - 4=explicit, 2=clean)
    copyright          -> cprt (copyright)
    publisher          -> \xa9too (encoded by)
    spotify_url        -> ----:spotdl:WOAS (custom tag)
    isrc               -> ----:spotdl:ISRC (custom tag)

Dependencies:
    - mutagen: Audio metadata library
    - requests: For downloading cover art

Usage:
    from spot_downloader.download.metadata import MetadataEmbedder
    
    embedder = MetadataEmbedder()
    embedder.embed_metadata(
        file_path=Path("/path/to/song.m4a"),
        track=track,
        lyrics=lyrics  # Optional
    )
"""

from pathlib import Path
from typing import Any

from mutagen.mp4 import MP4, MP4Cover

from spot_downloader.core.exceptions import MetadataError
from spot_downloader.core.logger import get_logger
from spot_downloader.download.lyrics import Lyrics
from spot_downloader.spotify.models import Track

logger = get_logger(__name__)


# M4A tag mapping (same as spotDL for consistency)
# See: https://mutagen.readthedocs.io/en/latest/api/mp4.html
M4A_TAGS = {
    "title": "\xa9nam",
    "artist": "\xa9ART",
    "album": "\xa9alb",
    "album_artist": "aART",
    "date": "\xa9day",
    "genre": "\xa9gen",
    "track_number": "trkn",  # Tuple: (track, total)
    "disc_number": "disk",   # Tuple: (disc, total)
    "cover": "covr",
    "lyrics": "\xa9lyr",
    "explicit": "rtng",      # 4 = explicit, 2 = clean
    "copyright": "cprt",
    "encoded_by": "\xa9too",
    "comment": "\xa9cmt",
    # Custom freeform tags (for Spotify URL, ISRC)
    "woas": "----:spotdl:WOAS",  # Web Original Audio Source
    "isrc": "----:spotdl:ISRC",
}


class MetadataEmbedder:
    """
    Embeds metadata into M4A audio files.
    
    This class handles all metadata embedding operations for
    downloaded M4A files. It uses mutagen for tag manipulation.
    
    Embedding Process:
        1. Open M4A file with mutagen
        2. Clear existing tags (optional)
        3. Set basic metadata tags
        4. Download and embed cover art
        5. Embed lyrics if available
        6. Save file
    
    Error Handling:
        - Cover art download failures are logged but don't stop embedding
        - Lyrics embedding failures are logged but don't stop embedding
        - File write failures raise MetadataError
    
    Thread Safety:
        Each embed_metadata() call operates on a separate file.
        Multiple threads can embed metadata to different files
        simultaneously.
    
    Example:
        embedder = MetadataEmbedder()
        
        try:
            embedder.embed_metadata(file_path, track, lyrics)
        except MetadataError as e:
            logger.error(f"Failed to embed metadata: {e}")
    """
    
    def __init__(self) -> None:
        """
        Initialize the MetadataEmbedder.
        
        No initialization required - this class is stateless.
        """
        pass
    
    def embed_metadata(
        self,
        file_path: Path,
        track: Track,
        lyrics: Lyrics | None = None
    ) -> None:
        """
        Embed all metadata into an M4A file.
        
        This is the main method for metadata embedding. It embeds
        all available metadata from the Track object.
        
        Args:
            file_path: Path to the M4A file to update.
            track: Track object containing metadata to embed.
            lyrics: Optional Lyrics object to embed.
        
        Raises:
            MetadataError: If file cannot be opened, written, or saved.
        
        Behavior:
            1. Open M4A file with mutagen
            2. Embed basic tags (title, artist, album, etc.)
            3. Embed extended tags (copyright, publisher, ISRC)
            4. Download and embed cover art (if URL available)
            5. Embed lyrics (if provided)
            6. Save file
        
        Non-Fatal Errors:
            - Cover art download failure: Logged, embedding continues
            - Lyrics embedding failure: Logged, embedding continues
        
        Fatal Errors:
            - File not found or not readable
            - File is not valid M4A
            - Permission denied on write
            - Disk full
        
        Example:
            embedder = MetadataEmbedder()
            embedder.embed_metadata(
                Path("song.m4a"),
                track,
                lyrics=Lyrics("lyrics text", is_synced=False, source="genius")
            )
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _open_file(self, file_path: Path) -> MP4:
        """
        Open an M4A file for metadata editing.
        
        Args:
            file_path: Path to the M4A file.
        
        Returns:
            MP4 object from mutagen.
        
        Raises:
            MetadataError: If file cannot be opened or is not valid M4A.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _embed_basic_tags(self, audio: MP4, track: Track) -> None:
        """
        Embed basic metadata tags.
        
        Args:
            audio: MP4 object to update.
            track: Track with metadata.
        
        Tags Embedded:
            - title (\xa9nam)
            - artist (\xa9ART) - all artists joined with ", "
            - album (\xa9alb)
            - album_artist (aART)
            - date (\xa9day)
            - genre (\xa9gen) - first genre if multiple
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _embed_track_disc_numbers(self, audio: MP4, track: Track) -> None:
        """
        Embed track and disc number tags.
        
        Args:
            audio: MP4 object to update.
            track: Track with metadata.
        
        Tags Embedded:
            - trkn: (track_number, tracks_count) tuple
            - disk: (disc_number, disc_count) tuple
        
        Format:
            M4A uses tuples for track/disc numbers: (number, total)
            This allows players to display "3 of 12".
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _embed_extended_tags(self, audio: MP4, track: Track) -> None:
        """
        Embed extended metadata tags.
        
        Args:
            audio: MP4 object to update.
            track: Track with metadata.
        
        Tags Embedded:
            - copyright (cprt)
            - encoded_by (\xa9too) - publisher/label
            - explicit (rtng) - 4 for explicit, 2 for clean
            - woas (custom) - Spotify URL
            - isrc (custom) - ISRC code
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _embed_cover_art(self, audio: MP4, cover_url: str | None) -> None:
        """
        Download and embed album cover art.
        
        Args:
            audio: MP4 object to update.
            cover_url: URL to cover image, or None.
        
        Behavior:
            1. If cover_url is None, skip silently
            2. Download image from URL
            3. Detect image format (JPEG or PNG)
            4. Create MP4Cover object
            5. Embed as 'covr' tag
        
        Error Handling:
            Download failures are logged but don't raise exceptions.
            The file will simply not have cover art.
        
        Image Formats:
            Supports JPEG and PNG. JPEG is preferred for smaller size.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _embed_lyrics(self, audio: MP4, lyrics: Lyrics | None) -> None:
        """
        Embed lyrics into the audio file.
        
        Args:
            audio: MP4 object to update.
            lyrics: Lyrics object, or None.
        
        Behavior:
            1. If lyrics is None, skip silently
            2. Embed lyrics text as \xa9lyr tag
            3. If synced (LRC format), text includes timestamps
        
        LRC Handling:
            For M4A files, LRC lyrics are embedded as plain text
            including the timestamp tags. Players that support LRC
            will parse them; others will display as-is.
        
        Note:
            Unlike MP3 which has separate USLT (unsync) and SYLT (sync)
            tags, M4A only has one lyrics tag. Synced lyrics are stored
            with their timestamps intact in the text.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _save_file(self, audio: MP4, file_path: Path) -> None:
        """
        Save the modified audio file.
        
        Args:
            audio: MP4 object to save.
            file_path: Path to save to (for error messages).
        
        Raises:
            MetadataError: If save fails (permissions, disk full, etc.)
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    @staticmethod
    def _download_cover(url: str) -> bytes | None:
        """
        Download cover art from URL.
        
        Args:
            url: URL to the cover image.
        
        Returns:
            Image bytes if successful, None if download failed.
        
        Behavior:
            - Uses requests to download image
            - Timeout of 10 seconds
            - Returns None on any error (doesn't raise)
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    @staticmethod
    def _detect_image_format(data: bytes) -> int:
        """
        Detect image format from bytes.
        
        Args:
            data: Image bytes.
        
        Returns:
            MP4Cover format constant:
            - MP4Cover.FORMAT_JPEG for JPEG
            - MP4Cover.FORMAT_PNG for PNG
        
        Detection:
            - JPEG: Starts with FF D8 FF
            - PNG: Starts with 89 50 4E 47
        """
        raise NotImplementedError("Contract only - implementation pending")


def embed_track_metadata(
    file_path: Path,
    track: Track,
    lyrics: Lyrics | None = None
) -> None:
    """
    Convenience function to embed metadata without creating embedder instance.
    
    Args:
        file_path: Path to the M4A file.
        track: Track with metadata.
        lyrics: Optional lyrics.
    
    Raises:
        MetadataError: If embedding fails.
    
    Example:
        embed_track_metadata(Path("song.m4a"), track, lyrics)
    """
    embedder = MetadataEmbedder()
    embedder.embed_metadata(file_path, track, lyrics)
