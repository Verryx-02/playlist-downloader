# Known Issues and Improvements

This document tracks problems I've identified while developing spot-downloader, along with proposed solutions and their current status.

---

## 1. Duplicate Track Handling Across Playlists

**Status:** Not implemented yet | **Priority:** High

### The Problem

Right now, if you download two playlists that share songs, the app will:
- Download the same song twice (wasting storage space)
- Run the YouTube Music matching algorithm again for that song (wasting time and API quota)
- Re-fetch all the metadata and lyrics (wasting bandwidth)

There's also a bigger issue: if you use `--replace` to fix a bad match for a song that's in multiple playlists, it only gets fixed in one playlist. The other playlists still have the old, wrong version. This creates inconsistencies in the database.

But here's the catch: users still need to *see* the duplicate songs in each playlist. If a song appears in 3 playlists, they should see it in all 3.

#### Example
```
Playlist1: 1-song-a.m4a, 2-song-b.m4a, 3-song-c.m4a
Playlist2: 1-song-c.m4a

Both playlists should show song-c, but the file should only be stored once.
```

### My Solution

I'm planning to restructure the database from `Playlist → Tracks` to `Global Tracks ← Playlists`:

The idea is to have a central table of all unique tracks (identified by `spotify_id`), containing:
- YouTube match information
- All metadata (artist, album, duration, etc.)
- File path to the downloaded audio
- Lyrics

Then playlists would reference these global tracks through a many-to-many relationship. When downloading a new playlist:

1. For each track, check if it already exists in the global registry
2. If yes: just create a reference (and maybe a hard link in the filesystem)
3. If no: run the full matching and download process, then add it to the global registry

This way, `--replace` would work on the global track and automatically propagate to all playlists that contain it.


---

## 2. Inconsistent Track Naming Across Playlists

**Status:** Needs investigation

### The Problem

The same song has different filenames depending on which playlist it's in:

```
Playlist A: 3-song-c.m4a
Playlist B: 1-song-c.m4a
Playlist C: 7-song-c.m4a
```

This happens because filenames include the track's position number in each playlist. This makes it confusing to manage files and ties into issue #1 above.


---

## 3. Inefficient Multi-Playlist Synchronization

**Status:** Not implemented yet

### The Problem

If you want to sync 5 playlists and your liked songs, you have to run the command 6 times:

```bash
spot-downloader --sync <playlist_url_1>
spot-downloader --sync <playlist_url_2>
spot-downloader --sync <playlist_url_3>
spot-downloader --sync <playlist_url_4>
spot-downloader --sync <playlist_url_5>
spot-downloader --sync --liked
```

This is annoying and tedious.

### My Solution

Make `--sync` sync everything by default:

```bash
# This syncs all playlists and liked tracks (requires Spotify login)
spot-downloader --sync

# New flag for syncing just playlists (no login needed)
spot-downloader --sync-no-login
```

Much simpler for daily use.

---

## 4. Log Files Cluttering the Download Directory

**Status:** Not implemented yet | **Priority:** Low

### The Problem

Log files get saved in the main directory:

```
Desktop
└─── Music
    └── SpotDownloader
        ├── database.db
        ├── download_failures.log
        ├── log_errors.log
        ├── log_full.log
        ├── lyrics_failures.log
        └── match_close_alternatives.log
```

This mixes user content with application logs.

### My Solution

Create a `logs/` subdirectory to keep things organized:

```
Desktop
└─── Music
    └── SpotDownloader
        ├── database.db
        └── logs
            ├── download_failures.log
            ├── log_errors.log
            ├── log_full.log
            ├── lyrics_failures.log
            └── match_close_alternatives.log
```

---

## 5. Missing Error Logs for Failed Downloads

**Status:** Under investigation

### The Problem

When downloads fail, the warnings don't get saved to `log_errors.log` like they should.

---

## 6. Log Files Get Overwritten

**Status:** Under investigation

### The Problem

Every time you run the program, it overwrites the previous log files. You lose all the historical data.

Current behavior:
```
Run 1: Creates log_errors.log
Run 2: Overwrites log_errors.log (data from Run 1 is gone)
```

What should happen:
```
Run 1: Creates log_errors_2024-12-19_14-30-45.log
Run 2: Creates log_errors_2024-12-19_15-22-13.log
```

---

## 7. Intermittent Error During YouTube Matching

**Status:** Under investigation | **Priority:** Low

### The Problem

Sometimes during Phase 2 (YouTube Music matching), a non-blocking error occurs. It doesn't crash the program, but I haven't been able to track down exactly what it is or when it happens. 


---

## 8. Removals and moves of songs in Spotify playlists not managed

**Status:** Under investigation | **Priority:** Medium because I don't remove or move songs from my playlists but someone does

### The Problem

Someone could decide to remove a song from a playlist. In 
in this case a data consistency problem would be created in the database



## 8. --2 applies only on last --1

**Status:** Under investigation | **Priority:** Medium 

### The Problem

If you run it in this order:
spot --url <url-1> --1
spot --url <url-2> --1
spot --2

The --2 will only be applied to songs in the playlist with url <url-2>.