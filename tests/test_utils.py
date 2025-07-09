# tests/test_utils.py
"""Test utilities and helpers"""

import pytest
import tempfile
from pathlib import Path
from src.utils.helpers import (
    sanitize_filename, 
    format_duration, 
    format_file_size,
    calculate_similarity,
    normalize_artist_name,
    normalize_track_title,
    parse_duration_string,
    validate_lyrics_content
)

class TestHelpers:
    """Test helper functions"""
    
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        assert sanitize_filename("Test/File\\Name") == "TestFileName"
        assert sanitize_filename("CON") == "_CON"  # Reserved Windows name
        assert sanitize_filename("Song: Title?") == "Song Title"
        assert sanitize_filename("") == "unknown"
    
    def test_format_duration(self):
        """Test duration formatting"""
        assert format_duration(90) == "1:30"
        assert format_duration(3661) == "1:01:01"
        assert format_duration(0) == "0:00"
        assert format_duration(-10) == "0:00"
    
    def test_format_file_size(self):
        """Test file size formatting"""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(512) == "512 B"
    
    def test_calculate_similarity(self):
        """Test string similarity calculation"""
        assert calculate_similarity("hello", "hello") == 1.0
        assert calculate_similarity("hello", "world") < 0.5
        assert calculate_similarity("", "") == 1.0
        assert calculate_similarity("test", "") == 0.0
    
    def test_normalize_artist_name(self):
        """Test artist name normalization"""
        assert normalize_artist_name("The Beatles") == "beatles"
        assert normalize_artist_name("Artist feat. Other") == "artist"
        assert normalize_artist_name("A Artist") == "artist"
    
    def test_normalize_track_title(self):
        """Test track title normalization"""
        assert normalize_track_title("Song (Remix)") == "song"
        assert normalize_track_title("Track feat. Artist") == "track"
        assert normalize_track_title("Title [Remaster]") == "title"
    
    def test_parse_duration_string(self):
        """Test duration string parsing"""
        assert parse_duration_string("3:45") == 225
        assert parse_duration_string("1:23:45") == 5025
        assert parse_duration_string("invalid") is None
    
    def test_validate_lyrics_content(self):
        """Test lyrics content validation"""
        assert validate_lyrics_content("This is a valid song lyrics content") == True
        assert validate_lyrics_content("short") == False
        assert validate_lyrics_content("instrumental") == False
