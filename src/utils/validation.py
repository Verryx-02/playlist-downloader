"""
Input validation utilities
"""
import os
import re
from urllib.parse import urlparse
from typing import Optional, List, Tuple

def validate_spotify_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Spotify playlist URL
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    # Check if it's a Spotify URL
    if not ('spotify.com' in url or url.startswith('spotify:')):
        return False, "Not a Spotify URL"
    
    # Check if it's a playlist URL
    if 'playlist/' not in url and ':playlist:' not in url:
        return False, "Not a playlist URL"
    
    # Try to extract playlist ID
    try:
        if 'playlist/' in url:
            playlist_id = url.split('playlist/')[-1].split('?')[0]
        else:
            parts = url.split(':')
            if len(parts) >= 3 and parts[1] == 'playlist':
                playlist_id = parts[2]
            else:
                return False, "Invalid Spotify URI format"
        
        # Validate playlist ID format
        if not re.match(r'^[a-zA-Z0-9]{22}$', playlist_id):
            return False, "Invalid playlist ID format"
        
        return True, None
        
    except Exception as e:
        return False, f"Error parsing URL: {e}"

def validate_output_directory(path: str) -> Tuple[bool, Optional[str]]:
    from .helpers import validate_and_create_directory
    """
    Validate output directory path
    
    Args:
        path: Directory path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Output directory cannot be empty"
    
    try:
        from pathlib import Path
        path_obj = Path(path).expanduser()

        # For user input, use strict validation (trusted_source=False)
        success, error_msg, validated_path = validate_and_create_directory(
            path_obj, 
            trusted_source=False
        )

        if not success:
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid path: {e}"

def validate_audio_format(format_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate audio format
    
    Args:
        format_name: Audio format name
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_formats = ['mp3', 'flac', 'm4a', 'aac', 'ogg', 'wav']
    
    if not format_name:
        return False, "Audio format cannot be empty"
    
    if format_name.lower() not in valid_formats:
        return False, f"Unsupported format: {format_name}. Valid formats: {', '.join(valid_formats)}"
    
    return True, None

def validate_quality_setting(quality: str) -> Tuple[bool, Optional[str]]:
    """
    Validate quality setting
    
    Args:
        quality: Quality setting
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_qualities = ['low', 'medium', 'high']
    
    if not quality:
        return False, "Quality setting cannot be empty"
    
    if quality.lower() not in valid_qualities:
        return False, f"Invalid quality: {quality}. Valid options: {', '.join(valid_qualities)}"
    
    return True, None
