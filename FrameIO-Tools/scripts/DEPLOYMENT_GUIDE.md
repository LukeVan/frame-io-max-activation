# 🚀 Frame.io Conference Deployment Guide

## 📦 **Two Deployment Options**

### **Option 1: Simple Zip & Install (Recommended)**

**✅ YES! You can zip the entire parent folder and move it to other machines.**

#### Steps:
1. **On Development Machine:**
   ```bash
   # Create deployment package
   cd /path/to/parent/directory
   zip -r FrameIO-Automation-Package.zip frame-io-v4-cli/
   ```

2. **On Target Conference Machines:**
   ```bash
   # Unzip package
   unzip FrameIO-Automation-Package.zip
   cd frame-io-v4-cli/
   
   # Run automated setup (installs everything)
   scripts/Setup_Conference_Mac.command
   ```

3. **What the setup script installs:**
   - ✅ Python dependencies (`watchdog`, `requests`, etc.)
   - ✅ Frame.io CLI (from included source code)
   - ✅ Desktop shortcuts for easy launching
   - ✅ Default folders for file operations

#### 🎯 **What You Need to Include in ZIP:**
```
frame-io-v4-cli/           # ← Zip this entire folder
├── .env                   # ← Your Frame.io credentials
├── fio/                   # ← CLI source code
├── scripts/               # ← Automation tools & launchers
├── setup.py               # ← For CLI installation
├── requirements.txt       # ← Python dependencies
└── README.md              # ← Documentation
```

### **Option 2: Manual Install (If Needed)**

If the automated setup fails, machines need:

1. **Python 3** (usually pre-installed on Mac)
2. **Manual Frame.io CLI install:**
   ```bash
   cd frame-io-v4-cli/
   pip3 install -e .
   ```
3. **Manual dependencies:**
   ```bash
   pip3 install watchdog requests python-dotenv click
   ```

## 🔐 **Authentication Setup**

### **Before Conference (One-Time Setup):**

1. **Get Frame.io API Credentials:**
   - Go to Adobe Developer Console
   - Create OAuth Server-to-Server app
   - Copy Client ID and Client Secret

2. **Create .env file in project root:**
   ```bash
   FRAME_CLIENT_ID=your_actual_client_id_here
   FRAME_CLIENT_SECRET=your_actual_client_secret_here
   ```

3. **Test authentication:**
   ```bash
   fio accounts  # Should show your Frame.io account
   ```

### **At Conference (Per Machine):**
- ✅ Credentials are already in the .env file you zipped
- ✅ No additional authentication needed
- ✅ All machines use the same credentials

## 🎪 **Conference Day Workflow**

### **Setup Phase (5-10 minutes per machine):**
1. **Copy & Unzip** the package to each Mac
2. **Run Setup**: Double-click `scripts/Setup_Conference_Mac.command`
3. **Verify**: Desktop shortcuts appear automatically

### **Operation Phase (Zero setup):**
1. **Hot Folder**: Double-click `🔥 Start Hot Folder` → Select folders → Drop files
2. **Status Monitor**: Double-click `📊 Start Status Monitor` → Select folders → Monitors automatically

## 🛠️ **Prerequisites for Target Machines**

### **✅ Usually Pre-Installed on Mac:**
- **Python 3** (comes with macOS)
- **Internet access** (for Frame.io API)

### **🔧 May Need Installation:**
- **pip3** (if not included with Python)
- **Xcode Command Line Tools** (if compilation is needed)

### **Quick Compatibility Check:**
```bash
# Run this on target machine before conference:
python3 --version     # Should show 3.7+
pip3 --version        # Should show pip version
curl frame.io        # Should resolve (internet test)
```

## 📁 **Folder Structure After Deployment**

```
MacBook/Desktop/
└── Activation Setup/                # ← Main folder for all Frame.io tools
    ├── 🔥 Start Hot Folder.command      # ← Double-click to upload files
    ├── 📊 Start Status Monitor.command  # ← Double-click to download approved files
    ├── FrameIO_Upload_HotFolder/         # ← Drop files here to upload
    └── FrameIO_Downloads/               # ← Approved files download here

MacBook/frame-io-v4-cli/             # ← Main package directory
├── .env                             # ← Your credentials
├── scripts/                         # ← All automation tools
└── (all other files)                # ← CLI source & documentation
```

## 🚨 **Troubleshooting at Conference**

### **"Command not found: fio"**
```bash
cd frame-io-v4-cli/
pip3 install -e .
```

### **"Authentication failed"**
- Check `.env` file exists in project root
- Verify credentials are correct (no extra spaces/characters)

### **"Permission denied"**
```bash
chmod +x scripts/*.command
```

### **Dependencies missing**
```bash
pip3 install watchdog requests python-dotenv click rich
```

## 💡 **Pro Tips for Conference Deployment**

1. **Test the ZIP package** on a different machine before the conference
2. **Bring a backup** of the .env credentials file
3. **Pre-test with conference network** if possible
4. **Create a setup checklist** for volunteer helpers
5. **Document your Frame.io folder IDs** for quick reference

## 🎯 **Quick Deploy Checklist**

**Pre-Conference:**
- [ ] Test complete workflow on development machine
- [ ] Create deployment ZIP with correct .env credentials
- [ ] Test ZIP deployment on at least one other machine
- [ ] Document all Frame.io folder IDs needed

**Conference Day:**
- [ ] Unzip package on each Mac
- [ ] Run `Setup_Conference_Mac.command` on each machine
- [ ] Verify desktop shortcuts appear
- [ ] Test one upload and one download workflow
- [ ] Brief users on double-click operation

---

**🎉 You're ready for seamless conference deployment!**
