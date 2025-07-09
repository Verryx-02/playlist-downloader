"""
YouTube Music audio downloader using yt-dlp
Handles high-quality audio extraction with progress tracking and error handling
"""

import os
import time
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..config.settings import get_settings
from ..utils.logger import get_logger, OperationLogger
from ..utils.helpers import (
    sanitize_filename, 
    format_file_size, 
    format_duration,
    retry_on_failure,
    ensure_directory,
    get_file_extension
)


@dataclass
class DownloadResult:
    """Result of a download operation"""
    success: bool
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    format_id: Optional[str] = None
    error_message: Optional[str] = None
    download_time: Optional[float] = None
    
    @property
    def file_size_str(self) -> str:
        """Get formatted file size"""
        return format_file_size(self.file_size) if self.file_size else "Unknown"


class DownloadProgressHook:
    """Progress hook for yt-dlp downloads"""
    
    def __init__(self, video_id: str, callback: Optional[Callable] = None):
        """
        Initialize progress hook
        
        Args:
            video_id: YouTube video ID
            callback: Optional progress callback function
        """
        self.video_id = video_id
        self.callback = callback
        self.logger = get_logger(__name__)
        
        # Progress tracking
        self.total_bytes = None
        self.downloaded_bytes = 0
        self.speed = None
        self.eta = None
        self.status = "starting"
        
    def __call__(self, d: Dict[str, Any]) -> None:
        """Handle progress update from yt-dlp"""
        self.status = d['status']
        
        if self.status == 'downloading':
            self.total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            self.downloaded_bytes = d.get('downloaded_bytes', 0)
            self.speed = d.get('speed')
            self.eta = d.get('eta')
            
            # Calculate progress percentage
            if self.total_bytes:
                progress_percent = (self.downloaded_bytes / self.total_bytes) * 100
            else:
                progress_percent = 0
            
            # Log progress periodically
            if self.downloaded_bytes % (1024 * 1024) < 50000:  # Every ~1MB
                self.logger.debug(
                    f"Download progress {self.video_id}: "
                    f"{progress_percent:.1f}% "
                    f"({format_file_size(self.downloaded_bytes)}"
                    f"/{format_file_size(self.total_bytes) if self.total_bytes else 'Unknown'})"
                )
            
            # Call custom callback if provided
            if self.callback:
                self.callback({
                    'video_id': self.video_id,
                    'status': self.status,
                    'progress_percent': progress_percent,
                    'downloaded_bytes': self.downloaded_bytes,
                    'total_bytes': self.total_bytes,
                    'speed': self.speed,
                    'eta': self.eta
                })
        
        elif self.status == 'finished':
            self.logger.debug(f"Download completed: {self.video_id}")
            if self.callback:
                self.callback({
                    'video_id': self.video_id,
                    'status': 'finished',
                    'file_path': d.get('filename')
                })
        
        elif self.status == 'error':
            self.logger.warning(f"Download error: {self.video_id}")
            if self.callback:
                self.callback({
                    'video_id': self.video_id,
                    'status': 'error',
                    'error': d.get('error', 'Unknown error')
                })


class YouTubeMusicDownloader:
    """High-quality audio downloader for YouTube Music"""
    
    def __init__(self):
        """Initialize downloader with settings"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Download configuration
        self.output_directory = self.settings.get_output_directory()
        self.audio_quality = self.settings.download.quality
        self.bitrate = self.settings.download.bitrate
        self.max_concurrent = self.settings.download.concurrency
        self.timeout = self.settings.download.timeout
        self.max_retries = self.settings.download.retry_attempts
        
        # Audio processing settings
        self.trim_silence = self.settings.audio.trim_silence
        self.normalize_audio = self.settings.audio.normalize
        self.max_duration = self.settings.audio.max_duration
        self.min_duration = self.settings.audio.min_duration
        
        # Rate limiting
        self.download_lock = threading.Lock()
        self.last_download_time = 0
        self.min_download_interval = 0.5  # 500ms between downloads
        
        # Temporary directory for downloads
        self.temp_dir = Path(tempfile.gettempdir()) / "playlist-downloader"
        ensure_directory(self.temp_dir)

    @property
    def audio_format(self):
        return self.settings.download.format

    def _get_ydl_options(self, output_path: str, progress_hook: Optional[DownloadProgressHook] = None) -> Dict[str, Any]:
        """Get yt-dlp options with complete output suppression"""
        import shutil
        import os
        ffmpeg_location = shutil.which('ffmpeg')
        
        options = {
            'format': self._get_format_selector(),
            'outtmpl': output_path,
            'noplaylist': True,
            'extractaudio': True,
            'audioformat': self.audio_format,
            'audioquality': self._get_audio_quality_value(),
            'embed_subs': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': False,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'socket_timeout': self.timeout,
            'retries': self.max_retries,
            'fragment_retries': self.max_retries,
            'file_access_retries': self.max_retries,
            'extract_flat': False,
        }
        
        # Add FFmpeg location if found
        if ffmpeg_location:
            options['ffmpeg_location'] = ffmpeg_location
        
        # Suppress all output by redirecting to devnull
        options['logtostderr'] = False
        options['consoletitle'] = False
    
        
        # Add progress hook if provided
        if progress_hook:
            options['progress_hooks'] = [progress_hook]
        
        # Audio quality settings
        if self.audio_format == 'mp3':
            options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': str(self.bitrate),
            }]
        elif self.audio_format == 'flac':
            options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'flac',
            }]
        
        return options
    
    def _get_format_selector(self) -> str:
        """Get yt-dlp format selector for best audio quality"""
        if self.audio_format == 'm4a':
            # Per M4A: preferisci AAC nativo in container M4A
            if self.audio_quality == 'high':
                return 'bestaudio[ext=m4a]/bestaudio[acodec=aac]/bestaudio'
            elif self.audio_quality == 'medium': 
                return 'bestaudio[ext=m4a][abr<=192]/bestaudio[acodec=aac][abr<=192]/bestaudio[abr<=192]'
            else:  # low
                return 'bestaudio[ext=m4a][abr<=128]/bestaudio[acodec=aac][abr<=128]/bestaudio[abr<=128]'
        else:
            # Logica esistente per altri formati
            if self.audio_quality == 'high':
                return 'bestaudio[acodec!=opus]/best[height<=720]'
            elif self.audio_quality == 'medium':
                return 'bestaudio[abr<=192]/best[height<=480]' 
            else:  # low
                return 'bestaudio[abr<=128]/best[height<=360]'
    
    def _get_audio_quality_value(self) -> str:
        """Get audio quality value for yt-dlp"""
        quality_map = {
            'high': '0',  # Best quality
            'medium': '5',  # Balanced
            'low': '9'   # Smaller files
        }
        return quality_map.get(self.audio_quality, '0')
    
    def _get_fallback_format_selectors(self) -> List[str]:
        """Get progressively more permissive format selectors for retry"""
        if self.audio_format == 'm4a':
            return [
                # Primary: Best M4A/AAC
                'bestaudio[ext=m4a]/bestaudio[acodec=aac]/bestaudio',
                # Fallback 1: Any M4A/AAC with lower quality constraints
                'bestaudio[ext=m4a][abr<=256]/bestaudio[acodec=aac][abr<=256]/bestaudio[abr<=256]',
                # Fallback 2: Any audio, will be converted
                'bestaudio/best[height<=720]',
                # Fallback 3: Most permissive
                'bestaudio/best'
            ]
        elif self.audio_format == 'mp3':
            return [
                # Primary: Best audio
                'bestaudio[acodec!=opus]/best[height<=720]',
                # Fallback 1: Lower quality constraint
                'bestaudio[abr<=320]/best[height<=480]',
                # Fallback 2: Any audio
                'bestaudio/best[height<=720]',
                # Fallback 3: Most permissive
                'bestaudio/best'
            ]
        else:  # flac
            return [
                # Primary: Best audio
                'bestaudio[acodec!=opus]/best[height<=720]',
                # Fallback 1: Any audio
                'bestaudio/best[height<=720]',
                # Fallback 2: Most permissive
                'bestaudio/best'
            ]
    
    def _rate_limit_download(self) -> None:
        """Apply rate limiting between downloads"""
        with self.download_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_download_time
            
            if time_since_last < self.min_download_interval:
                sleep_time = self.min_download_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_download_time = time.time()
    
    @retry_on_failure(max_attempts=3, delay=2.0, backoff=2.0)
    def download_audio(
        self, 
        video_id: str, 
        output_path: str,
        progress_callback: Optional[Callable] = None
    ) -> DownloadResult:
        """
        Download audio from YouTube video
        
        Args:
            video_id: YouTube video ID
            output_path: Output file path (without extension)
            progress_callback: Optional progress callback
            
        Returns:
            DownloadResult with download information
        """
        start_time = time.time()
        
        # Apply rate limiting
        self._rate_limit_download()
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        ensure_directory(output_dir)
        
        # Create progress hook
        progress_hook = DownloadProgressHook(video_id, progress_callback)
        
        # Prepare temporary output path
        temp_output = self.temp_dir / f"{video_id}_%(title)s.%(ext)s"
        
        # Get yt-dlp options
        ydl_opts = self._get_ydl_options(str(temp_output), progress_hook)
        
        try:
            self.logger.debug(f"Starting download: {video_id}")
            
            # Get fallback format selectors for retry
            format_selectors = self._get_fallback_format_selectors()
            last_exception = None
            
            for attempt, format_selector in enumerate(format_selectors, 1):
                try:
                    # Update format selector for this attempt
                    ydl_opts_attempt = ydl_opts.copy()
                    ydl_opts_attempt['format'] = format_selector
                    
                    if attempt > 1:
                        self.logger.debug(f"Download attempt {attempt}/{len(format_selectors)} with format: {format_selector}")
                    
                    with yt_dlp.YoutubeDL(ydl_opts_attempt) as ydl:
                        # Extract info first to get metadata (only on first attempt)
                        if attempt == 1:
                            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                            
                            # Validate duration
                            duration = info.get('duration', 0)
                            if duration > 0:
                                if duration < self.min_duration:
                                    raise Exception(f"Track too short: {duration}s (min: {self.min_duration}s)")
                                if duration > self.max_duration:
                                    raise Exception(f"Track too long: {duration}s (max: {self.max_duration}s)")
                        
                        # Perform download
                        ydl.download([f"https://youtube.com/watch?v={video_id}"])
                        
                        # If we get here, download succeeded
                        break
                        
                except Exception as e:
                    last_exception = e
                    error_msg = str(e)
                    
                    # Check if it's a format-related error that we should retry
                    format_errors = [
                        'Requested format is not available',
                        'HTTP Error 403',
                        'HTTP Error 429',
                        'Unable to extract',
                        'format not available'
                    ]
                    
                    should_retry = any(err in error_msg for err in format_errors)
                    
                    if should_retry and attempt < len(format_selectors):
                        self.logger.debug(f"Format attempt {attempt} failed: {error_msg}, trying next format")
                        continue
                    else:
                        # Either not a format error, or we've exhausted all formats
                        raise e
            
            # If we exhausted all format attempts without success
            if last_exception:
                raise last_exception
                
# Find downloaded file
            downloaded_file = self._find_downloaded_file(video_id)
            if not downloaded_file:
                raise Exception("Downloaded file not found")
            
            # Move to final location
            final_extension = get_file_extension(self.audio_format)
            final_path = f"{output_path}{final_extension}"
            
            # Ensure unique filename
            counter = 1
            while Path(final_path).exists():
                base_path = output_path
                final_path = f"{base_path}_{counter}{final_extension}"
                counter += 1
                
            # Move file
            os.rename(downloaded_file, final_path)
                
            # Get file info
            file_size = Path(final_path).stat().st_size
            download_time = time.time() - start_time
                
            self.logger.debug(f"Download completed: {video_id} -> {Path(final_path).name} ({format_file_size(file_size)}, {download_time:.1f}s)")
                
            return DownloadResult(
                success=True,
                file_path=final_path,
                file_size=file_size,
                duration=duration,
                format_id=info.get('format_id'),
                download_time=download_time
            )
 
        except Exception as e:
            download_time = time.time() - start_time
            error_message = str(e)
            
            self.logger.error(f"Download failed: {video_id} - {error_message}")
            
            # Clean up any partial files
            self._cleanup_partial_downloads(video_id)
            
            return DownloadResult(
                success=False,
                error_message=error_message,
                download_time=download_time
            )
    
    def _find_downloaded_file(self, video_id: str) -> Optional[str]:
        """
        Find downloaded file in temp directory
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Path to downloaded file or None
        """
        # Look for files containing the video ID
        for file_path in self.temp_dir.glob(f"{video_id}_*"):
            if file_path.is_file() and file_path.suffix in ['.mp3', '.flac', '.m4a', '.aac']:
                return str(file_path)
        
        return None
    
    def _cleanup_partial_downloads(self, video_id: str) -> None:
        """
        Clean up partial download files
        
        Args:
            video_id: YouTube video ID
        """
        try:
            for file_path in self.temp_dir.glob(f"{video_id}_*"):
                if file_path.is_file():
                    file_path.unlink()
                    self.logger.debug(f"Cleaned up partial file: {file_path.name}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup partial downloads: {e}")
    
    def download_multiple(
        self, 
        downloads: List[Tuple[str, str]],
        progress_callback: Optional[Callable] = None
    ) -> List[DownloadResult]:
        """
        Download multiple tracks concurrently
        
        Args:
            downloads: List of (video_id, output_path) tuples
            progress_callback: Optional progress callback
            
        Returns:
            List of DownloadResult objects
        """
        results = [None] * len(downloads)
        operation_logger = OperationLogger(self.logger, "Batch Download")
        
        operation_logger.start(f"Starting download of {len(downloads)} tracks")
        
        def download_single(index: int, video_id: str, output_path: str) -> Tuple[int, DownloadResult]:
            """Download single track with index tracking"""
            result = self.download_audio(video_id, output_path, progress_callback)
            return index, result
        
        # Execute downloads with controlled concurrency
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all downloads
            future_to_index = {
                executor.submit(download_single, i, video_id, output_path): i
                for i, (video_id, output_path) in enumerate(downloads)
            }
            
            completed = 0
            for future in as_completed(future_to_index):
                try:
                    index, result = future.result()
                    results[index] = result
                    completed += 1
                    
                    operation_logger.progress(
                        f"Downloaded {completed}/{len(downloads)} tracks",
                        completed,
                        len(downloads)
                    )
                    
                except Exception as e:
                    index = future_to_index[future]
                    results[index] = DownloadResult(
                        success=False,
                        error_message=f"Execution error: {e}"
                    )
                    completed += 1
        
        # Calculate statistics
        successful = sum(1 for r in results if r and r.success)
        failed = len(results) - successful
        total_size = sum(r.file_size for r in results if r and r.file_size)
        
        operation_logger.complete(
            f"Batch download completed: {successful} successful, {failed} failed, "
            f"total size: {format_file_size(total_size)}"
        )
        
        return results
    
    def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get video information without downloading
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video information dictionary or None
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                return {
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'upload_date': info.get('upload_date'),
                    'description': info.get('description', '')[:200],  # First 200 chars
                }
        except Exception as e:
            self.logger.warning(f"Failed to get video info for {video_id}: {e}")
            return None
    
    def validate_video_access(self, video_id: str) -> bool:
        """
        Check if video is accessible for download
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            True if video is accessible
        """
        try:
            info = self.get_video_info(video_id)
            return info is not None
        except Exception:
            return False
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary download files"""
        try:
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file() and time.time() - file_path.stat().st_mtime > 3600:  # 1 hour old
                    file_path.unlink()
                    self.logger.debug(f"Cleaned up old temp file: {file_path.name}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temp files: {e}")
    
    def get_download_stats(self) -> Dict[str, Any]:
        """
        Get downloader statistics and configuration
        
        Returns:
            Dictionary with download stats
        """
        return {
            'audio_format': self.audio_format,
            'audio_quality': self.audio_quality,
            'bitrate': self.bitrate,
            'max_concurrent': self.max_concurrent,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'output_directory': str(self.output_directory),
            'temp_directory': str(self.temp_dir)
        }


# Global downloader instance
_downloader_instance: Optional[YouTubeMusicDownloader] = None


def get_downloader() -> YouTubeMusicDownloader:
    """Get global downloader instance"""
    global _downloader_instance
    if not _downloader_instance:
        _downloader_instance = YouTubeMusicDownloader()
    return _downloader_instance


def reset_downloader() -> None:
    """Reset global downloader instance"""
    global _downloader_instance
    if _downloader_instance:
        _downloader_instance.cleanup_temp_files()
    _downloader_instance = None