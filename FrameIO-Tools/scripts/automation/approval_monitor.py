#!/usr/bin/env python3
"""
Frame.io Approval Monitor and Auto-Downloader

This script monitors specified Frame.io folders for approved files and automatically
downloads them to a local directory when their approval status changes to "approved".

The script uses Frame.io's metadata system to track approval status through custom fields.
"""

import os
import time
import json
import requests
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Import Frame.io CLI modules
from fio.config import get_default_account, get_default_folder
from fio.auth import get_access_token

# Load environment variables
load_dotenv()

@dataclass
class ApprovalConfig:
    """Configuration for approval monitoring"""
    folder_id: str
    local_download_path: str
    approval_field_names: List[str]  # e.g., ["Approval Status", "Review State"]
    approved_values: List[str]       # e.g., ["Approved", "Final", "Ready"]
    check_interval: int = 30        # 30 Seconds
    download_approved: bool = True
    track_downloaded: bool = True

@dataclass
class FileInfo:
    """Information about a Frame.io file"""
    file_id: str
    name: str
    status: str
    approval_status: Optional[str]
    approved_by: Optional[str]
    approved_date: Optional[str]
    download_url: Optional[str]
    file_size: int
    media_type: str
    last_updated: str

class FrameIOApprovalMonitor:
    def __init__(self, config: ApprovalConfig):
        self.config = config
        self.account_id = get_default_account()
        self.downloaded_files: Set[str] = set()
        self.tracked_files: Dict[str, FileInfo] = {}
        self.approval_fields: Dict[str, str] = {}  # field_name -> field_id mapping
        
        # Setup directories
        self.setup_directories()
        self.load_downloaded_files()
        
        # Initialize Frame.io connection
        self.headers = self._get_headers()
        
        # Discover approval fields
        self.discover_approval_fields()
    
    def setup_directories(self):
        """Create necessary directories"""
        Path(self.config.local_download_path).mkdir(parents=True, exist_ok=True)
        Path(self.config.local_download_path).joinpath('.frameio').mkdir(exist_ok=True)
    
    def load_downloaded_files(self):
        """Load list of previously downloaded files"""
        downloaded_file = Path(self.config.local_download_path) / '.frameio' / 'downloaded.json'
        if downloaded_file.exists():
            try:
                with open(downloaded_file, 'r') as f:
                    self.downloaded_files = set(json.load(f))
                print(f"📂 Loaded {len(self.downloaded_files)} previously downloaded files")
            except Exception as e:
                print(f"⚠️  Error loading downloaded files: {e}")
    
    def save_downloaded_files(self):
        """Save list of downloaded files"""
        downloaded_file = Path(self.config.local_download_path) / '.frameio' / 'downloaded.json'
        try:
            with open(downloaded_file, 'w') as f:
                json.dump(list(self.downloaded_files), f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving downloaded files: {e}")
    
    def _get_headers(self):
        """Get authentication headers"""
        token = get_access_token()
        return {
            'Authorization': f'Bearer {token}',
        }
    
    def discover_approval_fields(self):
        """Discover available metadata fields and find approval-related ones"""
        print("🔍 Discovering approval metadata fields...")
        
        url = f"https://api.frame.io/v4/accounts/{self.account_id}/metadata/field_definitions"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            field_definitions = response.json()['data']
            
            # Look for fields that might be approval-related
            for field in field_definitions:
                field_name = field['name']
                field_id = field['id']
                field_type = field['field_type']
                
                # Check if this field name matches our configured approval fields
                for approval_field_name in self.config.approval_field_names:
                    if approval_field_name.lower() in field_name.lower():
                        self.approval_fields[field_name] = field_id
                        print(f"✅ Found approval field: '{field_name}' (ID: {field_id}, Type: {field_type})")
                        
                        # If it's a select field, show the options
                        if field_type in ['select', 'select_multi'] and 'field_configuration' in field:
                            options = field['field_configuration'].get('options', [])
                            option_names = [opt['display_name'] for opt in options]
                            print(f"   Options: {', '.join(option_names)}")
            
            if not self.approval_fields:
                print("⚠️  No approval fields found! You may need to:")
                print("   1. Create custom metadata fields for approval tracking")
                print("   2. Update the approval_field_names in your config")
                print("   3. Check that the field names match exactly")
                
        except Exception as e:
            print(f"❌ Error discovering approval fields: {e}")
    
    def get_folder_files(self) -> List[FileInfo]:
        """Get all files from the monitored folder with metadata"""
        print(f"📁 Checking folder for files...")
        
        url = f"https://api.frame.io/v4/accounts/{self.account_id}/folders/{self.config.folder_id}/children"
        params = {
            'include': 'metadata,media_links.original',
            'type': 'file'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            folder_data = response.json()['data']
            
            files = []
            for item in folder_data:
                if item['type'] == 'file':
                    file_info = self._parse_file_info(item)
                    files.append(file_info)
            
            print(f"📄 Found {len(files)} files in folder")
            return files
            
        except Exception as e:
            print(f"❌ Error getting folder files: {e}")
            return []
    
    def _parse_file_info(self, file_data: dict) -> FileInfo:
        """Parse Frame.io file data into FileInfo object"""
        file_id = file_data['id']
        name = file_data['name']
        status = file_data.get('status', 'unknown')
        file_size = file_data.get('file_size', 0)
        media_type = file_data.get('media_type', 'unknown')
        last_updated = file_data.get('updated_at', '')
        
        # Get download URL
        download_url = None
        if 'media_links' in file_data and file_data['media_links']:
            original = file_data['media_links'].get('original', {})
            download_url = original.get('download_url')
        
        # Parse approval metadata
        approval_status = None
        approved_by = None
        approved_date = None
        
        metadata = file_data.get('metadata', [])
        for field in metadata:
            field_name = field.get('field_definition_name', '')
            field_type = field.get('field_type', '')
            value = field.get('value')
            
            # Check if this is an approval field
            if any(approval_field.lower() in field_name.lower() for approval_field in self.config.approval_field_names):
                if field_type in ['select', 'select_multi'] and value:
                    if isinstance(value, list) and value:
                        approval_status = value[0].get('display_name', str(value[0]))
                    else:
                        approval_status = str(value)
            
            # Check for user fields (who approved)
            elif field_type in ['user_single', 'user_multi'] and 'approv' in field_name.lower():
                if value and isinstance(value, list) and value:
                    approved_by = value[0].get('display_name', str(value[0]))
            
            # Check for date fields (when approved)
            elif field_type == 'date' and 'approv' in field_name.lower():
                if value:
                    approved_date = value
        
        return FileInfo(
            file_id=file_id,
            name=name,
            status=status,
            approval_status=approval_status,
            approved_by=approved_by,
            approved_date=approved_date,
            download_url=download_url,
            file_size=file_size,
            media_type=media_type,
            last_updated=last_updated
        )
    
    def is_approved(self, file_info: FileInfo) -> bool:
        """Check if a file is approved based on its metadata"""
        if not file_info.approval_status:
            return False
        
        # Check if the approval status matches any of our approved values
        for approved_value in self.config.approved_values:
            if approved_value.lower() in file_info.approval_status.lower():
                return True
        
        return False
    
    def download_file(self, file_info: FileInfo) -> bool:
        """Download an approved file to local storage"""
        if not file_info.download_url:
            print(f"❌ No download URL available for {file_info.name}")
            return False
        
        try:
            local_path = Path(self.config.local_download_path) / file_info.name
            
            # Avoid overwriting existing files
            if local_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_parts = file_info.name.rsplit('.', 1)
                if len(name_parts) == 2:
                    new_name = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
                else:
                    new_name = f"{file_info.name}_{timestamp}"
                local_path = Path(self.config.local_download_path) / new_name
            
            print(f"⬇️  Downloading: {file_info.name} ({file_info.file_size:,} bytes)")
            
            # Download the file
            response = requests.get(file_info.download_url, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✅ Downloaded: {local_path}")
            
            # Mark as downloaded
            self.downloaded_files.add(file_info.file_id)
            self.save_downloaded_files()
            
            return True
            
        except Exception as e:
            print(f"❌ Error downloading {file_info.name}: {e}")
            return False
    
    def check_for_approved_files(self):
        """Check folder for newly approved files and download them"""
        print(f"\n🔍 Checking for approved files at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        files = self.get_folder_files()
        newly_approved = []
        
        for file_info in files:
            # Skip if already downloaded
            if file_info.file_id in self.downloaded_files:
                continue
            
            # Check if approved
            if self.is_approved(file_info):
                newly_approved.append(file_info)
                print(f"✅ Found approved file: {file_info.name}")
                print(f"   Status: {file_info.approval_status}")
                if file_info.approved_by:
                    print(f"   Approved by: {file_info.approved_by}")
                if file_info.approved_date:
                    print(f"   Approved on: {file_info.approved_date}")
        
        # Download newly approved files
        if newly_approved and self.config.download_approved:
            print(f"\n⬇️  Downloading {len(newly_approved)} approved files...")
            for file_info in newly_approved:
                self.download_file(file_info)
        elif newly_approved:
            print(f"\n📋 Found {len(newly_approved)} approved files (download disabled)")
        else:
            print("🔍 No new approved files found")
        
        # Update tracked files
        for file_info in files:
            self.tracked_files[file_info.file_id] = file_info
    
    def print_status_summary(self):
        """Print a summary of current status"""
        print(f"\n📊 Status Summary:")
        print(f"   Monitored folder: {self.config.folder_id}")
        print(f"   Download path: {self.config.local_download_path}")
        print(f"   Approval fields: {', '.join(self.approval_fields.keys())}")
        print(f"   Approved values: {', '.join(self.config.approved_values)}")
        print(f"   Files downloaded: {len(self.downloaded_files)}")
        print(f"   Files tracked: {len(self.tracked_files)}")
        
        # Show approval status breakdown
        status_counts = {}
        for file_info in self.tracked_files.values():
            status = file_info.approval_status or "No status"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if status_counts:
            print("   Approval status breakdown:")
            for status, count in status_counts.items():
                print(f"     {status}: {count}")
    
    def run_continuous(self):
        """Run the monitor continuously"""
        print(f"🚀 Starting Frame.io Approval Monitor")
        print(f"⏱️  Check interval: {self.config.check_interval} seconds")
        
        self.print_status_summary()
        
        try:
            while True:
                self.check_for_approved_files()
                print(f"😴 Sleeping for {self.config.check_interval} seconds...")
                time.sleep(self.config.check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Error in monitoring loop: {e}")
    
    def run_once(self):
        """Run a single check"""
        print("🔍 Running single approval check...")
        self.check_for_approved_files()
        self.print_status_summary()

def create_config_from_args(args) -> ApprovalConfig:
    """Create ApprovalConfig from command line arguments"""
    return ApprovalConfig(
        folder_id=args.folder_id,
        local_download_path=args.download_path,
        approval_field_names=args.approval_fields,
        approved_values=args.approved_values,
        check_interval=args.interval,
        download_approved=not args.no_download,
        track_downloaded=True
    )

def main():
    parser = argparse.ArgumentParser(description='Monitor Frame.io folders for approved files')
    parser.add_argument('folder_id', help='Frame.io folder ID to monitor')
    parser.add_argument('download_path', help='Local path to download approved files')
    parser.add_argument('--approval-fields', nargs='+', 
                       default=['Approval Status', 'Review State', 'Status'], 
                       help='Names of metadata fields that contain approval status')
    parser.add_argument('--approved-values', nargs='+',
                       default=['Approved', 'Final', 'Ready', 'Complete'],
                       help='Values that indicate a file is approved')
    parser.add_argument('--interval', type=int, default=30,
                       help='Check interval in seconds (default: 30)')
    parser.add_argument('--no-download', action='store_true',
                       help='Only monitor, do not download files')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit (no continuous monitoring)')
    
    args = parser.parse_args()
    
    # Validate that we have required Frame.io credentials
    if not get_default_account():
        print("❌ No Frame.io account configured. Please run 'fio accounts' first.")
        return
    
    config = create_config_from_args(args)
    monitor = FrameIOApprovalMonitor(config)
    
    if args.once:
        monitor.run_once()
    else:
        monitor.run_continuous()

if __name__ == "__main__":
    main()
