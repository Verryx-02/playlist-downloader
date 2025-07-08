#!/usr/bin/env python3
"""
Setup configuration for Playlist-Downloader
A complete tool for downloading Spotify playlists with lyrics integration
"""

from setuptools import setup, find_packages

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Core requirements (always installed)
core_requirements = [
    "spotipy>=2.22.1",
    "ytmusicapi>=1.3.2", 
    "yt-dlp>=2023.12.30",
    "mutagen>=1.47.0",
    "pydub>=0.25.1",
    "click>=8.1.7",
    "pyyaml>=6.0.1",
    "requests>=2.31.0",
    "ffmpeg-python>=0.2.0",
    "lyricsgenius>=3.0.1",
    "tqdm>=4.66.1",
    "colorama>=0.4.6",
    "python-dotenv>=1.0.0",
    "aiohttp>=3.9.1",
    "asyncio-throttle>=1.0.2",
    "Pillow>=10.0.0",
]

setup(
    name="playlist-downloader",
    version="v0.9.0-beta",
    author="Playlist-Downloader Team",
    author_email="contact@playlist-downloader.com",
    description="Download Spotify playlists locally with YouTube Music integration and lyrics support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/verryx-02/playlist-downloader",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    python_requires=">=3.8",
    install_requires=core_requirements,
    extras_require={
        "advanced": [
            "librosa>=0.10.1",  # Advanced audio analysis
        ],
        "ai": [
            "tensorflow>=2.13.0",  # Future AI features
        ],
        "extra-lyrics": [
            "syncedlyrics>=0.4.0",
        ],
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "black>=23.11.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
        ],
        "all": [
            "librosa>=0.10.1",
            "tensorflow>=2.13.0", 
            "syncedlyrics>=0.4.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "playlist-dl=src.main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "src": ["config/*.yaml"],
    },
    keywords="spotify youtube music download playlist lyrics cli",
    project_urls={
        "Bug Reports": "https://github.com/verryx-02/playlist-downloader/issues",
        "Source": "https://github.com/verryx-02/playlist-downloader",
        "Documentation": "https://github.com/verryx-02/playlist-downloader/wiki",
    },
)