"""
Lyrics fetching for spot-downloader.

This module handles fetching song lyrics from various providers.
Lyrics are OPTIONAL - failure to fetch lyrics should never prevent
a track from being downloaded and saved.

Providers (in order of priority):
    1. Synced (syncedlyrics library) - Timestamped LRC lyrics
    2. Genius - Plain text lyrics (requires scraping)
    3. AZLyrics - Plain text lyrics (requires scraping)
    4. MusixMatch - Plain text lyrics (may require API key)

FRAGILE WARNING:
    Lyrics scraping is inherently fragile because:
    - Websites change their HTML structure frequently
    - Anti-bot protections may block requests
    - Rate limiting may cause failures
    - Some songs simply don't have lyrics available
    
    Always treat lyrics as a "nice to have" feature that may fail.

Usage:
    from spot_downloader.download.lyrics import LyricsFetcher
    
    fetcher = LyricsFetcher()
    
    # Try to get lyrics (returns None on failure)
    lyrics = fetcher.fetch_lyrics("Song Title", "Artist Name")
    
    if lyrics:
        # Embed in file
        embed_lyrics(file_path, lyrics)
    else:
        # Continue without lyrics - this is fine
        logger.debug("No lyrics found, continuing without")
"""

from dataclasses import dataclass
from typing import Any

from spot_downloader.core.exceptions import LyricsError
from spot_downloader.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Lyrics:
    """
    Container for fetched lyrics.
    
    Attributes:
        text: The lyrics text content.
              May be plain text or LRC format with timestamps.
        
        is_synced: Whether lyrics are timestamped (LRC format).
                   True for synced lyrics: "[00:15.00]First line..."
                   False for plain text lyrics.
        
        source: Name of the provider that returned the lyrics.
                Example: "genius", "synced", "azlyrics"
    
    LRC Format:
        Synced lyrics use LRC (LyRiCs) format with timestamps:
        [00:15.00]First line of the song
        [00:18.50]Second line continues
        
        These can be embedded as SYLT tags in MP3 or stored as
        separate .lrc files.
    """
    
    text: str
    is_synced: bool
    source: str
    
    @property
    def is_lrc(self) -> bool:
        """Check if lyrics are in LRC format (alias for is_synced)."""
        return self.is_synced


class LyricsFetcher:
    """
    Fetches lyrics from multiple providers with fallback.
    
    This class tries multiple lyrics sources in order until one
    succeeds or all fail. It handles errors gracefully and never
    raises exceptions to the caller (returns None instead).
    
    Provider Order:
        1. syncedlyrics - Best quality (timestamped)
        2. Genius - Large database, good coverage
        3. AZLyrics - Alternative source
        4. MusixMatch - Additional fallback
    
    Attributes:
        _providers: List of provider instances to try.
    
    Thread Safety:
        This class is thread-safe. Multiple threads can call
        fetch_lyrics() simultaneously.
    
    Example:
        fetcher = LyricsFetcher()
        lyrics = fetcher.fetch_lyrics("Bohemian Rhapsody", "Queen")
        
        if lyrics:
            if lyrics.is_synced:
                print("Got synced lyrics from", lyrics.source)
            else:
                print("Got plain lyrics from", lyrics.source)
        else:
            print("No lyrics available")
    """
    
    def __init__(self) -> None:
        """
        Initialize the LyricsFetcher with all available providers.
        
        Behavior:
            Creates instances of all supported lyrics providers.
            Providers that fail to initialize are skipped.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def fetch_lyrics(
        self,
        track_name: str,
        artist: str,
        album: str | None = None,
        duration_seconds: int | None = None
    ) -> Lyrics | None:
        """
        Fetch lyrics for a track from any available provider.
        
        This is the main method for fetching lyrics. It tries each
        provider in order until one returns lyrics or all fail.
        
        Args:
            track_name: The song title.
            artist: The primary artist name.
            album: Optional album name (helps some providers).
            duration_seconds: Optional duration (for synced lyrics matching).
        
        Returns:
            Lyrics object if found, None if all providers failed.
        
        Behavior:
            1. Try syncedlyrics provider (for LRC lyrics)
            2. If failed, try Genius
            3. If failed, try AZLyrics
            4. If failed, try MusixMatch
            5. Return first successful result or None
        
        Error Handling:
            - Provider errors are caught and logged
            - Never raises exceptions (returns None)
            - Each provider failure moves to next provider
        
        Logging:
            - DEBUG: Provider being tried
            - DEBUG: Provider result (success/failure)
            - WARNING: All providers failed (only if all fail)
        
        Example:
            lyrics = fetcher.fetch_lyrics(
                track_name="Bohemian Rhapsody",
                artist="Queen",
                album="A Night at the Opera",
                duration_seconds=354
            )
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _try_synced_lyrics(
        self,
        track_name: str,
        artist: str,
        duration_seconds: int | None
    ) -> Lyrics | None:
        """
        Try to fetch synced (LRC) lyrics using syncedlyrics library.
        
        Args:
            track_name: Song title.
            artist: Artist name.
            duration_seconds: Track duration for matching.
        
        Returns:
            Lyrics with is_synced=True if found, None otherwise.
        
        Behavior:
            Uses syncedlyrics library to search for LRC lyrics.
            Library handles multiple backends (Musixmatch, Lrclib, etc.)
        
        Note:
            syncedlyrics is a third-party library used by spotDL.
            It provides timestamped lyrics when available.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _try_genius(self, track_name: str, artist: str) -> Lyrics | None:
        """
        Try to fetch lyrics from Genius.
        
        Args:
            track_name: Song title.
            artist: Artist name.
        
        Returns:
            Lyrics with is_synced=False if found, None otherwise.
        
        Behavior:
            1. Search Genius API for song
            2. Get song page URL from search results
            3. Scrape lyrics from song page HTML
            4. Clean up HTML artifacts from lyrics text
        
        Note:
            Genius lyrics are scraped from HTML, which may break
            if Genius changes their page structure.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _try_azlyrics(self, track_name: str, artist: str) -> Lyrics | None:
        """
        Try to fetch lyrics from AZLyrics.
        
        Args:
            track_name: Song title.
            artist: Artist name.
        
        Returns:
            Lyrics with is_synced=False if found, None otherwise.
        
        Behavior:
            1. Construct AZLyrics URL from artist/title
            2. Fetch page HTML
            3. Extract lyrics from specific div
            4. Clean up text
        
        Note:
            AZLyrics has aggressive anti-bot protection.
            May fail frequently due to rate limiting or blocks.
        """
        raise NotImplementedError("Contract only - implementation pending")
    
    def _try_musixmatch(self, track_name: str, artist: str) -> Lyrics | None:
        """
        Try to fetch lyrics from MusixMatch.
        
        Args:
            track_name: Song title.
            artist: Artist name.
        
        Returns:
            Lyrics with is_synced=False if found, None otherwise.
        
        Behavior:
            Uses MusixMatch's unofficial API or web scraping.
            Implementation may vary based on available access.
        """
        raise NotImplementedError("Contract only - implementation pending")


def fetch_lyrics_for_track(
    track_name: str,
    artist: str,
    album: str | None = None,
    duration_seconds: int | None = None
) -> Lyrics | None:
    """
    Convenience function to fetch lyrics without creating fetcher instance.
    
    This is a stateless wrapper that creates a LyricsFetcher and
    calls fetch_lyrics(). Use this for one-off requests.
    
    Args:
        track_name: Song title.
        artist: Artist name.
        album: Optional album name.
        duration_seconds: Optional duration.
    
    Returns:
        Lyrics if found, None otherwise.
    
    Example:
        lyrics = fetch_lyrics_for_track("Song Title", "Artist")
        if lyrics:
            print(lyrics.text)
    """
    fetcher = LyricsFetcher()
    return fetcher.fetch_lyrics(track_name, artist, album, duration_seconds)
