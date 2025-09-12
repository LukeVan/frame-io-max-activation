#!/bin/bash
# Frame.io Conference Mac Setup
# Run this once to prepare a Mac workstation for Frame.io automation

# Set working directory to FrameIO-Tools (required for fio CLI setup.py)
cd "$(dirname "$0")/FrameIO-Tools"

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${PURPLE}===============================================${NC}"
    echo -e "${PURPLE}🎪 Frame.io Conference Mac Setup${NC}"
    echo -e "${PURPLE}===============================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}💡 $1${NC}"
}

# Check Python 3
check_python() {
    print_step "Checking Python 3..."
    
    if command -v python3 &> /dev/null; then
        python_version=$(python3 --version 2>&1)
        print_success "Found: $python_version"
    else
        print_error "Python 3 not found"
        print_info "Please install Python 3 from python.org or via Homebrew"
        return 1
    fi
}

# Check pip
check_pip() {
    print_step "Checking pip..."
    
    if command -v pip3 &> /dev/null; then
        pip_version=$(pip3 --version 2>&1)
        print_success "Found: $pip_version"
    else
        print_error "pip3 not found"
        print_info "pip should come with Python 3. Try reinstalling Python."
        return 1
    fi
}

# Install Python dependencies
install_dependencies() {
    print_step "Installing Python dependencies..."
    
    echo ""
d to e scr    
    # Try --user install first (recommended for modern macOS)
    if pip3 install --user watchdog requests python-dotenv click; then
        print_success "Dependencies installed successfully (user install)"
    # Fallback to --break-system-packages if needed
    elif pip3 install --break-system-packages watchdog requests python-dotenv click; then
        print_success "Dependencies installed successfully (system packages)"
        print_warning "Used --break-system-packages flag"
    else
        print_error "Failed to install dependencies"
        print_info "Try installing manually: pip3 install --user watchdog requests python-dotenv click"
        return 1
    fi
}

# Install Frame.io CLI
install_frameio_cli() {
    print_step "Installing Frame.io CLI..."
    
    if command -v fio &> /dev/null; then
        print_success "Frame.io CLI already installed"
    else
        print_info "Installing Frame.io CLI from local source..."
        
        # Try --user install first (recommended for modern macOS)
        if pip3 install --user -e .; then
            print_success "Frame.io CLI installed successfully (user install)"
        # Fallback to --break-system-packages if needed
        elif pip3 install --break-system-packages -e .; then
            print_success "Frame.io CLI installed successfully (system packages)"
            print_warning "Used --break-system-packages flag"
        else
            print_error "Failed to install Frame.io CLI"
            print_info "Try running: pip3 install --user -e . manually"
            return 1
        fi
    fi
    
    # Test CLI - check both system PATH and user Python bin
    print_step "Testing Frame.io CLI..."
    
    # Try system PATH first
    if command -v fio &> /dev/null; then
        print_success "Frame.io CLI is working (system PATH)"
        CLI_COMMAND="fio"
    else
        # Detect Python version and try user directories
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        USER_BIN_PATH="$HOME/Library/Python/$PYTHON_VERSION/bin"
        
        if [ -f "$USER_BIN_PATH/fio" ]; then
            print_success "Frame.io CLI found in user Python directory (Python $PYTHON_VERSION)"
            CLI_COMMAND="$USER_BIN_PATH/fio"
            
            # Add to PATH for this session
            export PATH="$USER_BIN_PATH:$PATH"
            print_info "Added user Python bin to PATH for this session"
        # Fallback: try common Python versions
        elif [ -f "$HOME/Library/Python/3.12/bin/fio" ]; then
            print_success "Frame.io CLI found in user Python directory (Python 3.12)"
            CLI_COMMAND="$HOME/Library/Python/3.12/bin/fio"
            export PATH="$HOME/Library/Python/3.12/bin:$PATH"
            print_info "Added user Python bin to PATH for this session"
        elif [ -f "$HOME/Library/Python/3.11/bin/fio" ]; then
            print_success "Frame.io CLI found in user Python directory (Python 3.11)"
            CLI_COMMAND="$HOME/Library/Python/3.11/bin/fio"
            export PATH="$HOME/Library/Python/3.11/bin:$PATH"
            print_info "Added user Python bin to PATH for this session"
        elif [ -f "$HOME/Library/Python/3.9/bin/fio" ]; then
            print_success "Frame.io CLI found in user Python directory (Python 3.9)"
            CLI_COMMAND="$HOME/Library/Python/3.9/bin/fio"
            export PATH="$HOME/Library/Python/3.9/bin:$PATH"
            print_info "Added user Python bin to PATH for this session"
        else
            print_error "Frame.io CLI not found in PATH or user Python directories"
            print_info "Try running: python3 -m pip install --user -e ."
            return 1
        fi
    fi
    
    # Setup .env file with credentials
    setup_credentials
}

# Setup Frame.io credentials (.env file)
setup_credentials() {
    print_step "Setting up Frame.io credentials..."
    
    # Make sure CLI_COMMAND is available (should be set by install_frameio_cli)
    if [ -z "$CLI_COMMAND" ]; then
        # Fallback: try to find fio command
        if command -v fio &> /dev/null; then
            CLI_COMMAND="fio"
        else
            print_warning "Frame.io CLI not found - authentication testing will be skipped"
            CLI_COMMAND=""
        fi
    fi
    
    # Check if .env already exists and has credentials
    if [ -f ".env" ]; then
        if grep -q "CLIENT_ID=" ".env" && grep -q "CLIENT_SECRET=" ".env"; then
            print_success "Found existing .env file with credentials"
            
            # Test authentication (if CLI is available)
            if [ -n "$CLI_COMMAND" ]; then
                print_step "Testing authentication..."
                if $CLI_COMMAND accounts &> /dev/null; then
                    print_success "Frame.io CLI authenticated successfully"
                    return 0
                else
                    print_warning "Existing credentials appear invalid"
                    echo ""
                    read -p "Would you like to update your credentials? (y/n): " update_creds
                    if [[ $update_creds != [Yy]* ]]; then
                        print_info "Keeping existing credentials (you can update .env manually later)"
                        return 0
                    fi
                    echo ""
                fi
            else
                print_success "Found existing .env file with credentials"
                print_info "Authentication testing skipped (CLI not available)"
                return 0
            fi
        else
            print_warning "Found .env file but it's missing credentials"
        fi
    else
        print_info "No .env file found - let's create one"
    fi
    
    echo ""
    print_info "You'll need your Frame.io API credentials from:"
    print_info "https://console.adobe.io/ (Create or select your Adobe project)"
    echo ""
    
    # Prompt for Client ID
    while true; do
        read -p "Enter your Frame.io CLIENT_ID: " client_id
        if [ -n "$client_id" ]; then
            break
        else
            print_error "CLIENT_ID cannot be empty. Please try again."
        fi
    done
    
    # Prompt for Client Secret  
    while true; do
        read -p "Enter your Frame.io CLIENT_SECRET: " client_secret
        if [ -n "$client_secret" ]; then
            break
        else
            print_error "CLIENT_SECRET cannot be empty. Please try again."
        fi
    done
    
    # Create .env file
    print_step "Creating .env file..."
    cat > .env << EOF
# Frame.io API Configuration
# Generated by Setup_Conference_Mac.command

CLIENT_ID=$client_id
CLIENT_SECRET=$client_secret

# Get your credentials from:
# https://console.adobe.io/
EOF
    
    if [ $? -eq 0 ]; then
        print_success "Created .env file with your credentials"
        chmod 600 .env  # Secure file permissions
        
        # Test the new credentials (if CLI is available)
        if [ -n "$CLI_COMMAND" ]; then
            print_step "Testing new credentials..."
            if $CLI_COMMAND accounts &> /dev/null; then
                print_success "🎉 Frame.io authentication successful!"
            else
                print_warning "Authentication test failed - please verify your credentials"
                print_info "You can edit .env file manually if needed"
            fi
        else
            print_success "Credentials saved to .env file"
            print_info "Authentication testing skipped (CLI not available)"
        fi
    else
        print_error "Failed to create .env file"
        return 1
    fi
}

# Create desktop shortcuts and folders
create_shortcuts() {
    print_step "Creating Activation Setup folder and shortcuts..."
    
    desktop_path="$HOME/Desktop"
    activation_folder="$desktop_path/Activation Setup"
    
    # Create the Activation Setup folder
    mkdir -p "$activation_folder"
    print_success "Created: Activation Setup folder on Desktop"
    
    # Create shortcuts in the Activation Setup folder
    if [ -f "scripts/Launch_HotFolder_Watcher.command" ]; then
        ln -sf "$(pwd)/scripts/Launch_HotFolder_Watcher.command" "$activation_folder/🔥 Start Hot Folder.command"
        print_success "Created: 🔥 Start Hot Folder.command"
    fi
    
    if [ -f "scripts/Launch_Status_Monitor.command" ]; then
        ln -sf "$(pwd)/scripts/Launch_Status_Monitor.command" "$activation_folder/📊 Start Status Monitor.command"
        print_success "Created: 📊 Start Status Monitor.command"
    fi
    
}

# Create default folders
create_folders() {
    print_step "Creating default folders in Activation Setup..."
    
    desktop_path="$HOME/Desktop"
    activation_folder="$desktop_path/Activation Setup"
    
    mkdir -p "$activation_folder/FrameIO_Upload_HotFolder"
    mkdir -p "$activation_folder/FrameIO_Downloads"
    mkdir -p "$activation_folder/Express-Download"
    
    print_success "Created default folders in Activation Setup"
    print_info "  📂 FrameIO_Upload_HotFolder - Drop files here to upload"
    print_info "  📥 FrameIO_Downloads - Approved files download here"
    print_info "  🚀 Express-Download - Express download folder"
}

# Main setup function
main() {
    clear
    print_header
    
    echo -e "${CYAN}This script will prepare your Mac for Frame.io automation tools.${NC}"
    echo ""
    print_warning "macOS Security: If this is your first time running this script,"
    print_warning "you may need to approve it in System Preferences > Privacy & Security"
    echo ""
    
    # Run all checks and setup steps
    check_python || exit 1
    check_pip || exit 1
    install_dependencies || exit 1
    install_frameio_cli || exit 1
    create_folders
    create_shortcuts
    
    echo ""
    print_success "🎉 Conference Mac setup complete!"
    echo ""
    print_info "What's next:"
    echo "  1. 📁 Open 'Activation Setup' folder on Desktop"
    echo "  2. 🔥 Double-click '🔥 Start Hot Folder' to upload files"
    echo "  3. 📊 Double-click '📊 Start Status Monitor' to download approved files"
    echo ""
    print_info "Your folders are ready:"
    echo "  📂 FrameIO_Upload_HotFolder - Drop files here to upload"
    echo "  📥 FrameIO_Downloads - Approved files download here"
    echo "  🚀 Express-Download - Express download folder"
    echo ""
    print_warning "macOS Security Note:"
    echo "  • First-time scripts may require approval in System Preferences > Privacy & Security"
    echo "  • Click 'Allow' when prompted, then re-run the script"
    echo ""
    print_info "If Frame.io CLI is not found, try this manual fix:"
    echo "  export PATH=\"\$HOME/Library/Python/3.9/bin:\$PATH\""
    echo "  (or replace 3.9 with your Python version)"
    echo ""
    print_warning "If you need to re-run this setup, just download and run Setup_Conference_Mac.command again"
    echo ""
    
    read -p "Press Enter to exit..."
}

# Run main function
main
