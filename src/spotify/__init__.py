# src/spotify/__init__.py
"""
Spotify integration package
Handles Spotify Web API communication and data models
"""

from .client import get_spotify_client, reset_spotify_client, SpotifyClient
from .models import (
    SpotifyPlaylist, 
    SpotifyTrack, 
    SpotifyArtist, 
    SpotifyAlbum,
    PlaylistTrack,
    TrackStatus,
    LyricsStatus,
    LyricsSource,
    AudioFormat,
    DownloadStats
)

__all__ = [
    'get_spotify_client',
    'reset_spotify_client', 
    'SpotifyClient',
    'SpotifyPlaylist',
    'SpotifyTrack',
    'SpotifyArtist', 
    'SpotifyAlbum',
    'PlaylistTrack',
    'TrackStatus',
    'LyricsStatus',
    'LyricsSource', 
    'AudioFormat',
    'DownloadStats'
]
