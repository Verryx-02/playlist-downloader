"""
Download module for spot-downloader.

This module provides functionality for:
- PHASE 3: Downloading audio from YouTube to tracks/ directory with hard links
- PHASE 4: Fetching lyrics from multiple providers
- PHASE 5: Embedding metadata and lyrics into M4A files

Architecture:
    The download module works with the FileManager's central storage pattern:
    - Audio files are stored ONCE in tracks/ directory (canonical files)
    - Playlist directories contain hard links with position-based names
    - Same track in multiple playlists = 1 file + N hard links

Components:
    - Downloader: Audio download orchestrator (PHASE 3)
    - DownloadProgressBar: Rich progress bar for downloads
    - LyricsFetcher: Multi-provider lyrics fetching (PHASE 4)
    - MetadataEmbedder: M4A metadata embedding (PHASE 5)

Usage:
    from spot_downloader.download import (
        # PHASE 3
        Downloader,
        download_tracks_phase3,
        DownloadStats,
        DownloadProgressBar,
        # PHASE 4
        fetch_lyrics_phase4,
        LyricsStats,
        # PHASE 5
        embed_metadata_phase5,
        EmbedStats,
    )
"""

from spot_downloader.download.downloader import (
    Downloader,
    DownloadProgressBar,
    DownloadStats,
    download_tracks_phase3,
    get_tracks_needing_download,
)

# Phase 4 and 5 imports - these will be implemented later
# For now, we provide placeholder imports that will fail gracefully
try:
    from spot_downloader.download.lyrics import (
        Lyrics,
        LyricsFetcher,
        fetch_lyrics_for_track,
    )
except ImportError:
    Lyrics = None  # type: ignore
    LyricsFetcher = None  # type: ignore
    fetch_lyrics_for_track = None  # type: ignore

try:
    from spot_downloader.download.metadata import (
        MetadataEmbedder,
        embed_track_metadata,
    )
except ImportError:
    MetadataEmbedder = None  # type: ignore
    embed_track_metadata = None  # type: ignore

try:
    from spot_downloader.download.lyrics_phase import (
        fetch_lyrics_phase4,
        LyricsStats,
    )
except ImportError:
    fetch_lyrics_phase4 = None  # type: ignore
    LyricsStats = None  # type: ignore

try:
    from spot_downloader.download.embed_phase import (
        embed_metadata_phase5,
        EmbedStats,
    )
except ImportError:
    embed_metadata_phase5 = None  # type: ignore
    EmbedStats = None  # type: ignore

__all__ = [
    # PHASE 3 - Download
    "Downloader",
    "DownloadProgressBar",
    "DownloadStats",
    "download_tracks_phase3",
    "get_tracks_needing_download",
    # PHASE 4 - Lyrics (will be available after implementation)
    "fetch_lyrics_phase4",
    "LyricsStats",
    "LyricsFetcher",
    "Lyrics",
    "fetch_lyrics_for_track",
    # PHASE 5 - Embed (will be available after implementation)
    "embed_metadata_phase5",
    "EmbedStats",
    "MetadataEmbedder",
    "embed_track_metadata",
]