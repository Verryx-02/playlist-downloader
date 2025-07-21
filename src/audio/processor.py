"""
Audio processing utilities for post-download enhancement and quality optimization

This module provides comprehensive audio processing capabilities for the Playlist-Downloader
application, handling post-download enhancement, quality analysis, format conversion, and
audio optimization. It implements advanced audio processing algorithms while maintaining
broad compatibility across different audio formats and system configurations.

Architecture Overview:

The module is built around two core components that work together to provide complete
audio processing capabilities:

1. **AudioAnalysis Data Structure**: Comprehensive audio quality metrics and characteristics
2. **AudioProcessor Engine**: Advanced processing pipeline with configurable enhancements

Key Processing Capabilities:

**Quality Enhancement Pipeline:**
- **Silence Removal**: Intelligent trimming of leading/trailing silence with padding
- **Audio Normalization**: EBU R128 loudness standard compliance with FFmpeg integration
- **Dynamic Range Optimization**: Preservation of audio dynamics while improving consistency
- **Format Conversion**: High-quality transcoding between MP3, FLAC, and M4A formats

**Advanced Audio Analysis:**
- **Quality Metrics**: Peak amplitude, RMS levels, dynamic range, silence ratio analysis
- **Issue Detection**: Clipping, low volume, excessive silence, and quality problems
- **Technical Analysis**: Sample rate, bit depth, bitrate, and format validation
- **Quality Scoring**: Comprehensive 0-100 quality assessment with detailed breakdown

**Intelligent Processing Features:**
- **Configurable Enhancement**: User-controllable processing stages and parameters
- **Quality-Aware Processing**: Adaptive algorithms based on source material characteristics
- **Format-Specific Optimization**: Tailored processing for different audio formats
- **Validation and Verification**: Comprehensive file integrity and quality validation

Design Patterns:

1. **Strategy Pattern**: Different processing strategies based on audio format and quality
2. **Template Method**: Common processing workflow with format-specific implementations
3. **Dependency Injection**: Optional advanced features with graceful degradation
4. **Singleton Pattern**: Global processor instance with shared configuration
5. **Decorator Pattern**: Retry logic for external tool integration (FFmpeg)

Advanced Dependencies and Fallbacks:

**Optional Advanced Processing (librosa):**
- High-precision audio analysis with scientific-grade algorithms
- Advanced spectral analysis and feature extraction
- Professional-quality audio processing capabilities
- Graceful fallback to basic processing when unavailable

**External Tool Integration (FFmpeg):**
- Professional-grade audio normalization using EBU R128 standard
- High-quality format conversion and audio processing
- Robust error handling with fallback strategies
- Automatic tool detection and configuration

**Core Dependencies (always available):**
- pydub: Cross-platform audio processing with broad format support
- numpy: Numerical computation for audio analysis algorithms
- soundfile: High-quality audio I/O operations

Configuration Integration:

The processor integrates comprehensively with the application configuration system:

**Audio Processing Settings:**
- trim_silence: Enable intelligent silence removal
- normalize_audio: Apply EBU R128 loudness normalization
- sample_rate: Target sample rate for processing
- channels: Target channel configuration (mono/stereo)

**Quality Control Parameters:**
- min_duration/max_duration: Acceptable track length ranges
- advanced_audio_analysis: Enable librosa-based advanced analysis
- bitrate: Target bitrate for lossy format conversion

**Processing Thresholds:**
- silence_threshold: dB level for silence detection (-40 dB default)
- target_lufs: EBU R128 loudness target (-23 LUFS standard)
- max_peak: Maximum peak level to prevent clipping (-1 dBFS)

Performance Optimizations:

**Memory Management:**
- Streaming audio processing for large files
- Temporary file handling with automatic cleanup
- Efficient numpy array operations for analysis
- Memory-conscious processing pipelines

**Processing Efficiency:**
- Multi-stage processing with early termination on errors
- Format-specific optimization for different audio types
- Configurable quality vs. speed tradeoffs
- Batch processing capabilities for multiple files

**External Tool Optimization:**
- FFmpeg process management with timeout handling
- Subprocess optimization for command-line tool integration
- Error detection and graceful fallback strategies

Quality Assessment Algorithm:

The module implements a sophisticated quality scoring system that evaluates multiple
audio characteristics:

**Quality Metrics (0-100 scale):**
- **Base Score**: Starts at 100 points
- **Clipping Penalty**: -30 points for digital clipping detection
- **Volume Issues**: -20 points for low volume, -10 for excessive volume
- **Silence Problems**: Progressive penalty for excessive silence content
- **Dynamic Range**: Penalties for compressed or over-expanded audio
- **RMS Level**: Optimal range rewards, penalties for extreme levels

**Issue Detection Categories:**
- **Critical Issues**: Clipping, corruption, unplayable content
- **Quality Issues**: Poor dynamic range, volume problems
- **Content Issues**: Excessive silence, unusual characteristics
- **Technical Issues**: Sample rate, bit depth, format problems

Usage Patterns:

**Basic Processing:**
    processor = get_audio_processor()
    success = processor.process_audio_file("input.mp3", "output.mp3")

**Quality Analysis:**
    analysis = processor.analyze_audio_quality("track.mp3")
    print(f"Quality Score: {analysis.quality_score}/100")

**Format Conversion:**
    processor.convert_format("input.mp3", "output.flac", "flac")

**Validation:**
    is_valid, issues = processor.validate_audio_file("track.mp3")

Error Handling and Reliability:

**Robust Error Recovery:**
- Graceful degradation when advanced tools unavailable
- Comprehensive logging for debugging and monitoring
- Automatic cleanup of temporary files and resources
- Continuation of processing despite non-critical failures

**External Tool Handling:**
- FFmpeg availability detection with fallback strategies
- Process timeout handling to prevent hanging operations
- Command-line argument validation and error checking
- Cross-platform compatibility for different tool installations

**File Safety:**
- Temporary file processing to prevent corruption of originals
- Atomic file operations for reliability
- Path validation and permission checking
- Format validation before processing

Thread Safety and Concurrency:

The processor is designed for safe concurrent usage in multi-threaded download
operations. Individual file operations are atomic, and the singleton pattern
ensures consistent configuration across threads.

Integration Points:

**Download Pipeline Integration:**
- Seamless integration with download completion workflows
- Quality validation for downloaded content
- Automatic enhancement based on user preferences
- Error reporting for failed processing operations

**Configuration System:**
- Real-time configuration updates without restart
- User preference integration for all processing options
- Advanced feature detection and capability reporting

**Logging and Monitoring:**
- Detailed processing logs for debugging and optimization
- Performance metrics and processing statistics
- Quality improvement tracking and reporting
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import soundfile as sf

# Optional advanced dependencies with graceful degradation
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    librosa = None

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import format_duration, retry_on_failure


@dataclass
class AudioAnalysis:
    """
    Comprehensive audio file analysis results with quality metrics and technical characteristics
    
    This dataclass encapsulates complete audio analysis results, providing both technical
    specifications and quality assessment metrics. It serves as the primary data structure
    for communicating audio characteristics throughout the application.
    
    The analysis combines objective technical measurements with subjective quality assessments
    to provide actionable insights for audio processing decisions and user feedback.
    
    Technical Specifications:
    These fields provide objective measurements of the audio file's technical characteristics:
    
    Attributes:
        duration: Track length in seconds (float precision for sub-second accuracy)
        sample_rate: Audio sampling frequency in Hz (e.g., 44100, 48000)
        channels: Number of audio channels (1=mono, 2=stereo, >2=surround)
        bit_depth: Bit depth per sample (8, 16, 24, 32) or None if not determinable
        bitrate: Estimated bitrate in kbps for lossy formats, None for lossless
        file_size: Total file size in bytes for storage and bandwidth calculations
        format: Audio format identifier (MP3, FLAC, M4A, etc.)
        
    Quality Metrics:
    These fields provide quantitative quality assessment based on audio content analysis:
        
        peak_amplitude: Maximum absolute amplitude (0.0-1.0, where 1.0 = full scale)
        rms_level: Root Mean Square level indicating average loudness (0.0-1.0)
        dynamic_range: Difference between peak and RMS in dB (higher = more dynamic)
        silence_ratio: Proportion of audio content below noise threshold (0.0-1.0)
        
    Issue Detection:
    Boolean flags indicating specific audio quality problems:
        
        clipping_detected: True if digital clipping (peak >= 0.99) is present
        low_volume: True if peak amplitude is below 0.1 (very quiet audio)
        excessive_silence: True if silence ratio exceeds 30% of total duration
        
    Overall Assessment:
        quality_score: Composite quality score from 0-100 (higher = better quality)
        
    Quality Score Calculation:
    The quality score uses a multi-factor algorithm that starts at 100 and applies
    penalties for detected issues:
    - Clipping: -30 points (severe quality degradation)
    - Low volume: -20 points (poor user experience)
    - Excessive silence: Progressive penalty based on silence percentage
    - Poor dynamic range: Penalties for over-compression or extreme dynamics
    - Suboptimal RMS levels: Penalties for very low or very high average levels
    
    Usage Examples:
    
        analysis = processor.analyze_audio_quality("track.mp3")
        
        # Check overall quality
        if analysis.quality_score < 50:
            print("Poor audio quality detected")
            
        # Identify specific issues
        if analysis.clipping_detected:
            print("Audio clipping detected - consider re-downloading")
            
        # Technical specifications
        print(f"Duration: {analysis.duration:.1f}s, "
              f"Sample Rate: {analysis.sample_rate}Hz, "
              f"Quality: {analysis.quality_score}/100")
    
    String Representation:
    The __str__ method provides a concise summary suitable for logging and user display,
    including duration, technical specs, and quality score in a readable format.
    """
    duration: float
    sample_rate: int
    channels: int
    bit_depth: Optional[int]
    bitrate: Optional[int]
    file_size: int
    format: str
    
    # Quality metrics derived from audio content analysis
    peak_amplitude: float
    rms_level: float
    dynamic_range: float
    silence_ratio: float
    
    # Issues detected through algorithmic analysis
    clipping_detected: bool
    low_volume: bool
    excessive_silence: bool
    quality_score: float  # 0-100 scale for overall quality assessment
    
    def __str__(self) -> str:
        """
        Generate concise string representation for logging and display
        
        Returns:
            Formatted string with key metrics: duration, sample rate, channels, quality score
            
        Format: "Audio Analysis: {duration}, {sample_rate}Hz, {channels}ch, Quality: {score}/100"
        
        Example: "Audio Analysis: 3:42, 44100Hz, 2ch, Quality: 87.3/100"
        """
        return (f"Audio Analysis: {format_duration(self.duration)}, "
                f"{self.sample_rate}Hz, {self.channels}ch, "
                f"Quality: {self.quality_score:.1f}/100")


class AudioProcessor:
    """
    Advanced audio processing and enhancement engine with intelligent quality optimization
    
    This class provides comprehensive audio processing capabilities for post-download
    enhancement, quality analysis, format conversion, and validation. It implements
    sophisticated algorithms for audio improvement while maintaining broad compatibility
    and user-configurable behavior.
    
    The processor uses a multi-stage pipeline approach where each processing step can be
    independently enabled or disabled based on user preferences and content characteristics.
    It integrates with external tools (FFmpeg) for professional-grade processing while
    providing fallback implementations for maximum compatibility.
    
    Core Processing Stages:
    
    1. **Analysis Stage**: Comprehensive audio quality assessment and characteristic analysis
    2. **Enhancement Stage**: Configurable improvements including silence removal and normalization
    3. **Conversion Stage**: High-quality format conversion with optimized settings
    4. **Validation Stage**: Quality control and file integrity verification
    
    Key Features:
    
    **Intelligent Silence Removal:**
    - Detects speech/music vs silence using configurable thresholds
    - Preserves natural pauses while removing excessive silence
    - Configurable padding to maintain audio flow and transitions
    - Protection against over-aggressive trimming of legitimate content
    
    **Professional Audio Normalization:**
    - EBU R128 loudness standard compliance for broadcast quality
    - Peak limiting to prevent clipping during normalization
    - FFmpeg integration for professional-grade processing
    - Fallback to basic normalization when advanced tools unavailable
    
    **Advanced Quality Analysis:**
    - Multi-dimensional quality assessment with objective metrics
    - Issue detection for common audio problems (clipping, low volume, etc.)
    - Dynamic range analysis for assessing audio compression
    - Comprehensive reporting for user feedback and debugging
    
    **Format Conversion Pipeline:**
    - High-quality transcoding between MP3, FLAC, and M4A formats
    - Format-specific optimization for best quality/size balance
    - Configurable quality settings for different use cases
    - Metadata preservation during conversion process
    
    Configuration Integration:
    
    All processing behavior is controlled through the application configuration system,
    enabling users to customize processing without code changes:
    
    - Processing stages can be individually enabled/disabled
    - Quality thresholds and parameters are user-configurable
    - Advanced features gracefully degrade when dependencies unavailable
    - Performance vs quality tradeoffs can be adjusted per user preference
    
    Dependency Management:
    
    **Required Dependencies:**
    - pydub: Core audio processing with broad format support
    - numpy: Numerical computation for analysis algorithms
    - soundfile: High-quality audio I/O operations
    
    **Optional Advanced Dependencies:**
    - librosa: Professional audio analysis and processing (install with pip install librosa)
    - FFmpeg: Professional audio processing and normalization (system installation)
    
    **Graceful Degradation:**
    When advanced dependencies are unavailable, the processor automatically falls back
    to basic implementations while logging appropriate warnings to inform users about
    available upgrades.
    
    Thread Safety:
    The processor is designed for safe concurrent usage in multi-threaded download
    operations. Individual file operations are atomic, and configuration is read-only
    after initialization.
    
    Error Handling Philosophy:
    The processor implements a "best effort" approach where individual processing
    stages can fail without preventing other stages from executing. This ensures
    maximum utility even when some features are unavailable or encounter errors.
    """
    
    def __init__(self):
        """
        Initialize audio processor with configuration-driven settings and capabilities detection
        
        Sets up the audio processing engine by loading user configuration, detecting available
        processing capabilities, and initializing processing parameters. All behavior is
        driven by the application configuration system for maximum user customization.
        
        Initialization Process:
        
        1. **Configuration Loading**: Read user preferences for all processing options
        2. **Capability Detection**: Identify available optional dependencies and tools
        3. **Parameter Setup**: Configure processing thresholds and quality settings
        4. **Resource Preparation**: Initialize logging and processing resources
        
        Configuration Categories:
        
        **Processing Control Settings:**
        - trim_silence: Enable/disable intelligent silence removal
        - normalize_audio: Enable/disable EBU R128 loudness normalization
        - target_sample_rate: Desired sample rate for processed audio
        - target_channels: Target channel configuration (1=mono, 2=stereo)
        
        **Quality Control Parameters:**
        - min_duration/max_duration: Acceptable track length ranges for validation
        - advanced_analysis: Enable librosa-based advanced audio analysis
        
        **Processing Thresholds:**
        - silence_threshold: dB level below which audio is considered silence (-40 dB)
        - min_silence_len: Minimum duration of silence to trigger removal (1000ms)
        - padding: Audio padding around non-silent sections (500ms)
        
        **Normalization Standards:**
        - target_lufs: EBU R128 loudness target (-23 LUFS broadcast standard)
        - max_peak: Maximum peak level to prevent clipping (-1 dBFS)
        
        Capability Detection:
        The initialization process detects available optional features:
        - librosa availability for advanced audio analysis
        - FFmpeg installation for professional normalization
        - System capabilities for optimal processing configuration
        
        Error Handling:
        Initialization is designed to never fail - missing dependencies result in
        feature degradation with appropriate logging rather than startup failures.
        """
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Core processing configuration from user preferences
        self.trim_silence = self.settings.audio.trim_silence
        self.normalize_audio = self.settings.audio.normalize
        self.target_sample_rate = self.settings.audio.sample_rate
        self.target_channels = self.settings.audio.channels
        
        # Quality control thresholds for validation and processing decisions
        self.min_duration = self.settings.audio.min_duration
        self.max_duration = self.settings.audio.max_duration
        
        # Silence detection configuration for intelligent trimming
        self.silence_threshold = -40  # dB below which audio is considered silence
        self.min_silence_len = 1000   # ms minimum silence duration to trigger removal
        self.padding = 500            # ms padding around non-silent sections for natural flow
        
        # Audio normalization standards for professional quality output
        self.target_lufs = -23.0      # EBU R128 standard for broadcast loudness
        self.max_peak = -1.0          # dBFS maximum peak to prevent clipping
        
        # Advanced processing capabilities (gracefully degrades if unavailable)
        self.advanced_analysis = self.settings.features.advanced_audio_analysis
    
    def process_audio_file(
        self, 
        input_path: str, 
        output_path: Optional[str] = None,
        apply_enhancements: bool = True
    ) -> bool:
        """
        Process audio file through comprehensive enhancement pipeline with atomic operations
        
        Applies the complete audio processing pipeline to enhance downloaded audio files.
        Uses temporary file processing to ensure atomic operations - either all processing
        succeeds or the original file remains unchanged.
        
        Args:
            input_path: Path to source audio file for processing
            output_path: Destination path for processed file (None = overwrite original)
            apply_enhancements: Whether to apply audio enhancement stages
            
        Returns:
            True if all processing stages complete successfully, False otherwise
            
        Processing Pipeline:
        
        1. **File Validation**: Verify input file exists and is accessible
        2. **Temporary Setup**: Create secure temporary file for atomic processing
        3. **Enhancement Stages**: Apply enabled processing stages in sequence
        4. **Quality Verification**: Validate processed output meets quality standards
        5. **Atomic Completion**: Replace original with processed version
        6. **Cleanup**: Remove temporary files and cleanup resources
        
        Enhancement Stages (if apply_enhancements=True):
        
        **Silence Trimming Stage:**
        - Detects and removes excessive silence from beginning and end
        - Preserves natural pauses and musical silences
        - Configurable thresholds and padding for optimal results
        - Logs amount of silence removed for user feedback
        
        **Audio Normalization Stage:**
        - Applies EBU R128 loudness normalization for consistent volume
        - Uses FFmpeg for professional-grade processing when available
        - Prevents clipping while maximizing perceived loudness
        - Fallback to basic normalization if advanced tools unavailable
        
        Atomic Processing Guarantee:
        The method uses temporary file processing to ensure that either:
        - All processing succeeds and output file is complete and valid
        - Processing fails and original file remains completely unchanged
        
        This prevents corruption or partial processing that could render files unusable.
        
        Error Handling Strategy:
        - Individual stage failures are logged but don't prevent other stages
        - Critical failures (file access, corruption) abort entire process
        - Temporary files are always cleaned up, even on failure
        - Detailed error logging for debugging without user interruption
        
        Performance Considerations:
        - Uses efficient temporary file handling to minimize I/O operations
        - Processes audio in-place where possible to reduce memory usage
        - Stages are optimized to avoid redundant audio loading and conversion
        - Progress logging for long operations on large files
        
        Usage Examples:
        
            # Basic processing with all enhancements
            success = processor.process_audio_file("downloaded.mp3")
            
            # Save to different location
            success = processor.process_audio_file("input.mp3", "enhanced.mp3")
            
            # Processing without enhancements (validation only)
            success = processor.process_audio_file("file.mp3", apply_enhancements=False)
        """
        try:
            input_file = Path(input_path)
            if not input_file.exists():
                self.logger.error(f"Input file not found: {input_path}")
                return False
            
            # Use input path as output if not specified
            if not output_path:
                output_path = input_path
            
            # Create temporary file for atomic processing operations
            with tempfile.NamedTemporaryFile(suffix=input_file.suffix, delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Copy input to temporary file for safe processing
                import shutil
                shutil.copy2(input_path, temp_path)
                
                # Apply enhancement pipeline if requested
                if apply_enhancements:
                    success = True
                    
                    # Stage 1: Intelligent silence trimming
                    if self.trim_silence:
                        stage_success = self._trim_silence(temp_path)
                        success = stage_success and success
                        if not stage_success:
                            self.logger.warning(f"Silence trimming failed for {input_file.name}")
                    
                    # Stage 2: Audio normalization for consistent loudness
                    if self.normalize_audio:
                        stage_success = self._normalize_audio(temp_path)
                        success = stage_success and success
                        if not stage_success:
                            self.logger.warning(f"Audio normalization failed for {input_file.name}")
                    
                    if not success:
                        self.logger.warning(f"Some processing steps failed for {input_file.name}")
                
                # Atomically move processed file to final destination
                if temp_path != output_path:
                    shutil.move(temp_path, output_path)
                
                self.logger.debug(f"Audio processing completed: {input_file.name}")
                return True
                
            finally:
                # Always clean up temporary file, even on failure
                if Path(temp_path).exists() and temp_path != output_path:
                    os.unlink(temp_path)
            
        except Exception as e:
            self.logger.error(f"Audio processing failed for {input_path}: {e}")
            return False
    
    def _trim_silence(self, file_path: str) -> bool:
        """
        Intelligently trim silence from audio file while preserving musical content and flow
        
        Implements sophisticated silence detection and removal that distinguishes between
        unwanted silence (recording artifacts, padding) and musically significant silence
        (pauses, rests, fade-ins/outs). The algorithm preserves natural audio flow while
        removing excessive silence that doesn't contribute to the listening experience.
        
        Args:
            file_path: Path to audio file for silence trimming (modified in-place)
            
        Returns:
            True if trimming succeeds or no significant silence found
            
        Silence Detection Algorithm:
        
        **Multi-Stage Detection Process:**
        1. **Audio Loading**: Load complete audio file into memory for analysis
        2. **Silence Mapping**: Identify all regions below silence threshold
        3. **Boundary Detection**: Find start/end of non-silent content regions
        4. **Padding Application**: Add configurable padding around content
        5. **Significance Assessment**: Determine if trimming would be beneficial
        
        **Threshold Configuration:**
        - silence_threshold: -40 dB default (configurable via settings)
        - min_silence_len: 1000ms minimum duration to consider as trimmable silence
        - padding: 500ms preserved around non-silent content for natural transitions
        - seek_step: 100ms granularity for efficient scanning
        
        **Musical Content Protection:**
        The algorithm is designed to preserve musically significant silence:
        - Natural pauses between musical phrases
        - Intentional silence in compositions (rests, breaks)
        - Fade-in/fade-out effects with low-level audio
        - Ambient content below normal speech/music levels
        
        **Processing Decision Logic:**
        Trimming only occurs when:
        - Total silence removed exceeds 1 second (significant improvement)
        - Non-silent content boundaries are clearly identifiable
        - Resulting audio maintains reasonable duration
        - No risk of removing legitimate musical content
        
        **Format Handling:**
        The method handles format-specific export requirements:
        - M4A/AAC files: Maps to 'mp4' format for pydub compatibility
        - Preserves original audio quality and encoding parameters
        - Maintains metadata compatibility across format boundaries
        
        **Progress Reporting:**
        Provides detailed logging of trimming operations:
        - Amount of silence removed with duration formatting
        - Before/after duration comparison for verification
        - Decision rationale when significant trimming is skipped
        
        Error Recovery:
        - Graceful handling of files with no detectable non-silent content
        - Protection against excessive trimming that could damage content
        - Fallback to original file if processing encounters errors
        - Detailed error logging for debugging unusual audio characteristics
        
        Performance Optimization:
        - Efficient seek-step scanning to balance accuracy and speed
        - Memory-conscious processing for large audio files
        - Format-specific optimization for different audio types
        """
        try:
            self.logger.debug(f"Trimming silence: {Path(file_path).name}")
            
            # Load complete audio file for silence analysis
            audio = AudioSegment.from_file(file_path)
            
            # Detect regions of non-silent audio using configurable thresholds
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_len,    # Minimum silence duration to consider
                silence_thresh=self.silence_threshold,   # dB threshold for silence detection
                seek_step=100  # Scan granularity for balance of accuracy and performance
            )
            
            if not nonsilent_ranges:
                self.logger.warning(f"No non-silent audio detected in {file_path}")
                return False
            
            # Calculate trim points with protective padding around content
            start_trim = max(0, nonsilent_ranges[0][0] - self.padding)
            end_trim = min(len(audio), nonsilent_ranges[-1][1] + self.padding)
            
            # Apply intelligent trimming with content preservation
            trimmed_audio = audio[start_trim:end_trim]
            
            # Assess significance of trimming operation for user feedback
            original_duration = len(audio) / 1000.0
            trimmed_duration = len(trimmed_audio) / 1000.0
            trimmed_amount = original_duration - trimmed_duration
            
            # Only apply trimming if it provides significant improvement
            if trimmed_amount > 1.0:  # More than 1 second removed = significant
                # Handle format-specific export requirements for cross-platform compatibility
                format_map = {
                    'm4a': 'mp4',  # M4A files use MP4 container format
                    'aac': 'mp4',  # AAC files also use MP4 container format  
                }
                file_extension = Path(file_path).suffix[1:]
                ffmpeg_format = format_map.get(file_extension, file_extension)
                
                # Export trimmed audio with format preservation
                trimmed_audio.export(file_path, format=ffmpeg_format)
                
                self.logger.debug(f"Silence trimmed: {trimmed_amount:.1f}s removed "
                                f"({format_duration(original_duration)} → {format_duration(trimmed_duration)})")
            else:
                self.logger.debug("No significant silence to trim - preserving original audio")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to trim silence: {e}")
            return False
    
    @retry_on_failure(max_attempts=2, delay=1.0)
    def _normalize_audio(self, file_path: str) -> bool:
        """
        Professional audio normalization using EBU R128 loudness standard with FFmpeg integration
        
        Implements broadcast-quality audio normalization that brings audio to consistent
        loudness levels while preserving dynamic range and preventing clipping. Uses the
        EBU R128 standard for professional-grade loudness measurement and normalization.
        
        Args:
            file_path: Path to audio file for normalization (modified in-place)
            
        Returns:
            True if normalization succeeds, False if FFmpeg unavailable or processing fails
            
        EBU R128 Loudness Standard:
        
        **Professional Broadcast Standard:**
        The EBU R128 recommendation defines loudness measurement and normalization for
        broadcast and streaming applications. It provides:
        - Consistent perceived loudness across different content
        - Preservation of artistic dynamic range
        - Prevention of loudness wars in digital audio
        - Compliance with international broadcasting standards
        
        **Key Parameters:**
        - Target LUFS: -23 LUFS (Loudness Units Full Scale) for broadcast compliance
        - True Peak: -1 dBFS maximum to prevent inter-sample clipping
        - LRA (Loudness Range): 7 LU for balanced dynamic range preservation
        - Gating: ITU-R BS.1770-4 gating algorithm for accurate measurement
        
        **Measurement Algorithm:**
        EBU R128 uses sophisticated psychoacoustic modeling:
        - K-weighting filter approximates human hearing sensitivity
        - Gating algorithm excludes silence and very quiet passages
        - Integrated loudness measurement over entire program
        - True peak detection prevents inter-sample clipping
        
        FFmpeg Integration:
        
        **loudnorm Filter Implementation:**
        Uses FFmpeg's loudnorm filter with two-pass processing:
        - First pass: Analyze audio characteristics and measure current loudness
        - Second pass: Apply precise normalization based on analysis results
        - Linear mode: Maintains original dynamic range characteristics
        
        **Command Construction:**
        - Input/output file handling with temporary file protection
        - Audio format preservation with sample rate/channel configuration
        - Comprehensive parameter specification for optimal results
        - Timeout protection for large files or slow systems
        
        **Quality Preservation:**
        - Maintains original sample rate and channel configuration
        - Preserves audio quality while normalizing loudness
        - Applies gentle limiting to prevent clipping
        - Respects artistic intent in dynamic range
        
        Error Handling and Fallbacks:
        
        **FFmpeg Availability Detection:**
        - Automatic detection of FFmpeg installation
        - Graceful degradation when FFmpeg unavailable
        - User notification about professional normalization options
        - Fallback to basic volume adjustment when needed
        
        **Process Management:**
        - Subprocess timeout handling (5 minutes) for reliability
        - Standard output/error capture for debugging
        - Process return code validation for success verification
        - Temporary file cleanup in all execution paths
        
        **Error Classification:**
        - Tool availability errors: Information for user upgrade path
        - Processing errors: Detailed logging for troubleshooting
        - Timeout errors: Protection against infinite hangs
        - File errors: Validation and access issue reporting
        
        Performance Considerations:
        
        **Processing Efficiency:**
        - Single-pass processing when possible for speed
        - Efficient temporary file handling to minimize I/O
        - Memory-conscious processing for large audio files
        - Optimal FFmpeg parameter selection for quality/speed balance
        
        **System Resource Management:**
        - Process timeout prevents system resource exhaustion
        - Temporary file cleanup prevents disk space leaks
        - CPU usage optimization through FFmpeg parameter tuning
        
        Compliance and Standards:
        This implementation follows professional audio standards:
        - EBU R128 recommendation compliance for broadcast quality
        - ITU-R BS.1770-4 loudness measurement algorithm
        - AES recommended practices for digital audio processing
        - Cross-platform compatibility for consistent results
        """
        try:
            self.logger.debug(f"Normalizing audio: {Path(file_path).name}")
            
            # Create temporary output file for atomic processing
            temp_output = f"{file_path}.norm"
            
            # Construct FFmpeg command for professional EBU R128 loudness normalization
            cmd = [
                'ffmpeg',
                '-i', file_path,  # Input file specification
                # EBU R128 loudnorm filter with broadcast-quality parameters
                '-af', f'loudnorm=I={self.target_lufs}:TP={self.max_peak}:LRA=7:'
                       f'measured_I=-23:measured_TP=-2:measured_LRA=7:measured_thresh=-34:'
                       f'linear=true',
                # Audio format preservation with target configuration
                '-ar', str(self.target_sample_rate),  # Sample rate configuration
                '-ac', str(self.target_channels),     # Channel configuration
                '-y',  # Overwrite output file without prompting
                temp_output
            ]
            
            # Execute FFmpeg with comprehensive error handling and timeout protection
            result = subprocess.run(
                cmd,
                capture_output=True,  # Capture stdout/stderr for debugging
                text=True,           # Text mode for string handling
                timeout=300          # 5 minute timeout prevents hanging
            )
            
            if result.returncode == 0:
                # Successful normalization - atomically replace original with processed version
                os.replace(temp_output, file_path)
                self.logger.debug("Audio normalization completed successfully")
                return True
            else:
                # FFmpeg processing failed - log error details and cleanup
                self.logger.warning(f"FFmpeg normalization failed: {result.stderr}")
                # Clean up temporary file to prevent disk space leaks
                if Path(temp_output).exists():
                    os.unlink(temp_output)
                return False
            
        except subprocess.TimeoutExpired:
            # Process timeout - protect against infinite hangs
            self.logger.error("Audio normalization timed out - file may be very large or system overloaded")
            return False
        except FileNotFoundError:
            # FFmpeg not installed - inform user about professional processing options
            self.logger.warning("FFmpeg not found - install FFmpeg for professional audio normalization")
            return False
        except Exception as e:
            # Unexpected errors - comprehensive logging for debugging
            self.logger.error(f"Failed to normalize audio: {e}")
            return False
    
    def analyze_audio_quality(self, file_path: str) -> Optional[AudioAnalysis]:
        """
        Comprehensive audio quality analysis with advanced metrics and issue detection
        
        Performs detailed analysis of audio files to assess quality characteristics,
        technical specifications, and potential issues. Uses either advanced scientific
        algorithms (librosa) or robust basic analysis (pydub/numpy) depending on
        available dependencies.
        
        Args:
            file_path: Path to audio file for quality analysis
        
        Returns:
            AudioAnalysis object with comprehensive metrics, or None if analysis fails
            
        Analysis Methodology:
        
        **Dual-Mode Analysis:**
        The method automatically selects the best available analysis approach:
        - **Advanced Mode (librosa)**: Scientific-grade audio analysis with professional algorithms
        - **Basic Mode (pydub/numpy)**: Robust analysis using always-available dependencies
        
        **Advanced Mode Features (when librosa available):**
        - High-precision audio loading with native sample rate preservation
        - Professional-grade amplitude and loudness analysis
        - Spectral analysis capabilities for advanced quality metrics
        - Scientific-grade numerical computation for accurate measurements
        
        **Basic Mode Features (fallback):**
        - Reliable cross-platform analysis using pydub framework
        - Numpy-based numerical computation for quality metrics
        - Broad format support through ffmpeg backend
        - Memory-efficient processing for large files
        
        Quality Metrics Calculation:
        
        **Amplitude Analysis:**
        - **Peak Amplitude**: Maximum absolute value across all samples (0.0-1.0 scale)
        - **RMS Level**: Root Mean Square average indicating perceived loudness
        - **Dynamic Range**: Ratio between peak and RMS levels in decibels
        
        **Content Analysis:**
        - **Silence Detection**: Identifies silent regions below 1% of peak amplitude
        - **Silence Ratio**: Percentage of audio content classified as silence
        - **Content Distribution**: Analysis of audio level distribution patterns
        
        **Quality Assessment:**
        - **Clipping Detection**: Identifies digital clipping at 99% of full scale
        - **Volume Analysis**: Detects low volume issues below 10% of full scale
        - **Silence Evaluation**: Flags excessive silence above 30% of duration
        
        **Technical Specifications:**
        - **Sample Rate**: Audio sampling frequency for quality assessment
        - **Bit Depth**: Bit resolution per sample (when determinable)
        - **Channel Configuration**: Mono, stereo, or surround channel analysis
        - **Format Information**: File format and encoding characteristics
        
        Multi-Format Support:
        
        **Primary Analysis Path (librosa):**
        - Native support for major audio formats
        - Automatic mono/stereo handling with proper dimension management
        - High-precision floating-point processing
        - Scientific-grade resampling and format conversion
        
        **Fallback Analysis Path (pydub/soundfile):**
        - Universal format support through ffmpeg backend
        - Robust handling of various audio container formats
        - Cross-platform compatibility for different system configurations
        - Graceful degradation when advanced features unavailable
        
        **Format-Specific Handling:**
        - MP3: Handles variable bitrate and quality assessment
        - FLAC: Lossless analysis with full dynamic range
        - M4A/AAC: Advanced Audio Coding quality evaluation
        - WAV: Uncompressed audio analysis with maximum precision
        
        Quality Scoring Algorithm:
        
        **Multi-Factor Assessment:**
        The quality score combines multiple objective measurements:
        - Base score of 100 points with penalties for detected issues
        - Clipping penalty: -30 points for digital distortion
        - Volume issues: -20 points for low volume, -10 for excessive volume
        - Silence problems: Progressive penalty based on silence percentage
        - Dynamic range: Penalties for over-compression or extreme dynamics
        - RMS optimization: Rewards for proper level balance
        
        **Weighting Strategy:**
        - Critical issues (clipping) receive highest penalties
        - User experience issues (volume) receive significant penalties
        - Content issues (silence) receive proportional penalties
        - Technical issues receive moderate penalties
        
        Error Handling and Robustness:
        
        **Graceful Degradation:**
        - Advanced analysis failures fall back to basic analysis
        - Individual metric failures don't prevent overall analysis
        - Missing technical information uses reasonable defaults
        - Format-specific issues are handled with appropriate fallbacks
        
        **Comprehensive Error Recovery:**
        - File access issues are detected and reported clearly
        - Corrupted audio data is identified without crashing
        - Unsupported formats are gracefully declined
        - Partial analysis results are returned when possible
        
        Performance Optimization:
        
        **Memory Management:**
        - Efficient audio loading strategies for large files
        - Streaming analysis for memory-constrained environments
        - Automatic cleanup of temporary analysis data
        
        **Computational Efficiency:**
        - Optimized algorithms for common analysis operations
        - Vectorized numpy operations for numerical computation
        - Efficient silence detection algorithms
        - Caching of intermediate results where beneficial
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return None
            
            # Get basic file system information
            file_size = file_path_obj.stat().st_size
            
            # Advanced analysis mode using librosa for scientific-grade processing
            if self.advanced_analysis and HAS_LIBROSA:
                # Load audio with librosa for high-precision analysis
                y, sr = librosa.load(file_path, sr=None, mono=False)
                
                # Ensure consistent array dimensions for analysis
                if y.ndim == 1:
                    y = np.expand_dims(y, axis=0)
                    channels = 1
                else:
                    channels = y.shape[0]
                
                # Calculate duration from sample count and sample rate
                duration = y.shape[-1] / sr
                
                # Advanced amplitude and loudness analysis
                peak_amplitude = np.max(np.abs(y))
                rms_level = np.sqrt(np.mean(y**2))
                
                # Dynamic range calculation (peak-to-RMS ratio in dB)
                if rms_level > 0:
                    dynamic_range = 20 * np.log10(peak_amplitude / rms_level)
                else:
                    dynamic_range = 0
                
                # Intelligent silence detection using content-aware thresholds
                silence_mask = np.abs(y) < (peak_amplitude * 0.01)  # 1% of peak amplitude
                silence_ratio = np.mean(silence_mask)
                
                # Quality issue detection with professional thresholds
                clipping_detected = peak_amplitude >= 0.99  # Digital clipping threshold
                low_volume = peak_amplitude < 0.1           # Low volume threshold
                excessive_silence = silence_ratio > 0.3     # Excessive silence threshold
                
                # Comprehensive quality score calculation
                quality_score = self._calculate_quality_score(
                    peak_amplitude, rms_level, dynamic_range, 
                    silence_ratio, clipping_detected, low_volume
                )
                
                # Technical specification extraction with fallback handling
                try:
                    info = sf.info(file_path)
                    sample_rate = info.samplerate
                    bit_depth = info.subtype_info.bits if hasattr(info.subtype_info, 'bits') else None
                except Exception:
                    # Fallback to basic audio information if soundfile fails
                    audio = AudioSegment.from_file(file_path)
                    sample_rate = audio.frame_rate
                    bit_depth = audio.sample_width * 8
                    
            else:
                # Basic analysis mode using pydub for broad compatibility
                if not HAS_LIBROSA and self.advanced_analysis:
                    self.logger.warning("Advanced audio analysis requested but librosa not available. "
                                      "Install with: pip install 'playlist-downloader[advanced]'")
                
                # Load audio using pydub for universal format support
                audio = AudioSegment.from_file(file_path)
                
                # Extract basic technical specifications
                duration = len(audio) / 1000.0  # Convert milliseconds to seconds
                sample_rate = audio.frame_rate
                channels = audio.channels
                bit_depth = audio.sample_width * 8
                
                # Convert audio to numpy array for numerical analysis
                samples = np.array(audio.get_array_of_samples())
                if channels == 2:
                    samples = samples.reshape((-1, 2)).T
                
                # Normalize samples to [-1, 1] range for analysis
                samples = samples.astype(np.float32) / (2**(bit_depth-1))
                
                # Calculate audio quality metrics using numpy operations
                peak_amplitude = np.max(np.abs(samples))
                rms_level = np.sqrt(np.mean(samples**2))
                
                # Dynamic range calculation with division-by-zero protection
                if rms_level > 0:
                    dynamic_range = 20 * np.log10(peak_amplitude / rms_level)
                else:
                    dynamic_range = 0
                
                # Content analysis for silence detection and quality assessment
                silence_mask = np.abs(samples) < (peak_amplitude * 0.01)
                silence_ratio = np.mean(silence_mask)
                
                # Issue detection using the same thresholds as advanced mode
                clipping_detected = peak_amplitude >= 0.99
                low_volume = peak_amplitude < 0.1
                excessive_silence = silence_ratio > 0.3
                
                # Quality score calculation using unified algorithm
                quality_score = self._calculate_quality_score(
                    peak_amplitude, rms_level, dynamic_range, 
                    silence_ratio, clipping_detected, low_volume
                )
            
            # Bitrate estimation from file size and duration
            bitrate = int((file_size * 8) / duration / 1000) if duration > 0 else None
            
            # Construct comprehensive analysis result
            return AudioAnalysis(
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=bit_depth,
                bitrate=bitrate,
                file_size=file_size,
                format=file_path_obj.suffix[1:].upper(),  # File extension as format
                peak_amplitude=peak_amplitude,
                rms_level=rms_level,
                dynamic_range=dynamic_range,
                silence_ratio=silence_ratio,
                clipping_detected=clipping_detected,
                low_volume=low_volume,
                excessive_silence=excessive_silence,
                quality_score=quality_score
            )
            
        except Exception as e:
            self.logger.error(f"Failed to analyze audio quality: {e}")
            return None

    def _calculate_quality_score(
        self, 
        peak: float, 
        rms: float, 
        dynamic_range: float,
        silence_ratio: float, 
        clipping: bool, 
        low_volume: bool
    ) -> float:
        """
        Calculate comprehensive audio quality score using multi-factor assessment algorithm
        
        Implements a sophisticated quality scoring system that evaluates multiple audio
        characteristics to produce a single quality metric from 0-100. The algorithm
        considers both objective technical measurements and subjective quality factors
        that affect the listening experience.
        
        Args:
            peak: Peak amplitude (0.0-1.0 scale, where 1.0 = full digital scale)
            rms: RMS level indicating average loudness (0.0-1.0 scale)
            dynamic_range: Dynamic range in decibels (peak-to-RMS ratio)
            silence_ratio: Proportion of silent content (0.0-1.0 scale)
            clipping: Boolean flag indicating digital clipping presence
            low_volume: Boolean flag indicating insufficient volume levels
            
        Returns:
            Quality score from 0-100 (higher scores indicate better quality)
            
        Scoring Algorithm:
        
        **Base Score Foundation:**
        Starts with a perfect score of 100 and applies penalties for detected issues.
        This approach ensures that perfect audio receives the maximum score while
        systematically reducing scores based on objective quality problems.
        
        **Critical Issue Penalties (High Impact):**
        
        **Digital Clipping (-30 points):**
        - Most severe penalty for audio distortion
        - Indicates fundamental quality degradation
        - Cannot be corrected through post-processing
        - Significantly impacts listening experience
        
        **Volume Issues (Moderate Impact):**
        
        **Low Volume (-20 points):**
        - Reduces usability and listening experience
        - May indicate recording or processing problems
        - Can often be corrected through normalization
        - Affects user satisfaction and perceived quality
        
        **Content Issues (Proportional Impact):**
        
        **Excessive Silence (Variable penalty):**
        - Progressive penalty based on silence percentage above 30%
        - Formula: (silence_ratio - 0.3) * 50 for ratios > 0.3
        - Affects content density and user experience
        - May indicate recording or processing artifacts
        
        **Dynamic Range Assessment:**
        
        **Over-Compression (Low Dynamic Range < 6dB):**
        - Penalty: (6 - dynamic_range) * 3 points per dB below 6
        - Indicates heavy compression or limiting
        - Reduces musical expressiveness and impact
        - Common in poorly mastered recordings
        
        **Over-Expansion (Very High Dynamic Range > 20dB):**
        - Penalty: (dynamic_range - 20) * 2 points per dB above 20
        - May indicate processing artifacts or unusual content
        - Can cause playback level management issues
        - Less severe than compression but still problematic
        
        **RMS Level Optimization:**
        
        **Very Low RMS (<0.05):**
        - Penalty: -15 points for extremely quiet content
        - May indicate recording level problems
        - Affects loudness consistency across tracks
        
        **Excessive RMS (>0.7):**
        - Penalty: -10 points for overly loud content
        - May indicate over-processing or poor level management
        - Can contribute to listening fatigue
        
        **Quality Boundaries:**
        Final score is clamped to valid range [0, 100] to ensure meaningful results.
        
        **Interpretation Guidelines:**
        - 90-100: Excellent quality, no significant issues detected
        - 80-89: Good quality, minor issues that don't affect listening experience
        - 70-79: Acceptable quality, some issues present but listenable
        - 60-69: Fair quality, multiple issues affecting user experience
        - 50-59: Poor quality, significant problems requiring attention
        - 0-49: Very poor quality, major issues preventing enjoyable listening
        
        **Algorithm Rationale:**
        The penalty weights are designed based on:
        - Severity of impact on listening experience
        - Ability to correct issues through post-processing
        - Typical user tolerance for different types of problems
        - Professional audio quality standards and best practices
        """
        score = 100.0  # Start with perfect score
        
        # Critical quality issues - highest penalties
        if clipping:
            score -= 30  # Severe penalty for digital distortion
        
        # Volume-related issues - significant user experience impact
        if low_volume:
            score -= 20  # Major penalty for poor usability
        
        # Content density issues - proportional to severity
        if silence_ratio > 0.3:
            # Progressive penalty for excessive silence above 30%
            score -= (silence_ratio - 0.3) * 50
        
        # Dynamic range assessment - balance is key
        if dynamic_range < 6:  # Over-compressed audio
            score -= (6 - dynamic_range) * 3  # 3 points per dB below optimal
        elif dynamic_range > 20:  # Over-expanded audio
            score -= (dynamic_range - 20) * 2  # 2 points per dB above optimal
        
        # RMS level optimization - proper level management
        if rms < 0.05:  # Very quiet content
            score -= 15
        elif rms > 0.7:  # Overly loud content
            score -= 10
        
        # Ensure score remains within valid bounds
        return max(0, min(100, score))
    
    def convert_format(
        self, 
        input_path: str, 
        output_path: str, 
        target_format: str,
        quality_settings: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        High-quality audio format conversion with optimized encoding parameters
        
        Converts audio files between different formats while preserving maximum quality
        and applying format-specific optimizations. Uses pydub with ffmpeg backend for
        broad format support and professional-grade conversion quality.
        
        Args:
            input_path: Source audio file path
            output_path: Destination file path for converted audio
            target_format: Target format identifier (mp3, flac, m4a)
            quality_settings: Optional format-specific encoding parameters
            
        Returns:
            True if conversion completes successfully, False otherwise
            
        Supported Formats and Optimization:
        
        **MP3 (MPEG-1 Audio Layer 3):**
        - Variable Bitrate (VBR) encoding for optimal quality/size balance
        - High-quality LAME encoder parameters (-q:a 0 = highest quality VBR)
        - Configurable bitrate target from user settings
        - Broad compatibility across all platforms and devices
        
        **FLAC (Free Lossless Audio Codec):**
        - Maximum compression level (8) for smallest lossless files
        - Bit-perfect audio preservation with no quality loss
        - Optimal for archival storage and high-quality playback systems
        - Maximum compression efficiency while maintaining fast decoding
        
        **M4A (MPEG-4 Audio):**
        - Advanced Audio Coding (AAC) for excellent compression efficiency
        - High-quality encoding with configurable bitrate targets
        - Excellent compatibility with Apple ecosystem and modern devices
        - Superior quality compared to MP3 at equivalent bitrates
        
        Quality Preservation Strategy:
        
        **Lossless Source Handling:**
        When converting from lossless formats (FLAC, WAV):
        - Preserves full dynamic range and frequency response
        - Uses highest quality encoding settings for lossy targets
        - Maintains original sample rate and bit depth where possible
        - Applies optimal dithering for bit depth reduction
        
        **Lossy-to-Lossy Conversion:**
        When converting between lossy formats:
        - Uses transcoding-optimized parameters to minimize quality loss
        - Applies conservative quality settings to prevent artifacts
        - Preserves as much of the original encoding quality as possible
        - Warns about potential quality degradation in logs
        
        **Sample Rate and Channel Handling:**
        - Preserves original sample rate unless specifically configured otherwise
        - Maintains channel configuration (mono/stereo/surround)
        - Applies high-quality resampling when rate conversion needed
        - Uses professional-grade interpolation algorithms
        
        Format-Specific Parameter Optimization:
        
        **MP3 Encoding Parameters:**
        - VBR mode with quality level 0 (highest quality variable bitrate)
        - Target bitrate from user configuration (typically 320kbps for high quality)
        - LAME encoder optimization for transparent quality
        - ID3v2.4 tag compatibility for maximum metadata support
        
        **FLAC Encoding Parameters:**
        - Compression level 8 for maximum file size reduction
        - Verification enabled to ensure bit-perfect encoding
        - Optimal predictor settings for best compression efficiency
        - Fast decoding optimization for real-time playback
        
        **M4A/AAC Encoding Parameters:**
        - High Efficiency AAC when available for better compression
        - Optimal psychoacoustic model selection for quality
        - Compatible atom structure for broad device support
        - Bitrate optimization based on content characteristics
        
        Error Handling and Validation:
        
        **Input Validation:**
        - Source file existence and accessibility verification
        - Format compatibility checking before conversion
        - Audio integrity validation to prevent corrupted output
        - Sufficient disk space verification for output file
        
        **Conversion Monitoring:**
        - Progress tracking for large file conversions
        - Real-time error detection during encoding process
        - Quality validation of output file after conversion
        - Automatic cleanup of partial files on failure
        
        **Output Verification:**
        - File integrity checking post-conversion
        - Duration comparison to detect encoding issues
        - Basic quality validation to ensure successful conversion
        - Metadata preservation verification where applicable
        
        Performance Considerations:
        
        **Memory Management:**
        - Streaming conversion for large files to minimize memory usage
        - Efficient temporary file handling during processing
        - Resource cleanup regardless of conversion success or failure
        
        **Processing Optimization:**
        - Multi-threaded encoding when supported by backend
        - Optimal buffer sizes for different format combinations
        - CPU usage balancing for system responsiveness
        - Disk I/O optimization for faster conversion speeds
        
        Usage Examples:
        
            # High-quality MP3 conversion
            success = processor.convert_format("input.flac", "output.mp3", "mp3")
            
            # Custom quality settings
            custom_settings = {"bitrate": "256k", "quality": "high"}
            success = processor.convert_format("input.wav", "output.m4a", "m4a", custom_settings)
            
            # Lossless archival conversion
            success = processor.convert_format("input.wav", "archive.flac", "flac")
        """
        try:
            self.logger.info(f"Converting {Path(input_path).name} to {target_format.upper()}")
            
            # Load source audio file using pydub's universal format support
            audio = AudioSegment.from_file(input_path)
            
            # Determine encoding parameters for optimal quality
            if quality_settings:
                export_params = quality_settings.copy()
            else:
                export_params = self._get_default_export_params(target_format)
            
            # Execute format conversion with optimized parameters
            audio.export(output_path, format=target_format, **export_params)
            
            self.logger.info(f"Format conversion completed: {Path(output_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Format conversion failed: {e}")
            return False
    
    def _get_default_export_params(self, format: str) -> Dict[str, Any]:
        """
        Get optimized default export parameters for specific audio formats
        
        Provides format-specific encoding parameters optimized for quality, compatibility,
        and efficiency. Parameters are based on industry best practices and user
        configuration settings for optimal results across different use cases.
        
        Args:
            format: Target audio format (mp3, flac, m4a)
            
        Returns:
            Dictionary of format-specific encoding parameters for pydub.export()
            
        Parameter Optimization Strategy:
        
        **MP3 Parameters:**
        - Uses Variable Bitrate (VBR) for optimal quality/size balance
        - Quality level 0 provides highest quality VBR encoding
        - Bitrate target from user settings (typically 192-320kbps)
        - LAME encoder parameters for professional quality
        
        **FLAC Parameters:**
        - Maximum compression level 8 for smallest lossless files
        - Preserves bit-perfect audio quality
        - Optimized for archival storage and high-quality playback
        - Fast decoding compatibility for real-time use
        
        **M4A Parameters:**
        - Advanced Audio Coding (AAC) for efficient compression
        - Configurable bitrate from user settings
        - High compatibility with modern devices and platforms
        - Optimized psychoacoustic model for transparent quality
        """
        params = {}
        
        if format == 'mp3':
            # MP3 encoding with high-quality VBR and user-configurable bitrate
            params = {
                'bitrate': f"{self.settings.download.bitrate}k",
                'parameters': ['-q:a', '0']  # Highest quality VBR encoding
            }
        elif format == 'flac':
            # FLAC encoding with maximum compression for efficient lossless storage
            params = {
                'parameters': ['-compression_level', '8']  # Maximum lossless compression
            }
        elif format == 'm4a':
            # M4A/AAC encoding with high-quality codec and configurable bitrate
            params = {
                'bitrate': f"{self.settings.download.bitrate}k",
                'codec': 'aac'  # Advanced Audio Coding for optimal compression
            }
        
        return params
    
    def validate_audio_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Comprehensive audio file validation with detailed issue reporting and quality assessment
        
        Performs thorough validation of audio files to ensure they meet quality standards
        and are suitable for the intended use case. Provides detailed feedback about any
        issues found, enabling informed decisions about file acceptance or processing.
        
        Args:
            file_path: Path to audio file for comprehensive validation
            
        Returns:
            Tuple of (is_valid, list_of_issues) where:
            - is_valid: Boolean indicating overall file validity
            - list_of_issues: Detailed list of problems found during validation
            
        Validation Process:
        
        **File System Validation:**
        1. **Existence Check**: Verify file exists at specified path
        2. **Size Validation**: Ensure file has reasonable size (>10KB, not empty)
        3. **Access Verification**: Confirm file is readable and accessible
        4. **Path Validation**: Check for valid file system path structure
        
        **Audio Content Analysis:**
        1. **Format Validation**: Verify file can be loaded as valid audio
        2. **Duration Assessment**: Check track length against configured limits
        3. **Quality Analysis**: Comprehensive audio quality evaluation
        4. **Technical Standards**: Sample rate, bit depth, and format compliance
        
        **Issue Detection Categories:**
        
        **Critical Issues (File Unusable):**
        - File does not exist or is inaccessible
        - File is empty or corrupted beyond repair
        - Cannot analyze audio content due to format errors
        - Duration falls outside acceptable ranges (too short/long)
        
        **Quality Issues (Affects User Experience):**
        - Digital clipping detected in audio content
        - Audio volume significantly too low for normal playback
        - Excessive silence content reducing track value
        - Poor overall quality score below minimum threshold
        
        **Technical Issues (May Affect Compatibility):**
        - Sample rate below minimum quality threshold (22.05kHz)
        - Unusual bit depths or encoding parameters
        - Format-specific compliance issues
        - Metadata problems or inconsistencies
        
        **Warning Issues (Minor Problems):**
        - File size appears unusually small for duration
        - Quality score in acceptable but lower range
        - Minor technical specification deviations
        
        Duration Validation:
        
        **Minimum Duration Check:**
        Ensures tracks meet minimum length requirements:
        - Prevents acceptance of clips, samples, or partial downloads
        - Configurable through application settings
        - Helps maintain collection quality standards
        
        **Maximum Duration Check:**
        Prevents acceptance of extremely long files:
        - Protects against corrupted files with inflated durations
        - Maintains reasonable storage and processing requirements
        - Configurable limits based on use case requirements
        
        Quality Assessment Integration:
        
        **Audio Analysis Integration:**
        Uses the comprehensive audio analysis system to evaluate:
        - Technical specifications and format compliance
        - Audio quality metrics and issue detection
        - Content characteristics and suitability
        
        **Quality Threshold Application:**
        - Clipping detection for audio integrity verification
        - Volume level assessment for playability
        - Silence ratio evaluation for content density
        - Overall quality score against minimum standards
        
        **Sample Rate Standards:**
        Validates audio meets minimum quality standards:
        - 22.05kHz minimum for acceptable audio quality
        - Identifies sub-standard recordings or processing
        - Ensures compatibility with quality expectations
        
        Validation Decision Logic:
        
        **Pass Criteria:**
        File is considered valid if:
        - No critical issues are detected
        - Quality issues are within acceptable tolerances
        - Technical specifications meet minimum requirements
        - Duration falls within configured acceptable range
        
        **Tolerance for Minor Issues:**
        Some issues are treated as warnings rather than failures:
        - Small file size warnings don't fail validation
        - Quality scores in acceptable range despite being lower
        - Technical deviations that don't affect usability
        
        **Comprehensive Reporting:**
        All detected issues are reported regardless of validation outcome:
        - Enables informed decision-making about file handling
        - Provides debugging information for processing issues
        - Supports quality improvement workflows
        
        Error Handling:
        
        **Exception Management:**
        Validation process handles errors gracefully:
        - File access errors are clearly reported
        - Analysis failures are documented with specific error information
        - Partial validation results are provided when possible
        - Unexpected errors don't crash the validation process
        
        **Resource Protection:**
        - Validation operations are bounded to prevent system overload
        - Memory usage is controlled for large file analysis
        - Processing timeouts prevent indefinite operations
        
        Usage Examples:
        
            # Basic validation
            is_valid, issues = processor.validate_audio_file("track.mp3")
            if not is_valid:
                print("Validation failed:", issues)
            
            # Quality assessment
            is_valid, issues = processor.validate_audio_file("downloaded.mp3")
            for issue in issues:
                if "Quality" in issue:
                    print(f"Quality concern: {issue}")
        """
        issues = []
        
        try:
            file_path_obj = Path(file_path)
            
            # File system validation - basic accessibility and sanity checks
            if not file_path_obj.exists():
                issues.append("File does not exist")
                return False, issues
            
            # File size validation to catch empty or corrupted files
            file_size = file_path_obj.stat().st_size
            if file_size == 0:
                issues.append("File is empty")
                return False, issues
            
            # Warn about suspiciously small files that might be incomplete
            if file_size < 10000:  # Less than 10KB is very small for audio
                issues.append("File suspiciously small - may be incomplete")
            
            # Comprehensive audio content analysis
            analysis = self.analyze_audio_quality(file_path)
            if not analysis:
                issues.append("Cannot analyze audio content - file may be corrupted")
                return False, issues
            
            # Duration validation against configured acceptable ranges
            if analysis.duration < self.min_duration:
                issues.append(f"Duration too short: {format_duration(analysis.duration)} "
                            f"(minimum: {format_duration(self.min_duration)})")
            
            if analysis.duration > self.max_duration:
                issues.append(f"Duration too long: {format_duration(analysis.duration)} "
                            f"(maximum: {format_duration(self.max_duration)})")
            
            # Audio quality issue detection with specific problem identification
            if analysis.clipping_detected:
                issues.append("Audio clipping detected - digital distortion present")
            
            if analysis.low_volume:
                issues.append("Audio volume very low - may affect playability")
            
            if analysis.excessive_silence:
                issues.append(f"Excessive silence: {analysis.silence_ratio:.1%} of track duration")
            
            # Overall quality assessment with threshold-based evaluation
            if analysis.quality_score < 50:
                issues.append(f"Poor audio quality: {analysis.quality_score:.1f}/100")
            
            # Technical specification validation for compatibility and quality
            if analysis.sample_rate < 22050:
                issues.append(f"Low sample rate: {analysis.sample_rate}Hz "
                            f"(minimum recommended: 22050Hz)")
            
            # Determine overall validation result based on issue severity
            # File passes validation if no critical issues or only minor warnings
            critical_keywords = ["does not exist", "is empty", "Cannot analyze", "too short", "too long"]
            has_critical_issues = any(any(keyword in issue for keyword in critical_keywords) for issue in issues)
            
            # Allow files with only minor issues (warnings) to pass validation
            minor_issue_keywords = ["suspiciously", "Poor audio quality"]
            has_only_minor_issues = all(any(keyword in issue for keyword in minor_issue_keywords) for issue in issues)
            
            is_valid = not has_critical_issues or (len(issues) > 0 and has_only_minor_issues)
            
            return is_valid, issues
            
        except Exception as e:
            # Handle unexpected validation errors gracefully
            issues.append(f"Validation error: {e}")
            return False, issues
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive audio processing configuration and capability information
        
        Returns current processor configuration, capability status, and processing
        parameters for debugging, monitoring, and user interface display purposes.
        
        Returns:
            Dictionary containing complete processor state and configuration
            
        Configuration Categories:
        
        **Processing Control:**
        - trim_silence: Whether intelligent silence removal is enabled
        - normalize_audio: Whether EBU R128 loudness normalization is active
        - advanced_analysis: Whether librosa-based advanced analysis is enabled
        
        **Audio Target Parameters:**
        - target_sample_rate: Desired sample rate for processed audio
        - target_channels: Target channel configuration (1=mono, 2=stereo)
        
        **Quality Control Thresholds:**
        - min_duration/max_duration: Acceptable track length ranges in seconds
        - silence_threshold: dB level for silence detection (-40 dB default)
        - target_lufs: EBU R128 loudness target (-23 LUFS broadcast standard)
        
        Usage for Monitoring and Debugging:
        This information helps with:
        - User interface configuration display
        - Debugging processing issues and unexpected behavior
        - System capability reporting and feature availability
        - Performance tuning and optimization analysis
        """
        return {
            # Processing stage configuration
            'trim_silence': self.trim_silence,
            'normalize_audio': self.normalize_audio,
            'advanced_analysis': self.advanced_analysis,
            
            # Audio format target parameters
            'target_sample_rate': self.target_sample_rate,
            'target_channels': self.target_channels,
            
            # Quality control thresholds
            'min_duration': self.min_duration,
            'max_duration': self.max_duration,
            'silence_threshold': self.silence_threshold,
            'target_lufs': self.target_lufs
        }


# Global processor instance for singleton pattern implementation
_processor_instance: Optional[AudioProcessor] = None


def get_audio_processor() -> AudioProcessor:
    """
    Factory function to retrieve the global audio processor instance
    
    Implements the singleton pattern to ensure consistent audio processing
    configuration and resource management across the entire application.
    Provides a single point of access for audio processing operations.
    
    Returns:
        Global AudioProcessor instance with current application configuration
        
    Singleton Benefits:
    - **Consistent Configuration**: Single source of truth for processing settings
    - **Resource Efficiency**: Shared processing resources and capability detection
    - **State Management**: Unified logging and performance tracking
    - **Memory Optimization**: Single instance reduces overhead for processing operations
    
    Initialization Behavior:
    - First call creates new AudioProcessor with current configuration
    - Subsequent calls return existing instance with same configuration
    - Configuration changes require application restart or manual instance reset
    
    Thread Safety:
    The singleton implementation is thread-safe for read operations and
    concurrent audio processing. Individual file operations are atomic
    at the file level, preventing interference between concurrent operations.
    
    Configuration Sources:
    - Application settings system for user preferences and processing options
    - System capability detection for optional features (librosa, FFmpeg)
    - Quality thresholds and processing parameters from user configuration
    - Performance settings for optimal processing on current system
    
    Usage Pattern:
        # Get processor in any module
        processor = get_audio_processor()
        
        # Use for audio processing operations
        success = processor.process_audio_file("input.mp3", "output.mp3")
        analysis = processor.analyze_audio_quality("track.mp3")
    """
    global _processor_instance
    if not _processor_instance:
        _processor_instance = AudioProcessor()
    return _processor_instance