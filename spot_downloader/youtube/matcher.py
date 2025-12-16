"""
YouTube Music matching for spot-downloader (PHASE 2).

This module handles finding the best YouTube Music match for each
Spotify track. It uses the same matching algorithm as spotDL for
consistency and accuracy.

Matching Algorithm:
    1. Search YouTube Music using ISRC (if available)
    2. If no ISRC match, search by "Artist - Title"
    3. Filter results by duration (within tolerance)
    4. Score results by title/artist similarity using rapidfuzz
    5. Prefer verified/official results over user uploads
    6. Return best match or None if no suitable match found

PHASE 2 Workflow:
    1. Get tracks without YouTube URL from database
    2. For each track, search YouTube Music
    3. Apply matching algorithm to find best result
    4. Store YouTube URL in database (or mark as failed)
    5. Return match statistics

Dependencies:
    - ytmusicapi: YouTube Music API client
    - rapidfuzz: Fuzzy string matching (same as spotDL)

Usage:
    from spot_downloader.youtube.matcher import YouTubeMatcher
    
    matcher = YouTubeMatcher(database)
    results = matcher.match_tracks(tracks, num_threads=4)
    
    # results contains MatchResult for each track
    matched = [r for r in results if r.matched]
    failed = [r for r in results if not r.matched]
"""

from typing import Any

from ytmusicapi import YTMusic

from spot_downloader.core.database import Database
from spot_downloader.core.logger import get_logger
from spot_downloader.spotify.models import Track
from spot_downloader.youtube.models import MatchResult, YouTubeResult

logger = get_logger(__name__)


# Duration tolerance for matching (seconds)
# If YouTube duration differs by more than this, result is rejected
DURATION_TOLERANCE_SECONDS = 10

# Minimum similarity score (0-100) for title/artist matching
# Below this threshold, result is rejected even if duration matches
MIN_SIMILARITY_SCORE = 70

# Search options for ytmusicapi (mirrors spotDL configuration)
SEARCH_OPTIONS = [
    {"filter": "songs", "ignore_spelling": True, "limit": 50},
    {"filter": "videos", "ignore_spelling": True, "limit": 50},
]


class YouTubeMatcher:
    """
    Matches Spotify tracks to YouTube Music videos/songs.
    
    This class implements PHASE 2 of the download workflow. It takes
    Track objects from PHASE 1 and finds the corresponding YouTube
    Music URL for each.
    
    Attributes:
        _database: Database instance for storing match results.
        _ytmusic: ytmusicapi YTMusic client instance.
    
    Thread Safety:
        The match_track() method is thread-safe and can be called
        from multiple threads simultaneously. Database operations
        use internal locking.
    
    Matching Strategy:
        1. ISRC Search (highest accuracy):
           If track has ISRC code, search YouTube Music using it.
           ISRC matches are very reliable.
        
        2. Text Search (fallback):
           Search using "Artist - Title" query.
           Score results using fuzzy string matching.
        
        3. Duration Filter:
           Reject results with duration difference > DURATION_TOLERANCE.
        
        4. Verification Preference:
           Prefer "songs" (verified/official) over "videos" (user uploads).
    
    Example:
        matcher = YouTubeMatcher(database)
        
        # Match single track
        result = matcher.match_track(track)
        if result.matched:
            print(f"Found: {result.youtube_url}")
        
        # Match multiple tracks with threading
        results = matcher.match_tracks(tracks, num_threads=4)
    """
    
    def __init__(self, database: Database) -> None:
        """
        Initialize the YouTubeMatcher.
        
        Args:
            database: Database instance for storing match results.
        
        Behavior:
            Creates a ytmusicapi.YTMusic client with English language.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def match_track(self, track: Track) -> MatchResult:
        """
        Find the best YouTube Music match for a single track.
        
        This is the core matching method that implements the full
        matching algorithm.
        
        Args:
            track: Track object from Spotify with metadata.
        
        Returns:
            MatchResult indicating success/failure and match details.
        
        Behavior:
            1. Try ISRC search if track has ISRC
            2. If ISRC fails, try text search ("Artist - Title")
            3. Process search results:
               a. Convert to YouTubeResult objects
               b. Filter by duration tolerance
               c. Score by title/artist similarity
               d. Sort by score (verified results get bonus)
            4. Return best match or failure result
        
        Logging:
            - DEBUG: Search queries and result counts
            - DEBUG: Match scores for top candidates
            - INFO: Successful matches
            - WARNING: Failed matches
        
        Thread Safety:
            This method is thread-safe. Multiple threads can call it
            simultaneously for different tracks.
        
        Example:
            result = matcher.match_track(track)
            if result.matched:
                database.set_youtube_url(playlist_id, track.spotify_id, result.youtube_url)
            else:
                database.mark_youtube_match_failed(playlist_id, track.spotify_id)
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def match_tracks(
        self,
        tracks: list[Track],
        playlist_id: str,
        num_threads: int = 4
    ) -> list[MatchResult]:
        """
        Match multiple tracks using parallel processing.
        
        This is the main entry point for PHASE 2 batch processing.
        
        Args:
            tracks: List of Track objects to match.
            playlist_id: Playlist ID for database updates.
            num_threads: Number of parallel threads for matching.
                        More threads = faster but higher API load.
        
        Returns:
            List of MatchResult objects, one per input track.
            Order matches input order.
        
        Behavior:
            1. Create thread pool with num_threads workers
            2. Submit match_track() task for each track
            3. As results complete:
               a. Update database (set_youtube_url or mark_failed)
               b. Log progress
            4. Wait for all tasks to complete
            5. Return all results
        
        Progress:
            Logs progress updates as matches complete.
            Uses tqdm progress bar if available.
        
        Database Updates:
            For each track:
            - If matched: set_youtube_url(playlist_id, track_id, url)
            - If failed: mark_youtube_match_failed(playlist_id, track_id)
        
        Thread Safety:
            Uses ThreadPoolExecutor for parallel processing.
            Database updates are thread-safe via Database locking.
        
        Example:
            matcher = YouTubeMatcher(database)
            results = matcher.match_tracks(tracks, playlist_id, num_threads=4)
            
            matched_count = sum(1 for r in results if r.matched)
            print(f"Matched {matched_count}/{len(tracks)} tracks")
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _search_by_isrc(self, isrc: str) -> list[YouTubeResult]:
        """
        Search YouTube Music using ISRC code.
        
        ISRC (International Standard Recording Code) is a unique
        identifier for recordings. Searching by ISRC gives the most
        accurate results when available.
        
        Args:
            isrc: The ISRC code (e.g., "GBUM71029604").
        
        Returns:
            List of YouTubeResult objects from the search.
            Empty list if no results found.
        
        Behavior:
            1. Search YouTube Music with ISRC as query
            2. Filter to "songs" only (ISRC should match official releases)
            3. Convert results to YouTubeResult objects
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _search_by_text(self, query: str) -> list[YouTubeResult]:
        """
        Search YouTube Music using text query.
        
        Args:
            query: Search query string, typically "Artist - Title".
        
        Returns:
            List of YouTubeResult objects from the search.
            Combines results from both "songs" and "videos" filters.
        
        Behavior:
            1. Search with filter="songs" (official releases)
            2. Search with filter="videos" (user uploads, live versions)
            3. Combine and deduplicate results
            4. Convert to YouTubeResult objects
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _filter_by_duration(
        self,
        results: list[YouTubeResult],
        target_duration_ms: int
    ) -> list[YouTubeResult]:
        """
        Filter results to those within duration tolerance.
        
        Args:
            results: List of YouTubeResult candidates.
            target_duration_ms: Target duration from Spotify track (milliseconds).
        
        Returns:
            Filtered list containing only results within DURATION_TOLERANCE_SECONDS
            of the target duration.
        
        Behavior:
            Computes absolute difference between result duration and target.
            Keeps results where difference <= DURATION_TOLERANCE_SECONDS.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _score_result(
        self,
        result: YouTubeResult,
        track: Track
    ) -> float:
        """
        Score a YouTube result against a Spotify track.
        
        Uses fuzzy string matching to compare titles and artists,
        with bonus points for verified sources.
        
        Args:
            result: YouTubeResult candidate to score.
            track: Spotify Track to match against.
        
        Returns:
            Score from 0 to 100 (higher is better match).
        
        Scoring Components:
            - Title similarity (0-100): Uses rapidfuzz ratio
            - Artist similarity (0-100): Compares artist strings
            - Verification bonus (+5): If result.is_verified
            - Album match bonus (+5): If album names match
        
        Final score = weighted average + bonuses
        
        Algorithm:
            This mirrors spotDL's scoring approach using rapidfuzz
            for string comparison.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _select_best_match(
        self,
        candidates: list[tuple[YouTubeResult, float]],
        min_score: float = MIN_SIMILARITY_SCORE
    ) -> YouTubeResult | None:
        """
        Select the best match from scored candidates.
        
        Args:
            candidates: List of (YouTubeResult, score) tuples.
            min_score: Minimum acceptable score (0-100).
        
        Returns:
            Best YouTubeResult if score >= min_score, None otherwise.
        
        Selection Logic:
            1. Filter to candidates with score >= min_score
            2. Sort by score descending
            3. Return top result, or None if none qualify
        """
        raise NotImplementedError("Contract only - implementation pending")


def match_tracks_phase2(
    database: Database,
    tracks: list[Track],
    playlist_id: str,
    num_threads: int = 4
) -> list[MatchResult]:
    """
    Convenience function for PHASE 2 track matching.
    
    This is the main entry point called by the CLI for YouTube matching.
    
    Args:
        database: Database instance.
        tracks: List of Track objects from PHASE 1.
        playlist_id: Playlist ID for database updates.
        num_threads: Number of parallel matching threads.
    
    Returns:
        List of MatchResult objects.
    
    Example:
        results = match_tracks_phase2(db, tracks, playlist_id, num_threads=4)
        matched = sum(1 for r in results if r.matched)
        print(f"Matched {matched}/{len(tracks)} tracks")
    """
    matcher = YouTubeMatcher(database)
    return matcher.match_tracks(tracks, playlist_id, num_threads)


def get_tracks_needing_match(database: Database, playlist_id: str) -> list[dict[str, Any]]:
    """
    Get tracks from database that need YouTube matching.
    
    Convenience function for getting tracks to process in PHASE 2
    when running phases separately.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID to query.
    
    Returns:
        List of track data dicts for tracks with youtube_url=None.
    """
    return database.get_tracks_without_youtube_url(playlist_id)
