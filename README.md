# spot_downloader

Download Spotify playlists via YouTube Music in M4A format with full metadata.

## Overview

spot_downloader converts Spotify playlists to local M4A audio files by:

1. **PHASE 1**: Fetching track metadata from Spotify (title, artist, album, cover, etc.)
2. **PHASE 2**: Matching each track on YouTube Music using fuzzy search
3. **PHASE 3**: Downloading audio and embedding metadata

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
spot --dl --url "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
```

### Sync Mode (Only New Tracks)

```bash
spot --dl --url "https://open.spotify.com/playlist/..." --sync
```

Downloads only tracks that aren't already in the local database.

### Download Liked Songs

```bash
spot --dl --liked
```

This will open your browser for Spotify authentication (required to access your Liked Songs).

### Run Phases Separately

You can run each phase independently:

```bash
# PHASE 1: Fetch Spotify metadata only
spot --dl --1 --url "https://open.spotify.com/playlist/..."

# PHASE 2: Match tracks on YouTube Music only
spot --dl --2 --url "https://open.spotify.com/playlist/..."

# PHASE 3: Download and process audio only
spot --dl --3 --url "https://open.spotify.com/playlist/..."
```

### Using Cookie File

```bash
spot --dl --url "https://..." --cookie-file ~/cookies.txt
```

## CLI Reference

```
spot --dl [OPTIONS]

Options:
  --url TEXT          Spotify playlist URL to download
  --liked             Download Liked Songs instead of a playlist
  --sync              Only download new tracks not in database
  --1                 Run only PHASE 1 (fetch Spotify metadata)
  --2                 Run only PHASE 2 (match on YouTube Music)
  --3                 Run only PHASE 3 (download audio)
  --cookie-file PATH  Path to cookies.txt for YouTube Premium
  --version           Show version and exit
  --help              Show this message and exit
```

## Output

### File Naming

Downloaded files follow this format:
```
{track_number}-{title}-{artist}.m4a
```

Track numbers are assigned sequentially based on download order.

### Log Files

Three log files are created in the output directory:

| File | Description |
|------|-------------|
| `log_full.txt` | Complete log of all events |
| `log_errors.txt` | Only errors and critical issues |
| `report.txt` | List of failed tracks with Spotify URLs |

### Database

A `database.json` file tracks the state of all playlists and tracks, enabling:
- Resume after interruption
- Sync mode (detect new tracks)
- Avoiding re-downloads

## Project Structure

```
spot_downloader/
├── core/
│   ├── config.py       # Configuration loading
│   ├── database.py     # Thread-safe JSON database
│   ├── exceptions.py   # Custom exceptions
│   └── logger.py       # Multi-file logging
├── spotify/
│   ├── client.py       # Spotify API singleton
│   ├── fetcher.py      # PHASE 1 implementation
│   └── models.py       # Track, Playlist dataclasses
├── youtube/
│   ├── matcher.py      # PHASE 2 implementation
│   └── models.py       # MatchResult dataclasses
├── download/
│   ├── downloader.py   # PHASE 3 implementation
│   ├── lyrics.py       # Multi-provider lyrics fetching
│   └── metadata.py     # M4A metadata embedding
├── utils/              # Utilities (sanitization, threading)
└── cli.py              # Click CLI interface
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
| tqdm | Progress bars |
| pyyaml | Config parsing |
| syncedlyrics | Timestamped lyrics |
| requests | HTTP requests |
| beautifulsoup4 | HTML parsing |

## Troubleshooting

### "Spotify authentication failed"
- Verify `client_id` and `client_secret` in `config.yaml`
- Check that your Spotify app is properly configured

### "No matching video found"
- Some tracks may not be available on YouTube Music
- Check `report.txt` for the list of failed tracks

### "FFmpeg not found"
- Ensure FFmpeg is installed and in your system PATH
- Try running `ffmpeg -version` to verify

### Low audio quality
- Without cookies, YouTube limits quality to 128 kbps
- Use `--cookie-file` with YouTube Premium cookies for 256 kbps

## License

MIT License - see LICENSE file for details.

## Acknowledgments

This project is inspired by [spotDL](https://github.com/spotDL/spotify-downloader) and uses similar matching algorithms for YouTube Music search.
