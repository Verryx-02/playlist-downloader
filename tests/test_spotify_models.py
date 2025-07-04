"""Test Spotify data models"""

import pytest
from datetime import datetime
from src.spotify.models import (
    SpotifyArtist, 
    SpotifyAlbum, 
    SpotifyTrack, 
    PlaylistTrack,
    TrackStatus
)

class TestSpotifyModels:
    """Test Spotify data models"""
    
    def test_spotify_artist_creation(self):
        """Test SpotifyArtist creation from data"""
        data = {
            'id': 'artist123',
            'name': 'Test Artist',
            'external_urls': {'spotify': 'https://spotify.com/artist/artist123'}
        }
        artist = SpotifyArtist.from_spotify_data(data)
        
        assert artist.id == 'artist123'
        assert artist.name == 'Test Artist'
        assert artist.external_urls['spotify'] == 'https://spotify.com/artist/artist123'
    
    def test_spotify_track_properties(self):
        """Test SpotifyTrack computed properties"""
        # Create mock data
        artist_data = {'id': 'artist1', 'name': 'Test Artist'}
        album_data = {
            'id': 'album1',
            'name': 'Test Album',
            'album_type': 'album',
            'total_tracks': 10,
            'release_date': '2023-01-01',
            'release_date_precision': 'day',
            'artists': [artist_data]
        }
        track_data = {
            'track': {
                'id': 'track1',
                'name': 'Test Track',
                'artists': [artist_data],
                'album': album_data,
                'duration_ms': 180000,  # 3 minutes
                'explicit': False,
                'popularity': 80,
                'track_number': 1
            }
        }
        
        track = SpotifyTrack.from_spotify_data(track_data)
        
        assert track.duration_str == "3:00"
        assert track.primary_artist == "Test Artist"
        assert track.all_artists == "Test Artist"
    
    def test_playlist_track_filename(self):
        """Test playlist track filename generation"""
        # Create simplified track for testing
        track = SpotifyTrack(
            id='track1',
            name='Test Song',
            artists=[SpotifyArtist(id='a1', name='Test Artist')],
            album=SpotifyAlbum(
                id='album1', name='Test Album', album_type='album',
                total_tracks=1, release_date='2023', release_date_precision='year',
                artists=[]
            ),
            duration_ms=180000,
            explicit=False,
            popularity=80,
            track_number=1
        )
        
        playlist_track = PlaylistTrack(
            spotify_track=track,
            playlist_position=1
        )
        
        filename = playlist_track.filename
        assert "01 - Test Artist - Test Song" in filename
