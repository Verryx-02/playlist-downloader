# Playlist-Downloader
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
  
A comprehensive tool for downloading Spotify playlists locally with YouTube Music integration and automatic lyrics support.

---

## Features

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

## Quick Start

### Prerequisites

- Python 3.8+
- FFmpeg (for audio processing)
- Spotify API keys
- Genius API access token (recommended)

### **Step 1: Install a Package Manager**
1. **Install Chocolatey:**
   - Open PowerShell as **Administrator** (Right-click → "Run as administrator")
   - Copy and paste this command:
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

   ```

### **Step 2: Install Python**
1. **Install Python**
    ```powershell
    choco install python

    ```
2. **Verify installation:**
   ```powershell
   python -V

   ```

### **Step 3: Install FFmpeg**
1. **Install FFmpeg:**
   ```powershell
   choco install ffmpeg

   ```

2. **Verify installation:**
   ```powershell
   ffmpeg -version

   ```

### **Step 3: Download and Setup Playlist-Downloader**

1. **Download the project:**  

    **If you have Git:**
   ```powershell
   git clone https://github.com/Verryx-02/playlist-downloader
   cd playlist-downloader
   ```  

    **If you don't have Git:**
    go to https://github.com/Verryx-02/playlist-downloader  
    Click on the green botton "Code"  
    Click on "download zip"  
    extract the zip on Desktop.   
    You can delete the zip file now if you want  

    **Enter in the project directory**
    ```powershell
    cd C:\Users\$env:USERNAME\Desktop\playlist-downloader*
    ```

2.	**Create a virtual environment**:
```bash
python -m venv .venv

```

3. **Activate the virtual environment**

**On Windows:**
```bash
.venv\Scripts\activate

```

**On Linux/macOS:**
```bash
source .venv/bin/activate

```

4. **Install dependencies**:
```bash
pip install -r requirements.txt

```

5. **Install the package**:
```bash
pip install -e .

```

---

## SSH Tunnel Setup (Required for Authentication)

**Why needed:** Spotify needs to redirect you after authorization.   
The SSH tunnel makes your computer temporarily reachable from the internet for this callback.

1. **In a separate terminal window, run:**
   ```powershell
   ssh -R 80:localhost:8080 nokey@localhost.run
   ```

2. **The service will generate a giant QR Code and give you a URL like:**
   ```
   https://abc123.lhr.life
   ```

3. **Save this link in a temporary file for now and add /callback at the end of the link.**
**the link have to be like this:**
   ```bash
   https://abc123.lhr.life/callback
   ```

4. **Do NOT close the ssh tunnel (the terminal with the giant QR)**

## Spotify Configuration

### **Step 1: Create Spotify App**

1. **Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)**
2. **Login** with your Spotify account  
3. Click **"Create an App"**  
4. Fill out the form:  
   - **App name:**
   ```bash
   Playlist Downloader
   ```

   - **App description:** 

   ```bash
   Personal music downloader`
   ```

   - **Website:** 
   ```bash
   http://localhost
   ```

   - **⚠️Redirect URI: use the link saved before. The link below is just an example. Don't copy it⚠️** 
   ```bash
   https://abc123.lhr.life/callback
   ```

   - **Select [x]Web API**  

5. **Click "Save"**
6. **Copy your Client ID and Client Secret in the same temporary file of the link**

### **Step 2: Configure the Project**

1. **Open the configuration file:**
   ```powershell
   notepad config\config_example.yaml
   ```

2. **Update Spotify credentials:**
   ```yaml
   spotify:
     client_id: "YOUR_CLIENT_ID_HERE"
     client_secret: "YOUR_CLIENT_SECRET_HERE"
     redirect_url: "YOUR_COPIED_LINK"
   ```

3. **Save the file**

4. **Rename the config_example.yaml file to**
    ```bash
    config.yaml
    ```

---


## First Use

### **Step 1: Spotify Authentication**

1. **Make sure your SSH tunnel is still running**
2. **Run login command:**
   ```powershell
   playlist-dl auth login
   ```

3. **The browser will open automatically to Spotify**
4. **Click "Authorize" or "Allow"**

**In the terminal you will see "Enter the authorization code":**
- Copy the **long code** from the redirected URL
- The code looks like: `AQBmA7j8k3L9m2N5o6P7...` and it's very long
- Paste the code in the terminal and press Enter

### **Step 2: System Test**

```powershell
# Check if everything works
playlist-dl doctor

```

### **Step 3: Your First Download**

1. **Find a Spotify playlist:**
   - Go to any Spotify playlist you like
   - Click "Share" → "Copy link"

2. **Download the playlist:**
   ```powershell
   playlist-dl download "https://open.spotify.com/playlist/YOUR_LINK_HERE"
   ```

3. **Files will be saved to:**
   ```
   C:\Users\YourName\Music\Playlist Downloads\Playlist Name\
   ```

---

## Advanced Configuration

### **Change Download Directory**

**Edit config.yaml:**
```yaml
download:
  output_directory: "C:\Music\My_Playlists"
  format: "m4a"          # m4a, mp3, flac
  quality: "high"        # low, medium, high
  concurrency: 3         # parallel downloads
```

### **Configure Lyrics (Optional but Recommended)**

1. **Get Genius API key (for better lyrics):**
   - Go to [genius.com/api-clients](https://genius.com/api-clients)
   - Create new app
   - Copy "Client Access Token"

2. **Add to config.yaml:**
   ```yaml
   lyrics:
     enabled: true
     genius_api_key: "YOUR_GENIUS_KEY_HERE"
     download_separate_files: true
     embed_in_audio: true
   ```

### **Audio Quality Settings**

```yaml
audio:
  trim_silence: true     # Remove silence from start/end
  normalize: false       # Audio normalization (can take longer)
  max_duration: 960      # Skip tracks longer than 16 minutes
  min_duration: 30       # Skip tracks shorter than 30 seconds
```

---

## Usage Guide

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

#### Download Your Liked Songs
**Downloads all your Spotify liked songs to a "My Liked Songs" folder.**
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

#### Sync Liked Songs
**Synchronizes your liked songs collection, downloading only newly liked tracks since the last sync.**
```bash
playlist-dl sync-liked
```

Synchronizes your liked songs collection, downloading only newly liked tracks since the last sync.

Options:
- `--output /path/to/output`: Custom output directory

#### Check Liked Songs Status
```bash
playlist-dl check-liked
```

Shows the current status of your liked songs collection without downloading anything.

**Note**: Your liked songs are automatically organized in a dedicated "My Liked Songs" folder and managed with the same sync tracking system as regular playlists.

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

## Lyrics Setup

### Genius API (Recommended)

1. Go to [Genius API](https://genius.com/api-clients)
2. Create a new API client
3. Get your access token
4. Set environment variable: `GENIUS_API_KEY=your_token`

**Features:**
- Large database with high accuracy
- Free tier: 60 requests/hour
- Best for English content

---

## Advanced Usage

### Batch Processing

Process multiple playlists: (not recommended, but you can try it)

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
| M4A | Lossy | Better | Medium | High |
| FLAC | Lossless | Perfect | Large | Medium |

**NOTE: The flac is not a real lossless audio format because the source was alredy compressed.**
**In this case M4A (default) is the best available quality.**

---

## Troubleshooting

### Common Issues

#### Authentication Problems
```bash
# Clear stored tokens and re-authenticate
playlist-dl auth logout
playlist-dl auth login
```

#### Permission Errors
```bash
# Fix output directory permissions
chmod 755 ~/Music/Playlist\ Downloads/
```

For other issues check the log files. One is created for each playlist:

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
- **Issues**: Report bugs on [GitHub Issues](https://github.com/playlist-downloader/playlist-downloader/issues)
- **Discussions**: Join conversations on [GitHub Discussions](https://github.com/playlist-downloader/playlist-downloader/discussions)

---

## Roadmap

### Upcoming Features

- [ ] **Discovery Weakly**: Update the Discovery Weakly playlist diferently
- [ ] **Web Interface**: Browser-based GUI
- [ ] **Mobile App**: iOS/Android companion
- [ ] **Cloud Sync**: Cross-device synchronization
- [ ] **Advanced Lyrics**: Karaoke mode and vocal removal
- [ ] **Metadata Enhancement**: MusicBrainz integration

### Version History

- **v0.9.0-beta** (Current): Initial release with core functionality

---

<div align="center">

**🎵 Happy Downloading! 🎵**

</div>
