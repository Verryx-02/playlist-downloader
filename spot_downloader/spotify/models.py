"""
Data models for Spotify entities.

This module defines immutable dataclasses representing Spotify objects
like tracks and playlists. These models are used throughout the application
to pass track information between phases.

Design Decisions:
    - All dataclasses are frozen (immutable) to prevent accidental modification
    - Fields match Spotify API response structure where possible
    - Optional fields have sensible defaults
    - Models are independent of database storage format

Usage:
    from spot_downloader.spotify.models import Track, Playlist
    
    track = Track(
        spotify_id="abc123",
        name="Song Title",
        artist="Artist Name",
        ...
    )
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Track:
    """
    Immutable representation of a Spotify track.
    
    This dataclass contains all the metadata fetched from Spotify API
    that is needed for:
        - YouTube Music matching (name, artist, album, duration)
        - File naming (name, artist, track_number)
        - Metadata embedding (all fields)
    
    Attributes:
        spotify_id: Unique Spotify track ID (22-character base62 string).
                    Example: "4cOdK2wGLETKBW3PvgPWqT"
        
        spotify_url: Full Spotify URL for the track.
                     Example: "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        
        name: Track title as it appears on Spotify.
              Example: "Bohemian Rhapsody"
        
        artist: Primary artist name (first artist in the list).
                Used for file naming and primary display.
                Example: "Queen"
        
        artists: List of all artist names for tracks with multiple artists.
                 Example: ["Queen"] or ["Calvin Harris", "Dua Lipa"]
        
        album: Album name.
               Example: "A Night at the Opera"
        
        album_artist: The main artist of the album (may differ from track artist
                      for compilations or features).
                      Example: "Queen"
        
        duration_ms: Track duration in milliseconds.
                     Used for YouTube matching to find correct version.
                     Example: 354320 (about 5:54)
        
        track_number: Position of track within the album.
                      Example: 11
        
        disc_number: Disc number for multi-disc albums.
                     Example: 1
        
        release_date: Release date string in ISO format.
                      May be full date "2024-01-15" or just year "2024".
                      Example: "1975-11-21"
        
        year: Release year extracted from release_date.
              Example: 1975
        
        isrc: International Standard Recording Code, if available.
              Used for more accurate YouTube matching.
              Example: "GBUM71029604"
        
        explicit: Whether the track is marked explicit on Spotify.
                  Example: False
        
        popularity: Spotify popularity score (0-100).
                    Example: 85
        
        cover_url: URL to the highest resolution album cover image.
                   Example: "https://i.scdn.co/image/ab67616d0000b273..."
        
        genres: List of genres from the artist's Spotify profile.
                Note: Spotify doesn't have per-track genres.
                Example: ["rock", "classic rock", "glam rock"]
        
        publisher: Record label / publisher name.
                   Example: "Hollywood Records"
        
        copyright_text: Copyright notice from the album.
                        Example: "(C) 1975 Queen Productions Ltd."

        assigned_number: Track number assigned for file naming.
                         This is calculated based on chronological order of addition
                         to the playlist (oldest = 1, newest = N).
                         None until assigned during PHASE 1.
                         Example: 42

        added_at: ISO timestamp of when the track was added to the playlist.
                  Used for sorting tracks chronologically.
                  Example: "2024-01-15T10:30:00Z"
    
    Class Methods:
        from_spotify_api: Create Track from Spotify API response dict.
        to_database_dict: Convert to dict for database storage.
    
    Example:
        # Creating from Spotify API response
        track = Track.from_spotify_api(spotify_track_data, artist_data, album_data)
        
        # Accessing fields
        print(f"{track.name} by {track.artist}")
        print(f"Duration: {track.duration_ms // 1000} seconds")
    """
    
    # Required fields (always present from Spotify)
    spotify_id: str
    spotify_url: str
    name: str
    artist: str
    artists: tuple[str, ...]  # Tuple for immutability
    album: str
    duration_ms: int
    
    # Fields with defaults (may not always be available)
    album_artist: str = ""
    track_number: int = 1
    disc_number: int = 1
    disc_count: int = 1
    tracks_count: int = 1
    release_date: str = ""
    year: int = 0
    isrc: str | None = None
    explicit: bool = False
    popularity: int = 0
    cover_url: str | None = None
    genres: tuple[str, ...] = field(default_factory=tuple)
    publisher: str = ""
    copyright_text: str = ""
    assigned_number: int | None = None
    added_at: str | None = None

    
    @classmethod
    def from_spotify_api(
        cls,
        track_data: dict[str, Any],
        artist_data: dict[str, Any] | None = None,
        album_data: dict[str, Any] | None = None,
        added_at: str | None = None
    ) -> "Track":
        """
        Create a Track instance from Spotify API response data.
        
        This factory method handles the extraction and normalization of
        data from Spotify's API response format.
        
        Args:
            track_data: The track object from Spotify API.
                        This is the response from spotify.track(track_id) or
                        the 'track' field from playlist_items response.
            artist_data: Optional artist object for genre information.
                         Response from spotify.artist(artist_id).
                         If None, genres will be empty.
            album_data: Optional album object for additional metadata.
                        Response from spotify.album(album_id).
                        If None, uses album data embedded in track_data.
            added_at: Optional ISO timestamp of when track was added to playlist.
                     Passed from the playlist_items wrapper.
        
        Returns:
            Track: A new Track instance populated with the extracted data.
        
        Behavior:
            1. Extract basic track info (id, name, duration, explicit)
            2. Extract artist info (name, list of all artists)
            3. Extract album info (name, release date, track number)
            4. If album_data provided, extract additional metadata
            5. If artist_data provided, extract genres
            6. Construct cover_url from highest-resolution image
            7. Parse release_date to extract year
            8. Return frozen Track instance
        
        Example:
            spotify_client = SpotifyClient()
            track_response = spotify_client.track("4cOdK2wGLETKBW3PvgPWqT")
            artist_response = spotify_client.artist(track_response['artists'][0]['id'])
            album_response = spotify_client.album(track_response['album']['id'])
            
            track = Track.from_spotify_api(track_response, artist_response, album_response)
        
        Note:
            This method mirrors the approach used in spotDL's Song.from_url()
            method for consistency in metadata extraction.
        """
        # Extract basic track info
        spotify_id = track_data["id"]
        spotify_url = track_data["external_urls"]["spotify"]
        name = track_data["name"]
        duration_ms = track_data["duration_ms"]
        explicit = track_data.get("explicit", False)
        popularity = track_data.get("popularity", 0)
        
        # Extract artists
        artists_list = [a["name"] for a in track_data.get("artists", [])]
        artist = artists_list[0] if artists_list else "Unknown Artist"
        artists = tuple(artists_list)
        
        # Extract ISRC
        isrc = track_data.get("external_ids", {}).get("isrc")
        
        # Extract album info from track_data (basic)
        album_info = track_data.get("album", {})
        album_name = album_info.get("name", "Unknown Album")
        track_number = track_data.get("track_number", 1)
        disc_number = track_data.get("disc_number", 1)
        
        # Get album artist from album info
        album_artists = album_info.get("artists", [])
        album_artist = album_artists[0]["name"] if album_artists else artist
        
        # Get release date from album
        release_date = album_info.get("release_date", "")
        
        # Parse year from release_date
        year = 0
        if release_date:
            try:
                year = int(release_date[:4])
            except (ValueError, IndexError):
                year = 0
        
        # Get cover URL - find highest resolution image
        cover_url = None
        images = album_info.get("images", [])
        if images:
            # Sort by size (width * height) descending, take first
            try:
                best_image = max(
                    images,
                    key=lambda img: (img.get("width") or 0) * (img.get("height") or 0)
                )
                cover_url = best_image.get("url")
            except (ValueError, TypeError):
                # Fallback to first image if sorting fails
                cover_url = images[0].get("url") if images else None
        
        # Default values that may be overridden by album_data
        publisher = ""
        copyright_text = ""
        disc_count = 1
        tracks_count = album_info.get("total_tracks", 1)
        genres: tuple[str, ...] = ()
        
        # If we have full album data, extract additional metadata
        if album_data:
            publisher = album_data.get("label", "")
            
            # Get copyright
            copyrights = album_data.get("copyrights", [])
            if copyrights:
                copyright_text = copyrights[0].get("text", "")
            
            # Get disc count from last track in album
            album_tracks = album_data.get("tracks", {}).get("items", [])
            if album_tracks:
                disc_count = album_tracks[-1].get("disc_number", 1)
            
            tracks_count = album_data.get("total_tracks", tracks_count)
            
            # Get better release date from album if available
            if album_data.get("release_date"):
                release_date = album_data["release_date"]
                try:
                    year = int(release_date[:4])
                except (ValueError, IndexError):
                    pass
            
            # Get better cover from album_data if available
            album_images = album_data.get("images", [])
            if album_images:
                try:
                    best_image = max(
                        album_images,
                        key=lambda img: (img.get("width") or 0) * (img.get("height") or 0)
                    )
                    cover_url = best_image.get("url")
                except (ValueError, TypeError):
                    pass
        
        # If we have artist data, extract genres
        if artist_data:
            genres = tuple(artist_data.get("genres", []))
        
        return cls(
            spotify_id=spotify_id,
            spotify_url=spotify_url,
            name=name,
            artist=artist,
            artists=artists,
            album=album_name,
            duration_ms=duration_ms,
            album_artist=album_artist,
            track_number=track_number,
            disc_number=disc_number,
            disc_count=disc_count,
            tracks_count=tracks_count,
            release_date=release_date,
            year=year,
            isrc=isrc,
            explicit=explicit,
            popularity=popularity,
            cover_url=cover_url,
            genres=genres,
            publisher=publisher,
            copyright_text=copyright_text,
            assigned_number=None,  # Assigned later by _assign_track_numbers
            added_at=added_at
        )
    
    def to_database_dict(self) -> dict[str, Any]:
        """
        Convert Track to a dictionary for database storage.
        
        Returns:
            Dictionary containing all track fields in a format suitable
            for JSON serialization and storage in the database.
        
        The returned dict includes:
            - All scalar fields as-is
            - Tuple fields (artists, genres) converted to lists
            - A 'metadata' key with the full track data for future use
        
        Example:
            track = Track(...)
            db.add_track(playlist_id, track.spotify_id, track.to_database_dict())
        """
        return {
            "name": self.name,
            "artist": self.artist,
            "artists": list(self.artists),
            "album": self.album,
            "album_artist": self.album_artist,
            "duration_ms": self.duration_ms,
            "track_number": self.track_number,
            "disc_number": self.disc_number,
            "disc_count": self.disc_count,
            "tracks_count": self.tracks_count,
            "release_date": self.release_date,
            "year": self.year,
            "isrc": self.isrc,
            "explicit": self.explicit,
            "popularity": self.popularity,
            "cover_url": self.cover_url,
            "genres": list(self.genres),
            "publisher": self.publisher,
            "copyright_text": self.copyright_text,
            "spotify_url": self.spotify_url,
            "assigned_number": self.assigned_number,
            "added_at": self.added_at,
        }
    
    @classmethod
    def from_database_dict(cls, track_id: str, data: dict[str, Any]) -> "Track":
        """
        Reconstruct a Track instance from database dictionary.
        
        This is the inverse of to_database_dict(), used when running
        phases 2-5 separately from phase 1.
        
        Args:
            track_id: The Spotify track ID (stored as dict key in database).
            data: The track data dictionary from the database.
                This is the dict returned by database.get_track() or
                items in database.get_tracks_without_youtube_url().
        
        Returns:
            Track: A new Track instance with all fields populated.
        
        Behavior:
            1. Extract all fields from the data dictionary
            2. Convert list fields back to tuples (artists, genres)
            3. Handle optional fields with appropriate defaults
            4. Return frozen Track instance
        
        Field Mapping:
            Database lists → Track tuples:
            - data["artists"] (list) → self.artists (tuple)
            - data["genres"] (list) → self.genres (tuple)
            
            Required fields (must exist in data):
            - name, artist, album, duration_ms, spotify_url
            
            Optional fields (use defaults if missing):
            - All other fields per Track dataclass defaults
        
        Example:
            # When running phase 2 separately
            track_dicts = database.get_tracks_without_youtube_url(playlist_id)
            tracks = [
                Track.from_database_dict(d["track_id"], d)
                for d in track_dicts
            ]
            
            # Now tracks is list[Track] ready for match_tracks_phase2()
        
        Note:
            The database stores lists for JSON compatibility, but Track
            uses tuples for immutability. This method handles the conversion.
        """
        # Convert lists to tuples
        artists = tuple(data.get("artists", [data.get("artist", "Unknown Artist")]))
        genres = tuple(data.get("genres", []))
        
        return cls(
            spotify_id=track_id,
            spotify_url=data.get("spotify_url", f"https://open.spotify.com/track/{track_id}"),
            name=data.get("name", "Unknown"),
            artist=data.get("artist", "Unknown Artist"),
            artists=artists,
            album=data.get("album", "Unknown Album"),
            duration_ms=data.get("duration_ms", 0),
            album_artist=data.get("album_artist", ""),
            track_number=data.get("track_number", 1),
            disc_number=data.get("disc_number", 1),
            disc_count=data.get("disc_count", 1),
            tracks_count=data.get("tracks_count", 1),
            release_date=data.get("release_date", ""),
            year=data.get("year", 0),
            isrc=data.get("isrc"),
            explicit=data.get("explicit", False),
            popularity=data.get("popularity", 0),
            cover_url=data.get("cover_url"),
            genres=genres,
            publisher=data.get("publisher", ""),
            copyright_text=data.get("copyright_text", ""),
            assigned_number=data.get("assigned_number"),
            added_at=data.get("added_at"),
        )

    @property
    def search_query(self) -> str:
        """
        Generate a search query string for YouTube Music matching.
        
        Returns:
            A search string in the format "Artist Name - Track Name"
            suitable for searching on YouTube Music.
        
        Example:
            track.search_query  # "Queen - Bohemian Rhapsody"
        """
        return f"{self.artist} - {self.name}"
    
    @property
    def duration_seconds(self) -> int:
        """
        Get track duration in seconds (rounded down).
        
        Returns:
            Duration in whole seconds.
        
        Example:
            track.duration_seconds  # 354 (for 354320 ms)
        """
        return self.duration_ms // 1000


@dataclass(frozen=True)
class Playlist:
    """
    Immutable representation of a Spotify playlist.
    
    This dataclass contains playlist metadata and the list of tracks.
    Used to pass playlist information from PHASE 1 to subsequent phases.
    
    Attributes:
        spotify_id: Unique Spotify playlist ID.
                    Example: "37i9dQZF1DXcBWIGoYBM5M"
        
        spotify_url: Full Spotify URL for the playlist.
                     Example: "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        
        name: Playlist name as it appears on Spotify.
              Example: "Today's Top Hits"
        
        description: Playlist description text (may contain HTML).
                     Example: "The hottest 50 tracks right now."
        
        owner_name: Display name of the playlist owner.
                    Example: "Spotify"
        
        cover_url: URL to the playlist cover image.
                   Example: "https://i.scdn.co/image/ab67706f0000..."
        
        tracks: Tuple of Track objects in playlist order.
                Tuple for immutability.
        
        total_tracks: Total number of tracks in the playlist.
                      May differ from len(tracks) if some tracks failed to load.
    
    Class Methods:
        from_spotify_api: Create Playlist from Spotify API response.
    
    Example:
        playlist = Playlist.from_spotify_api(playlist_data, tracks)
        print(f"{playlist.name}: {playlist.total_tracks} tracks")
        for track in playlist.tracks:
            print(f"  - {track.name}")
    """
    
    spotify_id: str
    spotify_url: str
    name: str
    description: str
    owner_name: str
    cover_url: str | None
    tracks: tuple[Track, ...]
    total_tracks: int
    
    @classmethod
    def from_spotify_api(
        cls,
        playlist_data: dict[str, Any],
        tracks: list[Track]
    ) -> "Playlist":
        """
        Create a Playlist instance from Spotify API response data.
        
        Args:
            playlist_data: The playlist object from Spotify API.
                          Response from spotify.playlist(playlist_id).
            tracks: List of Track objects already parsed from the playlist.
        
        Returns:
            Playlist: A new Playlist instance.
        
        Behavior:
            1. Extract playlist ID from URI or URL
            2. Extract name, description, owner info
            3. Find highest-resolution cover image
            4. Convert tracks list to tuple
            5. Return frozen Playlist instance
        
        Example:
            spotify_client = SpotifyClient()
            playlist_response = spotify_client.playlist(playlist_url)
            tracks = [Track.from_spotify_api(t) for t in ...]
            playlist = Playlist.from_spotify_api(playlist_response, tracks)
        """
        # Extract playlist ID
        spotify_id = playlist_data.get("id", "")
        
        # Extract URL
        spotify_url = playlist_data.get("external_urls", {}).get(
            "spotify", 
            f"https://open.spotify.com/playlist/{spotify_id}"
        )
        
        # Extract basic info
        name = playlist_data.get("name", "Unknown Playlist")
        description = playlist_data.get("description", "")
        
        # Extract owner info
        owner = playlist_data.get("owner", {})
        owner_name = owner.get("display_name", owner.get("id", "Unknown"))
        
        # Find highest-resolution cover image
        cover_url = None
        images = playlist_data.get("images", [])
        if images:
            try:
                best_image = max(
                    images,
                    key=lambda img: (img.get("width") or 0) * (img.get("height") or 0)
                )
                cover_url = best_image.get("url")
            except (ValueError, TypeError):
                cover_url = images[0].get("url") if images else None
        
        # Get total tracks from API response
        total_tracks = playlist_data.get("tracks", {}).get("total", len(tracks))
        
        return cls(
            spotify_id=spotify_id,
            spotify_url=spotify_url,
            name=name,
            description=description,
            owner_name=owner_name,
            cover_url=cover_url,
            tracks=tuple(tracks),
            total_tracks=total_tracks
        )
    
    @property
    def track_count(self) -> int:
        """
        Get the number of successfully parsed tracks.
        
        Returns:
            Number of Track objects in the tracks tuple.
            May be less than total_tracks if some failed to parse.
        """
        return len(self.tracks)


@dataclass(frozen=True)
class LikedSongs:
    """
    Immutable representation of a user's Liked Songs (Saved Tracks).
    
    Liked Songs is a special "playlist" that requires user authentication
    to access. It doesn't have a playlist ID like regular playlists.
    
    Attributes:
        tracks: Tuple of Track objects in order added (newest first).
        total_tracks: Total number of liked songs.
    
    Note:
        Unlike playlists, Liked Songs has no URL, name, or cover.
        The user must authenticate with --user-auth to access this.
    """
    
    tracks: tuple[Track, ...]
    total_tracks: int
    
    @classmethod
    def from_spotify_api(cls, tracks: list[Track], total: int) -> "LikedSongs":
        """
        Create a LikedSongs instance from parsed tracks.
        
        Args:
            tracks: List of Track objects from user's saved tracks.
            total: Total count from Spotify API response.
        
        Returns:
            LikedSongs: A new LikedSongs instance.
        """
        return cls(
            tracks=tuple(tracks),
            total_tracks=total
        )
    
    @property
    def track_count(self) -> int:
        """Get the number of successfully parsed tracks."""
        return len(self.tracks)