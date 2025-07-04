"""
Lyrics processing and multi-source management
Coordinates between different lyrics providers and handles processing, validation, and formatting
"""

import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from ..config.settings import get_settings
from ..utils.logger import get_logger, OperationLogger
from ..utils.helpers import (
    clean_lyrics_text,
    validate_lyrics_content,
    sanitize_filename,
    ensure_directory,
    create_backup_filename
)
from ..spotify.models import LyricsSource, LyricsStatus
from .genius import get_genius_provider
from .syncedlyrics import get_syncedlyrics_provider


class LyricsFormat(Enum):
    """Supported lyrics formats"""
    PLAIN_TEXT = "txt"
    LRC = "lrc"
    BOTH = "both"


@dataclass
class LyricsSearchResult:
    """Result of lyrics search from a provider"""
    source: LyricsSource
    lyrics: Optional[str] = None
    synced_lyrics: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
    search_time: Optional[float] = None
    confidence_score: Optional[float] = None


@dataclass
class LyricsProcessingResult:
    """Result of lyrics processing operation"""
    success: bool
    lyrics_text: Optional[str] = None
    synced_lyrics: Optional[str] = None
    source: Optional[LyricsSource] = None
    file_paths: List[str] = None
    embedded: bool = False
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.file_paths is None:
            self.file_paths = []


class LyricsProcessor:
    """Coordinates lyrics search, processing, and management across multiple sources"""
    
    def __init__(self):
        """Initialize lyrics processor"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Configuration
        self.enabled = self.settings.lyrics.enabled
        self.download_separate_files = self.settings.lyrics.download_separate_files
        self.embed_in_audio = self.settings.lyrics.embed_in_audio
        self.format = LyricsFormat(self.settings.lyrics.format)
        self.primary_source = LyricsSource(self.settings.lyrics.primary_source)
        self.fallback_sources = [LyricsSource(src) for src in self.settings.lyrics.fallback_sources]
        self.clean_lyrics = self.settings.lyrics.clean_lyrics
        self.min_length = self.settings.lyrics.min_length
        self.max_attempts = self.settings.lyrics.max_attempts
        
        # Provider instances
        self.providers = {
            LyricsSource.GENIUS: get_genius_provider(),
            LyricsSource.SYNCEDLYRICS: get_syncedlyrics_provider(),
        }
        
        # Processing statistics
        self.stats = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'source_usage': {source: 0 for source in LyricsSource}
        }
    
    def search_lyrics(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None,
        preferred_source: Optional[LyricsSource] = None
    ) -> LyricsProcessingResult:
        """
        Search for lyrics using multiple sources with fallback
        
        Args:
            artist: Artist name
            title: Track title
            album: Album name (optional)
            preferred_source: Preferred lyrics source (overrides default)
            
        Returns:
            LyricsProcessingResult with search results
        """
        if not self.enabled:
            return LyricsProcessingResult(
                success=False,
                error_message="Lyrics processing disabled"
            )
        
        self.stats['total_searches'] += 1
        operation_logger = OperationLogger(self.logger, f"Lyrics Search: {artist} - {title}")
        operation_logger.start()
        
        # Determine search order
        search_sources = self._get_search_order(preferred_source)
        
        # Try each source
        for source in search_sources:
            if source not in self.providers:
                operation_logger.warning(f"Provider not available: {source.value}")
                continue
            
            try:
                operation_logger.progress(f"Searching {source.value}")
                
                # Search with current provider
                result = self._search_with_provider(source, artist, title, album)
                
                if result.success and result.lyrics:
                    # Process and validate lyrics
                    processed_result = self._process_lyrics_result(result, artist, title)
                    
                    if processed_result.success:
                        self.stats['successful_searches'] += 1
                        self.stats['source_usage'][source] += 1
                        
                        operation_logger.complete(f"Lyrics found via {source.value}")
                        return processed_result
                    else:
                        operation_logger.warning(f"Lyrics validation failed from {source.value}")
                else:
                    operation_logger.warning(f"No lyrics found from {source.value}")
                    
            except Exception as e:
                operation_logger.warning(f"Error searching {source.value}: {e}")
                continue
        
        # No lyrics found from any source
        self.stats['failed_searches'] += 1
        operation_logger.error("No lyrics found from any source")
        
        return LyricsProcessingResult(
            success=False,
            error_message="No lyrics found from any configured source"
        )
    
    def _get_search_order(self, preferred_source: Optional[LyricsSource] = None) -> List[LyricsSource]:
        """
        Get search order for lyrics sources
        
        Args:
            preferred_source: Preferred source to try first
            
        Returns:
            List of sources in search order
        """
        if preferred_source and preferred_source in self.providers:
            # Start with preferred source, then fallbacks
            sources = [preferred_source]
            for source in [self.primary_source] + self.fallback_sources:
                if source != preferred_source and source not in sources:
                    sources.append(source)
        else:
            # Use configured order
            sources = [self.primary_source] + self.fallback_sources
        
        # Filter to only available providers
        return [source for source in sources if source in self.providers]
    
    def _search_with_provider(
        self, 
        source: LyricsSource, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> LyricsSearchResult:
        """
        Search lyrics with specific provider
        
        Args:
            source: Lyrics source to use
            artist: Artist name
            title: Track title
            album: Album name
            
        Returns:
            LyricsSearchResult
        """
        start_time = time.time()
        
        try:
            provider = self.providers[source]
            
            # Search for lyrics
            lyrics_text = provider.search_lyrics(artist, title, album)
            search_time = time.time() - start_time
            
            if lyrics_text:
                return LyricsSearchResult(
                    source=source,
                    lyrics=lyrics_text,
                    success=True,
                    search_time=search_time,
                    confidence_score=self._calculate_confidence_score(lyrics_text, title)
                )
            else:
                return LyricsSearchResult(
                    source=source,
                    success=False,
                    search_time=search_time,
                    error_message="No lyrics found"
                )
                
        except Exception as e:
            search_time = time.time() - start_time
            return LyricsSearchResult(
                source=source,
                success=False,
                search_time=search_time,
                error_message=str(e)
            )
    
    def _process_lyrics_result(
        self, 
        result: LyricsSearchResult, 
        artist: str, 
        title: str
    ) -> LyricsProcessingResult:
        """
        Process and validate lyrics search result
        
        Args:
            result: Raw search result
            artist: Artist name
            title: Track title
            
        Returns:
            Processed LyricsProcessingResult
        """
        try:
            if not result.lyrics:
                return LyricsProcessingResult(
                    success=False,
                    error_message="No lyrics content"
                )
            
            # Clean lyrics if enabled
            processed_lyrics = result.lyrics
            if self.clean_lyrics:
                processed_lyrics = clean_lyrics_text(processed_lyrics)
            
            # Validate lyrics content
            if not validate_lyrics_content(processed_lyrics, self.min_length):
                return LyricsProcessingResult(
                    success=False,
                    error_message="Lyrics validation failed"
                )
            
            return LyricsProcessingResult(
                success=True,
                lyrics_text=processed_lyrics,
                synced_lyrics=result.synced_lyrics,
                source=result.source
            )
            
        except Exception as e:
            return LyricsProcessingResult(
                success=False,
                error_message=f"Processing error: {e}"
            )
    
    def _calculate_confidence_score(self, lyrics: str, title: str) -> float:
        """
        Calculate confidence score for lyrics match
        
        Args:
            lyrics: Lyrics text
            title: Track title
            
        Returns:
            Confidence score 0-1
        """
        if not lyrics or not title:
            return 0.0
        
        # Check if track title appears in lyrics (indicates good match)
        title_words = set(title.lower().split())
        lyrics_words = set(lyrics.lower().split())
        
        title_in_lyrics = len(title_words.intersection(lyrics_words)) / len(title_words)
        
        # Base score from title match
        confidence = title_in_lyrics * 0.6
        
        # Bonus for sufficient length
        if len(lyrics) >= self.min_length * 2:
            confidence += 0.2
        
        # Bonus for structured lyrics (verses, chorus, etc.)
        structure_indicators = ['verse', 'chorus', 'bridge', 'intro', 'outro']
        has_structure = any(indicator in lyrics.lower() for indicator in structure_indicators)
        if has_structure:
            confidence += 0.1
        
        # Penalty for very short lyrics
        if len(lyrics) < self.min_length:
            confidence -= 0.3
        
        return max(0.0, min(1.0, confidence))
    
    def save_lyrics_files(
        self, 
        lyrics_result: LyricsProcessingResult,
        artist: str,
        title: str,
        output_directory: Union[str, Path],
        track_number: Optional[int] = None
    ) -> LyricsProcessingResult:
        """
        Save lyrics to separate files
        
        Args:
            lyrics_result: Processing result with lyrics
            artist: Artist name
            title: Track title
            output_directory: Directory to save files
            track_number: Track number for filename
            
        Returns:
            Updated LyricsProcessingResult with file paths
        """
        if not self.download_separate_files or not lyrics_result.success:
            return lyrics_result
        
        try:
            output_dir = Path(output_directory)
            ensure_directory(output_dir)
            
            # Generate base filename
            if track_number:
                filename_base = f"{track_number:02d} - {sanitize_filename(artist)} - {sanitize_filename(title)}"
            else:
                filename_base = f"{sanitize_filename(artist)} - {sanitize_filename(title)}"
            
            saved_files = []
            
            # Save lyrics based on format setting
            if self.format in [LyricsFormat.PLAIN_TEXT, LyricsFormat.BOTH]:
                if lyrics_result.lyrics_text:
                    txt_path = output_dir / f"{filename_base}.txt"
                    
                    # Create backup if file exists
                    if txt_path.exists():
                        backup_path = create_backup_filename(txt_path)
                        txt_path.rename(backup_path)
                        self.logger.info(f"Created backup: {backup_path.name}")
                    
                    # Write lyrics file
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(lyrics_result.lyrics_text)
                        
                        # Add metadata footer
                        f.write(f"\n\n---\nSource: {lyrics_result.source.value if lyrics_result.source else 'unknown'}\n")
                        f.write(f"Retrieved by Playlist-Downloader\n")
                    
                    saved_files.append(str(txt_path))
                    self.logger.info(f"Saved lyrics: {txt_path.name}")
            
            if self.format in [LyricsFormat.LRC, LyricsFormat.BOTH]:
                if lyrics_result.synced_lyrics:
                    lrc_path = output_dir / f"{filename_base}.lrc"
                    
                    # Create backup if file exists
                    if lrc_path.exists():
                        backup_path = create_backup_filename(lrc_path)
                        lrc_path.rename(backup_path)
                        self.logger.info(f"Created backup: {backup_path.name}")
                    
                    # Write LRC file
                    with open(lrc_path, 'w', encoding='utf-8') as f:
                        f.write(lyrics_result.synced_lyrics)
                    
                    saved_files.append(str(lrc_path))
                    self.logger.info(f"Saved synced lyrics: {lrc_path.name}")
                elif self.format == LyricsFormat.LRC and lyrics_result.lyrics_text:
                    # Convert plain text to simple LRC format
                    lrc_content = self._convert_to_simple_lrc(lyrics_result.lyrics_text)
                    lrc_path = output_dir / f"{filename_base}.lrc"
                    
                    with open(lrc_path, 'w', encoding='utf-8') as f:
                        f.write(lrc_content)
                    
                    saved_files.append(str(lrc_path))
                    self.logger.info(f"Saved converted LRC: {lrc_path.name}")
            
            # Update result with file paths
            lyrics_result.file_paths = saved_files
            
            return lyrics_result
            
        except Exception as e:
            self.logger.error(f"Failed to save lyrics files: {e}")
            lyrics_result.error_message = f"Failed to save files: {e}"
            return lyrics_result
    
    def _convert_to_simple_lrc(self, lyrics_text: str) -> str:
        """
        Convert plain text lyrics to simple LRC format
        
        Args:
            lyrics_text: Plain text lyrics
            
        Returns:
            Simple LRC format lyrics
        """
        lines = lyrics_text.split('\n')
        lrc_lines = []
        
        # Add metadata
        lrc_lines.append("[ar:Unknown Artist]")
        lrc_lines.append("[ti:Unknown Title]")
        lrc_lines.append("[by:Playlist-Downloader]")
        lrc_lines.append("")
        
        # Convert lines with simple timing (every 3 seconds)
        current_time = 0
        for line in lines:
            line = line.strip()
            if line:
                minutes = current_time // 60
                seconds = current_time % 60
                lrc_lines.append(f"[{minutes:02d}:{seconds:02d}.00]{line}")
                current_time += 3  # 3 seconds per line
            else:
                lrc_lines.append("")
        
        return '\n'.join(lrc_lines)
    
    def embed_lyrics_in_audio(
        self, 
        lyrics_result: LyricsProcessingResult,
        audio_file_path: str
    ) -> bool:
        """
        Embed lyrics in audio file metadata
        
        Args:
            lyrics_result: Processing result with lyrics
            audio_file_path: Path to audio file
            
        Returns:
            True if embedding successful
        """
        if not self.embed_in_audio or not lyrics_result.success:
            return False
        
        try:
            from ..audio.metadata import get_metadata_manager
            
            metadata_manager = get_metadata_manager()
            
            # This will be called from the main download process with track info
            # For now, just indicate that embedding should be done
            lyrics_result.embedded = True
            
            self.logger.debug(f"Lyrics marked for embedding in: {Path(audio_file_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to embed lyrics: {e}")
            return False
    
    def validate_lyrics_sources(self) -> Dict[LyricsSource, bool]:
        """
        Validate all configured lyrics sources
        
        Returns:
            Dictionary mapping source to availability status
        """
        status = {}
        
        for source, provider in self.providers.items():
            try:
                if hasattr(provider, 'validate_api_access'):
                    status[source] = provider.validate_api_access()
                else:
                    status[source] = True  # Assume available if no validation method
            except Exception as e:
                self.logger.warning(f"Failed to validate {source.value}: {e}")
                status[source] = False
        
        return status
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get lyrics processing statistics
        
        Returns:
            Dictionary with processing stats
        """
        total_searches = self.stats['total_searches']
        success_rate = (self.stats['successful_searches'] / total_searches * 100) if total_searches > 0 else 0
        
        return {
            'enabled': self.enabled,
            'total_searches': total_searches,
            'successful_searches': self.stats['successful_searches'],
            'failed_searches': self.stats['failed_searches'],
            'success_rate': f"{success_rate:.1f}%",
            'source_usage': {source.value: count for source, count in self.stats['source_usage'].items()},
            'configuration': {
                'primary_source': self.primary_source.value,
                'fallback_sources': [src.value for src in self.fallback_sources],
                'format': self.format.value,
                'download_separate_files': self.download_separate_files,
                'embed_in_audio': self.embed_in_audio,
                'clean_lyrics': self.clean_lyrics,
                'min_length': self.min_length
            }
        }
    
    def cleanup_lyrics_files(self, directory: Union[str, Path], older_than_days: int = 30) -> int:
        """
        Clean up old lyrics files
        
        Args:
            directory: Directory to clean
            older_than_days: Remove files older than this many days
            
        Returns:
            Number of files removed
        """
        try:
            import time
            
            directory = Path(directory)
            if not directory.exists():
                return 0
            
            cutoff_time = time.time() - (older_than_days * 24 * 3600)
            removed_count = 0
            
            for file_path in directory.glob("*.txt"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    removed_count += 1
            
            for file_path in directory.glob("*.lrc"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    removed_count += 1
            
            if removed_count > 0:
                self.logger.info(f"Cleaned up {removed_count} old lyrics files")
            
            return removed_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup lyrics files: {e}")
            return 0


# Global lyrics processor instance
_lyrics_processor: Optional[LyricsProcessor] = None


def get_lyrics_processor() -> LyricsProcessor:
    """Get global lyrics processor instance"""
    global _lyrics_processor
    if not _lyrics_processor:
        _lyrics_processor = LyricsProcessor()
    return _lyrics_processor


def reset_lyrics_processor() -> None:
    """Reset global lyrics processor instance"""
    global _lyrics_processor
    _lyrics_processor = None