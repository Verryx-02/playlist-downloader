"""
Audio processing utilities for post-download enhancement
Handles silence removal, normalization, format conversion, and quality analysis
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

# Optional advanced dependencies
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    librosa = None

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import format_duration, format_file_size, retry_on_failure


@dataclass
class AudioAnalysis:
    """Audio file analysis results"""
    duration: float
    sample_rate: int
    channels: int
    bit_depth: Optional[int]
    bitrate: Optional[int]
    file_size: int
    format: str
    
    # Quality metrics
    peak_amplitude: float
    rms_level: float
    dynamic_range: float
    silence_ratio: float
    
    # Issues detected
    clipping_detected: bool
    low_volume: bool
    excessive_silence: bool
    quality_score: float  # 0-100
    
    def __str__(self) -> str:
        return (f"Audio Analysis: {format_duration(self.duration)}, "
                f"{self.sample_rate}Hz, {self.channels}ch, "
                f"Quality: {self.quality_score:.1f}/100")


class AudioProcessor:
    """Audio processing and enhancement utilities"""
    
    def __init__(self):
        """Initialize audio processor"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Processing settings
        self.trim_silence = self.settings.audio.trim_silence
        self.normalize_audio = self.settings.audio.normalize
        self.target_sample_rate = self.settings.audio.sample_rate
        self.target_channels = self.settings.audio.channels
        
        # Quality thresholds
        self.min_duration = self.settings.audio.min_duration
        self.max_duration = self.settings.audio.max_duration
        
        # Silence detection settings
        self.silence_threshold = -40  # dB
        self.min_silence_len = 1000   # ms
        self.padding = 500            # ms padding around non-silent parts
        
        # Normalization settings
        self.target_lufs = -23.0      # EBU R128 standard
        self.max_peak = -1.0          # dBFS
        
        # Advanced processing (if enabled)
        self.advanced_analysis = self.settings.features.advanced_audio_analysis
    
    def process_audio_file(
        self, 
        input_path: str, 
        output_path: Optional[str] = None,
        apply_enhancements: bool = True
    ) -> bool:
        """
        Process audio file with configured enhancements
        
        Args:
            input_path: Path to input audio file
            output_path: Path for output file (None to overwrite input)
            apply_enhancements: Whether to apply audio enhancements
            
        Returns:
            True if processing successful
        """
        try:
            input_file = Path(input_path)
            if not input_file.exists():
                self.logger.error(f"Input file not found: {input_path}")
                return False
            
            # Use input path as output if not specified
            if not output_path:
                output_path = input_path
            
            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=input_file.suffix, delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Copy input to temp file
                import shutil
                shutil.copy2(input_path, temp_path)
                
                # Apply processing steps
                if apply_enhancements:
                    success = True
                    
                    # Trim silence
                    if self.trim_silence:
                        success = self._trim_silence(temp_path) and success
                    
                    # Normalize audio
                    if self.normalize_audio:
                        success = self._normalize_audio(temp_path) and success
                    
                    if not success:
                        self.logger.warning(f"Some processing steps failed for {input_file.name}")
                
                # Move processed file to output location
                if temp_path != output_path:
                    shutil.move(temp_path, output_path)
                
                self.logger.debug(f"Audio processing completed: {input_file.name}")
                return True
                
            finally:
                # Clean up temp file
                if Path(temp_path).exists() and temp_path != output_path:
                    os.unlink(temp_path)
            
        except Exception as e:
            self.logger.error(f"Audio processing failed for {input_path}: {e}")
            return False
    
    def _trim_silence(self, file_path: str) -> bool:
        """
        Trim silence from beginning and end of audio file
        
        Args:
            file_path: Path to audio file to process
            
        Returns:
            True if successful
        """
        try:
            self.logger.debug(f"Trimming silence: {Path(file_path).name}")
            
            # Load audio file
            audio = AudioSegment.from_file(file_path)
            
            # Detect non-silent parts
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_len,
                silence_thresh=self.silence_threshold,
                seek_step=100  # Check every 100ms
            )
            
            if not nonsilent_ranges:
                self.logger.warning(f"No non-silent audio detected in {file_path}")
                return False
            
            # Calculate trim points with padding
            start_trim = max(0, nonsilent_ranges[0][0] - self.padding)
            end_trim = min(len(audio), nonsilent_ranges[-1][1] + self.padding)
            
            # Apply trimming
            trimmed_audio = audio[start_trim:end_trim]
            
            # Check if significant trimming occurred
            original_duration = len(audio) / 1000.0
            trimmed_duration = len(trimmed_audio) / 1000.0
            trimmed_amount = original_duration - trimmed_duration
            
            if trimmed_amount > 1.0:  # More than 1 second trimmed
                # Export trimmed audio
                trimmed_audio.export(file_path, format=Path(file_path).suffix[1:])
                
                self.logger.debug(f"Silence trimmed: {trimmed_amount:.1f}s removed ({format_duration(original_duration)} → {format_duration(trimmed_duration)})")
            else:
                self.logger.debug("No significant silence to trim")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to trim silence: {e}")
            return False
    
    @retry_on_failure(max_attempts=2, delay=1.0)
    def _normalize_audio(self, file_path: str) -> bool:
        """
        Normalize audio using FFmpeg with EBU R128 loudness normalization
        
        Args:
            file_path: Path to audio file to normalize
            
        Returns:
            True if successful
        """
        try:
            self.logger.debug(f"Normalizing audio: {Path(file_path).name}")
            
            # Create temporary output file
            temp_output = f"{file_path}.norm"
            
            # FFmpeg command for EBU R128 loudness normalization
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-af', f'loudnorm=I={self.target_lufs}:TP={self.max_peak}:LRA=7:measured_I=-23:measured_TP=-2:measured_LRA=7:measured_thresh=-34:linear=true',
                '-ar', str(self.target_sample_rate),
                '-ac', str(self.target_channels),
                '-y',  # Overwrite output
                temp_output
            ]
            
            # Execute FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Replace original with normalized version
                os.replace(temp_output, file_path)
                self.logger.debug("Audio normalization completed")
                return True
            else:
                self.logger.warning(f"FFmpeg normalization failed: {result.stderr}")
                # Clean up temp file
                if Path(temp_output).exists():
                    os.unlink(temp_output)
                return False
            
        except subprocess.TimeoutExpired:
            self.logger.error("Audio normalization timed out")
            return False
        except FileNotFoundError:
            self.logger.warning("FFmpeg not found, skipping normalization")
            return False
        except Exception as e:
            self.logger.error(f"Failed to normalize audio: {e}")
            return False
    
    def analyze_audio_quality(self, file_path: str) -> Optional[AudioAnalysis]:
        """
        Analyze audio file quality and characteristics
    
        Args:
            file_path: Path to audio file
        
        Returns:
            AudioAnalysis object or None if analysis failed
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return None
            
            # Get file info
            file_size = file_path_obj.stat().st_size
            
            # Load audio for analysis
            if self.advanced_analysis and HAS_LIBROSA:
                # Use librosa for advanced analysis
                y, sr = librosa.load(file_path, sr=None, mono=False)
                
                # Ensure stereo format for analysis
                if y.ndim == 1:
                    y = np.expand_dims(y, axis=0)
                    channels = 1
                else:
                    channels = y.shape[0]
                
                duration = y.shape[-1] / sr
                
                # Calculate audio metrics
                peak_amplitude = np.max(np.abs(y))
                rms_level = np.sqrt(np.mean(y**2))
                
                # Dynamic range (difference between peak and RMS in dB)
                if rms_level > 0:
                    dynamic_range = 20 * np.log10(peak_amplitude / rms_level)
                else:
                    dynamic_range = 0
                
                # Silence detection
                silence_mask = np.abs(y) < (peak_amplitude * 0.01)  # 1% of peak
                silence_ratio = np.mean(silence_mask)
                
                # Quality assessment
                clipping_detected = peak_amplitude >= 0.99
                low_volume = peak_amplitude < 0.1
                excessive_silence = silence_ratio > 0.3
                
                # Calculate quality score
                quality_score = self._calculate_quality_score(
                    peak_amplitude, rms_level, dynamic_range, 
                    silence_ratio, clipping_detected, low_volume
                )
                
                # Get format info
                try:
                    info = sf.info(file_path)
                    sample_rate = info.samplerate
                    bit_depth = info.subtype_info.bits if hasattr(info.subtype_info, 'bits') else None
                except Exception:
                    # Fallback if soundfile fails
                    audio = AudioSegment.from_file(file_path)
                    sample_rate = audio.frame_rate
                    bit_depth = audio.sample_width * 8
                    
            else:
                # Basic analysis using pydub (always available)
                if not HAS_LIBROSA and self.advanced_analysis:
                    self.logger.warning("Advanced audio analysis requested but librosa not available. Install with: pip install 'playlist-downloader[advanced]'")
                
                audio = AudioSegment.from_file(file_path)
                
                duration = len(audio) / 1000.0
                sample_rate = audio.frame_rate
                channels = audio.channels
                bit_depth = audio.sample_width * 8
                
                # Convert to numpy for basic analysis
                samples = np.array(audio.get_array_of_samples())
                if channels == 2:
                    samples = samples.reshape((-1, 2)).T
                
                # Normalize to [-1, 1]
                samples = samples.astype(np.float32) / (2**(bit_depth-1))
                
                peak_amplitude = np.max(np.abs(samples))
                rms_level = np.sqrt(np.mean(samples**2))
                
                if rms_level > 0:
                    dynamic_range = 20 * np.log10(peak_amplitude / rms_level)
                else:
                    dynamic_range = 0
                
                silence_mask = np.abs(samples) < (peak_amplitude * 0.01)
                silence_ratio = np.mean(silence_mask)
                
                clipping_detected = peak_amplitude >= 0.99
                low_volume = peak_amplitude < 0.1
                excessive_silence = silence_ratio > 0.3
                
                quality_score = self._calculate_quality_score(
                    peak_amplitude, rms_level, dynamic_range, 
                    silence_ratio, clipping_detected, low_volume
                )
            
            # Estimate bitrate
            bitrate = int((file_size * 8) / duration / 1000) if duration > 0 else None
            
            return AudioAnalysis(
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=bit_depth,
                bitrate=bitrate,
                file_size=file_size,
                format=file_path_obj.suffix[1:].upper(),
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
        Calculate overall quality score (0-100)
        
        Args:
            peak: Peak amplitude (0-1)
            rms: RMS level (0-1)
            dynamic_range: Dynamic range in dB
            silence_ratio: Ratio of silent samples (0-1)
            clipping: Whether clipping is detected
            low_volume: Whether volume is too low
            
        Returns:
            Quality score from 0-100
        """
        score = 100.0
        
        # Penalize clipping
        if clipping:
            score -= 30
        
        # Penalize low volume
        if low_volume:
            score -= 20
        
        # Penalize excessive silence
        if silence_ratio > 0.3:
            score -= (silence_ratio - 0.3) * 50
        
        # Reward good dynamic range
        if dynamic_range < 6:  # Low dynamic range
            score -= (6 - dynamic_range) * 3
        elif dynamic_range > 20:  # Very high dynamic range
            score -= (dynamic_range - 20) * 2
        
        # Penalize very low or very high RMS
        if rms < 0.05:
            score -= 15
        elif rms > 0.7:
            score -= 10
        
        return max(0, min(100, score))
    
    def convert_format(
        self, 
        input_path: str, 
        output_path: str, 
        target_format: str,
        quality_settings: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Convert audio file to different format
        
        Args:
            input_path: Input file path
            output_path: Output file path
            target_format: Target format (mp3, flac, m4a)
            quality_settings: Format-specific quality settings
            
        Returns:
            True if conversion successful
        """
        try:
            self.logger.info(f"Converting {Path(input_path).name} to {target_format.upper()}")
            
            # Load audio
            audio = AudioSegment.from_file(input_path)
            
            # Apply quality settings
            if quality_settings:
                export_params = quality_settings.copy()
            else:
                export_params = self._get_default_export_params(target_format)
            
            # Export in target format
            audio.export(output_path, format=target_format, **export_params)
            
            self.logger.info(f"Format conversion completed: {Path(output_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Format conversion failed: {e}")
            return False
    
    def _get_default_export_params(self, format: str) -> Dict[str, Any]:
        """Get default export parameters for format"""
        params = {}
        
        if format == 'mp3':
            params = {
                'bitrate': f"{self.settings.download.bitrate}k",
                'parameters': ['-q:a', '0']  # High quality VBR
            }
        elif format == 'flac':
            params = {
                'parameters': ['-compression_level', '8']  # Maximum compression
            }
        elif format == 'm4a':
            params = {
                'bitrate': f"{self.settings.download.bitrate}k",
                'codec': 'aac'
            }
        
        return params
    
    def validate_audio_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Validate audio file and return issues found
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            file_path_obj = Path(file_path)
            
            # Check file exists
            if not file_path_obj.exists():
                issues.append("File does not exist")
                return False, issues
            
            # Check file size
            file_size = file_path_obj.stat().st_size
            if file_size == 0:
                issues.append("File is empty")
                return False, issues
            
            if file_size < 10000:  # Less than 10KB
                issues.append("File suspiciously small")
            
            # Analyze audio
            analysis = self.analyze_audio_quality(file_path)
            if not analysis:
                issues.append("Cannot analyze audio content")
                return False, issues
            
            # Check duration
            if analysis.duration < self.min_duration:
                issues.append(f"Duration too short: {format_duration(analysis.duration)}")
            
            if analysis.duration > self.max_duration:
                issues.append(f"Duration too long: {format_duration(analysis.duration)}")
            
            # Check quality issues
            if analysis.clipping_detected:
                issues.append("Audio clipping detected")
            
            if analysis.low_volume:
                issues.append("Audio volume very low")
            
            if analysis.excessive_silence:
                issues.append(f"Excessive silence: {analysis.silence_ratio:.1%}")
            
            if analysis.quality_score < 50:
                issues.append(f"Poor audio quality: {analysis.quality_score:.1f}/100")
            
            # Check sample rate
            if analysis.sample_rate < 22050:
                issues.append(f"Low sample rate: {analysis.sample_rate}Hz")
            
            return len(issues) == 0 or all("suspiciously" in issue or "Poor audio quality" in issue for issue in issues), issues
            
        except Exception as e:
            issues.append(f"Validation error: {e}")
            return False, issues
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get audio processing configuration and stats"""
        return {
            'trim_silence': self.trim_silence,
            'normalize_audio': self.normalize_audio,
            'target_sample_rate': self.target_sample_rate,
            'target_channels': self.target_channels,
            'min_duration': self.min_duration,
            'max_duration': self.max_duration,
            'advanced_analysis': self.advanced_analysis,
            'silence_threshold': self.silence_threshold,
            'target_lufs': self.target_lufs
        }


# Global processor instance
_processor_instance: Optional[AudioProcessor] = None


def get_audio_processor() -> AudioProcessor:
    """Get global audio processor instance"""
    global _processor_instance
    if not _processor_instance:
        _processor_instance = AudioProcessor()
    return _processor_instance