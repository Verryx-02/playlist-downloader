"""
Utility functions and helpers for Playlist-Downloader
Common functions for file handling, string processing, and validation
"""

import re
import unicodedata
from pathlib import Path
import time
from typing import Optional, List, Dict, Any, Union, Tuple
import string
import hashlib
from urllib.parse import urlparse
import time
from datetime import datetime, timedelta


def sanitize_filename(filename: str, max_length: int = 200, replace_spaces: bool = False) -> str:
    """
    Sanitize filename for cross-platform compatibility
    
    Args:
        filename: Original filename
        max_length: Maximum filename length
        replace_spaces: Whether to replace spaces with underscores
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return "unknown"
    
    # Remove wrapping quotes and extra whitespace first
    filename = filename.strip()
    
    # Remove leading/trailing quotes (single and double)
    while filename and filename[0] in ['"', "'"]:
        filename = filename[1:]
    while filename and filename[-1] in ['"', "'"]:
        filename = filename[:-1]
    
    # Strip whitespace again after quote removal
    filename = filename.strip()
    
    if not filename:
        return "unknown"
    
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    
    # Remove or replace problematic characters
    # Characters not allowed in Windows filenames + extra problematic ones
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]'
    filename = re.sub(invalid_chars, '', filename)
    
    # Remove additional problematic characters that can cause issues
    # Emoji and special Unicode characters that can cause path issues
    filename = re.sub(r'[^\w\s\-_.,()[\]{}!@#$%^&+=]', '', filename, flags=re.UNICODE)
    
    # Replace multiple whitespace characters with single space
    filename = re.sub(r'\s+', ' ', filename)
    
    # Replace spaces with underscores if requested
    if replace_spaces:
        filename = filename.replace(' ', '_')
    
    # Remove leading/trailing whitespace and dots (after all processing)
    filename = filename.strip(' .')
    
    # Handle reserved Windows names
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    # Check if the base name (without extension) is reserved
    name_part = filename.split('.')[0].upper() if '.' in filename else filename.upper()
    if name_part in reserved_names:
        filename = f"_{filename}"
    
    # Truncate if too long
    if len(filename) > max_length:
        # Try to preserve file extension
        if '.' in filename:
            name, ext = filename.rsplit('.', 1)
            available_length = max_length - len(ext) - 1
            if available_length > 0:
                filename = f"{name[:available_length]}.{ext}"
            else:
                filename = filename[:max_length]
        else:
            filename = filename[:max_length]
    
    # Final validation - ensure we have a valid filename
    if not filename or filename in ['.', '..'] or filename.isspace():
        filename = "unknown"
    
    # Remove any trailing dots or spaces that might have been introduced
    filename = filename.rstrip(' .')
    
    # Ensure filename is not empty after all processing
    if not filename:
        filename = "unknown"
    
    return filename

def sanitize_directory_name(dirname: str, max_length: int = 200) -> str:
    """
    Sanitize directory name for cross-platform compatibility
    More aggressive than filename sanitization
    
    Args:
        dirname: Original directory name
        max_length: Maximum directory name length
        
    Returns:
        Sanitized directory name
    """
    if not dirname:
        return "unknown_directory"
    
    # Remove wrapping quotes and extra whitespace first
    dirname = dirname.strip()
    
    # AGGRESSIVELY remove quotes from anywhere in the string
    dirname = dirname.replace('"', '').replace("'", '')
    
    # Strip whitespace again after quote removal
    dirname = dirname.strip()
    
    if not dirname:
        return "unknown_directory"
    
    # Normalize unicode characters
    import unicodedata
    dirname = unicodedata.normalize('NFKD', dirname)
    
    # Remove or replace problematic characters for directories
    import re
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]'
    dirname = re.sub(invalid_chars, '', dirname)
    
    # Remove additional problematic characters
    dirname = re.sub(r'[^\w\s\-_.,()[\]{}!@#$%^&+=]', '', dirname, flags=re.UNICODE)
    
    # Replace multiple whitespace characters with single space
    dirname = re.sub(r'\s+', ' ', dirname)
    
    # Remove leading/trailing whitespace and dots
    dirname = dirname.strip(' .')
    
    # Handle reserved Windows names
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    if dirname.upper() in reserved_names:
        dirname = f"_{dirname}"
    
    # Truncate if too long
    if len(dirname) > max_length:
        dirname = dirname[:max_length]
    
    # Remove trailing dots which can cause issues on Windows
    dirname = dirname.rstrip('.')
    
    # Ensure directory name doesn't start with dot (hidden directory)
    if dirname.startswith('.') and len(dirname) > 1:
        dirname = dirname[1:]
    
    # Replace problematic sequences
    dirname = dirname.replace('..', '_')
    
    # Final validation
    if not dirname or dirname.isspace():
        dirname = "unknown_directory"
    
    return dirname

def normalize_playlist_name_for_matching(name: str) -> str:
    """
    Normalize playlist name for directory matching
    
    Args:
        name: Original playlist name
        
    Returns:
        Normalized name for comparison
    """
    if not name:
        return ""
    
    # Remove quotes and normalize
    normalized = name.strip().replace('"', '').replace("'", '')
    
    # Convert to lowercase for comparison
    normalized = normalized.lower()
    
    # Remove extra spaces
    import re
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def create_safe_playlist_path(base_directory: Path, playlist_name: str) -> Path:
    """
    Create a safe path for playlist directory
    
    Args:
        base_directory: Base output directory
        playlist_name: Raw playlist name from Spotify
        
    Returns:
        Safe Path object for playlist directory
    """
    # Sanitize playlist name
    safe_name = sanitize_directory_name(playlist_name)
    
    # Create full path
    playlist_path = base_directory / safe_name
    
    # Handle duplicate names by adding suffix
    counter = 1
    original_path = playlist_path
    
    while playlist_path.exists():
        # Check if it's actually the same playlist (has tracklist.txt)
        tracklist = playlist_path / "tracklist.txt"
        if tracklist.exists():
            # Could be the same playlist, let caller decide
            break
        
        # Different directory with same name, create unique name
        safe_name_with_counter = f"{safe_name}_{counter}"
        playlist_path = base_directory / safe_name_with_counter
        counter += 1
        
        # Prevent infinite loop
        if counter > 100:
            safe_name_with_counter = f"{safe_name}_{int(time.time())}"
            playlist_path = base_directory / safe_name_with_counter
            break
    
    return playlist_path


def validate_and_create_directory(
    directory_path: Union[str, Path], 
    trusted_source: bool = False
) -> Tuple[bool, Optional[str], Path]:
    """
    Validate and create directory path safely
    
    Args:
        directory_path: Directory path to validate and create
        trusted_source: If True, allows relative paths from configuration
        
    Returns:
        Tuple of (success, error_message, resolved_path)
    """
    try:
        path_obj = Path(directory_path)
        
        # For trusted sources (configuration), resolve relative paths safely
        if trusted_source:
            # Allow relative paths but resolve them to absolute paths
            path_obj = path_obj.expanduser().resolve()
        else:
            # For untrusted sources (user input), apply strict security checks
            path_str = str(path_obj)
            
            # Security check - prevent directory traversal attacks  
            if '..' in path_str:
                return False, "Path contains unsafe components", path_obj
            
            path_obj = path_obj.resolve()
        # Create directory if it doesn't exist
        path_obj.mkdir(parents=True, exist_ok=True)
        
        # Verify it's actually a directory
        if not path_obj.is_dir():
            return False, f"Path exists but is not a directory: {path_obj}", path_obj
        
        # Check write permissions
        test_file = path_obj / ".test_write_permission"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            return False, f"No write permission: {e}", path_obj
        
        return True, None, path_obj
        
    except Exception as e:
        return False, f"Directory validation failed: {e}", Path(directory_path)

def format_duration(seconds: Union[int, float]) -> str:
    """
    Format duration in seconds to human-readable string
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 0:
        return "0:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable string
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes < 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate string similarity using Levenshtein distance
    
    Args:
        str1: First string
        str2: Second string
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not str1 or not str2:
        return 0.0
    
    # Normalize strings
    s1 = str1.lower().strip()
    s2 = str2.lower().strip()
    
    if s1 == s2:
        return 1.0
    
    # Calculate Levenshtein distance
    len1, len2 = len(s1), len(s2)
    
    # Create matrix
    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    
    # Initialize first row and column
    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j
    
    # Fill matrix
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            if s1[i-1] == s2[j-1]:
                cost = 0
            else:
                cost = 1
            
            matrix[i][j] = min(
                matrix[i-1][j] + 1,      # deletion
                matrix[i][j-1] + 1,      # insertion
                matrix[i-1][j-1] + cost  # substitution
            )
    
    # Calculate similarity
    max_len = max(len1, len2)
    if max_len == 0:
        return 1.0
    
    distance = matrix[len1][len2]
    similarity = 1 - (distance / max_len)
    
    return max(0.0, similarity)


def normalize_artist_name(artist: str) -> str:
    """
    Normalize artist name for better matching
    
    Args:
        artist: Original artist name
        
    Returns:
        Normalized artist name
    """
    # Convert to lowercase
    normalized = artist.lower()
    
    # Remove common prefixes/suffixes
    prefixes = ['the ', 'a ', 'an ']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    
    # Remove featuring information
    feat_patterns = [
        r'\s*\(feat\.?.*?\)',
        r'\s*\(ft\.?.*?\)',
        r'\s*feat\.?.*',
        r'\s*ft\.?.*',
        r'\s*featuring.*',
        r'\s*with.*'
    ]
    
    for pattern in feat_patterns:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def normalize_track_title(title: str) -> str:
    """
    Normalize track title for better matching
    
    Args:
        title: Original track title
        
    Returns:
        Normalized track title
    """
    # Convert to lowercase
    normalized = title.lower()
    
    # Remove version information in parentheses
    version_patterns = [
        r'\s*\(.*?version.*?\)',
        r'\s*\(.*?mix.*?\)',
        r'\s*\(.*?edit.*?\)',
        r'\s*\(.*?remix.*?\)',
        r'\s*\(.*?remaster.*?\)',
        r'\s*\[.*?version.*?\]',
        r'\s*\[.*?mix.*?\]',
        r'\s*\[.*?edit.*?\]',
        r'\s*\[.*?remix.*?\]',
        r'\s*\[.*?remaster.*?\]'
    ]
    
    for pattern in version_patterns:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    
    # Remove featuring information
    feat_patterns = [
        r'\s*\(feat\.?.*?\)',
        r'\s*\(ft\.?.*?\)',
        r'\s*feat\.?.*',
        r'\s*ft\.?.*',
        r'\s*featuring.*'
    ]
    
    for pattern in feat_patterns:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def create_search_query(artist: str, title: str, include_official: bool = True) -> List[str]:
    """
    Create search queries for YouTube Music
    
    Args:
        artist: Artist name
        title: Track title
        include_official: Whether to include "official audio" in queries
        
    Returns:
        List of search queries in order of preference
    """
    queries = []
    
    # Normalize inputs
    norm_artist = normalize_artist_name(artist)
    norm_title = normalize_track_title(title)
    
    # Primary query: "Artist - Title"
    queries.append(f"{norm_artist} - {norm_title}")
    
    # Official audio variants
    if include_official:
        queries.append(f"{norm_artist} - {norm_title} official audio")
        queries.append(f"{norm_artist} {norm_title} official audio")
    
    # Space-separated variant
    queries.append(f"{norm_artist} {norm_title}")
    
    # Title-only queries (more aggressive for artist mismatches)
    queries.append(norm_title)  # Always try title only
    queries.append(title.strip())  # Original title
    
    # Additional permissive queries for difficult matches
    if len(title.split()) > 1:
        # Quoted search for exact title match
        queries.append(f'"{norm_title}"')
    
    return queries


def extract_numbers(text: str) -> List[int]:
    """
    Extract all numbers from text
    
    Args:
        text: Input text
        
    Returns:
        List of extracted numbers
    """
    return [int(match) for match in re.findall(r'\d+', text)]


def is_valid_url(url: str) -> bool:
    """
    Check if string is a valid URL
    
    Args:
        url: URL string to validate
        
    Returns:
        True if valid URL
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def generate_file_hash(file_path: Union[str, Path], algorithm: str = 'md5') -> Optional[str]:
    """
    Generate hash of file contents
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256)
        
    Returns:
        Hash string or None if error
    """
    try:
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    except Exception:
        return None


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for retrying functions on failure
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Delay multiplier for exponential backoff
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        raise e
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
            
            return None
        return wrapper
    return decorator


def safe_path_join(*parts: str) -> Path:
    """
    Safely join path parts, ensuring no directory traversal
    
    Args:
        parts: Path parts to join
        
    Returns:
        Safe Path object
    """
    # Filter out dangerous parts
    safe_parts = []
    for part in parts:
        # Remove dangerous components
        clean_part = str(part).replace('..', '').replace('~', '')
        if clean_part and clean_part != '.' and clean_part != '/':
            safe_parts.append(clean_part)
    
    return Path(*safe_parts) if safe_parts else Path('.')


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if necessary
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def get_file_extension(format_name: str) -> str:
    """
    Get file extension for audio format
    
    Args:
        format_name: Format name (mp3, flac, m4a)
        
    Returns:
        File extension with dot
    """
    format_map = {
        'm4a': '.m4a',
        'mp3': '.mp3',
        'flac': '.flac',
        'aac': '.aac',
        'ogg': '.ogg',
        'wav': '.wav'
    }
    
    return format_map.get(format_name.lower(), '.mp3')


def parse_duration_string(duration_str: str) -> Optional[int]:
    """
    Parse duration string to seconds
    
    Args:
        duration_str: Duration string (e.g., "3:45", "1:23:45")
        
    Returns:
        Duration in seconds or None if invalid
    """
    try:
        parts = duration_str.split(':')
        if len(parts) == 2:
            # mm:ss
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        elif len(parts) == 3:
            # hh:mm:ss
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        else:
            return None
    except (ValueError, IndexError):
        return None


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with suffix
    
    Args:
        text: Original text
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    truncate_length = max_length - len(suffix)
    if truncate_length <= 0:
        return suffix[:max_length]
    
    return text[:truncate_length] + suffix


def clean_lyrics_text(lyrics: str) -> str:
    """
    Clean lyrics text by removing metadata and formatting
    
    Args:
        lyrics: Raw lyrics text
        
    Returns:
        Cleaned lyrics text
    """
    if not lyrics:
        return ""
    
    # Remove common metadata patterns
    patterns_to_remove = [
        r'\[Verse.*?\]',
        r'\[Chorus.*?\]',
        r'\[Bridge.*?\]',
        r'\[Intro.*?\]',
        r'\[Outro.*?\]',
        r'\[Pre-Chorus.*?\]',
        r'\[Hook.*?\]',
        r'\[Refrain.*?\]',
        r'\[.*?\]',  # Any remaining bracket content
        r'\(.*?\)',  # Parenthetical content (optional, might contain important info)
    ]
    
    cleaned = lyrics
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove extra whitespace and empty lines
    lines = [line.strip() for line in cleaned.split('\n')]
    lines = [line for line in lines if line]  # Remove empty lines
    
    return '\n'.join(lines)


def validate_lyrics_content(lyrics: str, min_length: int = 50) -> bool:
    """
    Validate if lyrics content is meaningful
    
    Args:
        lyrics: Lyrics text to validate
        min_length: Minimum length for valid lyrics
        
    Returns:
        True if lyrics are valid
    """
    if not lyrics or len(lyrics) < min_length:
        return False
    
    # Check for common "no lyrics" indicators
    no_lyrics_indicators = [
        'instrumental',
        'no lyrics',
        'music only',
        '[instrumental]',
        'lyrics not available',
        'sorry, no lyrics'
    ]
    
    lyrics_lower = lyrics.lower()
    for indicator in no_lyrics_indicators:
        if indicator in lyrics_lower:
            return False
    
    # Check if it's mostly non-text characters
    text_chars = sum(1 for c in lyrics if c.isalnum() or c.isspace())
    if text_chars / len(lyrics) < 0.7:  # Less than 70% text
        return False
    
    return True


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()


def format_timestamp(timestamp: Union[str, datetime]) -> str:
    """
    Format timestamp for display
    
    Args:
        timestamp: Timestamp string or datetime object
        
    Returns:
        Formatted timestamp string
    """
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return timestamp
    else:
        dt = timestamp
    
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def create_backup_filename(original_path: Union[str, Path]) -> Path:
    """
    Create backup filename with timestamp
    
    Args:
        original_path: Original file path
        
    Returns:
        Backup file path
    """
    path = Path(original_path)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if path.suffix:
        backup_name = f"{path.stem}.backup_{timestamp}{path.suffix}"
    else:
        backup_name = f"{path.name}.backup_{timestamp}"
    
    return path.parent / backup_name