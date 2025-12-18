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


# =============================================================================
# MATCHING ALGORITHM IMPROVEMENTS - Additional scoring parameters
# =============================================================================

# Forbidden words that indicate alternative versions (from spotDL)
# If Spotify title contains one of these but YouTube result doesn't,
# apply FORBIDDEN_WORD_PENALTY to avoid mismatches
FORBIDDEN_WORDS = (
    "bassboosted",
    "remix",
    "remastered",
    "remaster",
    "reverb",
    "bassboost",
    "live",
    "acoustic",
    "8daudio",
    "concert",
    "acapella",
    "slowed",
    "instrumental",
    "cover",
)

# Popularity-Views Correlation (Tier Relativi)
# For high-popularity Spotify tracks, boost YouTube results in the high-views tier
POPULARITY_HIGH_THRESHOLD = 70  # Spotify popularity score (0-100)
VIEWS_TIER_HIGH_PERCENTILE = 0.30  # Top 30% of results = high views tier
VIEWS_TIER_LOW_PERCENTILE = 0.70  # Bottom 30% of results = low views tier
VIEWS_BOOST_HIGH_TIER = 5  # Bonus points for high-views results on popular tracks

# Result Type Priority (Progressive Multiplier)
# Bonus points based on result_type and verification status
RESULT_TYPE_BONUS = {
    "song_verified": 7,      # Official YT Music release, verified
    "song_unverified": 5,    # YT Music song category, not verified
    "video_verified": 2,     # Video from verified channel
    "video_unverified": 0,   # Generic upload, no bonus
}

# Explicit Flag Matching (Asymmetric Penalties)
# Bonus/penalty based on explicit flag correlation
EXPLICIT_MATCH_SCORES = {
    "both_explicit": 3,           # Both explicit: perfect match
    "both_clean": 2,              # Both clean: good match
    "spotify_explicit_yt_clean": -5,  # Spotify explicit, YT clean: likely censored version
    "spotify_clean_yt_explicit": -2,  # Spotify clean, YT explicit: possible error
    "unknown": 0,                 # One or both have None: no adjustment
}

# Forbidden Word Penalty
# Applied when Spotify has a keyword (e.g., "remix") but YouTube doesn't
FORBIDDEN_WORD_PENALTY = -4

# Close Match Threshold for Tiebreaker
# When multiple results have scores within this range, log alternatives
CLOSE_MATCH_THRESHOLD = 5.0


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
        with bonus/penalty points based on multiple signals.
        
        Args:
            result: YouTubeResult candidate to score.
            track: Spotify Track to match against.
        
        Returns:
            Score (higher is better match). Base range 0-100, but bonuses
            and penalties can push it outside this range.
        
        Scoring Components (Base - from spotDL):
            - Title similarity (0-100): Uses rapidfuzz ratio
            - Artist similarity (0-100): Compares artist strings
            - Album match bonus (+5): If album names match
        
        Scoring Components (Improvements):
            
            1. Result Type Priority (replaces simple verification bonus):
               Based on combination of result_type and is_verified:
               - song + verified: +7 (official YT Music release)
               - song + unverified: +5 (YT Music category)
               - video + verified: +2 (official video)
               - video + unverified: +0 (no bonus)
               See RESULT_TYPE_BONUS constant.
            
            2. Popularity-Views Correlation (Relative Tiers):
               Only applied when track.popularity > POPULARITY_HIGH_THRESHOLD (70):
               - Compute views tier relative to other candidates in the set
               - High-views tier (top 30%): +VIEWS_BOOST_HIGH_TIER (+5)
               - Medium/Low tiers: no adjustment
               This filters spam/re-uploads for popular tracks without
               discriminating against niche artists.
               Note: Tier calculation requires the full candidate list,
               so this is computed in _select_best_match() context.
            
            3. Explicit Flag Matching (Asymmetric Penalties):
               Compares track.explicit with result.is_explicit:
               - Both explicit: +3 (perfect match)
               - Both clean: +2 (good match)
               - Spotify explicit, YT clean: -5 (likely censored version)
               - Spotify clean, YT explicit: -2 (possible tagging error)
               - Either is None: 0 (insufficient data)
               See EXPLICIT_MATCH_SCORES constant.
            
            4. Forbidden Words Check:
               If Spotify title contains a keyword from FORBIDDEN_WORDS
               (e.g., "remix", "live", "acoustic") but YouTube title doesn't:
               - Apply FORBIDDEN_WORD_PENALTY (-4)
               This prevents matching "Song (Remix)" to the original version.
        
        Final score = weighted_average(title, artist) + all_bonuses + all_penalties
        
        Algorithm:
            This extends spotDL's scoring approach, keeping the core
            fuzzy matching while adding complementary signals for
            improved accuracy.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _select_best_match(
        self,
        candidates: list[tuple[YouTubeResult, float]],
        track: Track,
        min_score: float = MIN_SIMILARITY_SCORE
    ) -> tuple[YouTubeResult | None, list[tuple[YouTubeResult, float]]]:
        """
        Select the best match from scored candidates and identify close alternatives.
        
        This method also applies the Popularity-Views Correlation bonus
        since it requires context about all candidates to compute relative tiers.
        
        Args:
            candidates: List of (YouTubeResult, score) tuples.
                       Scores should already include base scoring from _score_result().
            track: The Spotify Track being matched (needed for popularity check).
            min_score: Minimum acceptable score (0-100).
        
        Returns:
            Tuple of:
            - Best YouTubeResult if score >= min_score, None otherwise.
            - List of (YouTubeResult, score) for alternatives within
              CLOSE_MATCH_THRESHOLD points of the best match.
              Empty list if no close alternatives or no valid match.
        
        Selection Logic:
            1. Apply Popularity-Views Correlation:
               If track.popularity > POPULARITY_HIGH_THRESHOLD:
               a. Sort candidates by views (descending)
               b. Identify high-views tier (top 30%)
               c. Add VIEWS_BOOST_HIGH_TIER to candidates in high tier
            
            2. Filter to candidates with score >= min_score
            
            3. Sort by final score (descending)
            
            4. Select top result as best match
            
            5. Identify close alternatives (Conflict Resolution):
               Find all other candidates with score difference < CLOSE_MATCH_THRESHOLD
               from the best match. These are returned for logging/review.
        
        Tiebreaker Behavior:
            When close alternatives exist, the caller should log them using
            log_match_close_alternatives() so users can verify the selection.
            The message format includes:
            - The selected track with Spotify URL, YouTube URL, and score
            - All alternatives with YouTube URL and score
            - A notice: "Multiple close matches found. Verify if correct."
        
        Example:
            candidates = [(result1, 85.0), (result2, 82.5), (result3, 60.0)]
            best, alternatives = matcher._select_best_match(candidates, track)
            # best = result1
            # alternatives = [(result2, 82.5)]  # within 5 points of 85.0
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