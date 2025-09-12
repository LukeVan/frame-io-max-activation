#!/bin/bash
# Frame.io Hot Folder Watcher - Conference Launcher
# Double-click this file to start the hot folder watcher with guided setup

# Set working directory to FrameIO-Tools root (required for fio CLI)
cd "$(dirname "$0")/.."

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${PURPLE}===============================================${NC}"
    echo -e "${PURPLE}🔥 Frame.io Hot Folder Watcher Setup${NC}"
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

# Function to find and set up CLI command
setup_cli() {
    # Try system PATH first
    if command -v fio &> /dev/null; then
        CLI_COMMAND="fio"
        return 0
    fi
    
    # Try user Python bin directories
    for python_version in 3.9 3.10 3.11 3.12; do
        if [ -f "$HOME/Library/Python/$python_version/bin/fio" ]; then
            CLI_COMMAND="$HOME/Library/Python/$python_version/bin/fio"
            export PATH="$HOME/Library/Python/$python_version/bin:$PATH"
            return 0
        fi
    done
    
    return 1
}

# Function to check if CLI is working
check_cli() {
    print_step "Testing Frame.io CLI connection..."
    
    if ! setup_cli; then
        print_error "Frame.io CLI not found"
        print_info "Please run the Setup_Conference_Mac.command script first"
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    # Debug: Show current directory and .env file status
    echo "🔍 Debug info:"
    echo "  Current directory: $(pwd)"
    echo "  .env file exists: $([ -f .env ] && echo "YES" || echo "NO")"
    if [ -f .env ]; then
        echo "  .env file size: $(wc -c < .env) bytes"
        echo "  .env file preview:"
        head -2 .env | sed 's/=.*/=***/' || echo "    (cannot read .env)"
    fi
    
    echo "🔍 Testing CLI command: $CLI_COMMAND accounts"
    if $CLI_COMMAND accounts &> /dev/null; then
        print_success "Frame.io CLI is working!"
    else
        print_error "Frame.io CLI authentication failed"
        echo "🔍 CLI error output:"
        $CLI_COMMAND accounts 2>&1 | head -5
        print_info "Please check your .env file credentials"
        read -p "Press Enter to exit..."
        exit 1
    fi
}

# Function to get folder selection
get_folders() {
    print_step "Getting your Frame.io folders..."
    
    # First, ensure we have an account set
    print_step "Setting up Frame.io account..."
    if ! $CLI_COMMAND accounts &> /dev/null; then
        print_error "Failed to access Frame.io accounts"
        print_info "Please check your .env file credentials"
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    # Get the first (and likely only) account and set it as default
    account_info=$($CLI_COMMAND accounts --csv 2>/dev/null | tail -n +2 | head -n 1)
    if [ -n "$account_info" ]; then
        account_id=$(echo "$account_info" | cut -d',' -f2)
        if $CLI_COMMAND accounts "$account_id" &> /dev/null; then
            print_success "Set default account: $account_id"
        else
            print_warning "Failed to set default account"
        fi
    else
        print_warning "No account information found"
    fi
    
    echo ""
    echo -e "${CYAN}🏢 Available Workspaces:${NC}"
    $CLI_COMMAND workspaces
    
    # Get workspace data for selection
    workspace_data=$($CLI_COMMAND workspaces --csv)
    if [ $? -ne 0 ] || [ -z "$workspace_data" ]; then
        print_error "Failed to get workspace list"
        exit 1
    fi
    
    echo ""
    echo -e "${YELLOW}💡 Select a workspace:${NC}"
    
    # Parse workspaces and display clean numbered list (names only)
    workspace_names=()
    workspace_ids=()
    while IFS=',' read -r name id created updated; do
        # Remove quotes from name and id
        name=$(echo "$name" | sed 's/^"//;s/"$//')
        id=$(echo "$id" | sed 's/^"//;s/"$//')
        workspace_names+=("$name")
        workspace_ids+=("$id")
    done < <(echo "$workspace_data" | tail -n +2)
    
    # Display clean numbered list
    for i in "${!workspace_names[@]}"; do
        echo "$((i+1))) ${workspace_names[$i]}"
    done
    
    echo ""
    workspace_count=${#workspace_names[@]}
    read -p "Enter workspace number (1-$workspace_count): " workspace_choice
    
    if [ -z "$workspace_choice" ] || ! [[ "$workspace_choice" =~ ^[0-9]+$ ]]; then
        print_error "Please enter a valid number"
        exit 1
    fi
    
    if [ "$workspace_choice" -lt 1 ] || [ "$workspace_choice" -gt "$workspace_count" ]; then
        print_error "Invalid selection. Please choose 1-$workspace_count"
        exit 1
    fi
    
    # Get selected workspace info from arrays
    workspace_index=$((workspace_choice - 1))
    workspace_name="${workspace_names[$workspace_index]}"
    workspace_id="${workspace_ids[$workspace_index]}"
    
    echo ""
    print_step "Setting workspace: $workspace_name ($workspace_id)"
    $CLI_COMMAND workspaces "$workspace_name"
    
    echo ""
    echo -e "${CYAN}📂 Available Projects:${NC}"
    $CLI_COMMAND projects
    
    # Get project data for selection
    project_data=$($CLI_COMMAND projects --csv)
    if [ $? -ne 0 ] || [ -z "$project_data" ]; then
        print_error "Failed to get project list"
        exit 1
    fi
    
    echo ""
    echo -e "${YELLOW}💡 Select a project:${NC}"
    
    # Parse projects and display clean numbered list (names only)
    project_names=()
    project_ids=()
    while IFS=',' read -r name id created updated; do
        # Remove quotes from name and id
        name=$(echo "$name" | sed 's/^"//;s/"$//')
        id=$(echo "$id" | sed 's/^"//;s/"$//')
        project_names+=("$name")
        project_ids+=("$id")
    done < <(echo "$project_data" | tail -n +2)
    
    # Display clean numbered list
    for i in "${!project_names[@]}"; do
        echo "$((i+1))) ${project_names[$i]}"
    done
    
    echo ""
    project_count=${#project_names[@]}
    read -p "Enter project number (1-$project_count): " project_choice
    
    if [ -z "$project_choice" ] || ! [[ "$project_choice" =~ ^[0-9]+$ ]]; then
        print_error "Please enter a valid number"
        exit 1
    fi
    
    if [ "$project_choice" -lt 1 ] || [ "$project_choice" -gt "$project_count" ]; then
        print_error "Invalid selection. Please choose 1-$project_count"
        exit 1
    fi
    
    # Get selected project info from arrays
    project_index=$((project_choice - 1))
    project_name="${project_names[$project_index]}"
    project_id="${project_ids[$project_index]}"
    
    echo ""
    print_step "Setting project: $project_name ($project_id)"
    $CLI_COMMAND projects "$project_id"
    
    echo ""
    echo -e "${CYAN}📁 Available Folders:${NC}"
    $CLI_COMMAND ls
    
    echo ""
    read -p "Enter Target Folder ID (copy from parentheses above): " folder_id
    
    if [ -z "$folder_id" ]; then
        print_error "Folder ID is required"
        exit 1
    fi
    
    # Validate that folder_id looks like a UUID, not a name
    if [[ ! "$folder_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
        print_warning "That looks like a folder name, not a folder ID"
        print_info "Please copy the ID from the parentheses, like: 58c58656-98fd-4702-b1bc-2427790fcfa7"
        echo ""
        read -p "Enter the correct Folder ID: " folder_id
        
        if [[ ! "$folder_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
            print_error "Invalid folder ID format"
            exit 1
        fi
    fi
}

# Function to get watch folder
get_watch_folder() {
    print_step "Setting up local watch folder..."
    
    # Default to Desktop/Activation Setup/FrameIO_Upload_HotFolder
    default_folder="$HOME/Desktop/Activation Setup/FrameIO_Upload_HotFolder"
    
    echo ""
    echo -e "${CYAN}📂 Choose your local hot folder:${NC}"
    echo "1) Use default: $default_folder"
    echo "2) Choose existing folder"
    echo "3) Create new folder"
    echo ""
    read -p "Enter choice (1-3): " folder_choice
    
    case $folder_choice in
        1)
            watch_folder="$default_folder"
            mkdir -p "$watch_folder"
            ;;
        2)
            echo ""
            read -p "Enter full path to existing folder: " watch_folder
            if [ ! -d "$watch_folder" ]; then
                print_error "Folder does not exist: $watch_folder"
                exit 1
            fi
            ;;
        3)
            echo ""
            read -p "Enter full path for new folder: " watch_folder
            mkdir -p "$watch_folder"
            if [ ! -d "$watch_folder" ]; then
                print_error "Could not create folder: $watch_folder"
                exit 1
            fi
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
    
    print_success "Watch folder: $watch_folder"
}

# Function to save configuration
save_config() {
    config_file="hotfolder_config.txt"
    
    cat > "$config_file" << EOF
# Hot Folder Configuration
# Generated: $(date)
WORKSPACE_NAME="$workspace_name"
WORKSPACE_ID="$workspace_id"
PROJECT_NAME="$project_name"
PROJECT_ID="$project_id"
FOLDER_ID="$folder_id"
WATCH_FOLDER="$watch_folder"
EOF
    
    print_success "Configuration saved to $config_file"
}

# Function to start the watcher
start_watcher() {
    print_step "Starting Hot Folder Watcher..."
    
    echo ""
    print_info "Configuration Summary:"
    echo "  📂 Local Watch Folder: $watch_folder"
    echo "  🎯 Frame.io Target: $folder_id"
    echo ""
    
    print_warning "The watcher will now start. To stop it, press Ctrl+C in this window."
    echo ""
    
    read -p "Press Enter to start the watcher..."
    
    # Start the hot folder watcher (from project root)
    echo ""
    print_success "🚀 Starting Hot Folder Watcher!"
    echo ""
    
    python3 scripts/automation/simple_hotfolder.py "$watch_folder" "$folder_id"
}

# Function to load existing config
load_config() {
    config_file="hotfolder_config.txt"
    
    if [ -f "$config_file" ]; then
        print_step "Found existing configuration..."
        
        echo ""
        echo -e "${CYAN}📋 Previous Configuration:${NC}"
        cat "$config_file" | grep -E "(WORKSPACE_NAME|PROJECT_NAME|FOLDER_ID|WATCH_FOLDER)" | sed 's/^/  /'
        echo ""
        
        read -p "Use existing configuration? (Y/n): " use_existing
        
        # Default to yes if empty, or if explicitly y/Y
        if [[ -z "$use_existing" || $use_existing =~ ^[Yy]$ ]]; then
            # Safely source the config file
            echo "🔍 Loading configuration from $config_file..."
            if source_result=$(source "$config_file" 2>&1); then
                # Extract values directly from config file as backup
                workspace_name="${WORKSPACE_NAME:-$(grep '^WORKSPACE_NAME=' "$config_file" | cut -d'=' -f2- | sed 's/^"//;s/"$//')}"
                workspace_id="${WORKSPACE_ID:-$(grep '^WORKSPACE_ID=' "$config_file" | cut -d'=' -f2- | sed 's/^"//;s/"$//')}"
                project_name="${PROJECT_NAME:-$(grep '^PROJECT_NAME=' "$config_file" | cut -d'=' -f2- | sed 's/^"//;s/"$//')}"
                project_id="${PROJECT_ID:-$(grep '^PROJECT_ID=' "$config_file" | cut -d'=' -f2- | sed 's/^"//;s/"$//')}"
                folder_id="${FOLDER_ID:-$(grep '^FOLDER_ID=' "$config_file" | cut -d'=' -f2- | sed 's/^"//;s/"$//')}"
                watch_folder="${WATCH_FOLDER:-$(grep '^WATCH_FOLDER=' "$config_file" | cut -d'=' -f2- | sed 's/^"//;s/"$//')}"
                
                # Debug: Show loaded values
                echo "🔍 Debug - Loaded values:"
                echo "  workspace_name=[$workspace_name]"
                echo "  workspace_id=[$workspace_id]"
                echo "  project_name=[$project_name]"
                echo "  project_id=[$project_id]"
                echo "  folder_id=[$folder_id]"
                echo "  watch_folder=[$watch_folder]"
                
                # Handle missing IDs from old config files
                if [ -z "$workspace_id" ] || [ -z "$project_id" ]; then
                    print_warning "Config file is missing workspace/project IDs (old format)"
                    print_info "Please run fresh setup to get IDs, or manually add them to config"
                    return 1
                fi
                
                # Validate that we have required values
                if [ -z "$workspace_name" ] || [ -z "$project_name" ] || [ -z "$folder_id" ]; then
                    print_warning "Configuration file is incomplete or corrupted"
                    echo "🔍 Debug - Empty check results:"
                    echo "  workspace_name empty: $([ -z "$workspace_name" ] && echo "YES" || echo "NO")"
                    echo "  project_name empty: $([ -z "$project_name" ] && echo "YES" || echo "NO")"
                    echo "  folder_id empty: $([ -z "$folder_id" ] && echo "YES" || echo "NO")"
                    print_info "Starting fresh setup..."
                    return 1
                fi
                
                # Check if folder_id looks like a name instead of UUID
                if [[ ! "$folder_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
                    print_warning "Folder ID appears to be a name, not a UUID: $folder_id"
                    print_info "Please update your configuration with the correct folder ID"
                    echo ""
                    read -p "Would you like to fix this now? (y/N): " fix_now
                    if [[ $fix_now =~ ^[Yy]$ ]]; then
                        # Keep the workspace and project, but get new folder
                        setup_cli
                        get_folders
                        get_watch_folder
                        return 0
                    else
                        print_error "Cannot proceed with invalid folder ID"
                        exit 1
                    fi
                fi
                
                # Setup CLI and account
                if ! setup_cli; then
                    print_error "Frame.io CLI not found"
                    return 1
                fi
                
                # First, ensure we have an account set
                print_step "Setting up Frame.io account..."
                account_info=$($CLI_COMMAND accounts --csv 2>/dev/null | tail -n +2 | head -n 1)
                if [ -n "$account_info" ]; then
                    account_id=$(echo "$account_info" | cut -d',' -f2)
                    $CLI_COMMAND accounts "$account_id" &> /dev/null
                fi
                
                # Set workspace and project using IDs
                print_step "Setting workspace: $workspace_name ($workspace_id)"
                $CLI_COMMAND workspaces "$workspace_id"
                print_step "Setting project: $project_name ($project_id)"
                $CLI_COMMAND projects "$project_id"
                
                # Verify folders still exist
                if [ ! -d "$watch_folder" ]; then
                    print_warning "Watch folder no longer exists: $watch_folder"
                    get_watch_folder
                fi
                
                return 0
            else
                print_warning "Configuration file is corrupted"
                echo "🔍 Source error: $source_result"
                print_info "Starting fresh setup..."
                return 1
            fi
        fi
    fi
    
    return 1
}

# Main execution
main() {
    clear
    print_header
    
    # Check if we should load existing config
    if ! load_config; then
        # New setup
        check_cli
        get_folders
        get_watch_folder
        save_config
    else
        # Using existing config, just verify CLI
        check_cli
    fi
    
    start_watcher
}

# Run main function
main

# Keep terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    read -p "Press Enter to exit..."
fi
