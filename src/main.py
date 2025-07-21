"""
Main CLI interface for Playlist-Downloader

This module provides the comprehensive command-line interface for all functionality
including playlist synchronization, configuration management, authentication setup,
and system diagnostics. It serves as the primary entry point for user interactions
with the application.

The CLI is built using Click framework and provides structured command groups for:
- Playlist operations (download, update, list, download-liked, update-liked)
- Authentication handling (login, logout, status)
- Lyrics management (download, sources validation)
- Configuration management (show, set, reset)
- System diagnostics (doctor, status validation)
"""

import sys
import click
import functools
from pathlib import Path

# Import application modules for core functionality
from .config.settings import get_settings, reload_settings
from .config.auth import get_auth, reset_auth
from .spotify.client import get_spotify_client
from .spotify.models import TrackStatus
from .sync.synchronizer import get_synchronizer
from .lyrics.processor import get_lyrics_processor
from .utils.logger import configure_from_settings, get_logger, get_current_log_file
from .utils.helpers import format_duration
from .utils.validation import (
    validate_spotify_url, 
    validate_output_directory,
    validate_audio_format,
    validate_quality_setting
)


# Initialize logging system from configuration settings
configure_from_settings()
logger = get_logger(__name__)


def print_banner():
    """
    Print application banner to console
    
    Displays a styled ASCII art banner with application title and brief description.
    Used to provide visual identity and context when the application starts.
    """
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                      Playlist-Downloader                     ║
║                                                               ║
║  Download Spotify playlists with YouTube Music + Lyrics      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """
    click.echo(click.style(banner, fg='green', bold=True))


def handle_error(func):
    """
    Decorator to handle common CLI errors gracefully
    
    Wraps CLI command functions to provide consistent error handling across
    all commands. Catches common exceptions and provides user-friendly error
    messages while ensuring proper logging and exit codes.
    
    Args:
        func: The CLI command function to wrap
        
    Returns:
        Wrapped function with error handling
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            # Handle user cancellation gracefully
            click.echo(click.style("\n\nOperation cancelled by user", fg='yellow'))
            sys.exit(130)  # Standard exit code for SIGINT
        except Exception as e:
            # Log error for debugging and show user-friendly message
            logger.error(f"Command failed: {e}")
            click.echo(click.style(f"Error: {e}", fg='red'), err=True)
            sys.exit(1)  # Standard exit code for general errors
    return wrapper


# Main CLI group - root command that all subcommands attach to
@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--config', type=click.Path(), help='Path to config file')
@click.pass_context
def cli(ctx, version, verbose, config):
    """
    Playlist-Downloader - Download Spotify playlists with lyrics
    
    A powerful tool to download Spotify playlists locally using YouTube Music,
    with automatic lyrics integration and intelligent update capabilities.
    
    This is the main entry point that handles global options and coordinates
    subcommand execution. When invoked without subcommands, it shows the banner
    and basic usage information.
    """
    # Ensure Click context exists for subcommands
    ctx.ensure_object(dict)
    
    # Handle version information display
    if version:
        click.echo("Playlist-Downloader v1.0.0")
        return
    
    # Handle custom config file loading
    if config:
        reload_settings(config)
        click.echo(f"Loaded config: {config}")
    
    # Enable verbose logging if requested
    if verbose:
        ctx.obj['verbose'] = True
        logger.info("Verbose mode enabled")
    
    # If no subcommand provided, show banner and help
    if ctx.invoked_subcommand is None:
        print_banner()
        click.echo(ctx.get_help())


# Main download commands - primary functionality for playlist downloading
@cli.command()
@click.argument('playlist_url')
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--format', type=click.Choice(['mp3', 'flac', 'm4a']), help='Audio format')
@click.option('--quality', type=click.Choice(['low', 'medium', 'high']), help='Audio quality')
@click.option('--no-lyrics', is_flag=True, help='Skip lyrics download')
@click.option('--lyrics-source', type=click.Choice(['genius']), help='Lyrics source')
@click.option('--concurrent', '-c', type=int, help='Concurrent downloads')
@click.option('--dry-run', is_flag=True, help='Show what would be downloaded without downloading')
@handle_error
def download(playlist_url, output, format, quality, no_lyrics, lyrics_source, concurrent, dry_run):
    """
    Download a Spotify playlist
    
    Downloads or creates a new local copy of a Spotify playlist using YouTube Music
    as the audio source. Supports various audio formats and quality levels with
    optional lyrics integration from multiple sources.
    
    Args:
        playlist_url: Spotify playlist URL or ID to download
        output: Custom output directory (overrides config)
        format: Audio format override (mp3, flac, m4a)
        quality: Audio quality override (low, medium, high)
        no_lyrics: Skip lyrics download for faster processing
        lyrics_source: Preferred lyrics source (genius)
        concurrent: Number of parallel downloads (1-10)
        dry_run: Preview operations without actually downloading
    """
    # Validate the Spotify URL/ID format
    is_valid, error_msg = validate_spotify_url(playlist_url)
    if not is_valid:
        click.echo(click.style(f"Invalid playlist URL: {error_msg}", fg='red'), err=True)
        sys.exit(1)
    
    # Validate concurrent downloads parameter
    if concurrent and (concurrent < 1 or concurrent > 10):
        click.echo(click.style("Concurrent downloads must be between 1 and 10", fg='red'), err=True)
        sys.exit(1)
    
    # Validate output directory if provided
    if output:
        is_valid, error_msg = validate_output_directory(output)
        if not is_valid:
            click.echo(click.style(f"Invalid output directory: {error_msg}", fg='red'), err=True)
            sys.exit(1)
    
    # Display dry run notice if enabled
    if dry_run:
        click.echo("Dry run mode - showing what would be downloaded...")
    
    # Load current settings and apply command-line overrides
    settings = get_settings()
    
    # Apply setting overrides from command line
    if output:
        settings.download.output_directory = output
    if format:
        validate_audio_format(format)
        settings.download.format = format
        # Force reload of downloader with new format
        from .ytmusic.downloader import reset_downloader
        reset_downloader()
    if quality:
        validate_quality_setting(quality)
        settings.download.quality = quality
    if no_lyrics:
        settings.lyrics.enabled = False
    if lyrics_source:
        settings.lyrics.primary_source = lyrics_source
    if concurrent:
        settings.download.concurrency = concurrent
    
    # Initialize synchronizer with current settings
    synchronizer = get_synchronizer()
    
    # Get playlist information and create sync plan
    with click.progressbar(length=100, label='Analyzing playlist') as bar:
        try:
            sync_plan = synchronizer.create_sync_plan(playlist_url, force_full=False)
            bar.update(100)
        except Exception as e:
            click.echo(click.style(f"Failed to analyze playlist: {e}", fg='red'), err=True)
            sys.exit(1)
    
    # Check if playlist already exists and is up to date
    if not sync_plan.has_changes:
        click.echo("Playlist is already up to date!")
        return
    
    # Display playlist information and planned operations
    logger.console_info(f"Playlist: {sync_plan.playlist_name} ({sync_plan.estimated_downloads} tracks to download)")
    
    if dry_run:
        # Show detailed operation preview without executing
        click.echo("\nOperations that would be performed:")
        for i, operation in enumerate(sync_plan.operations, 1):
            if operation.track:
                click.echo(f"   {i}. Download: {operation.track.spotify_track.primary_artist} - {operation.track.spotify_track.name}")
            else:
                click.echo(f"   {i}. {operation.operation_type}: {operation.reason}")
        return
    
    # Confirm with user before proceeding
    if not click.confirm(f"\nProceed with downloading {sync_plan.estimated_downloads} tracks?"):
        click.echo("Download cancelled")
        return
    
    # Determine local directory for playlist
    spotify_client = get_spotify_client()
    playlist_id = spotify_client.extract_playlist_id(playlist_url)
    playlist = spotify_client.get_full_playlist(playlist_id)
    
    local_directory = settings.get_output_directory() / playlist.name
    local_directory.mkdir(parents=True, exist_ok=True)
    
    # Execute the sync plan
    result = synchronizer.execute_sync_plan(sync_plan, local_directory)
    
    # Display results summary
    if result.downloads_failed > 0:
        logger.console_info(f" {result.downloads_completed} downloaded, {result.downloads_failed} failed")
    else:
        logger.console_info(f" {result.downloads_completed} tracks downloaded")
        
    # Show lyrics results if enabled
    if settings.lyrics.enabled:
        click.echo(f"   Lyrics: {result.lyrics_completed}")
        click.echo(f"   Lyrics failed: {result.lyrics_failed}")
    
    # Show total time if available
    if result.total_time:
        click.echo(f"   Total time: {format_duration(result.total_time)}")
    
    click.echo(f"\nFiles saved to: {local_directory}")
    
    # Force flush output streams for immediate display
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except ValueError:
        # Ignore if streams are closed
        pass


@cli.command()
@click.argument('playlist_url')
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@handle_error
def update(playlist_url, output):
    """
    Update an existing playlist
    
    Updates a previously downloaded playlist by fetching only new or changed tracks
    from Spotify. Performs incremental synchronization to avoid re-downloading
    existing content while ensuring the local copy stays current.
    
    Args:
        playlist_url: Spotify playlist URL or ID to update
        output: Custom output directory (overrides detected location)
    """
    click.echo(f"Updating playlist: {playlist_url}")
    
    # Initialize synchronizer
    synchronizer = get_synchronizer()
    
    # Check current status of the playlist
    with click.progressbar(length=100, label='Checking playlist status') as bar:
        status = synchronizer.check_playlist_status(playlist_url)
        bar.update(100)
    
    # Handle status check errors
    if 'error' in status:
        click.echo(f"Error: {status['error']}")
        return
    
    # Display current playlist status
    click.echo(f"\nPlaylist Status:")
    click.echo(f"   Name: {status['playlist_name']}")
    click.echo(f"   Total tracks: {status['total_tracks']}")
    click.echo(f"   Local directory: {status['local_directory']}")
    click.echo(f"   Status: {status['sync_summary']}")
    
    # Check if update is actually needed
    if not status['needs_sync']:
        click.echo("Playlist is already up to date!")
        return
    
    # Determine local directory (use override if provided)
    local_directory = Path(status['local_directory'])
    if output:
        local_directory = Path(output)
        local_directory.mkdir(parents=True, exist_ok=True)
    
    # Create and execute update plan
    sync_plan = synchronizer.create_sync_plan(playlist_url, local_directory)
    
    # Confirm update with user
    if not click.confirm(f"\nProceed with update ({sync_plan.estimated_downloads} downloads)?"):
        click.echo("Update cancelled")
        return
    
    # Execute the update
    click.echo("\nStarting update...")
    result = synchronizer.execute_sync_plan(sync_plan, local_directory)
    
    # Display update results
    click.echo(f"\nUpdate Results: {result.summary}")


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--format', type=click.Choice(['mp3', 'flac', 'm4a']), help='Audio format')
@click.option('--quality', type=click.Choice(['low', 'medium', 'high']), help='Audio quality')
@click.option('--no-lyrics', is_flag=True, help='Skip lyrics download')
@click.option('--concurrent', '-c', type=int, help='Concurrent downloads')
@click.option('--dry-run', is_flag=True, help='Show what would be downloaded without downloading')
@handle_error
def download_liked(output, format, quality, no_lyrics, concurrent, dry_run):
    """
    Download your Spotify liked songs
    
    Downloads all songs from your Spotify "Liked Songs" collection into a 
    local "My Liked Songs" folder. Treats liked songs as a virtual playlist
    for consistent management and update capabilities.
    
    Args:
        output: Custom output directory (overrides config)
        format: Audio format override (mp3, flac, m4a)
        quality: Audio quality override (low, medium, high)
        no_lyrics: Skip lyrics download for faster processing
        concurrent: Number of parallel downloads (1-10)
        dry_run: Preview operations without actually downloading
    """
    # Validate concurrent downloads parameter
    if concurrent and (concurrent < 1 or concurrent > 10):
        click.echo(click.style("Concurrent downloads must be between 1 and 10", fg='red'), err=True)
        sys.exit(1)
    
    # Display dry run notice if enabled
    if dry_run:
        click.echo("Dry run mode - showing what would be downloaded...")
    
    # Initialize components
    settings = get_settings()
    spotify_client = get_spotify_client()
    synchronizer = get_synchronizer()
    
    # Override settings if options provided
    if output:
        settings.download.output_directory = output
    if format:
        settings.download.format = format
        # Force reload of downloader with new format
        from .ytmusic.downloader import reset_downloader
        reset_downloader()
    if quality:
        settings.download.quality = quality
    if no_lyrics:
        settings.lyrics.enabled = False
    if concurrent:
        settings.download.concurrency = concurrent
    
    # Get liked songs as virtual playlist
    with click.progressbar(length=100, label='Fetching liked songs') as bar:
        try:
            virtual_playlist = spotify_client.get_user_saved_tracks()
            bar.update(100)
        except Exception as e:
            click.echo(click.style(f"Failed to fetch liked songs: {e}", fg='red'), err=True)
            sys.exit(1)
    
    # Check if user has any liked songs
    if not virtual_playlist.tracks:
        click.echo("No liked songs found!")
        return
    
    # Find or create local directory for liked songs
    local_directory = synchronizer._find_liked_songs_directory()
    
    # Create sync plan using virtual playlist
    with click.progressbar(length=100, label='Analyzing liked songs') as bar:
        sync_plan = synchronizer._create_liked_songs_sync_plan(virtual_playlist, local_directory)
        bar.update(100)
    
    # Check if all songs are already downloaded
    if not sync_plan.has_changes:
        click.echo("All liked songs are already downloaded!")
        return
    
    # Display information about planned download
    logger.console_info(f"My Liked Songs ({sync_plan.estimated_downloads} tracks to download)")
    
    if dry_run:
        # Show detailed operation preview without executing
        click.echo("\nOperations that would be performed:")
        for i, operation in enumerate(sync_plan.operations, 1):
            if operation.track:
                click.echo(f"   {i}. Download: {operation.track.spotify_track.primary_artist} - {operation.track.spotify_track.name}")
            else:
                click.echo(f"   {i}. {operation.operation_type}: {operation.reason}")
        return
    
    # Confirm with user before proceeding
    if not click.confirm(f"\nProceed with downloading {sync_plan.estimated_downloads} liked songs?"):
        click.echo("Download cancelled")
        return
    
    # Execute sync plan for liked songs
    result = synchronizer.execute_liked_songs_sync(virtual_playlist, local_directory)
    
    # Display results summary
    if result.downloads_failed > 0:
        logger.console_info(f" {result.downloads_completed} downloaded, {result.downloads_failed} failed")
    else:
        logger.console_info(f" {result.downloads_completed} tracks downloaded")
        
    # Show lyrics results if enabled
    if settings.lyrics.enabled:
        click.echo(f"   Lyrics: {result.lyrics_completed}")
        click.echo(f"   Lyrics failed: {result.lyrics_failed}")
    
    # Show total time if available
    if result.total_time:
        click.echo(f"   Total time: {format_duration(result.total_time)}")
    
    click.echo(f"\nFiles saved to: {local_directory}")


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@handle_error
def update_liked(output):
    """
    Update your Spotify liked songs
    
    Updates your local "My Liked Songs" collection by downloading only newly
    liked tracks since the last update. Performs incremental synchronization
    to keep your local collection current with your Spotify liked songs.
    
    Args:
        output: Custom output directory (overrides detected location)
    """
    click.echo("Updating liked songs...")
    
    # Initialize components
    settings = get_settings()
    spotify_client = get_spotify_client()
    synchronizer = get_synchronizer()
    
    # Override output directory if provided
    if output:
        settings.download.output_directory = output
    
    # Check current status of liked songs
    with click.progressbar(length=100, label='Checking liked songs status') as bar:
        try:
            # Get current liked songs from Spotify
            virtual_playlist = spotify_client.get_user_saved_tracks()
            bar.update(50)
            
            # Find local directory for liked songs
            local_directory = synchronizer._find_liked_songs_directory()
            
            # Check if update is needed
            sync_plan = synchronizer._create_liked_songs_sync_plan(virtual_playlist, local_directory)
            bar.update(100)
            
        except Exception as e:
            click.echo(f"Error checking status: {e}")
            return
    
    # Show current status information
    click.echo(f"\nLiked Songs Status:")
    click.echo(f"   Collection: My Liked Songs")
    click.echo(f"   Total tracks: {len(virtual_playlist.tracks)}")
    click.echo(f"   Local directory: {local_directory}")
    
    # Check if tracklist file exists
    tracklist_path = local_directory / "tracklist.txt"
    click.echo(f"   Tracklist exists: {'Yes' if tracklist_path.exists() else 'No'}")
    
    # Check if update is needed
    if not sync_plan.has_changes:
        click.echo("Liked songs are already up to date!")
        return
    
    # Show what needs to be updated
    click.echo(f"   Needs Update: Yes")
    click.echo(f"   Downloads needed: {sync_plan.estimated_downloads}")
    
    # Confirm update with user
    if not click.confirm(f"\nProceed with update ({sync_plan.estimated_downloads} downloads)?"):
        click.echo("Update cancelled")
        return
    
    # Execute the update
    click.echo("\nStarting update...")
    result = synchronizer.execute_liked_songs_sync(virtual_playlist, local_directory)
    
    # Display update results
    click.echo(f"\nUpdate Results: {result.summary}")
    
    if result.success:
        if result.downloads_completed > 0:
            click.echo(f"   Downloaded: {result.downloads_completed}")
        if result.downloads_failed > 0:
            click.echo(f"   Failed: {result.downloads_failed}")
        if settings.lyrics.enabled:
            if result.lyrics_completed > 0:
                click.echo(f"   Lyrics: {result.lyrics_completed}")
            if result.lyrics_failed > 0:
                click.echo(f"   Lyrics failed: {result.lyrics_failed}")
        if result.total_time:
            click.echo(f"   Duration: {format_duration(result.total_time)}")
        
        click.echo(f"\nFiles saved to: {local_directory}")
    else:
        click.echo(f"Update failed: {result.error_message}")


@cli.command()
@click.option('--show-lyrics', is_flag=True, help='Show lyrics status')
@handle_error
def list(show_lyrics):
    """
    List local playlists
    
    Displays all locally downloaded playlists with their current status including
    track counts, download progress, and optional lyrics information. Provides
    an overview of your local music collection.
    
    Args:
        show_lyrics: Include lyrics status information in the display
    """
    # Get current settings and output directory
    settings = get_settings()
    output_dir = settings.get_output_directory()
    
    # Check if output directory exists
    if not output_dir.exists():
        click.echo("No playlists found (output directory doesn't exist)")
        return
    
    # Find all tracklist files in the output directory
    from .sync.tracker import get_tracklist_manager
    
    tracklist_manager = get_tracklist_manager()
    tracklist_files = tracklist_manager.find_tracklist_files(output_dir)
    
    # Check if any playlists were found
    if not tracklist_files:
        click.echo("No playlists found")
        return
    
    # Display header with count
    click.echo(f"Found {len(tracklist_files)} playlists:\n")
    
    # Process each playlist and display information
    for tracklist_path in tracklist_files:
        try:
            # Read tracklist metadata and entries
            metadata, entries = tracklist_manager.read_tracklist_file(tracklist_path)
            
            # Calculate download statistics
            total_tracks = len(entries)
            downloaded = len([e for e in entries if e.audio_status.value == 'downloaded'])
            download_percent = (downloaded / total_tracks * 100) if total_tracks > 0 else 0
            
            # Calculate lyrics statistics if requested
            lyrics_downloaded = 0
            lyrics_percent = 0
            if show_lyrics and metadata.lyrics_enabled:
                lyrics_downloaded = len([e for e in entries if e.lyrics_status.value == 'downloaded'])
                lyrics_percent = (lyrics_downloaded / total_tracks * 100) if total_tracks > 0 else 0
            
            # Display playlist information
            click.echo(f" {metadata.playlist_name}")
            click.echo(f"   {tracklist_path.parent}")
            click.echo(f"   {downloaded}/{total_tracks} tracks ({download_percent:.1f}%)")
            
            # Show lyrics info if requested and enabled
            if show_lyrics and metadata.lyrics_enabled:
                click.echo(f"   {lyrics_downloaded}/{total_tracks} lyrics ({lyrics_percent:.1f}%)")
            
            # Show last modified date
            click.echo(f"   Last modified: {metadata.last_modified}")
            click.echo()
            
        except Exception as e:
            click.echo(f"Error reading {tracklist_path}: {e}")


# Authentication commands group
@cli.group()
def auth():
    """
    Authentication management
    
    Command group for managing API authentication including setup, renewal,
    and reset operations for Spotify and other service authentications.
    """
    pass


@auth.command()
@handle_error
def login():
    """
    Authenticate with Spotify
    
    Initiates the OAuth flow for Spotify API authentication. Opens web browser
    for user authorization and stores resulting tokens securely for future use.
    Will check if already authenticated before starting new flow.
    """
    click.echo("Starting Spotify authentication...")
    
    # Get authentication manager
    auth_manager = get_auth()
    
    # Check if already authenticated
    if auth_manager.is_authenticated():
        user_info = auth_manager.get_user_info()
        username = user_info.get('display_name', user_info.get('id', 'Unknown')) if user_info else 'Unknown'
        click.echo(f"Already authenticated as: {username}")
        return
    
    # Attempt authentication
    try:
        token = auth_manager.get_valid_token()
        
        if token:
            # Authentication successful, get user info
            user_info = auth_manager.get_user_info()
            username = user_info.get('display_name', user_info.get('id', 'Unknown')) if user_info else 'Unknown'
            click.echo(f"Successfully authenticated as: {username}")
        else:
            click.echo("Authentication failed")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Authentication error: {e}")
        sys.exit(1)


@auth.command()
@handle_error
def logout():
    """
    Remove stored authentication
    
    Clears all stored authentication tokens and credentials. Useful for
    troubleshooting authentication issues or switching accounts. User will
    need to re-authenticate before using the application again.
    """
    click.echo("Removing stored authentication...")
    
    # Get authentication manager and revoke tokens
    auth_manager = get_auth()
    auth_manager.revoke_token()
    reset_auth()
    
    click.echo("Successfully logged out")


@auth.command()
@handle_error
def status():
    """
    Check authentication status
    
    Displays current authentication status including token validity,
    expiration times, and associated user information. Provides detailed
    information about the current authentication state.
    """
    # Get authentication manager
    auth_manager = get_auth()
    
    # Check and display authentication status
    if auth_manager.is_authenticated():
        user_info = auth_manager.get_user_info()
        if user_info:
            click.echo("Authentication Status: Authenticated")
            click.echo(f"   User: {user_info.get('display_name', user_info.get('id', 'Unknown'))}")
            click.echo(f"   Country: {user_info.get('country', 'Unknown')}")
            click.echo(f"   Followers: {user_info.get('followers', {}).get('total', 'Unknown')}")
        else:
            click.echo("Authentication Status: Authenticated (limited info)")
    else:
        click.echo("Authentication Status: Not authenticated")
        click.echo("   Run 'playlist-dl auth login' to authenticate")


# Lyrics commands group
@cli.group()
def lyrics():
    """
    Lyrics management
    
    Command group for managing lyrics operations including downloading lyrics
    for existing playlists and validating lyrics source availability.
    """
    pass


@lyrics.command()
@click.argument('playlist_url')
@click.option('--source', type=click.Choice(['genius']), help='Lyrics source')
@handle_error
def download_lyrics(playlist_url, source):
    """
    Download lyrics for existing playlist
    
    Downloads lyrics for tracks in an already downloaded playlist. Useful for
    adding lyrics to playlists that were downloaded without lyrics, or for
    updating lyrics with a different source.
    
    Args:
        playlist_url: Spotify playlist URL or ID
        source: Preferred lyrics source (genius)
    """
    click.echo(f"Downloading lyrics for: {playlist_url}")
    
    # Find playlist directory using synchronizer
    synchronizer = get_synchronizer()
    status = synchronizer.check_playlist_status(playlist_url)
    
    # Check for errors in playlist status
    if 'error' in status:
        click.echo(f"Error: {status['error']}")
        return
    
    # Verify local directory and tracklist exist
    local_directory = Path(status['local_directory'])
    tracklist_path = local_directory / "tracklist.txt"
    
    if not tracklist_path.exists():
        click.echo("Playlist not found locally. Download playlist first.")
        return
    
    # Read existing tracklist
    from .sync.tracker import get_tracklist_manager
    tracklist_manager = get_tracklist_manager()
    metadata, entries = tracklist_manager.read_tracklist_file(tracklist_path)
    
    # Find tracks that need lyrics
    lyrics_processor = get_lyrics_processor()
    tracks_needing_lyrics = [e for e in entries if e.lyrics_status.value != 'downloaded']
    
    if not tracks_needing_lyrics:
        click.echo("All tracks already have lyrics!")
        return
    
    click.echo(f"Downloading lyrics for {len(tracks_needing_lyrics)} tracks...")
    
    # Download lyrics for each track that needs them
    completed = 0
    failed = 0
    
    with click.progressbar(tracks_needing_lyrics, label='Downloading lyrics') as bar:
        for entry in bar:
            try:
                # Override source if specified by user
                preferred_source = None
                if source:
                    from .spotify.models import LyricsSource
                    preferred_source = LyricsSource(source)
                
                # Search for lyrics using the lyrics processor
                lyrics_result = lyrics_processor.search_lyrics(
                    entry.artist,
                    entry.title,
                    preferred_source=preferred_source
                )
                
                if lyrics_result.success:
                    # Save lyrics files to local directory
                    lyrics_result = lyrics_processor.save_lyrics_files(
                        lyrics_result,
                        entry.artist,
                        entry.title,
                        local_directory,
                        entry.position
                    )
                    completed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Failed to download lyrics for {entry.artist} - {entry.title}: {e}")
                failed += 1
    
    # Display lyrics download results
    click.echo(f"\nLyrics Results:")
    click.echo(f"   Completed: {completed}")
    click.echo(f"   Failed: {failed}")


@lyrics.command()
@handle_error
def sources():
    """
    Check lyrics sources status
    
    Performs validation of all configured lyrics sources to check their
    availability and configuration status. Useful for troubleshooting
    lyrics-related issues and confirming API key setup.
    """
    click.echo("Checking lyrics sources...")
    
    # Get lyrics processor and validate sources
    lyrics_processor = get_lyrics_processor()
    source_status = lyrics_processor.validate_lyrics_sources()
    
    click.echo("\nLyrics Sources Status:")
    
    # Display status for each configured source
    for source, available in source_status.items():
        # Visual indicator for availability
        status_icon = "[OK]" if available else "[FAIL]"
        status_text = "Available" if available else "Unavailable"
        click.echo(f"   {status_icon} {source.value}: {status_text}")


# Configuration commands group
@cli.group()
def config():
    """
    Configuration management
    
    Command group for viewing and modifying application configuration including
    download settings, audio preferences, lyrics options, and output paths.
    """
    pass


@config.command()
@handle_error
def show():
    """
    Show current configuration
    
    Displays all current configuration settings in a structured format.
    Includes download preferences, audio settings, lyrics configuration,
    and directory paths for user review.
    """
    # Get current settings
    settings = get_settings()
    
    click.echo("Current Configuration:\n")
    
    # Download settings section
    click.echo("Download:")
    click.echo(f"   Output directory: {settings.download.output_directory}")
    click.echo(f"   Format: {settings.download.format}")
    click.echo(f"   Quality: {settings.download.quality}")
    click.echo(f"   Concurrent downloads: {settings.download.concurrency}")
    
    # Lyrics settings section
    click.echo("\nLyrics:")
    click.echo(f"   Enabled: {settings.lyrics.enabled}")
    click.echo(f"   Primary source: {settings.lyrics.primary_source}")
    click.echo(f"   Fallback sources: {', '.join(settings.lyrics.fallback_sources)}")
    click.echo(f"   Format: {settings.lyrics.format}")
    click.echo(f"   Embed in audio: {settings.lyrics.embed_in_audio}")
    
    # Audio processing settings section
    click.echo("\nAudio:")
    click.echo(f"   Trim silence: {settings.audio.trim_silence}")
    click.echo(f"   Normalize: {settings.audio.normalize}")
    click.echo(f"   Sample rate: {settings.audio.sample_rate}Hz")


@config.command()
@click.option('--format', type=click.Choice(['mp3', 'flac', 'm4a']), help='Set audio format')
@click.option('--quality', type=click.Choice(['low', 'medium', 'high']), help='Set audio quality')
@click.option('--output', type=click.Path(), help='Set output directory')
@click.option('--lyrics-source', type=click.Choice(['genius']), help='Set primary lyrics source')
@handle_error
def set(format, quality, output, lyrics_source):
    """
    Update configuration settings
    
    Allows modification of key configuration parameters through command line.
    Changes are applied immediately and persist across application restarts.
    
    Args:
        format: Audio format for downloads (mp3, flac, m4a)
        quality: Audio quality level (low, medium, high)  
        output: Output directory path for downloads
        lyrics_source: Primary lyrics source service
    """
    # Get current settings
    settings = get_settings()
    changes = []
    
    # Apply format change if specified
    if format:
        settings.download.format = format
        if format == 'flac':
            click.echo(click.style("FLAC converts from compressed AAC (not true lossless). Consider m4a for best quality.", fg='yellow'))
        changes.append(f"Audio format: {format}")
    
    # Apply quality change if specified
    if quality:
        settings.download.quality = quality
        changes.append(f"Audio quality: {quality}")
    
    # Apply output directory change if specified
    if output:
        settings.download.output_directory = output
        changes.append(f"Output directory: {output}")
    
    # Apply lyrics source change if specified
    if lyrics_source:
        settings.lyrics.primary_source = lyrics_source
        changes.append(f"Lyrics source: {lyrics_source}")
    
    # Save changes and provide feedback
    if changes:
        settings.save_config()
        click.echo("Configuration updated:")
        for change in changes:
            click.echo(f"   • {change}")
    else:
        click.echo("No changes specified")


# System diagnostic commands
@cli.command()
@handle_error
def doctor():
    """
    Run system diagnostics
    
    Performs comprehensive system checks including API connectivity,
    authentication status, configuration validation, and dependency verification.
    Useful for troubleshooting setup and configuration issues.
    """
    click.echo("Running diagnostics...\n")
    
    # List to collect any issues found during diagnostics
    issues = []
    
    # Check authentication status
    auth_manager = get_auth()
    if auth_manager.is_authenticated():
        click.echo("Spotify authentication: OK")
    else:
        click.echo("Spotify authentication: Not authenticated")
        issues.append("Run 'playlist-dl auth login' to authenticate")
    
    # Check YouTube Music API functionality
    try:
        from .ytmusic.searcher import get_ytmusic_searcher
        searcher = get_ytmusic_searcher()
        if searcher.validate_search_config():
            click.echo("YouTube Music API: OK")
        else:
            click.echo("YouTube Music API: Failed")
            issues.append("YouTube Music API validation failed")
    except Exception as e:
        click.echo(f"YouTube Music API: Error - {e}")
        issues.append("YouTube Music API initialization failed")
    
    # Check lyrics sources availability
    try:
        lyrics_processor = get_lyrics_processor()
        source_status = lyrics_processor.validate_lyrics_sources()
        
        # Count available sources
        available_sources = [source.value for source, available in source_status.items() if available]
        if available_sources:
            click.echo(f"Lyrics sources: {', '.join(available_sources)}")
        else:
            click.echo("Lyrics sources: None available")
            issues.append("No lyrics sources are configured")
    except Exception as e:
        click.echo(f"Lyrics sources: Error - {e}")
        issues.append("Lyrics system initialization failed")
    
    # Check critical dependencies
    dependencies = [
        ('yt_dlp', 'yt-dlp', 'required for downloading'),
        ('mutagen', 'mutagen', 'required for metadata handling'),
    ]
    
    for module_name, display_name, purpose in dependencies:
        try:
            __import__(module_name)
            click.echo(f"{display_name}: OK")
        except ImportError:
            click.echo(f"{display_name}: Not installed")
            issues.append(f"{display_name} is {purpose}")
    
    # Check output directory accessibility
    settings = get_settings()
    output_dir = settings.get_output_directory()
    
    if output_dir.exists() and output_dir.is_dir():
        click.echo(f"Output directory: {output_dir}")
    else:
        click.echo(f"Output directory: {output_dir} (will be created)")

    # Check current logging configuration
    current_log = get_current_log_file()
    if current_log:
        click.echo(f"Logging: {current_log}")
    else:
        click.echo("Logging: Console only (will switch to playlist-specific when syncing)")
    
    # Display summary of any issues found
    if issues:
        click.echo(f"\nFound {len(issues)} issues:")
        for issue in issues:
            click.echo(f"   • {issue}")
    else:
        click.echo("\nAll systems operational!")


# Entry point for module execution
if __name__ == '__main__':
    cli()