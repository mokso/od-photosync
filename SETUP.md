# Quick Setup Guide

## Initial Setup

### 1. Choose Your Implementation

- **Python** (recommended, in root directory)
- **PowerShell** (in `powershell/` directory): `cd powershell`

### 2. Azure AD App Registration

1. Go to https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
2. Click "New registration"
3. Settings:
   - **Name**: OneDrive Photo Sync
   - **Supported account types**: Personal Microsoft accounts only
   - **Redirect URI**: 
     - PowerShell: Web → `http://localhost/login`
     - Python: Leave blank (or add platform later)
4. Click "Register"
5. Copy the **Application (client) ID**
6. Go to "API permissions" → "Add a permission" → "Microsoft Graph" → "Delegated permissions"
7. Add these permissions:
   - `Files.Read` (or `Files.ReadWrite` to delete after sync)
   - `offline_access`
8. **IMPORTANT for Python**: Go to "Authentication" → Scroll to "Advanced settings"
   - Set "Allow public client flows" to **YES**
   - Click Save
9. Click "Grant admin consent" (if required)

### 3. Configure

#### Python
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your client_id and paths
```

#### PowerShell
```powershell
cd powershell
cp config.ps1.example config.ps1
# Edit config.ps1 with your settings
```

### 4. Initial Authentication

#### Python
```bash
python photosync.py --initial-auth
```

#### PowerShell
```powershell
.\photosync.ps1
```

Follow the prompts to authenticate each profile.

### 5. Run Sync

#### Python
```bash
python photosync.py
```

#### PowerShell
```powershell
.\photosync.ps1
```

## Docker Setup (Python only)

```bash
# Build
docker-compose build

# Initial auth (interactive)
docker-compose run --rm photosync python photosync.py --initial-auth

# Run sync
docker-compose run --rm photosync

# Schedule with cron
0 2 * * * cd /path/to/od-photosync && docker-compose run --rm photosync
```

## Troubleshooting

### Authentication Failed
- Verify your client_id is correct
- Check API permissions are granted
- Try `--initial-auth` again

### Module Not Found (Python)
```bash
pip install -r requirements.txt
```

### File Permissions (Docker)
```bash
chmod 700 python/data
```

See implementation-specific documentation:
- Main [README](README.md) for Python implementation
- [PowerShell README](powershell/README.md) for PowerShell implementation
