"""
Spotify integration module for spot-downloader.

This module provides all functionality for interacting with Spotify API:
    - SpotifyClient: Singleton API client for Spotify operations
    - Track, Playlist, LikedSongs: Data models for Spotify entities
    - SpotifyFetcher: PHASE 1 implementation for fetching metadata

Usage:
    from spot_downloader.spotify import (
        SpotifyClient,
        SpotifyFetcher,
        Track, Playlist, LikedSongs,
        fetch_playlist_phase1,
        fetch_liked_songs_phase1
    )
    
    # Initialize client (once at startup)
    SpotifyClient.init(client_id, client_secret)
    
    # Fetch playlist
    playlist, tracks = fetch_playlist_phase1(database, playlist_url)
"""

from spot_downloader.spotify.client import SpotifyClient
from spot_downloader.spotify.fetcher import (
    SpotifyFetcher,
    fetch_liked_songs_phase1,
    fetch_playlist_phase1,
)
from spot_downloader.spotify.models import LikedSongs, Playlist, Track

__all__ = [
    # Client
    "SpotifyClient",
    # Models
    "Track",
    "Playlist",
    "LikedSongs",
    # Fetcher
    "SpotifyFetcher",
    "fetch_playlist_phase1",
    "fetch_liked_songs_phase1",
]
