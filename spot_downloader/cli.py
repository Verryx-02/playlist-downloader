"""
Command-line interface for spot-downloader.

This module implements the CLI using Click, providing all commands
for downloading Spotify playlists via YouTube Music.
rich-click is used for the output colors.

Commands:
    spot --url <playlist_url>           Download a playlist (all phases)
    spot --liked                        Download liked songs (all phases)
    spot --url <url> --sync             Sync mode (only new tracks)
    spot --1 --url <url>                Run only PHASE 1 (fetch metadata)
    spot --2                            Run only PHASE 2 (YouTube match)
    spot --3                            Run only PHASE 3 (download audio)
    spot --4                            Run only PHASE 4 (fetch lyrics)
    spot --5                            Run only PHASE 5 (embed metadata)
    spot --replace <file> <youtube_url> Replace audio in existing file

Options:
    --cookie-file <path>                Path to cookies.txt for YT Premium

Usage:
    # Download entire playlist (all 5 phases)
    spot --url "https://open.spotify.com/playlist/..."
    
    # Sync mode (download only new tracks)
    spot --url "https://open.spotify.com/playlist/..." --sync
    
    # Download liked songs
    spot --liked
    
    # Run phases separately
    spot --1 --url "https://..."        # Fetch Spotify metadata
    spot --2                            # Match on YouTube
    spot --3                            # Download audio
    spot --4                            # Fetch lyrics
    spot --5                            # Embed metadata and lyrics
    
    # Replace audio in existing file
    spot --replace ~/Music/01-Song-Artist.m4a "https://youtube.com/watch?v=..."

Configuration:
    The CLI requires a config.yaml file in the current directory with:
    - Spotify API credentials (client_id, client_secret)
    - Output directory path
    - Number of download threads
    - Optional cookie file path

Phase Dependencies:
    --1 (fetch metadata): Requires --url or --liked. Creates database entries.
    --2 (YouTube match): Requires tracks in database without youtube_url.
    --3 (download audio): Requires tracks with youtube_url but not downloaded.
    --4 (fetch lyrics): Requires tracks downloaded but lyrics not fetched.
    --5 (embed metadata): Requires tracks downloaded but metadata not embedded.
    
    When running without phase flags, all 5 phases run in sequence.
"""

import sys
from pathlib import Path
from typing import Optional

import rich_click as click

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
from spot_downloader.spotify import Track
from spot_downloader.core.database import LIKED_SONGS_KEY
from spot_downloader.download import (
    download_tracks_phase3,
    fetch_lyrics_phase4,
    embed_metadata_phase5,
)
from spot_downloader.utils.replace import replace_track_audio
from spot_downloader.spotify import (
    SpotifyClient,
    fetch_liked_songs_phase1,
    fetch_playlist_phase1,
)
from spot_downloader.utils import ensure_directory, extract_playlist_id
from spot_downloader.youtube import match_tracks_phase2, get_tracks_needing_match

logger = get_logger(__name__)


# Version string (if updated, update also in config.toml)
__version__ = "0.2.0"


@click.group(invoke_without_command=True)
@click.option(
    "--url",
    type=str,
    default=None,
    help="Spotify playlist URL. Required for --1 (fetch metadata phase)."
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
    help="Run only PHASE 1: fetch Spotify metadata. Requires --url or --liked."
)
@click.option(
    "--2", "phase2_only",
    is_flag=True,
    help="Run only PHASE 2: match tracks on YouTube Music."
)
@click.option(
    "--3", "phase3_only",
    is_flag=True,
    help="Run only PHASE 3: download audio files."
)
@click.option(
    "--4", "phase4_only",
    is_flag=True,
    help="Run only PHASE 4: fetch lyrics for downloaded tracks."
)
@click.option(
    "--5", "phase5_only",
    is_flag=True,
    help="Run only PHASE 5: embed metadata and lyrics into M4A files."
)
@click.option(
    "--replace",
    nargs=2,
    type=(click.Path(exists=True, path_type=Path), str),
    default=None,
    help="Replace audio in M4A file. Usage: --replace <file.m4a> <youtube_url>"
)
@click.option(
    "--cookie-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to cookies.txt for YouTube Music Premium quality."
)
@click.option(
    "--force-rematch",
    is_flag=True,
    help="Reset failed YouTube matches and retry matching in PHASE 2."
)
@click.option(
    "--version",
    is_flag=True,
    help="Show version and exit."
)
@click.pass_context
def cli(
    ctx: click.Context,
    url: Optional[str],
    liked: bool,
    sync: bool,
    phase1_only: bool,
    phase2_only: bool,
    phase3_only: bool,
    phase4_only: bool,
    phase5_only: bool,
    replace: Optional[tuple[Path, str]],
    cookie_file: Optional[Path],
    force_rematch: bool,
    version: bool
) -> None:
    """
    spot-downloader: Download Spotify playlists via YouTube Music.
    
    Downloads tracks from Spotify playlists by matching them on YouTube Music
    and downloading the audio in M4A format with full metadata.
    
    \b
    Examples:
        spot --url "https://open.spotify.com/playlist/..."
        spot --url "https://..." --sync
        spot --liked
        spot --replace song.m4a "https://youtube.com/watch?v=..."
    """
    # Handle --version
    if version:
        click.echo(f"spot-downloader {__version__}")
        ctx.exit(0)
    
    # Handle --replace (standalone operation)
    if replace:
        _handle_replace(replace, cookie_file)
        ctx.exit(0)
    
    # Phase flags
    phase_flags = [phase1_only, phase2_only, phase3_only, phase4_only, phase5_only]
    has_phase_flag = any(phase_flags)
    
    # Validate: show help only if no meaningful arguments
    # Phases 2-5 can run without --url/--liked (they use database)
    if not url and not liked and not has_phase_flag:
        # No arguments at all - show help
        click.echo(ctx.get_help())
        ctx.exit(0)
    
    if url and liked:
        raise click.UsageError("Cannot use both --url and --liked")
    
    # Validate URL is a playlist URL (not track, album, or artist)
    if url and "/playlist/" not in url:
        raise click.UsageError(
            "--url must be a Spotify playlist URL (containing '/playlist/'). "
            "For tracks, albums, or artists, use the appropriate Spotify feature."
        )
    
    # Phase flags are mutually exclusive
    if sum(phase_flags) > 1:
        raise click.UsageError("Only one phase flag (--1, --2, --3, --4, --5) can be used")
    
    # --1 requires --url or --liked
    if phase1_only and not url and not liked:
        raise click.UsageError("--1 requires --url or --liked")
    
    # --url can only be used with --1 (or when running all phases)
    if url and any([phase2_only, phase3_only, phase4_only, phase5_only]):
        raise click.UsageError("--url can only be used with --1 or when running all phases")
    
    # --liked can only be used with --1 (or when running all phases)
    if liked and any([phase2_only, phase3_only, phase4_only, phase5_only]):
        raise click.UsageError("--liked can only be used with --1 or when running all phases")
    
    # --sync only makes sense with --1 or when running all phases
    if sync and any([phase2_only, phase3_only, phase4_only, phase5_only]):
        raise click.UsageError("--sync can only be used with --1 or when running all phases")
    
    # Determine which phases to run
    if has_phase_flag:
        # Single phase mode
        run_phase1 = phase1_only
        run_phase2 = phase2_only
        run_phase3 = phase3_only
        run_phase4 = phase4_only
        run_phase5 = phase5_only
    else:
        # Run all phases
        run_phase1 = True
        run_phase2 = True
        run_phase3 = True
        run_phase4 = True
        run_phase5 = True
    
    # Store in context for the command
    ctx.ensure_object(dict)
    ctx.obj["url"] = url
    ctx.obj["liked"] = liked
    ctx.obj["sync"] = sync
    ctx.obj["run_phase1"] = run_phase1
    ctx.obj["run_phase2"] = run_phase2
    ctx.obj["run_phase3"] = run_phase3
    ctx.obj["run_phase4"] = run_phase4
    ctx.obj["run_phase5"] = run_phase5
    ctx.obj["cookie_file"] = cookie_file
    ctx.obj["force_rematch"] = force_rematch
    ctx.obj["user_auth"] = liked  # True if --liked, False otherwise
    
    # Run the download workflow
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
        # Phase 1 requires --url or --liked explicitly
        # Phases 2-5 can work without playlist_id (process all playlists)
        if options["liked"]:
            playlist_id = LIKED_SONGS_KEY
        elif options["url"]:
            playlist_id = extract_playlist_id(options["url"])
        else:
            # Running phase 2-5 without --url: playlist_id is None
            # Phase 2 will process ALL playlists
            # Phases 3-5 still need a specific playlist (use active one)
            playlist_id = None
        
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
                num_threads=config.download.threads,
                force_rematch=options["force_rematch"]
            )
        
        # Phases 3-5 require a specific playlist
        # If playlist_id is None, get the active one
        if playlist_id is None and any([options["run_phase3"], options["run_phase4"], options["run_phase5"]]):
            playlist_id = database.get_active_playlist_id()
            if playlist_id is None:
                click.echo("No playlist found in database. Run with --url first.", err=True)
                sys.exit(1)
        
        if options["run_phase3"]:
            _run_phase3(
                database=database,
                playlist_id=playlist_id,
                output_dir=config.output.directory,
                cookie_file=cookie_file,
                num_threads=config.download.threads
            )
        
        if options["run_phase4"]:
            _run_phase4(
                database=database,
                playlist_id=playlist_id,
                num_threads=config.download.threads
            )

        if options["run_phase5"]:
            _run_phase5(
                database=database,
                playlist_id=playlist_id,
                output_dir=config.output.directory,
                num_threads=config.download.threads
            )
        
        # Final statistics (only if we have a specific playlist)
        if playlist_id is not None:
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
    return load_config()


def _initialize_database(output_dir: Path) -> Database:
    """
    Initialize the SQLite database.
    
    Args:
        output_dir: Directory where database.db is stored.
    
    Returns:
        Database instance.
    
    Raises:
        DatabaseError: If database cannot be initialized.
    """
    db_path = output_dir / "database.db"
    return Database(db_path)


def _initialize_spotify(config: Config, user_auth: bool) -> None:
    """
    Initialize the Spotify client singleton.
    
    Args:
        config: Configuration with Spotify credentials.
        user_auth: Whether to enable user authentication.
    
    Raises:
        SpotifyError: If authentication fails.
    """
    SpotifyClient.init(
        client_id=config.spotify.client_id,
        client_secret=config.spotify.client_secret,
        user_auth=user_auth
    )


def _run_phase1(
    database: Database,
    url: str | None,
    liked: bool,
    sync: bool
) -> list[Track]:
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
    logger.info("=" * 60)
    logger.info("PHASE 1: Fetching Spotify metadata")
    logger.info("=" * 60)
    
    if liked:
        liked_songs, tracks = fetch_liked_songs_phase1(database, sync_mode=sync)
        logger.info(f"Fetched {liked_songs.total_tracks} liked songs")
    else:
        playlist, tracks = fetch_playlist_phase1(database, url, sync_mode=sync)
        logger.info(f"Fetched playlist: {playlist.name}")
        logger.info(f"Total tracks: {playlist.total_tracks}")
    
    if sync:
        logger.info(f"Sync mode: {len(tracks)} new tracks to process")
    else:
        logger.info(f"Tracks to process: {len(tracks)}")
    
    logger.info("PHASE 1 complete")
    return list(tracks)


def _run_phase2(
    database: Database,
    playlist_id: str | None,
    tracks: list[Track] | None,
    num_threads: int,
    force_rematch: bool = False
) -> None:
    """
    Run PHASE 2: Match tracks on YouTube Music.
    
    With Global Track Registry, matching is done globally - the same track
    is only matched once regardless of how many playlists contain it.
    
    Args:
        database: Database instance.
        playlist_id: Optional playlist ID for --force-rematch scope.
                    Not used for actual matching (that's global).
        tracks: Tracks from PHASE 1 (None if running phase separately).
        num_threads: Number of parallel matching threads.
        force_rematch: If True, reset failed matches before processing.
    """
    logger.info("=" * 60)
    logger.info("PHASE 2: Matching tracks on YouTube Music")
    logger.info("=" * 60)
    
    # Handle force_rematch
    if force_rematch:
        # Reset failed matches (globally or for specific playlist)
        reset_count = database.reset_failed_matches(playlist_id)
        if reset_count > 0:
            logger.info(f"Reset {reset_count} failed matches for re-matching")
    
    # Get tracks to process
    if tracks is None:
        # Running phase 2 separately - get ALL tracks needing match globally
        track_dicts = get_tracks_needing_match(database)
        
        if not track_dicts:
            logger.info("No tracks need YouTube matching")
            logger.info("PHASE 2 complete")
            return
        
        # Convert to Track objects
        tracks = [
            Track.from_database_dict(d["track_id"], d)
            for d in track_dicts
        ]
        logger.info(f"Found {len(tracks)} tracks needing YouTube match")
    else:
        # Tracks from phase 1 - filter to only those needing match
        existing_matched = set()
        for t in tracks:
            track_data = database.get_global_track(t.spotify_id)
            if track_data and track_data.get("youtube_url"):
                existing_matched.add(t.spotify_id)
        
        if existing_matched:
            tracks = [t for t in tracks if t.spotify_id not in existing_matched]
            logger.info(f"Skipping {len(existing_matched)} already matched tracks")
    
    if not tracks:
        logger.info("No tracks to match")
        logger.info("PHASE 2 complete")
        return
    
    logger.info(f"Matching {len(tracks)} tracks using {num_threads} threads")
    
    # Run matching (global - no playlist_id needed)
    match_tracks_phase2(database, tracks, num_threads)
    
    logger.info("PHASE 2 complete")


def _run_phase3(
    database: Database,
    playlist_id: str,
    output_dir: Path,
    cookie_file: Path | None,
    num_threads: int
) -> None:
    """
    Run PHASE 3: Download audio files.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID for database queries.
        output_dir: Directory for output files.
        cookie_file: Optional cookies.txt for YT Premium.
        num_threads: Number of parallel downloads.
    
    Behavior:
        1. Log phase start
        2. Get tracks with youtube_url but not downloaded
        3. For each track:
           a. Download audio from YouTube using yt-dlp
           b. Convert to M4A format
           c. Save with final filename: {assigned_number}-{title}-{artist}.m4a
           d. Update database: downloaded=True, file_path, download_timestamp
        4. Log download statistics
        5. Write failures to download_failures.log
    
    File Naming:
        Files are saved directly with their final name using the
        assigned_number from PHASE 1 (based on chronological order
        of when tracks were added to the playlist).
        
        Format: {assigned_number}-{title}-{artist}.m4a
        Example: 42-Bohemian Rhapsody-Queen.m4a
    
    Important:
        This phase does NOT fetch lyrics or embed metadata.
        Those operations are handled by PHASE 4 and PHASE 5.
    
    Database Updates:
        - Sets downloaded=True
        - Sets file_path to the final file location
        - Sets download_timestamp
    """
    raise NotImplementedError("Contract only - implementation pending")

def _run_phase4(
    database: Database,
    playlist_id: str,
    num_threads: int
) -> None:
    """
    Run PHASE 4: Fetch lyrics for downloaded tracks.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID for database queries.
        num_threads: Number of parallel fetching threads.
    
    Behavior:
        1. Log phase start
        2. Get tracks that are downloaded but don't have lyrics_fetched=True
        3. For each track:
           a. Attempt to fetch lyrics from multiple providers
           b. If found: store lyrics in database (lyrics_text, lyrics_synced, lyrics_source)
           c. If not found: log to lyrics_failures.log
           d. Mark lyrics_fetched=True regardless of success
        4. Log lyrics fetch statistics
    
    Database Updates:
        - Sets lyrics_text, lyrics_synced, lyrics_source for successful fetches
        - Sets lyrics_fetched=True for all processed tracks
    
    Logging:
        - INFO: Phase start, progress, completion
        - DEBUG: Individual track processing
        - Writes to lyrics_failures.log for tracks without lyrics
    """
    raise NotImplementedError("Contract only - implementation pending")


def _run_phase5(
    database: Database,
    playlist_id: str,
    output_dir: Path,
    num_threads: int = 4
) -> None:
    """
    Run PHASE 5: Embed metadata and lyrics into M4A files.
    
    Args:
        database: Database instance.
        playlist_id: Playlist ID for database queries.
        output_dir: Directory containing the M4A files.
        num_threads: Number of parallel embedding threads.
                    Cover art download benefits from parallelization.
    
    Behavior:
        1. Log phase start
        2. Get tracks that are downloaded but don't have metadata_embedded=True
        3. For each track (parallel with num_threads):
           a. Load file from file_path in database
           b. Embed all Spotify metadata (title, artist, album, cover, etc.)
           c. If lyrics_text exists in database, embed lyrics
           d. Mark metadata_embedded=True and lyrics_embedded=True (if lyrics present)
        4. Log embedding statistics
    
    File Naming:
        Files already have their final names from PHASE 3.
        This phase does NOT rename files, only embeds metadata.
    
    Database Updates:
        - Sets metadata_embedded=True
        - Sets lyrics_embedded=True if lyrics were embedded
    
    Logging:
        - INFO: Phase start, progress, completion
        - DEBUG: Individual track processing
        - ERROR: Files that couldn't be processed
    """
    raise NotImplementedError("Contract only - implementation pending")


def _handle_replace(replace_args: tuple[Path, str], cookie_file: Path | None) -> None:
    """
    Handle the --replace standalone operation.
    
    This function replaces the audio in an existing M4A file with audio
    downloaded from a YouTube URL, while preserving all metadata.
    
    Args:
        replace_args: Tuple of (m4a_file_path, youtube_url).
        cookie_file: Optional path to cookies.txt for Premium quality.
    
    Behavior:
        1. Load configuration (for cookie_file fallback)
        2. Validate the M4A file exists and is readable
        3. Extract existing metadata from the M4A file
        4. Download audio from YouTube URL
        5. Re-embed the preserved metadata into the new audio
        6. Replace the original file
    
    Raises:
        SystemExit: On any error (file not found, download failed, etc.)
    
    Note:
        This operation is completely independent from the database.
        It works on any M4A file produced by this application.
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
    stats = database.get_playlist_stats(playlist_id)
    
    logger.info("=" * 60)
    logger.info("FINAL STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Total tracks:      {stats['total']}")
    logger.info(f"Matched:           {stats['matched']}")
    logger.info(f"Downloaded:        {stats['downloaded']}")
    logger.info(f"Failed to match:   {stats['failed_match']}")
    logger.info(f"Pending match:     {stats['pending_match']}")
    logger.info(f"Pending download:  {stats['pending_download']}")
    logger.info("=" * 60)


def main() -> None:
    """
    Entry point for the CLI.
    
    This function is called when running `spot` from the command line.
    It invokes the Click CLI group.
    """
    cli()


if __name__ == "__main__":
    main()