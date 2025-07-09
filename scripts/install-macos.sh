#!/bin/bash

# Playlist-Downloader macOS Installation Script
# Automatically installs all dependencies and sets up the application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/verryx-02/playlist-downloader"
INSTALL_DIR="$HOME/Desktop/playlist-downloader"
PYTHON_MIN_VERSION="3.8"

# Helper functions
print_header() {
    echo ""
    echo -e "${PURPLE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║                     Playlist-Downloader                       ║${NC}"
    echo -e "${PURPLE}║                                                               ║${NC}"
    echo -e "${PURPLE}║                 macOS Automatic Installer                     ║${NC}"
    echo -e "${PURPLE}║                                                               ║${NC}"
    echo -e "${PURPLE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python version
check_python_version() {
    if command_exists python3; then
        local version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        local required_version="$PYTHON_MIN_VERSION"
        
        if [ "$(printf '%s\n' "$required_version" "$version" | sort -V | head -n1)" = "$required_version" ]; then
            return 0
        fi
    fi
    return 1
}

# Check if curl is available (should be on all modern macOS)
check_curl() {
    if ! command_exists curl; then
        print_warning "curl not found. Installing via Homebrew..."
        if command_exists brew; then
            brew install curl
            if ! command_exists curl; then
                print_error "Failed to install curl"
                print_info "Please install curl manually or download the project from:"
                print_info "$REPO_URL"
                exit 1
            fi
        else
            print_error "curl not found and Homebrew not available"
            print_info "Please install curl manually or download the project from:"
            print_info "$REPO_URL"
            exit 1
        fi
    fi
}

# Check if unzip is available (should be on all macOS)
check_unzip() {
    if ! command_exists unzip; then
        print_error "unzip command not found. Please install unzip first."
        print_info "You can also download the project manually from:"
        print_info "$REPO_URL"
        exit 1
    fi
}

# Check SSH connectivity (no longer need expect)
check_ssh() {
    if ! command_exists ssh; then
        print_error "SSH not found. SSH is required for tunnel setup."
        exit 1
    fi
    print_info "SSH available for tunnel automation"
}

# Install Homebrew
install_homebrew() {
    print_step "Installing Homebrew (macOS package manager)..."
    
    if command_exists brew; then
        print_info "Homebrew already installed"
        return 0
    fi
    
    print_info "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    if command_exists brew; then
        print_success "Homebrew installed successfully"
    else
        print_error "Failed to install Homebrew"
        exit 1
    fi
}

# Install Python
install_python() {
    print_step "Installing Python ${PYTHON_MIN_VERSION}+..."
    
    if check_python_version; then
        local version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
        print_info "Python $version already installed"
        return 0
    fi
    
    print_info "Installing Python via Homebrew..."
    brew install python@3.11
    
    # Ensure python3 is available
    if ! command_exists python3; then
        brew link python@3.11
    fi
    
    if check_python_version; then
        local version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
        print_success "Python $version installed successfully"
    else
        print_error "Failed to install Python ${PYTHON_MIN_VERSION}+"
        exit 1
    fi
}

# Install FFmpeg
install_ffmpeg() {
    print_step "Installing FFmpeg (audio processing)..."
    
    if command_exists ffmpeg; then
        print_info "FFmpeg already installed"
        return 0
    fi
    
    print_info "Installing FFmpeg via Homebrew..."
    brew install ffmpeg
    
    if command_exists ffmpeg; then
        print_success "FFmpeg installed successfully"
    else
        print_error "Failed to install FFmpeg"
        exit 1
    fi
}

# Setup project directory and download files
setup_project() {
    print_step "Setting up Playlist-Downloader project..."
    
    # Check if directory already exists
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Existing installation found at $INSTALL_DIR"
        
        while true; do
            read -p "Do you want to remove it and reinstall? (y/N): " yn
            case $yn in
                [Yy]* ) 
                    print_info "Removing existing installation..."
                    rm -rf "$INSTALL_DIR"
                    break
                    ;;
                [Nn]* | "" ) 
                    print_info "Using existing installation directory"
                    cd "$INSTALL_DIR"
                    return 0
                    ;;
                * ) echo "Please answer yes or no.";;
            esac
        done
    fi
    
    # Create directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Download project
    print_info "Downloading project from GitHub..."
    local zip_file="playlist-downloader.zip"
    
    if ! curl -L -o "$zip_file" "$REPO_URL/archive/refs/heads/main.zip"; then
        print_error "Failed to download project"
        print_info "You can download manually from: $REPO_URL"
        exit 1
    fi
    
    # Extract files
    print_info "Extracting project files..."
    if ! unzip -q "$zip_file"; then
        print_error "Failed to extract project files"
        exit 1
    fi
    
    # Move files from subdirectory to current directory
    local extracted_dir="playlist-downloader-main"
    if [ -d "$extracted_dir" ]; then
        mv "$extracted_dir"/* . 2>/dev/null || true
        mv "$extracted_dir"/.[^.]* . 2>/dev/null || true  # Move hidden files, ignore errors
        rmdir "$extracted_dir"
    fi
    
    # Clean up ZIP file
    rm -f "$zip_file"
    
    if [ -f "requirements.txt" ] && [ -f "setup.py" ]; then
        print_success "Project files downloaded and extracted"
    else
        print_error "Invalid project structure. Missing requirements.txt or setup.py"
        exit 1
    fi
}

# Setup Python virtual environment
setup_virtual_environment() {
    print_step "Setting up Python virtual environment..."
    
    cd "$INSTALL_DIR"
    
    # Check if virtual environment already exists
    if [ -d ".venv" ]; then
        echo ""
        echo -e "${YELLOW}⚠️  Existing virtual environment found${NC}"
        echo -e "${BLUE}Directory: $INSTALL_DIR/.venv${NC}"
        echo ""
        echo -e "${YELLOW}Options:${NC}"
        echo -e "${BLUE}1. Keep existing environment (recommended if already working)${NC}"
        echo -e "${BLUE}2. Remove and recreate environment${NC}"
        echo ""
        
        while true; do
            read -p "Do you want to keep the existing virtual environment? (y/N): " yn
            case $yn in
                [Yy]* ) 
                    print_info "Keeping existing virtual environment"
                    # Test if the environment works
                    if source .venv/bin/activate && python3 --version; then
                        print_success "Existing virtual environment is functional"
                        return 0
                    else
                        print_warning "Existing environment seems broken, recreating..."
                        rm -rf .venv
                        break
                    fi
                    ;;
                [Nn]* | "" ) 
                    print_info "Removing and recreating virtual environment..."
                    rm -rf .venv
                    break
                    ;;
                * ) echo "Please answer yes or no.";;
            esac
        done
    fi
    
    # Create new virtual environment
    print_info "Creating Python virtual environment..."
    python3 -m venv .venv
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Verify activation
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        print_success "Virtual environment created and activated"
        python3 --version
    else
        print_error "Failed to activate virtual environment"
        exit 1
    fi
}

# Install Python dependencies
install_dependencies() {
    print_step "Installing Python dependencies..."
    
    cd "$INSTALL_DIR"
    source .venv/bin/activate
    
    # Upgrade pip first (suppress output to avoid broken pipe)
    python3 -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1
    
    # Install requirements (suppress output to avoid broken pipe)
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt >/dev/null 2>&1
    else
        pip install spotipy yt-dlp mutagen pyyaml requests beautifulsoup4 >/dev/null 2>&1
    fi
    
    # Install the package in development mode with new setup method
    pip install --use-pep517 -e . >/dev/null 2>&1
    
    print_success "Dependencies ready"
}

# Verify installation
verify_installation() {
    print_step "Verifying installation..."
    
    cd "$INSTALL_DIR"
    source .venv/bin/activate
    
    # Test if playlist-dl command works
    if playlist-dl --help >/dev/null 2>&1; then
        print_success "Playlist-Downloader command working"
    else
        print_error "playlist-dl command not working"
        exit 1
    fi
    
    # Test dependencies
    local missing_deps=()
    
    if ! command_exists ffmpeg; then
        missing_deps+=("FFmpeg")
    fi
    
    if ! check_python_version; then
        missing_deps+=("Python ${PYTHON_MIN_VERSION}+")
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        exit 1
    fi
    
    print_success "All dependencies verified"
}

# Extract URL from SSH output
extract_tunnel_url() {
    local output="$1"
    local url=""
    
    # Method 1: Look for the specific "tunneled with tls termination" pattern
    # This matches lines like: "0e0838e2fec5d5.lhr.life tunneled with tls termination, https://0e0838e2fec5d5.lhr.life"
    if [[ "$output" =~ [a-z0-9]+\.lhr\.life\ tunneled\ with\ tls\ termination,\ (https://[a-z0-9]+\.lhr\.life) ]]; then
        url="${BASH_REMATCH[1]}"
        echo "$url"
        return 0
    fi
    
    # Method 2: Alternative pattern for localhost.run domains
    if [[ "$output" =~ [a-z0-9]+\.localhost\.run\ tunneled\ with\ tls\ termination,\ (https://[a-z0-9]+\.localhost\.run) ]]; then
        url="${BASH_REMATCH[1]}"
        echo "$url"
        return 0
    fi
    
    # Method 3: Fallback - look for any tunnel URL but NOT admin/docs URLs
    # Exclude admin.localhost.run, localhost.run/docs, etc.
    if [[ "$output" =~ (https://[a-z0-9]+\.lhr\.life) ]] && [[ ! "${BASH_REMATCH[1]}" =~ admin|docs|twitter ]]; then
        url="${BASH_REMATCH[1]}"
        echo "$url"
        return 0
    fi
    
    # Method 4: Fallback for localhost.run but exclude admin URLs
    if [[ "$output" =~ (https://[a-z0-9]+\.localhost\.run) ]] && [[ ! "${BASH_REMATCH[1]}" =~ admin|docs ]]; then
        url="${BASH_REMATCH[1]}"
        echo "$url"
        return 0
    fi
    
    return 1
}

# Attempt SSH tunnel with robust monitoring
attempt_ssh_tunnel() {
    local attempt_num="$1"
    local timeout_seconds="$2"
    local output_file="/tmp/ssh_tunnel_output_${attempt_num}.log"
    
    # Clean up any existing SSH processes
    pkill -f "ssh -R 80:localhost:8080 nokey@localhost.run" 2>/dev/null || true
    sleep 1
    
    # Remove old output file
    rm -f "$output_file"
    
    # Start SSH tunnel in background
    ssh -R 80:localhost:8080 nokey@localhost.run > "$output_file" 2>&1 &
    local ssh_pid=$!
    
    # Monitor output for specified timeout
    local counter=0
    local max_iterations=$((timeout_seconds * 10))  # Check every 0.1 seconds
    
    while [ $counter -lt $max_iterations ]; do
        # Check if SSH process is still running
        if ! kill -0 $ssh_pid 2>/dev/null; then
            break
        fi
        
        # Check if output file exists and has content
        if [ -f "$output_file" ]; then
            local output_content=$(cat "$output_file" 2>/dev/null || echo "")
            
            # Look for successful tunnel establishment
            if [[ "$output_content" =~ tunneled\ with\ tls\ termination ]] || 
               [[ "$output_content" =~ [a-z0-9]+\.lhr\.life ]] ||
               [[ "$output_content" =~ [a-z0-9]+\.localhost\.run ]]; then
                
                # Extract URL
                local tunnel_url=$(extract_tunnel_url "$output_content")
                if [ -n "$tunnel_url" ]; then
                    # DO NOT kill SSH process - keep it running for authentication
                    # Clean up output file  
                    rm -f "$output_file"
                    
                    # Return URL and PID (separated by |)
                    echo "$tunnel_url|$ssh_pid"
                    return 0
                fi
            fi
            
            # Check for connection errors
            if [[ "$output_content" =~ "Connection refused" ]] ||
               [[ "$output_content" =~ "Could not resolve hostname" ]] ||
               [[ "$output_content" =~ "Network is unreachable" ]]; then
                break
            fi
        fi
        
        sleep 0.1
        ((counter++))
    done
    
    # Timeout or error occurred, clean up
    kill $ssh_pid 2>/dev/null || true
    wait $ssh_pid 2>/dev/null || true
    
    # Clean up output file
    rm -f "$output_file"
    
    return 1
}

# Setup SSH tunnel and automatically capture URL
setup_ssh_tunnel() {
    # All messages go to stderr to avoid mixing with return value
    echo -e "${CYAN}[STEP]${NC} Setting up SSH tunnel and capturing callback URL..." >&2
    
    local tunnel_result=""
    local max_attempts=3
    local timeouts=(15 25 35)  # Increasing timeouts for each attempt
    
    # Try multiple attempts with increasing timeouts
    for i in $(seq 1 $max_attempts); do
        tunnel_result=$(attempt_ssh_tunnel $i ${timeouts[$((i-1))]})
        
        if [ -n "$tunnel_result" ]; then
            echo -e "${GREEN}[SUCCESS]${NC} SSH tunnel established successfully on attempt $i" >&2
            break
        fi
        
        if [ $i -lt $max_attempts ]; then
            echo -e "${YELLOW}[WARNING]${NC} Attempt $i failed, retrying in 3 seconds..." >&2
            sleep 3
        fi
    done
    
    if [[ -n "$tunnel_result" ]]; then
        # Parse tunnel_url and ssh_pid from result
        local tunnel_url=$(echo "$tunnel_result" | cut -d'|' -f1)
        local ssh_pid=$(echo "$tunnel_result" | cut -d'|' -f2)
        local callback_url="${tunnel_url}/callback"
        
        echo -e "${GREEN}[SUCCESS]${NC} Callback URL generated: $callback_url" >&2
        
        # Update config file automatically
        update_config_file "$callback_url" >&2
        
        echo "" >&2
        echo -e "${GREEN}SSH tunnel setup completed!${NC}" >&2
        echo "" >&2
        
        # Return ONLY ssh_pid to stdout
        echo "$ssh_pid"
        return 0
    else
        echo -e "${RED}[ERROR]${NC} All SSH tunnel attempts failed" >&2
        return 1
    fi
}

# Update config file with output directory
update_output_directory() {
    local config_file="$INSTALL_DIR/config/config.yaml"
    local output_dir="$HOME/Desktop/Playlist_Downloads"
    
    print_step "Updating output directory configuration..."
    
    if [ ! -f "$config_file" ]; then
        return 1
    fi
    
    # Create backup
    cp "$config_file" "$config_file.backup"
    
    # Use sed to update output directory while preserving formatting and comments
    local temp_file="/tmp/config_output_dir.yaml"
    cp "$config_file" "$temp_file"
    
    # Update output_directory if it exists
    if grep -q "^[[:space:]]*output_directory:" "$temp_file"; then
        sed -i.bak "s|^[[:space:]]*output_directory:.*|  output_directory: \"$output_dir\"|" "$temp_file"
    else
        # Add output_directory to download section
        sed -i.bak "/^download:/a\\
  output_directory: \"$output_dir\"" "$temp_file"
    fi
    
    # Clean up sed backup files
    rm -f "$temp_file.bak"
    
    # Verify the update worked
    if grep -q "output_directory:" "$temp_file"; then
        mv "$temp_file" "$config_file"
        print_success "Output directory set to: $output_dir"
        rm -f "$config_file.backup"
        return 0
    else
        mv "$config_file.backup" "$config_file"
        rm -f "$temp_file"
        return 1
    fi
}

# Close SSH tunnel after authentication
close_ssh_tunnel() {
    local ssh_pid="$1"
    
    if [ -n "$ssh_pid" ]; then
        print_info "Closing SSH tunnel (PID: $ssh_pid)..."
        kill $ssh_pid 2>/dev/null || true
        wait $ssh_pid 2>/dev/null || true
        print_success "SSH tunnel closed"
    fi
}

# Collect Spotify credentials from user
collect_spotify_credentials() {
    # All output goes to stderr except the final return value
    echo "" >&2
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}" >&2
    echo -e "${YELLOW}Spotify Configuration${NC}" >&2
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}" >&2
    echo "" >&2
    echo -e "${BLUE}Please provide your Spotify App credentials:${NC}" >&2
    echo -e "${PURPLE}(You can get these from: https://developer.spotify.com/dashboard)${NC}" >&2
    echo "" >&2
    
    # Get Client ID
    while true; do
        echo -n "Enter your Spotify Client ID: " >&2
        read client_id
        if [ -n "$client_id" ] && [ ${#client_id} -ge 10 ]; then
            break
        else
            echo -e "${RED}Client ID seems too short. Please enter a valid Client ID.${NC}" >&2
        fi
    done
    
    # Get Client Secret
    while true; do
        echo -n "Enter your Spotify Client Secret: " >&2
        read client_secret
        if [ -n "$client_secret" ] && [ ${#client_secret} -ge 10 ]; then
            break
        else
            echo -e "${RED}Client Secret seems too short. Please enter a valid Client Secret.${NC}" >&2
        fi
    done
    
    echo "" >&2
    echo -e "${GREEN}Credentials received!${NC}" >&2
    echo -e "${BLUE}Client ID: ${client_id:0:8}...${NC}" >&2
    echo -e "${BLUE}Client Secret: ${client_secret:0:8}...${NC}" >&2
    echo "" >&2
    
    # Return ONLY the credentials (to stdout)
    echo "$client_id|$client_secret"
}

# Update config file with Spotify credentials
update_spotify_credentials() {
    local client_id="$1"
    local client_secret="$2"
    local config_file="$INSTALL_DIR/config/config.yaml"
    
    print_step "Updating configuration file with Spotify credentials..."
    
    if [ ! -f "$config_file" ]; then
        print_error "Config file not found at $config_file"
        return 1
    fi
    
    # Create backup
    cp "$config_file" "$config_file.backup"
    
    # Use sed to update credentials while preserving formatting and comments
    local temp_file="/tmp/config_update.yaml"
    cp "$config_file" "$temp_file"
    
    # Update client_id if it exists
    if grep -q "^[[:space:]]*client_id:" "$temp_file"; then
        sed -i.bak "s/^[[:space:]]*client_id:.*/  client_id: \"$client_id\"/" "$temp_file"
    else
        # Add client_id to spotify section
        sed -i.bak "/^spotify:/a\\
  client_id: \"$client_id\"" "$temp_file"
    fi
    
    # Update client_secret if it exists
    if grep -q "^[[:space:]]*client_secret:" "$temp_file"; then
        sed -i.bak "s/^[[:space:]]*client_secret:.*/  client_secret: \"$client_secret\"/" "$temp_file"
    else
        # Add client_secret to spotify section
        sed -i.bak "/^[[:space:]]*client_id:/a\\
  client_secret: \"$client_secret\"" "$temp_file"
    fi
    
    # Clean up sed backup files
    rm -f "$temp_file.bak"
    
    # Verify the update worked
    if grep -q "client_id:" "$temp_file" && grep -q "client_secret:" "$temp_file"; then
        mv "$temp_file" "$config_file"
        print_success "Spotify credentials updated in config file"
        rm -f "$config_file.backup"
        return 0
    else
        print_error "Failed to update Spotify credentials"
        mv "$config_file.backup" "$config_file"
        rm -f "$temp_file"
        return 1
    fi
}

# Perform automatic Spotify login
perform_spotify_login() {
    print_step "Performing Spotify authentication..."
    
    cd "$INSTALL_DIR"
    source .venv/bin/activate
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Starting Spotify Authentication${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}The browser will open automatically for Spotify login...${NC}"
    echo -e "${PURPLE}Follow the instructions in your browser to complete authentication.${NC}"
    echo ""
    
    # Run the login command
    if playlist-dl auth login; then
        echo ""
        echo -e "${GREEN}Spotify authentication completed successfully!${NC}"
        echo ""
        return 0
    else
        echo ""
        echo -e "${RED}Spotify authentication failed${NC}"
        echo -e "${YELLOW}You may need to run 'playlist-dl auth login' manually later${NC}"
        echo ""
        return 1
    fi
}
update_config_file() {
    local callback_url="$1"
    local config_file="$INSTALL_DIR/config/config.yaml"
    
    print_step "Updating configuration file with callback URL..."
    
    if [ ! -f "$config_file" ]; then
        # Check for config_example.yaml
        local example_config="$INSTALL_DIR/config/config_example.yaml"
        if [ -f "$example_config" ]; then
            print_info "Copying config_example.yaml to config.yaml..."
            cp "$example_config" "$config_file"
        else
            print_error "No config file found at $config_file"
            return 1
        fi
    fi
    
    # Update the redirect_url field using a more robust approach
    if command_exists sed; then
        # Create backup
        cp "$config_file" "$config_file.backup"
        
        # Use a temporary file to avoid sed issues with special characters
        local temp_file="/tmp/config_temp.yaml"
        
        # Check if redirect_url field exists
        if grep -q "redirect_url:" "$config_file"; then
            # Field exists, replace it using awk (more robust than sed for this)
            awk -v url="$callback_url" '
                /^[[:space:]]*redirect_url:/ { 
                    sub(/redirect_url:.*/, "redirect_url: \"" url "\"")
                }
                { print }
            ' "$config_file" > "$temp_file"
            
            if [ -f "$temp_file" ] && [ -s "$temp_file" ]; then
                mv "$temp_file" "$config_file"
                print_success "Config file updated with callback URL"
            else
                print_warning "Failed to update config file automatically"
                mv "$config_file.backup" "$config_file"
                rm -f "$temp_file"
                return 1
            fi
        else
            # Field doesn't exist, add it
            echo "redirect_url: \"$callback_url\"" >> "$config_file"
            print_success "Added callback URL to config file"
        fi
        
        # Clean up backup if successful
        rm -f "$config_file.backup"
    else
        print_warning "sed and awk not available, cannot update config file automatically"
        print_info "Please manually update $config_file with:"
        print_info "redirect_url: \"$callback_url\""
        return 1
    fi
}

# Activate environment and show ready message
activate_environment() {
    cd "$INSTALL_DIR"
    source .venv/bin/activate
    print_success "Virtual environment activated"
}

# Show final success message with activation instructions
print_final_success() {
    echo ""
    echo -e "${GREEN}Playlist-Downloader Setup Complete!${NC}"
    echo ""
    echo -e "${GREEN}Everything is ready to use!${NC}"
    echo ""
    echo -e "${YELLOW}To use Playlist-Downloader:${NC}"
    echo -e "${CYAN}  cd ~/Desktop/playlist-downloader && source .venv/bin/activate${NC}"
    echo ""
    echo -e "${BLUE}Then try your first playlist download:${NC}"
    echo -e "${CYAN}  playlist-dl download \"https://open.spotify.com/playlist/YOUR_PLAYLIST_URL\"${NC}"
    echo ""
    echo -e "${PURPLE}For more commands and options:${NC}"
    echo -e "${CYAN}  playlist-dl --help${NC}"
    echo ""
    echo -e "${GREEN}Happy downloading!${NC}"
    echo ""
}

# Check if running on macOS
check_macos() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "This script is designed for macOS only"
        print_info "For other operating systems, please check:"
        print_info "$REPO_URL#installation"
        exit 1
    fi
}

# Main installation function
main() {
    print_header
    
    # System checks
    check_macos
    check_unzip
    
    # Installation steps
    install_homebrew
    check_curl
    check_ssh
    install_python
    install_ffmpeg
    setup_project
    setup_virtual_environment
    install_dependencies
    verify_installation
    
    # Automatic configuration steps
    echo ""
    echo -e "${GREEN}Installation completed successfully!${NC}"
    echo ""
    
    # Setup SSH tunnel and automatically update config (keep tunnel running)
    local ssh_pid=""
    ssh_pid=$(setup_ssh_tunnel)
    
    if [ $? -ne 0 ]; then
        print_error "SSH tunnel setup failed. You may need to configure manually."
        exit 1
    fi
    
    # Activate environment 
    activate_environment
    
    # Update output directory configuration
    update_output_directory
    
    # Collect Spotify credentials from user
    local credentials=""
    credentials=$(collect_spotify_credentials)
    local client_id=$(echo "$credentials" | cut -d'|' -f1)
    local client_secret=$(echo "$credentials" | cut -d'|' -f2)
    
    # Update config file with Spotify credentials
    if ! update_spotify_credentials "$client_id" "$client_secret"; then
        print_error "Failed to update Spotify credentials in config file"
        exit 1
    fi
    
    # Perform automatic Spotify login
    if ! perform_spotify_login; then
        print_warning "Automatic login failed, but configuration is complete"
    fi
    
    # Close SSH tunnel after authentication
    close_ssh_tunnel "$ssh_pid"
    
    # Show final success message
    print_final_success
}

# Trap errors
trap 'print_error "Installation failed at line $LINENO"' ERR

# Run main function
main "$@"