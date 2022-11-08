# od-photosync
Sync onedrive camera folder to local NAS

# Config

File named Config.ps1 must exists in the same folder
```
#AzureAD app config
$redirectUri = "http://localhost/login"
$appid = "guid-of-app"
$secret = 'app-secret'

# Refresh token will be peristed to PhotoSync subfolder
$PersistFolder = $env:OneDrive

$script:PhotoSyncProfiles = @(
    @{
        "Name" = "Mikko"
        "RemoveDownloaded" = $true
        "DestinationFolder" = "Z:\media\Kuvat"
    }
    @{
       "Name" = "Jenni"
       "RemoveDownloaded" = $true        
       "DestinationFolder" = "Z:\media\Kuvat"
    }
)
```
