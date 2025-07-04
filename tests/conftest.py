"""Test configuration and fixtures"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = Mock()
    settings.download.output_directory = "~/test_music"
    settings.download.format = "mp3"
    settings.download.quality = "high"
    settings.lyrics.enabled = True
    settings.lyrics.primary_source = "genius"
    return settings

@pytest.fixture
def sample_track_data():
    """Sample track data for testing"""
    return {
        'track': {
            'id': 'test_track_123',
            'name': 'Test Song',
            'artists': [{'id': 'artist_123', 'name': 'Test Artist'}],
            'album': {
                'id': 'album_123',
                'name': 'Test Album',
                'album_type': 'album',
                'total_tracks': 12,
                'release_date': '2023-01-01',
                'release_date_precision': 'day',
                'artists': [{'id': 'artist_123', 'name': 'Test Artist'}]
            },
            'duration_ms': 210000,  # 3:30
            'explicit': False,
            'popularity': 75,
            'track_number': 3
        }
    }