"""
SyncedLyrics integration for lyrics retrieval
Fast and reliable lyrics source without API requirements
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import sys
import io
from contextlib import redirect_stderr

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import (
    normalize_artist_name, 
    normalize_track_title,
    retry_on_failure,
    validate_lyrics_content,
    clean_lyrics_text
)
from ..spotify.models import LyricsSource

# Import syncedlyrics with error handling and configuration
try:
    import os
    import sys
    import logging
    
    # Set environment variables to reduce verbosity BEFORE importing
    os.environ['SYNCEDLYRICS_VERBOSE'] = '0'
    os.environ['MUSIXMATCH_VERBOSE'] = '0'
    # Disable Musixmatch logger
    logging.getLogger('Musixmatch').setLevel(logging.CRITICAL)
    logging.getLogger('Musixmatch').disabled = True
    
    # Redirect stderr to suppress Musixmatch output
    from contextlib import redirect_stderr
    import io
    
    import syncedlyrics
    
    # Try to disable specific providers that cause spam
    if hasattr(syncedlyrics, 'config'):
        try:
            syncedlyrics.config.MUSIXMATCH_ENABLED = False
        except:
            pass
    
    # Try other ways to disable musixmatch
    try:
        if hasattr(syncedlyrics, 'providers'):
            # Remove musixmatch from active providers if possible
            syncedlyrics.providers = [p for p in syncedlyrics.providers if 'musixmatch' not in p.lower()]
    except:
        pass
    
    HAS_SYNCEDLYRICS = True
except ImportError:
    HAS_SYNCEDLYRICS = False
    syncedlyrics = None


class SyncedLyricsProvider:
    """SyncedLyrics provider for fast lyrics retrieval without API keys"""
    
    def __init__(self):
        """Initialize SyncedLyrics provider"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Configuration
        self.timeout = self.settings.lyrics.timeout
        self.max_attempts = self.settings.lyrics.max_attempts
        
        # Rate limiting (be respectful)
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
        
        # Check if syncedlyrics is available
        if not HAS_SYNCEDLYRICS:
            self.logger.warning("syncedlyrics library not available. Install with: pip install syncedlyrics")
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    @retry_on_failure(max_attempts=2, delay=1.0)
    def search_lyrics(self, artist: str, title: str, album: Optional[str] = None) -> Optional[str]:
        """Search for lyrics using SyncedLyrics with safe output handling"""
        if not HAS_SYNCEDLYRICS:
            self.logger.debug("syncedlyrics library not available")
            return None
        
        try:
            self.logger.debug(f"Searching SyncedLyrics for: {artist} - {title}")
            self._rate_limit()
            
            # Use context manager for safe stream handling
            import sys
            import os
            from contextlib import contextmanager
            
            @contextmanager
            def suppress_output():
                """Suppress output without closing streams"""
                yield
            
            # Search with safe output suppression
            with suppress_output():
                lyrics = syncedlyrics.search(f"{artist} {title}")
            
            # Process results
            if lyrics:
                cleaned_lyrics = clean_lyrics_text(lyrics)
                if validate_lyrics_content(cleaned_lyrics, self.settings.lyrics.min_length):
                    self.logger.debug(f"SyncedLyrics lyrics found for: {artist} - {title}")
                    return cleaned_lyrics
            
            self.logger.debug(f"No SyncedLyrics results found for: {artist} - {title}")
            return None
            
        except Exception as e:
            self.logger.debug(f"SyncedLyrics search failed: {e}")
            return None
    
    def _generate_search_queries(self, artist: str, title: str) -> List[str]:
        """
        Generate search query variations for better matching
        
        Args:
            artist: Artist name
            title: Track title
            
        Returns:
            List of search queries
        """
        queries = []
        
        # Normalize inputs
        norm_artist = normalize_artist_name(artist)
        norm_title = normalize_track_title(title)
        
        # Primary query: "Artist Title"
        queries.append(f"{norm_artist} {norm_title}")
        
        # Alternative formats
        queries.append(f"{artist} {title}")  # Original formatting
        queries.append(f"{norm_artist} - {norm_title}")  # With dash
        
        # Title only (sometimes works better)
        queries.append(norm_title)
        
        # Remove featuring info if present
        import re
        clean_artist = re.sub(r'\s*(feat|ft|featuring)\.?\s+.*', '', norm_artist, flags=re.IGNORECASE)
        if clean_artist != norm_artist:
            queries.append(f"{clean_artist} {norm_title}")
        
        return queries
    
    def validate_api_access(self) -> bool:
        """
        Validate SyncedLyrics access (no API key required)
        
        Returns:
            True if syncedlyrics library is available
        """
        try:
            if not HAS_SYNCEDLYRICS:
                self.logger.warning("syncedlyrics library not installed")
                return False
            
            # Test with a simple search
            test_result = syncedlyrics.search("test")
            # If no exception, library is working (result can be None, that's normal)
            
            self.logger.info("SyncedLyrics validation successful")
            return True
            
        except Exception as e:
            self.logger.error(f"SyncedLyrics validation failed: {e}")
            return False
    
    def get_api_status(self) -> Dict[str, Any]:
        """
        Get SyncedLyrics status and configuration
        
        Returns:
            Dictionary with status information
        """
        return {
            'library_available': HAS_SYNCEDLYRICS,
            'requires_api_key': False,
            'timeout': self.timeout,
            'max_attempts': self.max_attempts,
            'rate_limit_interval': self.min_request_interval,
            'supports_synced_lyrics': True,  # syncedlyrics can provide LRC format
            'description': 'Free lyrics provider without API requirements'
        }
    
    def search_synced_lyrics(self, artist: str, title: str) -> Optional[str]:
        """
        Search for synchronized lyrics (LRC format)
        
        Args:
            artist: Artist name
            title: Track title
            
        Returns:
            Synced lyrics in LRC format or None
        """
        try:
            if not HAS_SYNCEDLYRICS:
                return None
            
            self.logger.debug(f"Searching for synced lyrics: {artist} - {title}")
            self._rate_limit()
            
            # Generate search query
            norm_artist = normalize_artist_name(artist)
            norm_title = normalize_track_title(title)
            query = f"{norm_artist} {norm_title}"
            
            # Search for synced lyrics
            # Search for synced lyrics (suppress Musixmatch output)
            with redirect_stderr(io.StringIO()):
                synced_lyrics = syncedlyrics.search(query, synced_only=True)
            
            if synced_lyrics and '[' in synced_lyrics and ']' in synced_lyrics:
                self.logger.info(f"Synced lyrics found for: {artist} - {title}")
                return synced_lyrics
            else:
                self.logger.debug(f"No synced lyrics found for: {artist} - {title}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Synced lyrics search failed: {e}")
            return None


# Global SyncedLyrics provider instance
_syncedlyrics_provider: Optional[SyncedLyricsProvider] = None


def get_syncedlyrics_provider() -> SyncedLyricsProvider:
    """Get global SyncedLyrics provider instance"""
    global _syncedlyrics_provider
    if not _syncedlyrics_provider:
        _syncedlyrics_provider = SyncedLyricsProvider()
    return _syncedlyrics_provider


def reset_syncedlyrics_provider() -> None:
    """Reset global SyncedLyrics provider instance"""
    global _syncedlyrics_provider
    _syncedlyrics_provider = None