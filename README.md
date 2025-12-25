![Banner](/Asset/banner.png)


## Overview

spot_downloader converts Spotify playlists to local M4A audio files by:

- **PHASE 1**: Fetching track metadata from Spotify (title, artist, album, cover, etc.)  
- **PHASE 2**: Matching each track on YouTube Music
- **PHASE 3**: Downloading audio  
- **PHASE 4**: Downloading lyrics  
- **PHASE 5**: Embedding metadata and lyrics  

The result is a collection of properly tagged M4A files ready for any music player.

## Features

- Download entire Spotify playlists or Liked Songs
- **Sync mode**: only download new tracks added since last sync
- M4A audio (128 kbps free, 256 kbps with YouTube Premium)
- Full metadata embedding (title, artist, album, cover art, lyrics, etc.)
- Automatic lyrics fetching from multiple providers
- Multi-threaded downloads
- Resume interrupted downloads
- Detailed logging and error reporting

## Requirements

- Python 3.11+
- FFmpeg
- Spotify Developer credentials
- Optional: YouTube Music cookies for Premium quality

## Installation

```bash
git clone https://github.com/Verryx-02/spot_downloader.git
cd spot_downloader
pip install -e .
```

## Configuration

Create a `config.yaml` file in your working directory:

```yaml
spotify:
  client_id: "your_spotify_client_id"
  client_secret: "your_spotify_client_secret"

output:
  directory: "~/Desktop/Music/SpotDownloader"

download:
  threads: 4
  cookie_file: null  # Optional: path to cookies.txt for YT Premium
```

### Spotify Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new application
3. Copy the Client ID and Client Secret to your `config.yaml`

### YouTube Premium Quality (Optional)

To download at 256 kbps instead of 128 kbps:

1. Install a browser extension like "Get cookies.txt"
2. Log in to [YouTube Music](https://music.youtube.com) with a Premium account
3. Export cookies to a file
4. Set `cookie_file` in `config.yaml` to the path of your cookies file

## Usage

### Download a Playlist

```bash
spot --url "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
```

### Sync Mode (Only New Tracks)

```bash
spot --url "https://open.spotify.com/playlist/..." --sync
```

Downloads only tracks that aren't already in the local database.

### Download Liked Songs

```bash
spot --liked
```

This will open your browser for Spotify authentication (required to access your Liked Songs).

### Run Phases Separately

You can run each phase independently:

```bash
# PHASE 1: Fetch Spotify metadata only and save them in SQLite database
spot --1 --url "https://open.spotify.com/playlist/..."

# PHASE 2: Match tracks on YouTube Music only (based on db data)
spot --2

# PHASE 3: Download and process audio only (based on db data)
spot --3

# PHASE 4: Fetch lyrics
spot --4

# PHASE 5: Embed metadata and lyrics
spot --5

```

### Using Cookie File

```bash
spot --url "https://..." --cookie-file ~/cookies.txt
```

## CLI Reference

```
spot [OPTIONS]

Options:
  --url <url>                   Spotify playlist URL to download
  --liked                       Download Liked Songs instead of a playlist
  --sync                        Only download new tracks not in database
  --replace <songPath>  <url>   Replace a song with the song of the youtube url (maintaining metadata and lyrics)
  --1                           Run only PHASE 1 (fetch Spotify metadata)
  --2                           Run only PHASE 2 (match on YouTube Music)
  --3                           Run only PHASE 3 (download audio)
  --4                           Run only PHASE 4 (fetch lyrics)
  --5                           Run only PHASE 5 (embed metadata and lyrics)
  --cookie-file PATH            Path to cookies.txt for YouTube Premium
  --version                     Show version and exit
  --help                        Show this message and exit
```

## Output

### File Naming

Downloaded files follow this format:
```
{track_number}-{title}-{artist}.m4a
```

Track numbers are assigned based on when tracks were added to the playlist (oldest first).

### Log Files

Five log files are created in the output directory:

| File | Description |
|------|-------------|
| `log_full.log` | Complete log of all events |
| `log_errors.log` | Only errors and critical issues |
| `download_failures.log` | List of tracks whose audio download failed, including Spotify URLs |
| `lyrics_failures.log` | List of tracks whose lyrics could not be retrieved, including Spotify URLs |
| `match_close_alternatives.log` | Tracks with multiple YouTube matches of similar score, for manual verification |


### Database

A `database.db` file tracks the state of all playlists and tracks, enabling:
- Resume after interruption
- Sync mode (detect new tracks)
- Avoiding re-downloads

## Project Structure

```
.
├── config.yaml.example       # Example configuration file
├── LICENSE
├── pyproject.toml            # Project dependencies and metadata
├── README.md
└── spot_downloader/
    ├── __init__.py           # Package init, architecture documentation
    ├── cli.py                # Click CLI interface
    ├── core/
    │   ├── __init__.py       # Core module exports
    │   ├── config.py         # Configuration loading and validation
    │   ├── database.py       # Thread-safe SQLite database
    │   ├── exceptions.py     # Custom exception classes
    │   └── logger.py         # Multi-file logging setup
    ├── spotify/
    │   ├── __init__.py       # Spotify module exports
    │   ├── client.py         # Spotify API singleton client
    │   ├── fetcher.py        # PHASE 1: Fetch metadata from Spotify
    │   └── models.py         # Track, Playlist, LikedSongs dataclasses
    ├── youtube/
    │   ├── __init__.py       # YouTube module exports
    │   ├── matcher.py        # PHASE 2: Match tracks on YouTube Music
    │   └── models.py         # MatchResult dataclass
    ├── download/
    │   ├── __init__.py       # Download module exports
    │   ├── downloader.py     # PHASE 3: Download audio from YouTube
    │   ├── lyrics.py         # Lyrics fetcher and data model
    │   ├── lyrics_phase.py   # PHASE 4: Fetch lyrics orchestration
    │   ├── metadata.py       # M4A metadata embedder
    │   └── embed_phase.py    # PHASE 5: Embed metadata orchestration
    └── utils/
        ├── __init__.py       # Utility functions (URL parsing, formatting)
        └── replace.py        # Replace audio in existing M4A files

7 directories, 26 files
```

## Metadata Tags

The following metadata is embedded in each M4A file:

| Tag | Source |
|-----|--------|
| Title | Spotify |
| Artist | Spotify |
| Album | Spotify |
| Album Artist | Spotify |
| Year | Spotify |
| Genre | Spotify (from artist) |
| Track Number | Spotify |
| Disc Number | Spotify |
| Cover Art | Spotify (downloaded) |
| Lyrics | Genius, AZLyrics, MusixMatch, Synced |
| Explicit | Spotify |
| Copyright | Spotify |
| ISRC | Spotify |

## Dependencies

| Package | Purpose |
|---------|---------|
| spotipy | Spotify API client |
| ytmusicapi | YouTube Music search |
| yt-dlp | YouTube download |
| mutagen | M4A metadata |
| rapidfuzz | Fuzzy string matching |
| click | CLI framework |
| rich-click | CLI colors |
| tqdm | Progress bars |
| pyyaml | Config parsing |
| syncedlyrics | Timestamped lyrics |
| requests | HTTP requests |
| beautifulsoup4 | HTML parsing |


## Demo
You can see a demo of spot-downloader in action in [this video](/Asset/Demo_phase1_2.mov) 


## Troubleshooting

### "Spotify authentication failed"
- Verify `client_id` and `client_secret` in `config.yaml`
- Check that your Spotify app is properly configured

### Low audio quality
- Without cookies, YouTube limits quality to 128 kbps
- Use `--cookie-file` with YouTube Premium cookies for 256 kbps

## License: 
[MIT](LICENSE)

<a href="https://ko-fi.com/verryx02">
  <img src="Asset/support_me_on_kofi_beige.png" alt="Support me on Ko-fi" width="170">
</a>

## Acknowledgments

This project is inspired by [spotDL](https://github.com/spotDL/spotify-downloader). It uses and improves its matching algorithm for music searches on YouTube.
