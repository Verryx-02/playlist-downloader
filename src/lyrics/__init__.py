# src/lyrics/__init__.py
"""
Lyrics integration package for multi-source lyrics retrieval and processing

This package provides a comprehensive lyrics management system that coordinates
multiple lyrics sources, processes lyrics content, and handles embedding lyrics
into audio files. It serves as the central hub for all lyrics-related functionality
in the Playlist-Downloader application.

Key components:
- LyricsProcessor: Main coordinator for lyrics operations and multi-source management
- GeniusLyricsProvider: Integration with Genius API for high-quality lyrics
- SyncedLyricsProvider: Provider for synchronized lyrics with timing information

The package abstracts the complexity of working with multiple lyrics sources,
providing a unified interface for:
- Searching lyrics across multiple providers
- Validating and processing lyrics content
- Handling both plain text and synchronized (LRC) lyrics formats
- Embedding lyrics into audio file metadata
- Saving lyrics as separate files (.txt, .lrc)
- Managing lyrics source priorities and fallbacks

Architecture:
The package follows a provider pattern where each lyrics source implements
a common interface, allowing the main processor to coordinate between them
seamlessly. This design enables easy addition of new lyrics sources and
provides robust fallback mechanisms when primary sources fail.

Usage:
Typically accessed through the main processor:
    processor = get_lyrics_processor()
    result = processor.process_track_lyrics(artist, title, album)

Or individual providers can be used directly:
    genius = get_genius_provider()
    lyrics = genius.search_lyrics(artist, title)
"""

# Import main lyrics processor and coordination classes
# The processor serves as the primary interface for lyrics operations
from .processor import get_lyrics_processor, reset_lyrics_processor, LyricsProcessor, LyricsProcessingResult

# Import Genius API provider for high-quality lyrics
# Genius typically provides the most accurate and complete lyrics
from .genius import get_genius_provider, reset_genius_provider, GeniusLyricsProvider

# Import synchronized lyrics provider for time-aligned lyrics
# SyncedLyrics provides LRC format lyrics with timing information
from .syncedlyrics import get_syncedlyrics_provider, reset_syncedlyrics_provider, SyncedLyricsProvider

# Define public API exports for the package
# This controls what symbols are available when using "from lyrics import *"
# and serves as the official public interface documentation
__all__ = [
    # Main lyrics processor - primary interface for lyrics operations
    'get_lyrics_processor',     # Factory function to get processor instance
    'reset_lyrics_processor',   # Function to reset/reinitialize processor
    'LyricsProcessor',          # Main processor class for direct instantiation
    'LyricsProcessingResult',   # Result container for lyrics processing operations
    
    # Genius API provider - high-quality lyrics source
    'get_genius_provider',      # Factory function to get Genius provider instance
    'reset_genius_provider',    # Function to reset/reinitialize Genius provider
    'GeniusLyricsProvider',     # Genius provider class for direct instantiation
    
    # Synchronized lyrics provider - time-aligned lyrics source
    'get_syncedlyrics_provider',    # Factory function to get SyncedLyrics provider instance
    'reset_syncedlyrics_provider',  # Function to reset/reinitialize SyncedLyrics provider
    'SyncedLyricsProvider'          # SyncedLyrics provider class for direct instantiation
]