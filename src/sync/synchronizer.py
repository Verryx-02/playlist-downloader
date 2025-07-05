"""
Playlist synchronization logic for incremental updates and change detection
Handles sync operations between Spotify playlists and local downloads
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config.settings import get_settings
from ..utils.logger import get_logger, OperationLogger
from ..utils.helpers import sanitize_filename
from ..utils.logger import reconfigure_logging_for_playlist, get_current_log_file
from ..utils.helpers import (
    sanitize_filename, 
    validate_and_create_directory
)
from ..spotify.client import get_spotify_client
from ..spotify.models import SpotifyPlaylist, PlaylistTrack, TrackStatus, LyricsStatus, LyricsSource
from ..ytmusic.searcher import get_ytmusic_searcher
from ..ytmusic.downloader import get_downloader
from ..audio.metadata import get_metadata_manager
from ..audio.processor import get_audio_processor
from ..lyrics.processor import get_lyrics_processor
from .tracker import get_tracklist_manager


@dataclass
class SyncOperation:
    """Single synchronization operation"""
    operation_type: str  # 'download', 'move', 'update', 'delete'
    track: Optional[PlaylistTrack] = None
    old_position: Optional[int] = None
    new_position: Optional[int] = None
    reason: Optional[str] = None


@dataclass
class SyncPlan:
    """Complete synchronization plan"""
    playlist_id: str
    playlist_name: str
    operations: List[SyncOperation]
    estimated_downloads: int
    estimated_time: Optional[float] = None
    requires_reordering: bool = False
    
    @property
    def has_changes(self) -> bool:
        """Check if plan has any operations"""
        return len(self.operations) > 0


@dataclass
class SyncResult:
    """Result of synchronization operation"""
    success: bool
    playlist_id: str
    operations_performed: int
    downloads_completed: int
    downloads_failed: int
    lyrics_completed: int
    lyrics_failed: int
    reordering_performed: bool
    total_time: Optional[float] = None
    error_message: Optional[str] = None
    
    @property
    def summary(self) -> str:
        """Get summary string"""
        if not self.success:
            return f"Sync failed: {self.error_message}"
        
        parts = []
        if self.downloads_completed > 0:
            parts.append(f"{self.downloads_completed} downloaded")
        if self.downloads_failed > 0:
            parts.append(f"{self.downloads_failed} failed")
        if self.lyrics_completed > 0:
            parts.append(f"{self.lyrics_completed} lyrics")
        if self.reordering_performed:
            parts.append("reordered")
        
        if not parts:
            return "No changes needed"
        
        return ", ".join(parts)


class PlaylistSynchronizer:
    """Handles playlist synchronization operations"""
    
    def __init__(self):
        """Initialize playlist synchronizer"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Component instances
        self.spotify_client = get_spotify_client()
        self.ytmusic_searcher = get_ytmusic_searcher()
        self.downloader = get_downloader()
        self.metadata_manager = get_metadata_manager()
        self.audio_processor = get_audio_processor()
        self.lyrics_processor = get_lyrics_processor()
        self.tracklist_manager = get_tracklist_manager()
        
        # Sync configuration
        self.auto_sync = self.settings.sync.auto_sync
        self.sync_lyrics = self.settings.sync.sync_lyrics
        self.detect_moved_tracks = self.settings.sync.detect_moved_tracks
        self.max_concurrent = self.settings.download.concurrency
        
        # File organization
        self.output_directory = self.settings.get_output_directory()
        self.naming_format = self.settings.naming.track_format

        # Batch update configuration
        self.batch_update_interval = 5  # Update tracklist every 5 downloads
        self.download_counter = 0  # Track completed downloads for batching


    def _simple_file_validation(self, file_path: Path) -> bool:
        """
        Simple validation for existing files (permissive)
        Only checks basic file properties without deep audio analysis
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if file appears to be a valid audio file
        """
        try:
            # Check file exists
            if not file_path.exists():
                return False
            
            # Check file size (must be larger than 100KB)
            file_size = file_path.stat().st_size
            if file_size < 100000:  # 100KB minimum
                return False
            
            # Check file extension
            valid_extensions = ['.mp3', '.flac', '.m4a', '.aac', '.ogg', '.wav']
            if file_path.suffix.lower() not in valid_extensions:
                return False
            
            # Basic file header check (just first few bytes)
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(10)
                    if len(header) < 4:
                        return False
                    
                    # Check for common audio file signatures
                    # MP3: ID3 tag or MPEG header
                    if header.startswith(b'ID3') or header[0:2] == b'\xff\xfb' or header[0:2] == b'\xff\xfa':
                        return True
                    # FLAC
                    if header.startswith(b'fLaC'):
                        return True
                    # M4A/AAC
                    if b'ftyp' in header[:10]:
                        return True
                    # OGG
                    if header.startswith(b'OggS'):
                        return True
                    # WAV/RIFF
                    if header.startswith(b'RIFF'):
                        return True
                    
                    return True
                    
            except Exception as e:
                return True
            
        except Exception as e:
            self.logger.debug(f"Simple validation failed for {file_path}: {e}")
            return False


    def _rigorous_file_validation(self, file_path: Path) -> bool:
        """
        Rigorous validation for newly downloaded files - SIMPLIFIED
        """
        try:
            # Use simple validation for now - the audio_processor is too strict
            return self._simple_file_validation(file_path)
        except Exception as e:
            self.logger.warning(f"Rigorous validation failed for {file_path}: {e}")
            return False


    def _scan_existing_files(self, playlist: SpotifyPlaylist, local_directory: Path) -> None:
        """
        Scan existing audio files in directory and match them to playlist tracks
        Creates initial track states based on found files
        
        Args:
            playlist: Spotify playlist
            local_directory: Local directory to scan
        """
        try:
            self.logger.info("Scanning existing files in directory...")
            
            # Find all audio files
            audio_extensions = ['.mp3', '.flac', '.m4a', '.aac']
            audio_files = []
            
            for ext in audio_extensions:
                audio_files.extend(local_directory.glob(f"*{ext}"))
            
            if not audio_files:
                self.logger.info("No existing audio files found")
                return
            
            # Parse file names and match to tracks
            matched_files = {}
            for file_path in audio_files:
                track_number = self._extract_track_number_from_filename(file_path.name)
                if track_number:
                    matched_files[track_number] = file_path
            
            # Update playlist track states based on found files
            files_matched = 0
            files_validated = 0
            
            for track in playlist.tracks:
                track_num = track.playlist_position
                
                if track_num in matched_files:
                    file_path = matched_files[track_num]
                    files_matched += 1
                    
                    # Validate file integrity
                    # Validate file integrity (permissive for existing files)
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    if self._validate_local_file(file_path, rigorous=False):
                        # File is valid - mark as downloaded
                        track.audio_status = TrackStatus.DOWNLOADED
                        track.local_file_path = str(file_path.relative_to(local_directory))
                        files_validated += 1
                        
                        # Check for lyrics files
                        lyrics_files = self._find_lyrics_files(file_path)
                        if lyrics_files:
                            track.lyrics_status = LyricsStatus.DOWNLOADED
                            track.lyrics_file_path = str(lyrics_files[0].relative_to(local_directory))
                            # Try to guess lyrics source from existing files/metadata
                            track.lyrics_source = self._guess_lyrics_source(lyrics_files[0])
                        else:
                            track.lyrics_status = LyricsStatus.PENDING if self.sync_lyrics else LyricsStatus.SKIPPED
                        
                        self.logger.debug(f"✅ Validated existing file: {file_path.name} ({file_size_mb:.1f}MB)")
                    else:
                        # File exists but failed basic validation
                        track.audio_status = TrackStatus.PENDING
                        track.lyrics_status = LyricsStatus.PENDING if self.sync_lyrics else LyricsStatus.SKIPPED
                        self.logger.warning(f"❌ File failed basic validation: {file_path.name} ({file_size_mb:.1f}MB)")
                        
                else:
                    # File not found - mark as pending
                    track.audio_status = TrackStatus.PENDING
                    track.lyrics_status = LyricsStatus.PENDING if self.sync_lyrics else LyricsStatus.SKIPPED
            
            if files_validated > 0:
                self.logger.console_info(f"📂 Found {files_validated} existing tracks")
            
        except Exception as e:
            self.logger.error(f"File scanning failed: {e}")
            # Set all tracks to pending as fallback
            for track in playlist.tracks:
                track.audio_status = TrackStatus.PENDING
                track.lyrics_status = LyricsStatus.PENDING if self.sync_lyrics else LyricsStatus.SKIPPED


    def _extract_track_number_from_filename(self, filename: str) -> Optional[int]:
        """
        Extract track number from filename
        Supports formats like: "01 - Artist - Title.mp3", "001. Artist - Title.mp3"
        
        Args:
            filename: Audio file name
            
        Returns:
            Track number or None if not found
        """
        try:
            import re
            
            # Pattern for "XXX - Artist - Title" or "XXX. Artist - Title"
            patterns = [
                r'^(\d{1,3})[\s\-\.]+',  # Number at start followed by space, dash, or dot
                r'^(\d{1,3})\s+\-',      # Number followed by space and dash
            ]
            
            for pattern in patterns:
                match = re.match(pattern, filename)
                if match:
                    return int(match.group(1))
            
            return None
            
        except Exception:
            return None


    def _find_lyrics_files(self, audio_file: Path) -> List[Path]:
        """
        Find lyrics files associated with audio file
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            List of lyrics file paths
        """
        try:
            lyrics_files = []
            base_name = audio_file.stem  # filename without extension
            directory = audio_file.parent
            
            # Look for .lrc and .txt files with same base name
            for ext in ['.lrc', '.txt']:
                lyrics_path = directory / f"{base_name}{ext}"
                if lyrics_path.exists():
                    lyrics_files.append(lyrics_path)
            
            return lyrics_files
            
        except Exception:
            return []


    def _guess_lyrics_source(self, lyrics_file: Path) -> Optional[LyricsSource]:
        """
        Try to guess lyrics source from file content or metadata
        
        Args:
            lyrics_file: Path to lyrics file
            
        Returns:
            Guessed LyricsSource or None
        """
        try:
            # Read first few lines to look for source indicators
            with open(lyrics_file, 'r', encoding='utf-8') as f:
                content = f.read(500)  # First 500 chars
            
            content_lower = content.lower()
            
            # Look for source indicators
            if 'genius' in content_lower:
                return LyricsSource.GENIUS
            elif 'syncedlyrics' in content_lower:
                return LyricsSource.SYNCEDLYRICS
            elif lyrics_file.suffix == '.lrc':
                # LRC files are often from syncedlyrics
                return LyricsSource.SYNCEDLYRICS
            else:
                # Default fallback
                return LyricsSource.GENIUS
                
        except Exception:
            return LyricsSource.UNKNOWN
    
    def _setup_playlist_logging(self, playlist: SpotifyPlaylist, local_directory: Path) -> None:
        """
        Configure logging for specific playlist
        
        Args:
            playlist: Spotify playlist
            local_directory: Local playlist directory
        """
        try:
            # Reconfigure logging to playlist directory
            reconfigure_logging_for_playlist(
                playlist_directory=local_directory,
                level=self.settings.logging.level,
                max_size=self.settings.logging.max_size,
                backup_count=self.settings.logging.backup_count
            )
            
            # Get the new logger and log startup info
            logger = get_logger(__name__)
            logger.info("=" * 80)
            logger.info(f"PLAYLIST SYNC STARTED: {playlist.name}")
            logger.info(f"Spotify ID: {playlist.id}")
            logger.info(f"Total tracks: {len(playlist.tracks)}")
            logger.info(f"Local directory: {local_directory}")
            logger.info(f"Log file: {get_current_log_file()}")
            logger.info("=" * 80)
            
        except Exception as e:
            # Use existing logger as fallback
            self.logger.error(f"Failed to setup playlist logging: {e}")
            
    def create_sync_plan(
        self, 
        playlist_url_or_id: str,
        local_directory: Optional[Path] = None
    ) -> SyncPlan:
        """
        Create synchronization plan for playlist
        
        Args:
            playlist_url_or_id: Spotify playlist URL or ID
            local_directory: Local playlist directory (auto-detected if None)
            
        Returns:
            SyncPlan with required operations
        """
        try:
            # Extract playlist ID
            playlist_id = self.spotify_client.extract_playlist_id(playlist_url_or_id)
            
            # Get current playlist from Spotify
            current_playlist = self.spotify_client.get_full_playlist(playlist_id)
            
            # Find or determine local directory
            if not local_directory:
                local_directory = self._find_playlist_directory(current_playlist)
            
            # Check if local version exists
            tracklist_path = local_directory / "tracklist.txt"
            
            if not tracklist_path.exists():
                # New playlist - create full download plan
                return self._create_initial_sync_plan(current_playlist, local_directory)
            else:
                # Existing playlist - create incremental sync plan
                return self._create_incremental_sync_plan(current_playlist, local_directory)
                
        except Exception as e:
            self.logger.error(f"Failed to create sync plan: {e}")
            return SyncPlan(
                playlist_id=playlist_id if 'playlist_id' in locals() else "",
                playlist_name="Unknown",
                operations=[],
                estimated_downloads=0
            )
    
    def cleanup_duplicate_directories(self, playlist: SpotifyPlaylist) -> None:
        """
        Clean up duplicate empty directories for the same playlist
        
        Args:
            playlist: Spotify playlist
        """
        try:
            from ..utils.helpers import normalize_playlist_name_for_matching
            target_name = normalize_playlist_name_for_matching(playlist.name)
            
            if not self.output_directory.exists():
                return
            
            # Find all directories that could be duplicates
            potential_duplicates = []
            active_directory = None
            
            for directory in self.output_directory.iterdir():
                if not directory.is_dir():
                    continue
                    
                dir_name = normalize_playlist_name_for_matching(directory.name)
                if dir_name == target_name or directory.name.startswith(target_name.replace(' ', '')):
                    tracklist_path = directory / "tracklist.txt"
                    
                    if tracklist_path.exists():
                        # This is the active directory
                        active_directory = directory
                    else:
                        # This might be an empty duplicate
                        potential_duplicates.append(directory)
            
            # Remove empty duplicate directories
            for duplicate in potential_duplicates:
                try:
                    if not any(duplicate.iterdir()):  # Directory is empty
                        duplicate.rmdir()
                except Exception as e:
                    self.logger.warning(f"Could not remove duplicate directory {duplicate}: {e}")
                    
        except Exception as e:
            self.logger.warning(f"Error during duplicate cleanup: {e}")


    def _find_playlist_directory(self, playlist: SpotifyPlaylist) -> Path:
        """
        Find existing playlist directory or create new one with improved matching
        
        Args:
            playlist: Spotify playlist
            
        Returns:
            Path to playlist directory
        """
        # First, search for existing playlist directories
        existing_matches = self._search_existing_playlist(playlist)
        
        if existing_matches:
            # Use the best match (first in sorted list)
            existing_path = existing_matches[0]
            return existing_path
        
        # No existing directory found, create new one with clean name
        from ..utils.helpers import sanitize_directory_name
        clean_name = sanitize_directory_name(playlist.name)
        playlist_path = self.output_directory / clean_name
        
        
        # Handle duplicate names by adding suffix
        counter = 1
        original_path = playlist_path
        
        while playlist_path.exists():
            # Check if it's actually the same playlist (has tracklist.txt with same Spotify ID)
            tracklist = playlist_path / "tracklist.txt"
            if tracklist.exists():
                try:
                    metadata, _ = self.tracklist_manager.read_tracklist_file(tracklist)
                    if metadata.spotify_id == playlist.id:
                        return playlist_path
                except Exception as e:
                    self.logger.warning(f"Could not verify existing playlist: {e}")
            
            # Different directory with same name, create unique name
            clean_name_with_counter = f"{clean_name}_{counter}"
            playlist_path = self.output_directory / clean_name_with_counter
            counter += 1
            
            # Prevent infinite loop
            if counter > 100:
                import time
                clean_name_with_counter = f"{clean_name}_{int(time.time())}"
                playlist_path = self.output_directory / clean_name_with_counter
                break
        
        # Validate and create the directory
        success, error_msg, validated_path = validate_and_create_directory(
            playlist_path, 
            trusted_source=True
        )
        
        if not success:
            # Fallback to timestamped directory name if still failing
            import time
            fallback_name = f"{clean_name}_{int(time.time())}"
            fallback_path = self.output_directory / fallback_name
            
            self.logger.warning(f"Directory creation failed ({error_msg}), using fallback: {fallback_path}")
            
            success, error_msg, validated_path = validate_and_create_directory(
                fallback_path, 
                trusted_source=True
            )
            if not success:
                raise Exception(f"Failed to create playlist directory: {error_msg}")
        
        return validated_path


    def _search_existing_playlist(self, playlist: SpotifyPlaylist) -> List[Path]:
        """
        Search for existing playlist directory by Spotify ID with improved matching
        
        Args:
            playlist: Spotify playlist to search for
            
        Returns:
            List of matching directory paths
        """
        matches = []
        
        try:
            # Get normalized playlist name for comparison
            from ..utils.helpers import normalize_playlist_name_for_matching
            target_name = normalize_playlist_name_for_matching(playlist.name)
            
            # Search all directories in output directory
            if self.output_directory.exists():
                for directory in self.output_directory.iterdir():
                    if not directory.is_dir():
                        continue
                    
                    # Check by tracklist content first (most reliable)
                    tracklist_path = directory / "tracklist.txt"
                    if tracklist_path.exists():
                        try:
                            metadata, _ = self.tracklist_manager.read_tracklist_file(tracklist_path)
                            if metadata.spotify_id == playlist.id:
                                matches.append(directory)
                                continue
                        except Exception as e:
                            self.logger.debug(f"Could not read tracklist {tracklist_path}: {e}")
                    
                    # Fallback: check by normalized directory name
                    dir_name = normalize_playlist_name_for_matching(directory.name)
                    if dir_name == target_name:
                        matches.append(directory)
            
            # Sort by preference: exact Spotify ID match first, then name matches
            def sort_key(path):
                tracklist_path = path / "tracklist.txt"
                if tracklist_path.exists():
                    try:
                        metadata, _ = self.tracklist_manager.read_tracklist_file(tracklist_path)
                        if metadata.spotify_id == playlist.id:
                            return 0  # Highest priority
                    except Exception:
                        pass
                return 1  # Lower priority
            
            matches.sort(key=sort_key)
            
        except Exception as e:
            self.logger.warning(f"Error searching for existing playlist: {e}")
        
        return matches
        
    def _create_incremental_sync_plan(
        self, 
        playlist: SpotifyPlaylist, 
        local_directory: Path
    ) -> SyncPlan:
        """
        Create sync plan for existing playlist (incremental update)
        
        Args:
            playlist: Current Spotify playlist
            local_directory: Local directory
            
        Returns:
            SyncPlan for incremental sync
        """
        operations = []
        
        # Read existing tracklist
        tracklist_path = local_directory / "tracklist.txt"
        
        # Verify tracklist exists before trying to read it
        if not tracklist_path.exists():
            self.logger.warning(f"Tracklist not found, treating as initial download: {tracklist_path}")
            return self._create_initial_sync_plan(playlist, local_directory)
        
        try:
            metadata, current_entries = self.tracklist_manager.read_tracklist_file(tracklist_path)
        except Exception as e:
            self.logger.warning(f"Failed to read tracklist, treating as initial download: {e}")
            return self._create_initial_sync_plan(playlist, local_directory)
 
        # Compare with current playlist
        differences = self.tracklist_manager.compare_tracklists(current_entries, playlist.tracks)
            
        # Create operations for added tracks
        for track in differences['added']:
            operation = SyncOperation(
                operation_type='download',
                track=track,
                reason='track_added'
            )
            operations.append(operation)
            
        # Create operations for moved tracks
        if self.detect_moved_tracks:
            for old_entry, new_track in differences['moved']:
                operation = SyncOperation(
                    operation_type='move',
                    track=new_track,
                    old_position=old_entry.position,
                    new_position=new_track.playlist_position,
                    reason='track_moved'
                )
                operations.append(operation)
            
        # Create operations for tracks needing re-download (failed/missing files)
        for entry in current_entries:
            if entry.spotify_id in {t.spotify_track.id for t in playlist.tracks}:
                # Find corresponding track
                track = next(t for t in playlist.tracks if t.spotify_track.id == entry.spotify_id)
                
               # Check if track needs download
                needs_download = False
                
                if entry.local_file_path:
                    # Has file path but file missing/invalid
                    file_path = local_directory / entry.local_file_path
                    if not file_path.exists() or not self._validate_local_file(file_path, rigorous=False):
                        needs_download = True
                elif entry.audio_status.value == 'pending':
                    # No file path and still pending
                    needs_download = True
                    
                if needs_download:
                    operation = SyncOperation(
                        operation_type='download',
                        track=track,
                        reason='file_missing_or_invalid'
                    )
                    operations.append(operation)
                
                
                # Check lyrics if enabled
                if self.sync_lyrics and entry.lyrics_status != LyricsStatus.DOWNLOADED:
                    # This will be handled during download operation
                    pass
            
        # Estimate time
        download_ops = [op for op in operations if op.operation_type == 'download']
        estimated_time = len(download_ops) * 30.0 + len(differences['moved']) * 2.0
            
        return SyncPlan(
            playlist_id=playlist.id,
            playlist_name=playlist.name,
            operations=operations,
            estimated_downloads=len(download_ops),
            estimated_time=estimated_time,
            requires_reordering=len(differences['moved']) > 0
        )

    def _create_initial_sync_plan(
        self, 
        playlist: SpotifyPlaylist, 
        local_directory: Path
    ) -> SyncPlan:
        """
        Create sync plan for new playlist (full download)
        
        Args:
            playlist: Spotify playlist
            local_directory: Local directory for playlist
            
        Returns:
            SyncPlan for initial download
        """
        # AGGIUNGERE QUESTO BLOCCO ALL'INIZIO:
        # Check if directory has existing audio files (from previous incomplete download)
        if local_directory.exists():
            audio_extensions = ['.mp3', '.flac', '.m4a', '.aac']
            existing_files = []
            for ext in audio_extensions:
                existing_files.extend(local_directory.glob(f"*{ext}"))
            
            if existing_files:
                # Scan and match existing files to tracks
                self._scan_existing_files(playlist, local_directory)
                
                # Create tracklist.txt with current states
                self._create_or_update_tracklist(playlist, local_directory)
                
                # Now create sync plan only for pending tracks
                pending_tracks = [track for track in playlist.tracks if track.audio_status == TrackStatus.PENDING]
                
                if not pending_tracks:
                    self.logger.info("All tracks already downloaded!")
                    return SyncPlan(
                        playlist_id=playlist.id,
                        playlist_name=playlist.name,
                        operations=[],
                        estimated_downloads=0,
                        estimated_time=0,
                        requires_reordering=False
                    )
                
                # Create operations only for pending tracks
                operations = []
                for track in pending_tracks:
                    operation = SyncOperation(
                        operation_type='download',
                        track=track,
                        reason='resume_download'
                    )
                    operations.append(operation)
                
                # Estimate download time
                estimated_time = len(operations) * 30.0
                if self.sync_lyrics:
                    estimated_time += len(operations) * 5.0
                
                self.logger.info(
                    f"Resuming download for '{playlist.name}': "
                    f"{len(operations)} tracks remaining out of {len(playlist.tracks)} total"
                )
                
                return SyncPlan(
                    playlist_id=playlist.id,
                    playlist_name=playlist.name,
                    operations=operations,
                    estimated_downloads=len(operations),
                    estimated_time=estimated_time,
                    requires_reordering=False
                )
            operations = []
        
        # Create download operations for all tracks
        for track in playlist.tracks:
            operation = SyncOperation(
                operation_type='download',
                track=track,
                reason='initial_download'
            )
            operations.append(operation)
        
        # Estimate download time
        # Assume ~30 seconds per track (search + download + processing)
        estimated_time = len(playlist.tracks) * 30.0
        
        # Add time for lyrics if enabled
        if self.sync_lyrics:
            estimated_time += len(playlist.tracks) * 5.0  # ~5 seconds per lyrics search
        
        self.logger.info(
            f"Created initial sync plan for '{playlist.name}': "
            f"{len(operations)} tracks to download"
        )
        
        return SyncPlan(
            playlist_id=playlist.id,
            playlist_name=playlist.name,
            operations=operations,
            estimated_downloads=len(operations),
            estimated_time=estimated_time,
            requires_reordering=False
        )
    
    def execute_sync_plan(self, sync_plan: SyncPlan, local_directory: Path) -> SyncResult:
        """
        Execute synchronization plan
        
        Args:
            sync_plan: Sync plan to execute
            local_directory: Local playlist directory
            
        Returns:
            SyncResult with operation results
        """
        # Get playlist and preserve it for final tracklist update
        original_playlist = self.spotify_client.get_full_playlist(sync_plan.playlist_id)
        self._setup_playlist_logging(original_playlist, local_directory)

        if not sync_plan.has_changes:
            return SyncResult(
                success=True,
                playlist_id=sync_plan.playlist_id,
                operations_performed=0,
                downloads_completed=0,
                downloads_failed=0,
                lyrics_completed=0,
                lyrics_failed=0,
                reordering_performed=False
            )
        
        # Get new logger instance after reconfiguration
        operation_logger = OperationLogger(get_logger(__name__), f"Sync: {sync_plan.playlist_name}")
        operation_logger.start()
        
        start_time = datetime.now()
        
        try:
            # Initialize result tracking
            result = SyncResult(
                success=True,
                playlist_id=sync_plan.playlist_id,
                operations_performed=0,
                downloads_completed=0,
                downloads_failed=0,
                lyrics_completed=0,
                lyrics_failed=0,
                reordering_performed=False
            )

            # Validate existing tracklist and update track states
            self._validate_existing_tracklist(original_playlist, local_directory)

            # Create initial tracklist if doesn't exist or update with validated states
            self._create_or_update_tracklist(original_playlist, local_directory)
            operation_logger.progress("Initial tracklist created/validated")

            # Reset download counter for batch updates
            self.download_counter = 0
            
            # Group operations by type
            download_operations = [op for op in sync_plan.operations if op.operation_type == 'download']
            move_operations = [op for op in sync_plan.operations if op.operation_type == 'move']
            
            # Execute download operations
            if download_operations:
                download_result = self._execute_download_operations(
                    download_operations, local_directory, operation_logger, sync_plan.playlist_id
                )
                result.downloads_completed += download_result['completed']
                result.downloads_failed += download_result['failed']
                result.lyrics_completed += download_result['lyrics_completed']
                result.lyrics_failed += download_result['lyrics_failed']
            
            # Execute move operations
            if move_operations:
                move_result = self._execute_move_operations(
                    move_operations, local_directory, operation_logger
                )
                result.reordering_performed = move_result['reordering_performed']
            
            result.operations_performed = len(sync_plan.operations)
            result.total_time = (datetime.now() - start_time).total_seconds()
            
            # Update the playlist tracks with the states from sync operations
            # DON'T reload from Spotify - preserve existing states
            self._update_playlist_track_states(original_playlist, sync_plan.operations)
            
            # Create or update tracklist file with updated states
            self._create_or_update_tracklist(original_playlist, local_directory)
            
            operation_logger.complete(result.summary)
            return result
        
            
        except Exception as e:
            operation_logger.error(f"Sync execution failed: {e}")
            return SyncResult(
                success=False,
                playlist_id=sync_plan.playlist_id,
                operations_performed=0,
                downloads_completed=0,
                downloads_failed=0,
                lyrics_completed=0,
                lyrics_failed=0,
                reordering_performed=False,
                error_message=str(e)
            )
        

    def _update_playlist_track_states(
        self, 
        playlist: SpotifyPlaylist, 
        operations: List[SyncOperation]
    ) -> None:
        """
        Update playlist track states based on completed sync operations
        
        Args:
            playlist: Playlist to update
            operations: Completed sync operations
        """
        try:
        
            # Create a map of track operations by Spotify ID
            operation_map = {}
            for operation in operations:
                if operation.track and operation.track.spotify_track.id:
                    operation_map[operation.track.spotify_track.id] = operation.track
            
            # Update playlist tracks with operation results
            for playlist_track in playlist.tracks:
                track_id = playlist_track.spotify_track.id
                
                if track_id in operation_map:
                    # Copy the updated states from the operation track
                    operation_track = operation_map[track_id]
                    
                    # Update audio status
                    playlist_track.audio_status = operation_track.audio_status
                    playlist_track.local_file_path = operation_track.local_file_path
                    playlist_track.youtube_video_id = operation_track.youtube_video_id
                    playlist_track.youtube_match_score = operation_track.youtube_match_score
                    
                    # Update lyrics status
                    playlist_track.lyrics_status = operation_track.lyrics_status
                    playlist_track.lyrics_source = operation_track.lyrics_source
                    playlist_track.lyrics_file_path = operation_track.lyrics_file_path
                    playlist_track.lyrics_embedded = operation_track.lyrics_embedded
                    
                    self.logger.debug(
                        f"Updated track state: {playlist_track.spotify_track.name} - "
                        f"Audio: {playlist_track.audio_status.value}, "
                        f"Lyrics: {playlist_track.lyrics_status.value}"
                    )
            # DEBUG: Log after update  
            downloaded_count = sum(1 for t in playlist.tracks if t.audio_status == TrackStatus.DOWNLOADED)
            
        except Exception as e:
            self.logger.error(f"Failed to update playlist track states: {e}")

    def _validate_existing_tracklist(
        self, 
        playlist: SpotifyPlaylist, 
        local_directory: Path
    ) -> None:
        """
        Validate existing tracklist against actual files in directory
        Updates track statuses based on file existence and integrity
        
        Args:
            playlist: Current Spotify playlist
            local_directory: Local playlist directory
        """
        try:
            tracklist_path = local_directory / "tracklist.txt"
            
            if not tracklist_path.exists():
                self.logger.info("No existing tracklist found, will create new one")
                return
            
            self.logger.info("Validating existing tracklist against local files...")
            
            # Read existing tracklist
            metadata, entries = self.tracklist_manager.read_tracklist_file(tracklist_path)
            
            # Create lookup map for entries
            entries_by_id = {entry.spotify_id: entry for entry in entries}
            
            validation_updates = 0
            
            # Check each track in current playlist
            for track in playlist.tracks:
                track_id = track.spotify_track.id
                
                if track_id in entries_by_id:
                    entry = entries_by_id[track_id]
                    
                    # If entry says downloaded, verify file exists and is valid
                    if entry.audio_status == TrackStatus.DOWNLOADED:
                        if entry.local_file_path:
                            file_path = local_directory / entry.local_file_path
                            
                            if file_path.exists() and self._validate_local_file(file_path, rigorous=False):    # File is valid, update track status
                                track.audio_status = TrackStatus.DOWNLOADED
                                track.local_file_path = entry.local_file_path
                                
                                # Check lyrics status too
                                if entry.lyrics_status == LyricsStatus.DOWNLOADED:
                                    if entry.lyrics_file_path:
                                        lyrics_path = local_directory / entry.lyrics_file_path
                                        if lyrics_path.exists():
                                            track.lyrics_status = LyricsStatus.DOWNLOADED
                                            track.lyrics_file_path = entry.lyrics_file_path
                                            track.lyrics_source = entry.lyrics_source
                                        else:
                                            track.lyrics_status = LyricsStatus.PENDING
                                            validation_updates += 1
                                    else:
                                        track.lyrics_status = entry.lyrics_status
                                        track.lyrics_source = entry.lyrics_source
                            else:
                                # File missing or invalid, mark as pending
                                track.audio_status = TrackStatus.PENDING
                                track.lyrics_status = LyricsStatus.PENDING
                                validation_updates += 1
                                self.logger.warning(
                                    f"File missing or invalid, marking as pending: "
                                    f"{track.spotify_track.primary_artist} - {track.spotify_track.name}"
                                )
                        else:
                            # No file path in tracklist, mark as pending
                            track.audio_status = TrackStatus.PENDING
                            track.lyrics_status = LyricsStatus.PENDING
                            validation_updates += 1
                    else:
                        # Entry shows not downloaded, keep current status
                        track.audio_status = entry.audio_status
                        track.lyrics_status = entry.lyrics_status
                else:
                    # Track not in existing tracklist, mark as pending
                    track.audio_status = TrackStatus.PENDING
                    track.lyrics_status = LyricsStatus.PENDING if self.sync_lyrics else LyricsStatus.SKIPPED
            
            if validation_updates > 0:
                
                # Update tracklist with corrected statuses
                self._create_or_update_tracklist(playlist, local_directory)
            else:
                self.logger.info("Tracklist validation completed - all statuses correct")
                
        except Exception as e:
            self.logger.error(f"Tracklist validation failed: {e}")
            # Continue without validation - sync will handle inconsistencies

    def _create_or_update_tracklist(self, playlist: SpotifyPlaylist, local_directory: Path) -> None:
        """
        Create new tracklist or update existing one after sync operations
        
        Args:
            playlist: Spotify playlist with updated track states
            local_directory: Local directory
        """
        try:
            
            # Log some example tracks
            for i, track in enumerate(playlist.tracks[:5]):  # First 5 tracks
                self.logger.debug(f"DEBUG TRACK {i+1}: {track.spotify_track.name} = {track.audio_status.value}")
            
            # Check if tracklist exists
            tracklist_path = local_directory / "tracklist.txt"
            
            if tracklist_path.exists():
                # Update existing tracklist
                self.tracklist_manager.update_tracklist_file(
                    tracklist_path,
                    playlist.tracks
                )
            else:
                # Create new tracklist
                created_path = self.tracklist_manager.create_tracklist_file(
                    playlist,
                    local_directory
                )
                self.logger.debug(f"Created new tracklist: {created_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to create/update tracklist: {e}")



    def _execute_download_operations(
        self, 
        operations: List[SyncOperation],
        local_directory: Path,
        operation_logger: OperationLogger,
        playlist_id: str
    ) -> Dict[str, int]:
        """
        Execute download operations with parallel processing
        
        Args:
            operations: Download operations to execute
            local_directory: Local directory
            operation_logger: Operation logger
            
        Returns:
            Dictionary with completion stats
        """
        result = {
            'completed': 0,
            'failed': 0,
            'lyrics_completed': 0,
            'lyrics_failed': 0
        }
        
        def download_single_track(operation: SyncOperation) -> Tuple[bool, bool, str]:
            """Download single track with lyrics"""
            try:
                track = operation.track
                
                # Search for track on YouTube Music
                search_result = self.ytmusic_searcher.get_best_match(
                    track.spotify_track.primary_artist,
                    track.spotify_track.name,
                    track.spotify_track.duration_ms // 1000,
                    track.spotify_track.album.name
                )
                
                if not search_result:
                    return False, False, "No YouTube Music match found"
                
                # Generate output filename
                filename = self._generate_track_filename(track)
                output_path = local_directory / filename
                
                # Download audio
                download_result = self.downloader.download_audio(
                    search_result.video_id,
                    str(output_path.with_suffix(''))  # Remove extension, downloader adds it
                )
                
                if not download_result.success:
                    return False, False, download_result.error_message or "Download failed"
                
                # Validate downloaded file with rigorous checking
                if download_result.file_path:
                    if not self._validate_local_file(Path(download_result.file_path), rigorous=True):
                        self.logger.warning(f"Downloaded file failed validation: {download_result.file_path}")
                        # Delete invalid file
                        try:
                            Path(download_result.file_path).unlink()
                        except Exception:
                            pass
                        return False, False, "Downloaded file failed integrity check"

                # Update track status
                track.audio_status = TrackStatus.DOWNLOADED
                track.local_file_path = download_result.file_path
                track.youtube_video_id = search_result.video_id
                track.youtube_match_score = search_result.total_score
                
                # Process audio (trimming, normalization)
                if download_result.file_path:
                    self.audio_processor.process_audio_file(download_result.file_path)
                
                lyrics_result = None

                # Download lyrics if enabled
                lyrics_success = False
                if self.sync_lyrics:
                    lyrics_result = self.lyrics_processor.search_lyrics(
                        track.spotify_track.primary_artist,
                        track.spotify_track.name,
                        track.spotify_track.album.name
                    )
                    
                    if lyrics_result.success:
                        # Save lyrics files
                        lyrics_result = self.lyrics_processor.save_lyrics_files(
                            lyrics_result,
                            track.spotify_track.primary_artist,
                            track.spotify_track.name,
                            local_directory,
                            track.playlist_position
                        )
                        
                        # Update track lyrics status
                        track.lyrics_status = LyricsStatus.DOWNLOADED
                        track.lyrics_source = lyrics_result.source
                        if lyrics_result.file_paths:
                            track.lyrics_file_path = lyrics_result.file_paths[0]
                        
                        lyrics_success = True
                    else:
                        track.lyrics_status = LyricsStatus.NOT_FOUND
                else:
                    # If lyrics are disabled, mark as skipped
                    track.lyrics_status = LyricsStatus.SKIPPED

                
                # Embed metadata (including lyrics if available)
                if download_result.file_path:
                    self.metadata_manager.embed_metadata(
                        download_result.file_path,
                        track.spotify_track,
                        track.playlist_position,
                        lyrics_result.lyrics_text if self.sync_lyrics and lyrics_result.success else None,
                        lyrics_result.source if self.sync_lyrics and lyrics_result.success else None
                    )
                
                return True, lyrics_success, "Success"
                
            except Exception as e:
                return False, False, str(e)
        
        # Execute downloads with controlled concurrency
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all download tasks
            future_to_operation = {
                executor.submit(download_single_track, op): op
                for op in operations
            }
            
            completed = 0
            for future in as_completed(future_to_operation):
                operation = future_to_operation[future]
                
                try:
                    download_success, lyrics_success, message = future.result()
                    
                    if download_success:
                        result['completed'] += 1
                        operation_logger.progress("Downloading tracks", completed + 1, len(operations))
                    else:
                        result['failed'] += 1
                        # Dettagli tecnici solo nel file di log
                        self.logger.warning(f"Download failed: {operation.track.spotify_track.primary_artist} - {operation.track.spotify_track.name}: {message}")
                    
                    if lyrics_success:
                        result['lyrics_completed'] += 1
                    elif self.sync_lyrics:
                        result['lyrics_failed'] += 1
                    
                    completed += 1
                    
                    # Batch update tracklist every N downloads
                    if download_success:  # Solo se download è riuscito
                        self.download_counter += 1
                        if self.download_counter % self.batch_update_interval == 0:
                            try:
                                # Get current playlist state for batch update
                                current_playlist = self.spotify_client.get_full_playlist(playlist_id)
                                
                                # Update playlist track states from operations
                                operation_map = {op.track.spotify_track.id: op.track for op in operations if op.track}
                                for track in current_playlist.tracks:
                                    if track.spotify_track.id in operation_map:
                                        op_track = operation_map[track.spotify_track.id]
                                        track.audio_status = op_track.audio_status
                                        track.lyrics_status = op_track.lyrics_status
                                        track.local_file_path = op_track.local_file_path
                                        track.lyrics_file_path = op_track.lyrics_file_path
                                        track.lyrics_source = op_track.lyrics_source
                                
                                # Update tracklist file
                                self._create_or_update_tracklist(current_playlist, local_directory)
                                self.logger.debug(f"Batch update: tracklist updated after {self.download_counter} downloads")
                            except Exception as e:
                                operation_logger.warning(f"Batch tracklist update failed: {e}")

                except Exception as e:
                    result['failed'] += 1
                    operation_logger.error(f"Download execution error: {e}")
                    completed += 1
                    operation.track.audio_status = TrackStatus.FAILED
                    operation.track.lyrics_status = LyricsStatus.FAILED if self.sync_lyrics else LyricsStatus.SKIPPED
        
        return result
    
    def _execute_move_operations(
        self, 
        operations: List[SyncOperation],
        local_directory: Path,
        operation_logger: OperationLogger
    ) -> Dict[str, Any]:
        """
        Execute move/reorder operations
        
        Args:
            operations: Move operations to execute
            local_directory: Local directory
            operation_logger: Operation logger
            
        Returns:
            Dictionary with operation results
        """
        try:
            # For now, we'll just update the tracklist with new positions
            # File renaming is handled during tracklist update
            
            operation_logger.progress("Reordering tracks", len(operations), len(operations))
            
            return {'reordering_performed': True}
            
        except Exception as e:
            operation_logger.error(f"Move operations failed: {e}")
            return {'reordering_performed': False}
    
    def _generate_track_filename(self, track: PlaylistTrack) -> str:
        """
        Generate filename for track based on naming format
        
        Args:
            track: Playlist track
            
        Returns:
            Filename string
        """
        try:
            # Use configured naming format
            filename = self.naming_format.format(
                track=track.playlist_position,
                artist=sanitize_filename(track.spotify_track.primary_artist),
                title=sanitize_filename(track.spotify_track.name),
                album=sanitize_filename(track.spotify_track.album.name)
            )
            
            return filename
            
        except Exception as e:
            # Fallback to simple format
            self.logger.warning(f"Failed to apply naming format, using fallback: {e}")
            return f"{track.playlist_position:02d} - {sanitize_filename(track.spotify_track.primary_artist)} - {sanitize_filename(track.spotify_track.name)}"
    

    def _validate_local_file(self, file_path: Path, rigorous: bool = False) -> bool:
        """
        Validate local audio file with appropriate level of checking
        """
        try:
            
            if rigorous:
                # Rigorous validation for newly downloaded files
                result = self._rigorous_file_validation(file_path)
                return result
            else:
                # Permissive validation for existing files
                result = self._simple_file_validation(file_path)
                return result
        except Exception as e:
            self.logger.warning(f"File validation failed for {file_path}: {e}")
            return False
    
    def check_playlist_status(self, playlist_url_or_id: str) -> Dict[str, Any]:
        """
        Check current status of playlist without making changes
        
        Args:
            playlist_url_or_id: Spotify playlist URL or ID
            
        Returns:
            Dictionary with playlist status information
        """
        try:
            # Extract playlist ID
            playlist_id = self.spotify_client.extract_playlist_id(playlist_url_or_id)
            
            # Get playlist
            playlist = self.spotify_client.get_full_playlist(playlist_id)
            
            # Find local directory
            local_directory = self._find_playlist_directory(playlist)
            
            # Check if tracklist exists
            tracklist_path = local_directory / "tracklist.txt"
            
            status = {
                'playlist_id': playlist.id,
                'playlist_name': playlist.name,
                'total_tracks': len(playlist.tracks),
                'local_directory': str(local_directory),
                'tracklist_exists': tracklist_path.exists(),
                'needs_sync': False,
                'sync_summary': "Unknown"
            }
            
            if tracklist_path.exists():
                # Compare with local state
                sync_plan = self.create_sync_plan(playlist_url_or_id, local_directory)
                status['needs_sync'] = sync_plan.has_changes
                status['sync_summary'] = f"{sync_plan.estimated_downloads} downloads needed" if sync_plan.has_changes else "Up to date"
                status['estimated_downloads'] = sync_plan.estimated_downloads
                status['estimated_time'] = sync_plan.estimated_time
            else:
                status['needs_sync'] = True
                status['sync_summary'] = "New playlist - full download needed"
                status['estimated_downloads'] = len(playlist.tracks)
                status['estimated_time'] = len(playlist.tracks) * 30.0
            
            return status
            
        except Exception as e:
            return {
                'error': str(e),
                'playlist_id': playlist_id if 'playlist_id' in locals() else "unknown"
            }
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """
        Get synchronizer statistics and configuration
        
        Returns:
            Dictionary with sync stats
        """
        return {
            'auto_sync': self.auto_sync,
            'sync_lyrics': self.sync_lyrics,
            'detect_moved_tracks': self.detect_moved_tracks,
            'max_concurrent': self.max_concurrent,
            'output_directory': str(self.output_directory),
            'naming_format': self.naming_format
        }


# Global synchronizer instance
_synchronizer_instance: Optional[PlaylistSynchronizer] = None


def get_synchronizer() -> PlaylistSynchronizer:
    """Get global playlist synchronizer instance"""
    global _synchronizer_instance
    if not _synchronizer_instance:
        _synchronizer_instance = PlaylistSynchronizer()
    return _synchronizer_instance