"""
Audio downloader for spot-downloader (PHASE 3).

This module handles downloading audio from YouTube and saving files
using the central storage architecture with hard links.

Architecture:
    output_directory/
    ├── tracks/                               # Central storage (canonical files)
    │   ├── Bohemian Rhapsody-Queen.m4a
    │   └── Title-Artist.m4a
    ├── My Playlist/                          # Playlist view (hard links)
    │   ├── 00001-Bohemian Rhapsody-Queen.m4a → ../tracks/Bohemian Rhapsody-Queen.m4a
    │   └── 00002-Title-Artist.m4a            → ../tracks/Title-Artist.m4a
    └── Another Playlist/
        └── 00001-Bohemian Rhapsody-Queen.m4a → ../tracks/Bohemian Rhapsody-Queen.m4a

PHASE 3 Workflow:
    1. Get tracks with YouTube URL but not downloaded from database
    2. For each track:
       a. Download audio from YouTube using yt-dlp
       b. Convert to M4A format using FFmpeg (via yt-dlp postprocessor)
       c. Save to tracks/ directory with canonical name: {title}-{artist}.m4a
       d. Update database: downloaded=True, file_path (canonical path)
       e. Create hard links in ALL playlist directories containing this track
    3. Generate statistics

Audio Quality:
    - Free YouTube: 128 kbps (maximum available)
    - YouTube Premium (with cookies): 256 kbps
    Quality is auto-detected based on cookie file.

File Naming:
    - Canonical (in tracks/): {title}-{artist}.m4a
    - Playlist links: {position:05d}-{title}-{artist}.m4a

Dependencies:
    - yt-dlp: YouTube download and extraction
    - FFmpeg: Audio conversion (must be installed)

Usage:
    from spot_downloader.download.downloader import download_tracks_phase3
    
    stats = download_tracks_phase3(
        database=db,
        output_dir=Path("/music"),
        playlist_id=playlist_id,
        cookie_file=Path("cookies.txt"),  # Optional
        num_threads=4
    )
    print(f"Downloaded: {stats.downloaded}/{stats.total}")
"""

import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from rich import get_console
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
)
from rich.theme import Theme
from yt_dlp import YoutubeDL

from spot_downloader.core.database import Database
from spot_downloader.core.exceptions import DownloadError
from spot_downloader.core.file_manager import FileManager
from spot_downloader.core.logger import get_logger, log_download_failure
from spot_downloader.core.progress import SizedTextColumn

logger = get_logger(__name__)


# Progress bar theme (same as matching phase)
DOWNLOAD_PROGRESS_THEME = Theme({
    "bar.back": "grey23",
    "bar.complete": "rgb(165,66,129)",
    "bar.finished": "rgb(114,156,31)",
    "bar.pulse": "rgb(165,66,129)",
    "progress.percentage": "white",
})


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


class DownloadProgressBar:
    """
    Progress bar for download phase using Rich library.
    
    Displays:
    - Description (e.g., "Downloading")
    - Status message (downloaded/failed counts)
    - Progress bar with spotDL-style colors
    - Percentage
    """
    
    def __init__(self, total: int, description: str = "Downloading"):
        """
        Initialize the progress bar.
        
        Args:
            total: Total number of items to process.
            description: Description to show on the left.
        """
        self.total = total
        self.description = description
        self.downloaded = 0
        self.failed = 0
        self.skipped = 0
        self.completed = 0
        
        self.console = get_console()
        self.console.push_theme(DOWNLOAD_PROGRESS_THEME)
        
        self.progress = Progress(
            SizedTextColumn(
                "[white]{task.description}",
                overflow="ellipsis",
                width=15,
            ),
            SizedTextColumn(
                "{task.fields[status]}",
                width=35,
                style="white",
            ),
            BarColumn(bar_width=40, finished_style="green"),
            "[progress.percentage]{task.percentage:>3.0f}%",
            console=self.console,
            transient=False,
            refresh_per_second=10,
        )
        
        self.task_id: Optional[TaskID] = None
        self._started = False
    
    def __enter__(self) -> "DownloadProgressBar":
        """Start the progress bar."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop the progress bar."""
        self.stop()
    
    def start(self) -> None:
        """Start the progress bar (can be called manually)."""
        if not self._started:
            self.progress.start()
            self.task_id = self.progress.add_task(
                description=self.description,
                total=self.total,
                status=self._get_status_text(),
            )
            self._started = True
    
    def stop(self) -> None:
        """Stop the progress bar."""
        if self._started:
            self.progress.stop()
            self._started = False
    
    def _get_status_text(self) -> str:
        """Get the status text showing downloaded/failed/skipped counts."""
        parts = [
            f"[green]✓ {self.downloaded}[/green]",
            f"[red]✗ {self.failed}[/red]",
        ]
        if self.skipped > 0:
            parts.append(f"[yellow]⊘ {self.skipped}[/yellow]")
        return "  ".join(parts)
    
    def update(self, success: bool, skipped: bool = False) -> None:
        """
        Update the progress bar with a completed item.
        
        Args:
            success: Whether the item was successfully downloaded.
            skipped: Whether the item was skipped (already exists).
        """
        self.completed += 1
        if skipped:
            self.skipped += 1
        elif success:
            self.downloaded += 1
        else:
            self.failed += 1
        
        if self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=self.completed,
                status=self._get_status_text(),
            )
    
    def log(self, message: str) -> None:
        """
        Print a log message above the progress bar.
        
        Args:
            message: The message to print.
        """
        self.progress.console.print(message, highlight=False)


class Downloader:
    """
    Downloads audio from YouTube and saves with hard link architecture.
    
    This class implements PHASE 3 of the download workflow:
    1. Downloads audio to tracks/ directory (canonical files)
    2. Creates hard links in playlist directories
    
    Attributes:
        _database: Database for tracking download state.
        _file_manager: FileManager for file operations.
        _cookie_file: Optional cookies.txt for YouTube Premium.
        _num_threads: Number of parallel downloads.
    
    Thread Safety:
        The download_track() method is thread-safe. Multiple threads
        can download different tracks simultaneously.
    
    Note:
        This class does NOT handle lyrics fetching or metadata embedding.
        Those operations are handled by PHASE 4 and PHASE 5 respectively.
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
            output_dir: Base output directory (contains tracks/, playlists, etc.)
            cookie_file: Optional path to cookies.txt file for
                        YouTube Premium quality (256 kbps).
                        If None, downloads at 128 kbps.
            num_threads: Default number of parallel download threads.
        """
        self._database = database
        self._file_manager = FileManager(output_dir)
        self._cookie_file = cookie_file
        self._num_threads = num_threads
        
        # Validate cookie file exists if provided
        if self._cookie_file is not None:
            if not self._cookie_file.exists():
                logger.warning(
                    f"Cookie file not found: {self._cookie_file}. "
                    "Downloads will be limited to 128 kbps."
                )
                self._cookie_file = None
            else:
                logger.debug(f"Using cookies for premium quality: {self._cookie_file}")
    
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
                   Each dict must have 'spotify_id', 'youtube_url',
                   'name', 'artist', and other metadata fields.
            playlist_id: Playlist ID (used for logging context).
            num_threads: Override default thread count.
        
        Returns:
            DownloadStats with counts of success/failure.
        
        Behavior:
            1. Create thread pool with num_threads workers
            2. Submit download_track() task for each track
            3. Track progress with Rich progress bar
            4. Collect results and statistics
            5. Return final stats
        """
        threads = num_threads if num_threads is not None else self._num_threads
        stats = DownloadStats(total=len(tracks))
        
        if not tracks:
            logger.info("No tracks to download")
            return stats
        
        logger.info(f"Starting download of {len(tracks)} tracks with {threads} threads")
        
        with DownloadProgressBar(total=len(tracks), description="Downloading") as progress:
            with ThreadPoolExecutor(max_workers=threads) as executor:
                # Submit all download tasks
                future_to_track = {
                    executor.submit(self.download_track, track_data): track_data
                    for track_data in tracks
                }
                
                # Process completed tasks
                for future in as_completed(future_to_track):
                    track_data = future_to_track[future]
                    track_name = track_data.get("name", "Unknown")
                    artist = track_data.get("artist", "Unknown")
                    
                    try:
                        success = future.result()
                        if success:
                            stats.downloaded += 1
                            progress.update(success=True)
                        else:
                            stats.failed += 1
                            progress.update(success=False)
                    except Exception as e:
                        stats.failed += 1
                        progress.update(success=False)
                        logger.error(f"Unexpected error downloading {artist} - {track_name}: {e}")
        
        # Log final statistics
        logger.info(
            f"Download complete: {stats.downloaded}/{stats.total} successful, "
            f"{stats.failed} failed"
        )
        
        return stats
    
    def download_track(self, track_data: dict[str, Any]) -> bool:
        """
        Download a single track from YouTube and create playlist links.
        
        This method handles the PHASE 3 download workflow for one track:
        1. Download audio from YouTube
        2. Save to tracks/ directory with canonical name
        3. Update database with canonical path
        4. Create hard links in all playlist directories
        
        Args:
            track_data: Track data dictionary from database.
                       Required keys: spotify_id, youtube_url, name, artist
        
        Returns:
            True if download succeeded, False otherwise.
        
        Thread Safety:
            This method is thread-safe. Uses per-track temp directories.
        """
        # Extract track info
        spotify_id = track_data.get("spotify_id") or track_data.get("track_id")
        youtube_url = track_data.get("youtube_url")
        name = track_data.get("name", "Unknown")
        artist = track_data.get("artist", "Unknown")
        spotify_url = track_data.get("spotify_url", "")
        
        if not spotify_id or not youtube_url:
            logger.error(f"Missing required fields for track: {name}")
            return False
        
        # Check if canonical file already exists
        canonical_path = self._file_manager.get_canonical_path(artist, name)
        if canonical_path.exists():
            logger.debug(f"File already exists: {canonical_path.name}")
            # Still need to update database and create links
            self._database.mark_downloaded(spotify_id, canonical_path)
            self._file_manager.update_playlist_links_from_db(
                self._database, spotify_id, canonical_path, name, artist
            )
            return True
        
        logger.debug(f"Downloading: {artist} - {name}")
        
        # Create a unique temp directory for this download
        temp_dir = Path(tempfile.mkdtemp(prefix=f"spot_dl_{spotify_id[:8]}_"))
        
        try:
            # Download audio to temp directory
            downloaded_file = self._download_audio(youtube_url, temp_dir)
            
            if downloaded_file is None:
                log_download_failure(
                    logger,
                    track_name=name,
                    artist=artist,
                    spotify_url=spotify_url,
                    error_message="yt-dlp returned no file"
                )
                return False
            
            # Move to canonical location in tracks/
            shutil.move(str(downloaded_file), str(canonical_path))
            
            # Update database with canonical path
            self._database.mark_downloaded(spotify_id, canonical_path)
            
            # Create hard links in all playlist directories containing this track
            self._file_manager.update_playlist_links_from_db(
                self._database, spotify_id, canonical_path, name, artist
            )
            
            logger.debug(f"Downloaded: {artist} - {name} -> {canonical_path.name}")
            return True
            
        except DownloadError as e:
            log_download_failure(
                logger,
                track_name=name,
                artist=artist,
                spotify_url=spotify_url,
                error_message=str(e)
            )
            return False
        except Exception as e:
            log_download_failure(
                logger,
                track_name=name,
                artist=artist,
                spotify_url=spotify_url,
                error_message=f"Unexpected error: {e}"
            )
            return False
        finally:
            # Clean up temp directory
            self._cleanup_temp_files(temp_dir)
    
    def _download_audio(
        self,
        youtube_url: str,
        output_path: Path
    ) -> Path | None:
        """
        Download audio from YouTube using yt-dlp.
        
        Args:
            youtube_url: YouTube video URL to download.
            output_path: Directory for temporary download file.
        
        Returns:
            Path to the downloaded M4A file, or None if download failed.
        
        Raises:
            DownloadError: If download fails.
        """
        # Generate unique output template
        output_template = str(output_path / "%(id)s.%(ext)s")
        
        options = self._get_yt_dlp_options(output_template)
        
        try:
            with YoutubeDL(options) as ydl:
                # Extract info and download
                info = ydl.extract_info(youtube_url, download=True)
                
                if info is None:
                    raise DownloadError("yt-dlp returned no info")
                
                # Find the downloaded file
                video_id = info.get("id", "unknown")
                
                # Look for the m4a file (postprocessor converts to m4a)
                m4a_file = output_path / f"{video_id}.m4a"
                if m4a_file.exists():
                    return m4a_file
                
                # Fallback: look for any audio file
                for ext in [".m4a", ".webm", ".opus", ".mp3", ".mp4"]:
                    candidate = output_path / f"{video_id}{ext}"
                    if candidate.exists():
                        return candidate
                
                # Last resort: find any file in the directory
                for f in output_path.iterdir():
                    if f.is_file() and f.suffix in [".m4a", ".webm", ".opus", ".mp3", ".mp4"]:
                        return f
                
                raise DownloadError(f"Downloaded file not found in {output_path}")
                
        except Exception as e:
            if isinstance(e, DownloadError):
                raise
            raise DownloadError(f"yt-dlp error: {e}") from e
    
    def _get_yt_dlp_options(self, output_template: str) -> dict[str, Any]:
        """
        Build yt-dlp options dictionary.
        
        Args:
            output_template: Output path template for yt-dlp.
        
        Returns:
            Dictionary of yt-dlp options.
        """
        options: dict[str, Any] = {
            # Format selection: prefer m4a, fallback to best audio
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            
            # Output
            "outtmpl": output_template,
            
            # Quiet mode (we handle our own logging)
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            
            # Encoding
            "encoding": "UTF-8",
            
            # Retries
            "retries": 3,
            "fragment_retries": 3,
            
            # Postprocessors: convert to m4a
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "0",  # Best quality
                }
            ],
            
            # Don't keep intermediate files
            "keepvideo": False,
        }
        
        # Add cookies if available
        if self._cookie_file is not None:
            options["cookiefile"] = str(self._cookie_file)
        
        return options
    
    def _cleanup_temp_files(self, temp_dir: Path) -> None:
        """
        Clean up temporary download files.
        
        Args:
            temp_dir: Directory containing temp files.
        """
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        except Exception as e:
            logger.debug(f"Failed to clean up temp directory {temp_dir}: {e}")


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
        output_dir: Base output directory (contains tracks/, playlists, etc.)
        playlist_id: Playlist ID (used for logging context).
        cookie_file: Optional cookies.txt for Premium quality.
        num_threads: Number of parallel downloads.
    
    Returns:
        DownloadStats with download results.
    
    Behavior:
        1. Get tracks needing download from database (global)
        2. Create Downloader instance
        3. Download all tracks to tracks/ directory
        4. Create hard links in playlist directories
        5. Return statistics
    """
    tracks = database.get_tracks_needing_download()
    
    if not tracks:
        logger.info("No tracks to download")
        return DownloadStats(total=0)
    
    logger.info(f"Found {len(tracks)} tracks to download")
    
    downloader = Downloader(
        database=database,
        output_dir=output_dir,
        cookie_file=cookie_file,
        num_threads=num_threads
    )
    
    return downloader.download_tracks(tracks, playlist_id, num_threads)


def get_tracks_needing_download(database: Database, playlist_id: str | None = None) -> list[dict[str, Any]]:
    """
    Get tracks from database that need downloading.
    
    Convenience function for getting tracks to process in PHASE 3
    when running phases separately.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID (currently unused - downloads are global).
    
    Returns:
        List of track data dicts for tracks with youtube_url set
        but downloaded=False.
    """
    return database.get_tracks_needing_download()