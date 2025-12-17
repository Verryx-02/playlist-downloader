"""
Spotify API client singleton for spot-downloader.

This module provides a singleton wrapper around the spotipy library,
ensuring that only one Spotify client instance exists throughout
the application lifetime.

Singleton Pattern:
    SpotifyClient uses the singleton pattern - it must be initialized
    once with init(), and subsequent calls to SpotifyClient() return
    the same instance. Attempting to call init() twice raises an error.

Authentication:
    Two authentication modes are supported:
    1. Client Credentials (default): Uses client_id and client_secret only.
       Suitable for accessing public playlists and track metadata.
    2. User Auth: Uses OAuth flow for accessing private data like Liked Songs.
       Requires user to authenticate via browser.

Usage:
    # At application startup (once only)
    from spot_downloader.spotify.client import SpotifyClient
    
    SpotifyClient.init(
        client_id="your_client_id",
        client_secret="your_client_secret"
    )
    
    # Later, anywhere in the code
    client = SpotifyClient()
    playlist = client.playlist("https://open.spotify.com/playlist/...")
    
Design:
    This implementation mirrors spotDL's SpotifyClient singleton pattern
    for consistency and to leverage proven authentication handling.
"""

from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

from spot_downloader.core.exceptions import SpotifyError


class SpotifyClientMeta(type):
    """
    Metaclass implementing the singleton pattern for SpotifyClient.
    
    This metaclass ensures:
    1. SpotifyClient cannot be instantiated before init() is called
    2. init() can only be called once
    3. After init(), SpotifyClient() always returns the same instance
    
    Attributes:
        _instance: The singleton SpotifyClient instance, or None.
        _initialized: Flag indicating whether init() has been called.
    """
    
    _instance: "SpotifyClient | None" = None
    _initialized: bool = False
    
    def __call__(cls) -> "SpotifyClient":
        """
        Get the SpotifyClient singleton instance.
        
        Returns:
            The singleton SpotifyClient instance.
        
        Raises:
            SpotifyError: If init() has not been called yet.
                         Error message instructs user to call init() first.
        """
        if cls._instance is None:
            raise SpotifyError(
                "SpotifyClient not initialized. Call SpotifyClient.init("
                "client_id, client_secret) first.",
                is_auth_error=True
            )
        return cls._instance
    
    def init(
        cls,
        client_id: str,
        client_secret: str,
        user_auth: bool = False
    ) -> "SpotifyClient":
        """
        Initialize the SpotifyClient singleton.
        
        This method must be called exactly once at application startup,
        before any other SpotifyClient operations.
        
        Args:
            client_id: Spotify application client ID from Developer Dashboard.
            client_secret: Spotify application client secret.
            user_auth: If True, use OAuth flow for user authentication.
                       Required for accessing Liked Songs.
                       If False (default), use client credentials flow.
        
        Returns:
            The initialized SpotifyClient singleton instance.
        
        Raises:
            SpotifyError: If init() has already been called (singleton violation).
            SpotifyError: If authentication fails (invalid credentials, network error).
        
        Behavior:
            1. Check that init() hasn't been called before
            2. Create spotipy.Spotify instance with appropriate auth
            3. Test the connection by fetching client info
            4. Store instance as singleton
            5. Return the instance
        
        Authentication Flows:
            Client Credentials (user_auth=False):
                - Uses SpotifyClientCredentials
                - No user interaction required
                - Can access public playlists, track/album/artist info
                - Cannot access Liked Songs or private playlists
            
            User Auth (user_auth=True):
                - Uses SpotifyOAuth with user-library-read scope
                - Opens browser for user to authenticate
                - Can access all user data including Liked Songs
                - Caches token for future runs
        
        Example:
            # Simple initialization for public playlists
            SpotifyClient.init(
                client_id=config.spotify.client_id,
                client_secret=config.spotify.client_secret
            )
            
            # With user auth for Liked Songs access
            SpotifyClient.init(
                client_id=config.spotify.client_id,
                client_secret=config.spotify.client_secret,
                user_auth=True
            )
        """
        if cls._initialized:
            raise SpotifyError(
                "SpotifyClient.init() has already been called. "
                "Use SpotifyClient() to get the existing instance.",
                is_auth_error=True
            )
        
        try:
            if user_auth:
                # OAuth flow for user data access (Liked Songs, private playlists)
                auth_manager = SpotifyOAuth(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri="http://127.0.0.1:8888/callback",
                    scope="user-library-read playlist-read-private",
                    open_browser=True
                )
            else:
                # Client credentials flow for public data only
                auth_manager = SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret
                )
            
            # Create spotipy instance
            spotify_instance = spotipy.Spotify(auth_manager=auth_manager)
            
            # Test connection by making a simple API call
            # For client credentials, we can't call current_user(), so we test differently
            if user_auth:
                spotify_instance.current_user()
            else:
                # Test with a simple search to verify credentials work
                spotify_instance.search(q="test", type="track", limit=1)
            
            # Create and store singleton instance
            instance = super().__call__(spotify_instance, user_auth)
            cls._instance = instance
            cls._initialized = True
            
            return instance
            
        except spotipy.SpotifyException as e:
            raise SpotifyError(
                f"Spotify authentication failed: {e}",
                details={"original_error": str(e)},
                is_auth_error=True
            ) from e
        except Exception as e:
            raise SpotifyError(
                f"Failed to initialize Spotify client: {e}",
                details={"original_error": str(e)},
                is_auth_error=True
            ) from e
    
    def is_initialized(cls) -> bool:
        """
        Check if the SpotifyClient has been initialized.
        
        Returns:
            True if init() has been called, False otherwise.
        
        Use Case:
            Useful for checking state before attempting operations,
            or for testing.
        """
        return cls._initialized
    
    def reset(cls) -> None:
        """
        Reset the singleton state (for testing only).
        
        This method clears the singleton instance, allowing init()
        to be called again. Should only be used in tests.
        
        Warning:
            Do not use this in production code. It exists only to
            enable proper test isolation.
        """
        cls._instance = None
        cls._initialized = False


class SpotifyClient(metaclass=SpotifyClientMeta):
    """
    Singleton Spotify API client.
    
    This class wraps spotipy.Spotify and provides methods for accessing
    Spotify data. It uses the singleton pattern - only one instance
    exists throughout the application.
    
    Initialization:
        Must be initialized with SpotifyClient.init() before use.
        See SpotifyClientMeta.init() for details.
    
    Attributes:
        _spotify: The underlying spotipy.Spotify instance.
        _user_auth: Whether user authentication is enabled.
    
    Thread Safety:
        The spotipy library handles its own session management.
        SpotifyClient methods are generally thread-safe for reading.
    
    Rate Limiting:
        Spotify API has rate limits. The spotipy library handles
        automatic retries with backoff. If rate limited, methods
        may block temporarily before retrying.
    
    Example:
        # After init() has been called
        client = SpotifyClient()
        
        # Get playlist info
        playlist = client.playlist("https://open.spotify.com/playlist/...")
        
        # Get track info
        track = client.track("https://open.spotify.com/track/...")
    """
    
    def __init__(self, spotify_instance: spotipy.Spotify, user_auth: bool) -> None:
        """
        Initialize the SpotifyClient instance.
        
        Note:
            This constructor is called by the metaclass init() method.
            Do not call directly - use SpotifyClient.init() instead.
        
        Args:
            spotify_instance: Configured spotipy.Spotify instance.
            user_auth: Whether user authentication is enabled.
        """
        self._spotify = spotify_instance
        self._user_auth = user_auth
    
    @property
    def has_user_auth(self) -> bool:
        """
        Check if user authentication is enabled.
        
        Returns:
            True if initialized with user_auth=True, False otherwise.
        
        Use Case:
            Check before attempting to access Liked Songs.
        """
        return self._user_auth
    
    # =========================================================================
    # Track Operations
    # =========================================================================
    
    def track(self, track_id_or_url: str) -> dict[str, Any]:
        """
        Get track metadata from Spotify.
        
        Args:
            track_id_or_url: Either a Spotify track ID or full URL.
                            ID example: "4cOdK2wGLETKBW3PvgPWqT"
                            URL example: "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        
        Returns:
            Dictionary containing full track metadata from Spotify API.
            See Spotify Web API documentation for structure.
        
        Raises:
            SpotifyError: If track not found (404).
            SpotifyError: If rate limited (after retries exhausted).
            SpotifyError: If network error occurs.
        
        Example:
            track_data = client.track("4cOdK2wGLETKBW3PvgPWqT")
            print(track_data['name'])  # "Song Title"
        """
        try:
            result = self._spotify.track(track_id_or_url)
            if result is None:
                raise SpotifyError(
                    f"Track not found: {track_id_or_url}",
                    details={"track_id": track_id_or_url}
                )
            return result
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    f"Rate limited while fetching track: {track_id_or_url}",
                    details={"track_id": track_id_or_url, "http_status": 429},
                    is_rate_limit=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch track: {e}",
                details={"track_id": track_id_or_url, "original_error": str(e)}
            ) from e
    
    def tracks(self, track_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get metadata for multiple tracks in a single request.
        
        Args:
            track_ids: List of Spotify track IDs (max 50 per request).
                      If more than 50, multiple requests are made.
        
        Returns:
            List of track metadata dictionaries.
            Order matches input order.
            None entries for tracks that couldn't be fetched.
        
        Raises:
            SpotifyError: If rate limited (after retries exhausted).
            SpotifyError: If network error occurs.
        
        Performance:
            Use this instead of multiple track() calls when fetching
            many tracks. Spotify allows up to 50 tracks per request.
        """
        if not track_ids:
            return []
        
        results: list[dict[str, Any]] = []
        
        try:
            # Process in batches of 50 (Spotify API limit)
            for i in range(0, len(track_ids), 50):
                batch = track_ids[i:i + 50]
                response = self._spotify.tracks(batch)
                if response and "tracks" in response:
                    results.extend(response["tracks"])
                else:
                    # Add None placeholders for failed batch
                    results.extend([None] * len(batch))
            
            return results
            
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    "Rate limited while fetching tracks batch",
                    details={"batch_size": len(track_ids), "http_status": 429},
                    is_rate_limit=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch tracks batch: {e}",
                details={"batch_size": len(track_ids), "original_error": str(e)}
            ) from e
    
    # =========================================================================
    # Artist Operations
    # =========================================================================
    
    def artist(self, artist_id_or_url: str) -> dict[str, Any]:
        """
        Get artist metadata from Spotify.
        
        Args:
            artist_id_or_url: Either a Spotify artist ID or full URL.
        
        Returns:
            Dictionary containing artist metadata including genres.
        
        Raises:
            SpotifyError: If artist not found or network error.
        
        Use Case:
            Primary use is to fetch genre information, which Spotify
            only provides at the artist level, not track level.
        """
        try:
            result = self._spotify.artist(artist_id_or_url)
            if result is None:
                raise SpotifyError(
                    f"Artist not found: {artist_id_or_url}",
                    details={"artist_id": artist_id_or_url}
                )
            return result
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    f"Rate limited while fetching artist: {artist_id_or_url}",
                    details={"artist_id": artist_id_or_url, "http_status": 429},
                    is_rate_limit=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch artist: {e}",
                details={"artist_id": artist_id_or_url, "original_error": str(e)}
            ) from e
    
    def artists(self, artist_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get metadata for multiple artists in a single request.
        
        Args:
            artist_ids: List of Spotify artist IDs (max 50 per request).
                       If more than 50, multiple requests are made.
        
        Returns:
            List of artist metadata dictionaries.
            Order matches input order.
            None entries for artists that couldn't be fetched.
        
        Raises:
            SpotifyError: If rate limited (after retries exhausted).
            SpotifyError: If network error occurs.
        
        Performance:
            Use this instead of multiple artist() calls when fetching
            genres for many tracks. Spotify allows up to 50 artists per request.
        """
        if not artist_ids:
            return []
        
        results: list[dict[str, Any]] = []
        
        try:
            # Process in batches of 50 (Spotify API limit)
            for i in range(0, len(artist_ids), 50):
                batch = artist_ids[i:i + 50]
                response = self._spotify.artists(batch)
                if response and "artists" in response:
                    results.extend(response["artists"])
                else:
                    results.extend([None] * len(batch))
            
            return results
            
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    "Rate limited while fetching artists batch",
                    details={"batch_size": len(artist_ids), "http_status": 429},
                    is_rate_limit=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch artists batch: {e}",
                details={"batch_size": len(artist_ids), "original_error": str(e)}
            ) from e
    
    # =========================================================================
    # Album Operations
    # =========================================================================
    
    def album(self, album_id_or_url: str) -> dict[str, Any]:
        """
        Get album metadata from Spotify.
        
        Args:
            album_id_or_url: Either a Spotify album ID or full URL.
        
        Returns:
            Dictionary containing album metadata including:
            - Label/publisher
            - Copyright info
            - Full release date
            - Track list
        
        Raises:
            SpotifyError: If album not found or network error.
        """
        try:
            result = self._spotify.album(album_id_or_url)
            if result is None:
                raise SpotifyError(
                    f"Album not found: {album_id_or_url}",
                    details={"album_id": album_id_or_url}
                )
            return result
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    f"Rate limited while fetching album: {album_id_or_url}",
                    details={"album_id": album_id_or_url, "http_status": 429},
                    is_rate_limit=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch album: {e}",
                details={"album_id": album_id_or_url, "original_error": str(e)}
            ) from e
    
    def albums(self, album_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get metadata for multiple albums in a single request.
        
        Args:
            album_ids: List of Spotify album IDs (max 20 per request).
                      If more than 20, multiple requests are made.
        
        Returns:
            List of album metadata dictionaries.
            Order matches input order.
            None entries for albums that couldn't be fetched.
        
        Raises:
            SpotifyError: If rate limited (after retries exhausted).
            SpotifyError: If network error occurs.
        
        Performance:
            Use this instead of multiple album() calls when fetching
            publisher/copyright for many tracks. Spotify allows up to
            20 albums per request.
        """
        if not album_ids:
            return []
        
        results: list[dict[str, Any]] = []
        
        try:
            # Process in batches of 20 (Spotify API limit for albums)
            for i in range(0, len(album_ids), 20):
                batch = album_ids[i:i + 20]
                response = self._spotify.albums(batch)
                if response and "albums" in response:
                    results.extend(response["albums"])
                else:
                    results.extend([None] * len(batch))
            
            return results
            
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    "Rate limited while fetching albums batch",
                    details={"batch_size": len(album_ids), "http_status": 429},
                    is_rate_limit=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch albums batch: {e}",
                details={"batch_size": len(album_ids), "original_error": str(e)}
            ) from e
    
    # =========================================================================
    # Playlist Operations
    # =========================================================================
    
    def playlist(self, playlist_id_or_url: str) -> dict[str, Any]:
        """
        Get playlist metadata from Spotify.
        
        Args:
            playlist_id_or_url: Either a Spotify playlist ID or full URL.
        
        Returns:
            Dictionary containing playlist metadata (name, description,
            owner, images). Does NOT include full track list - use
            playlist_items() for that.
        
        Raises:
            SpotifyError: If playlist not found, private, or network error.
        
        Note:
            For private playlists, user_auth must be enabled and the
            authenticated user must have access to the playlist.
        """
        try:
            result = self._spotify.playlist(
                playlist_id_or_url,
                fields="id,name,description,owner,images,external_urls,tracks.total,uri"
            )
            if result is None:
                raise SpotifyError(
                    f"Playlist not found: {playlist_id_or_url}",
                    details={"playlist_url": playlist_id_or_url}
                )
            return result
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    f"Rate limited while fetching playlist: {playlist_id_or_url}",
                    details={"playlist_url": playlist_id_or_url, "http_status": 429},
                    is_rate_limit=True
                ) from e
            if e.http_status == 404:
                raise SpotifyError(
                    f"Playlist not found: {playlist_id_or_url}",
                    details={"playlist_url": playlist_id_or_url, "http_status": 404}
                ) from e
            raise SpotifyError(
                f"Failed to fetch playlist: {e}",
                details={"playlist_url": playlist_id_or_url, "original_error": str(e)}
            ) from e
    
    def playlist_items(
        self,
        playlist_id_or_url: str,
        limit: int = 100,
        offset: int = 0
    ) -> dict[str, Any]:
        """
        Get tracks from a playlist with pagination.
        
        Args:
            playlist_id_or_url: Either a Spotify playlist ID or full URL.
            limit: Maximum number of tracks to return (max 100).
            offset: Index of first track to return (for pagination).
        
        Returns:
            Dictionary containing:
            - items: List of playlist track objects
            - total: Total number of tracks in playlist
            - next: URL for next page (or None)
            - previous: URL for previous page (or None)
        
        Raises:
            SpotifyError: If playlist not found or network error.
        
        Pagination:
            To fetch all tracks from a large playlist:
            1. Call with offset=0
            2. If 'next' is not None, increment offset by limit
            3. Repeat until 'next' is None
        
        Example:
            all_tracks = []
            offset = 0
            while True:
                response = client.playlist_items(playlist_url, offset=offset)
                all_tracks.extend(response['items'])
                if response['next'] is None:
                    break
                offset += 100
        """
        try:
            result = self._spotify.playlist_items(
                playlist_id_or_url,
                limit=min(limit, 100),
                offset=offset,
                additional_types=["track"]
            )
            if result is None:
                raise SpotifyError(
                    f"Failed to fetch playlist items: {playlist_id_or_url}",
                    details={"playlist_url": playlist_id_or_url}
                )
            return result
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    f"Rate limited while fetching playlist items: {playlist_id_or_url}",
                    details={"playlist_url": playlist_id_or_url, "http_status": 429},
                    is_rate_limit=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch playlist items: {e}",
                details={"playlist_url": playlist_id_or_url, "original_error": str(e)}
            ) from e
    
    def playlist_all_items(self, playlist_id_or_url: str) -> list[dict[str, Any]]:
        """
        Get ALL tracks from a playlist, handling pagination automatically.
        
        Args:
            playlist_id_or_url: Either a Spotify playlist ID or full URL.
        
        Returns:
            Complete list of all playlist track objects.
        
        Raises:
            SpotifyError: If playlist not found or network error.
        
        Behavior:
            Automatically paginates through all tracks using playlist_items().
            Makes multiple API requests as needed (100 tracks per request).
        
        Use Case:
            This is the primary method for fetching playlist contents
            in PHASE 1. It handles all pagination internally.
        
        Note:
            For very large playlists (1000+ tracks), this may take
            several seconds and make 10+ API requests.
        """
        all_items: list[dict[str, Any]] = []
        offset = 0
        
        while True:
            response = self.playlist_items(playlist_id_or_url, limit=100, offset=offset)
            items = response.get("items", [])
            all_items.extend(items)
            
            if response.get("next") is None:
                break
            offset += 100
        
        return all_items
    
    # =========================================================================
    # User Library Operations (requires user_auth)
    # =========================================================================
    
    def current_user_saved_tracks(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> dict[str, Any]:
        """
        Get user's Liked Songs (saved tracks) with pagination.
        
        Args:
            limit: Maximum number of tracks to return (max 50).
            offset: Index of first track to return (for pagination).
        
        Returns:
            Dictionary containing:
            - items: List of saved track objects (includes 'added_at')
            - total: Total number of liked songs
            - next: URL for next page (or None)
        
        Raises:
            SpotifyError: If user_auth not enabled.
            SpotifyError: If authentication invalid or expired.
            SpotifyError: If network error.
        
        Note:
            This method requires user authentication (user_auth=True
            in init()). Will raise SpotifyError if not enabled.
        """
        if not self._user_auth:
            raise SpotifyError(
                "User authentication required to access Liked Songs. "
                "Initialize SpotifyClient with user_auth=True.",
                is_auth_error=True
            )
        
        try:
            result = self._spotify.current_user_saved_tracks(
                limit=min(limit, 50),
                offset=offset
            )
            if result is None:
                raise SpotifyError(
                    "Failed to fetch saved tracks",
                    details={"offset": offset, "limit": limit}
                )
            return result
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                raise SpotifyError(
                    "Rate limited while fetching saved tracks",
                    details={"http_status": 429},
                    is_rate_limit=True
                ) from e
            if e.http_status == 401:
                raise SpotifyError(
                    "Authentication expired or invalid for accessing Liked Songs",
                    details={"http_status": 401},
                    is_auth_error=True
                ) from e
            raise SpotifyError(
                f"Failed to fetch saved tracks: {e}",
                details={"original_error": str(e)}
            ) from e
    
    def current_user_all_saved_tracks(self) -> list[dict[str, Any]]:
        """
        Get ALL user's Liked Songs, handling pagination automatically.
        
        Returns:
            Complete list of all saved track objects.
        
        Raises:
            SpotifyError: If user_auth not enabled.
            SpotifyError: If authentication invalid or network error.
        
        Behavior:
            Automatically paginates through all liked songs.
            Makes multiple API requests as needed (50 tracks per request).
        
        Use Case:
            This is the method for fetching Liked Songs in PHASE 1
            when --liked flag is used.
        """
        if not self._user_auth:
            raise SpotifyError(
                "User authentication required to access Liked Songs. "
                "Initialize SpotifyClient with user_auth=True.",
                is_auth_error=True
            )
        
        all_items: list[dict[str, Any]] = []
        offset = 0
        
        while True:
            response = self.current_user_saved_tracks(limit=50, offset=offset)
            items = response.get("items", [])
            all_items.extend(items)
            
            if response.get("next") is None:
                break
            offset += 50
        
        return all_items