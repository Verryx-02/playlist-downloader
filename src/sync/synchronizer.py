"""
Playlist synchronization logic for incremental updates and change detection
Handles sync operations between Spotify playlists and local downloads
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config.settings import get_settings
from ..utils.logger import get_logger, OperationLogger
from ..utils.helpers import sanitize_filename, ensure_directory, format_duration
from ..utils.helpers import (
    sanitize_filename, 
    sanitize_directory_name,
    create_safe_playlist_path,
    validate_and_create_directory
)
from ..spotify.client import get_spotify_client
from ..spotify.models import SpotifyPlaylist, PlaylistTrack, TrackStatus, LyricsStatus, DownloadStats
from ..ytmusic.searcher import get_ytmusic_searcher
from ..ytmusic.downloader import get_downloader
from ..audio.metadata import get_metadata_manager
from ..audio.processor import get_audio_processor
from ..lyrics.processor import get_lyrics_processor
from .tracker import get_tracklist_manager, TracklistEntry


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
    
    
    def _find_playlist_directory(self, playlist: SpotifyPlaylist) -> Path:
        """
        Find existing playlist directory or create new one with safe path handling
        
        Args:
            playlist: Spotify playlist
            
        Returns:
            Path to playlist directory
        """
        # Create safe playlist path
        playlist_path = create_safe_playlist_path(self.output_directory, playlist.name)
        
        # Check if this directory already contains our playlist
        tracklist_path = playlist_path / "tracklist.txt"
        if tracklist_path.exists():
            try:
                # Verify it's the same playlist by checking Spotify ID
                metadata, _ = self.tracklist_manager.read_tracklist_file(tracklist_path)
                if metadata.spotify_id == playlist.id:
                    self.logger.info(f"Found existing playlist directory: {playlist_path}")
                    return playlist_path
            except Exception as e:
                self.logger.warning(f"Could not verify existing playlist: {e}")
        
        # Try alternative names if the directory exists but contains different playlist
        if playlist_path.exists() and not tracklist_path.exists():
            self.logger.warning(f"Directory exists but no tracklist found: {playlist_path}")
            
            # Search for existing playlist in other directories
            possible_matches = self._search_existing_playlist(playlist)
            if possible_matches:
                return possible_matches[0]
        
        # Validate and create the directory
        success, error_msg, validated_path = validate_and_create_directory(playlist_path)
        
        if not success:
            # Fallback to timestamped directory name
            fallback_name = f"{sanitize_directory_name(playlist.name)}_{int(time.time())}"
            fallback_path = self.output_directory / fallback_name
            
            self.logger.warning(f"Directory creation failed ({error_msg}), using fallback: {fallback_path}")
            
            success, error_msg, validated_path = validate_and_create_directory(fallback_path)
            if not success:
                raise Exception(f"Failed to create playlist directory: {error_msg}")
        
        self.logger.info(f"Created playlist directory: {validated_path}")
        return validated_path


    def _search_existing_playlist(self, playlist: SpotifyPlaylist) -> List[Path]:
        """
        Search for existing playlist directory by Spotify ID
        
        Args:
            playlist: Spotify playlist to search for
            
        Returns:
            List of matching directory paths
        """
        matches = []
        
        try:
            # Search all tracklist files in output directory
            tracklist_files = self.tracklist_manager.find_tracklist_files(self.output_directory)
            
            for tracklist_path in tracklist_files:
                try:
                    metadata, _ = self.tracklist_manager.read_tracklist_file(tracklist_path)
                    if metadata.spotify_id == playlist.id:
                        matches.append(tracklist_path.parent)
                        self.logger.info(f"Found existing playlist by ID: {tracklist_path.parent}")
                except Exception as e:
                    self.logger.debug(f"Could not read tracklist {tracklist_path}: {e}")
                    continue
        
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
            metadata, current_entries = self.tracklist_manager.read_tracklist_file(tracklist_path)
            
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
                    
                    # Check if file exists and is valid
                    if entry.local_file_path:
                        file_path = local_directory / entry.local_file_path
                        if not file_path.exists() or not self._validate_local_file(file_path):
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
    
    def execute_sync_plan(self, sync_plan: SyncPlan, local_directory: Path) -> SyncResult:
        """
        Execute synchronization plan
        
        Args:
            sync_plan: Sync plan to execute
            local_directory: Local playlist directory
            
        Returns:
            SyncResult with operation results
        """
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
        
        operation_logger = OperationLogger(self.logger, f"Sync: {sync_plan.playlist_name}")
        operation_logger.start(f"Executing {len(sync_plan.operations)} operations")
        
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
            
            # Group operations by type
            download_operations = [op for op in sync_plan.operations if op.operation_type == 'download']
            move_operations = [op for op in sync_plan.operations if op.operation_type == 'move']
            
            # Execute download operations
            if download_operations:
                download_result = self._execute_download_operations(
                    download_operations, local_directory, operation_logger
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
            
            # Update tracklist file
            self._update_tracklist_after_sync(sync_plan.playlist_id, local_directory)
            
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
    
    def _execute_download_operations(
        self, 
        operations: List[SyncOperation],
        local_directory: Path,
        operation_logger: OperationLogger
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
                
                # Update track status
                track.audio_status = TrackStatus.DOWNLOADED
                track.local_file_path = download_result.file_path
                track.youtube_video_id = search_result.video_id
                track.youtube_match_score = search_result.total_score
                
                # Process audio (trimming, normalization)
                if download_result.file_path:
                    self.audio_processor.process_audio_file(download_result.file_path)
                
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
                        operation_logger.progress(
                            f"Downloaded: {operation.track.spotify_track.primary_artist} - {operation.track.spotify_track.name}",
                            completed + 1,
                            len(operations)
                        )
                    else:
                        result['failed'] += 1
                        operation_logger.warning(
                            f"Download failed: {operation.track.spotify_track.primary_artist} - {operation.track.spotify_track.name}: {message}"
                        )
                    
                    if lyrics_success:
                        result['lyrics_completed'] += 1
                    elif self.sync_lyrics:
                        result['lyrics_failed'] += 1
                    
                    completed += 1
                    
                except Exception as e:
                    result['failed'] += 1
                    operation_logger.error(f"Download execution error: {e}")
                    completed += 1
        
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
    
    def _update_tracklist_after_sync(self, playlist_id: str, local_directory: Path) -> None:
        """
        Update tracklist file after sync operations
        
        Args:
            playlist_id: Spotify playlist ID
            local_directory: Local directory
        """
        try:
            # Get current playlist state
            current_playlist = self.spotify_client.get_full_playlist(playlist_id)
            
            # Update tracklist file
            tracklist_path = local_directory / "tracklist.txt"
            self.tracklist_manager.update_tracklist_file(
                tracklist_path,
                current_playlist.tracks
            )
            
            self.logger.info(f"Updated tracklist: {tracklist_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to update tracklist after sync: {e}")
    
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
    
    def _validate_local_file(self, file_path: Path) -> bool:
        """
        Validate local audio file integrity
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if file is valid
        """
        try:
            return self.audio_processor.validate_audio_file(str(file_path))[0]
        except Exception:
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