# src/lyrics/__init__.py
"""
Lyrics integration package
Multi-source lyrics retrieval, processing, and embedding
"""

from .processor import get_lyrics_processor, reset_lyrics_processor, LyricsProcessor, LyricsProcessingResult
from .genius import get_genius_provider, reset_genius_provider, GeniusLyricsProvider
from .syncedlyrics import get_syncedlyrics_provider, reset_syncedlyrics_provider, SyncedLyricsProvider

__all__ = [
    'get_lyrics_processor',
    'reset_lyrics_processor',
    'LyricsProcessor',
    'LyricsProcessingResult',
    'get_genius_provider',
    'reset_genius_provider', 
    'GeniusLyricsProvider',
    'get_syncedlyrics_provider',
    'reset_syncedlyrics_provider',
    'SyncedLyricsProvider'
]