# src/audio/__init__.py
"""
Audio processing package
Handles audio enhancement, metadata management, and quality control
"""

from .metadata import get_metadata_manager, MetadataManager
from .processor import get_audio_processor, AudioProcessor, AudioAnalysis

__all__ = [
    'get_metadata_manager',
    'MetadataManager',
    'get_audio_processor',
    'AudioProcessor', 
    'AudioAnalysis'
]
