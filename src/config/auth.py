"""
OAuth2 authentication and token management for Spotify API
Handles authorization flow, token storage, and automatic refresh
"""

import json
import time
import webbrowser
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import socket

from .settings import get_settings


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
    
    def do_GET(self):
        """Handle GET request from OAuth callback"""
        # Parse the authorization code from callback URL
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'code' in query_params:
            self.server.authorization_code = query_params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            success_html = """
            <html>
            <head><title>Authorization Success</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #1DB954;">✅ Authorization Successful!</h1>
                <p>You can now close this window and return to the terminal.</p>
                <p>Playlist-Downloader has been granted access to your Spotify account.</p>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
        elif 'error' in query_params:
            self.server.authorization_error = query_params['error'][0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            error_html = f"""
            <html>
            <head><title>Authorization Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #E22134;">❌ Authorization Failed</h1>
                <p>Error: {query_params.get('error', ['Unknown'])[0]}</p>
                <p>Please try again or check your Spotify App settings.</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs"""
        pass


class SpotifyAuth:
    """Handles Spotify OAuth2 authentication and token management"""
    
    def __init__(self):
        """Initialize authentication with settings"""
        self.settings = get_settings()
        self.token_file = self.settings.get_token_storage_path()
        self.client_id = self.settings.spotify.client_id
        self.client_secret = self.settings.spotify.client_secret
        self.redirect_uri = self.settings.spotify.redirect_url
        self.scope = self.settings.spotify.scope
        
        self._spotify_client: Optional[spotipy.Spotify] = None
        self._token_info: Optional[Dict[str, Any]] = None
    
    def _find_available_port(self, start_port: int = 8080) -> int:
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        raise Exception("No available ports found")
    
    def _load_token(self) -> Optional[Dict[str, Any]]:
        """Load stored token from file"""
        try:
            if self.token_file.exists():
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                    
                # Validate token structure
                required_fields = ['access_token', 'refresh_token', 'expires_at', 'token_type']
                if all(field in token_data for field in required_fields):
                    return token_data
                else:
                    print("Warning: Invalid token structure, re-authentication required")
                    
        except Exception as e:
            print(f"Warning: Failed to load stored token: {e}")
        
        return None
    
    def _save_token(self, token_info: Dict[str, Any]) -> None:
        """Save token to file"""
        try:
            # Ensure directory exists
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save token with metadata
            token_data = {
                **token_info,
                'saved_at': datetime.now().isoformat(),
                'client_id': self.client_id  # Store client_id for validation
            }
            
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)
            
            # Set restrictive permissions (Unix-like systems)
            try:
                self.token_file.chmod(0o600)
            except Exception:
                pass  # Windows doesn't support chmod
                
        except Exception as e:
            print(f"Warning: Failed to save token: {e}")
    
    def _is_token_expired(self, token_info: Dict[str, Any]) -> bool:
        """Check if token is expired"""
        if 'expires_at' not in token_info:
            return True
        
        expires_at = token_info['expires_at']
        current_time = int(time.time())
        
        # Consider token expired if it expires within 5 minutes
        return current_time >= (expires_at - 300)
    
    def _refresh_token(self, token_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Refresh expired token using refresh_token"""
        if 'refresh_token' not in token_info:
            return None
        
        try:
            # Prepare refresh request
            token_url = "https://accounts.spotify.com/api/token"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': token_info['refresh_token'],
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            new_token = response.json()
            
            # Update token info
            updated_token = {
                'access_token': new_token['access_token'],
                'token_type': new_token.get('token_type', 'Bearer'),
                'expires_in': new_token.get('expires_in', 3600),
                'expires_at': int(time.time()) + new_token.get('expires_in', 3600),
                'refresh_token': new_token.get('refresh_token', token_info['refresh_token']),
                'scope': new_token.get('scope', self.scope)
            }
            
            self._save_token(updated_token)
            return updated_token
            
        except Exception as e:
            print(f"Warning: Failed to refresh token: {e}")
            return None
    
    def _authorize_new(self) -> Optional[Dict[str, Any]]:
        """Perform new OAuth2 authorization flow"""
        if not self.client_id or not self.client_secret:
            raise ValueError("Spotify client_id and client_secret must be configured")
        
        print(f"Starting authorization flow...")
        
        # Check if we're using an external tunnel or localhost
        if 'localhost' in self.redirect_uri or '127.0.0.1' in self.redirect_uri:
            # Using localhost - find available port and start local server
            port = self._find_available_port()
            callback_url = f"http://localhost:{port}/callback"
            self.redirect_uri = callback_url
            use_local_server = True
        else:
            # Using external tunnel (ngrok, localhost.run, etc.)
            callback_url = self.redirect_uri
            use_local_server = False
            print(f"Using external tunnel: {callback_url}")
        
        # Create authorization URL
        auth_url = "https://accounts.spotify.com/authorize"
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': callback_url,
            'scope': self.scope,
            'show_dialog': 'true'
        }
        
        authorization_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
        
        if use_local_server:
            # Start callback server for localhost
            server = HTTPServer(('localhost', port), CallbackHandler)
            server.authorization_code = None
            server.authorization_error = None
            
            # Start server in background thread
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            try:
                print(f"Opening browser for Spotify authorization...")
                print(f"If browser doesn't open, visit: {authorization_url}")
                webbrowser.open(authorization_url)
                
                # Wait for callback
                print("Waiting for authorization callback...")
                timeout = 300  # 5 minutes timeout
                start_time = time.time()
                
                while server.authorization_code is None and server.authorization_error is None:
                    time.sleep(0.5)
                    if time.time() - start_time > timeout:
                        raise TimeoutError("Authorization timeout")
                
                if server.authorization_error:
                    raise Exception(f"Authorization failed: {server.authorization_error}")
                
                if not server.authorization_code:
                    raise Exception("No authorization code received")
                
                # Exchange code for token
                token_info = self._exchange_code_for_token(server.authorization_code, callback_url)
                
                if token_info:
                    self._save_token(token_info)
                    print("✅ Authorization successful!")
                    return token_info
                else:
                    raise Exception("Failed to exchange authorization code for token")
                    
            finally:
                server.shutdown()
                server.server_close()
        else:
            # Using external tunnel - user must manually copy the code
            print(f"Opening browser for Spotify authorization...")
            print(f"If browser doesn't open, visit: {authorization_url}")
            webbrowser.open(authorization_url)
            
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
                    print("✅ Authorization successful!")
                    return token_info
                else:
                    raise Exception("Failed to exchange authorization code for token")
                    
            except KeyboardInterrupt:
                raise Exception("Authorization cancelled by user")
    
    def _exchange_code_for_token(self, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        try:
            token_url = "https://accounts.spotify.com/api/token"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Format token info
            token_info = {
                'access_token': token_data['access_token'],
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_in': token_data.get('expires_in', 3600),
                'expires_at': int(time.time()) + token_data.get('expires_in', 3600),
                'refresh_token': token_data.get('refresh_token'),
                'scope': token_data.get('scope', self.scope)
            }
            
            return token_info
            
        except Exception as e:
            print(f"Error exchanging code for token: {e}")
            return None
    
    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary"""
        # Load existing token
        if not self._token_info:
            self._token_info = self._load_token()
        
        # Check if we have a valid token
        if self._token_info:
            # Check if token is expired
            if self._is_token_expired(self._token_info):
                print("Access token expired, refreshing...")
                refreshed_token = self._refresh_token(self._token_info)
                if refreshed_token:
                    self._token_info = refreshed_token
                else:
                    print("Token refresh failed, re-authorization required")
                    self._token_info = None
        
        # If no valid token, perform new authorization
        if not self._token_info:
            print("No valid token found, starting authorization...")
            self._token_info = self._authorize_new()
        
        return self._token_info['access_token'] if self._token_info else None
    
    def get_spotify_client(self) -> Optional[spotipy.Spotify]:
        """Get authenticated Spotify client"""
        token = self.get_valid_token()
        if not token:
            return None
        
        if not self._spotify_client:
            self._spotify_client = spotipy.Spotify(auth=token)
        else:
            # Update token in existing client
            self._spotify_client.auth = token
        
        return self._spotify_client
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated"""
        try:
            client = self.get_spotify_client()
            if client:
                # Test API call
                client.current_user()
                return True
        except Exception:
            pass
        return False
    
    def revoke_token(self) -> None:
        """Revoke current token and delete stored credentials"""
        if self.token_file.exists():
            try:
                self.token_file.unlink()
                print("✅ Token revoked successfully")
            except Exception as e:
                print(f"Warning: Failed to delete token file: {e}")
        
        self._token_info = None
        self._spotify_client = None
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get current user information"""
        try:
            client = self.get_spotify_client()
            if client:
                return client.current_user()
        except Exception as e:
            print(f"Error getting user info: {e}")
        return None


# Global auth instance
_auth_instance: Optional[SpotifyAuth] = None


def get_auth() -> SpotifyAuth:
    """Get global authentication instance"""
    global _auth_instance
    if not _auth_instance:
        _auth_instance = SpotifyAuth()
    return _auth_instance


def reset_auth() -> None:
    """Reset global authentication instance"""
    global _auth_instance
    _auth_instance = None