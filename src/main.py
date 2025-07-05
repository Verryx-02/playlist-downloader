"""
Main CLI interface for Playlist-Downloader
Provides comprehensive command-line interface for all functionality
"""

import sys
import click
import functools
from pathlib import Path

from .config.settings import get_settings, reload_settings
from .config.auth import get_auth, reset_auth
from .spotify.client import get_spotify_client
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


# Initialize logging
configure_from_settings()
logger = get_logger(__name__)


def print_banner():
    """Print application banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                    🎵 Playlist-Downloader 🎵                   ║
║                                                               ║
║  Download Spotify playlists with YouTube Music + Lyrics      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """
    click.echo(click.style(banner, fg='green', bold=True))


def handle_error(func):
    """Decorator to handle common CLI errors"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            click.echo(click.style("\n\nOperation cancelled by user", fg='yellow'))
            sys.exit(130)
        except Exception as e:
            logger.error(f"Command failed: {e}")
            click.echo(click.style(f"❌ Error: {e}", fg='red'), err=True)
            sys.exit(1)
    return wrapper


# Main CLI group
@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--config', type=click.Path(), help='Path to config file')
@click.pass_context
def cli(ctx, version, verbose, config):
    """
    🎵 Playlist-Downloader - Download Spotify playlists with lyrics
    
    A powerful tool to download Spotify playlists locally using YouTube Music,
    with automatic lyrics integration and intelligent sync capabilities.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    if version:
        click.echo("Playlist-Downloader v1.0.0")
        return
    
    # Load custom config if specified
    if config:
        reload_settings(config)
        click.echo(f"✅ Loaded config: {config}")
    
    # Set verbose mode
    if verbose:
        ctx.obj['verbose'] = True
        logger.info("Verbose mode enabled")
    
    # If no command specified, show help
    if ctx.invoked_subcommand is None:
        print_banner()
        click.echo(ctx.get_help())


# Authentication commands
@cli.group()
def auth():
    """🔐 Authentication management"""
    pass


@auth.command()
@handle_error
def login():
    """Authenticate with Spotify"""
    click.echo("🔐 Starting Spotify authentication...")
    
    auth_manager = get_auth()
    
    if auth_manager.is_authenticated():
        user_info = auth_manager.get_user_info()
        username = user_info.get('display_name', user_info.get('id', 'Unknown')) if user_info else 'Unknown'
        click.echo(f"✅ Already authenticated as: {username}")
        return
    
    try:
        token = auth_manager.get_valid_token()
        
        if token:
            user_info = auth_manager.get_user_info()
            username = user_info.get('display_name', user_info.get('id', 'Unknown')) if user_info else 'Unknown'
            click.echo(f"✅ Successfully authenticated as: {username}")
        else:
            click.echo("❌ Authentication failed")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Authentication error: {e}")
        sys.exit(1)


@auth.command()
@handle_error
def logout():
    """Remove stored authentication"""
    click.echo("🔓 Removing stored authentication...")
    
    auth_manager = get_auth()
    auth_manager.revoke_token()
    reset_auth()
    
    click.echo("✅ Successfully logged out")


@auth.command()
@handle_error
def status():
    """Check authentication status"""
    auth_manager = get_auth()
    
    if auth_manager.is_authenticated():
        user_info = auth_manager.get_user_info()
        if user_info:
            click.echo("✅ Authentication Status: Authenticated")
            click.echo(f"   User: {user_info.get('display_name', user_info.get('id', 'Unknown'))}")
            click.echo(f"   Country: {user_info.get('country', 'Unknown')}")
            click.echo(f"   Followers: {user_info.get('followers', {}).get('total', 'Unknown')}")
        else:
            click.echo("✅ Authentication Status: Authenticated (limited info)")
    else:
        click.echo("❌ Authentication Status: Not authenticated")
        click.echo("   Run 'playlist-dl auth login' to authenticate")


# Main download commands
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
    """📥 Download a Spotify playlist"""
    
    # Validate playlist URL
    is_valid, error_msg = validate_spotify_url(playlist_url)
    if not is_valid:
        click.echo(click.style(f"❌ Invalid playlist URL: {error_msg}", fg='red'), err=True)
        sys.exit(1)
    
    # Validate output directory if provided
    if output:
        is_valid, error_msg = validate_output_directory(output)
        if not is_valid:
            click.echo(click.style(f"❌ Invalid output directory: {error_msg}", fg='red'), err=True)
            sys.exit(1)
    
    # Validate format if provided
    if format:
        is_valid, error_msg = validate_audio_format(format)
        if not is_valid:
            click.echo(click.style(f"❌ {error_msg}", fg='red'), err=True)
            sys.exit(1)
    
    # Validate quality if provided  
    if quality:
        is_valid, error_msg = validate_quality_setting(quality)
        if not is_valid:
            click.echo(click.style(f"❌ {error_msg}", fg='red'), err=True)
            sys.exit(1)
    
    # Validate concurrent downloads
    if concurrent and (concurrent < 1 or concurrent > 10):
        click.echo(click.style("❌ Concurrent downloads must be between 1 and 10", fg='red'), err=True)
        sys.exit(1)
    
    if dry_run:
        click.echo("🔍 Dry run mode - showing what would be downloaded...")
    
    # Initialize components
    settings = get_settings()
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
    if lyrics_source:
        settings.lyrics.primary_source = lyrics_source
    if concurrent:
        settings.download.concurrency = concurrent
    
    
    # Create sync plan
    with click.progressbar(length=100, label='Analyzing playlist') as bar:
        sync_plan = synchronizer.create_sync_plan(playlist_url)
        bar.update(100)
    
    if not sync_plan.has_changes:
        click.echo("✅ Playlist is already up to date!")
        return
    
    logger.console_info(f"🎵 {sync_plan.playlist_name} ({sync_plan.estimated_downloads} tracks to download)")
    
    if dry_run:
        click.echo("\n🔍 Operations that would be performed:")
        for i, operation in enumerate(sync_plan.operations, 1):
            if operation.track:
                click.echo(f"   {i}. Download: {operation.track.spotify_track.primary_artist} - {operation.track.spotify_track.name}")
            else:
                click.echo(f"   {i}. {operation.operation_type}: {operation.reason}")
        return
    
    # Confirm with user
    if not click.confirm(f"\nProceed with downloading {sync_plan.estimated_downloads} tracks?"):
        click.echo("❌ Download cancelled")
        return
    
    # Find local directory
    spotify_client = get_spotify_client()
    playlist_id = spotify_client.extract_playlist_id(playlist_url)
    playlist = spotify_client.get_full_playlist(playlist_id)
    
    local_directory = settings.get_output_directory() / playlist.name
    local_directory.mkdir(parents=True, exist_ok=True)
    
    # Execute sync plan
    result = synchronizer.execute_sync_plan(sync_plan, local_directory)
    
    # Show results
    if result.downloads_failed > 0:
        logger.console_info(f"✅ {result.downloads_completed} downloaded, {result.downloads_failed} failed")
    else:
        logger.console_info(f"✅ {result.downloads_completed} tracks downloaded")
        
    if settings.lyrics.enabled:
        click.echo(f"   🎵 Lyrics: {result.lyrics_completed}")
        click.echo(f"   🚫 Lyrics failed: {result.lyrics_failed}")
    
    if result.total_time:
        click.echo(f"   ⏱️ Total time: {format_duration(result.total_time)}")
    
    click.echo(f"\n📁 Files saved to: {local_directory}")
    # Force flush output streams
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
def sync(playlist_url, output):
    """🔄 Synchronize an existing playlist"""
    
    click.echo(f"🔄 Synchronizing playlist: {playlist_url}")
    
    synchronizer = get_synchronizer()
    
    # Check current status
    with click.progressbar(length=100, label='Checking playlist status') as bar:
        status = synchronizer.check_playlist_status(playlist_url)
        bar.update(100)
    
    if 'error' in status:
        click.echo(f"❌ Error: {status['error']}")
        return
    
    click.echo(f"\n📋 Playlist Status:")
    click.echo(f"   Name: {status['playlist_name']}")
    click.echo(f"   Total tracks: {status['total_tracks']}")
    click.echo(f"   Local directory: {status['local_directory']}")
    click.echo(f"   Status: {status['sync_summary']}")
    
    if not status['needs_sync']:
        click.echo("✅ Playlist is already up to date!")
        return
    
    # Create and execute sync plan
    local_directory = Path(status['local_directory'])
    
    if output:
        local_directory = Path(output)
        local_directory.mkdir(parents=True, exist_ok=True)
    
    sync_plan = synchronizer.create_sync_plan(playlist_url, local_directory)
    
    if not click.confirm(f"\nProceed with sync ({sync_plan.estimated_downloads} downloads)?"):
        click.echo("❌ Sync cancelled")
        return
    
    click.echo("\n🚀 Starting sync...")
    result = synchronizer.execute_sync_plan(sync_plan, local_directory)
    
    # Show results
    click.echo(f"\n📊 Sync Results: {result.summary}")


@cli.command()
@click.argument('playlist_url')
@handle_error
def check(playlist_url):
    """🔍 Check playlist status without downloading"""
    
    click.echo(f"🔍 Checking playlist: {playlist_url}")
    
    synchronizer = get_synchronizer()
    
    with click.progressbar(length=100, label='Analyzing playlist') as bar:
        status = synchronizer.check_playlist_status(playlist_url)
        bar.update(100)
    
    if 'error' in status:
        click.echo(f"❌ Error: {status['error']}")
        return
    
    # Show detailed status
    click.echo(f"\n📋 Playlist Information:")
    click.echo(f"   📛 Name: {status['playlist_name']}")
    click.echo(f"   🎵 Total tracks: {status['total_tracks']}")
    click.echo(f"   📁 Local directory: {status['local_directory']}")
    click.echo(f"   📄 Tracklist exists: {'Yes' if status['tracklist_exists'] else 'No'}")
    click.echo(f"   🔄 Needs sync: {'Yes' if status['needs_sync'] else 'No'}")
    click.echo(f"   📊 Status: {status['sync_summary']}")
    
    if status['needs_sync']:
        click.echo(f"   📥 Downloads needed: {status.get('estimated_downloads', 0)}")
        if status.get('estimated_time'):
            click.echo(f"   ⏱️ Estimated time: {format_duration(status['estimated_time'])}")


@cli.command()
@click.option('--show-lyrics', is_flag=True, help='Show lyrics status')
@handle_error
def list(show_lyrics):
    """📋 List local playlists"""
    
    settings = get_settings()
    output_dir = settings.get_output_directory()
    
    if not output_dir.exists():
        click.echo("📂 No playlists found (output directory doesn't exist)")
        return
    
    # Find all tracklist files
    from .sync.tracker import get_tracklist_manager
    
    tracklist_manager = get_tracklist_manager()
    tracklist_files = tracklist_manager.find_tracklist_files(output_dir)
    
    if not tracklist_files:
        click.echo("📂 No playlists found")
        return
    
    click.echo(f"📋 Found {len(tracklist_files)} playlists:\n")
    
    for tracklist_path in tracklist_files:
        try:
            metadata, entries = tracklist_manager.read_tracklist_file(tracklist_path)
            
            # Calculate stats
            total_tracks = len(entries)
            downloaded = len([e for e in entries if e.audio_status.value == 'downloaded'])
            download_percent = (downloaded / total_tracks * 100) if total_tracks > 0 else 0
            
            lyrics_downloaded = 0
            lyrics_percent = 0
            if show_lyrics and metadata.lyrics_enabled:
                lyrics_downloaded = len([e for e in entries if e.lyrics_status.value == 'downloaded'])
                lyrics_percent = (lyrics_downloaded / total_tracks * 100) if total_tracks > 0 else 0
            
            # Display playlist info
            click.echo(f"🎵 {metadata.playlist_name}")
            click.echo(f"   📁 {tracklist_path.parent}")
            click.echo(f"   📊 {downloaded}/{total_tracks} tracks ({download_percent:.1f}%)")
            
            if show_lyrics and metadata.lyrics_enabled:
                click.echo(f"   🎵 {lyrics_downloaded}/{total_tracks} lyrics ({lyrics_percent:.1f}%)")
            
            click.echo(f"   📅 Last modified: {metadata.last_modified}")
            click.echo()
            
        except Exception as e:
            click.echo(f"❌ Error reading {tracklist_path}: {e}")


# Lyrics commands
@cli.group()
def lyrics():
    """🎵 Lyrics management"""
    pass


@lyrics.command()
@click.argument('playlist_url')
@click.option('--source', type=click.Choice(['genius']), help='Lyrics source')
@handle_error
def download_lyrics(playlist_url, source):
    """Download lyrics for existing playlist"""
    
    click.echo(f"🎵 Downloading lyrics for: {playlist_url}")
    
    # Find playlist directory
    synchronizer = get_synchronizer()
    status = synchronizer.check_playlist_status(playlist_url)
    
    if 'error' in status:
        click.echo(f"❌ Error: {status['error']}")
        return
    
    local_directory = Path(status['local_directory'])
    tracklist_path = local_directory / "tracklist.txt"
    
    if not tracklist_path.exists():
        click.echo("❌ Playlist not found locally. Download playlist first.")
        return
    
    # Read tracklist
    from .sync.tracker import get_tracklist_manager
    tracklist_manager = get_tracklist_manager()
    metadata, entries = tracklist_manager.read_tracklist_file(tracklist_path)
    
    # Find tracks without lyrics
    lyrics_processor = get_lyrics_processor()
    tracks_needing_lyrics = [e for e in entries if e.lyrics_status.value != 'downloaded']
    
    if not tracks_needing_lyrics:
        click.echo("✅ All tracks already have lyrics!")
        return
    
    click.echo(f"📥 Downloading lyrics for {len(tracks_needing_lyrics)} tracks...")
    
    # Download lyrics for each track
    completed = 0
    failed = 0
    
    with click.progressbar(tracks_needing_lyrics, label='Downloading lyrics') as bar:
        for entry in bar:
            try:
                # Override source if specified
                preferred_source = None
                if source:
                    from .spotify.models import LyricsSource
                    preferred_source = LyricsSource(source)
                
                lyrics_result = lyrics_processor.search_lyrics(
                    entry.artist,
                    entry.title,
                    preferred_source=preferred_source
                )
                
                if lyrics_result.success:
                    # Save lyrics files
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
    
    click.echo(f"\n📊 Lyrics Results:")
    click.echo(f"   ✅ Completed: {completed}")
    click.echo(f"   ❌ Failed: {failed}")


@lyrics.command()
@handle_error
def sources():
    """Check lyrics sources status"""
    
    click.echo("🎵 Checking lyrics sources...")
    
    lyrics_processor = get_lyrics_processor()
    source_status = lyrics_processor.validate_lyrics_sources()
    
    click.echo("\n📊 Lyrics Sources Status:")
    
    for source, available in source_status.items():
        status_icon = "✅" if available else "❌"
        status_text = "Available" if available else "Unavailable"
        click.echo(f"   {status_icon} {source.value}: {status_text}")


# Configuration commands
@cli.group()
def config():
    """⚙️ Configuration management"""
    pass


@config.command()
@handle_error
def show():
    """Show current configuration"""
    
    settings = get_settings()
    
    click.echo("⚙️ Current Configuration:\n")
    
    # Download settings
    click.echo("📥 Download:")
    click.echo(f"   Output directory: {settings.download.output_directory}")
    click.echo(f"   Format: {settings.download.format}")
    click.echo(f"   Quality: {settings.download.quality}")
    click.echo(f"   Concurrent downloads: {settings.download.concurrency}")
    
    # Lyrics settings
    click.echo("\n🎵 Lyrics:")
    click.echo(f"   Enabled: {settings.lyrics.enabled}")
    click.echo(f"   Primary source: {settings.lyrics.primary_source}")
    click.echo(f"   Fallback sources: {', '.join(settings.lyrics.fallback_sources)}")
    click.echo(f"   Format: {settings.lyrics.format}")
    click.echo(f"   Embed in audio: {settings.lyrics.embed_in_audio}")
    
    # Audio settings
    click.echo("\n🎧 Audio:")
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
    """Update configuration settings"""
    
    settings = get_settings()
    changes = []
    
    if format:
        settings.download.format = format
        changes.append(f"Audio format: {format}")
    
    if quality:
        settings.download.quality = quality
        changes.append(f"Audio quality: {quality}")
    
    if output:
        settings.download.output_directory = output
        changes.append(f"Output directory: {output}")
    
    if lyrics_source:
        settings.lyrics.primary_source = lyrics_source
        changes.append(f"Lyrics source: {lyrics_source}")
    
    if changes:
        settings.save_config()
        click.echo("✅ Configuration updated:")
        for change in changes:
            click.echo(f"   • {change}")
    else:
        click.echo("ℹ️ No changes specified")


# System commands
@cli.command()
@handle_error
def doctor():
    """🩺 Run system diagnostics"""
    
    click.echo("🩺 Running diagnostics...\n")
    
    issues = []
    
    # Check authentication
    auth_manager = get_auth()
    if auth_manager.is_authenticated():
        click.echo("✅ Spotify authentication: OK")
    else:
        click.echo("❌ Spotify authentication: Not authenticated")
        issues.append("Run 'playlist-dl auth login' to authenticate")
    
    # Check YouTube Music API
    try:
        from .ytmusic.searcher import get_ytmusic_searcher
        searcher = get_ytmusic_searcher()
        if searcher.validate_search_config():
            click.echo("✅ YouTube Music API: OK")
        else:
            click.echo("❌ YouTube Music API: Failed")
            issues.append("YouTube Music API validation failed")
    except Exception as e:
        click.echo(f"❌ YouTube Music API: Error - {e}")
        issues.append("YouTube Music API initialization failed")
    
    # Check lyrics sources
    try:
        lyrics_processor = get_lyrics_processor()
        source_status = lyrics_processor.validate_lyrics_sources()
        
        available_sources = [source.value for source, available in source_status.items() if available]
        if available_sources:
            click.echo(f"✅ Lyrics sources: {', '.join(available_sources)}")
        else:
            click.echo("⚠️ Lyrics sources: None available")
            issues.append("No lyrics sources are configured")
    except Exception as e:
        click.echo(f"❌ Lyrics sources: Error - {e}")
        issues.append("Lyrics system initialization failed")
    
    # Check dependencies
    try:
        import yt_dlp
        click.echo("✅ yt-dlp: OK")
    except ImportError:
        click.echo("❌ yt-dlp: Not installed")
        issues.append("yt-dlp is required for downloading")
    
    try:
        import mutagen
        click.echo("✅ mutagen: OK")
    except ImportError:
        click.echo("❌ mutagen: Not installed")
        issues.append("mutagen is required for metadata handling")
    
    # Check output directory
    settings = get_settings()
    output_dir = settings.get_output_directory()
    
    if output_dir.exists() and output_dir.is_dir():
        click.echo(f"✅ Output directory: {output_dir}")
    else:
        click.echo(f"⚠️ Output directory: {output_dir} (will be created)")

    # Check current logging setup
    current_log = get_current_log_file()
    if current_log:
        click.echo(f"✅ Logging: {current_log}")
    else:
        click.echo("ℹ️ Logging: Console only (will switch to playlist-specific when syncing)")
    
    # Summary
    if issues:
        click.echo(f"\n⚠️ Found {len(issues)} issues:")
        for issue in issues:
            click.echo(f"   • {issue}")
    else:
        click.echo("\n✅ All systems operational!")


if __name__ == '__main__':
    cli()