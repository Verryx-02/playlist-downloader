# src/ytmusic/__init__.py
"""
YouTube Music integration package
Handles search, matching, and audio download from YouTube Music
"""

from .searcher import get_ytmusic_searcher, reset_ytmusic_searcher, YouTubeMusicSearcher, SearchResult
from .downloader import get_downloader, reset_downloader, YouTubeMusicDownloader, DownloadResult

__all__ = [
    'get_ytmusic_searcher',
    'reset_ytmusic_searcher',
    'YouTubeMusicSearcher',
    'SearchResult',
    'get_downloader',
    'reset_downloader', 
    'YouTubeMusicDownloader',
    'DownloadResult'
]