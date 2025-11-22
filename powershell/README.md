# PowerShell Version

Original PowerShell implementation of OneDrive photo sync.

> **Note:** The main Python implementation is now in the root directory. This PowerShell version left beacuse of historical purposes...

## Requirements

- PowerShell 5.1+ (Windows) or PowerShell Core 7+ (Cross-platform)
- Azure App registration with client secret
- OneDrive API v1.0 access

## Azure AD App Registration

The PowerShell version uses a different authentication flow than the Python version:

1. Go to [Azure Portal](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Use an existing app or create new registration:
   - Name: "OneDrive Photo Sync"
   - Supported account types: "Personal Microsoft accounts only"
   - Redirect URI: Web → `http://localhost/login`
3. Copy the **Application (client) ID**
4. Go to "Certificates & secrets" → "New client secret"
   - Create and copy the secret value
5. Under "API permissions", ensure you have:
   - OneDrive API → Delegated → `onedrive.readwrite`
   - OneDrive API → Delegated → `offline_access`

## Configuration

1. Copy the example config:
```powershell
cp config.ps1.example config.ps1
```

2. Edit `config.ps1`:

```powershell
# AzureAD app config
$redirectUri = "http://localhost/login"
$appid = "your-client-id-here"
$secret = 'your-client-secret-here'

# Refresh token will be persisted to Auth subfolder
$PersistFolder = "$PSScriptRoot\Auth"
$DestFolder = "Z:\media\Photos"  # Your NAS path

$script:PhotoSyncProfiles = @(
    @{
        "Name" = "Profile1"
        "RemoveDownloaded" = $true
    },
    @{
        "Name" = "Profile2"
        "RemoveDownloaded" = $true
    }
)
```

**Note:** The destination folder is shared across all profiles in the PowerShell version. Each profile creates a subfolder automatically.

## Usage

### Initial Setup
```powershell
# First run will open a browser for authentication
.\photosync.ps1
```

On first run, a browser window will open for each profile. Sign in with the Microsoft account you want to sync.

### Regular Sync
```powershell
# Run sync for all profiles
.\photosync.ps1
```

### Logout
```powershell
# Clear all cached tokens
.\photosync.ps1 -LogOut
```

## Features

- Multi-profile support (sync multiple OneDrive accounts)
- Interactive authentication with browser window
- Automatic token refresh
- Optional deletion of synced files from OneDrive
- Date-based folder organization (YYYY/YYYY_MM_DD/)

## Files

- `photosync.ps1` - Main script
- `onedrive-functions.ps1` - OneDrive API functions (auth, download, delete)
- `logging-functions.ps1` - Logging utilities
- `config.ps1` - Configuration (not in repo, copy from example)
- `config.ps1.example` - Configuration template
- `Auth/` - Authentication tokens (created at runtime)
- `Logs/` - Application logs (created at runtime)

## Troubleshooting

### Authentication Window Not Opening
- Ensure you're running in an interactive session (not as a scheduled task)
- Check that the redirect URI matches: `http://localhost/login`

### Token Refresh Failed
- Delete files in `Auth/` directory
- Run `.\photosync.ps1` again to re-authenticate

### BitsTransfer Not Available
- On Linux/Mac, the script will use `Invoke-WebRequest` instead
- BitsTransfer is Windows-only

### Client Secret Expired
- Generate a new client secret in Azure Portal
- Update `config.ps1` with the new secret

## Scheduling

### Windows Task Scheduler
```powershell
# Create a scheduled task
$action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument '-File "C:\path\to\photosync.ps1"'
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "OneDrive Photo Sync"
```