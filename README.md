# od-photosync

[![Docker Build](https://github.com/mokso/od-photosync/actions/workflows/docker-build.yml/badge.svg)](https://github.com/mokso/od-photosync/actions/workflows/docker-build.yml)
[![Docker Image](https://ghcr-badge.egpl.dev/mokso/od-photosync/latest_tag?trim=major&label=latest)](https://github.com/mokso/od-photosync/pkgs/container/od-photosync)
[![Docker Pulls](https://ghcr-badge.egpl.dev/mokso/od-photosync/size)](https://github.com/mokso/od-photosync/pkgs/container/od-photosync)

**Bidirectional sync** between OneDrive and local NAS storage. Download from OneDrive camera roll and upload files to OneDrive backup. Python implementation with container support.

## Features

### Download (OneDrive → Local NAS)
- ✅ Sync OneDrive camera roll to local storage
- ✅ Date-based folder organization (YYYY/YYYY_MM_DD/)
- ✅ Optional deletion of synced files from OneDrive

### Upload (Local NAS → OneDrive)
- ✅ Upload files from local folders to OneDrive
- ✅ Configurable file patterns (e.g., only PDFs, images)
- ✅ Automatic folder creation in OneDrive
- ✅ Smart caching system for 500k+ files
- ✅ Watermark/incremental scan (only process new files)
- ✅ Build cache from existing OneDrive files
- ✅ Large file support with resumable uploads (>4MB)
- ✅ Optional deletion of local files after upload

### Scheduling & Monitoring
- ✅ Built-in scheduler (no cron needed)
- ✅ Configurable intervals (minutes/hours/days)
- ✅ Healthchecks.io integration for monitoring
- ✅ Configurable authentication timeout
- ✅ Graceful shutdown on Ctrl+C

### General Features
- ✅ Device code flow authentication (headless-friendly)
- ✅ Multi-profile support (sync multiple OneDrive accounts)
- ✅ Automatic token refresh
- ✅ File verification to prevent duplicates
- ✅ Docker/Kubernetes ready
- ✅ Comprehensive logging

## Quick Start

### Local Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp config.yaml.example config.yaml
# Edit config.yaml with your client_id and paths

# Initial authentication
python photosync.py --initial-auth

# Run sync once
python photosync.py

# Run continuously on schedule (60 min intervals)
python photosync.py --schedule

# Run with custom interval (30 minutes)
python photosync.py --schedule --interval 30

# Build cache from existing OneDrive files (for large collections)
python photosync.py --build-cache
```

### Docker Compose 

Multiple compose files for different operations:

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env: Set PHOTOS_PATH=/mnt/kuvat (or your mount path)

# 2. Initial authentication (interactive)
docker-compose -f docker-compose.auth.yml run --rm photosync-auth

# 3. Optional: Build cache from existing OneDrive files (for large collections)
docker-compose -f docker-compose.build-cache.yml run --rm photosync-build-cache

# 4. Run scheduled sync (continuously, as daemon)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop scheduled sync
docker-compose down
```

**One-time sync:**
```bash
docker-compose -f docker-compose.sync-once.yml run --rm photosync-once
```

**Available compose files:**
- `docker-compose.yml` - Scheduled sync (runs continuously)
- `docker-compose.auth.yml` - Initial authentication
- `docker-compose.build-cache.yml` - Build cache from OneDrive
- `docker-compose.sync-once.yml` - Single sync run

### Docker (Manual)

```bash
# Pull the latest image
docker pull ghcr.io/mokso/od-photosync:latest

# Initial auth (interactive)
docker run --rm -it \
  -v ./data:/app/data \
  -v ./config.yaml:/app/config.yaml:ro \
  ghcr.io/mokso/od-photosync:latest \
  python photosync.py --initial-auth

# Run scheduled sync
docker run -d \
  -v /mnt/nas/photos:/photos \
  -v ./data:/app/data \
  -v ./config.yaml:/app/config.yaml:ro \
  ghcr.io/mokso/od-photosync:latest \
  python photosync.py --schedule
```

### Building Locally

```bash
# Build
docker build -t od-photosync .

# Initial auth (interactive)
docker-compose run --rm photosync python photosync.py --initial-auth

# Run sync
docker-compose run --rm photosync
```

**Available Tags:**
- `latest` - Latest build from main branch
- `main` - Latest build from main branch
- `python-rewrite` - Development branch
- `v*` - Specific version tags
- `sha-<commit>` - Specific commit builds

See [CONTAINER.md](CONTAINER.md) for detailed container documentation and Kubernetes deployment examples.

## Scheduling

### Built-in Scheduler (Recommended)

The application includes a built-in scheduler - no need for cron, systemd timers, or external schedulers:

```bash
# Run with built-in scheduler (uses schedule_interval_minutes from config)
python photosync.py --schedule

# Or override interval from command line (30 minutes)
python photosync.py --schedule --interval 30
```

**Configuration:**
```yaml
# config.yaml
schedule_interval_minutes: 60  # Run every hour
auth_timeout_seconds: 300      # 5 min timeout for auth
healthcheck_url: "https://hc-ping.com/your-uuid"  # Optional monitoring
```

**Docker with built-in scheduler:**
```bash
docker run -d \
  -v /mnt/nas/photos:/photos \
  -v ./data:/app/data \
  -v ./config.yaml:/app/config.yaml:ro \
  ghcr.io/mokso/od-photosync:latest \
  python photosync.py --schedule
```

### Alternative Scheduling Methods

**For NAS users (OpenMediaVault, TrueNAS, Synology):**
Run Python directly via OMV's scheduled jobs:
```bash
# SSH to NAS and install once
cd /srv/appdata/
git clone https://github.com/mokso/od-photosync.git
cd od-photosync
pip3 install -r requirements.txt
python3 photosync.py --initial-auth

# Create OMV scheduled job with:
cd /srv/appdata/od-photosync && python3 photosync.py
```

**For external cron/schedulers:**
Use the legacy scheduled container approach:
```bash
docker-compose -f docker-compose.scheduled.yml up -d
```

See [SCHEDULING.md](SCHEDULING.md) for all scheduling options including Dkron, K8s CronJobs, and more.

## PowerShell Version

The original PowerShell implementation is available in the [`powershell/`](powershell/) directory.

**Quick Start:**
```powershell
cd powershell
.\photosync.ps1
```

See [PowerShell README](powershell/README.md) for detailed documentation.



## Storage Structure

Photos are organized by date:
```
/photos/
├── Profile1/
│   ├── 2024/
│   │   ├── 2024_01_15/
│   │   │   ├── IMG_1234.jpg
│   │   │   └── IMG_1235.jpg
│   │   └── 2024_01_16/
│   └── 2025/
└── Profile2/
    └── ...
```

## Configuration

Create a `config.yaml` file:

```yaml
# Microsoft App Registration Client ID
client_id: "your-client-id-here"

# Data directory for storing auth tokens and logs
data_dir: "./data"

# Scheduled sync interval (for --schedule mode)
schedule_interval_minutes: 60

# Authentication timeout (skip profile if not auth'd in time)
auth_timeout_seconds: 300

# Healthchecks.io monitoring (optional)
healthcheck_url: "https://hc-ping.com/your-uuid-here"

# Download profiles - OneDrive camera roll to local NAS
download_profiles:
  - name: "Profile1"
    destination_folder: "Z:/media/Photos/Profile1"
    remove_downloaded: true

# Upload profiles - Local NAS to OneDrive backup
upload_profiles:
  - name: "NasBackup"
    source_folder: "Z:/media/Documents"
    onedrive_folder: "/Backup/Documents"
    file_patterns: ["*.pdf", "*.docx", "*.xlsx"]
    preserve_structure: true      # Keep folder structure
    use_cache: true               # Cache uploaded files (essential for 500k+ files)
    use_watermark: false          # Only scan new files (faster incremental)
    remove_uploaded: false
```

See [config.yaml.example](config.yaml.example) for more examples.

**📘 Upload Feature Documentation:** See [UPLOAD.md](UPLOAD.md) for detailed documentation on syncing files from your NAS to OneDrive.

## Command-Line Options

```bash
# Authentication
python photosync.py --initial-auth     # Force authentication for all profiles
python photosync.py --logout           # Remove all cached tokens

# Sync modes
python photosync.py                    # Run sync once
python photosync.py --schedule         # Run continuously (uses config interval)
python photosync.py --schedule --interval 30  # Run every 30 minutes

# Cache management (for upload profiles)
python photosync.py --build-cache      # Build cache from existing OneDrive files
python photosync.py --clear-cache      # Delete all upload caches

# Advanced
python photosync.py --config custom.yaml  # Use custom config file
```

**Performance Tips:**
- For large collections (500k+ files), run `--build-cache` first to avoid re-uploading
- Enable `use_watermark: true` for 95% faster incremental syncs
- Enable `use_cache: true` (default) to skip already uploaded files

## Azure AD App Registration

1. Go to [Azure Portal](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Create new registration:
   - Name: "OneDrive Photo Sync"
   - Supported account types: "Personal Microsoft accounts only"
   - Redirect URI: Leave blank (uses device code flow)
3. Copy the **Application (client) ID**
4. Under "API permissions", add:
   - Microsoft Graph → Delegated → `Files.ReadWrite`
   - Microsoft Graph → Delegated → `offline_access`
5. **IMPORTANT**: Go to "Authentication" → "Advanced settings" → Set "Allow public client flows" to **YES** → Save

See [SETUP.md](SETUP.md) for detailed setup instructions.

## Authentication: Python vs PowerShell

This Python implementation uses a different authentication approach compared to the original PowerShell version:

| Aspect | Python (This Version) | PowerShell (Original) |
|--------|----------------------|----------------------|
| **Auth Flow** | Device Code Flow | Interactive Browser Flow |
| **API** | Microsoft Graph API v1.0 | OneDrive API v1.0 |
| **Client Secret** | Not required | Required |
| **Scopes** | `Files.ReadWrite` | `onedrive.readwrite` |
| **Headless Support** | ✅ Yes (perfect for containers) | ❌ No (requires GUI) |
| **User Experience** | Enter code on any device | Browser opens automatically |
| **Container Ready** | ✅ Yes | Limited |

### Device Code Flow (Python)

When you run `python photosync.py --initial-auth`, you'll see:

```
To sign in, use a web browser to open the page https://www.microsoft.com/link
and enter the code ABC12345 to authenticate.
```

You can authenticate on **any device** (phone, tablet, another computer) by:
1. Opening the URL in a browser
2. Entering the code shown
3. Signing in with your Microsoft account

This makes it ideal for:
- 🐳 Docker containers
- 🖥️ Headless servers
- 🔒 Secure environments without GUI
- 📱 Authentication from mobile devices

### Interactive Browser Flow (PowerShell)

The PowerShell version automatically opens a browser window on the same machine, requiring:
- A GUI environment (Windows desktop)
- Interactive session
- Browser access on the same system

**Note:** You can use the same Azure app registration for both versions, but the Python version needs "Allow public client flows" enabled.

## Usage

## Healthchecks.io Monitoring

Monitor your scheduled syncs with healthchecks.io:

1. Create a check at https://healthchecks.io/
2. Set expected interval (e.g., 1 hour)
3. Add to config:
   ```yaml
   healthcheck_url: "https://hc-ping.com/your-uuid-here"
   ```

The application will send:
- `/start` signal when sync begins
- Success signal (no suffix) when sync completes
- `/fail` signal if errors occur or authentication times out

Perfect for getting alerts when:
- ❌ Syncs fail
- ⏰ Syncs don't run on schedule
- 🔐 Authentication timeouts occur

## Project Structure

```
od-photosync/
├── photosync.py              # Main application
├── auth_manager.py           # Authentication & token management
├── onedrive_client.py        # OneDrive API client
├── logger.py                 # Logging utilities
├── config.yaml               # Configuration file
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container image
├── docker-compose.yml        # Container orchestration
├── TROUBLESHOOTING.md        # Troubleshooting guide
├── data/                     # Auth tokens & logs (created at runtime)
└── powershell/               # Original PowerShell implementation
    └── ...
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

## License

MIT License
