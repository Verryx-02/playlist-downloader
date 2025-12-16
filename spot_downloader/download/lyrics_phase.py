"""
Lyrics fetching phase (PHASE 4) for spot-downloader.

This module provides the orchestration for fetching lyrics for all
downloaded tracks that don't yet have lyrics.

PHASE 4 Workflow:
    1. Query database for tracks where downloaded=True and lyrics_fetched=False
    2. For each track:
       a. Attempt to fetch lyrics using LyricsFetcher
       b. If found: store lyrics in database
       c. If not found: log to lyrics_failures.log
       d. Mark lyrics_fetched=True regardless
    3. Report statistics

Usage:
    from spot_downloader.download.lyrics_phase import fetch_lyrics_phase4
    
    stats = fetch_lyrics_phase4(database, playlist_id, num_threads=4)
    print(f"Found lyrics for {stats.found}/{stats.total} tracks")
"""

from dataclasses import dataclass
from typing import Any

from spot_downloader.core.database import Database
from spot_downloader.core.logger import get_logger, log_lyrics_failure
from spot_downloader.download.lyrics import LyricsFetcher, Lyrics

logger = get_logger(__name__)


@dataclass
class LyricsStats:
    """
    Statistics from a lyrics fetch batch.
    
    Attributes:
        total: Total number of tracks processed.
        found: Tracks where lyrics were found.
        not_found: Tracks where no lyrics were found.
        synced: Tracks with synced (LRC) lyrics.
        plain: Tracks with plain text lyrics.
    """
    
    total: int = 0
    found: int = 0
    not_found: int = 0
    synced: int = 0
    plain: int = 0
    
    @property
    def found_rate(self) -> float:
        """Calculate lyrics found rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.found / self.total) * 100


def fetch_lyrics_phase4(
    database: Database,
    playlist_id: str,
    num_threads: int = 4
) -> LyricsStats:
    """
    Fetch lyrics for all downloaded tracks that need them.
    
    This is the main entry point for PHASE 4.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID to process.
        num_threads: Number of parallel fetching threads.
    
    Returns:
        LyricsStats with fetch results.
    
    Behavior:
        1. Get tracks needing lyrics from database
        2. Create LyricsFetcher instance
        3. For each track (in parallel):
           a. Call fetcher.fetch_lyrics()
           b. If lyrics found: call database.set_lyrics()
           c. If not found: call log_lyrics_failure(), then database.mark_lyrics_fetched()
        4. Log summary statistics
        5. Return stats
    
    Database Updates:
        - Sets lyrics_text, lyrics_synced, lyrics_source for found lyrics
        - Sets lyrics_fetched=True for ALL processed tracks
    
    Logging:
        - INFO: Phase start, completion with stats
        - DEBUG: Individual track processing
        - Calls log_lyrics_failure() for tracks without lyrics
    
    Thread Safety:
        Uses thread pool for parallel fetching.
        Database operations are thread-safe.
    """
    raise NotImplementedError("Contract only - implementation pending")


def _fetch_lyrics_for_track(
    fetcher: LyricsFetcher,
    track_data: dict[str, Any]
) -> Lyrics | None:
    """
    Fetch lyrics for a single track.
    
    Args:
        fetcher: LyricsFetcher instance.
        track_data: Track data from database.
    
    Returns:
        Lyrics object if found, None otherwise.
    
    Note:
        This is a helper function for parallel processing.
        It does not update the database - that's done by the caller.
    """
    raise NotImplementedError("Contract only - implementation pending")