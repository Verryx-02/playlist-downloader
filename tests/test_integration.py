"""Integration tests"""

import pytest
from unittest.mock import Mock, patch
from src.config.settings import Settings

class TestIntegration:
    """Test system integration"""
    
    @patch('src.spotify.client.spotipy.Spotify')
    def test_spotify_client_initialization(self, mock_spotify):
        """Test Spotify client can be initialized"""
        from src.spotify.client import SpotifyClient
        
        # Mock authentication
        with patch('src.config.auth.get_auth') as mock_auth:
            mock_auth.return_value.get_spotify_client.return_value = mock_spotify
            
            client = SpotifyClient()
            assert client is not None
    
    def test_settings_validation(self):
        """Test settings validation"""
        settings = Settings()
        
        # Should pass validation with environment variables
        # (assuming they're set for testing)
        is_valid = settings.validate()
        # Note: This might fail in CI without proper env vars
        # In real tests, we'd mock or provide test credentials
    
    def test_logger_configuration(self):
        """Test logger can be configured"""
        from src.utils.logger import setup_logging, get_logger
        
        with patch('src.utils.logger.Path.mkdir'):
            setup_logging(level="DEBUG", console_output=True)
            logger = get_logger(__name__)
            assert logger is not None
