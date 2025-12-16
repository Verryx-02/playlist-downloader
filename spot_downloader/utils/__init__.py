"""
Utility functions for spot-downloader.

This module provides common utility functions used across the application:
    - Filename sanitization (using yt-dlp's sanitize_filename)
    - Threading utilities for parallel processing
    - Path manipulation helpers

Usage:
    from spot_downloader.utils import (
        sanitize_filename,
        run_in_parallel,
        ensure_directory
    )
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from tqdm import tqdm
from yt_dlp.utils import sanitize_filename as yt_dlp_sanitize

from spot_downloader.core.logger import get_logger
from spot_downloader.utils.replace import replace_track_audio

logger = get_logger(__name__)


# Type variable for generic parallel processing
T = TypeVar("T")
R = TypeVar("R")


def sanitize_filename(name: str, restricted: bool = False) -> str:
    """
    Sanitize a string for use as a filename.
    
    Uses yt-dlp's sanitize_filename function for consistency with
    how yt-dlp names downloaded files.
    
    Args:
        name: The string to sanitize (e.g., track title, artist name).
        restricted: If True, use more aggressive sanitization that
                   removes all special characters. Default False.
    
    Returns:
        Sanitized string safe for use in filenames.
    
    Sanitization Rules:
        - Replaces path separators (/, \\) with underscore
        - Removes characters invalid on Windows (: * ? " < > |)
        - Handles Unicode characters appropriately
        - Trims leading/trailing whitespace
        - Collapses multiple spaces to single space
    
    Examples:
        sanitize_filename("Hello: World")  # "Hello_ World"
        sanitize_filename("AC/DC")         # "AC_DC"
        sanitize_filename("What?!")        # "What_!"
    
    Note:
        This wraps yt_dlp.utils.sanitize_filename to provide a
        consistent interface and allow for future customization.
    """
    return yt_dlp_sanitize(name, restricted=restricted)


def generate_track_filename(
    track_number: int,
    title: str,
    artist: str,
    extension: str = "m4a"
) -> str:
    """
    Generate a filename for a downloaded track.
    
    Creates a filename in the format: {number}-{title}-{artist}.{ext}
    
    Args:
        track_number: Sequential track number (1-indexed).
        title: Track title (will be sanitized).
        artist: Artist name (will be sanitized).
        extension: File extension without dot. Default "m4a".
    
    Returns:
        Complete filename string.
    
    Example:
        generate_track_filename(1, "Bohemian Rhapsody", "Queen")
        # Returns: "1-Bohemian Rhapsody-Queen.m4a"
        
        generate_track_filename(42, "Hello: World", "AC/DC")
        # Returns: "42-Hello_ World-AC_DC.m4a"
    """
    safe_title = sanitize_filename(title)
    safe_artist = sanitize_filename(artist)
    return f"{track_number}-{safe_title}-{safe_artist}.{extension}"


def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Path to the directory.
    
    Returns:
        The same path (for chaining).
    
    Raises:
        OSError: If directory cannot be created (permissions, etc.)
    
    Behavior:
        Creates the directory and all parent directories if they
        don't exist. Does nothing if directory already exists.
    
    Example:
        output_dir = ensure_directory(Path("~/Music/Downloads"))
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_in_parallel(
    func: Callable[[T], R],
    items: Iterable[T],
    num_threads: int = 4,
    description: str = "Processing",
    show_progress: bool = True
) -> list[tuple[T, R | Exception]]:
    """
    Run a function on multiple items in parallel with progress tracking.
    
    This is a generic utility for parallel processing with:
    - Thread pool execution
    - tqdm progress bar
    - Error collection (doesn't stop on failures)
    
    Args:
        func: Function to call for each item. Takes one argument.
        items: Iterable of items to process.
        num_threads: Number of parallel threads.
        description: Description for the progress bar.
        show_progress: Whether to show tqdm progress bar.
    
    Returns:
        List of (item, result) tuples where result is either the
        return value or an Exception if the call failed.
    
    Behavior:
        1. Create thread pool with num_threads workers
        2. Submit func(item) for each item
        3. Display progress bar as tasks complete
        4. Collect results (including exceptions)
        5. Return all results
    
    Error Handling:
        Exceptions are caught and returned in the result tuple.
        Processing continues for other items.
    
    Example:
        def download(url):
            # ... download logic
            return file_path
        
        urls = ["url1", "url2", "url3"]
        results = run_in_parallel(download, urls, num_threads=4)
        
        for url, result in results:
            if isinstance(result, Exception):
                print(f"Failed: {url} - {result}")
            else:
                print(f"Success: {url} -> {result}")
    """
    items_list = list(items)  # Materialize for length
    results: list[tuple[T, R | Exception]] = []
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all tasks
        future_to_item = {
            executor.submit(func, item): item
            for item in items_list
        }
        
        # Process completions with progress bar
        iterator = as_completed(future_to_item)
        if show_progress:
            iterator = tqdm(
                iterator,
                total=len(items_list),
                desc=description,
                unit="item"
            )
        
        for future in iterator:
            item = future_to_item[future]
            try:
                result = future.result()
                results.append((item, result))
            except Exception as e:
                results.append((item, e))
    
    return results


def run_in_parallel_with_callback(
    func: Callable[[T], R],
    items: Iterable[T],
    on_success: Callable[[T, R], None],
    on_error: Callable[[T, Exception], None],
    num_threads: int = 4,
    description: str = "Processing",
    show_progress: bool = True
) -> tuple[int, int]:
    """
    Run a function in parallel with callbacks for results.
    
    Similar to run_in_parallel but calls callbacks immediately
    as results become available, rather than collecting all results.
    
    Args:
        func: Function to call for each item.
        items: Iterable of items to process.
        on_success: Called with (item, result) on success.
        on_error: Called with (item, exception) on failure.
        num_threads: Number of parallel threads.
        description: Description for progress bar.
        show_progress: Whether to show progress bar.
    
    Returns:
        Tuple of (success_count, error_count).
    
    Use Case:
        When you need to process results immediately (e.g., update
        database) rather than waiting for all items to complete.
    
    Example:
        def on_download_success(track, file_path):
            database.mark_downloaded(track.id, file_path)
        
        def on_download_error(track, error):
            log_download_failure(track, str(error))
        
        success, errors = run_in_parallel_with_callback(
            download_track,
            tracks,
            on_success=on_download_success,
            on_error=on_download_error
        )
    """
    items_list = list(items)
    success_count = 0
    error_count = 0
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_item = {
            executor.submit(func, item): item
            for item in items_list
        }
        
        iterator = as_completed(future_to_item)
        if show_progress:
            iterator = tqdm(
                iterator,
                total=len(items_list),
                desc=description,
                unit="item"
            )
        
        for future in iterator:
            item = future_to_item[future]
            try:
                result = future.result()
                on_success(item, result)
                success_count += 1
            except Exception as e:
                on_error(item, e)
                error_count += 1
    
    return success_count, error_count


def extract_spotify_id(url_or_id: str) -> str:
    """
    Extract Spotify ID from a URL or return ID as-is.
    
    Handles various Spotify URL formats:
        - https://open.spotify.com/track/ID
        - https://open.spotify.com/track/ID?si=xxx
        - spotify:track:ID
        - Just the ID
    
    Args:
        url_or_id: Spotify URL or bare ID.
    
    Returns:
        The 22-character Spotify ID.
    
    Examples:
        extract_spotify_id("https://open.spotify.com/track/abc123?si=xyz")
        # Returns: "abc123"
        
        extract_spotify_id("spotify:track:abc123")
        # Returns: "abc123"
        
        extract_spotify_id("abc123")
        # Returns: "abc123"
    """
    # Handle spotify: URI format
    if url_or_id.startswith("spotify:"):
        parts = url_or_id.split(":")
        return parts[-1]
    
    # Handle URL format
    if "spotify.com" in url_or_id:
        # Remove query parameters
        url_or_id = url_or_id.split("?")[0]
        # Get last path segment
        return url_or_id.rstrip("/").split("/")[-1]
    
    # Assume it's already an ID
    return url_or_id


def extract_playlist_id(url: str) -> str:
    """
    Extract playlist ID from a Spotify playlist URL.
    
    Args:
        url: Spotify playlist URL.
    
    Returns:
        The playlist ID.
    
    Raises:
        ValueError: If URL is not a valid Spotify playlist URL.
    
    Examples:
        extract_playlist_id("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
        # Returns: "37i9dQZF1DXcBWIGoYBM5M"
    """
    if "playlist" not in url:
        raise ValueError(f"Not a playlist URL: {url}")
    return extract_spotify_id(url)


def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds.
    
    Returns:
        Formatted string like "3:45" or "1:02:30".
    
    Examples:
        format_duration(225)   # "3:45"
        format_duration(3750)  # "1:02:30"
        format_duration(45)    # "0:45"
    """
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"


def parse_duration(duration_str: str) -> int:
    """
    Parse duration string to seconds.
    
    Handles formats from YouTube Music API like "3:45" or "1:02:30".
    
    Args:
        duration_str: Duration string.
    
    Returns:
        Duration in seconds.
    
    Examples:
        parse_duration("3:45")     # 225
        parse_duration("1:02:30")  # 3750
    """
    parts = duration_str.split(":")
    parts = [int(p) for p in parts]
    
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        return int(parts[0])
