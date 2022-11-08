[CmdletBinding()]
Param(
  [Switch] $LogOut
)
#dotsource functions and configuration
. .\onedrive-functions.ps1
. .\config.ps1


function RunSync {  
  # Get files on OneDrive cameraroll folder
  $cameraRollFiles = GetODCameraRollItems 
  
  
  foreach ($f in $cameraRollFiles) {
    $filename = $f.name
    $fileid = $f.id
    Write-host "Processing [$filename]"
  
    $takenDateTime = if ($f.photo.takenDateTime) {
      #photos has this
      $f.photo.takenDateTime
    } elseif ($f.photo.alternateTakenDateTime) {
      #vides has this 
      $f.photo.alternateTakenDateTime
    }
  
    if (-not $takenDateTime) {
      Write-host "Not photo or video? $filename [$fileid], skipping..."
      continue
    }
  
    # construct folder structure <root>/2015/2015_01_15/2015_01_15_22_54_23.jpg
    $storeagePath = Join-path $DestFolder (Join-path $takenDateTime.ToString('yyyy') $takenDateTime.ToString('yyyy_MM_dd')) 
    $storageFullPath = Join-path $storeagePath $filename
  
    #check if target file already exists
    $exists = EnsureFileSynced -TargetPath $storageFullPath -OneDriveItem $f -RemoveIfExists $true
    if ($exists) {
      Write-host "File [$filename] already exists locally, processing next one..."
      continue
    }
  
    # ensure target folder exists
    if (-not (Test-Path $storeagePath)) {
      Write-host "Creating directory [$storeagePath]"
      New-Item $storeagePath -ItemType Directory
    }
  
    $sourceUrl = $f.'@content.downloadUrl'
    Write-host "Start download file $($f.name) to [$storageFullPath]  from [$sourceUrl]"
    Start-BitsTransfer -Source $sourceUrl -Destination $storageFullPath
  
    # Ensure download succesful
    $exists = EnsureFileSynced -TargetPath $storageFullPath -OneDriveItem $f -RemoveIfExists $true
    if (-not $exists) {
      Write-Warning "Something went wrong with $filname"
    }
  }
}

function Authenticate {
  Param (
    $AuthFile,
    $ProfileName
  )


  if (Test-path $AuthFile) {
    Write-host "Getting auth from file $SAuthfile"
    $OldAuth = Import-Clixml -Path $AuthFile
    if (-not $OldAuth.refresh_token) {
      Write-Warning "no refresh token...WTF?"
      return
    }
    if ($OldAuth.expires -lt (Get-Date).AddMinutes(-5)) {
      Write-host "Getting new access token"
      $Auth = GetODAuthentication -ClientID $appid -AppKey $secret -RedirectURI $redirectUri -RefreshToken $OldAuth.refresh_token
    }
    else {
      Write-host "reusing persisted access-token"
      $Auth = $OldAuth
    }
  } 
  else {

    Write-host "No persisted token, authenticating to graph api"
    $Auth = GetODAuthentication -ClientID $appid -AppKey $secret -RedirectURI $redirectUri -ProfileName $ProfileName
  }
  
  if ($Auth.access_token) {
    Write-host "Saving to $AuthFile"
    $Auth | Export-Clixml -Path $AuthFile
    $script:OnedriveAccessToken = $Auth.access_token
    return $true
  }
    
  $OnedriveAccessToken = $null
  return $false
  

}

if ($LogOut) {
  Write-host "Logging out..."
  GetODAuthentication -ClientID $appid -LogOut
  return
}

foreach ($p in $PhotoSyncProfiles) {
  write-host "profile: `n$($p | ConvertTo-Json)"
  $dataFolder = Join-Path $PersistFolder "PhotoSync"
  #ensure folder exists 
  if (-not (Test-Path $dataFolder)){
    New-Item $dataFolder -ItemType Directory
  }
  $authFileName = "Auth_$($p.Name).xml"
  $AuthFile = Join-Path $dataFolder $authFileName

  if (Authenticate -AuthFile $AuthFile -ProfileName $p.Name) {
    #GetODCameraRollItems
    Write-host "Running sync for profile [$($p.Name)]"
    RunSync
  }
}




