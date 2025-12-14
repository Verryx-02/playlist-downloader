"""
Audio downloader for spot-downloader (PHASE 3).

This module handles downloading audio from YouTube and converting
to M4A format with embedded metadata. It is the final phase of
the download workflow.

PHASE 3 Workflow:
    1. Get tracks with YouTube URL but not downloaded from database
    2. For each track:
       a. Download audio from YouTube using yt-dlp
       b. Convert to M4A format using FFmpeg
       c. Fetch lyrics (optional, may fail)
       d. Embed metadata (title, artist, cover, lyrics)
       e. Rename to final filename
       f. Mark as downloaded in database
    3. Generate statistics

Audio Quality:
    - Free YouTube: 128 kbps (maximum available)
    - YouTube Premium (with cookies): 256 kbps
    Quality is auto-detected based on cookie file.

File Naming:
    Files are named: {track_number}-{title}-{artist}.m4a
    - track_number: Sequential based on download timestamp
    - title/artist: Sanitized using yt_dlp.utils.sanitize_filename

Dependencies:
    - yt-dlp: YouTube download and extraction
    - FFmpeg: Audio conversion (must be installed)
    - mutagen: Metadata embedding (via metadata.py)

Usage:
    from spot_downloader.download.downloader import Downloader
    
    downloader = Downloader(
        database=database,
        output_dir=Path("/path/to/output"),
        cookie_file=Path("/path/to/cookies.txt")  # Optional
    )
    
    stats = downloader.download_tracks(tracks, playlist_id, num_threads=4)
    print(f"Downloaded: {stats['downloaded']}/{stats['total']}")
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename

from spot_downloader.core.database import Database
from spot_downloader.core.exceptions import DownloadError
from spot_downloader.core.logger import get_logger, log_failed_track
from spot_downloader.download.lyrics import LyricsFetcher, Lyrics
from spot_downloader.download.metadata import MetadataEmbedder
from spot_downloader.spotify.models import Track

logger = get_logger(__name__)


@dataclass
class DownloadStats:
    """
    Statistics from a download batch.
    
    Attributes:
        total: Total number of tracks to download.
        downloaded: Successfully downloaded and processed.
        failed: Failed to download.
        skipped: Already downloaded (skipped).
    """
    
    total: int = 0
    downloaded: int = 0
    failed: int = 0
    skipped: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.downloaded / self.total) * 100


class Downloader:
    """
    Downloads audio from YouTube and processes into final M4A files.
    
    This class implements PHASE 3 of the download workflow. It takes
    tracks with YouTube URLs and produces final M4A files with
    embedded metadata.
    
    Attributes:
        _database: Database for tracking download state.
        _output_dir: Directory where files are saved.
        _cookie_file: Optional cookies.txt for YouTube Premium.
        _num_threads: Number of parallel downloads.
        _lyrics_fetcher: LyricsFetcher instance.
        _metadata_embedder: MetadataEmbedder instance.
    
    Thread Safety:
        The download_track() method is thread-safe. Multiple threads
        can download different tracks simultaneously.
    
    Example:
        downloader = Downloader(
            database=db,
            output_dir=Path("/music"),
            cookie_file=Path("cookies.txt")
        )
        
        stats = downloader.download_tracks(tracks, playlist_id)
        print(f"Downloaded {stats.downloaded} of {stats.total} tracks")
    """
    
    def __init__(
        self,
        database: Database,
        output_dir: Path,
        cookie_file: Path | None = None,
        num_threads: int = 4
    ) -> None:
        """
        Initialize the Downloader.
        
        Args:
            database: Database instance for state tracking.
            output_dir: Directory where M4A files will be saved.
                       Created if it doesn't exist.
            cookie_file: Optional path to cookies.txt file for
                        YouTube Premium quality (256 kbps).
                        If None, downloads at 128 kbps.
            num_threads: Default number of parallel download threads.
        
        Behavior:
            1. Store configuration
            2. Create output_dir if it doesn't exist
            3. Initialize LyricsFetcher and MetadataEmbedder
            4. Validate cookie_file exists (if provided)
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def download_tracks(
        self,
        tracks: list[dict[str, Any]],
        playlist_id: str,
        num_threads: int | None = None
    ) -> DownloadStats:
        """
        Download multiple tracks using parallel processing.
        
        This is the main entry point for PHASE 3 batch processing.
        
        Args:
            tracks: List of track data dicts from database.
                   Each dict must have 'track_id', 'youtube_url',
                   and all metadata fields.
            playlist_id: Playlist ID for database updates.
            num_threads: Override default thread count.
        
        Returns:
            DownloadStats with counts of success/failure.
        
        Behavior:
            1. Create thread pool with num_threads workers
            2. Submit download_track() task for each track
            3. Track progress with tqdm progress bar
            4. Collect results and statistics
            5. Return final stats
        
        Progress:
            Displays a tqdm progress bar with track names.
            Console output is coordinated to not break the bar.
        
        Error Handling:
            Individual track failures don't stop the batch.
            Failed tracks are logged and counted in stats.
        
        Example:
            tracks = database.get_tracks_not_downloaded(playlist_id)
            stats = downloader.download_tracks(tracks, playlist_id)
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def download_track(
        self,
        track_data: dict[str, Any],
        playlist_id: str
    ) -> bool:
        """
        Download and process a single track.
        
        This method handles the complete download workflow for one track.
        
        Args:
            track_data: Track data dictionary from database.
                       Required keys: track_id, youtube_url, name,
                       artist, artists, album, duration_ms, etc.
            playlist_id: Playlist ID for database updates.
        
        Returns:
            True if download succeeded, False otherwise.
        
        Behavior:
            1. Reconstruct Track object from track_data
            2. Download audio from YouTube URL
            3. Convert to M4A using FFmpeg
            4. Fetch lyrics (optional, may fail silently)
            5. Embed metadata and lyrics
            6. Generate filename and rename
            7. Update database (mark downloaded)
            8. Return success
        
        Error Handling:
            - Download errors: Logged, returns False
            - Conversion errors: Logged, returns False
            - Metadata errors: Logged, returns False
            - Lyrics errors: Logged, continues (lyrics optional)
        
        Logging:
            - INFO: Starting download
            - INFO: Download complete
            - ERROR: Download failed (with reason)
            - DEBUG: Individual steps
        
        Thread Safety:
            This method is thread-safe. Uses per-track temp files.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _download_audio(
        self,
        youtube_url: str,
        output_path: Path
    ) -> Path:
        """
        Download audio from YouTube using yt-dlp.
        
        Args:
            youtube_url: YouTube video URL to download.
            output_path: Directory for temporary download file.
        
        Returns:
            Path to the downloaded audio file.
        
        Raises:
            DownloadError: If download fails.
        
        Behavior:
            1. Configure yt-dlp options for best audio
            2. Download audio stream
            3. Return path to downloaded file
        
        yt-dlp Options:
            - format: best audio quality available
            - extract_audio: True
            - cookies: From cookie_file if provided
            - quiet: True (we log ourselves)
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _convert_to_m4a(
        self,
        input_path: Path,
        output_path: Path
    ) -> None:
        """
        Convert audio file to M4A format using FFmpeg.
        
        Args:
            input_path: Path to input audio file.
            output_path: Path for output M4A file.
        
        Raises:
            DownloadError: If conversion fails.
        
        Behavior:
            Converts to M4A (AAC) at maximum quality.
            Uses FFmpeg via yt-dlp's post-processor.
        
        Note:
            If input is already M4A, may just copy without re-encoding.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _generate_filename(
        self,
        track: Track,
        track_number: int
    ) -> str:
        """
        Generate the final filename for a track.
        
        Args:
            track: Track object with metadata.
            track_number: Sequential number for this download.
        
        Returns:
            Sanitized filename: "{track_number}-{title}-{artist}.m4a"
        
        Sanitization:
            Uses yt_dlp.utils.sanitize_filename to remove/replace
            characters that are invalid in filenames.
        
        Example:
            _generate_filename(track, 42)
            # Returns: "42-Bohemian Rhapsody-Queen.m4a"
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _get_yt_dlp_options(self) -> dict[str, Any]:
        """
        Build yt-dlp options dictionary.
        
        Returns:
            Dictionary of yt-dlp options.
        
        Options Include:
            - format: Best audio format preference
            - quiet: True (suppress yt-dlp output)
            - no_warnings: True
            - cookiefile: Path if cookie_file provided
            - outtmpl: Output template for temp files
        
        Audio Quality:
            With cookies (Premium): Up to 256 kbps
            Without cookies: Up to 128 kbps
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _cleanup_temp_files(self, temp_dir: Path) -> None:
        """
        Clean up temporary download files.
        
        Args:
            temp_dir: Directory containing temp files.
        
        Behavior:
            Removes all files in temp_dir created during download.
            Called after successful processing or on error.
        """
        raise NotImplementedError("Contract only - implementation pending")


def download_tracks_phase3(
    database: Database,
    output_dir: Path,
    playlist_id: str,
    cookie_file: Path | None = None,
    num_threads: int = 4
) -> DownloadStats:
    """
    Convenience function for PHASE 3 track downloading.
    
    This is the main entry point called by the CLI for downloads.
    
    Args:
        database: Database instance.
        output_dir: Output directory for M4A files.
        playlist_id: Playlist ID to download.
        cookie_file: Optional cookies.txt for Premium quality.
        num_threads: Number of parallel downloads.
    
    Returns:
        DownloadStats with download results.
    
    Behavior:
        1. Get tracks needing download from database
        2. Create Downloader instance
        3. Download all tracks
        4. Return statistics
    
    Example:
        stats = download_tracks_phase3(
            database=db,
            output_dir=Path("/music"),
            playlist_id=playlist_id,
            num_threads=4
        )
        print(f"Downloaded: {stats.downloaded}")
        print(f"Failed: {stats.failed}")
    """
    tracks = database.get_tracks_not_downloaded(playlist_id)
    
    if not tracks:
        logger.info("No tracks to download")
        return DownloadStats(total=0)
    
    downloader = Downloader(
        database=database,
        output_dir=output_dir,
        cookie_file=cookie_file,
        num_threads=num_threads
    )
    
    return downloader.download_tracks(tracks, playlist_id, num_threads)


def get_tracks_needing_download(database: Database, playlist_id: str) -> list[dict[str, Any]]:
    """
    Get tracks from database that need downloading.
    
    Convenience function for getting tracks to process in PHASE 3
    when running phases separately.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID to query.
    
    Returns:
        List of track data dicts for tracks with youtube_url set
        but downloaded=False.
    """
    return database.get_tracks_not_downloaded(playlist_id)
