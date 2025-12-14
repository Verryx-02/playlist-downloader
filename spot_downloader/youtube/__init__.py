"""
YouTube Music integration module for spot-downloader.

This module provides functionality for matching Spotify tracks to
YouTube Music videos and songs (PHASE 2).

Components:
    - YouTubeResult: Data model for YouTube search results
    - MatchResult: Data model for matching outcomes
    - YouTubeMatcher: Main matcher class with matching algorithm

Usage:
    from spot_downloader.youtube import (
        YouTubeMatcher,
        MatchResult,
        YouTubeResult,
        match_tracks_phase2
    )
    
    # Match tracks from PHASE 1
    results = match_tracks_phase2(database, tracks, playlist_id)
    
    matched_count = sum(1 for r in results if r.matched)
    print(f"Matched {matched_count}/{len(tracks)} tracks")
"""

from spot_downloader.youtube.matcher import (
    YouTubeMatcher,
    get_tracks_needing_match,
    match_tracks_phase2,
)
from spot_downloader.youtube.models import MatchResult, YouTubeResult

__all__ = [
    # Models
    "YouTubeResult",
    "MatchResult",
    # Matcher
    "YouTubeMatcher",
    "match_tracks_phase2",
    "get_tracks_needing_match",
]
