# od-photosync

[![Docker Build](https://github.com/mokso/od-photosync/actions/workflows/docker-build.yml/badge.svg)](https://github.com/mokso/od-photosync/actions/workflows/docker-build.yml)
[![Docker Image](https://ghcr-badge.egpl.dev/mokso/od-photosync/latest_tag?trim=major&label=latest)](https://github.com/mokso/od-photosync/pkgs/container/od-photosync)
[![Docker Pulls](https://ghcr-badge.egpl.dev/mokso/od-photosync/size)](https://github.com/mokso/od-photosync/pkgs/container/od-photosync)

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

#### Using Pre-built Image (Recommended)

```bash
# Pull the latest image
docker pull ghcr.io/mokso/od-photosync:latest

# Or use docker-compose with pre-built image
# Update docker-compose.yml to use: image: ghcr.io/mokso/od-photosync:latest

# Initial auth (interactive)
docker run --rm -it \
  -v ./data:/app/data \
  -v ./config.yaml:/app/config.yaml:ro \
  ghcr.io/mokso/od-photosync:latest \
  python photosync.py --initial-auth

# Run sync
docker run --rm \
  -v /mnt/nas/photos:/photos \
  -v ./data:/app/data \
  -v ./config.yaml:/app/config.yaml:ro \
  ghcr.io/mokso/od-photosync:latest
```

#### Building Locally

```bash
# Build
docker-compose build

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
