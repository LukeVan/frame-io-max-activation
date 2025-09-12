#!/bin/bash

# Launch_Express_Cleanup.command
# Launcher script for Express-Download Cleanup Monitor

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                  🚀 EXPRESS-DOWNLOAD CLEANUP                     ║${NC}"
    echo -e "${CYAN}║                     Kiosk Reset Monitor                          ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

print_header

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed or not in PATH"
fi

# Check if Frame.io CLI is available
if ! python3 -c "import fio.cli" 2>/dev/null; then
    print_error "Frame.io CLI is not installed. Please run setup first."
fi

print_step "Checking configuration..."

# Check for config files
config_found=false
if [[ -f "hotfolder_config.txt" ]]; then
    print_success "Found hotfolder configuration"
    config_found=true
fi

if [[ -f "status_monitor_config.txt" ]]; then
    print_success "Found status monitor configuration"  
    config_found=true
fi

if [[ "$config_found" == "false" ]]; then
    print_warning "No configuration files found"
    print_info "The cleanup will only clear the Boards_Express_Downloads folder"
    echo ""
fi

# Set default Boards_Express_Downloads folder path
default_express_folder="$HOME/Desktop/Activation Setup/Boards_Express_Downloads"

echo ""
print_step "Boards_Express_Downloads folder setup:"
print_info "Default: $default_express_folder"
echo ""
read -p "Press Enter to use default, or type custom path: " custom_path

if [[ -n "$custom_path" ]]; then
    express_folder="$custom_path"
else
    express_folder="$default_express_folder"
fi

# Expand tilde and resolve path
express_folder="${express_folder/#~/$HOME}"

print_step "Validating Boards_Express_Downloads folder: $express_folder"

# Create folder if it doesn't exist
if [[ ! -d "$express_folder" ]]; then
    print_warning "Boards_Express_Downloads folder doesn't exist"
    read -p "Create it? (y/n): " create_folder
    if [[ "$create_folder" =~ ^[Yy]$ ]]; then
        mkdir -p "$express_folder"
        if [[ $? -eq 0 ]]; then
            print_success "Created Boards_Express_Downloads folder"
        else
            print_error "Failed to create Boards_Express_Downloads folder"
        fi
    else
        print_error "Boards_Express_Downloads folder is required"
    fi
else
    print_success "Boards_Express_Downloads folder found"
fi

echo ""
print_step "Starting Boards Express Downloads Cleanup Monitor..."
print_info "📁 Monitoring: $express_folder"
print_info "🎯 Trigger: Drop PNG or MP4 files to reset kiosk"
echo ""
print_success "Monitor is running - drop PNG/MP4 files to trigger cleanup"
print_warning "Press Ctrl+C to stop the monitor"
echo ""

# Run the cleanup monitor
python3 express_cleanup.py "$express_folder"

echo ""
print_success "Boards Express Downloads cleanup monitor stopped"
echo ""
read -p "Press Enter to close this window..."
