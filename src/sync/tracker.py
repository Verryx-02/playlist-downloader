"""
Tracklist.txt file management for tracking playlist state and sync status
Handles reading, writing, and parsing of playlist tracking files
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import (
    get_current_timestamp, 
    create_backup_filename,
    validate_and_create_directory
)

from ..spotify.models import SpotifyPlaylist, PlaylistTrack, TrackStatus, LyricsStatus, LyricsSource


class TracklistFormat(Enum):
    """Tracklist file format versions"""
    V1 = "1.0"
    V2 = "2.0"  # Current version with lyrics support


@dataclass
class TracklistEntry:
    """Single entry in tracklist file"""
    position: int
    artist: str
    title: str
    duration: str
    spotify_id: str
    audio_status: TrackStatus
    lyrics_status: LyricsStatus
    local_file_path: Optional[str] = None
    lyrics_file_path: Optional[str] = None
    lyrics_source: Optional[LyricsSource] = None
    
    def get_status_icons(self) -> str:
        """Get status icons for display"""
        audio_icon = "✅" if self.audio_status == TrackStatus.DOWNLOADED else "⏳"
        
        if self.lyrics_status == LyricsStatus.DOWNLOADED:
            lyrics_icon = "🎵"
        elif self.lyrics_status == LyricsStatus.NOT_FOUND:
            lyrics_icon = "🚫"
        elif self.lyrics_status == LyricsStatus.INSTRUMENTAL:
            lyrics_icon = "🎼"
        else:
            lyrics_icon = "⏳"
        
        return f"{audio_icon}{lyrics_icon}"


@dataclass
class TracklistMetadata:
    """Metadata section of tracklist file"""
    playlist_name: str
    spotify_id: str
    created: str
    total_tracks: int
    last_modified: str
    lyrics_enabled: bool
    lyrics_source: str
    format_version: str = TracklistFormat.V2.value
    
    # Optional metadata
    description: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    collaborative: Optional[bool] = None


class TracklistManager:
    """Manages tracklist.txt files for playlist synchronization tracking"""
    
    def __init__(self):
        """Initialize tracklist manager"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # File configuration
        self.backup_tracklist = self.settings.sync.backup_tracklist
        
        # Status icons mapping
        self.status_icons = {
            TrackStatus.PENDING: "⏳",
            TrackStatus.DOWNLOADING: "⬇️",
            TrackStatus.DOWNLOADED: "✅", 
            TrackStatus.FAILED: "❌",
            TrackStatus.SKIPPED: "⏭️"
        }
        
        self.lyrics_icons = {
            LyricsStatus.PENDING: "⏳",
            LyricsStatus.DOWNLOADING: "⬇️", 
            LyricsStatus.DOWNLOADED: "🎵",
            LyricsStatus.FAILED: "❌",
            LyricsStatus.NOT_FOUND: "🚫",
            LyricsStatus.INSTRUMENTAL: "🎼",
            LyricsStatus.SKIPPED: "⏭️"
        }
         # Track created backups for cleanup
        self.created_backups: List[Path] = []
    
    def create_tracklist_file(
    self, 
    playlist: SpotifyPlaylist, 
    output_directory: Path
    ) -> Path:
        """
        Create new tracklist.txt file for playlist with robust path handling
        
        Args:
            playlist: Spotify playlist object
            output_directory: Directory to create file in
            
        Returns:
            Path to created tracklist file
        """
        try:
            # Validate and create output directory
            success, error_msg, validated_dir = validate_and_create_directory(
                output_directory, 
                trusted_source=True
            )
            if not success:
                raise Exception(f"Cannot create output directory: {error_msg}")
            
            tracklist_path = validated_dir / "tracklist.txt"
            
            # Create backup if file exists
            if tracklist_path.exists() and self.backup_tracklist:
                backup_path = create_backup_filename(tracklist_path)
                try:
                    tracklist_path.rename(backup_path)
                    self.created_backups.append(backup_path)
                    self.logger.info(f"Created tracklist backup: {backup_path.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to create backup: {e}")
            
            # Create metadata
            metadata = TracklistMetadata(
                playlist_name=playlist.name,
                spotify_id=playlist.id,
                created=get_current_timestamp(),
                total_tracks=len(playlist.tracks),
                last_modified=get_current_timestamp(),
                lyrics_enabled=self.settings.lyrics.enabled,
                lyrics_source=self.settings.lyrics.primary_source,
                description=playlist.description,
                owner=playlist.owner_name,
                public=playlist.public,
                collaborative=playlist.collaborative
            )
            
            # Write tracklist file
            self._write_tracklist_file(tracklist_path, metadata, playlist.tracks)
            
            # Verify the file was created successfully
            if not tracklist_path.exists():
                raise Exception("Tracklist file was not created successfully")
            
            self.logger.info(f"Created tracklist: {tracklist_path}")
            return tracklist_path
            
        except Exception as e:
            self.logger.error(f"Failed to create tracklist file: {e}")
            raise Exception(f"Tracklist creation failed: {e}")
        
    def _safe_tracklist_path(self, directory: Path) -> Path:
        """
        Get safe tracklist path with validation
        
        Args:
            directory: Directory containing tracklist
            
        Returns:
            Safe tracklist path
        """
        try:
            # Ensure directory exists
            if not directory.exists():
                success, error_msg, validated_dir = validate_and_create_directory(
                    directory, 
                    trusted_source=True
                )
                if not success:
                    raise Exception(f"Cannot access directory: {error_msg}")
                directory = validated_dir
            
            tracklist_path = directory / "tracklist.txt"
            
            # Verify parent directory is accessible
            if not directory.is_dir():
                raise Exception(f"Path is not a directory: {directory}")
            
            return tracklist_path
            
        except Exception as e:
            self.logger.error(f"Failed to create safe tracklist path: {e}")
            raise

    
    def read_tracklist_file(self, tracklist_path: Path) -> Tuple[TracklistMetadata, List[TracklistEntry]]:
        """
        Read and parse tracklist.txt file with robust error handling
        
        Args:
            tracklist_path: Path to tracklist file
            
        Returns:
            Tuple of (metadata, track entries)
        """
        try:
            # Resolve path to handle any relative/symbolic links
            resolved_path = tracklist_path.resolve()
            
            if not resolved_path.exists():
                raise FileNotFoundError(f"Tracklist file not found: {resolved_path}")
            
            if not resolved_path.is_file():
                raise Exception(f"Path exists but is not a file: {resolved_path}")
            
            # Check file is readable
            if not os.access(resolved_path, os.R_OK):
                raise PermissionError(f"Cannot read tracklist file: {resolved_path}")
            
            with open(resolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verify file has content
            if not content.strip():
                raise Exception(f"Tracklist file is empty: {resolved_path}")
            
            # Parse metadata and entries
            metadata = self._parse_metadata(content)
            entries = self._parse_entries(content)
            
            self.logger.debug(f"Read tracklist: {metadata.playlist_name} ({len(entries)} tracks)")
            return metadata, entries
            
        except Exception as e:
            self.logger.error(f"Failed to read tracklist file: {e}")
            raise Exception(f"Tracklist reading failed: {e}")

    
    def update_tracklist_file(
        self, 
        tracklist_path: Path, 
        tracks: List[PlaylistTrack],
        update_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update existing tracklist file with current track status
        
        Args:
            tracklist_path: Path to tracklist file
            tracks: Updated playlist tracks
            update_metadata: Optional metadata updates
        """
        try:
            # Read existing file
            existing_metadata, existing_entries = self.read_tracklist_file(tracklist_path)
            
            # Update metadata
            existing_metadata.last_modified = get_current_timestamp()
            existing_metadata.total_tracks = len(tracks)
            
            if update_metadata:
                for key, value in update_metadata.items():
                    if hasattr(existing_metadata, key):
                        setattr(existing_metadata, key, value)
            
            # Create backup if enabled
            if self.backup_tracklist:
                backup_path = create_backup_filename(tracklist_path)
                tracklist_path.rename(backup_path)
                self.created_backups.append(backup_path)
                self.logger.debug(f"Created update backup: {backup_path.name}")
            
            # Write updated file
            self._write_tracklist_file(tracklist_path, existing_metadata, tracks)
            
            self.logger.info(f"Updated tracklist: {tracklist_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to update tracklist file: {e}")
            raise Exception(f"Tracklist update failed: {e}")
    
    def _write_tracklist_file(
        self, 
        file_path: Path, 
        metadata: TracklistMetadata, 
        tracks: List[PlaylistTrack]
    ) -> None:
        """
        Write tracklist file with metadata and track entries
        
        Args:
            file_path: Path to write file
            metadata: Tracklist metadata
            tracks: Playlist tracks
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write("# Playlist-Downloader Tracklist\n")
            f.write(f"# Format Version: {metadata.format_version}\n")
            f.write(f"# Playlist: {metadata.playlist_name}\n")
            f.write(f"# Spotify ID: {metadata.spotify_id}\n")
            f.write(f"# Created: {metadata.created}\n")
            f.write(f"# Total tracks: {metadata.total_tracks}\n")
            f.write(f"# Last modified: {metadata.last_modified}\n")
            f.write(f"# Lyrics enabled: {metadata.lyrics_enabled}\n")
            f.write(f"# Lyrics source: {metadata.lyrics_source}\n")
            
            # Optional metadata
            if metadata.description:
                f.write(f"# Description: {metadata.description}\n")
            if metadata.owner:
                f.write(f"# Owner: {metadata.owner}\n")
            if metadata.public is not None:
                f.write(f"# Public: {metadata.public}\n")
            if metadata.collaborative is not None:
                f.write(f"# Collaborative: {metadata.collaborative}\n")
            
            f.write("#\n")
            f.write("# Status Icons:\n")
            f.write("# Audio: ✅=Downloaded, ⏳=Pending, ❌=Failed, ⏭️=Skipped\n")
            f.write("# Lyrics: 🎵=Downloaded, 🚫=Not Found, 🎼=Instrumental, ⏳=Pending\n")
            f.write("#\n\n")
            
            # Write track entries
            for track in tracks:
                status_icons = track.get_status_icons()
                
                # Format: STATUS POSITION. Artist - Title (Duration) [spotify:track:ID]
                line = (
                    f"{status_icons} "
                    f"{track.playlist_position:02d}. "
                    f"{track.spotify_track.all_artists} - "
                    f"{track.spotify_track.name} "
                    f"({track.spotify_track.duration_str}) "
                    f"[spotify:track:{track.spotify_track.id}]"
                )
                
                # Add local file info if available
                if track.local_file_path:
                    line += f" -> {Path(track.local_file_path).name}"
                
                # Add lyrics info if available
                if track.lyrics_file_path:
                    line += f" | Lyrics: {Path(track.lyrics_file_path).name}"
                elif track.lyrics_source:
                    line += f" | Lyrics: {track.lyrics_source.value}"
                
                f.write(line + "\n")
    
    def _parse_metadata(self, content: str) -> TracklistMetadata:
        """
        Parse metadata from tracklist file content
        
        Args:
            content: File content
            
        Returns:
            TracklistMetadata object
        """
        metadata = {}
        
        # Extract metadata from comments
        for line in content.split('\n'):
            if line.startswith('# ') and ':' in line:
                key_part = line[2:].split(':', 1)
                if len(key_part) == 2:
                    key = key_part[0].strip().lower().replace(' ', '_')
                    value = key_part[1].strip()
                    metadata[key] = value
        
        # Create metadata object with defaults
        return TracklistMetadata(
            playlist_name=metadata.get('playlist', 'Unknown Playlist'),
            spotify_id=metadata.get('spotify_id', ''),
            created=metadata.get('created', get_current_timestamp()),
            total_tracks=int(metadata.get('total_tracks', 0)),
            last_modified=metadata.get('last_modified', get_current_timestamp()),
            lyrics_enabled=metadata.get('lyrics_enabled', 'true').lower() == 'true',
            lyrics_source=metadata.get('lyrics_source', 'genius'),
            format_version=metadata.get('format_version', TracklistFormat.V1.value),
            description=metadata.get('description'),
            owner=metadata.get('owner'),
            public=metadata.get('public', 'false').lower() == 'true' if 'public' in metadata else None,
            collaborative=metadata.get('collaborative', 'false').lower() == 'true' if 'collaborative' in metadata else None
        )
    
    def _parse_entries(self, content: str) -> List[TracklistEntry]:
        """
        Parse track entries from tracklist file content
        
        Args:
            content: File content
            
        Returns:
            List of TracklistEntry objects
        """
        entries = []
        
        # Pattern to match track lines
        # Example: ✅🎵 01. Artist - Title (3:24) [spotify:track:ID] -> filename.mp3 | Lyrics: genius
        pattern = r'^([✅⏳❌⏭️⬇️])([🎵🚫🎼⏳❌⏭️⬇️])?\s+(\d+)\.\s+(.+?)\s+-\s+(.+?)\s+\(([^)]+)\)\s+\[spotify:track:([^\]]+)\](.*)$'
        
        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            try:
                match = re.match(pattern, line)
                if match:
                    audio_icon, lyrics_icon, position, artist, title, duration, spotify_id, extra = match.groups()
                    
                    # Parse status icons
                    audio_status = self._icon_to_audio_status(audio_icon)
                    lyrics_status = self._icon_to_lyrics_status(lyrics_icon or "⏳")
                    
                    # Parse extra information
                    local_file_path = None
                    lyrics_file_path = None
                    lyrics_source = None
                    
                    if extra:
                        # Parse local file path
                        file_match = re.search(r'->\s+([^|]+)', extra)
                        if file_match:
                            local_file_path = file_match.group(1).strip()
                        
                        # Parse lyrics information
                        lyrics_match = re.search(r'Lyrics:\s+([^|]+)', extra)
                        if lyrics_match:
                            lyrics_info = lyrics_match.group(1).strip()
                            
                            # Check if it's a file path or source
                            if lyrics_info.endswith(('.txt', '.lrc')):
                                lyrics_file_path = lyrics_info
                            else:
                                try:
                                    lyrics_source = LyricsSource(lyrics_info)
                                except ValueError:
                                    lyrics_source = LyricsSource.UNKNOWN
                    
                    entry = TracklistEntry(
                        position=int(position),
                        artist=artist.strip(),
                        title=title.strip(),
                        duration=duration.strip(),
                        spotify_id=spotify_id.strip(),
                        audio_status=audio_status,
                        lyrics_status=lyrics_status,
                        local_file_path=local_file_path,
                        lyrics_file_path=lyrics_file_path,
                        lyrics_source=lyrics_source
                    )
                    
                    entries.append(entry)
                else:
                    self.logger.warning(f"Failed to parse tracklist line {line_num}: {line}")
                    
            except Exception as e:
                self.logger.warning(f"Error parsing tracklist line {line_num}: {e}")
                continue
        
        return entries
    
    def _icon_to_audio_status(self, icon: str) -> TrackStatus:
        """Convert status icon to TrackStatus enum"""
        icon_map = {
            "✅": TrackStatus.DOWNLOADED,
            "⏳": TrackStatus.PENDING,
            "❌": TrackStatus.FAILED,
            "⏭️": TrackStatus.SKIPPED,
            "⬇️": TrackStatus.DOWNLOADING
        }
        return icon_map.get(icon, TrackStatus.PENDING)
    
    def _icon_to_lyrics_status(self, icon: str) -> LyricsStatus:
        """Convert lyrics icon to LyricsStatus enum"""
        icon_map = {
            "🎵": LyricsStatus.DOWNLOADED,
            "🚫": LyricsStatus.NOT_FOUND,
            "🎼": LyricsStatus.INSTRUMENTAL,
            "⏳": LyricsStatus.PENDING,
            "❌": LyricsStatus.FAILED,
            "⏭️": LyricsStatus.SKIPPED,
            "⬇️": LyricsStatus.DOWNLOADING
        }
        return icon_map.get(icon, LyricsStatus.PENDING)
    
    def compare_tracklists(
        self, 
        current_entries: List[TracklistEntry], 
        new_tracks: List[PlaylistTrack]
    ) -> Dict[str, List[Any]]:
        """
        Compare existing tracklist with new playlist state
        
        Args:
            current_entries: Existing tracklist entries
            new_tracks: New playlist tracks
            
        Returns:
            Dictionary with differences: added, removed, moved, modified
        """
        # Create lookup maps
        current_by_id = {entry.spotify_id: entry for entry in current_entries}
        current_by_position = {entry.position: entry for entry in current_entries}
        new_by_id = {track.spotify_track.id: track for track in new_tracks}
        new_by_position = {track.playlist_position: track for track in new_tracks}
        
        # Find differences
        differences = {
            'added': [],      # New tracks not in current
            'removed': [],    # Tracks in current but not in new
            'moved': [],      # Tracks that changed position
            'modified': []    # Tracks with metadata changes
        }
        
        # Find added tracks
        for track in new_tracks:
            if track.spotify_track.id not in current_by_id:
                differences['added'].append(track)
        
        # Find removed tracks
        for entry in current_entries:
            if entry.spotify_id not in new_by_id:
                differences['removed'].append(entry)
        
        # Find moved and modified tracks
        for track in new_tracks:
            if track.spotify_track.id in current_by_id:
                current_entry = current_by_id[track.spotify_track.id]
                
                # Check if position changed
                if current_entry.position != track.playlist_position:
                    differences['moved'].append((current_entry, track))
                
                # Check if metadata changed
                if (current_entry.artist != track.spotify_track.all_artists or
                    current_entry.title != track.spotify_track.name or
                    current_entry.duration != track.spotify_track.duration_str):
                    differences['modified'].append((current_entry, track))
        
        return differences
    
    def get_sync_summary(self, differences: Dict[str, List[Any]]) -> str:
        """
        Generate human-readable sync summary
        
        Args:
            differences: Differences from compare_tracklists
            
        Returns:
            Summary string
        """
        summary_parts = []
        
        if differences['added']:
            summary_parts.append(f"{len(differences['added'])} tracks added")
        
        if differences['removed']:
            summary_parts.append(f"{len(differences['removed'])} tracks removed")
        
        if differences['moved']:
            summary_parts.append(f"{len(differences['moved'])} tracks moved")
        
        if differences['modified']:
            summary_parts.append(f"{len(differences['modified'])} tracks modified")
        
        if not summary_parts:
            return "No changes detected"
        
        return ", ".join(summary_parts)
    
    def find_tracklist_files(self, search_directory: Path) -> List[Path]:
        """
        Find all tracklist.txt files in directory tree
        
        Args:
            search_directory: Directory to search
            
        Returns:
            List of tracklist file paths
        """
        tracklist_files = []
        
        try:
            for tracklist_path in search_directory.rglob("tracklist.txt"):
                if tracklist_path.is_file():
                    tracklist_files.append(tracklist_path)
            
            self.logger.debug(f"Found {len(tracklist_files)} tracklist files in {search_directory}")
            
        except Exception as e:
            self.logger.error(f"Failed to search for tracklist files: {e}")
        
        return tracklist_files
    
    def validate_tracklist_file(self, tracklist_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate tracklist file format and content
        
        Args:
            tracklist_path: Path to tracklist file
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            if not tracklist_path.exists():
                issues.append("File does not exist")
                return False, issues
            
            # Try to parse file
            metadata, entries = self.read_tracklist_file(tracklist_path)
            
            # Validate metadata
            if not metadata.playlist_name:
                issues.append("Missing playlist name")
            
            if not metadata.spotify_id:
                issues.append("Missing Spotify ID")
            
            # Validate entries
            if not entries:
                issues.append("No track entries found")
            
            if metadata.total_tracks != len(entries):
                issues.append(f"Track count mismatch: metadata={metadata.total_tracks}, entries={len(entries)}")
            
            # Check for duplicate positions
            positions = [entry.position for entry in entries]
            if len(set(positions)) != len(positions):
                issues.append("Duplicate track positions found")
            
            # Check for missing Spotify IDs
            missing_ids = [entry.position for entry in entries if not entry.spotify_id]
            if missing_ids:
                issues.append(f"Missing Spotify IDs for positions: {missing_ids}")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            issues.append(f"Parse error: {e}")
            return False, issues

    def cleanup_backups(self) -> None:
            """Clean up tracked backup files"""
            cleaned_count = 0
            for backup_path in self.created_backups:
                try:
                    if backup_path.exists():
                        backup_path.unlink()
                        cleaned_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup backup {backup_path}: {e}")
            
            if cleaned_count > 0:
                self.logger.debug(f"Cleaned up {cleaned_count} backup files")
            
            self.created_backups.clear()

# Global tracklist manager instance
_tracklist_manager: Optional[TracklistManager] = None

def get_tracklist_manager() -> TracklistManager:
    """Get global tracklist manager instance"""
    global _tracklist_manager
    if not _tracklist_manager:
        _tracklist_manager = TracklistManager()
    return _tracklist_manager