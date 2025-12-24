"""
File management for spot-downloader.

This module handles the file storage architecture with a central tracks/
directory and hard links in playlist directories.

Architecture:
    output_directory/
    ├── database.db
    ├── tracks/                               # Central storage (canonical files)
    │   ├── Queen-Bohemian Rhapsody.m4a
    │   ├── The Beatles-Hey Jude.m4a
    │   └── AC_DC-Back In Black.m4a
    ├── logs/
    │   └── ...
    ├── My Playlist/                          # Playlist view (hard links)
    │   ├── 00001-Bohemian Rhapsody-Queen.m4a → ../tracks/Queen-Bohemian Rhapsody.m4a
    │   ├── 00002-Hey Jude-The Beatles.m4a    → ../tracks/The Beatles-Hey Jude.m4a
    │   └── 00003-Back In Black-AC_DC.m4a     → ../tracks/AC_DC-Back In Black.m4a
    └── Another Playlist/
        ├── 00001-Back In Black-AC_DC.m4a     → ../tracks/AC_DC-Back In Black.m4a
        └── 00002-Bohemian Rhapsody-Queen.m4a → ../tracks/Queen-Bohemian Rhapsody.m4a

File Naming:
    - Canonical (in tracks/): {artist}-{title}.m4a
    - Playlist links: {position:05d}-{title}-{artist}.m4a
    
    Position uses 5-digit padding (00001-99999) to support Spotify's
    maximum of 10,000 tracks per playlist.

Hard Links vs Symlinks:
    - Hard links are preferred (same inode, no storage duplication)
    - Symlinks used as fallback for cross-filesystem scenarios

Usage:
    from spot_downloader.core.file_manager import FileManager
    
    fm = FileManager(output_dir)
    
    # Get canonical path for download
    canonical = fm.get_canonical_path("Queen", "Bohemian Rhapsody")
    
    # After download, create links in all playlists
    fm.create_playlist_link(canonical, "My Playlist", 1, "Queen", "Bohemian Rhapsody")
"""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spot_downloader.core.database import Database


# Characters that are invalid in filenames on various operating systems
_INVALID_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Maximum filename length (conservative for cross-platform compatibility)
_MAX_FILENAME_LENGTH = 200


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use in a filename.
    
    Args:
        name: The string to sanitize.
    
    Returns:
        A sanitized string safe for use in filenames.
    
    Behavior:
        - Replaces invalid characters with underscores
        - Strips leading/trailing whitespace and dots
        - Truncates to maximum length
        - Returns "Unknown" if result is empty
    """
    if not name:
        return "Unknown"
    
    # Replace invalid characters
    result = _INVALID_CHARS_PATTERN.sub("_", name)
    
    # Strip whitespace and dots (dots at start can hide files on Unix)
    result = result.strip(" .")
    
    # Truncate if too long
    if len(result) > _MAX_FILENAME_LENGTH:
        result = result[:_MAX_FILENAME_LENGTH].rstrip(" .")
    
    return result if result else "Unknown"


class FileManager:
    """
    Manages file storage with hard links for playlist views.
    
    This class implements the central storage pattern where:
    - Audio files are stored once in tracks/ directory
    - Playlist directories contain hard links with position-based names
    
    Attributes:
        output_dir: Base output directory.
        tracks_dir: Central tracks storage directory.
    """
    
    def __init__(self, output_dir: Path) -> None:
        """
        Initialize FileManager.
        
        Args:
            output_dir: Base output directory for all files.
        
        Behavior:
            Creates tracks/ directory if it doesn't exist.
        """
        self.output_dir = output_dir
        self.tracks_dir = output_dir / "tracks"
        self.tracks_dir.mkdir(parents=True, exist_ok=True)
    
    def get_canonical_filename(self, artist: str, title: str) -> str:
        """
        Generate canonical filename (no position number).
        
        Format: {artist}-{title}.m4a
        
        Args:
            artist: Artist name.
            title: Track title.
        
        Returns:
            Sanitized filename.
        
        Example:
            get_canonical_filename("Queen", "Bohemian Rhapsody")
            # Returns: "Queen-Bohemian Rhapsody.m4a"
        """
        safe_artist = sanitize_filename(artist)
        safe_title = sanitize_filename(title)
        return f"{safe_artist}-{safe_title}.m4a"
    
    def get_canonical_path(self, artist: str, title: str) -> Path:
        """
        Get full path in central tracks/ directory.
        
        Args:
            artist: Artist name.
            title: Track title.
        
        Returns:
            Path to file in tracks/ directory.
        """
        return self.tracks_dir / self.get_canonical_filename(artist, title)
    
    def get_playlist_filename(self, position: int, title: str, artist: str) -> str:
        """
        Generate playlist-specific filename with position.
        
        Format: {position:05d}-{title}-{artist}.m4a
        
        Uses 5-digit padding to support up to 99,999 tracks
        (Spotify max is 10,000 per playlist).
        
        Args:
            position: Position in playlist (1-indexed).
            title: Track title.
            artist: Artist name.
        
        Returns:
            Sanitized filename with position prefix.
        
        Example:
            get_playlist_filename(42, "Bohemian Rhapsody", "Queen")
            # Returns: "00042-Bohemian Rhapsody-Queen.m4a"
        """
        safe_title = sanitize_filename(title)
        safe_artist = sanitize_filename(artist)
        return f"{position:05d}-{safe_title}-{safe_artist}.m4a"
    
    def get_playlist_dir(self, playlist_name: str) -> Path:
        """
        Get or create playlist directory.
        
        Args:
            playlist_name: Human-readable playlist name.
        
        Returns:
            Path to playlist directory (created if needed).
        """
        safe_name = sanitize_filename(playlist_name)
        playlist_dir = self.output_dir / safe_name
        playlist_dir.mkdir(parents=True, exist_ok=True)
        return playlist_dir
    
    def create_playlist_link(
        self,
        canonical_path: Path,
        playlist_name: str,
        position: int,
        title: str,
        artist: str
    ) -> Path:
        """
        Create hard link in playlist directory.
        
        Args:
            canonical_path: Path to canonical file in tracks/.
            playlist_name: Playlist name for directory.
            position: Track position in playlist.
            title: Track title (for filename).
            artist: Artist name (for filename).
        
        Returns:
            Path to the created link in playlist directory.
        
        Behavior:
            - Tries hard link first (same filesystem)
            - Falls back to symlink (cross-filesystem)
            - Removes existing link if present
        
        Raises:
            FileNotFoundError: If canonical_path doesn't exist.
        """
        if not canonical_path.exists():
            raise FileNotFoundError(f"Canonical file not found: {canonical_path}")
        
        playlist_dir = self.get_playlist_dir(playlist_name)
        link_name = self.get_playlist_filename(position, title, artist)
        link_path = playlist_dir / link_name
        
        # Remove existing link if present
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        
        try:
            # Try hard link first
            os.link(canonical_path, link_path)
        except OSError:
            # Fallback to symlink (cross-filesystem or other issues)
            # Use relative path for symlink
            rel_path = os.path.relpath(canonical_path, playlist_dir)
            link_path.symlink_to(rel_path)
        
        return link_path
    
    def update_all_playlist_links(
        self,
        canonical_path: Path,
        title: str,
        artist: str,
        playlists: list[dict]
    ) -> list[Path]:
        """
        Create/update links in ALL playlists containing a track.
        
        Called after download or --replace.
        
        Args:
            canonical_path: Path to canonical file in tracks/.
            title: Track title.
            artist: Artist name.
            playlists: List of dicts with 'name' and 'position' keys.
                      (From Database.get_playlists_containing_track)
        
        Returns:
            List of created link paths.
        
        Example:
            playlists = db.get_playlists_containing_track(spotify_id)
            links = fm.update_all_playlist_links(
                canonical_path, title, artist, playlists
            )
        """
        links = []
        
        for playlist in playlists:
            try:
                link = self.create_playlist_link(
                    canonical_path=canonical_path,
                    playlist_name=playlist["name"],
                    position=playlist["position"],
                    title=title,
                    artist=artist
                )
                links.append(link)
            except Exception:
                # Log error but continue with other playlists
                pass
        
        return links
    
    def update_playlist_links_from_db(
        self,
        database: "Database",
        spotify_id: str,
        canonical_path: Path,
        title: str,
        artist: str
    ) -> list[Path]:
        """
        Create/update links in ALL playlists containing a track.
        
        Convenience method that queries the database.
        
        Args:
            database: Database instance.
            spotify_id: Spotify track ID.
            canonical_path: Path to canonical file in tracks/.
            title: Track title.
            artist: Artist name.
        
        Returns:
            List of created link paths.
        """
        playlists = database.get_playlists_containing_track(spotify_id)
        return self.update_all_playlist_links(canonical_path, title, artist, playlists)
    
    def cleanup_playlist_orphans(
        self,
        playlist_name: str,
        valid_positions: set[int]
    ) -> int:
        """
        Remove links in playlist that no longer correspond to tracks.
        
        Called during sync to remove tracks that were removed from
        the Spotify playlist.
        
        Args:
            playlist_name: Playlist name.
            valid_positions: Set of valid position numbers.
        
        Returns:
            Number of orphaned links removed.
        """
        playlist_dir = self.get_playlist_dir(playlist_name)
        removed = 0
        
        for file in playlist_dir.iterdir():
            if not (file.is_file() or file.is_symlink()):
                continue
            
            if not file.suffix.lower() == ".m4a":
                continue
            
            try:
                # Extract position from filename (first 5 chars)
                pos_str = file.name.split("-")[0]
                pos = int(pos_str)
                
                if pos not in valid_positions:
                    file.unlink()
                    removed += 1
            except (ValueError, IndexError):
                # Filename doesn't match expected pattern, skip
                pass
        
        return removed
    
    def get_track_file_count(self) -> int:
        """Get number of audio files in tracks/ directory."""
        return sum(1 for f in self.tracks_dir.iterdir() if f.suffix.lower() == ".m4a")
    
    def get_total_size_bytes(self) -> int:
        """Get total size of files in tracks/ directory."""
        return sum(
            f.stat().st_size
            for f in self.tracks_dir.iterdir()
            if f.is_file()
        )
    
    def file_exists_in_tracks(self, artist: str, title: str) -> bool:
        """Check if a track file already exists."""
        return self.get_canonical_path(artist, title).exists()