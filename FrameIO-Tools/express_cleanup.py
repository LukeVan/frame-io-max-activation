#!/usr/bin/env python3
"""
Boards Express Downloads Cleanup Script
Monitors Boards_Express_Downloads folder for PNG/MP4 trigger files (except untitled.mp4)
When detected, cleans up local folders and Frame.io files for kiosk reset
Note: Trigger files are preserved in Boards_Express_Downloads folder for manual handling
"""

import os
import sys
import time
import shutil
import subprocess
import argparse
import re
from pathlib import Path
from typing import Set, Dict, Any
import threading

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("❌ Missing required dependency: watchdog")
    print("📦 Please install it with: pip install watchdog")
    sys.exit(1)

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_status(message: str, color: str = Colors.CYAN) -> None:
    """Print a status message with color and timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] {message}{Colors.END}")

def print_success(message: str) -> None:
    print_status(f"✅ {message}", Colors.GREEN)

def print_error(message: str) -> None:
    print_status(f"❌ {message}", Colors.RED)

def print_warning(message: str) -> None:
    print_status(f"⚠️ {message}", Colors.YELLOW)

def print_info(message: str) -> None:
    print_status(f"ℹ️ {message}", Colors.BLUE)

def load_config_file(config_path: Path) -> Dict[str, str]:
    """Load configuration from a text file"""
    config = {}
    if not config_path.exists():
        print_warning(f"Config file not found: {config_path}")
        return config
    
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    config[key.strip()] = value
        print_info(f"Loaded config from {config_path}")
    except Exception as e:
        print_error(f"Failed to load config {config_path}: {e}")
    
    return config

def clean_local_folder(folder_path: str, folder_name: str) -> bool:
    """Clean all files from a local folder"""
    try:
        folder = Path(folder_path)
        if not folder.exists():
            print_warning(f"{folder_name} folder doesn't exist: {folder_path}")
            return True
        
        # Count files before cleanup
        files = list(folder.glob('*'))
        file_count = len([f for f in files if f.is_file()])
        
        if file_count == 0:
            print_info(f"{folder_name} folder is already empty")
            return True
        
        # Delete all files
        for item in files:
            if item.is_file():
                item.unlink()
                print_info(f"Deleted: {item.name}")
            elif item.is_dir():
                shutil.rmtree(item)
                print_info(f"Deleted folder: {item.name}")
        
        print_success(f"Cleaned {file_count} items from {folder_name}")
        return True
        
    except Exception as e:
        print_error(f"Failed to clean {folder_name}: {e}")
        return False

def get_cli_command():
    """Get the correct Frame.io CLI command path"""
    # Try different possible locations
    cli_commands = [
        'fio',  # Global install
        f'{os.path.expanduser("~/Library/Python/3.12/bin/fio")}',
        f'{os.path.expanduser("~/Library/Python/3.11/bin/fio")}',
        f'{os.path.expanduser("~/Library/Python/3.10/bin/fio")}',
        f'{os.path.expanduser("~/Library/Python/3.9/bin/fio")}',
    ]
    
    for cmd in cli_commands:
        try:
            result = subprocess.run([cmd, 'accounts'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    return 'fio'  # Fallback to default

def clean_frameio_folder(folder_id: str) -> bool:
    """Clean all files from a Frame.io folder using CLI"""
    try:
        print_info(f"Getting file list from Frame.io folder: {folder_id}")
        
        cli_cmd = get_cli_command()
        
        # Load configurations to get workspace and project info
        hotfolder_config = load_config_file(Path("hotfolder_config.txt"))
        if not hotfolder_config:
            print_error("No hotfolder configuration found - cannot determine workspace/project")
            return False
        
        workspace_name = hotfolder_config.get('WORKSPACE_NAME')
        project_name = hotfolder_config.get('PROJECT_NAME')
        
        if not workspace_name or not project_name:
            print_error("Missing workspace or project name in configuration")
            return False
        
        # Set Frame.io CLI context
        print_info(f"Setting workspace: {workspace_name}")
        try:
            subprocess.run([cli_cmd, 'workspaces', workspace_name], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to set workspace: {e}")
            return False
        
        print_info(f"Setting project: {project_name}")
        try:
            subprocess.run([cli_cmd, 'projects', project_name], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to set project: {e}")
            return False
        
        # Navigate to the specific folder
        print_info(f"Navigating to folder: {folder_id}")
        try:
            subprocess.run([cli_cmd, 'cd', folder_id], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to navigate to folder: {e}")
            return False
        
        # Get list of files in the current folder
        print_info("Getting file list from current folder...")
        result = subprocess.run(
            [cli_cmd, 'ls'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if not result.stdout.strip():
            print_info("Frame.io folder is already empty")
            return True
        
        # Parse regular ls output to get file IDs
        lines = result.stdout.strip().split('\n')
        if len(lines) == 0:
            print_info("Frame.io folder is already empty")
            return True
        
        file_count = 0
        # Process lines to find files (not folders)
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
                
            # Check if this line contains a file (not a folder emoji 📁)
            if line and not line.startswith('📁'):
                # Look for UUID in this line or the next line
                file_uuid = None
                file_name = line
                
                # Try to extract UUID from current line
                uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
                uuid_match = re.search(uuid_pattern, line)
                
                if uuid_match:
                    file_uuid = uuid_match.group()
                    # Remove UUID from filename for cleaner display
                    file_name = re.sub(r'\s*\([^)]*' + file_uuid + r'[^)]*\)', '', line).strip()
                elif i + 1 < len(lines):
                    # Check next line for UUID
                    next_line = lines[i + 1].strip()
                    uuid_match = re.search(uuid_pattern, next_line)
                    if uuid_match:
                        file_uuid = uuid_match.group()
                        i += 1  # Skip the next line since we processed it
                
                # If we found a file UUID, delete it
                if file_uuid:
                    try:
                        subprocess.run(
                            [cli_cmd, 'delete', '--force', file_uuid],
                            check=True,
                            capture_output=True
                        )
                        print_info(f"Deleted from Frame.io: {file_name}")
                        file_count += 1
                    except subprocess.CalledProcessError as e:
                        print_error(f"Failed to delete {file_name} from Frame.io: {e}")
            
            i += 1
        
        if file_count > 0:
            print_success(f"Cleaned {file_count} files from Frame.io folder")
        else:
            print_info("No files found to delete in Frame.io folder")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to access Frame.io folder: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print_error(f"CLI error output: {e.stderr}")
        if hasattr(e, 'stdout') and e.stdout:
            print_error(f"CLI stdout: {e.stdout}")
        return False
    except Exception as e:
        print_error(f"Failed to clean Frame.io folder: {e}")
        return False

def perform_cleanup(express_folder: Path) -> bool:
    """Perform full cleanup of all configured folders"""
    print_status("🚀 EXPRESS CLEANUP TRIGGERED", Colors.BOLD + Colors.CYAN)
    
    success = True
    
    # Load hotfolder config
    hotfolder_config = load_config_file(Path("hotfolder_config.txt"))
    status_config = load_config_file(Path("status_monitor_config.txt"))
    
    # Clean local folders
    if 'WATCH_FOLDER' in hotfolder_config:
        success &= clean_local_folder(hotfolder_config['WATCH_FOLDER'], "Upload HotFolder")
    
    if 'DOWNLOAD_FOLDER' in status_config:
        success &= clean_local_folder(status_config['DOWNLOAD_FOLDER'], "Downloads")
    
    # Clean Frame.io folder
    folder_id = None
    if 'FOLDER_ID' in hotfolder_config:
        folder_id = hotfolder_config['FOLDER_ID']
    elif 'FOLDER_ID' in status_config:
        folder_id = status_config['FOLDER_ID']
    
    if folder_id:
        success &= clean_frameio_folder(folder_id)
    else:
        print_warning("No Frame.io folder ID found in config files")
    
    # Note: Boards_Express_Downloads folder is NOT cleaned - trigger files are preserved for manual handling
    
    if success:
        print_success("🎉 KIOSK RESET COMPLETE - Ready for next user!")
    else:
        print_error("⚠️ Cleanup completed with some errors")
    
    return success

class ExpressCleanupHandler(FileSystemEventHandler):
    """Handles file system events in Boards_Express_Downloads folder"""
    
    def __init__(self, express_folder: Path):
        self.express_folder = express_folder
        self.processing = False
        super().__init__()
    
    def on_created(self, event):
        if not event.is_directory:
            self._check_trigger_file(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self._check_trigger_file(event.dest_path)
    
    def _check_trigger_file(self, file_path: str):
        """Check if the file is a trigger file (PNG/MP4, but not untitled.mp4)"""
        if self.processing:
            return
        
        file_path = Path(file_path)
        
        # Check if it's a PNG or MP4 file
        if file_path.suffix.lower() in ['.png', '.mp4']:
            # Skip untitled.mp4 files (common default name that shouldn't trigger cleanup)
            if file_path.name.lower() == 'untitled.mp4':
                print_status(f"⏭️ Skipping trigger file: {file_path.name} (untitled.mp4 files are ignored)")
                return
                
            print_status(f"🎯 Trigger file detected: {file_path.name}")
            
            # Wait a moment for file to be fully written
            time.sleep(1)
            
            # Prevent multiple simultaneous cleanups
            self.processing = True
            try:
                perform_cleanup(self.express_folder)
            finally:
                self.processing = False

def main():
    parser = argparse.ArgumentParser(
        description="Boards Express Downloads Cleanup Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 express_cleanup.py /path/to/Boards_Express_Downloads
  python3 express_cleanup.py "$HOME/Desktop/Activation Setup/Boards_Express_Downloads"

This script monitors the Boards_Express_Downloads folder and triggers a full cleanup
when PNG or MP4 files are added (except untitled.mp4). The cleanup includes:
- Local FrameIO_Upload_HotFolder
- Local FrameIO_Downloads  
- Files from the configured Frame.io project folder

Note: PNG/MP4 trigger files are preserved in Boards_Express_Downloads for manual handling
        """
    )
    
    parser.add_argument(
        'express_folder',
        help='Path to the Boards_Express_Downloads folder to monitor'
    )
    
    parser.add_argument(
        '--config-dir',
        default='.',
        help='Directory containing config files (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Setup paths
    express_folder = Path(args.express_folder).expanduser().resolve()
    config_dir = Path(args.config_dir).expanduser().resolve()
    
    # Change to config directory so config files can be found
    os.chdir(config_dir)
    
    print_status("🚀 BOARDS EXPRESS DOWNLOADS CLEANUP MONITOR", Colors.BOLD + Colors.HEADER)
    print_info(f"Monitor folder: {express_folder}")
    print_info(f"Config directory: {config_dir}")
    
    # Validate express folder
    if not express_folder.exists():
        print_error(f"Boards_Express_Downloads folder doesn't exist: {express_folder}")
        sys.exit(1)
    
    # Check if config files exist
    hotfolder_config_path = config_dir / "hotfolder_config.txt"
    status_config_path = config_dir / "status_monitor_config.txt"
    
    if not hotfolder_config_path.exists() and not status_config_path.exists():
        print_warning("No config files found - cleanup will be limited to Boards_Express_Downloads folder")
    
    print_success("Monitor started - drop PNG or MP4 files to trigger cleanup")
    print_info("Press Ctrl+C to stop")
    
    # Setup file watcher
    event_handler = ExpressCleanupHandler(express_folder)
    observer = Observer()
    observer.schedule(event_handler, str(express_folder), recursive=False)
    
    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print_status("🛑 Stopping Boards Express Downloads monitor...", Colors.YELLOW)
        observer.stop()
    
    observer.join()
    print_success("Boards Express Downloads monitor stopped")

if __name__ == "__main__":
    main()
