#!/bin/bash
# Installation script for Playlist-Downloader

echo "🎵 Installing Playlist-Downloader..."

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 8)" || {
    echo "❌ Python 3.8+ required"
    exit 1
}

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .

echo "✅ Installation complete!"
echo "Next steps:"
echo "1. Set up your .env file with API credentials"
echo "2. Run: playlist-dl --help"
