"""
ID3 tag and metadata management for audio files
Handles embedding of track information, album art, and lyrics
"""

import os
import re
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, BinaryIO
from io import BytesIO
from PIL import Image
import mutagen
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TPE2, TPOS, TCON, COMM, APIC, USLT, SYLT
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import retry_on_failure, sanitize_filename
from ..spotify.models import SpotifyTrack, LyricsSource


class MetadataManager:
    """Manages audio file metadata and ID3 tags"""
    
    def __init__(self):
        """Initialize metadata manager"""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Metadata configuration
        self.include_album_art = self.settings.metadata.include_album_art
        self.include_spotify_metadata = self.settings.metadata.include_spotify_metadata
        self.preserve_original_tags = self.settings.metadata.preserve_original_tags
        self.add_comment = self.settings.metadata.add_comment
        self.id3_version = self.settings.metadata.id3_version
        self.encoding = self.settings.metadata.encoding
        
        # Lyrics configuration
        self.embed_lyrics = self.settings.lyrics.embed_in_audio
        self.include_lyrics_in_comment = self.settings.metadata.include_lyrics_in_comment
        
        # HTTP session for downloading images
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.settings.network.user_agent
        })
    
    def embed_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None,
        synced_lyrics: Optional[str] = None
    ) -> bool:
        """
        Embed complete metadata into audio file
        
        Args:
            file_path: Path to audio file
            track: Spotify track information
            track_number: Track number in playlist
            lyrics: Lyrics text
            lyrics_source: Source of lyrics
            synced_lyrics: Synchronized lyrics (LRC format)
            
        Returns:
            True if successful
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                self.logger.error(f"Audio file not found: {file_path}")
                return False
            
            # Determine file format and handle accordingly
            file_extension = file_path_obj.suffix.lower()
            
            if file_extension == '.mp3':
                return self._embed_mp3_metadata(file_path, track, track_number, lyrics, lyrics_source, synced_lyrics)
            elif file_extension == '.flac':
                return self._embed_flac_metadata(file_path, track, track_number, lyrics, lyrics_source)
            elif file_extension in ['.m4a', '.mp4']:
                return self._embed_mp4_metadata(file_path, track, track_number, lyrics, lyrics_source)
            else:
                self.logger.warning(f"Unsupported file format: {file_extension}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to embed metadata in {file_path}: {e}")
            return False
    
    def _embed_mp3_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None,
        synced_lyrics: Optional[str] = None
    ) -> bool:
        """Embed metadata in MP3 file using ID3 tags"""
        try:
            # Load or create ID3 tags
            try:
                audio = MP3(file_path, ID3=ID3)
                if audio.tags is None:
                    audio.add_tags()
            except mutagen.id3.ID3NoHeaderError:
                audio = MP3(file_path)
                audio.add_tags()
            
            # Clear existing tags if not preserving
            if not self.preserve_original_tags:
                audio.tags.clear()
            
            # Basic track information
            audio.tags.add(TIT2(encoding=3, text=track.name))  # Title
            audio.tags.add(TPE1(encoding=3, text=track.all_artists))  # Artist
            audio.tags.add(TALB(encoding=3, text=track.album.name))  # Album
            audio.tags.add(TPE2(encoding=3, text=track.album.artists[0].name if track.album.artists else ""))  # Album Artist
            
            # Release year
            if track.album.release_date:
                year = track.album.release_date[:4]  # Extract year
                audio.tags.add(TDRC(encoding=3, text=year))
            
            # Track number
            if track_number:
                audio.tags.add(TRCK(encoding=3, text=str(track_number)))
            else:
                audio.tags.add(TRCK(encoding=3, text=str(track.track_number)))
            
            # Disc number
            if track.disc_number > 1:
                audio.tags.add(TPOS(encoding=3, text=str(track.disc_number)))
            
            # Genre (if available)
            if track.album.genres:
                audio.tags.add(TCON(encoding=3, text=track.album.genres[0]))
            
            # Comments
            comment_text = self._create_comment_text(track, lyrics_source)
            if comment_text:
                audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=comment_text))
            
            # Lyrics embedding
            if self.embed_lyrics and lyrics:
                # Unsynchronized lyrics
                audio.tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics))
                
                # Synchronized lyrics (if available)
                if synced_lyrics:
                    self._embed_synced_lyrics_mp3(audio, synced_lyrics)
            
            # Album art
            if self.include_album_art:
                album_art = self._download_album_art(track.album.get_best_image())
                if album_art:
                    audio.tags.add(APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,  # Cover (front)
                        desc='Cover',
                        data=album_art
                    ))
            
            # Save changes
            audio.save(v2_version=4 if self.id3_version == "2.4" else 3)
            
            self.logger.debug(f"MP3 metadata embedded successfully: {Path(file_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to embed MP3 metadata: {e}")
            return False
    
    def _embed_flac_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None
    ) -> bool:
        """Embed metadata in FLAC file using Vorbis comments"""
        try:
            audio = FLAC(file_path)
            
            # Clear existing tags if not preserving
            if not self.preserve_original_tags:
                audio.clear()
            
            # Basic track information
            audio['TITLE'] = track.name
            audio['ARTIST'] = track.all_artists
            audio['ALBUM'] = track.album.name
            audio['ALBUMARTIST'] = track.album.artists[0].name if track.album.artists else ""
            
            # Release year
            if track.album.release_date:
                audio['DATE'] = track.album.release_date[:4]
            
            # Track number
            if track_number:
                audio['TRACKNUMBER'] = str(track_number)
            else:
                audio['TRACKNUMBER'] = str(track.track_number)
            
            # Disc number
            if track.disc_number > 1:
                audio['DISCNUMBER'] = str(track.disc_number)
            
            # Genre
            if track.album.genres:
                audio['GENRE'] = track.album.genres[0]
            
            # Comments
            comment_text = self._create_comment_text(track, lyrics_source)
            if comment_text:
                audio['COMMENT'] = comment_text
            
            # Lyrics
            if self.embed_lyrics and lyrics:
                audio['LYRICS'] = lyrics
            
            # Spotify-specific metadata
            if self.include_spotify_metadata:
                audio['SPOTIFY_TRACK_ID'] = track.id
                audio['SPOTIFY_ALBUM_ID'] = track.album.id
                audio['SPOTIFY_ARTIST_ID'] = track.artists[0].id if track.artists else ""
            
            # Album art
            if self.include_album_art:
                album_art = self._download_album_art(track.album.get_best_image())
                if album_art:
                    # Create picture block
                    picture = mutagen.flac.Picture()
                    picture.type = 3  # Cover (front)
                    picture.mime = 'image/jpeg'
                    picture.desc = 'Cover'
                    picture.data = album_art
                    audio.add_picture(picture)
            
            # Save changes
            audio.save()
            
            self.logger.debug(f"FLAC metadata embedded successfully: {Path(file_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to embed FLAC metadata: {e}")
            return False
    
    def _embed_mp4_metadata(
        self, 
        file_path: str, 
        track: SpotifyTrack,
        track_number: Optional[int] = None,
        lyrics: Optional[str] = None,
        lyrics_source: Optional[LyricsSource] = None
    ) -> bool:
        """Embed metadata in MP4/M4A file"""
        try:
            audio = MP4(file_path)
            
            # Clear existing tags if not preserving
            if not self.preserve_original_tags:
                audio.clear()
            
            # Basic track information
            audio['\xa9nam'] = [track.name]  # Title
            audio['\xa9ART'] = [track.all_artists]  # Artist
            audio['\xa9alb'] = [track.album.name]  # Album
            audio['aART'] = [track.album.artists[0].name if track.album.artists else ""]  # Album Artist
            
            # Release year
            if track.album.release_date:
                audio['\xa9day'] = [track.album.release_date[:4]]
            
            # Track number
            if track_number:
                audio['trkn'] = [(track_number, 0)]
            else:
                audio['trkn'] = [(track.track_number, 0)]
            
            # Disc number
            if track.disc_number > 1:
                audio['disk'] = [(track.disc_number, 0)]
            
            # Genre
            if track.album.genres:
                audio['\xa9gen'] = [track.album.genres[0]]
            
            # Comments
            comment_text = self._create_comment_text(track, lyrics_source)
            if comment_text:
                audio['\xa9cmt'] = [comment_text]
            
            # Lyrics
            if self.embed_lyrics and lyrics:
                audio['\xa9lyr'] = [lyrics]
            
            # Album art
            if self.include_album_art:
                album_art = self._download_album_art(track.album.get_best_image())
                if album_art:
                    audio['covr'] = [mutagen.mp4.MP4Cover(album_art, mutagen.mp4.MP4Cover.FORMAT_JPEG)]
            
            # Save changes
            audio.save()
            
            self.logger.debug(f"MP4 metadata embedded successfully: {Path(file_path).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to embed MP4 metadata: {e}")
            return False
    
    def _embed_synced_lyrics_mp3(self, audio: MP3, synced_lyrics: str) -> None:
        """
        Embed synchronized lyrics in MP3 file
        
        Args:
            audio: MP3 audio object
            synced_lyrics: LRC format lyrics
        """
        try:
            # Parse LRC format lyrics
            lyrics_data = []
            
            for line in synced_lyrics.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Match LRC timestamp format [mm:ss.xx]
                match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\](.*)', line)
                if match:
                    minutes, seconds, centiseconds, text = match.groups()
                    
                    # Convert to milliseconds
                    timestamp = (int(minutes) * 60 + int(seconds)) * 1000 + int(centiseconds) * 10
                    
                    lyrics_data.append((text.strip(), timestamp))
            
            if lyrics_data:
                # Create SYLT frame (Synchronized Lyrics)
                audio.tags.add(SYLT(
                    encoding=3,
                    lang='eng',
                    format=2,  # Milliseconds
                    type=1,    # Lyrics
                    desc='',
                    text=lyrics_data
                ))
                
                self.logger.debug("Synchronized lyrics embedded successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to embed synchronized lyrics: {e}")
    
    def _create_comment_text(self, track: SpotifyTrack, lyrics_source: Optional[LyricsSource] = None) -> str:
        """
        Create comment text for audio file
        
        Args:
            track: Spotify track information
            lyrics_source: Source of lyrics
            
        Returns:
            Comment text
        """
        comment_parts = []
        
        if self.add_comment:
            comment_parts.append("Downloaded by Playlist-Downloader")
        
        if self.include_spotify_metadata:
            comment_parts.append(f"Spotify ID: {track.id}")
        
        if self.include_lyrics_in_comment and lyrics_source:
            comment_parts.append(f"Lyrics: {lyrics_source.value}")
        
        return " | ".join(comment_parts)
    
    @retry_on_failure(max_attempts=3, delay=1.0)
    def _download_album_art(self, image_url: Optional[str]) -> Optional[bytes]:
        """
        Download album artwork from URL
        
        Args:
            image_url: URL of album artwork
            
        Returns:
            Image data as bytes or None
        """
        if not image_url:
            return None
        
        try:
            response = self.session.get(
                image_url, 
                timeout=self.settings.network.request_timeout,
                stream=True
            )
            response.raise_for_status()
            
            # Load image and convert to JPEG if needed
            image_data = response.content
            
            # Validate and process image
            try:
                with Image.open(BytesIO(image_data)) as img:
                    # Convert to RGB if necessary
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    # Resize if too large (max 1000x1000)
                    if img.width > 1000 or img.height > 1000:
                        img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
                    
                    # Save as JPEG
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=90, optimize=True)
                    return output.getvalue()
                    
            except Exception as e:
                self.logger.warning(f"Failed to process album art image: {e}")
                # Return original data if processing fails
                return image_data
            
        except Exception as e:
            self.logger.warning(f"Failed to download album art from {image_url}: {e}")
            return None
    
    def read_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read metadata from audio file
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Dictionary with metadata or None
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return None
            
            file_extension = file_path_obj.suffix.lower()
            
            if file_extension == '.mp3':
                return self._read_mp3_metadata(file_path)
            elif file_extension == '.flac':
                return self._read_flac_metadata(file_path)
            elif file_extension in ['.m4a', '.mp4']:
                return self._read_mp4_metadata(file_path)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to read metadata from {file_path}: {e}")
            return None
    
    def _read_mp3_metadata(self, file_path: str) -> Dict[str, Any]:
        """Read metadata from MP3 file"""
        audio = MP3(file_path, ID3=ID3)
        
        metadata = {
            'title': str(audio.tags.get('TIT2', [''])[0]) if audio.tags and audio.tags.get('TIT2') else '',
            'artist': str(audio.tags.get('TPE1', [''])[0]) if audio.tags and audio.tags.get('TPE1') else '',
            'album': str(audio.tags.get('TALB', [''])[0]) if audio.tags and audio.tags.get('TALB') else '',
            'year': str(audio.tags.get('TDRC', [''])[0]) if audio.tags and audio.tags.get('TDRC') else '',
            'track_number': str(audio.tags.get('TRCK', [''])[0]) if audio.tags and audio.tags.get('TRCK') else '',
            'has_lyrics': bool(audio.tags and audio.tags.get('USLT')),
            'duration': audio.info.length if audio.info else 0,
            'bitrate': audio.info.bitrate if audio.info else 0,
        }
        
        return metadata
    
    def _read_flac_metadata(self, file_path: str) -> Dict[str, Any]:
        """Read metadata from FLAC file"""
        audio = FLAC(file_path)
        
        metadata = {
            'title': audio.get('TITLE', [''])[0],
            'artist': audio.get('ARTIST', [''])[0],
            'album': audio.get('ALBUM', [''])[0],
            'year': audio.get('DATE', [''])[0],
            'track_number': audio.get('TRACKNUMBER', [''])[0],
            'has_lyrics': bool(audio.get('LYRICS')),
            'duration': audio.info.length if audio.info else 0,
            'bitrate': audio.info.bitrate if audio.info else 0,
        }
        
        return metadata
    
    def _read_mp4_metadata(self, file_path: str) -> Dict[str, Any]:
        """Read metadata from MP4 file"""
        audio = MP4(file_path)
        
        metadata = {
            'title': audio.get('\xa9nam', [''])[0] if audio.get('\xa9nam') else '',
            'artist': audio.get('\xa9ART', [''])[0] if audio.get('\xa9ART') else '',
            'album': audio.get('\xa9alb', [''])[0] if audio.get('\xa9alb') else '',
            'year': audio.get('\xa9day', [''])[0] if audio.get('\xa9day') else '',
            'track_number': str(audio.get('trkn', [(0, 0)])[0][0]) if audio.get('trkn') else '',
            'has_lyrics': bool(audio.get('\xa9lyr')),
            'duration': audio.info.length if audio.info else 0,
            'bitrate': audio.info.bitrate if audio.info else 0,
        }
        
        return metadata
    
    def strip_metadata(self, file_path: str) -> bool:
        """
        Remove all metadata from audio file
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if successful
        """
        try:
            file_path_obj = Path(file_path)
            file_extension = file_path_obj.suffix.lower()
            
            if file_extension == '.mp3':
                audio = MP3(file_path, ID3=ID3)
                if audio.tags:
                    audio.tags.clear()
                    audio.save()
            elif file_extension == '.flac':
                audio = FLAC(file_path)
                audio.clear()
                audio.save()
            elif file_extension in ['.m4a', '.mp4']:
                audio = MP4(file_path)
                audio.clear()
                audio.save()
            else:
                return False
            
            self.logger.debug(f"Metadata stripped from: {file_path_obj.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to strip metadata from {file_path}: {e}")
            return False
    
    def validate_file_integrity(self, file_path: str) -> bool:
        """
        Validate audio file integrity
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if file is valid
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists() or file_path_obj.stat().st_size == 0:
                return False
            
            file_extension = file_path_obj.suffix.lower()
            
            if file_extension == '.mp3':
                MP3(file_path)
            elif file_extension == '.flac':
                FLAC(file_path)
            elif file_extension in ['.m4a', '.mp4']:
                MP4(file_path)
            else:
                return False
            
            return True
            
        except Exception:
            return False


# Global metadata manager instance
_metadata_manager: Optional[MetadataManager] = None


def get_metadata_manager() -> MetadataManager:
    """Get global metadata manager instance"""
    global _metadata_manager
    if not _metadata_manager:
        _metadata_manager = MetadataManager()
    return _metadata_manager