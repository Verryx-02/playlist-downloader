# Playlist-Downloader Windows Installation Script
# Automatically installs all dependencies and sets up the application

param(
    [switch]$SkipChecks,
    [switch]$IsElevated
)

# Ensure we stop on errors
$ErrorActionPreference = "Stop"

# Configuration
$REPO_URL = "https://github.com/verryx-02/playlist-downloader"
$INSTALL_DIR = "$env:USERPROFILE\Desktop\playlist-downloader"
$PYTHON_MIN_VERSION = [Version]"3.8.0"

# Helper function to get console width
function Get-ConsoleWidth {
    try {
        return $Host.UI.RawUI.WindowSize.Width
    }
    catch {
        return 80
    }
}

# Helper function to center text
function Center-Text {
    param([string]$Text)
    $width = Get-ConsoleWidth
    $padding = [Math]::Max(0, ($width - $Text.Length) / 2)
    return " " * $padding + $Text
}

# Helper function to center and print colored box
function Center-Box {
    param(
        [string]$Line,
        [ConsoleColor]$Color = [ConsoleColor]::White
    )
    $width = Get-ConsoleWidth
    $textWidth = 63  # Width of the ASCII box
    $padding = [Math]::Max(0, ($width - $textWidth) / 2)
    Write-Host (" " * $padding + $Line) -ForegroundColor $Color
}

# Helper function for centered interactive prompts
function Center-Prompt {
    param([string]$Prompt)
    $width = Get-ConsoleWidth
    $padding = [Math]::Max(0, ($width - $Prompt.Length) / 2)
    Write-Host ""
    Write-Host -NoNewline (" " * $padding + "🔸 " + $Prompt) -ForegroundColor Yellow
}

# Header functions
function Print-Header {
    Write-Host ""
    Center-Box "╔═══════════════════════════════════════════════════════════════╗" Magenta
    Center-Box "║                     Playlist-Downloader                       ║" Magenta
    Center-Box "║                                                               ║" Magenta
    Center-Box "║                Windows Automatic Installer                    ║" Magenta
    Center-Box "║                                                               ║" Magenta
    Center-Box "╚═══════════════════════════════════════════════════════════════╝" Magenta
    Write-Host ""
}

function Print-Step {
    param([string]$Message)
    Write-Host "[STEP] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Print-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Print-Warning {
    param([string]$Message)
    Write-Host "[WARNING] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Print-Error {
    param([string]$Message)
    Write-Host "[ERROR] " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Print-Info {
    param([string]$Message)
    Write-Host "[INFO] " -ForegroundColor Blue -NoNewline
    Write-Host $Message
}

# Check if command exists
function Test-Command {
    param([string]$Command)
    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

# Check if running on Windows
function Test-Windows {
    if ($PSVersionTable.Platform -and $PSVersionTable.Platform -ne "Win32NT") {
        Print-Error "This script is designed for Windows only"
        Print-Info "For other operating systems, please check:"
        Print-Info "$REPO_URL#installation"
        exit 1
    }
}

# Check PowerShell version
function Test-PowerShellVersion {
    $minVersion = [Version]"5.1.0"
    $currentVersion = $PSVersionTable.PSVersion
    
    if ($currentVersion -lt $minVersion) {
        Print-Error "PowerShell $minVersion or higher is required"
        Print-Info "Current version: $currentVersion"
        Print-Info "Please update PowerShell from: https://github.com/PowerShell/PowerShell"
        exit 1
    }
    
    Print-Info "PowerShell $currentVersion detected"
}

# Check and set execution policy
function Set-ExecutionPolicyIfNeeded {
    try {
        $currentPolicy = Get-ExecutionPolicy -Scope CurrentUser -ErrorAction SilentlyContinue
        
        if ($currentPolicy -eq "Restricted") {
            Print-Warning "PowerShell execution policy is Restricted"
            Print-Info "Setting execution policy to RemoteSigned for current user..."
            
            Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
            Print-Success "Execution policy updated successfully"
        }
        else {
            Print-Info "Execution policy: $currentPolicy"
        }
    }
    catch {
        Print-Warning "Could not check/set execution policy: $($_.Exception.Message)"
        Print-Info "You may need to run: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser"
    }
}

# Check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Refresh environment variables safely
function Update-EnvironmentPath {
    try {
        $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        
        # Clean and combine paths, removing duplicates
        $allPaths = @()
        if ($machinePath) { $allPaths += $machinePath.Split(';') }
        if ($userPath) { $allPaths += $userPath.Split(';') }
        
        # Remove empty entries and duplicates
        $cleanPaths = $allPaths | Where-Object { $_ -and $_.Trim() } | Select-Object -Unique
        
        $env:Path = $cleanPaths -join ';'
        Print-Info "Environment PATH updated"
    }
    catch {
        Print-Warning "Failed to update PATH: $($_.Exception.Message)"
    }
}

# Check Python version
function Test-PythonVersion {
    $pythonCommands = @("python", "python3", "py")
    
    foreach ($cmd in $pythonCommands) {
        if (Test-Command $cmd) {
            try {
                $versionOutput = & $cmd --version 2>&1
                if ($versionOutput -match "Python (\d+\.\d+\.\d+)") {
                    $pythonVersion = [Version]$matches[1]
                    if ($pythonVersion -ge $PYTHON_MIN_VERSION) {
                        $script:PythonCommand = $cmd
                        return $true
                    }
                }
            }
            catch {
                continue
            }
        }
    }
    return $false
}

# Install Chocolatey with proper elevation handling
function Install-Chocolatey {
    Print-Step "Installing Chocolatey (Windows package manager)..."
    
    # Check if already installed
    Update-EnvironmentPath
    if (Test-Command "choco") {
        Print-Info "Chocolatey already installed"
        return $true
    }
    
    Print-Info "Chocolatey not found. Installing..."
    
    # Check if we have admin rights
    if (-not (Test-Administrator)) {
        Print-Warning "Administrator privileges required for Chocolatey installation"
        Print-Info "Attempting to restart script with elevated privileges..."
        
        try {
            # Build arguments for the elevated process
            $scriptPath = $MyInvocation.MyCommand.Path
            $arguments = @(
                "-NoProfile"
                "-ExecutionPolicy Bypass" 
                "-File `"$scriptPath`""
                "-IsElevated"
            )
            
            # Start elevated process and wait
            $process = Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -Verb RunAs -PassThru -WindowStyle Normal
            
            if ($process) {
                Print-Info "Waiting for elevated installation to complete..."
                $process.WaitForExit()
                
                if ($process.ExitCode -eq 0) {
                    Print-Success "Elevated installation completed successfully"
                    Update-EnvironmentPath
                    
                    # Verify Chocolatey is now available
                    if (Test-Command "choco") {
                        return $true
                    }
                    else {
                        throw "Chocolatey not found after installation"
                    }
                }
                else {
                    throw "Elevated installation failed with exit code: $($process.ExitCode)"
                }
            }
            else {
                throw "Failed to start elevated process"
            }
        }
        catch {
            Print-Error "Failed to elevate privileges: $($_.Exception.Message)"
            Print-Info "Please install Chocolatey manually:"
            Print-Info "1. Run PowerShell as Administrator"
            Print-Info "2. Execute: Set-ExecutionPolicy Bypass -Scope Process -Force; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
            return $false
        }
    }
    else {
        # We are already admin, install directly
        try {
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
            
            Update-EnvironmentPath
            
            if (Test-Command "choco") {
                Print-Success "Chocolatey installed successfully"
                return $true
            }
            else {
                throw "Chocolatey installation verification failed"
            }
        }
        catch {
            Print-Error "Failed to install Chocolatey: $($_.Exception.Message)"
            return $false
        }
    }
}

# Install Python
function Install-Python {
    Print-Step "Installing Python $($PYTHON_MIN_VERSION.Major).$($PYTHON_MIN_VERSION.Minor)+..."
    
    if (Test-PythonVersion) {
        $version = & $script:PythonCommand --version 2>&1
        if ($version -match "Python (\d+\.\d+\.\d+)") {
            Print-Info "Python $($matches[1]) already installed and accessible"
            return $true
        }
    }
    
    Print-Info "Installing Python via Chocolatey..."
    
    try {
        $chocoResult = & choco install python -y 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "Chocolatey install failed with exit code $LASTEXITCODE. Output: $chocoResult"
        }
        
        # Wait for installation to complete and refresh PATH
        Start-Sleep -Seconds 10
        Update-EnvironmentPath
        
        # Test again with longer wait if needed
        $retries = 3
        for ($i = 1; $i -le $retries; $i++) {
            if (Test-PythonVersion) {
                $version = & $script:PythonCommand --version 2>&1
                if ($version -match "Python (\d+\.\d+\.\d+)") {
                    Print-Success "Python $($matches[1]) installed successfully"
                    return $true
                }
            }
            
            if ($i -lt $retries) {
                Print-Info "Waiting for Python installation to be available... (attempt $i/$retries)"
                Start-Sleep -Seconds 10
                Update-EnvironmentPath
            }
        }
        
        throw "Python installation verification failed after $retries attempts"
    }
    catch {
        Print-Error "Failed to install Python: $($_.Exception.Message)"
        Print-Info "Please install Python manually from: https://python.org"
        return $false
    }
}

# Install FFmpeg
function Install-FFmpeg {
    Print-Step "Installing FFmpeg (audio processing)..."
    
    if (Test-Command "ffmpeg") {
        Print-Info "FFmpeg already installed"
        return $true
    }
    
    Print-Info "Installing FFmpeg via Chocolatey..."
    
    try {
        $chocoResult = & choco install ffmpeg -y 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "Chocolatey install failed with exit code $LASTEXITCODE. Output: $chocoResult"
        }
        
        # Wait for installation and refresh PATH
        Start-Sleep -Seconds 10
        Update-EnvironmentPath
        
        # Test with retries
        $retries = 3
        for ($i = 1; $i -le $retries; $i++) {
            if (Test-Command "ffmpeg") {
                Print-Success "FFmpeg installed successfully"
                return $true
            }
            
            if ($i -lt $retries) {
                Print-Info "Waiting for FFmpeg installation to be available... (attempt $i/$retries)"
                Start-Sleep -Seconds 10
                Update-EnvironmentPath
            }
        }
        
        throw "FFmpeg installation verification failed after $retries attempts"
    }
    catch {
        Print-Error "Failed to install FFmpeg: $($_.Exception.Message)"
        Print-Info "Please install FFmpeg manually from: https://ffmpeg.org"
        return $false
    }
}

# Setup project directory and download files
function Setup-Project {
    Print-Step "Setting up Playlist-Downloader project..."
    
    # Check if directory already exists
    if (Test-Path $INSTALL_DIR) {
        Print-Warning "Existing installation found at $INSTALL_DIR"
        
        Start-Sleep -Seconds 2
        do {
            Center-Prompt "Do you want to remove it and reinstall? (y/N): "
            $response = Read-Host
            
            switch ($response.ToLower()) {
                "y" {
                    Print-Info "Removing existing installation..."
                    try {
                        Remove-Item -Recurse -Force $INSTALL_DIR
                        break
                    }
                    catch {
                        Print-Error "Failed to remove existing directory: $($_.Exception.Message)"
                        return $false
                    }
                }
                { $_ -in @("n", "") } {
                    Print-Info "Using existing installation directory"
                    try {
                        Set-Location $INSTALL_DIR
                        return $true
                    }
                    catch {
                        Print-Error "Cannot access existing directory: $($_.Exception.Message)"
                        return $false
                    }
                }
                default {
                    Write-Host "Please answer yes or no."
                }
            }
        } while ($true)
    }
    
    # Create directory
    try {
        New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
        Set-Location $INSTALL_DIR
        Print-Info "Created project directory: $INSTALL_DIR"
    }
    catch {
        Print-Error "Failed to create directory: $($_.Exception.Message)"
        return $false
    }
    
    # Download project
    Print-Info "Downloading project from GitHub..."
    $zipFile = "playlist-downloader.zip"
    $downloadUrl = "$REPO_URL/archive/refs/heads/main.zip"
    
    try {
        # Use TLS 1.2 for compatibility
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($downloadUrl, $zipFile)
        $webClient.Dispose()
        
        Print-Success "Project downloaded successfully"
    }
    catch {
        Print-Error "Failed to download project: $($_.Exception.Message)"
        Print-Info "You can download manually from: $REPO_URL"
        return $false
    }
    
    # Extract files
    Print-Info "Extracting project files..."
    
    try {
        # Use .NET method for better compatibility
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zipFile, ".")
        
        # Move files from subdirectory to current directory
        $extractedDir = "playlist-downloader-main"
        if (Test-Path $extractedDir) {
            Get-ChildItem -Path $extractedDir -Force | Move-Item -Destination . -Force
            Remove-Item -Recurse -Force $extractedDir
        }
        
        # Clean up ZIP file
        Remove-Item -Force $zipFile
        
        # Verify structure
        if ((Test-Path "requirements.txt") -and (Test-Path "setup.py")) {
            Print-Success "Project files extracted successfully"
            return $true
        }
        else {
            throw "Invalid project structure. Missing requirements.txt or setup.py"
        }
    }
    catch {
        Print-Error "Failed to extract project files: $($_.Exception.Message)"
        return $false
    }
}

# Setup Python virtual environment
function Setup-VirtualEnvironment {
    Print-Step "Setting up Python virtual environment..."
    
    try {
        Set-Location $INSTALL_DIR
    }
    catch {
        Print-Error "Cannot access install directory: $($_.Exception.Message)"
        return $false
    }
    
    # Check if virtual environment already exists
    if (Test-Path ".venv") {
        Write-Host ""
        Write-Host "⚠️  Existing virtual environment found" -ForegroundColor Yellow
        Write-Host "Directory: $INSTALL_DIR\.venv" -ForegroundColor Blue
        Write-Host ""
        Write-Host "Options:" -ForegroundColor Yellow
        Write-Host "1. Keep existing environment (recommended if already working)" -ForegroundColor Blue
        Write-Host "2. Remove and recreate environment" -ForegroundColor Blue
        Write-Host ""
        
        Start-Sleep -Seconds 2
        do {
            Center-Prompt "Do you want to keep the existing virtual environment? (y/N): "
            $response = Read-Host
            
            switch ($response.ToLower()) {
                "y" {
                    Print-Info "Keeping existing virtual environment"
                    # Test if the environment works
                    try {
                        $testResult = & ".venv\Scripts\python.exe" --version 2>&1
                        if ($testResult -match "Python") {
                            Print-Success "Existing virtual environment is functional"
                            return $true
                        }
                        else {
                            throw "Environment test failed: $testResult"
                        }
                    }
                    catch {
                        Print-Warning "Existing environment seems broken, recreating..."
                        Remove-Item -Recurse -Force .venv
                        break
                    }
                }
                { $_ -in @("n", "") } {
                    Print-Info "Removing and recreating virtual environment..."
                    try {
                        Remove-Item -Recurse -Force .venv
                        break
                    }
                    catch {
                        Print-Error "Failed to remove existing environment: $($_.Exception.Message)"
                        return $false
                    }
                }
                default {
                    Write-Host "Please answer yes or no."
                }
            }
        } while ($true)
    }
    
    # Create virtual environment
    Print-Info "Creating Python virtual environment..."
    
    try {
        $venvResult = & $script:PythonCommand -m venv .venv 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "venv creation failed with exit code $LASTEXITCODE. Output: $venvResult"
        }
        
        # Verify creation
        if (Test-Path ".venv\Scripts\python.exe") {
            Print-Success "Virtual environment created successfully"
            return $true
        }
        else {
            throw "Virtual environment directory not found after creation"
        }
    }
    catch {
        Print-Error "Failed to create virtual environment: $($_.Exception.Message)"
        Print-Info "Make sure Python is properly installed and accessible"
        return $false
    }
}

# Install Python dependencies
function Install-Dependencies {
    Print-Step "Installing Python dependencies..."
    
    try {
        Set-Location $INSTALL_DIR
    }
    catch {
        Print-Error "Cannot access install directory: $($_.Exception.Message)"
        return $false
    }
    
    # Verify virtual environment exists
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Print-Error "Virtual environment not found. Please run Setup-VirtualEnvironment first."
        return $false
    }
    
    try {
        Print-Info "Upgrading pip..."
        $pipUpgradeResult = & ".venv\Scripts\python.exe" -m pip install --upgrade pip 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Print-Warning "Pip upgrade had issues: $pipUpgradeResult"
        }
        
        Print-Info "Installing requirements..."
        $requirementsResult = & ".venv\Scripts\python.exe" -m pip install -r requirements.txt 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "Requirements installation failed with exit code $LASTEXITCODE. Output: $requirementsResult"
        }
        
        Print-Info "Installing package in development mode..."
        $packageResult = & ".venv\Scripts\python.exe" -m pip install -e . 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "Package installation failed with exit code $LASTEXITCODE. Output: $packageResult"
        }
        
        Print-Success "Dependencies installed successfully"
        return $true
    }
    catch {
        Print-Error "Failed to install dependencies: $($_.Exception.Message)"
        Print-Info "You may need to install dependencies manually:"
        Print-Info "1. Navigate to: $INSTALL_DIR"
        Print-Info "2. Run: .venv\Scripts\python.exe -m pip install -r requirements.txt"
        Print-Info "3. Run: .venv\Scripts\python.exe -m pip install -e ."
        return $false
    }
}

# Verify installation
function Test-Installation {
    Print-Step "Verifying installation..."
    
    try {
        Set-Location $INSTALL_DIR
    }
    catch {
        Print-Error "Cannot access install directory: $($_.Exception.Message)"
        return $false
    }
    
    try {
        # Test if the module can be imported
        $importTest = & ".venv\Scripts\python.exe" -c "import playlist_downloader; print('Import successful')" 2>&1
        
        if ($LASTEXITCODE -eq 0 -and $importTest -match "Import successful") {
            Print-Success "Playlist-Downloader installed correctly"
            return $true
        }
        else {
            throw "Import test failed: $importTest"
        }
    }
    catch {
        Print-Error "Installation verification failed: $($_.Exception.Message)"
        Print-Info "You may need to check the installation manually"
        return $false
    }
}

# Setup SSH tunnel with improved error handling
function Setup-SSHTunnel {
    Print-Step "Setting up SSH tunnel and capturing callback URL..."
    
    if (-not (Test-Command "ssh")) {
        Print-Error "SSH not found. Please install OpenSSH:"
        Print-Info "1. Open Settings > Apps > Optional Features"
        Print-Info "2. Add 'OpenSSH Client'"
        Print-Info "Or install via Chocolatey: choco install openssh"
        return $null
    }
    
    $maxAttempts = 3
    $timeouts = @(15, 25, 35)  # Increasing timeouts for each attempt
    
    for ($i = 1; $i -le $maxAttempts; $i++) {
        Print-Info "Attempting SSH tunnel setup (attempt $i/$maxAttempts)..."
        
        $tunnelResult = Start-SSHTunnel $i $timeouts[$i-1]
        
        if ($tunnelResult) {
            Print-Success "SSH tunnel established successfully on attempt $i"
            return $tunnelResult
        }
        
        if ($i -lt $maxAttempts) {
            Print-Warning "Attempt $i failed, retrying in 3 seconds..."
            Start-Sleep -Seconds 3
        }
    }
    
    Print-Error "All SSH tunnel attempts failed"
    return $null
}

# Start SSH tunnel with improved output capture
function Start-SSHTunnel {
    param(
        [int]$Attempt,
        [int]$Timeout
    )
    
    try {
        # Create unique temporary file
        $outputFile = [System.IO.Path]::GetTempFileName()
        
        # Start SSH process with output redirection
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = "ssh"
        $processInfo.Arguments = "-R 80:localhost:8080 nokey@localhost.run"
        $processInfo.RedirectStandardOutput = $true
        $processInfo.RedirectStandardError = $true
        $processInfo.UseShellExecute = $false
        $processInfo.CreateNoWindow = $true
        
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        
        # Event handlers for output
        $outputBuilder = New-Object System.Text.StringBuilder
        $errorBuilder = New-Object System.Text.StringBuilder
        
        $outputAction = {
            if (-not [string]::IsNullOrEmpty($EventArgs.Data)) {
                $outputBuilder.AppendLine($EventArgs.Data) | Out-Null
            }
        }
        
        $errorAction = {
            if (-not [string]::IsNullOrEmpty($EventArgs.Data)) {
                $errorBuilder.AppendLine($EventArgs.Data) | Out-Null
            }
        }
        
        Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action $outputAction | Out-Null
        Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action $errorAction | Out-Null
        
        # Start process and begin reading
        $process.Start() | Out-Null
        $process.BeginOutputReadLine()
        $process.BeginErrorReadLine()
        
        # Wait for tunnel URL with timeout
        $startTime = Get-Date
        $tunnelUrl = $null
        
        while ((Get-Date) -lt $startTime.AddSeconds($Timeout)) {
            $combinedOutput = $outputBuilder.ToString() + $errorBuilder.ToString()
            
            # Look for tunnel URL in output
            if ($combinedOutput -match "https://([a-z0-9]+\.lhr\.life)") {
                $tunnelUrl = $matches[0]
                break
            }
            
            # Check for connection errors
            if ($combinedOutput -match "Connection refused|Could not resolve hostname|Network is unreachable") {
                break
            }
            
            Start-Sleep -Milliseconds 500
        }
        
        if ($tunnelUrl) {
            # Return both URL and process
            return @{
                Url = $tunnelUrl
                Process = $process
            }
        }
        else {
            # Clean up failed process
            if (-not $process.HasExited) {
                $process.Kill()
                $process.WaitForExit(5000)
            }
            $process.Dispose()
            return $null
        }
    }
    catch {
        Print-Warning "SSH tunnel attempt failed: $($_.Exception.Message)"
        return $null
    }
    finally {
        # Clean up temporary file
        if ($outputFile -and (Test-Path $outputFile)) {
            Remove-Item $outputFile -Force -ErrorAction SilentlyContinue
        }
        
        # Remove event handlers
        Get-EventSubscriber | Where-Object { $_.SourceObject -eq $process } | Unregister-Event
    }
}

# Update config file
function Update-ConfigFile {
    param([string]$CallbackUrl)
    
    $configFile = "$INSTALL_DIR\config\config.yaml"
    
    Print-Step "Updating configuration file with callback URL..."
    
    try {
        # Ensure config directory exists
        $configDir = Split-Path $configFile
        if (-not (Test-Path $configDir)) {
            New-Item -ItemType Directory -Force -Path $configDir | Out-Null
        }
        
        # Read existing config or create new one
        $configContent = ""
        if (Test-Path $configFile) {
            $configContent = Get-Content $configFile -Raw -ErrorAction SilentlyContinue
        }
        
        # Update or add callback URL
        if ($configContent -match "callback_url:") {
            $configContent = $configContent -replace "callback_url:.*", "callback_url: `"$CallbackUrl`""
        }
        else {
            if ($configContent -and -not $configContent.EndsWith("`n")) {
                $configContent += "`n"
            }
            $configContent += "callback_url: `"$CallbackUrl`""
        }
        
        # Write updated config
        Set-Content -Path $configFile -Value $configContent -Encoding UTF8
        
        Print-Success "Configuration updated with callback URL: $CallbackUrl"
        return $true
    }
    catch {
        Print-Error "Failed to update config file: $($_.Exception.Message)"
        Print-Info "You'll need to manually add the callback URL to config\config.yaml"
        return $false
    }
}

# Spotify authentication
function Start-SpotifyAuth {
    Print-Step "Starting Spotify authentication..."
    
    try {
        Set-Location $INSTALL_DIR
    }
    catch {
        Print-Error "Cannot access install directory: $($_.Exception.Message)"
        return $false
    }
    
    try {
        Print-Info "Starting authentication process..."
        Print-Info "Please follow the browser prompts to authorize Spotify access."
        
        # Start auth process
        $authResult = & ".venv\Scripts\python.exe" -m playlist_downloader.auth login 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "Spotify authentication completed successfully!" -ForegroundColor Green
            Write-Host ""
            return $true
        }
        else {
            Write-Host ""
            Write-Host "Spotify authentication failed" -ForegroundColor Red
            Write-Host "Exit code: $LASTEXITCODE" -ForegroundColor Yellow
            Write-Host "Output: $authResult" -ForegroundColor Yellow
            Write-Host "You may need to run authentication manually later" -ForegroundColor Yellow
            Write-Host ""
            return $false
        }
    }
    catch {
        Print-Error "Authentication process failed: $($_.Exception.Message)"
        return $false
    }
}

# Show final success message
function Show-FinalSuccess {
    Write-Host ""
    Write-Host "Playlist-Downloader Setup Complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Everything is ready to use!" -ForegroundColor Green
    Write-Host ""
    Start-Sleep -Seconds 2
    Write-Host "To use Playlist-Downloader:" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host ""
    Start-Sleep -Seconds 2
    Write-Host "Then try your first playlist download:" -ForegroundColor Blue
    Write-Host "  python -m playlist_downloader download `"https://open.spotify.com/playlist/YOUR_PLAYLIST_URL`"" -ForegroundColor Cyan
    Write-Host ""
    Start-Sleep -Seconds 2
    Write-Host "For more commands and options:" -ForegroundColor Magenta
    Write-Host "  python -m playlist_downloader --help" -ForegroundColor Cyan
    Write-Host ""
}

# Handle elevated execution
function Handle-ElevatedExecution {
    if ($IsElevated) {
        Print-Info "Running in elevated mode for Chocolatey installation..."
        
        # Just install Chocolatey and exit
        try {
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
            
            Print-Success "Chocolatey installed successfully in elevated mode"
            exit 0
        }
        catch {
            Print-Error "Failed to install Chocolatey in elevated mode: $($_.Exception.Message)"
            exit 1
        }
    }
}

# Main installation function
function main {
    # Handle elevated execution first
    Handle-ElevatedExecution
    
    Print-Header
    
    # System checks
    if (-not $SkipChecks) {
        Test-Windows
        Test-PowerShellVersion
        Set-ExecutionPolicyIfNeeded
    }
    
    # Installation steps
    $steps = @(
        @{ Name = "Install-Chocolatey"; Function = { Install-Chocolatey } },
        @{ Name = "Install-Python"; Function = { Install-Python } },
        @{ Name = "Install-FFmpeg"; Function = { Install-FFmpeg } },
        @{ Name = "Setup-Project"; Function = { Setup-Project } },
        @{ Name = "Setup-VirtualEnvironment"; Function = { Setup-VirtualEnvironment } },
        @{ Name = "Install-Dependencies"; Function = { Install-Dependencies } },
        @{ Name = "Test-Installation"; Function = { Test-Installation } }
    )
    
    foreach ($step in $steps) {
        $result = & $step.Function
        if (-not $result) {
            Print-Error "Installation failed at step: $($step.Name)"
            Print-Info "Please check the error messages above and try running the script again."
            exit 1
        }
    }
    
    # Configuration steps
    Write-Host ""
    Write-Host "Installation completed successfully!" -ForegroundColor Green
    Write-Host ""
    
    # Setup SSH tunnel and configuration
    $tunnelInfo = Setup-SSHTunnel
    
    if ($tunnelInfo) {
        $callbackUrl = $tunnelInfo.Url + "/callback"
        $configResult = Update-ConfigFile $callbackUrl
        
        if ($configResult) {
            Write-Host ""
            Write-Host "SSH tunnel setup completed!" -ForegroundColor Green
            Write-Host ""
            
            # Start Spotify authentication
            $authSuccess = Start-SpotifyAuth
            
            # Clean up SSH process
            try {
                if ($tunnelInfo.Process -and -not $tunnelInfo.Process.HasExited) {
                    $tunnelInfo.Process.Kill()
                    $tunnelInfo.Process.WaitForExit(5000)
                }
                $tunnelInfo.Process.Dispose()
            }
            catch {
                # Process cleanup failed, but continue
                Print-Warning "Could not clean up SSH tunnel process"
            }
            
            if ($authSuccess) {
                Show-FinalSuccess
            }
            else {
                Write-Host "Installation complete, but you'll need to complete Spotify authentication manually." -ForegroundColor Yellow
                Write-Host "Run: .venv\Scripts\python.exe -m playlist_downloader.auth login" -ForegroundColor Cyan
            }
        }
        else {
            Print-Warning "Configuration update failed. You'll need to set up authentication manually."
        }
    }
    else {
        Write-Host "SSH tunnel setup failed. You'll need to configure authentication manually." -ForegroundColor Yellow
        Write-Host "See the manual installation guide for SSH tunnel setup." -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "Installation process completed!" -ForegroundColor Green
    Write-Host "Project location: $INSTALL_DIR" -ForegroundColor Blue
    Write-Host ""
}

# Run main function with error handling
try {
    main
}
catch {
    Print-Error "Installation failed: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "For manual installation, please visit:" -ForegroundColor Yellow
    Write-Host "$REPO_URL#installation" -ForegroundColor Cyan
    
    # Show stack trace in debug mode
    if ($DebugPreference -eq "Continue") {
        Write-Host ""
        Write-Host "Stack trace:" -ForegroundColor Red
        Write-Host $_.ScriptStackTrace -ForegroundColor Red
    }
    
    exit 1
}