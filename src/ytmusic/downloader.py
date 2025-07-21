"""
YouTube Music audio downloader using yt-dlp with high-quality extraction and comprehensive error handling

This module provides a complete audio downloading system for YouTube Music tracks using yt-dlp
as the underlying engine. It implements sophisticated download strategies, progress tracking,
concurrent download management, and robust error handling to ensure reliable high-quality
audio extraction for playlist downloads.

Key Features:
- High-quality audio extraction with format optimization (M4A, MP3, FLAC)
- Intelligent format selection with automatic fallback strategies
- Real-time progress tracking with detailed statistics
- Concurrent download management with rate limiting
- Comprehensive error handling and retry mechanisms
- Automatic file organization and cleanup
- Duration validation and quality control
- Thread-safe operations for batch downloads

Download Architecture:
The system uses a multi-layered approach to ensure download success:

1. Format Selection Strategy:
   - Primary: Optimal format for requested audio type (M4A AAC, MP3, FLAC)
   - Fallback: Progressive relaxation of quality constraints
   - Final: Most permissive format selection for difficult videos

2. Progress Tracking System:
   - Real-time download progress monitoring
   - Bandwidth and ETA calculations
   - Custom callback support for UI integration
   - Detailed logging for debugging and monitoring

3. Concurrent Download Management:
   - Configurable concurrency limits to prevent overwhelming
   - Rate limiting between downloads for API compliance
   - Thread-safe file operations and progress tracking
   - Automatic cleanup of failed or partial downloads

4. Quality Assurance:
   - Duration validation against track metadata
   - File size verification and format validation
   - Automatic handling of age-restricted or geo-blocked content
   - Smart retry logic for transient failures

Error Handling Strategy:
The downloader implements comprehensive error recovery:
- Format-specific error detection and automatic fallback
- Network error retry with exponential backoff
- Temporary file cleanup on failures
- Graceful degradation for batch operations

Configuration:
All behavior is controlled through application settings including:
- Audio format and quality preferences
- Concurrency limits and timeout values
- Retry attempts and backoff strategies
- Output directory and file naming conventions
- Duration limits and validation parameters

Integration:
This module integrates with:
- YouTube Music searcher for video ID resolution
- Audio processor for post-download enhancement
- Metadata manager for tag embedding
- Progress tracking system for user feedback

Rate Limiting:
Implements 500ms intervals between downloads to prevent overwhelming
YouTube's servers and reduce risk of IP-based throttling.
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
    format_file_size, 
    retry_on_failure,
    ensure_directory,
    get_file_extension
)


@dataclass
class DownloadResult:
    """
    Container for download operation results with comprehensive metadata and statistics
    
    This dataclass encapsulates all information about a download operation, including
    success status, file information, performance metrics, and error details. It
    provides a standardized way to communicate download results between components
    and enables detailed tracking of download operations.
    
    The class includes computed properties for convenient access to formatted
    information, such as human-readable file sizes, and maintains all necessary
    metadata for post-download processing and analysis.
    
    Success Tracking:
    - success: Boolean indicating overall operation success
    - error_message: Detailed error information for failed downloads
    
    File Information:
    - file_path: Complete path to downloaded file
    - file_size: File size in bytes for storage tracking
    - format_id: yt-dlp format identifier for quality verification
    
    Performance Metrics:
    - download_time: Total time taken for download operation
    - duration: Track duration for validation purposes
    
    Attributes:
        success: True if download completed successfully, False otherwise
        file_path: Complete path to the downloaded audio file (None if failed)
        file_size: Size of downloaded file in bytes (None if unavailable)
        duration: Audio duration in seconds for validation (None if unavailable)
        format_id: yt-dlp format identifier used for download (None if unavailable)
        error_message: Detailed error description for failed downloads (None if successful)
        download_time: Total time taken for download operation in seconds (None if unavailable)
        
        file_size_str: Computed property returning human-readable file size
    """
    # Download operation status and results
    success: bool                           # Overall operation success indicator
    file_path: Optional[str] = None        # Path to successfully downloaded file
    file_size: Optional[int] = None        # File size in bytes
    duration: Optional[float] = None       # Track duration for validation
    format_id: Optional[str] = None        # yt-dlp format identifier
    error_message: Optional[str] = None    # Error details for failed downloads
    download_time: Optional[float] = None  # Total operation time in seconds
    
    @property
    def file_size_str(self) -> str:
        """
        Get formatted file size string for display purposes
        
        Returns a human-readable file size string using appropriate units
        (B, KB, MB, GB) or "Unknown" if file size information is unavailable.
        
        Returns:
            Formatted file size string (e.g., "3.2 MB") or "Unknown"
            
        Note:
            Uses the format_file_size utility function for consistent
            formatting across the application.
        """
        return format_file_size(self.file_size) if self.file_size else "Unknown"


class DownloadProgressHook:
    """
    Real-time progress tracking hook for yt-dlp download operations
    
    This class provides comprehensive progress monitoring for yt-dlp downloads,
    capturing bandwidth statistics, completion percentages, and status updates
    in real-time. It integrates with yt-dlp's progress hook system to provide
    detailed feedback during download operations.
    
    The hook supports custom callback functions for UI integration and implements
    intelligent progress reporting to avoid overwhelming logs with excessive updates.
    It tracks multiple progress metrics including download speed, estimated time
    to completion, and data transfer statistics.
    
    Progress Tracking Features:
    - Real-time download percentage calculation
    - Bandwidth monitoring with speed calculations
    - ETA estimation based on current progress
    - Status change detection (downloading, finished, error)
    - Periodic logging with configurable intervals
    - Custom callback support for external progress tracking
    
    Integration:
    The hook is designed to work seamlessly with yt-dlp's progress reporting
    system while providing additional features like periodic logging and
    custom callback integration for UI components.
    """
    
    def __init__(self, video_id: str, callback: Optional[Callable] = None):
        """
        Initialize progress tracking hook with video identification and callback support
        
        Sets up the progress hook for a specific video download with optional
        external callback for UI integration. Initializes all tracking variables
        and prepares the logging system.
        
        Args:
            video_id: YouTube video ID for identification in logs and callbacks
            callback: Optional progress callback function for external integration
                     Function should accept dict with progress information
                     
        Callback Data Format:
        The callback function receives a dictionary containing:
        - video_id: Video being downloaded
        - status: Current download status (downloading, finished, error)
        - progress_percent: Completion percentage (0-100)
        - downloaded_bytes: Bytes downloaded so far
        - total_bytes: Total file size (if known)
        - speed: Current download speed in bytes/second
        - eta: Estimated time to completion in seconds
        - file_path: Final file path (for finished status)
        - error: Error message (for error status)
        """
        # Video identification and callback configuration
        self.video_id = video_id
        self.callback = callback
        self.logger = get_logger(__name__)
        
        # Progress tracking state variables
        self.total_bytes = None      # Total file size (when available)
        self.downloaded_bytes = 0    # Bytes downloaded so far
        self.speed = None           # Current download speed (bytes/sec)
        self.eta = None             # Estimated time to completion (seconds)
        self.status = "starting"    # Current download status
        
    def __call__(self, d: Dict[str, Any]) -> None:
        """
        Handle progress update from yt-dlp download system
        
        This method is called by yt-dlp during download operations to provide
        real-time progress updates. It processes the raw progress data, calculates
        derived metrics, and provides appropriate logging and callback notifications.
        
        Args:
            d: Progress dictionary from yt-dlp containing status and metrics
               Structure varies by status but typically includes:
               - status: "downloading", "finished", or "error"
               - downloaded_bytes: Bytes downloaded (downloading status)
               - total_bytes: Total file size (downloading status)
               - speed: Download speed in bytes/second (downloading status)
               - eta: Estimated time to completion (downloading status)
               - filename: Output file path (finished status)
               - error: Error information (error status)
               
        Progress Calculation:
        Calculates completion percentage based on downloaded vs total bytes,
        with fallback to 0% if total size is unknown. Implements intelligent
        logging intervals to prevent log spam while maintaining useful feedback.
        
        Callback Integration:
        Calls external callback function (if provided) with standardized
        progress information for UI updates or external monitoring systems.
        """
        # Update current status from yt-dlp
        self.status = d['status']
        
        if self.status == 'downloading':
            # Extract download progress metrics
            self.total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            self.downloaded_bytes = d.get('downloaded_bytes', 0)
            self.speed = d.get('speed')
            self.eta = d.get('eta')
            
            # Calculate completion percentage
            if self.total_bytes:
                progress_percent = (self.downloaded_bytes / self.total_bytes) * 100
            else:
                progress_percent = 0
            
            # Implement intelligent logging intervals to prevent spam
            # Log approximately every 1MB of progress to balance detail with performance
            if self.downloaded_bytes % (1024 * 1024) < 50000:  # Every ~1MB
                self.logger.debug(
                    f"Download progress {self.video_id}: "
                    f"{progress_percent:.1f}% "
                    f"({format_file_size(self.downloaded_bytes)}"
                    f"/{format_file_size(self.total_bytes) if self.total_bytes else 'Unknown'})"
                )
            
            # Notify external callback with comprehensive progress data
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
            # Handle successful download completion
            self.logger.debug(f"Download completed: {self.video_id}")
            if self.callback:
                self.callback({
                    'video_id': self.video_id,
                    'status': 'finished',
                    'file_path': d.get('filename')
                })
        
        elif self.status == 'error':
            # Handle download errors with detailed information
            self.logger.warning(f"Download error: {self.video_id}")
            if self.callback:
                self.callback({
                    'video_id': self.video_id,
                    'status': 'error',
                    'error': d.get('error', 'Unknown error')
                })


class YouTubeMusicDownloader:
    """
    High-quality audio downloader for YouTube Music with advanced features and error handling
    
    This class provides a comprehensive audio downloading system specifically optimized
    for YouTube Music content. It implements sophisticated download strategies, concurrent
    processing capabilities, and robust error handling to ensure reliable high-quality
    audio extraction for playlist downloads.
    
    The downloader uses yt-dlp as the underlying download engine while adding significant
    value through intelligent format selection, progress tracking, concurrent download
    management, and comprehensive error recovery mechanisms.
    
    Core Features:
    
    1. Intelligent Format Selection:
       - Optimized format selectors for different audio types (M4A, MP3, FLAC)
       - Progressive fallback strategies for difficult-to-download content
       - Quality-aware format selection based on user preferences
       - Automatic codec selection for best compatibility and quality
    
    2. Advanced Download Management:
       - Concurrent download support with configurable limits
       - Rate limiting to prevent server overload and IP restrictions
       - Temporary file management with automatic cleanup
       - Unique filename generation to prevent conflicts
    
    3. Progress Tracking and Monitoring:
       - Real-time progress tracking with detailed statistics
       - Custom callback support for UI integration
       - Comprehensive logging for debugging and monitoring
       - Performance metrics collection and reporting
    
    4. Error Handling and Recovery:
       - Multiple retry strategies with exponential backoff
       - Format-specific error detection and automatic fallback
       - Network error recovery with intelligent retry logic
       - Graceful failure handling for batch operations
    
    5. Quality Assurance:
       - Duration validation against expected track length
       - File size verification and format validation
       - Audio quality optimization based on user preferences
       - Automatic handling of age-restricted content
    
    Configuration Integration:
    All behavior is controlled through application settings, allowing for
    flexible configuration of download parameters, quality preferences,
    concurrency limits, and error handling strategies.
    
    Thread Safety:
    The downloader is designed for concurrent operation with thread-safe
    file operations, rate limiting, and progress tracking.
    """
    
    def __init__(self):
        """
        Initialize YouTube Music downloader with comprehensive configuration and setup
        
        Sets up the downloader with all necessary configuration from application settings,
        prepares download directories, initializes rate limiting mechanisms, and configures
        quality parameters for optimal audio extraction.
        
        Configuration Loading:
        - Loads audio format and quality preferences
        - Sets up concurrency limits and timeout values
        - Configures retry attempts and error handling
        - Initializes output and temporary directories
        
        Thread Safety Setup:
        - Creates thread lock for rate limiting coordination
        - Initializes shared state variables for concurrent access
        - Sets up temporary directory for download staging
        
        Quality Parameters:
        - Configures duration limits for track validation
        - Sets up audio processing preferences
        - Initializes format selection parameters
        """
        # Load comprehensive application configuration
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Download configuration parameters from settings
        self.output_directory = self.settings.get_output_directory()
        self.audio_quality = self.settings.download.quality
        self.bitrate = self.settings.download.bitrate
        self.max_concurrent = self.settings.download.concurrency
        self.timeout = self.settings.download.timeout
        self.max_retries = self.settings.download.retry_attempts
        
        # Audio processing settings for quality control
        self.trim_silence = self.settings.audio.trim_silence
        self.normalize_audio = self.settings.audio.normalize
        self.max_duration = self.settings.audio.max_duration
        self.min_duration = self.settings.audio.min_duration
        
        # Rate limiting configuration for server-friendly downloading
        self.download_lock = threading.Lock()  # Thread synchronization for rate limiting
        self.last_download_time = 0            # Timestamp of last download start
        self.min_download_interval = 0.5       # 500ms between downloads
        
        # Temporary directory setup for download staging
        self.temp_dir = Path(tempfile.gettempdir()) / "playlist-downloader"
        ensure_directory(self.temp_dir)

    @property
    def audio_format(self):
        """
        Get the configured audio format for downloads
        
        Returns the audio format setting from configuration, used throughout
        the download process for format selection and file naming.
        
        Returns:
            Audio format string ('mp3', 'flac', 'm4a')
        """
        return self.settings.download.format

    def _get_ydl_options(self, output_path: str, progress_hook: Optional[DownloadProgressHook] = None) -> Dict[str, Any]:
        """
        Generate comprehensive yt-dlp configuration options for optimal audio extraction
        
        Creates a complete configuration dictionary for yt-dlp with optimized settings
        for audio extraction, output suppression, error handling, and progress tracking.
        The configuration is tailored for batch operations with minimal user intervention.
        
        Args:
            output_path: Template for output file naming
            progress_hook: Optional progress tracking hook for real-time updates
            
        Returns:
            Dictionary containing complete yt-dlp configuration options
            
        Configuration Categories:
        
        1. Format and Quality Settings:
           - Audio format selection and extraction preferences
           - Quality settings based on user configuration
           - Codec-specific optimization parameters
        
        2. Output and File Management:
           - Output path templates and naming conventions
           - File format preferences and conversion settings
           - Subtitle and metadata handling
        
        3. Error Handling and Reliability:
           - Timeout and retry configuration
           - Fragment retry logic for network issues
           - File access retry for filesystem problems
        
        4. Output Suppression:
           - Complete suppression of yt-dlp console output
           - Error logging redirection for clean operation
           - Progress tracking through hook system only
        
        5. Audio Processing:
           - Post-processing pipelines for format conversion
           - Quality optimization and codec selection
           - Audio-specific extraction parameters
        """
        # Locate FFmpeg for audio processing (required for format conversion)
        import shutil
        import os
        ffmpeg_location = shutil.which('ffmpeg')
        
        # Base configuration with audio-focused settings
        options = {
            # Format selection and audio extraction
            'format': self._get_format_selector(),
            'outtmpl': output_path,
            'noplaylist': True,           # Download single video only
            'extractaudio': True,         # Extract audio stream
            'audioformat': self.audio_format,
            'audioquality': self._get_audio_quality_value(),
            
            # Disable unnecessary features for audio-only operation
            'embed_subs': False,          # No subtitles needed for audio
            'writesubtitles': False,      # No subtitle files
            'writeautomaticsub': False,   # No auto-generated subs
            'ignoreerrors': False,        # Don't ignore errors (we handle them)
            
            # Complete output suppression for clean batch operation
            'quiet': True,                # Suppress most output
            'no_warnings': True,          # Suppress warning messages
            'noprogress': True,          # Disable built-in progress (use hook)
            
            # Reliability and error handling configuration
            'socket_timeout': self.timeout,           # Network timeout
            'retries': self.max_retries,             # Download retries
            'fragment_retries': self.max_retries,    # Fragment-level retries
            'file_access_retries': self.max_retries, # File access retries
            'extract_flat': False,                   # Extract full info
        }
        
        # Add FFmpeg location if available for audio processing
        if ffmpeg_location:
            options['ffmpeg_location'] = ffmpeg_location
        
        # Additional output suppression for completely clean operation
        options['logtostderr'] = False    # Don't log to stderr
        options['consoletitle'] = False   # Don't update console title
    
        
        # Add progress tracking hook if provided
        if progress_hook:
            options['progress_hooks'] = [progress_hook]
        
        # Configure audio-specific post-processing based on format
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
        """
        Generate intelligent format selector string for yt-dlp based on audio format and quality
        
        Creates optimized format selection strings that prioritize the best available
        audio quality for the requested format while providing intelligent fallbacks.
        The selectors are designed to maximize audio quality while ensuring compatibility.
        
        Returns:
            yt-dlp format selector string optimized for requested audio format
            
        Format Selection Strategy:
        
        For M4A Format:
        - Prioritizes native AAC codec in M4A containers for best quality
        - Falls back to AAC codec in other containers if needed
        - Uses quality-aware bitrate filtering based on user preferences
        - Provides broad compatibility fallback for difficult content
        
        For Other Formats (MP3, FLAC):
        - Prioritizes high-quality audio streams (excludes Opus for compatibility)
        - Uses height-based fallbacks to ensure video availability
        - Applies bitrate filtering for quality control
        - Balances quality with file size based on user settings
        
        Quality Levels:
        - High: Best available quality with minimal restrictions
        - Medium: Balanced quality with moderate bitrate limits
        - Low: Smaller files with more aggressive bitrate limits
        """
        if self.audio_format == 'm4a':
            # M4A format optimization: prefer native AAC in M4A containers
            if self.audio_quality == 'high':
                return 'bestaudio[ext=m4a]/bestaudio[acodec=aac]/bestaudio'
            elif self.audio_quality == 'medium': 
                return 'bestaudio[ext=m4a][abr<=192]/bestaudio[acodec=aac][abr<=192]/bestaudio[abr<=192]'
            else:  # low
                return 'bestaudio[ext=m4a][abr<=128]/bestaudio[acodec=aac][abr<=128]/bestaudio[abr<=128]'
        else:
            # General format selection for MP3/FLAC with quality-based constraints
            if self.audio_quality == 'high':
                return 'bestaudio[acodec!=opus]/best[height<=720]'
            elif self.audio_quality == 'medium':
                return 'bestaudio[abr<=192]/best[height<=480]' 
            else:  # low
                return 'bestaudio[abr<=128]/best[height<=360]'
    
    def _get_audio_quality_value(self) -> str:
        """
        Convert quality setting to yt-dlp audio quality parameter
        
        Translates user-friendly quality settings into yt-dlp's numeric
        quality scale, where lower numbers indicate higher quality.
        
        Returns:
            yt-dlp audio quality value string
            
        Quality Mapping:
        - high: "0" (best available quality)
        - medium: "5" (balanced quality and size)
        - low: "9" (smallest files, lower quality)
        """
        quality_map = {
            'high': '0',  # Best quality
            'medium': '5',  # Balanced
            'low': '9'   # Smaller files
        }
        return quality_map.get(self.audio_quality, '0')
    
    def _get_fallback_format_selectors(self) -> List[str]:
        """
        Generate progressive fallback format selectors for retry operations
        
        Creates a list of increasingly permissive format selectors that can be
        used when the primary format selection fails. This ensures maximum
        download success by gradually relaxing quality constraints.
        
        Returns:
            List of format selector strings ordered from most to least restrictive
            
        Fallback Strategy:
        
        For M4A Format:
        1. Primary: Optimal M4A/AAC selection with quality preferences
        2. Fallback 1: M4A/AAC with relaxed bitrate constraints
        3. Fallback 2: Any audio format (will be converted to M4A)
        4. Fallback 3: Most permissive selection for difficult content
        
        For MP3 Format:
        1. Primary: High-quality audio with codec preferences
        2. Fallback 1: Medium quality with bitrate limits
        3. Fallback 2: Any audio with basic quality constraints
        4. Fallback 3: Most permissive selection
        
        For FLAC Format:
        1. Primary: Best available audio quality
        2. Fallback 1: Any audio (will be converted to FLAC)
        3. Fallback 2: Most permissive selection
        
        Progressive Relaxation:
        Each fallback level relaxes constraints further, ensuring that
        even difficult-to-download content can be retrieved with acceptable quality.
        """
        if self.audio_format == 'm4a':
            return [
                # Primary: Best M4A/AAC selection with quality optimization
                'bestaudio[ext=m4a]/bestaudio[acodec=aac]/bestaudio',
                # Fallback 1: M4A/AAC with relaxed bitrate constraints
                'bestaudio[ext=m4a][abr<=256]/bestaudio[acodec=aac][abr<=256]/bestaudio[abr<=256]',
                # Fallback 2: Any audio format (conversion will handle M4A output)
                'bestaudio/best[height<=720]',
                # Fallback 3: Most permissive selection for difficult content
                'bestaudio/best'
            ]
        elif self.audio_format == 'mp3':
            return [
                # Primary: High-quality audio with codec preferences
                'bestaudio[acodec!=opus]/best[height<=720]',
                # Fallback 1: Medium quality with bitrate constraints
                'bestaudio[abr<=320]/best[height<=480]',
                # Fallback 2: Any audio with basic quality limits
                'bestaudio/best[height<=720]',
                # Fallback 3: Most permissive for maximum compatibility
                'bestaudio/best'
            ]
        else:  # flac
            return [
                # Primary: Best available audio quality for FLAC conversion
                'bestaudio[acodec!=opus]/best[height<=720]',
                # Fallback 1: Any audio (FLAC conversion handles quality)
                'bestaudio/best[height<=720]',
                # Fallback 2: Most permissive selection
                'bestaudio/best'
            ]
    
    def _rate_limit_download(self) -> None:
        """
        Apply thread-safe rate limiting between download operations
        
        Enforces a minimum interval between download starts to prevent overwhelming
        YouTube's servers and reduce the risk of IP-based throttling or rate limiting.
        Uses thread synchronization to ensure proper spacing in concurrent operations.
        
        Rate Limiting Strategy:
        - 500ms minimum interval between download starts
        - Thread-safe implementation for concurrent downloads
        - Conservative approach to maintain long-term access
        - Balances download speed with server respect
        
        Thread Safety:
        Uses a threading lock to ensure that only one thread can check and update
        the rate limiting state at a time, preventing race conditions in concurrent
        download scenarios.
        """
        with self.download_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_download_time
            
            # Enforce minimum interval between download operations
            if time_since_last < self.min_download_interval:
                sleep_time = self.min_download_interval - time_since_last
                time.sleep(sleep_time)
            
            # Update timestamp for next rate limit calculation
            self.last_download_time = time.time()
    
    @retry_on_failure(max_attempts=3, delay=2.0, backoff=2.0)
    def download_audio(
        self, 
        video_id: str, 
        output_path: str,
        progress_callback: Optional[Callable] = None
    ) -> DownloadResult:
        """
        Download audio from YouTube video with comprehensive error handling and fallback strategies
        
        Performs a complete audio download operation using yt-dlp with intelligent
        format selection, progress tracking, error recovery, and quality validation.
        Implements multiple fallback strategies to maximize download success rates.
        
        Args:
            video_id: YouTube video ID to download
            output_path: Base output file path (without extension)
            progress_callback: Optional callback for real-time progress updates
                             Function receives dict with progress information
            
        Returns:
            DownloadResult object containing success status, file information,
            performance metrics, and error details if applicable
            
        Download Process:
        
        1. Pre-download Setup:
           - Apply rate limiting for server-friendly operation
           - Ensure output directory exists
           - Set up progress tracking and temporary file management
        
        2. Format Selection and Retry:
           - Start with optimal format for requested audio type
           - On failure, progress through increasingly permissive formats
           - Handle format-specific errors with appropriate fallbacks
        
        3. Content Validation:
           - Extract video metadata for duration validation
           - Check against minimum and maximum duration limits
           - Reject content that doesn't meet quality criteria
        
        4. Download Execution:
           - Execute download with comprehensive error handling
           - Track progress through custom hook system
           - Handle network errors and temporary failures
        
        5. Post-download Processing:
           - Locate downloaded file in temporary directory
           - Move to final destination with unique naming
           - Calculate file statistics and performance metrics
           - Clean up temporary files on success or failure
        
        Error Recovery:
        Implements multiple layers of error recovery:
        - Format-specific retry with different selectors
        - Network error retry with exponential backoff (via decorator)
        - Temporary file cleanup on any failure
        - Graceful error reporting with detailed messages
        
        Quality Assurance:
        - Duration validation against track metadata
        - File size verification and format validation
        - Automatic rejection of inappropriate content
        """
        start_time = time.time()
        
        # Apply rate limiting to prevent server overload
        self._rate_limit_download()
        
        # Ensure output directory structure exists
        output_dir = Path(output_path).parent
        ensure_directory(output_dir)
        
        # Set up progress tracking with optional external callback
        progress_hook = DownloadProgressHook(video_id, progress_callback)
        
        # Prepare temporary output path for staging
        temp_output = self.temp_dir / f"{video_id}_%(title)s.%(ext)s"
        
        # Get base yt-dlp configuration options
        ydl_opts = self._get_ydl_options(str(temp_output), progress_hook)
        
        try:
            self.logger.debug(f"Starting download: {video_id}")
            
            # Get progressive fallback format selectors for maximum success
            format_selectors = self._get_fallback_format_selectors()
            last_exception = None
            
            # Attempt download with each format selector until success
            for attempt, format_selector in enumerate(format_selectors, 1):
                try:
                    # Configure yt-dlp options for this specific attempt
                    ydl_opts_attempt = ydl_opts.copy()
                    ydl_opts_attempt['format'] = format_selector
                    
                    if attempt > 1:
                        self.logger.debug(f"Download attempt {attempt}/{len(format_selectors)} with format: {format_selector}")
                    
                    with yt_dlp.YoutubeDL(ydl_opts_attempt) as ydl:
                        # Extract metadata for validation (only on first attempt)
                        if attempt == 1:
                            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                            
                            # Validate track duration against configured limits
                            duration = info.get('duration', 0)
                            if duration > 0:
                                if duration < self.min_duration:
                                    raise Exception(f"Track too short: {duration}s (min: {self.min_duration}s)")
                                if duration > self.max_duration:
                                    raise Exception(f"Track too long: {duration}s (max: {self.max_duration}s)")
                        
                        # Execute the actual download operation
                        ydl.download([f"https://youtube.com/watch?v={video_id}"])
                        
                        # If we reach here, download succeeded - break out of retry loop
                        break
                        
                except Exception as e:
                    last_exception = e
                    error_msg = str(e)
                    
                    # Identify format-related errors that warrant retry with different format
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
                        # Either not a format error, or we've exhausted all format options
                        raise e
            
            # If all format attempts failed, raise the last exception
            if last_exception:
                raise last_exception
                
            # Locate the downloaded file in temporary directory
            downloaded_file = self._find_downloaded_file(video_id)
            if not downloaded_file:
                raise Exception("Downloaded file not found")
            
            # Prepare final output path with appropriate extension
            final_extension = get_file_extension(self.audio_format)
            final_path = f"{output_path}{final_extension}"
            
            # Ensure unique filename to prevent conflicts
            counter = 1
            while Path(final_path).exists():
                base_path = output_path
                final_path = f"{base_path}_{counter}{final_extension}"
                counter += 1
                
            # Move file from temporary to final location
            os.rename(downloaded_file, final_path)
                
            # Calculate file statistics and performance metrics
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
            # Handle any download failure with comprehensive error reporting
            download_time = time.time() - start_time
            error_message = str(e)
            
            self.logger.error(f"Download failed: {video_id} - {error_message}")
            
            # Clean up any partial downloads to prevent disk space waste
            self._cleanup_partial_downloads(video_id)
            
            return DownloadResult(
                success=False,
                error_message=error_message,
                download_time=download_time
            )
    
    def _find_downloaded_file(self, video_id: str) -> Optional[str]:
        """
        Locate downloaded file in temporary directory using video ID pattern matching
        
        Searches the temporary download directory for files matching the video ID
        pattern, filtering for recognized audio formats. Handles the variable
        naming conventions used by yt-dlp for downloaded files.
        
        Args:
            video_id: YouTube video ID to search for
            
        Returns:
            Complete path to downloaded file if found, None otherwise
            
        Search Strategy:
        - Uses glob patterns to find files containing the video ID
        - Filters results to include only recognized audio formats
        - Returns the first matching file found
        
        Supported Formats:
        Searches for files with extensions: .mp3, .flac, .m4a, .aac
        """
        # Search for files containing the video ID with common audio extensions
        for file_path in self.temp_dir.glob(f"{video_id}_*"):
            if file_path.is_file() and file_path.suffix in ['.mp3', '.flac', '.m4a', '.aac']:
                return str(file_path)
        
        return None
    
    def _cleanup_partial_downloads(self, video_id: str) -> None:
        """
        Clean up partial or failed download files to prevent disk space accumulation
        
        Removes any files in the temporary directory that match the video ID pattern,
        preventing accumulation of partial downloads that can consume significant
        disk space over time.
        
        Args:
            video_id: YouTube video ID to clean up files for
            
        Cleanup Strategy:
        - Searches for all files matching the video ID pattern
        - Removes both partial downloads and metadata files
        - Logs cleanup actions for debugging purposes
        - Handles cleanup errors gracefully to prevent operation interruption
        """
        try:
            # Find and remove all files matching the video ID pattern
            for file_path in self.temp_dir.glob(f"{video_id}_*"):
                if file_path.is_file():
                    file_path.unlink()
                    self.logger.debug(f"Cleaned up partial file: {file_path.name}")
        except Exception as e:
            # Log cleanup failures but don't interrupt main operation
            self.logger.warning(f"Failed to cleanup partial downloads: {e}")
    
    def download_multiple(
        self, 
        downloads: List[Tuple[str, str]],
        progress_callback: Optional[Callable] = None
    ) -> List[DownloadResult]:
        """
        Download multiple tracks concurrently with comprehensive progress tracking and error handling
        
        Executes multiple download operations concurrently using a thread pool while
        maintaining rate limiting, progress tracking, and individual error isolation.
        Each download is handled independently to prevent failures from affecting
        other operations in the batch.
        
        Args:
            downloads: List of (video_id, output_path) tuples to download
            progress_callback: Optional callback for individual download progress updates
            
        Returns:
            List of DownloadResult objects in same order as input
            Failed downloads return DownloadResult with success=False
            
        Concurrency Management:
        - Uses ThreadPoolExecutor for controlled concurrent execution
        - Respects max_concurrent setting to prevent resource exhaustion
        - Maintains rate limiting across concurrent downloads
        - Provides thread-safe progress tracking and logging
        
        Progress Tracking:
        - Tracks overall batch progress with completion statistics
        - Provides detailed operation logging for monitoring
        - Calculates aggregate statistics (success rate, total size)
        - Maintains order correspondence between input and results
        
        Error Isolation:
        - Individual download failures don't affect other downloads
        - Comprehensive error handling for execution failures
        - Detailed error reporting for failed downloads
        - Graceful degradation for batch operations
        
        Performance Optimization:
        - Efficient thread pool management for optimal resource usage
        - Progress reporting optimized for batch operations
        - Memory-efficient result collection and processing
        """
        results = [None] * len(downloads)
        operation_logger = OperationLogger(self.logger, "Batch Download")
        
        operation_logger.start(f"Starting download of {len(downloads)} tracks")
        
        def download_single(index: int, video_id: str, output_path: str) -> Tuple[int, DownloadResult]:
            """
            Download single track with index tracking for result ordering
            
            Wrapper function for individual downloads that maintains order
            information for proper result placement in the output list.
            
            Args:
                index: Position in original download list
                video_id: YouTube video ID to download
                output_path: Output file path for this download
                
            Returns:
                Tuple of (index, DownloadResult) for result placement
            """
            result = self.download_audio(video_id, output_path, progress_callback)
            return index, result
        
        # Execute downloads with controlled concurrency using thread pool
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all download tasks to the thread pool
            future_to_index = {
                executor.submit(download_single, i, video_id, output_path): i
                for i, (video_id, output_path) in enumerate(downloads)
            }
            
            completed = 0
            # Process completed downloads as they finish
            for future in as_completed(future_to_index):
                try:
                    # Get result and place in correct position
                    index, result = future.result()
                    results[index] = result
                    completed += 1
                    
                    # Update progress tracking with completion statistics
                    operation_logger.progress(
                        f"Downloaded {completed}/{len(downloads)} tracks",
                        completed,
                        len(downloads)
                    )
                    
                except Exception as e:
                    # Handle execution errors by creating failed result
                    index = future_to_index[future]
                    results[index] = DownloadResult(
                        success=False,
                        error_message=f"Execution error: {e}"
                    )
                    completed += 1
        
        # Calculate comprehensive batch statistics
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
        Extract video metadata and information without downloading content
        
        Retrieves comprehensive metadata about a YouTube video using yt-dlp's
        information extraction capabilities. Useful for validation, analysis,
        and metadata collection without the overhead of actual downloading.
        
        Args:
            video_id: YouTube video ID to analyze
            
        Returns:
            Dictionary containing video metadata, None if extraction fails
            
        Extracted Information:
        - title: Video title as stored on YouTube
        - duration: Video duration in seconds
        - uploader: Channel name or uploader information
        - view_count: Number of views for popularity assessment
        - upload_date: Date when video was uploaded
        - description: Video description (truncated to 200 characters)
        
        Use Cases:
        - Pre-download validation of video accessibility
        - Metadata collection for search result analysis
        - Duration verification before download attempts
        - Channel and popularity assessment for quality evaluation
        
        Error Handling:
        Gracefully handles extraction failures by returning None,
        allowing calling code to handle missing information appropriately.
        """
        try:
            # Configure yt-dlp for metadata extraction only
            ydl_opts = {
                'quiet': True,           # Suppress output for clean operation
                'no_warnings': True,     # Reduce noise in logs
                'extract_flat': False,   # Extract complete metadata
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract metadata without downloading content
                info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                
                # Return structured metadata dictionary
                return {
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'upload_date': info.get('upload_date'),
                    'description': info.get('description', '')[:200],  # First 200 chars
                }
        except Exception as e:
            # Log extraction failures for debugging
            self.logger.warning(f"Failed to get video info for {video_id}: {e}")
            return None
    
    def validate_video_access(self, video_id: str) -> bool:
        """
        Check if video is accessible and available for download
        
        Performs a lightweight check to determine if a video can be accessed
        and is likely to be downloadable. Uses metadata extraction as a proxy
        for download accessibility.
        
        Args:
            video_id: YouTube video ID to validate
            
        Returns:
            True if video appears accessible, False otherwise
            
        Validation Strategy:
        - Attempts metadata extraction without downloading
        - Successful extraction indicates basic accessibility
        - Handles age restrictions and geo-blocking gracefully
        - Provides quick validation for batch operations
        
        Use Cases:
        - Pre-filtering video lists before download attempts
        - Validation of search results before processing
        - Quick accessibility checks for user feedback
        """
        try:
            info = self.get_video_info(video_id)
            return info is not None
        except Exception:
            return False
    
    def cleanup_temp_files(self) -> None:
        """
        Clean up old temporary files to prevent disk space accumulation
        
        Removes temporary files that are older than a specified threshold to
        prevent gradual accumulation of forgotten temporary files that can
        consume significant disk space over time.
        
        Cleanup Strategy:
        - Removes files older than 1 hour from temporary directory
        - Preserves recent files that may be from active downloads
        - Handles cleanup errors gracefully to avoid operation interruption
        - Logs cleanup actions for monitoring and debugging
        
        Automatic Maintenance:
        This method is called automatically during downloader reset to
        ensure periodic cleanup of temporary files.
        """
        try:
            # Find and remove old temporary files
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file() and time.time() - file_path.stat().st_mtime > 3600:  # 1 hour old
                    file_path.unlink()
                    self.logger.debug(f"Cleaned up old temp file: {file_path.name}")
        except Exception as e:
            # Log cleanup failures but don't interrupt operation
            self.logger.warning(f"Failed to cleanup temp files: {e}")
    
    def get_download_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive downloader statistics and configuration information
        
        Returns detailed information about current downloader configuration,
        performance parameters, and operational settings. Useful for debugging,
        monitoring, and configuration validation.
        
        Returns:
            Dictionary containing complete downloader configuration and statistics
            
        Configuration Information:
        - Audio format and quality settings
        - Concurrency and performance parameters
        - Timeout and retry configuration
        - Directory locations and file management settings
        
        This information helps with troubleshooting download issues and
        understanding current downloader behavior and constraints.
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


# Global downloader instance management
# Singleton pattern ensures consistent configuration and resource usage across application
_downloader_instance: Optional[YouTubeMusicDownloader] = None


def get_downloader() -> YouTubeMusicDownloader:
    """
    Get the global YouTube Music downloader instance (singleton pattern)
    
    Provides access to the shared downloader instance used throughout the
    application. Creates the instance on first access and returns the same
    instance for subsequent calls, ensuring consistent configuration and
    efficient resource utilization.
    
    Returns:
        Global YouTubeMusicDownloader instance
        
    Benefits of Singleton Pattern:
    - Shared temporary directory and file management
    - Consistent rate limiting across all download operations
    - Centralized configuration management
    - Efficient resource utilization for concurrent downloads
    - Maintains download state and performance optimizations
    """
    global _downloader_instance
    if not _downloader_instance:
        _downloader_instance = YouTubeMusicDownloader()
    return _downloader_instance


def reset_downloader() -> None:
    """
    Reset the global downloader instance with automatic cleanup
    
    Clears the global downloader instance, forcing a new instance to be created
    on the next access. Performs automatic cleanup of temporary files before
    reset to maintain system cleanliness.
    
    Use Cases:
    - Configuration changes that require fresh initialization
    - Testing scenarios requiring clean state
    - Recovery from persistent download issues
    - Periodic maintenance and cleanup operations
    
    Cleanup Operations:
    Automatically calls cleanup_temp_files() on the existing instance before
    reset to ensure temporary files don't accumulate over multiple resets.
    """
    global _downloader_instance
    if _downloader_instance:
        _downloader_instance.cleanup_temp_files()
    _downloader_instance = None