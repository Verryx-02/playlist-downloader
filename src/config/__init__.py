"""
Configuration management package for Playlist-Downloader with comprehensive settings and authentication

This package provides the complete configuration management system for the Playlist-Downloader
application, serving as the central hub for all configuration-related functionality including
application settings, authentication management, and environment configuration.

The package implements a clean separation of concerns with two main components:

1. Settings Management (settings.py):
   - Application configuration from YAML files and environment variables
   - Settings validation and type checking
   - Configuration persistence and hot-reloading capabilities
   - Centralized configuration access throughout the application

2. Authentication Management (auth.py):
   - Spotify OAuth2 authentication flow implementation
   - Secure token storage and automatic refresh
   - Authentication state management and validation
   - Session persistence across application restarts

Package Architecture:
The configuration package follows a modular design where each component has specific
responsibilities while providing a unified interface through this __init__.py file.
This design ensures:

- Clean separation between settings and authentication concerns
- Consistent access patterns for configuration throughout the application
- Easy testing and mocking of configuration components
- Flexible configuration sources (files, environment, defaults)

Public API Design:
The package exposes a carefully curated public API through the __all__ definition,
providing both factory functions for easy access and class references for advanced
usage patterns:

Factory Functions (Recommended):
- get_settings(): Singleton access to application settings
- get_auth(): Singleton access to authentication manager
- reload_settings(): Hot-reload settings from configuration files
- reset_auth(): Reset authentication state for testing/troubleshooting

Class References (Advanced Usage):
- Settings: Direct access to settings class for custom instantiation
- SpotifyAuth: Direct access to auth class for testing and customization

Integration Points:
This package integrates with other application components:
- Utils package: Uses logging and helper functions
- Spotify package: Provides authentication for API access  
- Download package: Supplies configuration for download behavior
- Audio package: Provides audio processing settings
- Lyrics package: Supplies lyrics provider configuration

Usage Patterns:
The most common usage pattern throughout the application is:

    from config import get_settings, get_auth
    
    settings = get_settings()
    auth = get_auth()

This provides clean, consistent access to configuration while maintaining
the singleton pattern for efficient resource usage.

Configuration Sources:
The package supports multiple configuration sources in order of precedence:
1. Environment variables (highest priority, for sensitive data)
2. YAML configuration files (primary configuration method)
3. Default values (fallback for missing configuration)

This hierarchical approach allows for flexible deployment scenarios while
maintaining security best practices for sensitive information like API keys.

Thread Safety:
All configuration access is thread-safe, making it suitable for use in
concurrent download operations and multi-threaded application scenarios.
"""

# Settings management imports
# These provide comprehensive application configuration functionality
from .settings import get_settings, reload_settings, Settings

# Authentication management imports  
# These provide OAuth2 authentication and token management for Spotify API
from .auth import get_auth, reset_auth, SpotifyAuth

# Public API definition for the configuration package
# This controls what symbols are available when using "from config import *"
# and serves as the official public interface documentation
__all__ = [
    # Settings management - primary configuration interface
    'get_settings',      # Factory function for singleton settings access
    'reload_settings',   # Function to hot-reload settings from files
    'Settings',          # Settings class for direct instantiation (advanced usage)
    
    # Authentication management - Spotify OAuth2 interface
    'get_auth',          # Factory function for singleton authentication access
    'reset_auth',        # Function to reset authentication state
    'SpotifyAuth'        # Authentication class for direct instantiation (advanced usage)
]