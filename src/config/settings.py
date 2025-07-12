"""
Configuration management for Playlist-Downloader
Handles loading, validation, and management of application settings
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class SpotifyConfig:
    """Spotify API configuration"""
    client_id: str = ""
    client_secret: str = ""
    redirect_url: str = "http://localhost:8080/callback"
    scope: str = "playlist-read-private playlist-read-collaborative user-library-read"


@dataclass
class DownloadConfig:
    """Download configuration settings"""
    output_directory: str = "~/Music/Playlist Downloads"
    format: str = "m4a"  # mp3, flac, m4a
    quality: str = "high"  # low, medium, high
    bitrate: int = 320
    concurrency: int = 3
    retry_attempts: int = 3
    timeout: int = 300


@dataclass
class AudioConfig:
    """Audio processing configuration"""
    trim_silence: bool = True
    normalize: bool = False
    max_duration: int = 960  # 16 minutes
    min_duration: int = 30   # 30 seconds
    sample_rate: int = 44100
    channels: int = 2


@dataclass
class YTMusicConfig:
    """YouTube Music search configuration"""
    search_algorithm: str = "multi_strategy"
    max_results: int = 5
    score_threshold: int = 70
    prefer_official: bool = True
    exclude_live: bool = True
    exclude_covers: bool = True
    duration_tolerance: int = 15


@dataclass
class LyricsConfig:
    """Lyrics download and processing configuration"""
    enabled: bool = True
    download_separate_files: bool = True
    embed_in_audio: bool = True
    format: str = "lrc"  # lrc, txt, both
    primary_source: str = "genius"
    fallback_sources: list = field(default_factory=lambda: ["syncedlyrics"])
    clean_lyrics: bool = True
    min_length: int = 50
    timeout: int = 30
    max_attempts: int = 3
    genius_api_key: str = ""
    similarity_threshold: float = 0.7
    exclude_instrumental: bool = True
    include_translations: bool = False


@dataclass
class SyncConfig:
    """Synchronization configuration"""
    auto_sync: bool = False
    check_interval: int = 3600
    sync_lyrics: bool = True
    backup_tracklist: bool = True
    detect_moved_tracks: bool = True


@dataclass
class MetadataConfig:
    """Metadata and ID3 tag configuration"""
    include_album_art: bool = True
    include_spotify_metadata: bool = True
    preserve_original_tags: bool = False
    add_comment: bool = True
    id3_version: str = "2.4"
    encoding: str = "utf-8"
    include_lyrics_in_comment: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: str = ""
    max_size: str = "50MB"
    backup_count: int = 3
    console_output: bool = True
    colored_output: bool = True


@dataclass
class NetworkConfig:
    """Network and HTTP configuration"""
    user_agent: str = "Playlist-Downloader/1.0"
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1
    rate_limit_delay: int = 1


@dataclass
class SecurityConfig:
    """Security and storage configuration"""
    token_storage_path: str = "~/.playlist-downloader/tokens.json"
    config_directory: str = "~/.playlist-downloader/"
    encrypt_tokens: bool = False


@dataclass
class FeaturesConfig:
    """Feature flags configuration"""
    experimental_parallel_lyrics: bool = False
    smart_retry_algorithm: bool = True
    advanced_audio_analysis: bool = False
    playlist_backup: bool = True


@dataclass
class NamingConfig:
    """File naming configuration"""
    track_format: str = "{track:02d} - {artist} - {title}"
    sanitize_filenames: bool = True
    max_filename_length: int = 200
    replace_spaces: bool = False


class Settings:
    """Main settings class that manages all configuration"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize settings from config file or environment variables
        
        Args:
            config_path: Path to custom config file
        """
        self.config_path = config_path
        self.config_dir = Path.home() / ".playlist-downloader"
        
        # Initialize configuration objects
        self.spotify = SpotifyConfig()
        self.download = DownloadConfig()
        self.audio = AudioConfig()
        self.ytmusic = YTMusicConfig()
        self.lyrics = LyricsConfig()
        self.update = SyncConfig()
        self.metadata = MetadataConfig()
        self.logging = LoggingConfig()
        self.network = NetworkConfig()
        self.security = SecurityConfig()
        self.features = FeaturesConfig()
        self.naming = NamingConfig()
        
        # Load configuration
        self._load_config()
        self._load_environment_variables()
        self._create_directories()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        config_paths = [
            self.config_path,
            self.config_dir / "config.yaml",
            Path("config/config.yaml"),
            Path("config.yaml")
        ]
        
        config_data = {}
        for path in config_paths:
            if path and Path(path).exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f) or {}
                    break
                except Exception as e:
                    print(f"Warning: Failed to load config from {path}: {e}")
        
        # Apply configuration to dataclasses
        self._apply_config(config_data)
    
    def _apply_config(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration data to dataclass instances"""
        config_mapping = {
            'spotify': self.spotify,
            'download': self.download,
            'audio': self.audio,
            'ytmusic': self.ytmusic,
            'lyrics': self.lyrics,
            'update': self.update,
            'metadata': self.metadata,
            'logging': self.logging,
            'network': self.network,
            'security': self.security,
            'features': self.features,
            'naming': self.naming
        }
        
        for section_name, section_data in config_data.items():
            if section_name in config_mapping and isinstance(section_data, dict):
                config_obj = config_mapping[section_name]
                for key, value in section_data.items():
                    if hasattr(config_obj, key):
                        setattr(config_obj, key, value)
    
    def _load_environment_variables(self) -> None:
        """Load sensitive configuration from environment variables"""
        env_mappings = {
            'SPOTIFY_CLIENT_ID': lambda v: setattr(self.spotify, 'client_id', v),
            'SPOTIFY_CLIENT_SECRET': lambda v: setattr(self.spotify, 'client_secret', v),
            'SPOTIFY_REDIRECT_URL': lambda v: setattr(self.spotify, 'redirect_url', v),
            'GENIUS_API_KEY': lambda v: setattr(self.lyrics, 'genius_api_key', v),
            'DOWNLOAD_OUTPUT_DIR': lambda v: setattr(self.download, 'output_directory', v),
        }
        
        for env_var, setter in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                setter(value)
    
    def _create_directories(self) -> None:
        """Create necessary directories"""
        directories = [
            Path(self.security.config_directory).expanduser(),
            Path(self.download.output_directory).expanduser(),
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Warning: Failed to create directory {directory}: {e}")
    
    def get_output_directory(self) -> Path:
        """Get the expanded output directory path"""
        return Path(self.download.output_directory).expanduser()
    
    def get_config_directory(self) -> Path:
        """Get the expanded config directory path"""
        return Path(self.security.config_directory).expanduser()
    
    def get_token_storage_path(self) -> Path:
        """Get the expanded token storage path"""
        return Path(self.security.token_storage_path).expanduser()
    
    def save_config(self, path: Optional[str] = None) -> None:
        """
        Save current configuration to file
        
        Args:
            path: Custom path to save config, defaults to user config directory
        """
        if not path:
            path = self.get_config_directory() / "config.yaml"
        else:
            path = Path(path)
        
        config_data = {
            'spotify': self._dataclass_to_dict(self.spotify),
            'download': self._dataclass_to_dict(self.download),
            'audio': self._dataclass_to_dict(self.audio),
            'ytmusic': self._dataclass_to_dict(self.ytmusic),
            'lyrics': self._dataclass_to_dict(self.lyrics),
            'update': self._dataclass_to_dict(self.update),
            'metadata': self._dataclass_to_dict(self.metadata),
            'logging': self._dataclass_to_dict(self.logging),
            'network': self._dataclass_to_dict(self.network),
            'security': self._dataclass_to_dict(self.security),
            'features': self._dataclass_to_dict(self.features),
            'naming': self._dataclass_to_dict(self.naming)
        }
        
        # Remove sensitive data from saved config
        config_data['spotify']['client_id'] = ""
        config_data['spotify']['client_secret'] = ""
        config_data['lyrics']['genius_api_key'] = ""
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save config to {path}: {e}")
    
    def _dataclass_to_dict(self, obj) -> Dict[str, Any]:
        """Convert dataclass to dictionary"""
        result = {}
        for key, value in obj.__dict__.items():
            result[key] = value
        return result
    
    def validate(self) -> bool:
        """
        Validate current configuration
        
        Returns:
            True if configuration is valid
        """
        errors = []
        
        # Validate Spotify credentials
        if not self.spotify.client_id or not self.spotify.client_secret:
            errors.append("Spotify client_id and client_secret are required")
        
        # Validate download format
        if self.download.format not in ['mp3', 'flac', 'm4a']:
            errors.append(f"Invalid download format: {self.download.format}")
        
        # Validate quality setting
        if self.download.quality not in ['low', 'medium', 'high']:
            errors.append(f"Invalid quality setting: {self.download.quality}")
        
        # Validate lyrics format
        if self.lyrics.format not in ['lrc', 'txt', 'both']:
            errors.append(f"Invalid lyrics format: {self.lyrics.format}")
        
        # Validate lyrics source
        valid_sources = ['genius','syncedlyrics']
        if self.lyrics.primary_source not in valid_sources:
            errors.append(f"Invalid primary lyrics source: {self.lyrics.primary_source}")
        
        # Print validation errors
        if errors:
            print("Configuration validation errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True
    
    def __str__(self) -> str:
        """String representation of settings"""
        sections = [
            f"Download: {self.download.format} @ {self.download.quality}",
            f"Output: {self.download.output_directory}",
            f"Lyrics: {'enabled' if self.lyrics.enabled else 'disabled'}",
            f"Concurrency: {self.download.concurrency}",
        ]
        return f"Settings({', '.join(sections)})"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """Reload settings from configuration files"""
    global settings
    settings = Settings(config_path)
    return settings