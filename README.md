<div align="center">

# Playlist-Downloader

</div>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>


A comprehensive tool for downloading Spotify playlists locally with YouTube Music integration and automatic lyrics support.

---

<div align="center">

## Features

</div>


### **Core Functionality**
- **Complete Playlist Downloads**: Download entire Spotify playlists with metadata
- **High-Quality Audio**: Best available audio quality from YouTube Music (up to 256kbps AAC)
- **Intelligent Matching**: Advanced algorithm for finding the best YouTube Music matches
- **Multi-Format Support**: M4A, MP3, and FLAC output formats 

### **Lyrics Integration**
- **Multi-Source Lyrics**: Primary support for Genius API
- **Automatic Embedding**: Lyrics embedded directly in audio file metadata
- **Separate Files**: Optional .lrc (synchronized) and .txt lyrics files
- **Smart Matching**: Intelligent lyrics search with quality validation

### **Synchronization**
- **Incremental Updates**: Only download new/changed tracks
- **Smart Reordering**: Detect and handle moved tracks
- **Status Tracking**: Detailed tracklist.txt files for sync state
- **Resume Capability**: Resume interrupted downloads

### **Audio Processing**
- **Silence Trimming**: Automatic removal of silence from start/end
- **Audio Normalization**: EBU R128 loudness normalization
- **Quality Control**: Audio validation and integrity checking
- **Metadata Enhancement**: Complete ID3 tags with album artwork

### **Advanced Features**
- **Parallel Downloads**: Configurable concurrent download limits
- **Rate Limiting**: Respectful API usage with automatic rate limiting
- **Error Recovery**: Smart retry logic with exponential backoff
- **Cross-Platform**: Works on Windows, macOS, and Linux

---

<div align="center">

## Quick Start

</div>


### Prerequisites (Will be installed automatically in a virtual environment if they are not

- Python 3.8+
- FFmpeg (for audio processing)
- Spotify API keys
- Genius API access token (recommended)

---

<div align="center">

### **MacOs automatic installation:**
</div>

Open the terminal and paste the command below:
```bash
cd ~/Desktop && curl -L -o install-macos.sh https://raw.githubusercontent.com/verryx-02/playlist-downloader/main/scripts/install-macos.sh && chmod +x install-macos.sh && ./install-macos.sh && cd ~/Desktop && rm install-macos.sh && cd playlist-downloader
```

<details>
<summary><strong>What does this frightening command do?</strong></summary>
This single command will:

- Navigate to your Desktop
- Download the installation script from GitHub
- Make the script executable
- Run the automatic installer (installs Python, FFmpeg, sets up project)
- Clean up by removing the installer file
- Enter the project directory

You can reed the script [here](https://github.com/Verryx-02/playlist-downloader/blob/main/scripts/install-macos.sh). 
</details>
---

<div align="center">

### **Windows automatic installation:**

</div>


Open the Powershell and paste the command below:
```bash
cd $env:USERPROFILE\Desktop; Invoke-WebRequest -Uri "https://raw.githubusercontent.com/verryx-02/playlist-downloader/main/scripts/install-windows.ps1" -OutFile "install-windows.ps1"; Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\install-windows.ps1; Remove-Item "install-windows.ps1" -Force; cd playlist-downloader
```
<details>
<summary><strong>What does this frightening command do?</strong></summary>
This single command will:

- Navigate to your Desktop
- Download the installation script from GitHub
- Allow script execution (temporarily, for security)
- Run the automatic installer (installs Chocolatey, Python, FFmpeg, sets up project)
- Clean up by removing the installer file
- Enter the project directory
You can reed the script [here](https://github.com/Verryx-02/playlist-downloader/blob/main/scripts/install-windows.ps1). 
</details>
---

<div align="center">

### **Manual installation:**

</div>

For the manual installation see this guide 

---

<div align="center">

## Usage Guide

</div>


### Basic Commands

#### Download a Playlist
```bash
playlist-dl download "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"
```

Options:
- `--format mp3|flac|m4a`: Audio format (default: m4a)
- `--quality low|medium|high`: Audio quality (default: high)
- `--no-lyrics`: Skip lyrics download
- `--output /path/to/output`: Custom output directory
- `--concurrent 5`: Number of parallel downloads

#### Sync an Existing Playlist 
If a certain Playlyst has been modified after you downloaded it, you can only download the changes with the sync command here:
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

### Liked Songs Management

#### **Downloads all your Spotify liked songs to a "My Liked Songs" folder.**
Command:
```bash
playlist-dl download-liked
```

Options:
- `--format mp3|flac|m4a`: Audio format (default: m4a)
- `--quality low|medium|high`: Audio quality (default: high)
- `--no-lyrics`: Skip lyrics download
- `--output /path/to/output`: Custom output directory
- `--concurrent 5`: Number of parallel downloads
- `--dry-run`: Preview what would be downloaded

#### **Synchronizes your liked songs collection, downloading only newly liked tracks since the last sync.**  
Command:
```bash
playlist-dl sync-liked
```  

Options:
- `--output /path/to/output`: Custom output directory

#### Shows the current status of your liked songs collection without downloading anything.
 
**Note**: Your liked songs are automatically organized in a dedicated "My Liked Songs" folder and managed with the same sync tracking system as regular playlists.  
Command:
```bash
playlist-dl check-liked
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

---

## Tracklist Format

The `tracklist.txt` file tracks sync status:

```
# Playlist-Downloader Tracklist
# Playlist: My Awesome Playlist
# Spotify ID: 37i9dQZF...HRQd
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

---

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
| M4A | Lossy | Better | Medium | High |
| FLAC | Lossless | Perfect | Large | Medium |

**NOTE: The flac is not a real lossless audio format because the source was alredy compressed.**
**In this case M4A (default) is the best available quality.**

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Legal Notice

**Important**: This tool is for personal use only. Users are responsible for:

- ✅ Only downloading content they have the right to access
- ✅ Respecting copyright laws in their jurisdiction  
- ✅ Complying with Spotify, YouTube, and other services' Terms of Service
- ✅ Not redistributing downloaded content

The developers are not responsible for any misuse of this software.

---

## Acknowledgments

- **Spotify** - For the Web API that makes playlist access possible
- **YouTube Music** - For providing high-quality audio content
- **Genius** - For comprehensive lyrics database
- **Open Source Libraries** - spotipy, yt-dlp, mutagen, and many others

---

## Support

- **Documentation**: Check this README and inline help (`playlist-dl --help`)
- **Issues**: Report bugs on [GitHub Issues](https://github.com/Verryx-02/playlist-downloader/issues)


---

## Roadmap

### Upcoming Features

- [ ] **Discovery Weakly**: Update the Discovery Weakly playlist diferently
- [ ] **Yt-Music playlist download:** Without going through Spotify
- [ ] **Web Interface**: Browser-based GUI
- [ ] **Mobile App**: iOS/Android companion
- [ ] **Cloud Sync**: Cross-device synchronization
- [ ] **Advanced Lyrics**: Karaoke mode and vocal removal
- [ ] **Metadata Enhancement**: MusicBrainz integration

### Version History

- **v0.9.0-beta** (Current): Initial release with core functionality

