"""
Download module for spot-downloader.

This module provides functionality for:
- PHASE 3: Downloading audio from YouTube
- PHASE 4: Fetching lyrics from multiple providers
- PHASE 5: Embedding metadata and lyrics into M4A files

Components:
    - Downloader: Audio download orchestrator (PHASE 3)
    - LyricsFetcher: Multi-provider lyrics fetching
    - MetadataEmbedder: M4A metadata embedding
    - fetch_lyrics_phase4: PHASE 4 orchestration
    - embed_metadata_phase5: PHASE 5 orchestration

Usage:
    from spot_downloader.download import (
        # PHASE 3
        Downloader,
        download_tracks_phase3,
        DownloadStats,
        # PHASE 4
        fetch_lyrics_phase4,
        LyricsStats,
        # PHASE 5
        embed_metadata_phase5,
        EmbedStats,
        # Utilities
        MetadataEmbedder,
        LyricsFetcher,
        Lyrics,
    )
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
from spot_downloader.download.lyrics_phase import (
    fetch_lyrics_phase4,
    LyricsStats,
)
from spot_downloader.download.embed_phase import (
    embed_metadata_phase5,
    EmbedStats,
)

__all__ = [
    # PHASE 3 - Download
    "Downloader",
    "DownloadStats",
    "download_tracks_phase3",
    "get_tracks_needing_download",
    # PHASE 4 - Lyrics
    "fetch_lyrics_phase4",
    "LyricsStats",
    "LyricsFetcher",
    "Lyrics",
    "fetch_lyrics_for_track",
    # PHASE 5 - Embed
    "embed_metadata_phase5",
    "EmbedStats",
    "MetadataEmbedder",
    "embed_track_metadata",
]