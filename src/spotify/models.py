"""
Data models for Spotify playlist and track information
Defines structures for storing and manipulating music metadata
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TrackStatus(Enum):
    """Track download and processing status"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    SKIPPED = "skipped"


class LyricsStatus(Enum):
    """Lyrics download status"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    INSTRUMENTAL = "instrumental"
    SKIPPED = "skipped"


class LyricsSource(Enum):
    """Available lyrics sources"""
    GENIUS = "genius"
    SYNCEDLYRICS = "syncedlyrics"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class AudioFormat(Enum):
    """Supported audio formats"""
    MP3 = "mp3"
    FLAC = "flac"
    M4A = "m4a"


@dataclass
class SpotifyArtist:
    """Spotify artist information"""
    id: str
    name: str
    external_urls: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    popularity: Optional[int] = None
    followers: Optional[int] = None
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any]) -> 'SpotifyArtist':
        """Create SpotifyArtist from Spotify API response"""
        return cls(
            id=data['id'],
            name=data['name'],
            external_urls=data.get('external_urls', {}),
            href=data.get('href'),
            uri=data.get('uri'),
            genres=data.get('genres', []),
            popularity=data.get('popularity'),
            followers=data.get('followers', {}).get('total') if data.get('followers') else None
        )


@dataclass
class SpotifyAlbum:
    """Spotify album information"""
    id: str
    name: str
    album_type: str
    total_tracks: int
    release_date: str
    release_date_precision: str
    artists: List[SpotifyArtist] = field(default_factory=list)
    external_urls: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    images: List[Dict[str, Any]] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    popularity: Optional[int] = None
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any]) -> 'SpotifyAlbum':
        """Create SpotifyAlbum from Spotify API response"""
        artists = [SpotifyArtist.from_spotify_data(artist) for artist in data.get('artists', [])]
        
        return cls(
            id=data['id'],
            name=data['name'],
            album_type=data['album_type'],
            total_tracks=data['total_tracks'],
            release_date=data['release_date'],
            release_date_precision=data['release_date_precision'],
            artists=artists,
            external_urls=data.get('external_urls', {}),
            href=data.get('href'),
            uri=data.get('uri'),
            images=data.get('images', []),
            genres=data.get('genres', []),
            popularity=data.get('popularity')
        )
    
    def get_best_image(self, min_size: int = 300) -> Optional[str]:
        """Get the best album image URL above minimum size"""
        if not self.images:
            return None
        
        # Filter images above minimum size
        suitable_images = [img for img in self.images 
                          if img.get('width', 0) >= min_size or img.get('height', 0) >= min_size]
        
        if suitable_images:
            # Return the largest suitable image
            return max(suitable_images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']
        else:
            # Return the largest available image
            return max(self.images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']


@dataclass
class SpotifyTrack:
    """Spotify track information"""
    id: str
    name: str
    artists: List[SpotifyArtist]
    album: SpotifyAlbum
    duration_ms: int
    explicit: bool
    popularity: int
    track_number: int
    disc_number: int = 1
    external_urls: Dict[str, str] = field(default_factory=dict)
    external_ids: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    preview_url: Optional[str] = None
    is_local: bool = False
    is_playable: bool = True
    
    # Additional metadata
    added_at: Optional[datetime] = None
    genres: List[str] = field(default_factory=list)
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any], added_at: Optional[str] = None) -> 'SpotifyTrack':
        """Create SpotifyTrack from Spotify API response"""
        track_data = data.get('track', data)  # Handle playlist item format
        
        artists = [SpotifyArtist.from_spotify_data(artist) for artist in track_data.get('artists', [])]
        album = SpotifyAlbum.from_spotify_data(track_data['album'])
        
        # Parse added_at if provided
        added_at_dt = None
        if added_at:
            try:
                added_at_dt = datetime.fromisoformat(added_at.replace('Z', '+00:00'))
            except Exception:
                pass
        
        return cls(
            id=track_data['id'],
            name=track_data['name'],
            artists=artists,
            album=album,
            duration_ms=track_data['duration_ms'],
            explicit=track_data['explicit'],
            popularity=track_data['popularity'],
            track_number=track_data['track_number'],
            disc_number=track_data.get('disc_number', 1),
            external_urls=track_data.get('external_urls', {}),
            external_ids=track_data.get('external_ids', {}),
            href=track_data.get('href'),
            uri=track_data.get('uri'),
            preview_url=track_data.get('preview_url'),
            is_local=track_data.get('is_local', False),
            is_playable=track_data.get('is_playable', True),
            added_at=added_at_dt
        )
    
    @property
    def duration_str(self) -> str:
        """Get formatted duration string (mm:ss)"""
        total_seconds = self.duration_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    @property
    def primary_artist(self) -> str:
        """Get primary artist name"""
        return self.artists[0].name if self.artists else "Unknown Artist"
    
    @property
    def all_artists(self) -> str:
        """Get all artist names joined by comma"""
        return ", ".join(artist.name for artist in self.artists)
    
    @property
    def clean_title(self) -> str:
        """Get cleaned track title for filename"""
        return self.name.replace('/', '-').replace('\\', '-')
    
    @property
    def clean_artist(self) -> str:
        """Get cleaned primary artist name for filename"""
        return self.primary_artist.replace('/', '-').replace('\\', '-')


@dataclass
class PlaylistTrack:
    """Track within a playlist context with additional metadata"""
    spotify_track: SpotifyTrack
    playlist_position: int
    
    # Download status
    audio_status: TrackStatus = TrackStatus.PENDING
    lyrics_status: LyricsStatus = LyricsStatus.PENDING
    
    # File information
    local_file_path: Optional[str] = None
    lyrics_file_path: Optional[str] = None
    audio_format: Optional[AudioFormat] = None
    file_size_bytes: Optional[int] = None
    
    # Download metadata
    download_attempts: int = 0
    lyrics_attempts: int = 0
    last_download_attempt: Optional[datetime] = None
    last_lyrics_attempt: Optional[datetime] = None
    download_error: Optional[str] = None
    lyrics_error: Optional[str] = None
    
    # YouTube Music match info
    youtube_video_id: Optional[str] = None
    youtube_title: Optional[str] = None
    youtube_duration: Optional[int] = None
    youtube_match_score: Optional[float] = None
    
    # Lyrics information
    lyrics_source: Optional[LyricsSource] = None
    lyrics_content: Optional[str] = None
    lyrics_synced: bool = False
    lyrics_embedded: bool = False
    
    @property
    def track_id(self) -> str:
        """Get Spotify track ID"""
        return self.spotify_track.id
    
    @property
    def track_name(self) -> str:
        """Get track name"""
        return self.spotify_track.name
    
    @property
    def artist_name(self) -> str:
        """Get primary artist name"""
        return self.spotify_track.primary_artist
    
    @property
    def duration_str(self) -> str:
        """Get formatted duration"""
        return self.spotify_track.duration_str
    
    @property
    def filename(self) -> str:
        """Generate filename for this track"""
        from ..utils.helpers import sanitize_filename
        
        position = f"{self.playlist_position:02d}"
        artist = sanitize_filename(self.artist_name)
        title = sanitize_filename(self.track_name)
        
        return f"{position} - {artist} - {title}"
    
    def get_status_icons(self) -> str:
        """Get status icons for tracklist display"""
        audio_icon = "✅" if self.audio_status == TrackStatus.DOWNLOADED else "⏳"
        lyrics_icon = "🎵" if self.lyrics_status == LyricsStatus.DOWNLOADED else "🚫" if self.lyrics_status == LyricsStatus.NOT_FOUND else "⏳"
        return f"{audio_icon}{lyrics_icon}"


@dataclass
class SpotifyPlaylist:
    """Spotify playlist information"""
    id: str
    name: str
    description: str
    owner_id: str
    owner_name: str
    public: bool
    collaborative: bool
    total_tracks: int
    external_urls: Dict[str, str] = field(default_factory=dict)
    href: Optional[str] = None
    uri: Optional[str] = None
    images: List[Dict[str, Any]] = field(default_factory=list)
    followers: Optional[int] = None
    snapshot_id: Optional[str] = None
    
    # Track list
    tracks: List[PlaylistTrack] = field(default_factory=list)
    
    # Local metadata
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    local_directory: Optional[str] = None
    
    @classmethod
    def from_spotify_data(cls, data: Dict[str, Any]) -> 'SpotifyPlaylist':
        """Create SpotifyPlaylist from Spotify API response"""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            owner_id=data['owner']['id'],
            owner_name=data['owner']['display_name'] or data['owner']['id'],
            public=data.get('public', False),
            collaborative=data.get('collaborative', False),
            total_tracks=data['tracks']['total'],
            external_urls=data.get('external_urls', {}),
            href=data.get('href'),
            uri=data.get('uri'),
            images=data.get('images', []),
            followers=data.get('followers', {}).get('total') if data.get('followers') else None,
            snapshot_id=data.get('snapshot_id')
        )
    
    def add_track(self, spotify_track: SpotifyTrack, position: int, added_at: Optional[str] = None) -> PlaylistTrack:
        """Add a track to the playlist"""
        playlist_track = PlaylistTrack(
            spotify_track=spotify_track,
            playlist_position=position
        )
        self.tracks.append(playlist_track)
        return playlist_track
    
    def get_track_by_id(self, track_id: str) -> Optional[PlaylistTrack]:
        """Get track by Spotify ID"""
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        return None
    
    def get_track_by_position(self, position: int) -> Optional[PlaylistTrack]:
        """Get track by playlist position"""
        for track in self.tracks:
            if track.playlist_position == position:
                return track
        return None
    
    @property
    def downloaded_tracks(self) -> List[PlaylistTrack]:
        """Get list of successfully downloaded tracks"""
        return [track for track in self.tracks if track.audio_status == TrackStatus.DOWNLOADED]
    
    @property
    def pending_tracks(self) -> List[PlaylistTrack]:
        """Get list of tracks pending download"""
        return [track for track in self.tracks if track.audio_status == TrackStatus.PENDING]
    
    @property
    def failed_tracks(self) -> List[PlaylistTrack]:
        """Get list of tracks with failed downloads"""
        return [track for track in self.tracks if track.audio_status == TrackStatus.FAILED]
    
    @property
    def download_progress(self) -> float:
        """Get download progress as percentage (0.0-1.0)"""
        if not self.tracks:
            return 0.0
        downloaded = len(self.downloaded_tracks)
        return downloaded / len(self.tracks)
    
    @property
    def lyrics_downloaded_count(self) -> int:
        """Get count of tracks with downloaded lyrics"""
        return len([track for track in self.tracks if track.lyrics_status == LyricsStatus.DOWNLOADED])
    
    @property
    def lyrics_progress(self) -> float:
        """Get lyrics download progress as percentage (0.0-1.0)"""
        if not self.tracks:
            return 0.0
        downloaded = self.lyrics_downloaded_count
        return downloaded / len(self.tracks)
    
    def get_best_image(self, min_size: int = 300) -> Optional[str]:
        """Get the best playlist image URL above minimum size"""
        if not self.images:
            return None
        
        # Filter images above minimum size
        suitable_images = [img for img in self.images 
                          if img.get('width', 0) >= min_size or img.get('height', 0) >= min_size]
        
        if suitable_images:
            # Return the largest suitable image
            return max(suitable_images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']
        else:
            # Return the largest available image
            return max(self.images, key=lambda x: x.get('width', 0) * x.get('height', 0))['url']
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert playlist to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'owner_name': self.owner_name,
            'public': self.public,
            'collaborative': self.collaborative,
            'total_tracks': self.total_tracks,
            'external_urls': self.external_urls,
            'href': self.href,
            'uri': self.uri,
            'images': self.images,
            'followers': self.followers,
            'snapshot_id': self.snapshot_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None,
            'local_directory': self.local_directory,
            'tracks': [self._track_to_dict(track) for track in self.tracks]
        }
    
    def _track_to_dict(self, track: PlaylistTrack) -> Dict[str, Any]:
        """Convert PlaylistTrack to dictionary"""
        return {
            'spotify_track_id': track.spotify_track.id,
            'playlist_position': track.playlist_position,
            'audio_status': track.audio_status.value,
            'lyrics_status': track.lyrics_status.value,
            'local_file_path': track.local_file_path,
            'lyrics_file_path': track.lyrics_file_path,
            'audio_format': track.audio_format.value if track.audio_format else None,
            'file_size_bytes': track.file_size_bytes,
            'download_attempts': track.download_attempts,
            'lyrics_attempts': track.lyrics_attempts,
            'last_download_attempt': track.last_download_attempt.isoformat() if track.last_download_attempt else None,
            'last_lyrics_attempt': track.last_lyrics_attempt.isoformat() if track.last_lyrics_attempt else None,
            'download_error': track.download_error,
            'lyrics_error': track.lyrics_error,
            'youtube_video_id': track.youtube_video_id,
            'youtube_title': track.youtube_title,
            'youtube_duration': track.youtube_duration,
            'youtube_match_score': track.youtube_match_score,
            'lyrics_source': track.lyrics_source.value if track.lyrics_source else None,
            'lyrics_synced': track.lyrics_synced,
            'lyrics_embedded': track.lyrics_embedded
        }


@dataclass
class DownloadStats:
    """Statistics for download operations"""
    total_tracks: int = 0
    downloaded_tracks: int = 0
    failed_tracks: int = 0
    skipped_tracks: int = 0
    total_lyrics: int = 0
    downloaded_lyrics: int = 0
    failed_lyrics: int = 0
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_size_bytes: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate download success rate"""
        if self.total_tracks == 0:
            return 0.0
        return self.downloaded_tracks / self.total_tracks
    
    @property
    def lyrics_success_rate(self) -> float:
        """Calculate lyrics download success rate"""
        if self.total_lyrics == 0:
            return 0.0
        return self.downloaded_lyrics / self.total_lyrics
    
    @property
    def duration(self) -> Optional[float]:
        """Get operation duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def total_size_mb(self) -> float:
        """Get total size in megabytes"""
        return self.total_size_bytes / (1024 * 1024)
    
    def __str__(self) -> str:
        """String representation of stats"""
        return (f"Downloads: {self.downloaded_tracks}/{self.total_tracks} "
                f"({self.success_rate:.1%}), "
                f"Lyrics: {self.downloaded_lyrics}/{self.total_lyrics} "
                f"({self.lyrics_success_rate:.1%}), "
                f"Size: {self.total_size_mb:.1f}MB")