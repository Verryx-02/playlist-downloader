#!/bin/bash

# Playlist-Downloader macOS Installation Script
# Automatically installs all dependencies and sets up the application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/verryx-02/playlist-downloader"
INSTALL_DIR="$HOME/playlist-downloader"
PYTHON_MIN_VERSION="3.8"

# Helper functions
print_header() {
    echo ""
    echo -e "${PURPLE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║                    🎵 Playlist-Downloader 🎵                   ║${NC}"
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

# Check if expect is available for SSH tunnel automation
check_expect() {
    if ! command_exists expect; then
        print_info "Installing expect for SSH tunnel automation..."
        brew install expect
        
        if ! command_exists expect; then
            print_error "Failed to install expect"
            exit 1
        fi
    fi
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

# Download and setup project
setup_project() {
    print_step "Setting up Playlist-Downloader project..."
    
    # Remove existing directory if it exists
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Existing installation found at $INSTALL_DIR"
        read -p "Do you want to remove it and reinstall? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
            print_info "Removed existing installation"
        else
            print_info "Using existing installation directory"
            cd "$INSTALL_DIR"
            return 0
        fi
    fi
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Download repository as ZIP
    print_info "Downloading repository from $REPO_URL..."
    local zip_url="${REPO_URL}/archive/refs/heads/main.zip"
    local zip_file="playlist-downloader.zip"
    
    if ! curl -L -o "$zip_file" "$zip_url"; then
        print_error "Failed to download repository"
        exit 1
    fi
    
    # Extract ZIP
    print_info "Extracting project files..."
    if ! unzip -q "$zip_file"; then
        print_error "Failed to extract repository"
        exit 1
    fi
    
    # Move files from subdirectory to current directory
    local extracted_dir="playlist-downloader-main"
    if [ -d "$extracted_dir" ]; then
        mv "$extracted_dir"/* .
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
            read -p "Do you want to keep the existing virtual environment? (y/N): " -n 1 -r
            echo
            
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Keeping existing virtual environment"
                
                # Verify the existing environment works
                if [ -f ".venv/bin/activate" ]; then
                    source .venv/bin/activate
                    
                    # Test if Python works and has basic packages
                    if python3 -c "import sys; print(f'Python {sys.version}')" 2>/dev/null; then
                        print_success "Existing virtual environment is functional"
                        
                        # Check if requirements are installed
                        if pip list | grep -q "spotipy\|yt-dlp\|mutagen" 2>/dev/null; then
                            print_info "Core packages appear to be installed"
                            print_info "Will verify and update dependencies if needed..."
                            return 0
                        else
                            print_warning "Core packages not found, will install dependencies"
                            return 0
                        fi
                    else
                        print_error "Existing virtual environment appears corrupted"
                        print_info "Will recreate the environment..."
                        rm -rf .venv
                    fi
                else
                    print_error "Existing virtual environment is invalid"
                    print_info "Will recreate the environment..."
                    rm -rf .venv
                fi
                break
            elif [[ $REPLY =~ ^[Nn]$ ]] || [[ $REPLY == "" ]]; then
                print_info "Removing existing virtual environment"
                rm -rf .venv
                break
            else
                echo -e "${RED}Please answer y (yes) or n (no)${NC}"
            fi
        done
    fi
    
    # Create new virtual environment if needed
    if [ ! -d ".venv" ]; then
        print_info "Creating new virtual environment..."
        python3 -m venv .venv
        
        if [ ! -d ".venv" ] || [ ! -f ".venv/bin/activate" ]; then
            print_error "Failed to create virtual environment"
            exit 1
        fi
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip --quiet
    
    print_success "Virtual environment ready"
}

# Install Python dependencies
install_dependencies() {
    print_step "Installing Python dependencies..."
    
    cd "$INSTALL_DIR"
    source .venv/bin/activate
    
    # Check if requirements.txt exists
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found"
        exit 1
    fi
    
    # Check if main packages are already installed
    local packages_installed=true
    local core_packages=("spotipy" "yt-dlp" "mutagen" "click" "pyyaml")
    
    for package in "${core_packages[@]}"; do
        if ! pip list | grep -q "^$package " 2>/dev/null; then
            packages_installed=false
            break
        fi
    done
    
    if [ "$packages_installed" = true ]; then
        print_info "Core packages already installed"
        
        # Ask if user wants to update/reinstall
        echo ""
        read -p "Do you want to update/reinstall dependencies? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Updating dependencies..."
            pip install -r requirements.txt --upgrade --quiet
        else
            print_info "Skipping dependency installation"
        fi
    else
        print_info "Installing missing dependencies..."
        pip install -r requirements.txt --quiet
    fi
    
    # Always try to install the package itself
    print_info "Installing/updating Playlist-Downloader..."
    pip install -e . --quiet
    
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

# Setup SSH tunnel and automatically capture URL
setup_ssh_tunnel() {
    print_step "Setting up SSH tunnel and capturing callback URL..."
    
    print_info "Starting automated SSH tunnel to localhost.run..."
    print_info "This may take a few seconds..."
    
    # Create expect script for SSH tunnel automation
    local expect_script="/tmp/ssh_tunnel_auto.exp"
    
    cat > "$expect_script" << 'EXPECT_EOF'
#!/usr/bin/expect -f

set timeout 60
log_user 0

spawn ssh -R 80:localhost:8080 nokey@localhost.run

set tunnel_url ""

expect {
    -re "(https://[a-zA-Z0-9]+\.lhr\.life)" {
        set tunnel_url $expect_out(1,string)
        puts "CAPTURED_URL:$tunnel_url"
        exp_continue
    }
    -re "(https://[a-zA-Z0-9]+\.localhost\.run)" {
        set tunnel_url $expect_out(1,string)
        puts "CAPTURED_URL:$tunnel_url"
        exp_continue
    }
    "Connected to localhost.run" {
        exp_continue
    }
    timeout {
        puts "TUNNEL_ERROR:Timeout waiting for tunnel URL"
        exit 1
    }
    eof {
        if {$tunnel_url ne ""} {
            puts "CAPTURED_URL:$tunnel_url"
            exit 0
        } else {
            puts "TUNNEL_ERROR:Connection closed without URL"
            exit 1
        }
    }
}

sleep 3

if {$tunnel_url ne ""} {
    puts "CAPTURED_URL:$tunnel_url"
    exit 0
} else {
    puts "TUNNEL_ERROR:No URL found"
    exit 1
}
EXPECT_EOF
    
    chmod +x "$expect_script"
    
    # Run expect script and capture output
    local tunnel_output
    tunnel_output=$("$expect_script" 2>&1)
    
    # Extract URL from output
    if [[ "$tunnel_output" =~ CAPTURED_URL:(https://[^[:space:]]+) ]]; then
        local tunnel_url="${BASH_REMATCH[1]}"
        local callback_url="${tunnel_url}/callback"
        
        print_success "SSH tunnel URL captured: $tunnel_url"
        print_success "Callback URL generated: $callback_url"
        
        # Kill any remaining SSH processes
        pkill -f "ssh -R 80:localhost:8080" 2>/dev/null || true
        
        # Save URLs to files for reference
        echo "$tunnel_url" > "$INSTALL_DIR/tunnel_url.txt"
        echo "$callback_url" > "$INSTALL_DIR/callback_url.txt"
        
        # Update config file automatically
        update_config_file "$callback_url"
        
        echo ""
        echo -e "${GREEN}✅ SSH tunnel setup completed automatically!${NC}"
        echo -e "${CYAN}Tunnel URL: $tunnel_url${NC}"
        echo -e "${CYAN}Callback URL: $callback_url${NC}"
        echo -e "${BLUE}URLs saved to: $INSTALL_DIR/tunnel_url.txt and callback_url.txt${NC}"
        echo ""
        
        # Clean up
        rm -f "$expect_script"
        return 0
    else
        print_error "Failed to automatically capture SSH tunnel URL"
        print_info "Output received: $tunnel_output"
        print_warning "You'll need to set up the SSH tunnel manually"
        
        echo ""
        echo -e "${YELLOW}Manual SSH tunnel setup:${NC}"
        echo -e "${BLUE}1. Run in a separate terminal: ssh -R 80:localhost:8080 nokey@localhost.run${NC}"
        echo -e "${BLUE}2. Copy the generated URL${NC}"
        echo -e "${BLUE}3. Add '/callback' to the end${NC}"
        echo -e "${BLUE}4. Update config/config.yaml with your callback URL${NC}"
        echo ""
        
        # Clean up
        rm -f "$expect_script"
        return 1
    fi
}

# Update config file with callback URL
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
    
    # Update the redirect_url field using sed
    if command_exists sed; then
        # Create backup
        cp "$config_file" "$config_file.backup"
        
        # Update redirect_url field
        if grep -q "redirect_url:" "$config_file"; then
            # Field exists, replace it
            if sed -i.tmp "s|redirect_url:.*|redirect_url: \"$callback_url\"|g" "$config_file"; then
                rm -f "$config_file.tmp"
                print_success "Updated redirect_url in config.yaml"
            else
                print_error "Failed to update config file"
                mv "$config_file.backup" "$config_file"
                return 1
            fi
        else
            print_warning "redirect_url field not found in config file"
            return 1
        fi
        
        # Remove backup if successful
        rm -f "$config_file.backup"
        
        print_info "Configuration file updated successfully"
        print_info "Location: $config_file"
        
    else
        print_error "sed command not available for config update"
        return 1
    fi
}

# Activate environment and show ready message
activate_environment() {
    print_step "Activating Python environment..."
    
    cd "$INSTALL_DIR"
    
    # Create activation command for the user
    echo ""
    echo -e "${GREEN}🎵 Playlist-Downloader is ready! 🎵${NC}"
    echo ""
    echo -e "${CYAN}To use Playlist-Downloader:${NC}"
    echo -e "1. Open a new terminal"
    echo -e "2. Run these commands:"
    echo ""
    echo -e "${BLUE}cd $INSTALL_DIR${NC}"
    echo -e "${BLUE}source .venv/bin/activate${NC}"
    echo ""
    echo -e "${CYAN}Then you can use all playlist-dl commands!${NC}"
    echo ""
}

# Print final configuration steps
print_configuration_steps() {
    echo ""
    echo -e "${YELLOW}📋 Final Configuration Steps:${NC}"
    echo ""
    echo -e "${BLUE}1. Configure Spotify API:${NC}"
    echo -e "   • Go to: ${CYAN}https://developer.spotify.com/dashboard${NC}"
    echo -e "   • Create new app"
    
    if [ -f "$INSTALL_DIR/callback_url.txt" ]; then
        local saved_url=$(cat "$INSTALL_DIR/callback_url.txt")
        echo -e "   • Use this redirect URI: ${GREEN}$saved_url${NC}"
    else
        echo -e "   • Use your callback URL as redirect URI"
    fi
    
    echo -e "   • Copy Client ID and Client Secret"
    echo ""
    echo -e "${BLUE}2. Add your Spotify credentials to config:${NC}"
    echo -e "   • Edit: ${CYAN}$INSTALL_DIR/config/config.yaml${NC}"
    echo -e "   • Replace ${YELLOW}\"YOUR CLIENT ID\"${NC} with your actual Client ID"
    echo -e "   • Replace ${YELLOW}\"YOUR CLIENT SECRET\"${NC} with your actual Client Secret"
    echo -e "   • ${GREEN}✅ Redirect URL already configured automatically!${NC}"
    echo ""
    echo -e "${BLUE}3. Authenticate with Spotify:${NC}"
    echo -e "   playlist-dl auth login"
    echo ""
    echo -e "${BLUE}4. Test your first download:${NC}"
    echo -e "   playlist-dl download \"https://open.spotify.com/playlist/YOUR_PLAYLIST_URL\""
    echo ""
    echo -e "${CYAN}💡 For detailed guides, check:${NC}"
    echo -e "   ${REPO_URL}#readme"
    echo ""
    echo -e "${GREEN}🎵 Almost ready! Just add your Spotify credentials and you're done! 🎵${NC}"
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
    check_expect
    install_python
    install_ffmpeg
    setup_project
    setup_virtual_environment
    install_dependencies
    verify_installation
    
    # Automatic configuration steps
    echo ""
    echo -e "${GREEN}🎉 Installation completed successfully! 🎉${NC}"
    echo ""
    
    # Setup SSH tunnel and automatically update config
    setup_ssh_tunnel
    
    # Activate environment and show ready message
    activate_environment
    
    # Final configuration instructions
    print_configuration_steps
}

# Trap errors
trap 'print_error "Installation failed at line $LINENO"' ERR

# Run main function
main "$@"
