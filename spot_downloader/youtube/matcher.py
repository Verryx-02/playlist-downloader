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

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from rapidfuzz import fuzz
from ytmusicapi import YTMusic

from spot_downloader.core.database import Database
from spot_downloader.core.logger import get_logger, log_match_close_alternatives
from spot_downloader.spotify.models import Track
from spot_downloader.youtube.models import MatchResult, YouTubeResult

from spot_downloader.core.logger import (
    get_logger,
    log_match_close_alternatives,
    format_matched_message,
    format_close_matches_message,
    format_no_match_message,
    format_progress_message,
    Colors,
)
from spot_downloader.core.progress import MatchingProgressBar


logger = get_logger(__name__)


# =============================================================================
# DURATION AND SIMILARITY THRESHOLDS
# =============================================================================

# Duration tolerance for matching (seconds)
# If YouTube duration differs by more than this, result is rejected
DURATION_TOLERANCE_SECONDS = 10

# Minimum similarity score (0-100) for title/artist matching
# Below this threshold, result is rejected even if duration matches
MIN_SIMILARITY_SCORE = 70

# Weights for title/artist similarity in final score
# These sum to 1.0 and control the relative importance of title vs artist match
TITLE_WEIGHT = 0.65
ARTIST_WEIGHT = 0.35

# Search options for ytmusicapi (mirrors spotDL configuration)
SEARCH_OPTIONS = [
    {"filter": "songs", "ignore_spelling": True, "limit": 50},
    {"filter": "videos", "ignore_spelling": True, "limit": 50},
]


# =============================================================================
# RETRY CONFIGURATION FOR TRANSIENT ERRORS
# =============================================================================

# Maximum number of retry attempts for API calls
MAX_SEARCH_RETRIES = 3

# Base delay between retries (seconds) - uses exponential backoff
RETRY_DELAY_SECONDS = 1.0


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

# Album match bonus
ALBUM_MATCH_BONUS = 5

# Forbidden Word Penalty (per word, matches spotDL)
# Applied when YouTube has a keyword (e.g., "acoustic", "instrumental") that Spotify doesn't
# SpotDL applies -15 for EACH forbidden word found
FORBIDDEN_WORD_PENALTY = 15

# Close Match Threshold for Tiebreaker
# When multiple results have scores within this range, log alternatives
CLOSE_MATCH_THRESHOLD = 5.0


def _normalize_text(text: str) -> str:
    """
    Normalize text for comparison by removing special characters and lowercasing.
    
    Args:
        text: The text to normalize.
    
    Returns:
        Normalized lowercase text with special characters removed.
    """
    # Remove text in parentheses/brackets (often contains version info)
    # but keep the base text
    text = re.sub(r'\s*[\(\[\{].*?[\)\]\}]\s*', ' ', text)
    # Remove special characters except spaces
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text.lower().strip()


def _check_forbidden_words(spotify_title: str, youtube_title: str) -> list[str]:
    """
    Check if YouTube title contains forbidden words that Spotify title lacks.
    
    This mirrors spotDL's check_forbidden_words() function. It detects when
    YouTube has alternative version indicators (acoustic, instrumental, etc.)
    that the Spotify track doesn't have, indicating a potential mismatch.
    
    Args:
        spotify_title: The Spotify track title.
        youtube_title: The YouTube result title.
    
    Returns:
        List of forbidden words found in YouTube but not in Spotify.
        Empty list if no mismatches found.
    
    Example:
        # Spotify: "Playing God" vs YouTube: "Playing God (Acoustic)"
        # Returns: ["acoustic"]
    """
    spotify_lower = spotify_title.lower()
    youtube_lower = youtube_title.lower()
    
    found_words = []
    for word in FORBIDDEN_WORDS:
        if word in youtube_lower and word not in spotify_lower:
            found_words.append(word)
    
    return found_words


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
        from multiple threads simultaneously. The ytmusicapi client
        is stateless for search operations, and database operations
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
        results = matcher.match_tracks(tracks, playlist_id, num_threads=4)
    """
    
    def __init__(self, database: Database) -> None:
        """
        Initialize the YouTubeMatcher.
        
        Args:
            database: Database instance for storing match results.
        
        Behavior:
            Creates a ytmusicapi.YTMusic client with English language.
        """
        self._database = database
        self._ytmusic = YTMusic(language="en")
    
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
            2. If ISRC search fails, try text search ("Artist - Title")
            3. Process search results:
               a. Convert to YouTubeResult objects
               b. Filter by duration tolerance
               c. Score by title/artist similarity
               d. Sort by score (verified results get bonus)
            4. Return best match or failure result
        
        ISRC Search "Failure" Definition:
            The ISRC search is considered to have "failed" (triggering text
            search fallback) in any of these cases:
            - Zero results returned from the YouTube Music API
            - Results returned but none pass the duration filter
            - Results pass duration filter but none exceed MIN_SIMILARITY_SCORE
            Note: API exceptions trigger retry logic with exponential backoff.
            After MAX_SEARCH_RETRIES failed attempts, the search fails.
        
        Logging:
            - DEBUG: Search queries and result counts
            - DEBUG: Match scores for top candidates
            - INFO: Successful matches
            - WARNING: Failed matches
        
        Thread Safety:
            This method is thread-safe. Multiple threads can call it
            simultaneously for different tracks. The ytmusicapi client
            is stateless for searches, and database operations use locks.
        
        Example:
            result = matcher.match_track(track)
            if result.matched:
                print(f"Matched: {result.youtube_url}")
            else:
                print(f"Failed: {result.match_reason}")
        """
        logger.debug(f"Matching track: {track.artist} - {track.name}")
        
        # Try ISRC search first if available
        if track.isrc:
            logger.debug(f"Trying ISRC search: {track.isrc}")
            results = self._search_by_isrc(track.isrc)
            
            if results:
                # Filter by duration
                filtered = self._filter_by_duration(results, track.duration_ms)
                
                if filtered:
                    # Score and select best match
                    scored = [(r, self._score_result(r, track)) for r in filtered]
                    best, alternatives = self._select_best_match(scored, track)
                    
                    if best is not None:
                        best_result, best_score = best
                        confidence = min(best_score / 100.0, 1.0)
                        
                        logger.debug(
                            f"ISRC match found: {best_result.title} "
                            f"(score: {best_score:.1f})"
                        )
                        
                        return MatchResult.success(
                            spotify_id=track.spotify_id,
                            youtube_result=best_result,
                            confidence=confidence,
                            reason=f"ISRC match (score: {best_score:.1f})",
                            close_alternatives=alternatives
                        )
                    else:
                        logger.debug(
                            f"ISRC results found but none passed score threshold"
                        )
                else:
                    logger.debug(
                        f"ISRC results found but none passed duration filter"
                    )
            else:
                logger.debug(f"No ISRC results found")
        
        # Fall back to text search
        search_query = track.search_query
        logger.debug(f"Trying text search: {search_query}")
        
        results = self._search_by_text(search_query)
        
        if not results:
            logger.warning(f"No results found for: {track.artist} - {track.name}")
            return MatchResult.failure(
                spotify_id=track.spotify_id,
                reason=f"No results found for search query: {search_query}"
            )
        
        # Filter by duration
        filtered = self._filter_by_duration(results, track.duration_ms)
        
        if not filtered:
            logger.warning(
                f"No results within duration tolerance for: "
                f"{track.artist} - {track.name}"
            )
            return MatchResult.failure(
                spotify_id=track.spotify_id,
                reason=f"No results within {DURATION_TOLERANCE_SECONDS}s duration tolerance"
            )
        
        # Score all filtered results
        scored = [(r, self._score_result(r, track)) for r in filtered]
        
        # Select best match
        best, alternatives = self._select_best_match(scored, track)
        
        if best is None:
            logger.warning(
                f"No results above minimum score for: "
                f"{track.artist} - {track.name}"
            )
            return MatchResult.failure(
                spotify_id=track.spotify_id,
                reason=f"No results above minimum similarity score ({MIN_SIMILARITY_SCORE})"
            )
        
        best_result, best_score = best
        confidence = min(best_score / 100.0, 1.0)
        
        logger.debug(
            f"Text search match: {best_result.title} by {best_result.author} "
            f"(score: {best_score:.1f})"
        )
        
        return MatchResult.success(
            spotify_id=track.spotify_id,
            youtube_result=best_result,
            confidence=confidence,
            reason=f"Text search match (score: {best_score:.1f})",
            close_alternatives=alternatives
        )
    
    
    def match_tracks(
        self,
        tracks: list[Track],
        playlist_id: str,
        num_threads: int = 4,
        progress_bar: MatchingProgressBar | None = None
    ) -> list[MatchResult]:
        """
        Match multiple tracks using parallel processing.
        
        Args:
            tracks: List of Track objects to match.
            playlist_id: Playlist ID for database updates.
            num_threads: Number of parallel threads for matching.
            progress_bar: Optional existing progress bar to use.
                         If None, creates a new one.
        
        Returns:
            List of MatchResult objects, one per input track.
        """
        if not tracks:
            return []
        
        # Map to store results in original order
        results_map: dict[str, MatchResult] = {}
        
        # Determine if we own the progress bar (and should manage its lifecycle)
        own_progress_bar = progress_bar is None
        if own_progress_bar:
            progress_bar = MatchingProgressBar(total=len(tracks), description="Matching")
            progress_bar.start()
        
        def process_track(track: Track) -> tuple[Track, MatchResult]:
            """Process a single track and return both track and result."""
            result = self.match_track(track)
            return (track, result)
        
        try:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                # Submit all tasks
                future_to_track = {
                    executor.submit(process_track, track): track
                    for track in tracks
                }
                
                # Process results as they complete
                for future in as_completed(future_to_track):
                    track = future_to_track[future]
                    
                    try:
                        _, result = future.result()
                        results_map[track.spotify_id] = result
                        
                        # Update database and log
                        if result.matched:
                            self._database.set_youtube_url(
                                playlist_id,
                                track.spotify_id,
                                result.youtube_url
                            )
                            progress_bar.log(
                                format_matched_message(
                                    track.artist,
                                    track.name,
                                    result.youtube_url
                                )
                            )
                            
                            # Log close alternatives if present
                            if result.has_close_alternatives:
                                alternatives_with_titles = [
                                    (alt.title, alt.url, score)
                                    for alt, score in result.close_alternatives
                                ]
                                selected_title = result.youtube_result.title if result.youtube_result else ""
                                
                                # Log warning to console (colored)
                                progress_bar.log(
                                    f"{Colors.YELLOW}WARNING{Colors.RESET}: " +
                                    format_close_matches_message(
                                        track.name,
                                        track.artist,
                                        result.confidence * 100
                                    )
                                )
                                
                                # Log to file only
                                log_match_close_alternatives(
                                    logger=logger,
                                    track_name=track.name,
                                    artist=track.artist,
                                    spotify_url=track.spotify_url,
                                    youtube_url=result.youtube_url,
                                    youtube_title=selected_title,
                                    score=result.confidence * 100,
                                    alternatives=alternatives_with_titles,
                                    assigned_number=track.assigned_number
                                )
                            
                            # Update progress bar
                            progress_bar.update(
                                matched=True,
                                has_close_matches=result.has_close_alternatives
                            )
                        else:
                            self._database.mark_youtube_match_failed(
                                playlist_id,
                                track.spotify_id
                            )
                            progress_bar.log(
                                f"{Colors.RED}ERROR{Colors.RESET}: " +
                                format_no_match_message(
                                    track.artist,
                                    track.name,
                                    result.match_reason
                                )
                            )
                            progress_bar.update(matched=False)
                        
                    except Exception as e:
                        logger.error(
                            f"Error matching {track.artist} - {track.name}: {e}"
                        )
                        results_map[track.spotify_id] = MatchResult.failure(
                            spotify_id=track.spotify_id,
                            reason=f"Exception during matching: {str(e)}"
                        )
                        self._database.mark_youtube_match_failed(
                            playlist_id,
                            track.spotify_id
                        )
                        progress_bar.update(matched=False)
        
        finally:
            # Only stop the progress bar if we created it
            if own_progress_bar:
                progress_bar.stop()
        
        # Build results list in original order
        return [results_map[track.spotify_id] for track in tracks]


    def match_tracks_phase2(
        database: Database,
        tracks: list[Track],
        playlist_id: str,
        num_threads: int = 4,
        progress_bar: MatchingProgressBar | None = None
    ) -> list[MatchResult]:
        """
        Convenience function for PHASE 2 track matching.
        
        Args:
            database: Database instance.
            tracks: List of Track objects from PHASE 1.
            playlist_id: Playlist ID for database updates.
            num_threads: Number of parallel matching threads.
            progress_bar: Optional existing progress bar to use.
        
        Returns:
            List of MatchResult objects.
        """
        matcher = YouTubeMatcher(database)
        return matcher.match_tracks(tracks, playlist_id, num_threads, progress_bar)
        
    def _search_with_retry(
        self, 
        search_func: callable, 
        *args, 
        **kwargs
    ) -> list[dict[str, Any]]:
        """
        Execute a search function with retry logic for transient errors.
        
        Args:
            search_func: The search function to call.
            *args: Positional arguments for the search function.
            **kwargs: Keyword arguments for the search function.
        
        Returns:
            List of search results, or empty list if all retries fail.
        
        Behavior:
            Retries up to MAX_SEARCH_RETRIES times with exponential backoff
            for transient errors (network issues, rate limits, etc.).
        """
        last_exception = None
        
        for attempt in range(MAX_SEARCH_RETRIES):
            try:
                return search_func(*args, **kwargs) or []
            except Exception as e:
                last_exception = e
                if attempt < MAX_SEARCH_RETRIES - 1:
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                    logger.debug(
                        f"Search attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Search failed after {MAX_SEARCH_RETRIES} attempts: {e}"
                    )
        
        return []
    
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
            4. Retry on transient errors with exponential backoff
        """
        raw_results = self._search_with_retry(
            self._ytmusic.search,
            isrc,
            filter="songs",
            ignore_spelling=True,
            limit=20
        )
        
        results = []
        for raw in raw_results:
            # Skip results without video ID or artists
            if not raw.get("videoId") or not raw.get("artists"):
                continue
            
            try:
                result = YouTubeResult.from_ytmusic_result(raw)
                if result.video_id and result.duration_seconds > 0:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse ISRC result: {e}")
                continue
        
        return results
    
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
            5. Retry on transient errors with exponential backoff
        """
        all_results = []
        seen_ids = set()
        
        for options in SEARCH_OPTIONS:
            raw_results = self._search_with_retry(
                self._ytmusic.search,
                query,
                **options
            )
            
            for raw in raw_results:
                video_id = raw.get("videoId")
                
                # Skip duplicates, results without ID, or without artists
                if not video_id or video_id in seen_ids:
                    continue
                if not raw.get("artists"):
                    continue
                
                seen_ids.add(video_id)
                
                try:
                    result = YouTubeResult.from_ytmusic_result(raw)
                    if result.video_id and result.duration_seconds > 0:
                        all_results.append(result)
                except Exception as e:
                    logger.debug(f"Failed to parse text search result: {e}")
                    continue
        
        return all_results
    
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
        target_seconds = target_duration_ms // 1000
        
        filtered = []
        for result in results:
            diff = abs(result.duration_seconds - target_seconds)
            if diff <= DURATION_TOLERANCE_SECONDS:
                filtered.append(result)
        
        return filtered
    
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
            
            2. Explicit Flag Matching (Asymmetric Penalties):
               Compares track.explicit with result.is_explicit:
               - Both explicit: +3 (perfect match)
               - Both clean: +2 (good match)
               - Spotify explicit, YT clean: -5 (likely censored version)
               - Spotify clean, YT explicit: -2 (possible tagging error)
               - Either is None: 0 (insufficient data)
               See EXPLICIT_MATCH_SCORES constant.
            
            3. Forbidden Words Check (spotDL style):
               If YouTube title contains a keyword from FORBIDDEN_WORDS
               (e.g., "acoustic", "instrumental", "live") but Spotify title doesn't:
               - Apply -15 penalty PER WORD found
               This prevents matching original songs to alternate versions.
               Example: "Playing God" on Spotify should not match "Playing God (Acoustic)"
               on YouTube, which would get -15 penalty.
        
        Final score = weighted_average(title, artist) + all_bonuses + all_penalties
        
        Note:
            Popularity-Views Correlation bonus is applied in _select_best_match()
            since it requires context about all candidates to compute relative tiers.
        """
        # Normalize texts for comparison
        spotify_title = _normalize_text(track.name)
        youtube_title = _normalize_text(result.title)
        
        # Build artist strings for comparison
        spotify_artist = _normalize_text(track.artist)
        youtube_artist = _normalize_text(result.author)
        
        # Also try matching against all artists
        spotify_all_artists = _normalize_text(" ".join(track.artists))
        youtube_all_artists = _normalize_text(" ".join(result.artists)) if result.artists else youtube_artist
        
        # Calculate title similarity
        title_score = fuzz.ratio(spotify_title, youtube_title)
        
        # Calculate artist similarity (best of primary or all artists)
        artist_score_primary = fuzz.ratio(spotify_artist, youtube_artist)
        artist_score_all = fuzz.ratio(spotify_all_artists, youtube_all_artists)
        artist_score = max(artist_score_primary, artist_score_all)
        
        # Weighted average of title and artist scores
        base_score = (title_score * TITLE_WEIGHT) + (artist_score * ARTIST_WEIGHT)
        
        # Initialize bonus/penalty accumulator
        adjustments = 0.0
        
        # 1. Result Type Priority bonus
        if result.result_type == "song":
            if result.is_verified:
                adjustments += RESULT_TYPE_BONUS["song_verified"]
            else:
                adjustments += RESULT_TYPE_BONUS["song_unverified"]
        else:
            if result.is_verified:
                adjustments += RESULT_TYPE_BONUS["video_verified"]
            else:
                adjustments += RESULT_TYPE_BONUS["video_unverified"]
        
        # 2. Album match bonus
        if track.album and result.album:
            spotify_album = _normalize_text(track.album)
            youtube_album = _normalize_text(result.album)
            album_similarity = fuzz.ratio(spotify_album, youtube_album)
            if album_similarity >= 80:
                adjustments += ALBUM_MATCH_BONUS
        
        # 3. Explicit flag matching
        if track.explicit is not None and result.is_explicit is not None:
            if track.explicit and result.is_explicit:
                adjustments += EXPLICIT_MATCH_SCORES["both_explicit"]
            elif not track.explicit and not result.is_explicit:
                adjustments += EXPLICIT_MATCH_SCORES["both_clean"]
            elif track.explicit and not result.is_explicit:
                adjustments += EXPLICIT_MATCH_SCORES["spotify_explicit_yt_clean"]
            elif not track.explicit and result.is_explicit:
                adjustments += EXPLICIT_MATCH_SCORES["spotify_clean_yt_explicit"]
        
        # 4. Forbidden words check (spotDL style)
        # Check if YouTube has forbidden words that Spotify doesn't have
        forbidden_words_found = _check_forbidden_words(track.name, result.title)
        for _ in forbidden_words_found:
            adjustments -= FORBIDDEN_WORD_PENALTY  # -15 per word
        
        final_score = base_score + adjustments
        
        return final_score
    
    def _select_best_match(
        self,
        candidates: list[tuple[YouTubeResult, float]],
        track: Track,
        min_score: float = MIN_SIMILARITY_SCORE
    ) -> tuple[tuple[YouTubeResult, float] | None, list[tuple[YouTubeResult, float]]]:
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
            - Best (YouTubeResult, score) if score >= min_score, None otherwise.
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
        """
        if not candidates:
            return None, []
        
        # Make mutable copy for score adjustments
        adjusted_candidates = [(r, s) for r, s in candidates]
        
        # Apply Popularity-Views Correlation for popular tracks
        if track.popularity > POPULARITY_HIGH_THRESHOLD:
            # Get candidates with known view counts
            candidates_with_views = [
                (r, s, r.views) for r, s in adjusted_candidates
                if r.views is not None
            ]
            
            if candidates_with_views:
                # Sort by views to determine tiers
                candidates_with_views.sort(key=lambda x: x[2], reverse=True)
                
                # Calculate high-views tier threshold (top 30%)
                high_tier_count = max(1, int(len(candidates_with_views) * VIEWS_TIER_HIGH_PERCENTILE))
                high_tier_ids = {
                    c[0].video_id for c in candidates_with_views[:high_tier_count]
                }
                
                # Apply bonus to high-tier candidates
                adjusted_candidates = [
                    (r, s + VIEWS_BOOST_HIGH_TIER if r.video_id in high_tier_ids else s)
                    for r, s in adjusted_candidates
                ]
        
        # Filter by minimum score
        valid_candidates = [
            (r, s) for r, s in adjusted_candidates if s >= min_score
        ]
        
        if not valid_candidates:
            return None, []
        
        # Sort by score (descending)
        valid_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Best match
        best = valid_candidates[0]
        best_result, best_score = best
        
        # Find close alternatives
        close_alternatives = []
        for r, s in valid_candidates[1:]:
            if best_score - s <= CLOSE_MATCH_THRESHOLD:
                close_alternatives.append((r, s))
        
        return best, close_alternatives


def match_tracks_phase2(
    database: Database,
    tracks: list[Track],
    playlist_id: str,
    num_threads: int = 4,
    progress_bar: MatchingProgressBar | None = None
) -> list[MatchResult]:
    """
    Convenience function for PHASE 2 track matching.
    
    Args:
        database: Database instance.
        tracks: List of Track objects from PHASE 1.
        playlist_id: Playlist ID for database updates.
        num_threads: Number of parallel matching threads.
        progress_bar: Optional existing progress bar to use.
    
    Returns:
        List of MatchResult objects.
    """
    matcher = YouTubeMatcher(database)
    return matcher.match_tracks(tracks, playlist_id, num_threads, progress_bar)


def get_tracks_needing_match(
    database: Database, 
    playlist_id: str | None = None
) -> list[dict[str, Any]]:
    """
    Get tracks from database that need YouTube matching.
    
    Convenience function for getting tracks to process in PHASE 2
    when running phases separately.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID to query. If None, returns tracks from
                     ALL playlists that need matching.
    
    Returns:
        List of track data dicts for tracks with youtube_url=None.
        Each dict includes 'track_id' key.
        When playlist_id is None, each dict also includes 'playlist_id'.
    """
    if playlist_id is None:
        return database.get_all_tracks_needing_match()
    return database.get_tracks_without_youtube_url(playlist_id)