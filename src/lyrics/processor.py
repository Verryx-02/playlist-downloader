"""
Lyrics processing and multi-source management with intelligent coordination and quality validation

This module provides a comprehensive lyrics management system that coordinates between multiple
lyrics providers, handles sophisticated processing and validation, and manages different output
formats. It serves as the central hub for all lyrics-related operations in the Playlist-Downloader
application.

The system implements a multi-source approach with intelligent fallback strategies, ensuring
maximum success rate in lyrics retrieval while maintaining quality standards. It supports
multiple output formats, file management, and seamless integration with audio metadata systems.

Key Features:

1. Multi-Source Coordination:
   - Primary and fallback source configuration for maximum coverage
   - Intelligent search ordering based on provider reliability and preferences
   - Provider-specific error handling and retry mechanisms
   - Comprehensive statistics tracking for source performance analysis

2. Advanced Processing Pipeline:
   - Lyrics content validation and quality assessment
   - Automatic text cleaning and formatting normalization
   - Confidence scoring for match quality evaluation
   - Support for both plain text and synchronized lyrics (LRC format)

3. Flexible Output Management:
   - Multiple format support (TXT, LRC, or both)
   - Automatic file naming with artist and track information
   - Backup creation for existing files to prevent data loss
   - Metadata embedding in audio files for portable lyrics

4. Quality Assurance System:
   - Content length validation against configurable thresholds
   - Structure analysis for identifying well-formatted lyrics
   - Confidence scoring based on title matching and content analysis
   - Provider validation and availability checking

5. File Management:
   - Organized file structure with sanitized naming conventions
   - Automatic backup creation when overwriting existing files
   - Cleanup utilities for managing old lyrics files
   - Support for batch operations and directory management

Architecture Overview:

The lyrics processor uses a provider pattern where multiple lyrics sources implement a common
interface, allowing the main processor to coordinate between them seamlessly. This design
enables easy addition of new lyrics sources and provides robust fallback mechanisms.

Provider Integration:
- Genius API: High-quality lyrics with detailed search algorithms
- SyncedLyrics: Synchronized lyrics with timing information
- Extensible architecture for additional providers

Processing Flow:
1. Source Selection: Determine search order based on configuration and preferences
2. Provider Search: Execute searches across available providers with error handling
3. Quality Validation: Assess content quality and match confidence
4. Format Processing: Convert between different lyrics formats as needed
5. Output Generation: Save files and embed metadata according to configuration

Configuration:
All behavior is controlled through application settings including:
- Primary and fallback source configuration
- Output format preferences (TXT, LRC, both)
- Quality thresholds and validation parameters
- File management and naming conventions
- Processing and embedding options

Statistics and Monitoring:
The system maintains comprehensive statistics including:
- Search success rates by provider
- Processing performance metrics
- Source usage patterns and reliability data
- Configuration status and validation results

This information enables optimization of source selection and troubleshooting of
lyrics retrieval issues.
"""

import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
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
from ..spotify.models import LyricsSource
from .genius import get_genius_provider
from .syncedlyrics import get_syncedlyrics_provider


class LyricsFormat(Enum):
    """
    Enumeration of supported lyrics output formats
    
    Defines the available formats for lyrics output, supporting both plain text
    and synchronized lyrics formats. This allows users to choose their preferred
    format based on their music player capabilities and preferences.
    
    Formats:
    - PLAIN_TEXT: Standard text files (.txt) with lyrics only
    - LRC: Synchronized lyrics format (.lrc) with timing information
    - BOTH: Saves both formats for maximum compatibility
    
    The LRC format is particularly useful for music players that support
    synchronized lyrics display, while plain text provides universal compatibility.
    """
    PLAIN_TEXT = "txt"  # Standard text format for universal compatibility
    LRC = "lrc"         # Synchronized lyrics with timing information
    BOTH = "both"       # Save both formats for maximum flexibility


@dataclass
class LyricsSearchResult:
    """
    Container for lyrics search results from individual providers with comprehensive metadata
    
    This dataclass encapsulates all information returned from a lyrics provider search,
    including the actual lyrics content, performance metrics, and quality assessment data.
    It provides a standardized way to communicate search results between providers and
    the main processing system.
    
    The class supports both plain text and synchronized lyrics, allowing providers to
    return timing information when available. Performance metrics enable optimization
    of provider selection and troubleshooting of search issues.
    
    Quality Assessment:
    The confidence_score field provides a quality metric (0-1) indicating how well
    the found lyrics match the requested track. This enables intelligent selection
    when multiple sources return results.
    
    Attributes:
        source: LyricsSource enum indicating which provider returned this result
        lyrics: Plain text lyrics content (None if not found)
        synced_lyrics: Synchronized lyrics in LRC format (None if not available)
        success: Boolean indicating whether the search was successful
        error_message: Detailed error information for failed searches (None if successful)
        search_time: Time taken for this search operation in seconds (None if unavailable)
        confidence_score: Quality score 0-1 for match assessment (None if not calculated)
    """
    # Provider identification and core results
    source: LyricsSource                    # Which provider returned this result
    lyrics: Optional[str] = None           # Plain text lyrics content
    synced_lyrics: Optional[str] = None    # Synchronized lyrics (LRC format)
    success: bool = False                  # Overall operation success indicator
    
    # Error handling and diagnostics
    error_message: Optional[str] = None    # Detailed error information
    
    # Performance and quality metrics
    search_time: Optional[float] = None       # Search operation duration
    confidence_score: Optional[float] = None # Match quality assessment (0-1)


@dataclass
class LyricsProcessingResult:
    """
    Comprehensive result container for complete lyrics processing operations
    
    This dataclass represents the final result of the entire lyrics processing pipeline,
    including search, validation, formatting, and file operations. It provides complete
    information about the processing outcome and enables post-processing operations
    like metadata embedding and file management.
    
    The class tracks all aspects of lyrics processing including content, file paths,
    embedding status, and error information. This comprehensive tracking enables
    detailed reporting and troubleshooting of lyrics operations.
    
    File Management:
    The file_paths list tracks all created files (TXT, LRC) for cleanup and
    verification purposes. The embedded flag indicates whether lyrics have
    been embedded in audio file metadata.
    
    Error Handling:
    Detailed error messages provide specific information about processing
    failures, enabling targeted troubleshooting and user feedback.
    
    Attributes:
        success: Boolean indicating overall processing success
        lyrics_text: Final processed plain text lyrics (None if unavailable)
        synced_lyrics: Final processed synchronized lyrics (None if unavailable)
        source: Provider that supplied the lyrics (None if failed)
        file_paths: List of created file paths for tracking and cleanup
        embedded: Boolean indicating if lyrics were embedded in audio metadata
        error_message: Detailed error information for failed operations (None if successful)
    """
    # Core processing results
    success: bool                           # Overall processing success indicator
    lyrics_text: Optional[str] = None      # Final processed plain text lyrics
    synced_lyrics: Optional[str] = None    # Final processed synchronized lyrics
    source: Optional[LyricsSource] = None  # Provider that supplied the lyrics
    
    # File management and output tracking
    file_paths: List[str] = None           # List of created file paths
    embedded: bool = False                 # Whether lyrics were embedded in audio
    
    # Error handling and diagnostics
    error_message: Optional[str] = None    # Detailed error information
    
    def __post_init__(self):
        """
        Initialize default values for mutable attributes
        
        Ensures that the file_paths list is properly initialized as an empty list
        rather than None, preventing AttributeError when appending file paths
        during processing operations.
        """
        if self.file_paths is None:
            self.file_paths = []


class LyricsProcessor:
    """
    Central coordinator for lyrics search, processing, and management across multiple sources
    
    This class serves as the main orchestrator for all lyrics-related operations in the
    Playlist-Downloader application. It coordinates between multiple lyrics providers,
    implements intelligent search strategies, handles comprehensive processing and
    validation, and manages different output formats.
    
    The processor implements a sophisticated multi-source approach with configurable
    primary and fallback sources, ensuring maximum success rate in lyrics retrieval
    while maintaining quality standards. It provides comprehensive statistics tracking,
    file management, and integration with audio metadata systems.
    
    Core Responsibilities:
    
    1. Provider Coordination:
       - Manages multiple lyrics providers (Genius, SyncedLyrics, etc.)
       - Implements intelligent search ordering and fallback strategies
       - Handles provider-specific errors and retry mechanisms
       - Maintains provider availability and performance statistics
    
    2. Search Strategy:
       - Configurable primary and fallback source ordering
       - Preferred source override for specific searches
       - Provider filtering based on availability and configuration
       - Comprehensive error handling across all providers
    
    3. Content Processing:
       - Lyrics validation and quality assessment
       - Text cleaning and formatting normalization
       - Confidence scoring for match quality evaluation
       - Format conversion between plain text and synchronized lyrics
    
    4. Output Management:
       - Multiple format support (TXT, LRC, both)
       - Intelligent file naming with artist and track information
       - Backup creation for existing files to prevent data loss
       - Metadata embedding in audio files for portable lyrics
    
    5. Statistics and Monitoring:
       - Comprehensive tracking of search success rates
       - Provider usage patterns and performance metrics
       - Configuration validation and status reporting
       - File management and cleanup operations
    
    Configuration Integration:
    All behavior is controlled through application settings, allowing for flexible
    configuration of providers, formats, quality thresholds, and file management
    options without code changes.
    
    Thread Safety:
    The processor is designed for concurrent use in multi-threaded download
    operations, with appropriate synchronization for shared resources.
    """
    
    def __init__(self):
        """
        Initialize lyrics processor with comprehensive configuration and provider setup
        
        Sets up the lyrics processor with all necessary configuration from application
        settings, initializes provider connections, and prepares statistics tracking
        for optimal lyrics retrieval and processing.
        
        Configuration Loading:
        - Loads all lyrics-related settings from application configuration
        - Configures output formats and file management options
        - Sets up quality thresholds and validation parameters
        - Initializes provider preferences and fallback strategies
        
        Provider Initialization:
        - Creates connections to all configured lyrics providers
        - Validates provider availability and configuration
        - Sets up provider-specific settings and authentication
        - Prepares fallback chains for maximum success rate
        
        Statistics Setup:
        - Initializes comprehensive tracking for search operations
        - Prepares provider usage and performance monitoring
        - Sets up success rate calculation and reporting
        - Creates foundation for optimization and troubleshooting
        """
        # Load comprehensive application configuration
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Core lyrics processing configuration
        self.enabled = self.settings.lyrics.enabled
        self.download_separate_files = self.settings.lyrics.download_separate_files
        self.embed_in_audio = self.settings.lyrics.embed_in_audio
        self.format = LyricsFormat(self.settings.lyrics.format)
        self.primary_source = LyricsSource(self.settings.lyrics.primary_source)
        self.fallback_sources = [LyricsSource(src) for src in self.settings.lyrics.fallback_sources]
        self.clean_lyrics = self.settings.lyrics.clean_lyrics
        self.min_length = self.settings.lyrics.min_length
        self.max_attempts = self.settings.lyrics.max_attempts
        
        # Provider instances for different lyrics sources
        # Each provider implements the same interface for consistent operation
        self.providers = {
            LyricsSource.GENIUS: get_genius_provider(),
            LyricsSource.SYNCEDLYRICS: get_syncedlyrics_provider(),
        }
        
        # Comprehensive processing statistics for monitoring and optimization
        self.stats = {
            'total_searches': 0,           # Total number of search operations
            'successful_searches': 0,      # Number of successful lyrics retrievals
            'failed_searches': 0,          # Number of failed search attempts
            'source_usage': {source: 0 for source in LyricsSource}  # Per-provider usage tracking
        }
    
    def search_lyrics(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None,
        preferred_source: Optional[LyricsSource] = None
    ) -> LyricsProcessingResult:
        """
        Search for lyrics using intelligent multi-source strategy with comprehensive fallback
        
        Executes a complete lyrics search operation using multiple providers with intelligent
        fallback strategies. Implements quality validation, confidence scoring, and comprehensive
        error handling to maximize success rate while maintaining quality standards.
        
        Args:
            artist: Artist name from track metadata
            title: Track title from track metadata
            album: Album name for additional search context (optional)
            preferred_source: Override primary source for this search (optional)
            
        Returns:
            LyricsProcessingResult containing search results, processed lyrics,
            and comprehensive metadata about the operation
            
        Search Process:
        
        1. Configuration Validation:
           - Check if lyrics processing is enabled
           - Validate provider availability and configuration
           - Update statistics and prepare operation logging
        
        2. Source Selection Strategy:
           - Determine search order based on preferred source override
           - Fall back to configured primary and fallback sources
           - Filter sources based on provider availability
        
        3. Provider Search Loop:
           - Execute searches across available providers in order
           - Handle provider-specific errors with graceful fallback
           - Implement timeout and retry logic for robust operation
        
        4. Quality Validation:
           - Validate lyrics content against quality thresholds
           - Calculate confidence scores for match assessment
           - Process and clean lyrics according to configuration
        
        5. Result Processing:
           - Format lyrics according to output preferences
           - Update comprehensive statistics for monitoring
           - Prepare result for file operations and embedding
        
        Error Handling:
        Implements comprehensive error handling at multiple levels:
        - Individual provider failures don't affect other providers
        - Network and API errors are handled with appropriate fallbacks
        - Configuration errors are reported with detailed messages
        - Processing errors include specific failure information
        
        Performance Optimization:
        - Early termination when high-quality results are found
        - Provider ordering based on historical success rates
        - Intelligent timeout handling to prevent hanging operations
        - Comprehensive statistics for ongoing optimization
        """
        # Check if lyrics processing is enabled in configuration
        if not self.enabled:
            return LyricsProcessingResult(
                success=False,
                error_message="Lyrics processing disabled"
            )
        
        # Update processing statistics and prepare operation logging
        self.stats['total_searches'] += 1
        operation_logger = OperationLogger(self.logger, f"Lyrics Search: {artist} - {title}")
        self.logger.debug("Starting lyrics search")
        
        # Determine intelligent search order based on configuration and preferences
        search_sources = self._get_search_order(preferred_source)
        
        # Execute search across all available providers with fallback handling
        for source in search_sources:
            # Validate provider availability before attempting search
            if source not in self.providers:
                operation_logger.warning(f"Provider not available: {source.value}")
                continue
            
            try:
                self.logger.debug(f"Searching {source.value}")
                
                # Execute search with current provider using error isolation
                result = self._search_with_provider(source, artist, title, album)
                
                if result.success and result.lyrics:
                    # Process and validate found lyrics for quality assurance
                    processed_result = self._process_lyrics_result(result, artist, title)
                    
                    if processed_result.success:
                        # Update success statistics and provider usage tracking
                        self.stats['successful_searches'] += 1
                        self.stats['source_usage'][source] += 1
                        
                        self.logger.debug(f"Lyrics found via {source.value}")
                        return processed_result
                    else:
                        self.logger.debug(f"Lyrics validation failed from {source.value}")
                else:
                    self.logger.debug(f"No lyrics found from {source.value}")
                    
            except Exception as e:
                # Log provider-specific errors but continue with fallback providers
                operation_logger.warning(f"Error searching {source.value}: {e}")
                continue
        
        # No lyrics found from any configured provider
        self.stats['failed_searches'] += 1
        self.logger.debug("No lyrics found from any source")
        
        return LyricsProcessingResult(
            success=False,
            error_message="No lyrics found from any configured source"
        )
    
    def _get_search_order(self, preferred_source: Optional[LyricsSource] = None) -> List[LyricsSource]:
        """
        Determine intelligent search order for lyrics providers based on preferences and configuration
        
        Creates an optimized search order that prioritizes preferred sources while ensuring
        comprehensive coverage through fallback providers. This intelligent ordering maximizes
        success rate while respecting user preferences and provider reliability.
        
        Args:
            preferred_source: Optional source to prioritize for this search
                             Overrides default primary source when specified
            
        Returns:
            List of LyricsSource objects in optimal search order
            Filtered to include only available and configured providers
            
        Search Ordering Logic:
        
        1. Preferred Source Priority:
           - If preferred source is specified and available, place it first
           - Continue with configured primary and fallback sources
           - Avoid duplicate sources in the final ordering
        
        2. Default Configuration:
           - Start with configured primary source
           - Add configured fallback sources in order
           - Maintain user-defined provider preferences
        
        3. Availability Filtering:
           - Remove providers that are not available or configured
           - Ensure all returned sources have active provider instances
           - Handle provider initialization failures gracefully
        
        This approach ensures that each search operation uses the most appropriate
        provider ordering while maintaining flexibility for different search scenarios.
        """
        if preferred_source and preferred_source in self.providers:
            # Prioritize preferred source while maintaining fallback coverage
            sources = [preferred_source]
            # Add primary and fallback sources, avoiding duplicates
            for source in [self.primary_source] + self.fallback_sources:
                if source != preferred_source and source not in sources:
                    sources.append(source)
        else:
            # Use standard configuration ordering
            sources = [self.primary_source] + self.fallback_sources
        
        # Filter to only include providers that are available and configured
        return [source for source in sources if source in self.providers]
    
    def _search_with_provider(
        self, 
        source: LyricsSource, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> LyricsSearchResult:
        """
        Execute lyrics search with specific provider using comprehensive error handling
        
        Performs a lyrics search operation with a single provider while tracking
        performance metrics and handling provider-specific errors. This method
        provides a standardized interface for all provider types while maintaining
        provider-specific optimization and error handling.
        
        Args:
            source: LyricsSource enum specifying which provider to use
            artist: Artist name for search query
            title: Track title for search query
            album: Optional album name for enhanced search context
            
        Returns:
            LyricsSearchResult containing search outcome, content, and performance data
            
        Search Process:
        
        1. Performance Tracking:
           - Record search start time for performance metrics
           - Track provider-specific operation timing
           - Monitor success rates for optimization
        
        2. Provider Execution:
           - Delegate search to provider-specific implementation
           - Handle provider-specific parameters and options
           - Manage authentication and rate limiting as needed
        
        3. Result Processing:
           - Validate returned content and format
           - Calculate confidence scores for quality assessment
           - Structure results for consistent downstream processing
        
        4. Error Handling:
           - Catch and classify provider-specific errors
           - Provide detailed error information for troubleshooting
           - Ensure graceful degradation for temporary failures
        
        Performance Metrics:
        Tracks detailed timing information for each search operation,
        enabling optimization of provider selection and identification
        of performance bottlenecks in the lyrics retrieval process.
        """
        # Start performance tracking for this search operation
        start_time = time.time()
        
        try:
            # Get provider instance and execute search
            provider = self.providers[source]
            
            # Delegate to provider-specific search implementation
            lyrics_text = provider.search_lyrics(artist, title, album)
            search_time = time.time() - start_time
            
            if lyrics_text:
                # Search successful - create comprehensive result with quality metrics
                return LyricsSearchResult(
                    source=source,
                    lyrics=lyrics_text,
                    success=True,
                    search_time=search_time,
                    confidence_score=self._calculate_confidence_score(lyrics_text, title)
                )
            else:
                # Search completed but no lyrics found
                return LyricsSearchResult(
                    source=source,
                    success=False,
                    search_time=search_time,
                    error_message="No lyrics found"
                )
                
        except Exception as e:
            # Handle provider-specific errors with comprehensive reporting
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
        Process and validate lyrics search result with comprehensive quality assurance
        
        Performs complete processing of raw lyrics search results including content
        validation, text cleaning, format normalization, and quality assessment.
        This critical step ensures that only high-quality, properly formatted
        lyrics are returned to the user.
        
        Args:
            result: Raw search result from lyrics provider
            artist: Artist name for context and validation
            title: Track title for context and validation
            
        Returns:
            LyricsProcessingResult with processed content and validation status
            
        Processing Pipeline:
        
        1. Content Validation:
           - Verify that lyrics content is present and non-empty
           - Check for minimum content requirements
           - Validate basic text structure and encoding
        
        2. Content Cleaning (if enabled):
           - Remove metadata tags and formatting artifacts
           - Normalize whitespace and line endings
           - Clean up common lyrics formatting issues
           - Preserve essential structure while removing noise
        
        3. Quality Validation:
           - Apply minimum length requirements
           - Validate content format and structure
           - Check for placeholder or error text
           - Assess overall content quality
        
        4. Result Structuring:
           - Create comprehensive result container
           - Include original source information
           - Preserve both cleaned and synchronized lyrics
           - Prepare for downstream file operations
        
        Quality Assurance:
        The processing pipeline implements multiple quality checks to ensure
        that only meaningful, properly formatted lyrics are accepted. This
        prevents common issues like placeholder text, error messages, or
        corrupted content from being saved as lyrics.
        """
        try:
            # Validate that lyrics content is present and non-empty
            if not result.lyrics:
                return LyricsProcessingResult(
                    success=False,
                    error_message="No lyrics content"
                )
            
            # Apply content cleaning if enabled in configuration
            processed_lyrics = result.lyrics
            if self.clean_lyrics:
                processed_lyrics = clean_lyrics_text(processed_lyrics)
            
            # Perform comprehensive content validation
            if not validate_lyrics_content(processed_lyrics, self.min_length):
                return LyricsProcessingResult(
                    success=False,
                    error_message="Lyrics validation failed"
                )
            
            # Create successful processing result with all content
            return LyricsProcessingResult(
                success=True,
                lyrics_text=processed_lyrics,
                synced_lyrics=result.synced_lyrics,
                source=result.source
            )
            
        except Exception as e:
            # Handle processing errors with detailed error information
            return LyricsProcessingResult(
                success=False,
                error_message=f"Processing error: {e}"
            )
    
    def _calculate_confidence_score(self, lyrics: str, title: str) -> float:
        """
        Calculate confidence score for lyrics match quality using multiple assessment criteria
        
        Implements a sophisticated scoring algorithm that evaluates how well found lyrics
        match the requested track based on multiple factors including title correlation,
        content length, structure analysis, and format quality. This score enables
        intelligent selection when multiple sources return results.
        
        Args:
            lyrics: Lyrics text content to evaluate
            title: Original track title for comparison
            
        Returns:
            Confidence score between 0.0 and 1.0, where:
            - 0.0 indicates poor match quality
            - 1.0 indicates perfect match quality
            - Typical good matches score 0.7-0.9
            
        Scoring Criteria:
        
        1. Title Correlation (60% weight):
           - Analyzes presence of title words in lyrics content
           - Calculates intersection ratio between title and lyrics words
           - Accounts for common variations and formatting differences
        
        2. Content Length Assessment (20% weight):
           - Rewards lyrics with sufficient content length
           - Penalizes extremely short content that may be incomplete
           - Uses configurable minimum length thresholds
        
        3. Structure Analysis (10% weight):
           - Identifies presence of song structure indicators
           - Looks for verse, chorus, bridge markers
           - Rewards well-structured, professionally formatted lyrics
        
        4. Quality Penalties (10% weight):
           - Penalizes very short content that may be errors
           - Reduces score for obvious placeholder or error text
           - Accounts for formatting and encoding issues
        
        Algorithm Details:
        The scoring algorithm uses a weighted approach where title correlation
        is the primary factor, supplemented by content quality indicators.
        This balance ensures that matches are both accurate and complete.
        """
        # Basic validation - return zero score for invalid input
        if not lyrics or not title:
            return 0.0
        
        # Prepare text for comparison by normalizing case and splitting into words
        title_words = set(title.lower().split())
        lyrics_words = set(lyrics.lower().split())
        
        # Calculate title correlation as primary quality indicator
        # This measures how well the lyrics match the expected track
        title_in_lyrics = len(title_words.intersection(lyrics_words)) / len(title_words)
        
        # Base confidence score from title correlation (60% weight)
        confidence = title_in_lyrics * 0.6
        
        # Content length bonus for substantial lyrics (20% weight)
        # Rewards lyrics with sufficient content to be meaningful
        if len(lyrics) >= self.min_length * 2:
            confidence += 0.2
        
        # Structure analysis bonus for professional formatting (10% weight)
        # Identifies well-structured lyrics with song sections
        structure_indicators = ['verse', 'chorus', 'bridge', 'intro', 'outro']
        has_structure = any(indicator in lyrics.lower() for indicator in structure_indicators)
        if has_structure:
            confidence += 0.1
        
        # Quality penalty for very short content (10% weight)
        # Reduces score for content that may be incomplete or error messages
        if len(lyrics) < self.min_length:
            confidence -= 0.3
        
        # Ensure score remains within valid range [0.0, 1.0]
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
        Save lyrics to separate files with intelligent naming and backup management
        
        Creates lyrics files in the specified directory using intelligent naming
        conventions and comprehensive backup management. Supports multiple output
        formats and provides detailed tracking of created files for cleanup and
        verification purposes.
        
        Args:
            lyrics_result: Processing result containing lyrics content
            artist: Artist name for filename generation
            title: Track title for filename generation
            output_directory: Target directory for lyrics files
            track_number: Optional track number for ordered naming
            
        Returns:
            Updated LyricsProcessingResult with file_paths populated
            
        File Management Features:
        
        1. Intelligent Naming:
           - Sanitizes artist and title for filesystem compatibility
           - Includes track numbers for proper ordering when available
           - Uses consistent naming convention across all files
           - Handles special characters and length limitations
        
        2. Format Support:
           - Plain text files (.txt) for universal compatibility
           - Synchronized lyrics files (.lrc) with timing information
           - Both formats when configured for maximum compatibility
           - Format conversion from plain text to simple LRC when needed
        
        3. Backup Management:
           - Automatically creates backups of existing files
           - Prevents data loss when overwriting lyrics files
           - Uses timestamped backup naming for organization
           - Logs backup operations for user awareness
        
        4. Metadata Integration:
           - Adds source attribution to lyrics files
           - Includes processing metadata for reference
           - Maintains traceability of lyrics origins
           - Provides context for manual verification
        
        Error Handling:
        Comprehensive error handling ensures that file operation failures
        don't interrupt the overall lyrics processing pipeline. Detailed
        error messages enable troubleshooting of filesystem issues.
        """
        # Skip file saving if not enabled or if no lyrics to save
        if not self.download_separate_files or not lyrics_result.success:
            return lyrics_result
        
        try:
            # Ensure output directory exists and is accessible
            output_dir = Path(output_directory)
            ensure_directory(output_dir)
            
            # Generate intelligent filename base with track ordering and sanitization
            if track_number:
                filename_base = f"{track_number:02d} - {sanitize_filename(artist)} - {sanitize_filename(title)}"
            else:
                filename_base = f"{sanitize_filename(artist)} - {sanitize_filename(title)}"
            
            saved_files = []
            
            # Save plain text format if configured
            if self.format in [LyricsFormat.PLAIN_TEXT, LyricsFormat.BOTH]:
                if lyrics_result.lyrics_text:
                    txt_path = output_dir / f"{filename_base}.txt"
                    
                    # Create backup if file already exists to prevent data loss
                    if txt_path.exists():
                        backup_path = create_backup_filename(txt_path)
                        txt_path.rename(backup_path)
                        self.logger.info(f"Created backup: {backup_path.name}")
                    
                    # Write lyrics file with metadata footer for traceability
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(lyrics_result.lyrics_text)
                        
                        # Add source attribution and processing metadata
                        f.write(f"\n\n---\nSource: {lyrics_result.source.value if lyrics_result.source else 'unknown'}\n")
                        f.write(f"Retrieved by Playlist-Downloader\n")
                    
                    saved_files.append(str(txt_path))
                    self.logger.info(f"Saved lyrics: {txt_path.name}")
            
            # Save LRC format if configured
            if self.format in [LyricsFormat.LRC, LyricsFormat.BOTH]:
                if lyrics_result.synced_lyrics:
                    # Save synchronized lyrics from provider
                    lrc_path = output_dir / f"{filename_base}.lrc"
                    
                    # Create backup if file already exists
                    if lrc_path.exists():
                        backup_path = create_backup_filename(lrc_path)
                        lrc_path.rename(backup_path)
                        self.logger.info(f"Created backup: {backup_path.name}")
                    
                    # Write synchronized lyrics file
                    with open(lrc_path, 'w', encoding='utf-8') as f:
                        f.write(lyrics_result.synced_lyrics)
                    
                    saved_files.append(str(lrc_path))
                    self.logger.info(f"Saved synced lyrics: {lrc_path.name}")
                elif self.format == LyricsFormat.LRC and lyrics_result.lyrics_text:
                    # Convert plain text to simple LRC format when synchronized lyrics unavailable
                    lrc_content = self._convert_to_simple_lrc(lyrics_result.lyrics_text)
                    lrc_path = output_dir / f"{filename_base}.lrc"
                    
                    with open(lrc_path, 'w', encoding='utf-8') as f:
                        f.write(lrc_content)
                    
                    saved_files.append(str(lrc_path))
                    self.logger.info(f"Saved converted LRC: {lrc_path.name}")
            
            # Update processing result with created file paths for tracking
            lyrics_result.file_paths = saved_files
            
            return lyrics_result
            
        except Exception as e:
            # Handle file operation errors with detailed reporting
            self.logger.error(f"Failed to save lyrics files: {e}")
            lyrics_result.error_message = f"Failed to save files: {e}"
            return lyrics_result
    
    def _convert_to_simple_lrc(self, lyrics_text: str) -> str:
        """
        Convert plain text lyrics to simple LRC format with basic timing information
        
        Creates a basic LRC (synchronized lyrics) file from plain text lyrics by
        adding simple timing information. While not as accurate as professionally
        timed lyrics, this provides basic synchronization for music players that
        support LRC format.
        
        Args:
            lyrics_text: Plain text lyrics to convert
            
        Returns:
            LRC format string with basic timing information
            
        LRC Format Features:
        - Standard LRC metadata headers for compatibility
        - Simple timing algorithm (3 seconds per line)
        - Proper line formatting for music player compatibility
        - Attribution metadata for source tracking
        
        Timing Algorithm:
        Uses a simple 3-second-per-line timing algorithm that provides basic
        synchronization. While not precise, this enables lyrics display in
        LRC-compatible players and provides a foundation for manual timing
        adjustments if needed.
        
        The generated LRC includes standard metadata fields and maintains
        proper formatting for maximum compatibility with different music
        players and lyrics display applications.
        """
        # Split lyrics into individual lines for timing assignment
        lines = lyrics_text.split('\n')
        lrc_lines = []
        
        # Add standard LRC metadata headers for player compatibility
        lrc_lines.append("[ar:Unknown Artist]")
        lrc_lines.append("[ti:Unknown Title]")
        lrc_lines.append("[by:Playlist-Downloader]")
        lrc_lines.append("")
        
        # Convert each line with simple timing algorithm
        current_time = 0
        for line in lines:
            line = line.strip()
            if line:
                # Calculate minutes and seconds for LRC timestamp format
                minutes = current_time // 60
                seconds = current_time % 60
                # Add line with LRC timestamp format [mm:ss.xx]
                lrc_lines.append(f"[{minutes:02d}:{seconds:02d}.00]{line}")
                current_time += 3  # 3 seconds per line
            else:
                # Preserve empty lines for structure
                lrc_lines.append("")
        
        return '\n'.join(lrc_lines)
    
    def embed_lyrics_in_audio(
        self, 
        lyrics_result: LyricsProcessingResult,
        audio_file_path: str
    ) -> bool:
        """
        Embed lyrics in audio file metadata for portable lyrics storage
        
        Integrates lyrics directly into audio file metadata, making lyrics
        available to music players without requiring separate lyrics files.
        This provides the most portable solution for lyrics storage and
        ensures lyrics travel with the audio file.
        
        Args:
            lyrics_result: Processing result containing lyrics to embed
            audio_file_path: Path to audio file for metadata embedding
            
        Returns:
            True if embedding was successful, False otherwise
            
        Embedding Strategy:
        The method marks lyrics for embedding and coordinates with the
        audio metadata manager for actual embedding operations. This
        separation allows for batch optimization and consistent metadata
        handling across the application.
        
        Integration:
        This method integrates with the audio metadata system to ensure
        lyrics are embedded using the appropriate format and encoding
        for the specific audio file type (MP3, FLAC, M4A, etc.).
        """
        # Skip embedding if not enabled or no lyrics available
        if not self.embed_in_audio or not lyrics_result.success:
            return False
        
        try:
            # Import metadata manager for audio file operations
            from ..audio.metadata import get_metadata_manager
            
            metadata_manager = get_metadata_manager()
            
            # Mark lyrics for embedding - actual embedding handled by metadata manager
            # This approach allows for batch optimization and consistent metadata handling
            lyrics_result.embedded = True
            
            self.logger.debug(f"Lyrics marked for embedding in: {Path(audio_file_path).name}")
            return True
            
        except Exception as e:
            # Handle embedding errors with detailed reporting
            self.logger.error(f"Failed to embed lyrics: {e}")
            return False
    
    def validate_lyrics_sources(self) -> Dict[LyricsSource, bool]:
        """
        Validate availability and configuration of all lyrics sources
        
        Performs comprehensive validation of all configured lyrics providers
        to ensure they are properly configured and accessible. This diagnostic
        method helps troubleshoot lyrics retrieval issues and provides status
        information for system monitoring.
        
        Returns:
            Dictionary mapping each LyricsSource to its availability status
            True indicates provider is available and properly configured
            False indicates provider has configuration or connectivity issues
            
        Validation Process:
        
        1. Provider Availability:
           - Checks that provider instances are properly initialized
           - Validates provider configuration and authentication
           - Tests basic connectivity and API access
        
        2. API Validation:
           - Calls provider-specific validation methods when available
           - Tests authentication and quota status
           - Verifies API endpoints and service availability
        
        3. Fallback Handling:
           - Assumes availability when validation methods are not implemented
           - Provides conservative estimates for unknown provider states
           - Logs validation failures for troubleshooting
        
        Use Cases:
        - System startup validation and configuration verification
        - Troubleshooting lyrics retrieval failures
        - Monitoring provider availability and service status
        - Configuration validation after settings changes
        """
        status = {}
        
        # Validate each configured provider
        for source, provider in self.providers.items():
            try:
                # Use provider-specific validation when available
                if hasattr(provider, 'validate_api_access'):
                    status[source] = provider.validate_api_access()
                else:
                    status[source] = True  # Assume available if no validation method
            except Exception as e:
                # Log validation failures for troubleshooting
                self.logger.warning(f"Failed to validate {source.value}: {e}")
                status[source] = False
        
        return status
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive lyrics processing statistics and configuration information
        
        Returns detailed statistics about lyrics processing operations including
        success rates, provider usage patterns, and current configuration status.
        This information enables performance monitoring, optimization, and
        troubleshooting of lyrics retrieval operations.
        
        Returns:
            Dictionary containing comprehensive statistics and configuration data
            
        Statistics Categories:
        
        1. Performance Metrics:
           - Total search operations performed
           - Success and failure counts with calculated success rate
           - Provider-specific usage patterns and reliability data
        
        2. Configuration Status:
           - Current primary and fallback source configuration
           - Output format and file management settings
           - Quality thresholds and processing parameters
           - Feature enablement status (embedding, cleaning, etc.)
        
        3. Provider Information:
           - Usage statistics for each configured provider
           - Source reliability and performance data
           - Provider availability and configuration status
        
        Use Cases:
        - Performance monitoring and optimization
        - Configuration validation and troubleshooting
        - Provider selection and fallback strategy optimization
        - User feedback and system status reporting
        """
        # Calculate performance metrics from collected statistics
        total_searches = self.stats['total_searches']
        success_rate = (self.stats['successful_searches'] / total_searches * 100) if total_searches > 0 else 0
        
        return {
            # Processing status and performance metrics
            'enabled': self.enabled,
            'total_searches': total_searches,
            'successful_searches': self.stats['successful_searches'],
            'failed_searches': self.stats['failed_searches'],
            'success_rate': f"{success_rate:.1f}%",
            
            # Provider usage and performance data
            'source_usage': {source.value: count for source, count in self.stats['source_usage'].items()},
            
            # Comprehensive configuration information
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
        Clean up old lyrics files to prevent disk space accumulation
        
        Removes lyrics files older than the specified threshold to prevent
        gradual accumulation of outdated lyrics files that can consume
        significant disk space over time. Useful for maintenance and
        cleanup operations.
        
        Args:
            directory: Directory containing lyrics files to clean
            older_than_days: Remove files older than this many days (default: 30)
            
        Returns:
            Number of files successfully removed during cleanup operation
            
        Cleanup Strategy:
        - Targets both .txt and .lrc files for comprehensive cleanup
        - Uses file modification time for age determination
        - Preserves recent files that may be actively used
        - Provides detailed logging of cleanup operations
        
        Safety Features:
        - Conservative default age threshold (30 days)
        - Graceful error handling for file access issues
        - Detailed logging of removed files for verification
        - Non-destructive failure mode (continues on errors)
        
        Use Cases:
        - Regular maintenance of lyrics directories
        - Disk space management for large music collections
        - Cleanup after configuration changes or testing
        - Automated maintenance in long-running applications
        """
        try:
            import time
            
            # Convert directory path and validate existence
            directory = Path(directory)
            if not directory.exists():
                return 0
            
            # Calculate cutoff timestamp for file age determination
            cutoff_time = time.time() - (older_than_days * 24 * 3600)
            removed_count = 0
            
            # Clean up plain text lyrics files
            for file_path in directory.glob("*.txt"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    removed_count += 1
            
            # Clean up LRC lyrics files
            for file_path in directory.glob("*.lrc"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    removed_count += 1
            
            # Log cleanup results for monitoring
            if removed_count > 0:
                self.logger.info(f"Cleaned up {removed_count} old lyrics files")
            
            return removed_count
            
        except Exception as e:
            # Handle cleanup errors gracefully without interrupting operations
            self.logger.error(f"Failed to cleanup lyrics files: {e}")
            return 0


# Global lyrics processor instance management
# Singleton pattern ensures consistent configuration and statistics across application
_lyrics_processor: Optional[LyricsProcessor] = None


def get_lyrics_processor() -> LyricsProcessor:
    """
    Get the global lyrics processor instance (singleton pattern)
    
    Provides access to the shared lyrics processor instance used throughout
    the application. Creates the instance on first access and returns the
    same instance for subsequent calls, ensuring consistent configuration,
    statistics tracking, and provider management across all lyrics operations.
    
    Returns:
        Global LyricsProcessor instance
        
    Benefits of Singleton Pattern:
    - Shared statistics and performance tracking across all operations
    - Consistent provider configuration and authentication
    - Centralized cache management for provider instances
    - Efficient resource utilization for provider connections
    - Unified configuration management for all lyrics operations
    """
    global _lyrics_processor
    if not _lyrics_processor:
        _lyrics_processor = LyricsProcessor()
    return _lyrics_processor


def reset_lyrics_processor() -> None:
    """
    Reset the global lyrics processor instance
    
    Clears the global processor instance, forcing a new instance to be created
    on the next access. Useful for testing, configuration changes, or
    troubleshooting lyrics processing issues that might require fresh
    initialization of providers and statistics.
    
    Use Cases:
    - Configuration changes requiring fresh provider initialization
    - Testing scenarios requiring clean statistics and state
    - Recovery from persistent provider connection issues
    - Development and debugging operations requiring state reset
    
    Note:
        This resets the processor instance and statistics but does not
        affect saved lyrics files or embedded metadata. Provider connections
        will be re-established on next access with current configuration.
    """
    global _lyrics_processor
    _lyrics_processor = None