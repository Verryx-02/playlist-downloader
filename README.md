# 🎵 Playlist-Downloader

A comprehensive tool for downloading Spotify playlists locally with YouTube Music integration and automatic lyrics support.

## ✨ Features

### 🎵 **Core Functionality**
- **Complete Playlist Downloads**: Download entire Spotify playlists with metadata
- **High-Quality Audio**: Best available audio quality from YouTube Music (up to 256kbps AAC)
- **Intelligent Matching**: Advanced algorithm for finding the best YouTube Music matches
- **Multi-Format Support**: MP3, FLAC, and M4A output formats

### 🎤 **Lyrics Integration**
- **Multi-Source Lyrics**: Primary support for Genius API
- **Automatic Embedding**: Lyrics embedded directly in audio file metadata
- **Separate Files**: Optional .lrc (synchronized) and .txt (plain) lyrics files
- **Smart Matching**: Intelligent lyrics search with quality validation

### 🔄 **Synchronization**
- **Incremental Updates**: Only download new/changed tracks
- **Smart Reordering**: Detect and handle moved tracks
- **Status Tracking**: Detailed tracklist.txt files for sync state
- **Resume Capability**: Resume interrupted downloads

### 🎧 **Audio Processing**
- **Silence Trimming**: Automatic removal of silence from start/end
- **Audio Normalization**: EBU R128 loudness normalization
- **Quality Control**: Audio validation and integrity checking
- **Metadata Enhancement**: Complete ID3 tags with album artwork

### 🛠️ **Advanced Features**
- **Parallel Downloads**: Configurable concurrent download limits
- **Rate Limiting**: Respectful API usage with automatic rate limiting
- **Error Recovery**: Smart retry logic with exponential backoff
- **Cross-Platform**: Works on Windows, macOS, and Linux

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- FFmpeg (for audio processing)
- Spotify Developer Account (for API access)

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/playlist-downloader/playlist-downloader.git
cd playlist-downloader
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install the package**:
```bash
pip install -e .
```

### Configuration

1. **Create Spotify App**:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new app
   - Note your `Client ID` and `Client Secret`
   - Add `http://localhost:8080/callback` to Redirect URIs

2. **Set up environment variables**:
```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
```

Or create a `.env` file:
```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

3. **Optional: Configure Lyrics APIs**:
```bash
export GENIUS_API_KEY="your_genius_api_key"
```

### First Run

1. **Authenticate with Spotify**:
```bash
playlist-dl auth login
```

2. **Download a playlist**:
```bash
playlist-dl download "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd"
```

3. **Check system status**:
```bash
playlist-dl doctor
```

## 📖 Usage Guide

### Basic Commands

#### Download a Playlist
```bash
playlist-dl download "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"
```

Options:
- `--format mp3|flac|m4a`: Audio format (default: mp3)
- `--quality low|medium|high`: Audio quality (default: high)
- `--no-lyrics`: Skip lyrics download
- `--output /path/to/output`: Custom output directory
- `--concurrent 5`: Number of parallel downloads

#### Sync an Existing Playlist
```bash
playlist-dl sync "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"
```

#### Check Playlist Status
```bash
playlist-dl check "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"
```

#### List Local Playlists
```bash
playlist-dl list --show-lyrics
```

### Lyrics Management

#### Download Lyrics Only
```bash
playlist-dl lyrics download "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"
```

#### Check Lyrics Sources
```bash
playlist-dl lyrics sources
```

### Configuration

#### View Current Settings
```bash
playlist-dl config show
```

#### Update Settings
```bash
playlist-dl config set --format flac --quality high --lyrics-source genius
```

### Authentication

#### Login
```bash
playlist-dl auth login
```

#### Check Status
```bash
playlist-dl auth status
```

#### Logout
```bash
playlist-dl auth logout
```

## ⚙️ Configuration

### Configuration File

The application uses a YAML configuration file located at `~/.playlist-downloader/config.yaml`:

```yaml
download:
  output_directory: "~/Music/Playlist Downloads"
  format: "mp3"
  quality: "high"
  bitrate: 320
  concurrency: 3

lyrics:
  enabled: true
  download_separate_files: true
  embed_in_audio: true
  format: "lrc"
  primary_source: "genius"
  clean_lyrics: true

audio:
  trim_silence: true
  normalize: false
  sample_rate: 44100
  channels: 2

sync:
  auto_sync: false
  sync_lyrics: true
  detect_moved_tracks: true
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SPOTIFY_CLIENT_ID` | Spotify App Client ID | Yes |
| `SPOTIFY_CLIENT_SECRET` | Spotify App Client Secret | Yes |
| `GENIUS_API_KEY` | Genius API Token | Optional |
| `DOWNLOAD_OUTPUT_DIR` | Default output directory | Optional |

## 📁 File Organization

```
~/Music/Playlist Downloads/
└── My Awesome Playlist/
    ├── tracklist.txt                    # Sync tracking file
    ├── 01 - Artist - Song Title.mp3     # Audio files
    ├── 01 - Artist - Song Title.lrc     # Synchronized lyrics
    ├── 02 - Another Artist - Song.mp3
    ├── 02 - Another Artist - Song.txt   # Plain text lyrics
    └── ...
```

### Tracklist Format

The `tracklist.txt` file tracks sync status:

```
# Playlist-Downloader Tracklist
# Playlist: My Awesome Playlist
# Spotify ID: 37i9dQZF1DX0XUsuxWHRQd
# Created: 2025-07-03 14:30:00
# Total tracks: 50
# Last modified: 2025-07-03 10:15:00
# Lyrics enabled: true

✅🎵 01. Artist A - Song Title (3:24) [spotify:track:abc123]
✅⏳ 02. Artist B - Another Song (4:15) [spotify:track:def456]
⏳⏳ 03. Artist C - Third Track (2:58) [spotify:track:ghi789]
```

**Status Icons:**
- Audio: ✅=Downloaded, ⏳=Pending, ❌=Failed, ⏭️=Skipped
- Lyrics: 🎵=Downloaded, 🚫=Not Found, 🎼=Instrumental, ⏳=Pending

## 🎤 Lyrics Setup

### Genius API (Recommended)

1. Go to [Genius API](https://genius.com/api-clients)
2. Create a new API client
3. Get your access token
4. Set environment variable: `GENIUS_API_KEY=your_token`

**Features:**
- Large database with high accuracy
- Free tier: 60 requests/hour
- Best for English content


**Features:**
- Official Spotify partner
- Free tier: 2000 requests/day
- Synchronized lyrics support
- Multilingual content

## 🛠️ Advanced Usage

### Batch Processing

Process multiple playlists:

```bash
# Create a script for multiple playlists
cat << 'EOF' > download_playlists.sh
#!/bin/bash
playlists=(
    "https://open.spotify.com/playlist/PLAYLIST1"
    "https://open.spotify.com/playlist/PLAYLIST2"
    "https://open.spotify.com/playlist/PLAYLIST3"
)

for playlist in "${playlists[@]}"; do
    echo "Processing: $playlist"
    playlist-dl download "$playlist" --format flac --quality high
done
EOF

chmod +x download_playlists.sh
./download_playlists.sh
```

### Custom Output Structure

```bash
# Download to specific directory with custom format
playlist-dl download "PLAYLIST_URL" \
    --output "/media/music/playlists" \
    --format flac \
    --quality high \
    --concurrent 5
```

### Sync Scheduling

Set up automatic sync with cron:

```bash
# Edit crontab
crontab -e

# Add line for daily sync at 3 AM
0 3 * * * /usr/local/bin/playlist-dl sync "PLAYLIST_URL" >> /var/log/playlist-sync.log 2>&1
```

### Quality Settings

| Quality | Description | Typical Bitrate |
|---------|-------------|-----------------|
| `low` | Small files, mobile-friendly | ~128 kbps |
| `medium` | Balanced quality/size | ~192 kbps |
| `high` | Best available quality | ~256 kbps |

### Format Comparison

| Format | Compression | Quality | File Size | Compatibility |
|--------|-------------|---------|-----------|---------------|
| MP3 | Lossy | Good | Small | Universal |
| M4A/AAC | Lossy | Better | Medium | High |
| FLAC | Lossless | Perfect | Large | Medium |

## 🔧 Troubleshooting

### Common Issues

#### Authentication Problems
```bash
# Clear stored tokens and re-authenticate
playlist-dl auth logout
playlist-dl auth login
```

#### Missing Dependencies
```bash
# Install missing audio processing tools
# Ubuntu/Debian:
sudo apt install ffmpeg

# macOS:
brew install ffmpeg

# Windows (using chocolatey):
choco install ffmpeg
```

#### Permission Errors
```bash
# Fix output directory permissions
chmod 755 ~/Music/Playlist\ Downloads/
```

#### Network Issues
```bash
# Check system diagnostics
playlist-dl doctor

# Test with verbose output
playlist-dl download "PLAYLIST_URL" --verbose
```

### Error Messages

| Error | Solution |
|-------|----------|
| `Spotify client_id and client_secret are required` | Set environment variables or config |
| `YouTube Music API validation failed` | Check internet connection |
| `No lyrics sources are configured` | Set up Genius API keys |
| `Permission denied writing to output directory` | Check directory permissions |

### Debug Mode

Enable verbose logging:

```bash
export PLAYLIST_DL_LOG_LEVEL=DEBUG
playlist-dl download "PLAYLIST_URL" --verbose
```

Check log file:
```bash
tail -f ~/.playlist-downloader/playlist-dl.log
```

## 🤝 Contributing

### Development Setup

1. **Clone and install in development mode**:
```bash
git clone https://github.com/playlist-downloader/playlist-downloader.git
cd playlist-downloader
pip install -e .[dev]
```

2. **Run tests**:
```bash
pytest tests/
```

3. **Code formatting**:
```bash
black src/
flake8 src/
```

### Architecture Overview

```
src/
├── config/          # Configuration management
├── spotify/         # Spotify API integration
├── ytmusic/         # YouTube Music search/download
├── lyrics/          # Multi-source lyrics system
├── audio/           # Audio processing and metadata
├── sync/            # Synchronization logic
├── utils/           # Utilities and helpers
└── main.py          # CLI interface
```

### Adding New Features

1. **New Lyrics Provider**: Implement in `src/lyrics/`
2. **Audio Format**: Extend `src/audio/processor.py`
3. **CLI Commands**: Add to `src/main.py`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Legal Notice

**Important**: This tool is for personal use only. Users are responsible for:

- ✅ Only downloading content they have the right to access
- ✅ Respecting copyright laws in their jurisdiction  
- ✅ Complying with Spotify, YouTube, and other services' Terms of Service
- ✅ Not redistributing downloaded content

The developers are not responsible for any misuse of this software.

## 🙏 Acknowledgments

- **Spotify** - For the Web API that makes playlist access possible
- **YouTube Music** - For providing high-quality audio content
- **Genius** - For comprehensive lyrics database
- **Open Source Libraries** - spotipy, yt-dlp, mutagen, and many others

## 📞 Support

- **Documentation**: Check this README and inline help (`playlist-dl --help`)
- **Issues**: Report bugs on [GitHub Issues](https://github.com/playlist-downloader/playlist-downloader/issues)
- **Discussions**: Join conversations on [GitHub Discussions](https://github.com/playlist-downloader/playlist-downloader/discussions)

## 🗺️ Roadmap

### Upcoming Features

- [ ] **Playlist Collaboration**: Shared playlist management
- [ ] **Smart Playlists**: Auto-updating based on criteria  
- [ ] **Web Interface**: Browser-based GUI
- [ ] **Mobile App**: iOS/Android companion
- [ ] **Cloud Sync**: Cross-device synchronization
- [ ] **Advanced Lyrics**: Karaoke mode and vocal removal
- [ ] **Metadata Enhancement**: MusicBrainz integration
- [ ] **Format Conversion**: Built-in audio conversion tools

### Version History

- **v1.0.0** (Current): Initial release with core functionality
- **v0.9.0**: Beta with lyrics integration
- **v0.8.0**: Alpha with basic download capabilities

---

<div align="center">

**🎵 Happy Downloading! 🎵**

*Made with ❤️ for music lovers everywhere*

</div>