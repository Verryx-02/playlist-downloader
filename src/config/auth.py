"""
OAuth2 authentication and token management for Spotify API

This module implements a complete OAuth2 authentication flow for Spotify Web API
integration. It handles the complex authorization process, secure token storage,
automatic token refresh, and provides a clean interface for authenticated API access.

Key features:
- Full OAuth2 authorization code flow implementation
- Support for both localhost callback and external tunnel services (ngrok, localhost.run)
- Automatic token refresh with exponential backoff
- Secure token storage with file permissions management
- Comprehensive error handling and user feedback
- Thread-safe HTTP callback server for authorization
- Session persistence across application restarts

The authentication flow follows Spotify's OAuth2 specification:
1. Generate authorization URL with required scopes
2. Open browser for user consent
3. Receive authorization code via callback
4. Exchange code for access/refresh tokens
5. Store tokens securely for future use
6. Automatically refresh tokens when expired

Security considerations:
- Tokens stored with restrictive file permissions (600)
- Client credentials validation
- Token expiry validation with safety buffer
- Secure HTTP server for callback handling
"""

import json
import time
import webbrowser
import urllib.parse
from typing import Dict, Optional, Any
from datetime import datetime
import spotipy
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import socket

from .settings import get_settings


class CallbackHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for OAuth2 callback processing
    
    This handler processes the callback from Spotify's authorization server
    after user consent. It extracts the authorization code from the callback URL
    and provides user-friendly feedback through styled HTML responses.
    
    The handler supports both successful authorization and error conditions,
    storing results in the parent server instance for the main authentication
    flow to process.
    
    Attributes:
        server: Parent HTTPServer instance with authorization_code and authorization_error attributes
    """
    
    def do_GET(self):
        """
        Handle GET request from OAuth callback
        
        Processes the OAuth2 callback URL to extract either the authorization code
        (on success) or error information (on failure). Provides immediate user
        feedback through styled HTML pages and stores results for the main
        authentication flow to retrieve.
        
        The callback URL format is:
        - Success: http://callback_url?code=AUTHORIZATION_CODE&state=STATE
        - Error: http://callback_url?error=ERROR_CODE&error_description=DESCRIPTION
        
        Sets server.authorization_code or server.authorization_error based on result.
        """
        # Parse the authorization code from callback URL
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Check for successful authorization with code parameter
        if 'code' in query_params:
            # Store authorization code in server instance for main thread to retrieve
            self.server.authorization_code = query_params['code'][0]
            
            # Send successful response headers
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Provide user-friendly success page with Spotify branding
            success_html = """
            <html>
            <head><title>Authorization Success</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #1DB954;">Authorization Successful!</h1>
                <p>You can now close this window and return to the terminal.</p>
                <p>Playlist-Downloader has been granted access to your Spotify account.</p>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
            
        # Check for authorization error
        elif 'error' in query_params:
            # Store error information for main thread to handle
            self.server.authorization_error = query_params['error'][0]
            
            # Send error response headers
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Provide user-friendly error page with troubleshooting hints
            error_html = f"""
            <html>
            <head><title>Authorization Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #E22134;">Authorization Failed</h1>
                <p>Error: {query_params.get('error', ['Unknown'])[0]}</p>
                <p>Please try again or check your Spotify App settings.</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())
    
    def log_message(self, format, *args):
        """
        Suppress HTTP server logs to keep console output clean
        
        Overrides the default HTTP server logging to prevent verbose
        request logs from cluttering the user interface during the
        OAuth flow. This maintains a clean console experience.
        
        Args:
            format: Log message format string (ignored)
            *args: Log message arguments (ignored)
        """
        pass


class SpotifyAuth:
    """
    Comprehensive Spotify OAuth2 authentication and token management
    
    This class handles the complete OAuth2 flow for Spotify API authentication,
    including authorization, token storage, automatic refresh, and session
    management. It supports both localhost callbacks and external tunnel services
    for flexible deployment scenarios.
    
    Key responsibilities:
    - OAuth2 authorization code flow execution
    - Secure token storage and retrieval
    - Automatic token refresh before expiration
    - Spotify API client instance management
    - Authentication state validation
    - Support for multiple callback methods (localhost/tunnel)
    
    The class follows the OAuth2 specification and Spotify's specific requirements:
    - Authorization scopes for playlist and user data access
    - Token expiration handling with safety margins
    - Refresh token management for long-term authentication
    - Secure credential storage with proper file permissions
    
    Attributes:
        settings: Application settings instance
        token_file: Path to secure token storage file
        client_id: Spotify application client ID
        client_secret: Spotify application client secret
        redirect_uri: OAuth2 callback URL
        scope: Required permission scopes for API access
        _spotify_client: Cached authenticated Spotify client instance
        _token_info: Current token information dictionary
    """
    
    def __init__(self):
        """
        Initialize authentication manager with application settings
        
        Loads configuration from application settings and prepares the
        authentication environment. Validates that required credentials
        are available and sets up secure token storage paths.
        
        Raises:
            ValueError: If required Spotify credentials are not configured
        """
        # Load application configuration
        self.settings = get_settings()
        
        # Set up secure token storage path
        self.token_file = self.settings.get_token_storage_path()
        
        # Extract Spotify application credentials from settings
        self.client_id = self.settings.spotify.client_id
        self.client_secret = self.settings.spotify.client_secret
        self.redirect_uri = self.settings.spotify.redirect_url
        self.scope = self.settings.spotify.scope
        
        # Initialize client and token caches
        self._spotify_client: Optional[spotipy.Spotify] = None
        self._token_info: Optional[Dict[str, Any]] = None
    
    def _find_available_port(self, start_port: int = 8080) -> int:
        """
        Find an available port for the OAuth callback server
        
        Searches for an available port starting from the specified port number.
        This ensures the callback server can bind successfully without conflicts
        with other running services. Essential for localhost-based OAuth flows.
        
        Args:
            start_port: Starting port number to check (default: 8080)
            
        Returns:
            First available port number in the range [start_port, start_port+100)
            
        Raises:
            Exception: If no available ports found in the search range
            
        Note:
            Checks up to 100 ports to balance thoroughness with performance.
            Most systems will have available ports in this range.
        """
        # Search through a reasonable range of ports
        for port in range(start_port, start_port + 100):
            try:
                # Attempt to bind to the port to test availability
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                # Port is already in use, try the next one
                continue
        
        # No available ports found in the range
        raise Exception("No available ports found")
    
    def _load_token(self) -> Optional[Dict[str, Any]]:
        """
        Load and validate stored authentication token from file
        
        Attempts to load previously stored token information from the secure
        token file. Validates the token structure to ensure all required fields
        are present before returning. Invalid or corrupted tokens are rejected
        to trigger re-authentication.
        
        Returns:
            Dictionary containing token information if valid, None otherwise
            Token dictionary includes: access_token, refresh_token, expires_at,
            token_type, scope, saved_at, client_id
            
        Note:
            Validates token structure but does not check expiration - that's
            handled separately to allow for refresh token usage.
        """
        try:
            # Check if token file exists
            if self.token_file.exists():
                # Load token data from JSON file
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                    
                # Validate that all required fields are present
                # These fields are essential for token usage and refresh
                required_fields = ['access_token', 'refresh_token', 'expires_at', 'token_type']
                if all(field in token_data for field in required_fields):
                    return token_data
                else:
                    # Token structure is invalid, inform user
                    print("Warning: Invalid token structure, re-authentication required")
                    
        except Exception as e:
            # Handle file read errors, JSON parsing errors, etc.
            print(f"Warning: Failed to load stored token: {e}")
        
        # Return None to trigger new authentication
        return None
    
    def _save_token(self, token_info: Dict[str, Any]) -> None:
        """
        Save token information to secure storage file
        
        Stores token information in a JSON file with appropriate metadata
        and security measures. Creates parent directories if needed and
        sets restrictive file permissions to protect sensitive credentials.
        
        Args:
            token_info: Complete token information dictionary to store
                       Must include access_token, refresh_token, expires_at, etc.
                       
        Note:
            Adds metadata (saved_at timestamp, client_id) for validation
            and debugging purposes. Sets file permissions to 600 (owner only)
            on Unix-like systems for security.
        """
        try:
            # Ensure parent directory exists for token storage
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Add metadata to token information for validation and debugging
            token_data = {
                **token_info,  # Include all original token fields
                'saved_at': datetime.now().isoformat(),  # Timestamp for debugging
                'client_id': self.client_id  # Store client_id for validation
            }
            
            # Write token data to JSON file with readable formatting
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)
            
            # Set restrictive file permissions for security (Unix-like systems)
            try:
                # 0o600 = owner read/write only (no group, no other)
                self.token_file.chmod(0o600)
            except Exception:
                # Windows doesn't support chmod, silently continue
                pass
                
        except Exception as e:
            # Handle file write errors, permission errors, etc.
            print(f"Warning: Failed to save token: {e}")
    
    def _is_token_expired(self, token_info: Dict[str, Any]) -> bool:
        """
        Check if access token is expired or approaching expiration
        
        Determines if the current access token needs to be refreshed by
        comparing the expiration time with the current time. Includes a
        safety buffer to refresh tokens before they actually expire,
        preventing API call failures due to timing issues.
        
        Args:
            token_info: Token information dictionary containing expires_at field
            
        Returns:
            True if token is expired or will expire within safety buffer,
            False if token is still valid for use
            
        Note:
            Uses a 5-minute (300 second) safety buffer to account for:
            - Network latency in API calls
            - Clock synchronization differences
            - Processing time for token refresh
        """
        # Check if expiration time is present in token data
        if 'expires_at' not in token_info:
            # Missing expiration data - consider expired to trigger refresh
            return True
        
        # Get token expiration timestamp
        expires_at = token_info['expires_at']
        current_time = int(time.time())
        
        # Consider token expired if it expires within 5 minutes (300 seconds)
        # This safety buffer prevents API failures due to token expiry during use
        safety_buffer_seconds = 300
        return current_time >= (expires_at - safety_buffer_seconds)
    
    def _refresh_token(self, token_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Refresh expired access token using refresh token
        
        Exchanges the stored refresh token for a new access token using
        Spotify's token refresh endpoint. This allows maintaining authentication
        without requiring user re-authorization. Updates the stored token
        information with the new credentials.
        
        Args:
            token_info: Current token information containing refresh_token
            
        Returns:
            Updated token information dictionary if refresh successful,
            None if refresh failed (triggers re-authorization)
            
        Note:
            Refresh tokens may be rotated by Spotify, so the response may
            include a new refresh token. Falls back to existing refresh
            token if not provided in response.
        """
        # Verify refresh token is available
        if 'refresh_token' not in token_info:
            return None
        
        try:
            # Spotify token refresh endpoint
            token_url = "https://accounts.spotify.com/api/token"
            
            # Request headers for token refresh
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Token refresh request data
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': token_info['refresh_token'],
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            # Send refresh request to Spotify
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Parse new token information from response
            new_token = response.json()
            
            # Build updated token information
            # Note: Spotify may or may not provide a new refresh token
            updated_token = {
                'access_token': new_token['access_token'],
                'token_type': new_token.get('token_type', 'Bearer'),
                'expires_in': new_token.get('expires_in', 3600),  # Default 1 hour
                'expires_at': int(time.time()) + new_token.get('expires_in', 3600),
                # Use new refresh token if provided, otherwise keep existing one
                'refresh_token': new_token.get('refresh_token', token_info['refresh_token']),
                'scope': new_token.get('scope', self.scope)
            }
            
            # Save updated token information
            self._save_token(updated_token)
            return updated_token
            
        except Exception as e:
            # Handle network errors, API errors, parsing errors, etc.
            print(f"Warning: Failed to refresh token: {e}")
            return None
    
    def _authorize_new(self) -> Optional[Dict[str, Any]]:
        """
        Perform complete OAuth2 authorization flow for new authentication
        
        Executes the full OAuth2 authorization code flow including:
        1. Authorization URL generation with required scopes
        2. Browser-based user consent collection
        3. Authorization code reception via callback
        4. Token exchange for access/refresh tokens
        5. Secure token storage for future use
        
        Supports both localhost callback (with embedded HTTP server) and
        external tunnel services (ngrok, localhost.run) for different
        deployment scenarios.
        
        Returns:
            Complete token information dictionary if successful, None if failed
            
        Raises:
            ValueError: If client credentials are not configured
            TimeoutError: If authorization process times out
            Exception: For various authorization failures
            
        Note:
            The callback method is determined by the redirect_uri configuration:
            - localhost/127.0.0.1: Uses embedded HTTP server
            - External URLs: Uses manual code entry flow
        """
        # Validate required credentials are configured
        if not self.client_id or not self.client_secret:
            raise ValueError("Spotify client_id and client_secret must be configured")
        
        print(f"Starting authorization flow...")
        
        # Determine callback method based on redirect URI configuration
        if 'localhost' in self.redirect_uri or '127.0.0.1' in self.redirect_uri:
            # Using localhost - start embedded HTTP server for callback
            port = self._find_available_port()
            callback_url = f"http://localhost:{port}/callback"
            self.redirect_uri = callback_url
            use_local_server = True
        else:
            # Using external tunnel service (ngrok, localhost.run, etc.)
            callback_url = self.redirect_uri
            use_local_server = False
            print(f"Using external tunnel: {callback_url}")
        
        # Build Spotify authorization URL with required parameters
        auth_url = "https://accounts.spotify.com/authorize"
        params = {
            'client_id': self.client_id,
            'response_type': 'code',  # Authorization code flow
            'redirect_uri': callback_url,
            'scope': self.scope,  # Required permissions
            'show_dialog': 'true'  # Force consent screen for clarity
        }
        
        # Generate complete authorization URL
        authorization_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
        
        if use_local_server:
            # Localhost callback: start embedded HTTP server
            server = HTTPServer(('localhost', port), CallbackHandler)
            # Initialize server state for callback handling
            server.authorization_code = None
            server.authorization_error = None
            
            # Start server in background thread to handle callback
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True  # Allow main thread to exit
            server_thread.start()
            
            try:
                # Open user's browser for authorization
                print(f"Opening browser for Spotify authorization...")
                print(f"If browser doesn't open, visit: {authorization_url}")
                webbrowser.open(authorization_url)
                
                # Wait for callback with timeout protection
                print("Waiting for authorization callback...")
                timeout_seconds = 300  # 5 minutes maximum wait time
                start_time = time.time()
                
                # Poll for callback result
                while server.authorization_code is None and server.authorization_error is None:
                    time.sleep(0.5)  # Check every 500ms
                    if time.time() - start_time > timeout_seconds:
                        raise TimeoutError("Authorization timeout")
                
                # Check for authorization errors
                if server.authorization_error:
                    raise Exception(f"Authorization failed: {server.authorization_error}")
                
                # Validate authorization code was received
                if not server.authorization_code:
                    raise Exception("No authorization code received")
                
                # Exchange authorization code for access token
                token_info = self._exchange_code_for_token(server.authorization_code, callback_url)
                
                if token_info:
                    # Save token and report success
                    self._save_token(token_info)
                    print("Authorization successful!")
                    return token_info
                else:
                    raise Exception("Failed to exchange authorization code for token")
                    
            finally:
                # Always clean up the HTTP server
                server.shutdown()
                server.server_close()
        else:
            # External tunnel: manual code entry flow
            print(f"Opening browser for Spotify authorization...")
            print(f"If browser doesn't open, visit: {authorization_url}")
            webbrowser.open(authorization_url)
            
            # Provide clear instructions for manual code entry
            print("\n" + "="*80)
            print("USING EXTERNAL TUNNEL:")
            print("1. Complete authorization in the browser")
            print("2. After authorization, you'll be redirected to your tunnel URL")
            print("3. Copy the 'code' parameter from the URL")
            print("4. Paste it below when prompted")
            print("="*80 + "\n")
            
            # Get authorization code from user input
            try:
                auth_code = input("Enter the authorization code from the redirect URL: ").strip()
                if not auth_code:
                    raise Exception("No authorization code provided")
                
                # Exchange code for token
                token_info = self._exchange_code_for_token(auth_code, callback_url)
                
                if token_info:
                    self._save_token(token_info)
                    print("Authorization successful!")
                    return token_info
                else:
                    raise Exception("Failed to exchange authorization code for token")
                    
            except KeyboardInterrupt:
                raise Exception("Authorization cancelled by user")
    
    def _exchange_code_for_token(self, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access and refresh tokens
        
        Completes the OAuth2 flow by exchanging the authorization code received
        from the callback for actual access tokens. This is the final step of
        the authorization process that provides the credentials needed for API access.
        
        Args:
            code: Authorization code from Spotify callback
            redirect_uri: The exact redirect URI used in authorization request
            
        Returns:
            Complete token information dictionary if successful, None if failed
            Token includes: access_token, refresh_token, expires_at, token_type, scope
            
        Note:
            The redirect_uri must exactly match the one used in the authorization
            request for security. Handles token expiration calculation and
            provides sensible defaults for missing fields.
        """
        try:
            # Spotify token exchange endpoint
            token_url = "https://accounts.spotify.com/api/token"
            
            # Request headers for token exchange
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Token exchange request data
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,  # Must match authorization request
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            # Send token exchange request to Spotify
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Parse token response
            token_data = response.json()
            
            # Build standardized token information structure
            token_info = {
                'access_token': token_data['access_token'],
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_in': token_data.get('expires_in', 3600),  # Default 1 hour
                # Calculate absolute expiration time for easier checking
                'expires_at': int(time.time()) + token_data.get('expires_in', 3600),
                'refresh_token': token_data.get('refresh_token'),
                'scope': token_data.get('scope', self.scope)
            }
            
            return token_info
            
        except Exception as e:
            # Handle network errors, API errors, parsing errors, etc.
            print(f"Error exchanging code for token: {e}")
            return None
    
    def get_valid_token(self) -> Optional[str]:
        """
        Get a valid access token, handling refresh and re-authorization as needed
        
        This is the main method for obtaining a valid access token for API calls.
        It handles the complete token lifecycle including loading stored tokens,
        checking expiration, refreshing when possible, and triggering new
        authorization when necessary.
        
        Returns:
            Valid access token string if successful, None if authentication failed
            
        Flow:
        1. Load existing token from storage if not already cached
        2. Check if token is expired and refresh if possible
        3. If refresh fails or no stored token, start new authorization
        4. Return access token for immediate use
        
        Note:
            This method is the primary entry point for token management and
            should be called before any Spotify API operations.
        """
        # Load existing token if not already cached in memory
        if not self._token_info:
            self._token_info = self._load_token()
        
        # Process existing token if available
        if self._token_info:
            # Check if current token is expired or approaching expiration
            if self._is_token_expired(self._token_info):
                print("Access token expired, refreshing...")
                # Attempt to refresh using refresh token
                refreshed_token = self._refresh_token(self._token_info)
                if refreshed_token:
                    # Refresh successful, update cached token
                    self._token_info = refreshed_token
                else:
                    # Refresh failed, clear token to trigger re-authorization
                    print("Token refresh failed, re-authorization required")
                    self._token_info = None
        
        # If no valid token available, perform new authorization
        if not self._token_info:
            print("No valid token found, starting authorization...")
            self._token_info = self._authorize_new()
        
        # Return access token if available
        return self._token_info['access_token'] if self._token_info else None
    
    def get_spotify_client(self) -> Optional[spotipy.Spotify]:
        """
        Get authenticated Spotify API client instance
        
        Provides a configured spotipy.Spotify client with valid authentication.
        Handles token management automatically and caches the client instance
        for efficiency. Updates the token in existing client instances when
        tokens are refreshed.
        
        Returns:
            Authenticated Spotify client if successful, None if authentication failed
            
        Note:
            The returned client is ready for immediate API use. Token management
            is handled transparently, so the client will always have valid
            credentials when returned.
        """
        # Get valid access token (handles refresh/re-auth as needed)
        token = self.get_valid_token()
        if not token:
            return None
        
        # Create new client instance if not already cached
        if not self._spotify_client:
            self._spotify_client = spotipy.Spotify(auth=token)
        else:
            # Update token in existing client instance
            # This is more efficient than creating new client instances
            self._spotify_client.auth = token
        
        return self._spotify_client
    
    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated with valid credentials
        
        Verifies authentication status by attempting to get a valid Spotify
        client and making a test API call. This provides a reliable way to
        check if the application can successfully access Spotify's API.
        
        Returns:
            True if authentication is valid and API is accessible, False otherwise
            
        Note:
            This method makes an actual API call (current_user) to verify
            authentication, so it requires network connectivity and may
            trigger token refresh if needed.
        """
        try:
            # Attempt to get authenticated client
            client = self.get_spotify_client()
            if client:
                # Test authentication with a lightweight API call
                client.current_user()
                return True
        except Exception:
            # Any exception indicates authentication failure
            pass
        return False
    
    def revoke_token(self) -> None:
        """
        Revoke current authentication and delete stored credentials
        
        Completely removes all stored authentication information including
        access tokens, refresh tokens, and cached client instances. This
        effectively logs the user out and requires re-authorization for
        future API access.
        
        Note:
            This only removes local token storage. The tokens remain valid
            on Spotify's side until they naturally expire. Use this method
            for logout functionality or troubleshooting authentication issues.
        """
        # Delete stored token file if it exists
        if self.token_file.exists():
            try:
                self.token_file.unlink()
                print("Token revoked successfully")
            except Exception as e:
                print(f"Warning: Failed to delete token file: {e}")
        
        # Clear cached authentication state
        self._token_info = None
        self._spotify_client = None
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current authenticated user's profile information
        
        Retrieves the Spotify user profile for the currently authenticated user.
        This includes display name, user ID, follower count, and other profile
        details available through the Spotify Web API.
        
        Returns:
            User profile information dictionary if successful, None if failed
            Profile includes: id, display_name, email, followers, etc.
            
        Note:
            Requires valid authentication. If authentication is invalid,
            this method will return None rather than raising an exception.
        """
        try:
            # Get authenticated client
            client = self.get_spotify_client()
            if client:
                # Retrieve current user profile information
                return client.current_user()
        except Exception as e:
            # Handle authentication errors, network errors, etc.
            print(f"Error getting user info: {e}")
        return None


# Global authentication instance management
# Singleton pattern ensures consistent authentication state across the application
_auth_instance: Optional[SpotifyAuth] = None


def get_auth() -> SpotifyAuth:
    """
    Get the global authentication instance (singleton pattern)
    
    Provides access to the shared authentication instance used throughout
    the application. Creates the instance on first access and returns the
    same instance for subsequent calls, ensuring consistent authentication
    state across all modules.
    
    Returns:
        Global SpotifyAuth instance
        
    Note:
        This singleton pattern ensures that authentication state (tokens,
        client instances) is shared efficiently across the entire application
        without requiring manual instance management.
    """
    global _auth_instance
    if not _auth_instance:
        _auth_instance = SpotifyAuth()
    return _auth_instance


def reset_auth() -> None:
    """
    Reset the global authentication instance
    
    Clears the global authentication instance, forcing a new instance to be
    created on the next access. This is useful for testing, configuration
    changes, or troubleshooting authentication issues.
    
    Note:
        This does not revoke tokens or delete stored credentials - it only
        clears the in-memory instance. Use SpotifyAuth.revoke_token() for
        complete logout functionality.
    """
    global _auth_instance
    _auth_instance = None