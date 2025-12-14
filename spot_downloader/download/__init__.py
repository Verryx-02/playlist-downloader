"""
Download module for spot-downloader.

This module provides functionality for downloading audio from YouTube
and processing into final M4A files with metadata (PHASE 3).

Components:
    - Downloader: Main download orchestrator
    - MetadataEmbedder: M4A metadata embedding
    - LyricsFetcher: Optional lyrics fetching
    - DownloadStats: Download statistics

Usage:
    from spot_downloader.download import (
        Downloader,
        download_tracks_phase3,
        DownloadStats,
        MetadataEmbedder,
        LyricsFetcher
    )
    
    # Download all pending tracks
    stats = download_tracks_phase3(
        database=db,
        output_dir=Path("/music"),
        playlist_id=playlist_id,
        num_threads=4
    )
    
    print(f"Downloaded: {stats.downloaded}/{stats.total}")
"""

from spot_downloader.download.downloader import (
    Downloader,
    DownloadStats,
    download_tracks_phase3,
    get_tracks_needing_download,
)
from spot_downloader.download.lyrics import (
    Lyrics,
    LyricsFetcher,
    fetch_lyrics_for_track,
)
from spot_downloader.download.metadata import (
    MetadataEmbedder,
    embed_track_metadata,
)

__all__ = [
    # Downloader
    "Downloader",
    "DownloadStats",
    "download_tracks_phase3",
    "get_tracks_needing_download",
    # Metadata
    "MetadataEmbedder",
    "embed_track_metadata",
    # Lyrics
    "Lyrics",
    "LyricsFetcher",
    "fetch_lyrics_for_track",
]
