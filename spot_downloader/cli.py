"""
Command-line interface for spot-downloader.

This module implements the CLI using Click, providing all commands
for downloading Spotify playlists via YouTube Music.

Commands:
    spot --dl --url <playlist_url>      Download a playlist
    spot --dl --liked                   Download liked songs
    spot --dl --url <url> --sync        Sync mode (only new tracks)
    spot --dl --liked --sync            Sync liked songs
    spot --dl --1 --url <url>           Run only PHASE 1 (fetch metadata)
    spot --dl --2 --url <url>           Run only PHASE 2 (YouTube match)
    spot --dl --3 --url <url>           Run only PHASE 3 (download)

Options:
    --cookie-file <path>                Path to cookies.txt for YT Premium

Usage:
    # Download entire playlist
    spot --dl --url "https://open.spotify.com/playlist/..."
    
    # Sync mode (download only new tracks)
    spot --dl --url "https://open.spotify.com/playlist/..." --sync
    
    # Download liked songs
    spot --dl --liked
    
    # Run phases separately
    spot --dl --1 --url "https://..."   # Fetch Spotify metadata
    spot --dl --2 --url "https://..."   # Match on YouTube
    spot --dl --3 --url "https://..."   # Download and process

Configuration:
    The CLI requires a config.yaml file in the current directory with:
    - Spotify API credentials (client_id, client_secret)
    - Output directory path
    - Number of download threads
    - Optional cookie file path
"""

import sys
from pathlib import Path
from typing import Optional

import click

from spot_downloader.core import (
    Config,
    ConfigError,
    Database,
    DatabaseError,
    SpotDownloaderError,
    SpotifyError,
    get_logger,
    load_config,
    setup_logging,
    shutdown_logging,
)
from spot_downloader.core.database import LIKED_SONGS_KEY
from spot_downloader.download import download_tracks_phase3
from spot_downloader.spotify import (
    SpotifyClient,
    fetch_liked_songs_phase1,
    fetch_playlist_phase1,
)
from spot_downloader.utils import ensure_directory, extract_playlist_id
from spot_downloader.youtube import match_tracks_phase2

logger = get_logger(__name__)


# Version string
__version__ = "0.1.0"


@click.group(invoke_without_command=True)
@click.option(
    "--dl",
    is_flag=True,
    help="Download mode. Required for all download operations."
)
@click.option(
    "--url",
    type=str,
    default=None,
    help="Spotify playlist URL to download."
)
@click.option(
    "--liked",
    is_flag=True,
    help="Download user's Liked Songs instead of a playlist."
)
@click.option(
    "--sync",
    is_flag=True,
    help="Sync mode: only download new tracks not already in database."
)
@click.option(
    "--1", "phase1_only",
    is_flag=True,
    help="Run only PHASE 1: fetch Spotify metadata."
)
@click.option(
    "--2", "phase2_only",
    is_flag=True,
    help="Run only PHASE 2: match tracks on YouTube Music."
)
@click.option(
    "--3", "phase3_only",
    is_flag=True,
    help="Run only PHASE 3: download and process audio files."
)
@click.option(
    "--cookie-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to cookies.txt for YouTube Music Premium quality."
)
@click.option(
    "--version",
    is_flag=True,
    help="Show version and exit."
)
@click.pass_context
def cli(
    ctx: click.Context,
    dl: bool,
    url: Optional[str],
    liked: bool,
    sync: bool,
    phase1_only: bool,
    phase2_only: bool,
    phase3_only: bool,
    cookie_file: Optional[Path],
    user_auth: bool,
    version: bool
) -> None:
    """
    spot-downloader: Download Spotify playlists via YouTube Music.
    
    Downloads tracks from Spotify playlists by matching them on YouTube Music
    and downloading the audio in M4A format with full metadata.
    
    \b
    Examples:
        spot --dl --url "https://open.spotify.com/playlist/..."
        spot --dl --url "https://..." --sync
        spot --dl --liked
    """
    # Handle --version
    if version:
        click.echo(f"spot-downloader {__version__}")
        ctx.exit(0)
    
    # Validate options
    if not dl:
        # No --dl flag, show help
        click.echo(ctx.get_help())
        ctx.exit(0)
    
    # Must have either --url or --liked
    if not url and not liked:
        raise click.UsageError("Must specify either --url <playlist> or --liked")
    
    if url and liked:
        raise click.UsageError("Cannot use both --url and --liked")
    
    # Phase flags are mutually exclusive
    phase_flags = [phase1_only, phase2_only, phase3_only]
    if sum(phase_flags) > 1:
        raise click.UsageError("Only one phase flag (--1, --2, --3) can be used")
    
    # Determine which phases to run
    run_phase1 = not phase2_only and not phase3_only
    run_phase2 = not phase1_only and not phase3_only
    run_phase3 = not phase1_only and not phase2_only
    
    # Store in context for the command
    ctx.ensure_object(dict)
    ctx.obj["url"] = url
    ctx.obj["liked"] = liked
    ctx.obj["sync"] = sync
    ctx.obj["run_phase1"] = run_phase1
    ctx.obj["run_phase2"] = run_phase2
    ctx.obj["run_phase3"] = run_phase3
    ctx.obj["cookie_file"] = cookie_file
    ctx.obj["user_auth"] = liked  # True se --liked, False otherwise
    
    # Run the download
    _run_download(ctx.obj)


def _run_download(options: dict) -> None:
    """
    Execute the download workflow based on CLI options.
    
    This is the main orchestration function that:
    1. Loads configuration
    2. Sets up logging
    3. Initializes database and Spotify client
    4. Runs the appropriate phases
    5. Reports results
    
    Args:
        options: Dictionary with CLI options from click context.
    
    Raises:
        SystemExit: On fatal errors (with appropriate exit code).
    """
    config: Config | None = None
    database: Database | None = None
    
    try:
        # Load configuration
        config = _load_configuration()
        
        # Setup logging
        setup_logging(config.output.directory)
        logger.info("spot-downloader starting")
        
        # Ensure output directory exists
        ensure_directory(config.output.directory)
        
        # Initialize database
        database = _initialize_database(config.output.directory)
        
        # Initialize Spotify client
        _initialize_spotify(config, options["user_auth"])
        
        # Determine playlist ID
        if options["liked"]:
            playlist_id = LIKED_SONGS_KEY
        else:
            playlist_id = extract_playlist_id(options["url"])
        
        # Override cookie file from CLI if provided
        cookie_file = options["cookie_file"] or config.download.cookie_file
        
        # Run phases
        tracks = None
        
        if options["run_phase1"]:
            tracks = _run_phase1(
                database=database,
                url=options["url"],
                liked=options["liked"],
                sync=options["sync"]
            )
        
        if options["run_phase2"]:
            _run_phase2(
                database=database,
                playlist_id=playlist_id,
                tracks=tracks,
                num_threads=config.download.threads
            )
        
        if options["run_phase3"]:
            _run_phase3(
                database=database,
                playlist_id=playlist_id,
                output_dir=config.output.directory,
                cookie_file=cookie_file,
                num_threads=config.download.threads
            )
        
        # Final statistics
        _print_final_stats(database, playlist_id)
        
        logger.info("spot-downloader completed successfully")
        
    except ConfigError as e:
        click.echo(f"Configuration error: {e.message}", err=True)
        sys.exit(1)
        
    except DatabaseError as e:
        click.echo(f"Database error: {e.message}", err=True)
        logger.error(f"Database error: {e.message}", exc_info=True)
        sys.exit(2)
        
    except SpotifyError as e:
        click.echo(f"Spotify error: {e.message}", err=True)
        if e.is_auth_error:
            click.echo("Check your client_id and client_secret in config.yaml", err=True)
        logger.error(f"Spotify error: {e.message}", exc_info=True)
        sys.exit(3)
        
    except SpotDownloaderError as e:
        click.echo(f"Error: {e.message}", err=True)
        logger.error(f"Error: {e.message}", exc_info=True)
        sys.exit(4)
        
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        logger.info("Interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        logger.exception("Unexpected error")
        sys.exit(1)
        
    finally:
        shutdown_logging()


def _load_configuration() -> Config:
    """
    Load and validate configuration from config.yaml.
    
    Returns:
        Config object with validated settings.
    
    Raises:
        ConfigError: If configuration is invalid or missing.
    """
    raise NotImplementedError("Contract only - implementation pending")


def _initialize_database(output_dir: Path) -> Database:
    """
    Initialize the JSON database.
    
    Args:
        output_dir: Directory where database.json is stored.
    
    Returns:
        Database instance.
    
    Raises:
        DatabaseError: If database cannot be initialized.
    """
    raise NotImplementedError("Contract only - implementation pending")


def _initialize_spotify(config: Config, user_auth: bool) -> None:
    """
    Initialize the Spotify client singleton.
    
    Args:
        config: Configuration with Spotify credentials.
        user_auth: Whether to enable user authentication.
    
    Raises:
        SpotifyError: If authentication fails.
    """
    raise NotImplementedError("Contract only - implementation pending")


def _run_phase1(
    database: Database,
    url: str | None,
    liked: bool,
    sync: bool
) -> list:
    """
    Run PHASE 1: Fetch Spotify metadata.
    
    Args:
        database: Database instance.
        url: Playlist URL (None if using --liked).
        liked: Whether to fetch Liked Songs.
        sync: Whether to filter to new tracks only.
    
    Returns:
        List of Track objects to process.
    
    Behavior:
        1. Log phase start
        2. Call appropriate fetcher (playlist or liked songs)
        3. Log track counts
        4. Return tracks for next phase
    """
    raise NotImplementedError("Contract only - implementation pending")


def _run_phase2(
    database: Database,
    playlist_id: str,
    tracks: list | None,
    num_threads: int
) -> None:
    """
    Run PHASE 2: Match tracks on YouTube Music.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID for database queries.
        tracks: Tracks from PHASE 1 (None if running phase separately).
        num_threads: Number of parallel matching threads.
    
    Behavior:
        1. Log phase start
        2. Get tracks needing match from database (if tracks is None)
        3. Run matcher with threading
        4. Log match statistics
    """
    raise NotImplementedError("Contract only - implementation pending")


def _run_phase3(
    database: Database,
    playlist_id: str,
    output_dir: Path,
    cookie_file: Path | None,
    num_threads: int
) -> None:
    """
    Run PHASE 3: Download and process audio files.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID for database queries.
        output_dir: Directory for output files.
        cookie_file: Optional cookies.txt for YT Premium.
        num_threads: Number of parallel downloads.
    
    Behavior:
        1. Log phase start
        2. Get tracks needing download from database
        3. Run downloader with threading
        4. Log download statistics
    """
    raise NotImplementedError("Contract only - implementation pending")


def _print_final_stats(database: Database, playlist_id: str) -> None:
    """
    Print final download statistics.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID to get stats for.
    
    Output:
        Prints a summary table with:
        - Total tracks
        - Matched tracks
        - Downloaded tracks
        - Failed tracks
    """
    raise NotImplementedError("Contract only - implementation pending")


def main() -> None:
    """
    Entry point for the CLI.
    
    This function is called when running `spot` from the command line.
    It invokes the Click CLI group.
    """
    cli()


if __name__ == "__main__":
    main()
