"""
Data models for YouTube matching results.

This module defines dataclasses for YouTube Music search results
and matching outcomes.

Design:
    Models are based on spotDL's Result class structure for compatibility
    with their matching algorithm patterns.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class YouTubeResult:
    """
    Immutable representation of a YouTube Music search result.
    
    This dataclass contains information about a single video/song
    returned from a YouTube Music search. Multiple results are
    compared against the Spotify track to find the best match.
    
    Attributes:
        video_id: YouTube video ID (11-character string).
                  Example: "dQw4w9WgXcQ"
        
        url: Full YouTube URL for the video.
             For songs: "https://music.youtube.com/watch?v=..."
             For videos: "https://www.youtube.com/watch?v=..."
        
        title: Video/song title as it appears on YouTube.
               Example: "Never Gonna Give You Up"
        
        author: Channel/artist name.
                Example: "Rick Astley"
        
        artists: Tuple of artist names (for official songs).
                 May be empty for user uploads.
                 Example: ("Rick Astley",)
        
        duration_seconds: Video duration in seconds.
                         Used for matching against Spotify duration.
                         Example: 213
        
        is_verified: Whether this is from an official/verified source.
                     True for YouTube Music official songs.
                     False for user uploads and regular videos.
        
        album: Album name if available (YouTube Music songs only).
               None for videos and uploads.
               Example: "Whenever You Need Somebody"
        
        is_explicit: Whether marked as explicit content.
                     None if not specified.
        
        views: View count if available.
               Used as tiebreaker in matching (prefer popular).
        
        result_type: Type of result from YouTube Music API.
                     "song" for official songs, "video" for videos.
    
    Class Methods:
        from_ytmusic_result: Create from ytmusicapi search result.
    
    Example:
        result = YouTubeResult.from_ytmusic_result(ytmusic_data)
        print(f"{result.title} by {result.author} ({result.duration_seconds}s)")
    """
    
    video_id: str
    url: str
    title: str
    author: str
    duration_seconds: int
    is_verified: bool
    
    # Optional fields
    artists: tuple[str, ...] = ()
    album: str | None = None
    is_explicit: bool | None = None
    views: int | None = None
    result_type: str = "video"
    
    @classmethod
    def from_ytmusic_result(cls, result: dict[str, Any]) -> "YouTubeResult":
        """
        Create a YouTubeResult from a ytmusicapi search result.
        
        Args:
            result: Dictionary from ytmusicapi.YTMusic.search() response.
        
        Returns:
            YouTubeResult populated with data from the API response.
        
        Behavior:
            1. Extract videoId
            2. Build URL based on result type (song vs video)
            3. Extract title and artist info
            4. Parse duration string to seconds
            5. Determine if verified (resultType == "song")
            6. Extract optional fields (album, explicit, views)
        
        Duration Parsing:
            ytmusicapi returns duration as "3:33" or "1:02:15" string.
            This is converted to total seconds (213 or 3735).
        
        URL Format:
            - Songs: https://music.youtube.com/watch?v={id}
            - Videos: https://www.youtube.com/watch?v={id}
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds for comparison with Spotify."""
        return self.duration_seconds * 1000


@dataclass(frozen=True)
class MatchResult:
    """
    Result of matching a Spotify track to YouTube.
    
    This dataclass represents the outcome of the matching process,
    including whether a match was found and match quality metrics.
    
    Attributes:
        spotify_id: The Spotify track ID that was matched.
        
        matched: Whether a suitable match was found.
                 True if youtube_result is not None.
        
        youtube_result: The best matching YouTubeResult, or None if no match.
        
        confidence: Match confidence score (0.0 to 1.0).
                    Based on title/artist similarity and duration match.
                    Higher is better.
        
        match_reason: Human-readable explanation of match decision.
                      Examples:
                      - "Exact ISRC match"
                      - "High similarity (0.95) with duration match"
                      - "No results found for search query"
        
        close_alternatives: Tuple of (YouTubeResult, score) for matches
                           within CLOSE_MATCH_THRESHOLD points of the best.
                           Empty tuple if no close alternatives exist.
                           Used for logging ambiguous matches so users can
                           verify the selection and use --replace if needed.
    
    Properties:
        youtube_url: The YouTube URL if matched, None otherwise.
        has_close_alternatives: True if there are alternative matches to review.
    
    Example:
        match = matcher.match_track(track)
        if match.matched:
            print(f"Found: {match.youtube_url} (confidence: {match.confidence:.2f})")
            if match.has_close_alternatives:
                print(f"Warning: {len(match.close_alternatives)} close alternatives found")
        else:
            print(f"No match: {match.match_reason}")
    """
    
    spotify_id: str
    matched: bool
    youtube_result: YouTubeResult | None
    confidence: float
    match_reason: str
    close_alternatives: tuple[tuple[YouTubeResult, float], ...] = ()
    
    @property
    def youtube_url(self) -> str | None:
        """Get the YouTube URL if matched."""
        return self.youtube_result.url if self.youtube_result else None
    
    @property
    def has_close_alternatives(self) -> bool:
        """Check if there are close alternative matches to review."""
        return len(self.close_alternatives) > 0
    
    @classmethod
    def success(
        cls,
        spotify_id: str,
        youtube_result: YouTubeResult,
        confidence: float,
        reason: str,
        close_alternatives: list[tuple[YouTubeResult, float]] | None = None
    ) -> "MatchResult":
        """
        Create a successful match result.
        
        Args:
            spotify_id: The Spotify track ID.
            youtube_result: The matching YouTubeResult.
            confidence: Match confidence (0.0-1.0).
            reason: Explanation of why this match was chosen.
            close_alternatives: Optional list of (YouTubeResult, score) tuples
                               for matches within CLOSE_MATCH_THRESHOLD of best.
                               If provided, these will be logged for user review.
        
        Returns:
            MatchResult with matched=True.
        
        Example:
            # Match with no alternatives
            result = MatchResult.success(
                spotify_id="abc123",
                youtube_result=best_result,
                confidence=0.95,
                reason="High similarity match"
            )
            
            # Match with close alternatives (will be logged)
            result = MatchResult.success(
                spotify_id="abc123",
                youtube_result=best_result,
                confidence=0.87,
                reason="Best match with close alternatives",
                close_alternatives=[(alt1, 84.5), (alt2, 83.2)]
            )
        """
        return cls(
            spotify_id=spotify_id,
            matched=True,
            youtube_result=youtube_result,
            confidence=confidence,
            match_reason=reason,
            close_alternatives=tuple(close_alternatives) if close_alternatives else ()
        )
    
    @classmethod
    def failure(cls, spotify_id: str, reason: str) -> "MatchResult":
        """
        Create a failed match result.
        
        Args:
            spotify_id: The Spotify track ID.
            reason: Explanation of why matching failed.
        
        Returns:
            MatchResult with matched=False and empty close_alternatives.
        """
        return cls(
            spotify_id=spotify_id,
            matched=False,
            youtube_result=None,
            confidence=0.0,
            match_reason=reason,
            close_alternatives=()
        )