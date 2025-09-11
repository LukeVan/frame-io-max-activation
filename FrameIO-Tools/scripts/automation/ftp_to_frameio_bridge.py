#!/usr/bin/env python3
"""
FTP to Frame.io Bridge

This script monitors an FTP server for new files, downloads them to a local folder,
and automatically uploads them to Frame.io.

Features:
- Monitors FTP server for new files every 10 seconds
- Downloads new files to local watch folder
- Watches local folder for new files and uploads to Frame.io
- Uses existing CLI upload functions with rate limiting
- Supports various file types and metadata extraction
- Handles errors gracefully with retry logic
- Prevents duplicate uploads
- Configurable FTP polling interval
"""

import os
import time
import argparse
import threading
import ftplib
from pathlib import Path
from typing import Set, Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
import hashlib
import urllib.parse

# Import CLI upload functions
from fio.commands.projects import upload_file_with_rate_limit, RateLimiter
from fio.config import get_default_account, get_default_folder, get_rate_limit

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("❌ Missing required dependency: watchdog")
    print("📦 Please install it with: pip install watchdog")
    exit(1)

@dataclass
class FTPConfig:
    """FTP server configuration"""
    host: str
    port: int = 21
    username: str = ""
    password: str = ""
    remote_path: str = "/"
    passive_mode: bool = True
    poll_interval: int = 10  # seconds - checking every 10 seconds
    
    @classmethod
    def from_url(cls, ftp_url: str) -> 'FTPConfig':
        """Parse FTP URL into config"""
        parsed = urllib.parse.urlparse(ftp_url)
        
        return cls(
            host=parsed.hostname or "",
            port=parsed.port or 21,
            username=parsed.username or "",
            password=parsed.password or "",
            remote_path=parsed.path or "/"
        )

@dataclass
class FTPFileInfo:
    """Information about a file on FTP server"""
    name: str
    size: int
    modified_time: datetime
    is_directory: bool = False
    
    def __hash__(self):
        return hash((self.name, self.size, self.modified_time))

@dataclass
class UploadJob:
    """Represents a file upload job"""
    file_path: str
    file_name: str
    file_size: int
    file_hash: str
    created_time: float
    upload_attempts: int = 0
    max_attempts: int = 3
    
    @classmethod
    def from_file(cls, file_path: str) -> 'UploadJob':
        """Create UploadJob from file path"""
        path = Path(file_path)
        file_size = path.stat().st_size
        
        # Calculate file hash for duplicate detection
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        return cls(
            file_path=str(path.absolute()),
            file_name=path.name,
            file_size=file_size,
            file_hash=file_hash,
            created_time=time.time()
        )

class FTPMonitor:
    """Monitors FTP server for new files and downloads them"""
    
    def __init__(self, ftp_config: FTPConfig, download_path: Path):
        self.ftp_config = ftp_config
        self.download_path = download_path
        self.known_files: Set[FTPFileInfo] = set()
        self.downloaded_files: Set[str] = set()
        self._running = False
        self._monitor_thread = None
        
        # Ensure download directory exists
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        print(f"📡 FTP Monitor: {ftp_config.host}:{ftp_config.port}")
        print(f"📂 Download to: {download_path}")
        print(f"⏰ Checking every {ftp_config.poll_interval} seconds")
    
    def start_monitoring(self):
        """Start FTP monitoring in background thread"""
        if self._running:
            return
            
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print("🚀 FTP monitor started")
    
    def stop_monitoring(self):
        """Stop FTP monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join()
        print("🛑 FTP monitor stopped")
    
    def _monitor_loop(self):
        """Main FTP monitoring loop"""
        while self._running:
            try:
                self._check_ftp_for_new_files()
                time.sleep(self.ftp_config.poll_interval)
            except Exception as e:
                print(f"❌ Error in FTP monitor: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _check_ftp_for_new_files(self):
        """Check FTP server for new files"""
        try:
            print(f"🔍 Checking FTP server for new files... [{datetime.now().strftime('%H:%M:%S')}]")
            
            # Connect to FTP server
            ftp = ftplib.FTP()
            ftp.connect(self.ftp_config.host, self.ftp_config.port, timeout=30)
            
            # Login
            if self.ftp_config.username:
                ftp.login(self.ftp_config.username, self.ftp_config.password)
                print(f"🔐 Logged in as: {self.ftp_config.username}")
            else:
                ftp.login()  # Anonymous login
                print("🔓 Anonymous login")
            
            # Set passive mode
            ftp.set_pasv(self.ftp_config.passive_mode)
            
            # Change to remote directory
            if self.ftp_config.remote_path != "/":
                ftp.cwd(self.ftp_config.remote_path)
                print(f"📁 Changed to directory: {self.ftp_config.remote_path}")
            
            # Get file list
            current_files = self._get_ftp_file_list(ftp)
            
            # Find new files
            new_files = current_files - self.known_files
            
            if new_files:
                print(f"📥 Found {len(new_files)} new files on FTP server")
                for file_info in new_files:
                    if not file_info.is_directory:
                        self._download_file(ftp, file_info)
            else:
                print("ℹ️  No new files found")
            
            # Update known files
            self.known_files = current_files
            
            ftp.quit()
            
        except Exception as e:
            print(f"❌ FTP check failed: {e}")
    
    def _get_ftp_file_list(self, ftp: ftplib.FTP) -> Set[FTPFileInfo]:
        """Get list of files from FTP server"""
        files = set()
        
        try:
            # Use MLSD if available (more reliable)
            for name, facts in ftp.mlsd():
                if name in ['.', '..']:
                    continue
                    
                is_dir = facts.get('type', '').lower() == 'dir'
                size = int(facts.get('size', 0))
                
                # Parse modification time
                modify_time = facts.get('modify')
                if modify_time:
                    try:
                        modified_time = datetime.strptime(modify_time, '%Y%m%d%H%M%S')
                    except ValueError:
                        modified_time = datetime.now()
                else:
                    modified_time = datetime.now()
                
                files.add(FTPFileInfo(
                    name=name,
                    size=size,
                    modified_time=modified_time,
                    is_directory=is_dir
                ))
                
        except ftplib.error_perm:
            # Fallback to LIST if MLSD not supported
            print("ℹ️  MLSD not supported, using LIST")
            lines = []
            ftp.retrlines('LIST', lines.append)
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 9:
                    name = ' '.join(parts[8:])
                    if name not in ['.', '..']:
                        is_dir = line.startswith('d')
                        size = int(parts[4]) if not is_dir and parts[4].isdigit() else 0
                        
                        files.add(FTPFileInfo(
                            name=name,
                            size=size,
                            modified_time=datetime.now(),  # Can't parse reliably from LIST
                            is_directory=is_dir
                        ))
        
        return files
    
    def _download_file(self, ftp: ftplib.FTP, file_info: FTPFileInfo):
        """Download a file from FTP server"""
        try:
            local_path = self.download_path / file_info.name
            
            # Skip if already downloaded
            if file_info.name in self.downloaded_files:
                print(f"⚠️  File already downloaded: {file_info.name}")
                return
            
            print(f"📥 Downloading: {file_info.name} ({file_info.size:,} bytes)")
            
            # Download file
            with open(local_path, 'wb') as local_file:
                def write_chunk(data):
                    local_file.write(data)
                
                ftp.retrbinary(f'RETR {file_info.name}', write_chunk)
            
            # Mark as downloaded
            self.downloaded_files.add(file_info.name)
            
            print(f"✅ Downloaded: {file_info.name} -> {local_path}")
            
        except Exception as e:
            print(f"❌ Failed to download {file_info.name}: {e}")

class HotFolderHandler(FileSystemEventHandler):
    """Handles file system events for the hot folder"""
    
    def __init__(self, upload_queue: 'UploadQueue'):
        self.upload_queue = upload_queue
        self.processing_files: Set[str] = set()
        
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = event.src_path
        print(f"🔍 New file detected in hot folder: {file_path}")
        
        # Wait a moment for file to be fully written
        threading.Thread(
            target=self._process_new_file, 
            args=(file_path,),
            daemon=True
        ).start()
    
    def _process_new_file(self, file_path: str):
        """Process a newly created file with stability check"""
        if file_path in self.processing_files:
            return
            
        self.processing_files.add(file_path)
        
        try:
            # Wait for file to be stable (not being written to)
            stable_size = None
            for attempt in range(10):  # Check for up to 10 seconds
                try:
                    current_size = os.path.getsize(file_path)
                    if stable_size is None:
                        stable_size = current_size
                    elif stable_size == current_size:
                        # File size hasn't changed, assume it's stable
                        break
                    else:
                        stable_size = current_size
                    time.sleep(1)
                except (OSError, FileNotFoundError):
                    # File might still be being written or was deleted
                    time.sleep(1)
                    continue
            
            # Verify file still exists and is accessible
            if not os.path.exists(file_path):
                print(f"⚠️  File disappeared: {file_path}")
                return
                
            try:
                upload_job = UploadJob.from_file(file_path)
                self.upload_queue.add_job(upload_job)
                print(f"📋 Queued for Frame.io upload: {upload_job.file_name} ({upload_job.file_size:,} bytes)")
            except Exception as e:
                print(f"❌ Error creating upload job for {file_path}: {e}")
                
        finally:
            self.processing_files.discard(file_path)

class UploadQueue:
    """Manages the queue of files to upload to Frame.io"""
    
    def __init__(self, target_folder_id: str, extract_metadata: bool = False, 
                 stable_delay: float = 2.0):
        self.target_folder_id = target_folder_id
        self.extract_metadata = extract_metadata
        self.stable_delay = stable_delay
        
        self.upload_queue: Dict[str, UploadJob] = {}
        self.uploaded_hashes: Set[str] = set()
        self.rate_limiter = RateLimiter(get_rate_limit())
        self.account_id = get_default_account()
        
        self._running = False
        self._worker_thread = None
        
        print(f"🎯 Frame.io upload target: Folder {target_folder_id}")
        print(f"⏱️  Rate limit: {get_rate_limit()} requests per minute")
        
    def add_job(self, job: UploadJob):
        """Add a new upload job to the queue"""
        # Check for duplicates by hash
        if job.file_hash in self.uploaded_hashes:
            print(f"⚠️  Skipping duplicate file: {job.file_name}")
            return
            
        # Check if already in queue
        if job.file_path in self.upload_queue:
            print(f"⚠️  File already in upload queue: {job.file_name}")
            return
            
        self.upload_queue[job.file_path] = job
        
    def start_processing(self):
        """Start the upload worker thread"""
        if self._running:
            return
            
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_uploads, daemon=True)
        self._worker_thread.start()
        print("🚀 Frame.io upload processor started")
        
    def stop_processing(self):
        """Stop the upload worker thread"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join()
        print("🛑 Frame.io upload processor stopped")
        
    def _process_uploads(self):
        """Main upload processing loop"""
        while self._running:
            try:
                if not self.upload_queue:
                    time.sleep(1)
                    continue
                    
                # Get next job (oldest first)
                job_path = min(self.upload_queue.keys(), 
                             key=lambda k: self.upload_queue[k].created_time)
                job = self.upload_queue[job_path]
                
                # Check if file has been stable long enough
                time_since_creation = time.time() - job.created_time
                if time_since_creation < self.stable_delay:
                    time.sleep(0.5)
                    continue
                    
                # Remove from queue
                del self.upload_queue[job_path]
                
                # Attempt upload
                self._upload_file(job)
                
            except Exception as e:
                print(f"❌ Error in upload processor: {e}")
                time.sleep(5)
                
    def _upload_file(self, job: UploadJob) -> bool:
        """Upload a single file to Frame.io"""
        print(f"⬆️  Uploading to Frame.io: {job.file_name} ({job.file_size:,} bytes)")
        
        try:
            # Verify file still exists
            if not os.path.exists(job.file_path):
                print(f"❌ File no longer exists: {job.file_path}")
                return False
            
            # Test authentication before attempting upload
            from fio.auth import get_access_token
            try:
                token = get_access_token()
                if not token:
                    raise Exception("Failed to get access token")
            except Exception as auth_error:
                print(f"❌ Authentication error: {auth_error}")
                raise Exception(f"Authentication failed: {auth_error}")
                
            # Use CLI upload function with rate limiting
            upload_file_with_rate_limit(
                local_path=job.file_path,
                rate_limiter=self.rate_limiter,
                extract_metadata=self.extract_metadata,
                target_folder_id=self.target_folder_id,
                account_id=self.account_id
            )
            
            # Mark as uploaded
            self.uploaded_hashes.add(job.file_hash)
            print(f"✅ Successfully uploaded to Frame.io: {job.file_name}")
            
            return True
            
        except Exception as e:
            job.upload_attempts += 1
            print(f"❌ Frame.io upload failed (attempt {job.upload_attempts}/{job.max_attempts}): {job.file_name}")
            print(f"   Error: {str(e)}")
            
            # Check if it's an authentication error
            error_str = str(e).lower()
            if "invalid_client" in error_str or "missing client_id" in error_str or "authentication" in error_str:
                print(f"🔐 Authentication issue detected. Please check your Frame.io credentials.")
                print(f"   Try running: fio accounts")
            
            # Retry if under max attempts
            if job.upload_attempts < job.max_attempts:
                retry_delay = 30 if "authentication" not in error_str else 60  # Longer delay for auth issues
                print(f"🔄 Will retry {job.file_name} in {retry_delay} seconds...")
                # Re-add to queue with delay
                threading.Timer(retry_delay, lambda: self.add_job(job)).start()
            else:
                print(f"💀 Giving up on {job.file_name} after {job.max_attempts} attempts")
                
            return False

class FTPToFrameIOBridge:
    """Main bridge class that coordinates FTP monitoring and Frame.io uploading"""
    
    def __init__(self, ftp_config: FTPConfig, watch_path: str, target_folder_id: str, 
                 extract_metadata: bool = False, stable_delay: float = 2.0):
        self.watch_path = Path(watch_path).absolute()
        self.target_folder_id = target_folder_id
        
        # Create watch folder if it doesn't exist
        self.watch_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.ftp_monitor = FTPMonitor(ftp_config, self.watch_path)
        self.upload_queue = UploadQueue(target_folder_id, extract_metadata, stable_delay)
        self.event_handler = HotFolderHandler(self.upload_queue)
        self.observer = Observer()
        
        print(f"🌉 FTP to Frame.io Bridge")
        print(f"📡 FTP: {ftp_config.host}:{ftp_config.port}{ftp_config.remote_path}")
        print(f"📂 Local: {self.watch_path}")
        print(f"🎯 Frame.io: {target_folder_id}")
        
    def start(self):
        """Start the FTP to Frame.io bridge"""
        print(f"🚀 Starting FTP to Frame.io bridge...")
        
        # Start Frame.io upload processor
        self.upload_queue.start_processing()
        
        # Start local folder watcher
        self.observer.schedule(self.event_handler, str(self.watch_path), recursive=False)
        self.observer.start()
        
        # Start FTP monitoring
        self.ftp_monitor.start_monitoring()
        
        print(f"✅ FTP to Frame.io bridge is running!")
        print(f"📡 Monitoring FTP: {self.ftp_monitor.ftp_config.host} (every {self.ftp_monitor.ftp_config.poll_interval}s)")
        print(f"📂 Local watch folder: {self.watch_path}")
        print(f"🎯 Uploading to Frame.io folder: {self.target_folder_id}")
        print("Press Ctrl+C to stop...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\\n🛑 Stopping FTP to Frame.io bridge...")
            self.stop()
            
    def stop(self):
        """Stop the FTP to Frame.io bridge"""
        self.ftp_monitor.stop_monitoring()
        self.observer.stop()
        self.observer.join()
        self.upload_queue.stop_processing()
        print("✅ FTP to Frame.io bridge stopped")

def main():
    parser = argparse.ArgumentParser(description='Monitor FTP server and upload new files to Frame.io')
    parser.add_argument('ftp_url', help='FTP server URL (ftp://user:pass@host:port/path)')
    parser.add_argument('watch_folder', help='Local folder to download FTP files to')
    parser.add_argument('target_folder_id', help='Frame.io folder ID to upload files to')
    parser.add_argument('--metadata', '-m', action='store_true', 
                       help='Extract and upload metadata from files')
    parser.add_argument('--stable-delay', type=float, default=2.0,
                       help='Seconds to wait after file creation before uploading (default: 2.0)')
    parser.add_argument('--poll-interval', type=int, default=10,
                       help='FTP polling interval in seconds (default: 10)')
    parser.add_argument('--passive', action='store_true', default=True,
                       help='Use FTP passive mode (default: True)')
    
    args = parser.parse_args()
    
    # Parse FTP configuration
    try:
        ftp_config = FTPConfig.from_url(args.ftp_url)
        ftp_config.poll_interval = args.poll_interval
        ftp_config.passive_mode = args.passive
    except Exception as e:
        print(f"❌ Invalid FTP URL: {e}")
        return 1
    
    # Verify CLI is configured
    if not get_default_account():
        print("❌ No Frame.io account configured. Please run 'fio accounts' first.")
        return 1
        
    try:
        bridge = FTPToFrameIOBridge(
            ftp_config=ftp_config,
            watch_path=args.watch_folder,
            target_folder_id=args.target_folder_id,
            extract_metadata=args.metadata,
            stable_delay=args.stable_delay
        )
        bridge.start()
        return 0
        
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
