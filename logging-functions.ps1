function WriteLog {
    Param(
      [String] $Msg,
      [String] $Level = "Info",
      [String] $LogFolder = "$PSScriptRoot\Logs"
    )
  
    if (-not (Test-Path $LogFolder)) {
      New-Item $LogFolder -ItemType Directory
    }
    $today = Get-Date -Format "yyyy-MM-dd"
    $LogFile = Join-Path $LogFolder "Photosync-$today.log"
  
    $logRow = "$(Get-Date -Format "HH:mm:ss") : $Level : $msg"
    $logRow | Out-File $LogFile -Append
    Write-Host $logRow
  }