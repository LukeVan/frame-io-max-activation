#!/usr/bin/env python3
"""
Simplified Hot Folder Watcher that uses CLI commands directly
This avoids potential issues with internal function calls and authentication
"""

import os
import time
import subprocess
import argparse
import threading
from pathlib import Path
from typing import Set
from dataclasses import dataclass
import hashlib

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

def should_ignore_file(file_path: str) -> bool:
    """Check if a file should be ignored based on name patterns"""
    file_name = Path(file_path).name.lower()
    
    # System files to ignore
    ignored_patterns = [
        '.ds_store',           # macOS Finder metadata
        '._.ds_store',         # macOS resource fork
        'thumbs.db',           # Windows thumbnail cache
        'desktop.ini',         # Windows folder settings
        '.localized',          # macOS localization
        '.fseventsd',          # macOS file system events
        '.spotlight-v100',     # macOS Spotlight index
        '.trashes',            # macOS trash
        '.documentrevisions-v100',  # macOS document versions
        '.fuse_hidden',        # FUSE hidden files
    ]
    
    # Check exact matches first
    for pattern in ignored_patterns:
        if file_name == pattern:
            return True
    
    # Check wildcard patterns
    if file_name.startswith('._'):  # macOS resource forks
        return True
    if file_name.endswith('~'):     # Backup files
        return True
    if file_name.startswith('.#'):  # Lock files
        return True
    if file_name.startswith('#') and file_name.endswith('#'):  # Emacs temp
        return True
    if file_name.endswith('.tmp') or file_name.endswith('.temp'):  # Temp files
        return True
    if file_name.startswith('.tmp'):  # Temp files
        return True
    if file_name.startswith('.dat.nosync'):  # Sync service temp files
        return True
    if file_name.startswith('.syncthing'):  # Syncthing temp files
        return True
    if file_name.endswith('.synctmp'):  # More sync temp files
        return True
        
    # Check file extensions that should be ignored
    ignored_extensions = [
        '.part',      # Partial downloads
        '.crdownload', # Chrome downloads
        '.download',   # Firefox downloads
        '.!ut',        # uTorrent partial
    ]
    
    file_extension = Path(file_path).suffix.lower()
    if file_extension in ignored_extensions:
        return True
    
    return False

class SimpleHotFolderHandler(FileSystemEventHandler):
    """Handles file system events for the hot folder"""
    
    def __init__(self, upload_queue: 'SimpleUploadQueue'):
        self.upload_queue = upload_queue
        self.processing_files: Set[str] = set()
        
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        self._handle_new_file(event.src_path, "created")
    
    def on_moved(self, event):
        """Handle file move/rename events (like temp file -> final name)"""
        if event.is_directory:
            return
        # Process the destination file (the final renamed file)
        self._handle_new_file(event.dest_path, "moved")
    
    def _handle_new_file(self, file_path: str, event_type: str):
        """Common handler for new files (created or moved)"""
        # Check if this file should be ignored
        if should_ignore_file(file_path):
            print(f"⏭️  Ignoring system/temp file: {Path(file_path).name} ({event_type})")
            return
        
        # If not ignored, show that we're going to process it
        print(f"📸 Processing file: {Path(file_path).name} ({event_type})")
        
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
                print(f"⚠️  File disappeared during stability check: {Path(file_path).name}")
                return
            
            print(f"✅ File is stable: {Path(file_path).name} ({os.path.getsize(file_path):,} bytes)")
                
            try:
                # Calculate file hash for duplicate detection
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                
                upload_job = UploadJob(
                    file_path=str(Path(file_path).absolute()),
                    file_name=Path(file_path).name,
                    file_size=os.path.getsize(file_path),
                    file_hash=file_hash,
                    created_time=time.time()
                )
                
                self.upload_queue.add_job(upload_job)
                print(f"📋 Queued for upload: {upload_job.file_name} ({upload_job.file_size:,} bytes)")
            except Exception as e:
                print(f"❌ Error creating upload job for {file_path}: {e}")
                
        finally:
            self.processing_files.discard(file_path)

class SimpleUploadQueue:
    """Manages the queue of files to upload using CLI commands"""
    
    def __init__(self, target_folder_id: str, extract_metadata: bool = False):
        self.target_folder_id = target_folder_id
        self.extract_metadata = extract_metadata
        
        self.upload_queue: dict = {}
        self.uploaded_hashes: Set[str] = set()
        
        self._running = False
        self._worker_thread = None
        
        print(f"🎯 Upload target: Folder {target_folder_id}")
        
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
                if time_since_creation < 2.0:  # 2 second stability delay
                    time.sleep(0.5)
                    continue
                    
                # Remove from queue
                del self.upload_queue[job_path]
                
                # Attempt upload
                self._upload_file_via_cli(job)
                
            except Exception as e:
                print(f"❌ Error in upload processor: {e}")
                time.sleep(5)
                
    def _upload_file_via_cli(self, job: UploadJob) -> bool:
        """Upload a single file using the CLI command"""
        print(f"⬆️  Uploading: {job.file_name} ({job.file_size:,} bytes)")
        
        try:
            # Verify file still exists
            if not os.path.exists(job.file_path):
                print(f"❌ File no longer exists: {job.file_path}")
                return False
            
            # First, navigate to the target folder
            print(f"📂 Setting target folder: {self.target_folder_id}")
            cd_result = subprocess.run([
                'fio', 'cd', self.target_folder_id
            ], capture_output=True, text=True, timeout=30)
            
            if cd_result.returncode != 0:
                raise Exception(f"Failed to navigate to folder: {cd_result.stderr}")
            
            # Build upload command
            upload_cmd = ['fio', 'upload', job.file_path]
            if self.extract_metadata:
                upload_cmd.append('--md')
            
            print(f"🔧 Running: {' '.join(upload_cmd)}")
            
            # Run upload command
            result = subprocess.run(
                upload_cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  # 5 minute timeout
                input='y\n'  # Auto-confirm upload
            )
            
            if result.returncode == 0:
                # Mark as uploaded
                self.uploaded_hashes.add(job.file_hash)
                print(f"✅ Successfully uploaded: {job.file_name}")
                return True
            else:
                raise Exception(f"Upload command failed: {result.stderr or result.stdout}")
            
        except subprocess.TimeoutExpired:
            error_msg = f"Upload timed out after 5 minutes"
            print(f"❌ {error_msg}: {job.file_name}")
            self._handle_upload_failure(job, error_msg)
            return False
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Upload failed: {job.file_name}")
            print(f"   Error: {error_msg}")
            self._handle_upload_failure(job, error_msg)
            return False
    
    def _handle_upload_failure(self, job: UploadJob, error_msg: str):
        """Handle upload failure with retry logic"""
        job.upload_attempts += 1
        print(f"   Attempt {job.upload_attempts}/{job.max_attempts}")
        
        # Retry if under max attempts
        if job.upload_attempts < job.max_attempts:
            retry_delay = 60  # 1 minute delay for retries
            print(f"🔄 Will retry {job.file_name} in {retry_delay} seconds...")
            # Re-add to queue with delay
            threading.Timer(retry_delay, lambda: self.add_job(job)).start()
        else:
            print(f"💀 Giving up on {job.file_name} after {job.max_attempts} attempts")

class SimpleHotFolderWatcher:
    """Simplified hot folder watcher using CLI commands"""
    
    def __init__(self, watch_path: str, target_folder_id: str, extract_metadata: bool = False):
        self.watch_path = Path(watch_path).absolute()
        self.target_folder_id = target_folder_id
        
        # Verify watch folder exists
        if not self.watch_path.exists():
            raise ValueError(f"Watch folder does not exist: {self.watch_path}")
        if not self.watch_path.is_dir():
            raise ValueError(f"Watch path is not a directory: {self.watch_path}")
            
        # Initialize components
        self.upload_queue = SimpleUploadQueue(target_folder_id, extract_metadata)
        self.event_handler = SimpleHotFolderHandler(self.upload_queue)
        self.observer = Observer()
        
        print(f"👀 Watching: {self.watch_path}")
        
    def start(self):
        """Start watching the hot folder"""
        print(f"🔥 Starting simple hot folder watcher...")
        
        # Test CLI connectivity first
        print("🔍 Testing CLI connectivity...")
        try:
            result = subprocess.run(['fio', 'accounts'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise Exception(f"CLI test failed: {result.stderr}")
            print("✅ CLI connectivity verified")
        except Exception as e:
            print(f"❌ CLI test failed: {e}")
            print("Please ensure 'fio accounts' works before running the hot folder watcher")
            return
        
        # Start upload processor
        self.upload_queue.start_processing()
        
        # Start file system watcher
        self.observer.schedule(self.event_handler, str(self.watch_path), recursive=False)
        self.observer.start()
        
        print(f"✅ Simple hot folder watcher is running!")
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
    parser = argparse.ArgumentParser(description='Simple hot folder watcher using CLI commands')
    parser.add_argument('watch_folder', help='Local folder to watch for new files')
    parser.add_argument('target_folder_id', help='Frame.io folder ID to upload files to')
    parser.add_argument('--metadata', '-m', action='store_true', 
                       help='Extract and upload metadata from files')
    
    args = parser.parse_args()
    
    try:
        watcher = SimpleHotFolderWatcher(
            watch_path=args.watch_folder,
            target_folder_id=args.target_folder_id,
            extract_metadata=args.metadata
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
