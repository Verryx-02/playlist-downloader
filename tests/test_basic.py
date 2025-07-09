"""Basic tests for Playlist-Downloader"""

import pytest
from src.main import cli

def test_cli_import():
    """Test that CLI can be imported"""
    assert cli is not None

def test_placeholder():
    """Placeholder test"""
    assert True
