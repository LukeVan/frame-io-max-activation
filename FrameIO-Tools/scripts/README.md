# Frame.io Automation Scripts

This directory contains production automation scripts for Frame.io workflows.

## 📁 Directory Structure

```
scripts/
├── automation/           # Main automation workflows
│   ├── approval_monitor.py      # Monitors Frame.io for approved files
│   ├── ftp_to_frameio_bridge.py # FTP to Frame.io file bridge
│   ├── simple_hotfolder.py      # Local hotfolder uploader
│   └── status_monitor.py        # Status-based file monitor
└── utilities/           # Helper and utility scripts
    └── set_file_status.py       # Set file metadata for testing
```

## 🚀 Quick Start Commands

### Status Monitor (Recommended)
Monitors Frame.io metadata fields for approved files and downloads them:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli
python3 scripts/automation/status_monitor.py FOLDER_ID ../working_folders/approved_downloads
```

### Advanced Approval Monitor
Full-featured monitor with field discovery and multiple approval workflows:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli
python3 scripts/automation/approval_monitor.py FOLDER_ID ../working_folders/approved_downloads
```

### FTP to Frame.io Bridge
Downloads files from FTP and uploads to Frame.io:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli
python3 scripts/automation/ftp_to_frameio_bridge.py ftp://server:port ../working_folders/ftp_downloads FOLDER_ID
```

### Simple Hot Folder
Watches local folder and uploads new files:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli
python3 scripts/automation/simple_hotfolder.py ../working_folders/hotfolder_uploads FOLDER_ID
```

## 📋 Your Specific Folder IDs

**Replace these with your actual folder IDs:**
- **Upload Target**: `71a2d5ed-9f18-4a0d-ac02-9bc1b0c95e3e`
- **Monitor Source**: `10761dd7-895a-43b2-9c27-5d54aaf00280`
- **FTP Server**: `ftp://192.168.1.77:2121`

## 🛠️ Setup Requirements

1. **Navigate to project root**:
   ```bash
   cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli
   ```

2. **Frame.io CLI configured**:
   ```bash
   fio accounts  # Should show your account
   ```

3. **Python dependencies**:
   ```bash
   pip3 install watchdog  # For hotfolder monitoring
   ```

## 🔥 Production Commands (Copy-Paste Ready)

### Start FTP Bridge:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli && python3 scripts/automation/ftp_to_frameio_bridge.py ftp://192.168.1.77:2121 working_folders/ftp_downloads 71a2d5ed-9f18-4a0d-ac02-9bc1b0c95e3e --metadata
```

### Start Status Monitor:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli && python3 scripts/automation/status_monitor.py 10761dd7-895a-43b2-9c27-5d54aaf00280 working_folders/approved_downloads
```

### Start Status Monitor with Custom Fields:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli && python3 scripts/automation/status_monitor.py 10761dd7-895a-43b2-9c27-5d54aaf00280 working_folders/approved_downloads --status-fields "Approval Status" "Review State" "Status" --approved-values "Approved" "Final" "Ready"
```

### Start Hot Folder:
```bash
cd /Users/lukevan/Documents/GitHub/frame-io-v4-cli && python3 scripts/automation/simple_hotfolder.py working_folders/hotfolder_uploads 71a2d5ed-9f18-4a0d-ac02-9bc1b0c95e3e --metadata
```

## 📝 Working Folders

All input/output folders are in `../working_folders/` relative to scripts:
- `approved_downloads/` - Downloaded approved files
- `ftp_downloads/` - Files downloaded from FTP
- `hotfolder_uploads/` - Local files to upload
- `Scans-Approved/` - Processed scans
- `Scans-input/` - Input scans

*Working folders are excluded from git via .gitignore*

---

*For detailed documentation, see [docs/README_AUTOMATION_SCRIPTS.md](../docs/README_AUTOMATION_SCRIPTS.md)*
