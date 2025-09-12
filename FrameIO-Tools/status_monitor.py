#!/usr/bin/env python3
"""
Frame.io Status Field Monitor and Auto-Downloader

Simplified script that monitors the "Status" metadata field on files in a 
Frame.io folder and downloads files when their status changes to "approved".
"""

import os
import time
import json
import requests
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from dotenv import load_dotenv

# Import Frame.io CLI modules
from fio.config import get_default_account, get_default_folder
from fio.auth import get_access_token

# Load environment variables
load_dotenv()

@dataclass
class FileStatus:
    """Track file status and metadata"""
    file_id: str
    name: str
    status_value: Optional[str]
    file_size: int
    media_type: str
    download_url: Optional[str]
    last_updated: str
    is_approved: bool = False

class StatusMonitor:
    def __init__(self, folder_id: str, download_path: str, approved_values: List[str], 
                 check_interval: int = 300, download_enabled: bool = True):
        self.folder_id = folder_id
        self.download_path = Path(download_path)
        self.approved_values = [v.lower() for v in approved_values]  # Case insensitive
        self.check_interval = check_interval
        self.download_enabled = download_enabled
        
        self.account_id = get_default_account()
        self.downloaded_files: Set[str] = set()
        self.tracked_files: Dict[str, FileStatus] = {}
        
        # Setup
        self.setup_directories()
        self.load_downloaded_files()
        self.headers = self._get_headers()
    
    def setup_directories(self):
        """Create necessary directories"""
        self.download_path.mkdir(parents=True, exist_ok=True)
        (self.download_path / '.frameio').mkdir(exist_ok=True)
    
    def load_downloaded_files(self):
        """Load list of previously downloaded files"""
        downloaded_file = self.download_path / '.frameio' / 'downloaded.json'
        if downloaded_file.exists():
            try:
                with open(downloaded_file, 'r') as f:
                    self.downloaded_files = set(json.load(f))
                print(f"📂 Loaded {len(self.downloaded_files)} previously downloaded files")
            except Exception as e:
                print(f"⚠️  Error loading downloaded files: {e}")
    
    def save_downloaded_files(self):
        """Save list of downloaded files"""
        downloaded_file = self.download_path / '.frameio' / 'downloaded.json'
        try:
            with open(downloaded_file, 'w') as f:
                json.dump(list(self.downloaded_files), f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving downloaded files: {e}")
    
    def _get_headers(self):
        """Get authentication headers"""
        token = get_access_token()
        return {
            'Authorization': f'Bearer {token}'
        }
    
    def get_folder_files(self) -> List[FileStatus]:
        """Get all files from the folder with their metadata"""
        print(f"📁 Checking folder for files...")
        
        # First get basic file list
        url = f"https://api.frame.io/v4/accounts/{self.account_id}/folders/{self.folder_id}/children"
        params = {
            'include': 'media_links.original',
            'type': 'file'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            folder_data = response.json()['data']
            
            files = []
            for item in folder_data:
                if item['type'] == 'file':
                    # Get detailed metadata for each file
                    file_status = self._get_file_with_metadata(item)
                    files.append(file_status)
            
            print(f"📄 Found {len(files)} files in folder")
            return files
            
        except Exception as e:
            print(f"❌ Error getting folder files: {e}")
            return []
    
    def _get_file_with_metadata(self, file_data: dict) -> FileStatus:
        """Get a file with its detailed metadata from the dedicated endpoint"""
        file_id = file_data.get('id')
        
        # Get metadata from the dedicated endpoint
        metadata_url = f"https://api.frame.io/v4/accounts/{self.account_id}/files/{file_id}/metadata"
        
        try:
            metadata_response = requests.get(metadata_url, headers=self.headers)
            metadata_response.raise_for_status()
            metadata_data = metadata_response.json()['data']
            
            # Combine file data with metadata
            enhanced_file_data = file_data.copy()
            enhanced_file_data['metadata'] = metadata_data.get('metadata', [])
            
            return self._parse_file_status(enhanced_file_data)
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error fetching metadata for {file_data.get('name', 'unknown')}: {e}")
            # Fall back to file without metadata
            return self._parse_file_status(file_data)
    
    def _parse_file_status(self, file_data: dict) -> FileStatus:
        """Parse file data and extract status information"""
        file_id = file_data['id']
        name = file_data['name']
        file_size = file_data.get('file_size', 0)
        media_type = file_data.get('media_type', 'unknown')
        last_updated = file_data.get('updated_at', '')
        
        # Get download URL
        download_url = None
        if 'media_links' in file_data and file_data['media_links']:
            original = file_data['media_links'].get('original', {})
            download_url = original.get('download_url')
        
        # Look for Approval/Status metadata field
        status_value = None
        metadata = file_data.get('metadata', [])
        
        for field in metadata:
            field_name = field.get('field_definition_name', '').lower()
            field_type = field.get('field_type', '')
            value = field.get('value')
            
            # Look for "approval" or "status" field (case insensitive)
            if 'approval' in field_name or 'status' in field_name:
                print(f"🔍 Found approval field: '{field.get('field_definition_name')}' = {value}")
                
                if field_type in ['select', 'select_multi'] and value:
                    if isinstance(value, list) and value:
                        # Extract display name from select option
                        status_value = value[0].get('display_name', str(value[0]))
                    else:
                        status_value = str(value)
                elif field_type == 'text' and value:
                    status_value = str(value)
                break
        
        # Check if this status value indicates approval
        is_approved = False
        if status_value:
            for approved_value in self.approved_values:
                if approved_value in status_value.lower():
                    is_approved = True
                    break
        
        return FileStatus(
            file_id=file_id,
            name=name,
            status_value=status_value,
            file_size=file_size,
            media_type=media_type,
            download_url=download_url,
            last_updated=last_updated,
            is_approved=is_approved
        )
    
    def download_file(self, file_status: FileStatus) -> bool:
        """Download an approved file"""
        if not file_status.download_url:
            print(f"❌ No download URL available for {file_status.name}")
            return False
        
        try:
            local_path = self.download_path / file_status.name
            
            # Avoid overwriting existing files
            if local_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_parts = file_status.name.rsplit('.', 1)
                if len(name_parts) == 2:
                    new_name = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
                else:
                    new_name = f"{file_status.name}_{timestamp}"
                local_path = self.download_path / new_name
            
            print(f"⬇️  Downloading: {file_status.name} ({file_status.file_size:,} bytes)")
            print(f"   Status: {file_status.status_value}")
            print(f"   Saving to: {local_path}")
            
            # Download the file
            response = requests.get(file_status.download_url, stream=True)
            response.raise_for_status()
            
            total_size = 0
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total_size += len(chunk)
            
            print(f"✅ Successfully downloaded: {local_path} ({total_size:,} bytes)")
            
            # Mark as downloaded
            self.downloaded_files.add(file_status.file_id)
            self.save_downloaded_files()
            
            return True
            
        except Exception as e:
            print(f"❌ Error downloading {file_status.name}: {e}")
            return False
    
    def check_files(self):
        """Check for approved files and download them"""
        print(f"\n🔍 Checking for approved files at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        files = self.get_folder_files()
        newly_approved = []
        
        for file_status in files:
            # Skip if already downloaded
            if file_status.file_id in self.downloaded_files:
                continue
            
            print(f"📄 {file_status.name}:")
            print(f"   Status: {file_status.status_value or 'No status field found'}")
            print(f"   Approved: {file_status.is_approved}")
            
            # Check if approved
            if file_status.is_approved:
                newly_approved.append(file_status)
                print(f"   ✅ File is approved!")
        
        # Download newly approved files
        if newly_approved and self.download_enabled:
            print(f"\n⬇️  Downloading {len(newly_approved)} approved files...")
            success_count = 0
            for file_status in newly_approved:
                if self.download_file(file_status):
                    success_count += 1
            print(f"✅ Successfully downloaded {success_count}/{len(newly_approved)} files")
        elif newly_approved:
            print(f"\n📋 Found {len(newly_approved)} approved files (download disabled)")
        else:
            print("\n🔍 No new approved files found")
        
        # Update tracked files
        for file_status in files:
            self.tracked_files[file_status.file_id] = file_status
    
    def print_status_summary(self):
        """Print current status summary"""
        print(f"\n📊 Status Summary:")
        print(f"   Monitored folder: {self.folder_id}")
        print(f"   Download path: {self.download_path}")
        print(f"   Approved values: {', '.join(self.approved_values)}")
        print(f"   Files downloaded: {len(self.downloaded_files)}")
        print(f"   Files tracked: {len(self.tracked_files)}")
        
        # Show status breakdown
        status_counts = {}
        for file_status in self.tracked_files.values():
            status = file_status.status_value or "No status"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if status_counts:
            print("   Status breakdown:")
            for status, count in status_counts.items():
                approved_indicator = " ✅" if any(av in status.lower() for av in self.approved_values) else ""
                print(f"     {status}: {count}{approved_indicator}")
    
    def run_once(self):
        """Run a single check"""
        print("🔍 Running single status check...")
        self.check_files()
        self.print_status_summary()
    
    def run_continuous(self):
        """Run continuous monitoring"""
        print(f"🚀 Starting Frame.io Status Monitor")
        print(f"⏱️  Check interval: {self.check_interval} seconds")
        print(f"📁 Monitoring folder: {self.folder_id}")
        print(f"💾 Download path: {self.download_path}")
        print(f"✅ Approved values: {', '.join(self.approved_values)}")
        
        try:
            while True:
                self.check_files()
                self.print_status_summary()
                print(f"\n😴 Sleeping for {self.check_interval} seconds...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Error in monitoring loop: {e}")

def main():
    parser = argparse.ArgumentParser(description='Monitor Frame.io Status field for approved files')
    parser.add_argument('folder_id', help='Frame.io folder ID to monitor')
    parser.add_argument('download_path', help='Local path to download approved files')
    parser.add_argument('--approved-values', nargs='+',
                       default=['approved', 'final', 'ready', 'complete'],
                       help='Status values that indicate approval (case insensitive)')
    parser.add_argument('--interval', type=int, default=300,
                       help='Check interval in seconds (default: 300)')
    parser.add_argument('--no-download', action='store_true',
                       help='Only monitor, do not download files')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit (no continuous monitoring)')
    
    args = parser.parse_args()
    
    # Validate Frame.io credentials
    if not get_default_account():
        print("❌ No Frame.io account configured. Please run 'fio accounts' first.")
        return
    
    monitor = StatusMonitor(
        folder_id=args.folder_id,
        download_path=args.download_path,
        approved_values=args.approved_values,
        check_interval=args.interval,
        download_enabled=not args.no_download
    )
    
    if args.once:
        monitor.run_once()
    else:
        monitor.run_continuous()

if __name__ == "__main__":
    main()
