#!/usr/bin/env python3
"""
Frame.io Hot Folder Watcher

This script monitors a local folder for new files and automatically uploads them
to a specified Frame.io folder using the existing CLI upload functionality.

Features:
- Watches for new files added to a local "hot folder"
- Automatically uploads files to Frame.io when detected
- Uses existing CLI upload functions with rate limiting
- Supports various file types and metadata extraction
- Handles errors gracefully with retry logic
- Prevents duplicate uploads
"""

import os
import time
import argparse
import threading
from pathlib import Path
from typing import Set, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib

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
        print(f"🔍 New file detected: {file_path}")
        
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
                print(f"📋 Queued for upload: {upload_job.file_name} ({upload_job.file_size:,} bytes)")
            except Exception as e:
                print(f"❌ Error creating upload job for {file_path}: {e}")
                
        finally:
            self.processing_files.discard(file_path)

class UploadQueue:
    """Manages the queue of files to upload"""
    
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
        
        print(f"🎯 Upload target: Folder {target_folder_id}")
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
        print("🚀 Upload processor started")
        
    def stop_processing(self):
        """Stop the upload worker thread"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join()
        print("🛑 Upload processor stopped")
        
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
        """Upload a single file"""
        print(f"⬆️  Uploading: {job.file_name} ({job.file_size:,} bytes)")
        
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
            print(f"✅ Successfully uploaded: {job.file_name}")
            
            return True
            
        except Exception as e:
            job.upload_attempts += 1
            print(f"❌ Upload failed (attempt {job.upload_attempts}/{job.max_attempts}): {job.file_name}")
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

class HotFolderWatcher:
    """Main hot folder watcher class"""
    
    def __init__(self, watch_path: str, target_folder_id: str, 
                 extract_metadata: bool = False, stable_delay: float = 2.0):
        self.watch_path = Path(watch_path).absolute()
        self.target_folder_id = target_folder_id
        
        # Verify watch folder exists
        if not self.watch_path.exists():
            raise ValueError(f"Watch folder does not exist: {self.watch_path}")
        if not self.watch_path.is_dir():
            raise ValueError(f"Watch path is not a directory: {self.watch_path}")
            
        # Initialize components
        self.upload_queue = UploadQueue(target_folder_id, extract_metadata, stable_delay)
        self.event_handler = HotFolderHandler(self.upload_queue)
        self.observer = Observer()
        
        print(f"👀 Watching: {self.watch_path}")
        
    def start(self):
        """Start watching the hot folder"""
        print(f"🔥 Starting hot folder watcher...")
        
        # Start upload processor
        self.upload_queue.start_processing()
        
        # Start file system watcher
        self.observer.schedule(self.event_handler, str(self.watch_path), recursive=False)
        self.observer.start()
        
        print(f"✅ Hot folder watcher is running!")
        print(f"📂 Drop files into: {self.watch_path}")
        print(f"🎯 Files will be uploaded to Frame.io folder: {self.target_folder_id}")
        print("Press Ctrl+C to stop...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\\n🛑 Stopping hot folder watcher...")
            self.stop()
            
    def stop(self):
        """Stop the hot folder watcher"""
        self.observer.stop()
        self.observer.join()
        self.upload_queue.stop_processing()
        print("✅ Hot folder watcher stopped")

def main():
    parser = argparse.ArgumentParser(description='Watch a local folder and upload new files to Frame.io')
    parser.add_argument('watch_folder', help='Local folder to watch for new files')
    parser.add_argument('target_folder_id', help='Frame.io folder ID to upload files to')
    parser.add_argument('--metadata', '-m', action='store_true', 
                       help='Extract and upload metadata from files')
    parser.add_argument('--stable-delay', type=float, default=2.0,
                       help='Seconds to wait after file creation before uploading (default: 2.0)')
    
    args = parser.parse_args()
    
    # Verify CLI is configured
    if not get_default_account():
        print("❌ No Frame.io account configured. Please run 'fio accounts' first.")
        return 1
        
    try:
        watcher = HotFolderWatcher(
            watch_path=args.watch_folder,
            target_folder_id=args.target_folder_id,
            extract_metadata=args.metadata,
            stable_delay=args.stable_delay
        )
        watcher.start()
        return 0
        
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
