"""
Configuration management for Playlist-Downloader

This module handles loading, validation, and management of application settings
from multiple sources including YAML files and environment variables. It provides
a centralized configuration system that supports hot-reloading and validation.

The configuration is organized into logical sections using dataclasses:
- Spotify API settings (credentials, scopes)
- Download preferences (format, quality, output)
- Audio processing options (normalization, trimming)
- Lyrics integration settings (sources, formats)
- System and security configurations

All sensitive data (API keys, secrets) can be loaded from environment variables
for security, while non-sensitive settings can be stored in YAML files.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


@dataclass
class SpotifyConfig:
    """
    Spotify API configuration and authentication settings
    
    Contains credentials and settings for Spotify Web API integration.
    Sensitive values (client_id, client_secret) should be provided via
    environment variables for security.
    """
    client_id: str = ""
    client_secret: str = ""
    redirect_url: str = "http://localhost:8080/callback"
    scope: str = "playlist-read-private playlist-read-collaborative user-library-read"


@dataclass
class DownloadConfig:
    """
    Download configuration settings and preferences
    
    Controls audio download behavior including format, quality, concurrency,
    and retry logic. These settings affect both performance and output quality.
    """
    output_directory: str = "~/Music/Playlist Downloads"
    format: str = "m4a"  # mp3, flac, m4a
    quality: str = "high"  # low, medium, high
    bitrate: int = 320
    concurrency: int = 3
    retry_attempts: int = 3
    timeout: int = 300


@dataclass
class AudioConfig:
    """
    Audio processing configuration options
    
    Settings for post-download audio enhancement including silence removal,
    normalization, and quality control. These affect processing time but
    can significantly improve audio quality and consistency.
    """
    trim_silence: bool = True
    normalize: bool = False
    max_duration: int = 960  # 16 minutes
    min_duration: int = 30   # 30 seconds
    sample_rate: int = 44100
    channels: int = 2


@dataclass
class YTMusicConfig:
    """
    YouTube Music search configuration and algorithms
    
    Controls the intelligent search behavior for finding the best YouTube Music
    matches for Spotify tracks. Tuning these parameters affects match accuracy
    and search performance.
    """
    search_algorithm: str = "multi_strategy"
    max_results: int = 5
    score_threshold: int = 70
    prefer_official: bool = True
    exclude_live: bool = True
    exclude_covers: bool = True
    duration_tolerance: int = 15


@dataclass
class LyricsConfig:
    """
    Lyrics download and processing configuration
    
    Manages lyrics integration from multiple sources including download behavior,
    format preferences, and quality validation. Supports both embedded lyrics
    and separate files with various formats.
    """
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
    """
    Synchronization configuration for playlist updates
    
    Controls how the application handles playlist synchronization including
    automatic updates, change detection, and backup behavior. These settings
    determine how efficiently playlists stay current with Spotify.
    """
    auto_sync: bool = False
    check_interval: int = 3600
    sync_lyrics: bool = True
    backup_tracklist: bool = True
    detect_moved_tracks: bool = True


@dataclass
class MetadataConfig:
    """
    Metadata and ID3 tag configuration
    
    Controls how metadata is embedded in audio files including what information
    to include, ID3 version, and encoding. Proper metadata makes files more
    compatible with music players and media libraries.
    """
    include_album_art: bool = True
    include_spotify_metadata: bool = True
    preserve_original_tags: bool = False
    add_comment: bool = True
    id3_version: str = "2.4"
    encoding: str = "utf-8"
    include_lyrics_in_comment: bool = False


@dataclass
class LoggingConfig:
    """
    Logging configuration and output settings
    
    Controls application logging behavior including log levels, file output,
    rotation, and console formatting. Proper logging is essential for
    debugging and monitoring application behavior.
    """
    level: str = "INFO"
    file: str = ""
    max_size: str = "50MB"
    backup_count: int = 3
    console_output: bool = True
    colored_output: bool = True


@dataclass
class NetworkConfig:
    """
    Network and HTTP configuration settings
    
    Controls network behavior including timeouts, retry logic, rate limiting,
    and user agent strings. These settings help ensure reliable operation
    while respecting API rate limits.
    """
    user_agent: str = "Playlist-Downloader/1.0"
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1
    rate_limit_delay: int = 1


@dataclass
class SecurityConfig:
    """
    Security and storage configuration
    
    Controls where sensitive data is stored and how it's protected.
    Includes paths for token storage and configuration directories.
    """
    token_storage_path: str = "~/.playlist-downloader/tokens.json"
    config_directory: str = "~/.playlist-downloader/"
    encrypt_tokens: bool = False


@dataclass
class FeaturesConfig:
    """
    Feature flags configuration for experimental features
    
    Controls access to experimental or advanced features that may be
    unstable or still in development. Allows gradual rollout of new
    functionality without breaking existing workflows.
    """
    experimental_parallel_lyrics: bool = False
    smart_retry_algorithm: bool = True
    advanced_audio_analysis: bool = False
    playlist_backup: bool = True


@dataclass
class NamingConfig:
    """
    File naming configuration and formatting
    
    Controls how downloaded files are named including format templates,
    character sanitization, and length limits. Proper naming ensures
    compatibility across different filesystems and media players.
    """
    track_format: str = "{track:02d} - {artist} - {title}"
    sanitize_filenames: bool = True
    max_filename_length: int = 200
    replace_spaces: bool = False


class Settings:
    """
    Main settings class that manages all configuration
    
    This class serves as the central configuration manager, loading settings
    from multiple sources (YAML files, environment variables) and providing
    a unified interface for accessing configuration throughout the application.
    
    The class handles:
    - Loading configuration from YAML files
    - Overriding with environment variables
    - Creating necessary directories
    - Validating configuration values
    - Saving configuration back to files
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize settings from config file or environment variables
        
        Args:
            config_path: Path to custom config file, if None uses default locations
        """
        self.config_path = config_path
        self.config_dir = Path.home() / ".playlist-downloader"
        
        # Initialize all configuration objects with default values
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
        
        # Load configuration from various sources in order of precedence
        self._load_config()
        self._load_environment_variables()
        self._create_directories()
    
    def _load_config(self) -> None:
        """
        Load configuration from YAML file
        
        Searches for configuration files in multiple locations in order of
        precedence. The first file found will be used. This allows for
        both system-wide and user-specific configurations.
        """
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
        
        # Apply loaded configuration to dataclass instances
        self._apply_config(config_data)
    
    def _apply_config(self, config_data: Dict[str, Any]) -> None:
        """
        Apply configuration data to dataclass instances
        
        Maps configuration sections from the YAML file to the appropriate
        dataclass instances, updating only the attributes that exist in
        both the config file and the dataclass definition.
        
        Args:
            config_data: Dictionary containing configuration sections
        """
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
        
        # Apply configuration values to corresponding dataclass instances
        for section_name, section_data in config_data.items():
            if section_name in config_mapping and isinstance(section_data, dict):
                config_obj = config_mapping[section_name]
                for key, value in section_data.items():
                    if hasattr(config_obj, key):
                        setattr(config_obj, key, value)
    
    def _load_environment_variables(self) -> None:
        """
        Load sensitive configuration from environment variables
        
        Environment variables take precedence over file-based configuration
        for security-sensitive values. This allows secure deployment without
        storing credentials in configuration files.
        """
        env_mappings = {
            'SPOTIFY_CLIENT_ID': lambda v: setattr(self.spotify, 'client_id', v),
            'SPOTIFY_CLIENT_SECRET': lambda v: setattr(self.spotify, 'client_secret', v),
            'SPOTIFY_REDIRECT_URL': lambda v: setattr(self.spotify, 'redirect_url', v),
            'GENIUS_API_KEY': lambda v: setattr(self.lyrics, 'genius_api_key', v),
            'DOWNLOAD_OUTPUT_DIR': lambda v: setattr(self.download, 'output_directory', v),
        }
        
        # Apply environment variables if they exist
        for env_var, setter in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                setter(value)
    
    def _create_directories(self) -> None:
        """
        Create necessary directories for application operation
        
        Ensures that required directories exist, creating them if necessary.
        This includes the configuration directory and output directory.
        Handles permission errors gracefully with warnings.
        """
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
        """
        Get the expanded output directory path
        
        Returns the output directory with user home directory expansion
        and path resolution applied.
        
        Returns:
            Path object for the output directory
        """
        return Path(self.download.output_directory).expanduser()
    
    def get_config_directory(self) -> Path:
        """
        Get the expanded config directory path
        
        Returns the configuration directory with user home directory expansion
        and path resolution applied.
        
        Returns:
            Path object for the configuration directory
        """
        return Path(self.security.config_directory).expanduser()
    
    def get_token_storage_path(self) -> Path:
        """
        Get the expanded token storage path
        
        Returns the token storage file path with user home directory expansion
        and path resolution applied.
        
        Returns:
            Path object for the token storage file
        """
        return Path(self.security.token_storage_path).expanduser()
    
    def save_config(self, path: Optional[str] = None) -> None:
        """
        Save current configuration to file
        
        Serializes the current configuration to a YAML file, excluding
        sensitive data like API keys and secrets for security.
        
        Args:
            path: Custom path to save config, defaults to user config directory
            
        Raises:
            Exception: If the configuration cannot be saved
        """
        if not path:
            path = self.get_config_directory() / "config.yaml"
        else:
            path = Path(path)
        
        # Convert all dataclass instances to dictionaries
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
        
        # Remove sensitive data from saved config for security
        config_data['spotify']['client_id'] = ""
        config_data['spotify']['client_secret'] = ""
        config_data['lyrics']['genius_api_key'] = ""
        
        try:
            # Ensure directory exists before saving
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save config to {path}: {e}")
    
    def _dataclass_to_dict(self, obj) -> Dict[str, Any]:
        """
        Convert dataclass to dictionary
        
        Helper method to serialize dataclass instances to dictionaries
        for YAML output.
        
        Args:
            obj: Dataclass instance to convert
            
        Returns:
            Dictionary representation of the dataclass
        """
        result = {}
        for key, value in obj.__dict__.items():
            result[key] = value
        return result
    
    def validate(self) -> bool:
        """
        Validate current configuration
        
        Performs comprehensive validation of all configuration values to
        ensure they are valid and consistent. This helps catch configuration
        errors early and provides helpful error messages.
        
        Returns:
            True if configuration is valid, False otherwise
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
        
        # Display validation errors if any exist
        if errors:
            print("Configuration validation errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True
    
    def __str__(self) -> str:
        """
        String representation of settings
        
        Provides a concise summary of key configuration values for
        debugging and logging purposes.
        
        Returns:
            String summary of configuration
        """
        sections = [
            f"Download: {self.download.format} @ {self.download.quality}",
            f"Output: {self.download.output_directory}",
            f"Lyrics: {'enabled' if self.lyrics.enabled else 'disabled'}",
            f"Concurrency: {self.download.concurrency}",
        ]
        return f"Settings({', '.join(sections)})"


# Global settings instance for singleton pattern
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global settings instance
    
    Provides access to the singleton settings instance that is shared
    throughout the application. This ensures consistent configuration
    across all modules.
    
    Returns:
        The global Settings instance
    """
    return settings


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """
    Reload settings from configuration files
    
    Creates a new settings instance with updated configuration from files
    and environment variables. Useful for hot-reloading configuration
    during development or when configuration files change.
    
    Args:
        config_path: Optional path to specific config file
        
    Returns:
        New Settings instance with reloaded configuration
    """
    global settings
    settings = Settings(config_path)
    return settings