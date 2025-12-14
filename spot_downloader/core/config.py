"""
Configuration management for spot-downloader.

This module handles loading, validating, and providing access to the
application configuration stored in config.yaml.

The configuration file contains:
    - Spotify API credentials (client_id, client_secret)
    - Output directory for downloaded files
    - Number of parallel download threads
    - Optional cookie file path for YouTube Premium quality

Configuration File Location:
    The config.yaml file must be in the current working directory
    when running the application.

Example config.yaml:
    spotify:
      client_id: "your_client_id_here"
      client_secret: "your_client_secret_here"
    
    output:
      directory: "~/Desktop/Music/SpotDownloader"
    
    download:
      threads: 4
      cookie_file: null  # Optional: path to cookies.txt for YT Premium
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from spot_downloader.core.exceptions import ConfigError


# Default configuration file name (always in current working directory)
CONFIG_FILENAME = "config.yaml"


@dataclass(frozen=True)
class SpotifyConfig:
    """
    Spotify API credentials configuration.
    
    These credentials are obtained from the Spotify Developer Dashboard:
    https://developer.spotify.com/dashboard
    
    Attributes:
        client_id: The Spotify application client ID.
                   A 32-character hexadecimal string.
        client_secret: The Spotify application client secret.
                       A 32-character hexadecimal string.
                       Keep this value secure and never commit to version control.
    """
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class OutputConfig:
    """
    Output directory configuration.
    
    Attributes:
        directory: Absolute path to the directory where downloaded files will be saved.
                   Path expansion is performed (~ is expanded to home directory).
                   The directory will be created if it doesn't exist.
                   
                   Files are saved as: {directory}/{track_number}-{title}-{artist}.m4a
    """
    directory: Path


@dataclass(frozen=True)
class DownloadConfig:
    """
    Download behavior configuration.
    
    Attributes:
        threads: Number of parallel download threads.
                 Higher values speed up downloads but increase API rate limit risk.
                 Recommended range: 1-8. Default: 4.
        cookie_file: Optional path to a cookies.txt file exported from browser.
                     Required for YouTube Music Premium quality (256 kbps).
                     Without cookies, downloads are limited to 128 kbps.
                     The file should be exported from music.youtube.com using
                     a browser extension like "Get cookies.txt".
    """
    threads: int
    cookie_file: Path | None


@dataclass(frozen=True)
class Config:
    """
    Complete application configuration.
    
    This is the main configuration object that aggregates all configuration
    sections. It is created by load_config() and should be treated as
    immutable (frozen dataclass).
    
    Attributes:
        spotify: Spotify API credentials.
        output: Output directory settings.
        download: Download behavior settings.
    
    Example:
        config = load_config()
        print(f"Saving to: {config.output.directory}")
        print(f"Using {config.download.threads} threads")
    """
    spotify: SpotifyConfig
    output: OutputConfig
    download: DownloadConfig


def load_config(config_path: Path | None = None) -> Config:
    """
    Load and validate configuration from config.yaml.
    
    This function reads the YAML configuration file, validates all required
    fields are present and have valid values, expands paths, and returns
    a frozen Config object.
    
    Args:
        config_path: Optional explicit path to config file.
                     If None, looks for config.yaml in current working directory.
    
    Returns:
        Config: A frozen dataclass containing all configuration values.
    
    Raises:
        ConfigError: If the config file is not found, has invalid YAML syntax,
                     is missing required fields, or contains invalid values.
                     The error message will indicate the specific problem.
    
    Behavior:
        1. Locate config file (explicit path or CWD/config.yaml)
        2. Read and parse YAML content
        3. Validate structure (required sections exist)
        4. Validate and extract spotify credentials
        5. Validate and expand output directory path
        6. Validate download settings with defaults
        7. Create and return frozen Config object
    
    Example:
        try:
            config = load_config()
        except ConfigError as e:
            print(f"Configuration error: {e.message}")
            sys.exit(1)
    
    Thread Safety:
        This function is NOT thread-safe. It should be called once at
        application startup, before any threads are created.
    """
    # Implementation will:
    # 1. Resolve config_path to CONFIG_FILENAME in CWD if None
    # 2. Check file exists, raise ConfigError if not
    # 3. Read file content with proper encoding (UTF-8)
    # 4. Parse YAML with yaml.safe_load(), catch yaml.YAMLError
    # 5. Call _validate_config() to check structure and values
    # 6. Build and return Config object
    raise NotImplementedError("Contract only - implementation pending")


def _validate_config(raw_config: dict[str, Any]) -> None:
    """
    Validate the raw configuration dictionary structure and values.
    
    This is an internal helper function that checks the configuration
    has all required sections and valid values.
    
    Args:
        raw_config: Dictionary parsed from config.yaml.
    
    Raises:
        ConfigError: If validation fails, with a descriptive message
                     indicating what is missing or invalid.
    
    Validation Rules:
        - 'spotify' section must exist
        - 'spotify.client_id' must be a non-empty string
        - 'spotify.client_secret' must be a non-empty string
        - 'output' section must exist
        - 'output.directory' must be a non-empty string
        - 'download' section is optional (defaults applied)
        - 'download.threads' if present must be integer >= 1
        - 'download.cookie_file' if present must be string or null
    """
    raise NotImplementedError("Contract only - implementation pending")


def _parse_spotify_config(spotify_section: dict[str, Any]) -> SpotifyConfig:
    """
    Parse and validate the spotify configuration section.
    
    Args:
        spotify_section: The 'spotify' section from config.yaml.
    
    Returns:
        SpotifyConfig: Validated Spotify credentials.
    
    Raises:
        ConfigError: If client_id or client_secret is missing or empty.
    """
    raise NotImplementedError("Contract only - implementation pending")


def _parse_output_config(output_section: dict[str, Any]) -> OutputConfig:
    """
    Parse and validate the output configuration section.
    
    Expands ~ to home directory and converts to absolute Path.
    Does NOT create the directory (that happens at download time).
    
    Args:
        output_section: The 'output' section from config.yaml.
    
    Returns:
        OutputConfig: Validated output configuration with expanded path.
    
    Raises:
        ConfigError: If directory is missing or empty.
    """
    raise NotImplementedError("Contract only - implementation pending")


def _parse_download_config(download_section: dict[str, Any] | None) -> DownloadConfig:
    """
    Parse and validate the download configuration section.
    
    Applies defaults if section is missing or fields are not specified.
    
    Args:
        download_section: The 'download' section from config.yaml, or None.
    
    Returns:
        DownloadConfig: Validated download configuration with defaults applied.
                        Default threads: 4
                        Default cookie_file: None
    
    Raises:
        ConfigError: If threads is not a positive integer, or if
                     cookie_file path doesn't exist when specified.
    """
    raise NotImplementedError("Contract only - implementation pending")
