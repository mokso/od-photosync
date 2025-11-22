# od-photosync

Sync OneDrive camera roll to local NAS storage. Python implementation with container support.

## Features

- ✅ Device code flow authentication (headless-friendly)
- ✅ Multi-profile support (sync multiple OneDrive accounts)
- ✅ Automatic token refresh
- ✅ Optional deletion of synced files from OneDrive
- ✅ Date-based folder organization (YYYY/YYYY_MM_DD/)
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

# Run sync
python photosync.py
```

### Docker

```bash
# Build
docker-compose build

# Initial auth (interactive)
docker-compose run --rm photosync python photosync.py --initial-auth

# Run sync
docker-compose run --rm photosync
```

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

# Photo sync profiles
profiles:
  - name: "Profile1"
    destination_folder: "Z:/media/Photos/Profile1"
    remove_downloaded: true
```

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

## Usage

```bash
# Initial authentication (run once per profile)
python photosync.py --initial-auth

# Run sync
python photosync.py

# Logout (remove tokens)
python photosync.py --logout
```

## Scheduling

### Linux/Mac (cron)
```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/od-photosync && python photosync.py
```

### Docker (cron)
```bash
0 2 * * * cd /path/to/od-photosync && docker-compose run --rm photosync
```

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
