"""
spot-downloader: Download Spotify playlists via YouTube Music.

This package provides a complete workflow for downloading Spotify playlists
by matching tracks on YouTube Music and converting to M4A format with
embedded metadata.

Architecture:
    The download process is split into 3 phases that can be run together
    or separately:
    
    PHASE 1 (spotify/): Fetch metadata from Spotify
        - Connect to Spotify API
        - Fetch playlist or Liked Songs
        - Extract track metadata (title, artist, album, etc.)
        - Store in JSON database
    
    PHASE 2 (youtube/): Match tracks on YouTube Music
        - Search YouTube Music for each track
        - Use fuzzy matching to find best result
        - Verify duration matches
        - Store YouTube URLs in database
    
    PHASE 3 (download/): Download and process audio
        - Download audio from YouTube using yt-dlp
        - Convert to M4A format
        - Fetch lyrics (optional)
        - Embed metadata using mutagen
        - Save with proper filename

Modules:
    core/       - Configuration, database, logging, exceptions
    spotify/    - Spotify API client and metadata fetching
    youtube/    - YouTube Music matching
    download/   - Audio download and metadata embedding
    utils/      - Utility functions
    cli.py      - Command-line interface

Usage:
    Command Line:
        spot --dl --url "https://open.spotify.com/playlist/..."
        spot --dl --url "https://..." --sync
        spot --dl --liked --user-auth
    
    Python API:
        from spot_downloader.core import load_config, Database, setup_logging
        from spot_downloader.spotify import SpotifyClient, fetch_playlist_phase1
        from spot_downloader.youtube import match_tracks_phase2
        from spot_downloader.download import download_tracks_phase3
        
        config = load_config()
        setup_logging(config.output.directory)
        database = Database(config.output.directory / "database.json")
        
        SpotifyClient.init(config.spotify.client_id, config.spotify.client_secret)
        
        playlist, tracks = fetch_playlist_phase1(database, playlist_url)
        match_tracks_phase2(database, tracks, playlist.spotify_id)
        download_tracks_phase3(database, config.output.directory, playlist.spotify_id)

Configuration:
    Requires a config.yaml file in the current directory:
    
        spotify:
          client_id: "your_client_id"
          client_secret: "your_client_secret"
        
        output:
          directory: "~/Desktop/Music/SpotDownloader"
        
        download:
          threads: 4
          cookie_file: null

Dependencies:
    - spotipy: Spotify API client
    - ytmusicapi: YouTube Music API client
    - yt-dlp: YouTube download and extraction
    - mutagen: Audio metadata manipulation
    - rapidfuzz: Fuzzy string matching
    - click: CLI framework
    - tqdm: Progress bars
    - pyyaml: Configuration file parsing
"""

__version__ = "0.1.0"
__author__ = "spot-downloader"
__license__ = "MIT"

# Convenience imports for common usage
from spot_downloader.core import (
    Config,
    ConfigError,
    Database,
    DatabaseError,
    DownloadError,
    MetadataError,
    SpotDownloaderError,
    SpotifyError,
    YouTubeError,
    get_logger,
    load_config,
    setup_logging,
)
from spot_downloader.spotify import SpotifyClient, Track, Playlist

__all__ = [
    # Version
    "__version__",
    # Core
    "Config",
    "load_config",
    "Database",
    "setup_logging",
    "get_logger",
    # Exceptions
    "SpotDownloaderError",
    "ConfigError",
    "DatabaseError",
    "SpotifyError",
    "YouTubeError",
    "DownloadError",
    "MetadataError",
    # Models
    "SpotifyClient",
    "Track",
    "Playlist",
]
