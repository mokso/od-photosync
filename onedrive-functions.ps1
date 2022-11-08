$RootUrl = "https://api.onedrive.com/v1.0"

function GetODAuthentication
{
	<#
	.DESCRIPTION
	Authenticate to MS Identity with code flow
	https://learn.microsoft.com/en-us/onedrive/developer/rest-api/getting-started/msa-oauth?view=odsp-graph-online
	
#>
	PARAM(
		#AzureAD app id
		[Parameter(Mandatory=$True)]
		[string]$ClientId,
		#Profilename
		[string]$ProfileName,
		#AzureAD app secret
		[string]$AppKey="",
		#Refresh token
		[string]$RefreshToken="",
		[string]$Scope = "onedrive.readwrite,offline_access",
		[string]$RedirectURI ="https://login.live.com/oauth20_desktop.srf",
		[switch]$DontShowLoginScreen=$false,
		[switch]$AutoAccept,
		[switch]$LogOut
	)
	$Authentication=""

	$Type="code"

	if ($RefreshToken) {
		Write-Verbose "A refresh token is given. Try to get access token with it"
		$url = "https://login.live.com/oauth20_token.srf"
		$method = "Post"
		#$body="client_id=$ClientId&redirect_URI=$RedirectURI&client_secret=$([uri]::EscapeDataString($AppKey))&refresh_token="+$RefreshToken+"&grant_type=refresh_token"
		$body = @{
			"client_id"=$ClientId
			"redirect_URI"=$RedirectURI
			"client_secret"=[uri]::EscapeDataString($AppKey)
			"refresh_token"=$RefreshToken
			"grant_type"="refresh_token"
		}

		Write-Verbose "Invoking $method [$url] with body`n$($body | ConvertTo-Json)"
		$Authentication = Invoke-RestMethod -Method post -Uri $url -ContentType "application/x-www-form-urlencoded" -Body $Body 
		Write-Verbose "Response:`n$($Authentication | ConvertTo-Json)"
	} 
	else {
		Write-Verbose "Authentication mode: [$Type]"
		[Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | out-null
		[Reflection.Assembly]::LoadWithPartialName("System.Drawing") | out-null
		[Reflection.Assembly]::LoadWithPartialName("System.Web") | out-null

		if ($Logout) {
			$URIGetAccessToken="https://login.live.com/logout.srf?client_id=$ClientId&redirect_uri=$RedirectURI"
		}
		else {
			$URIGetAccessToken="https://login.live.com/oauth20_authorize.srf?client_id=$ClientId&scope=$Scope&response_type=code&redirect_URI=$RedirectURI"
		}

		Write-Verbose "URIGetAccessToken  [$URIGetAccessToken]"

		#craft browser window
		$form = New-Object Windows.Forms.Form
		$form.text = "Authenticate to OneDrive ($ProfileName)"
		$form.size = New-Object Drawing.size @(700,600)
		$form.Width = 675
		$form.Height = 750
		$web=New-object System.Windows.Forms.WebBrowser
		$web.IsWebBrowserContextMenuEnabled = $true
		$web.Width = 600
		$web.Height = 700
		$web.Location = "25, 25"
		$web.navigate($URIGetAccessToken)

		#do this when Add_DocumentCompleted happens 
		$DocComplete  = {
			Write-Verbose "Doc completed"
			Write-Verbose "Url: [$($web.Url.AbsoluteUri)]"
			if ($web.Url.AbsoluteUri -match "access_token=|error|code=|logout") {
				$form.Close() 
			}
			if ($web.DocumentText -like '*ucaccept*') {
				Write-Verbose "Looks like there is some consents to give"
			}
		}

		#add code to Add_DocumentCompleted event
		$web.Add_DocumentCompleted($DocComplete)

		$form.Controls.Add($web)
		$form.showdialog() | out-null

		
		if ($LogOut) {
			return "Logged out, kkthxbye"
		}

		
		# Build object from last URI (which should contains the token)
		$ReturnURI=($web.Url).ToString().Replace("#","&")
		Write-Verbose "Start searching ReturnUri [$ReturnURI] for code..."
		#Add stuff from return uri queryparams to auth object, we should have code=xyzxzy in there
		$code = $null
		ForEach ($element in $ReturnURI.Split("?")[1].Split("&")) {
			if ($element.split("=")[0] -eq "code") {
				$code = $element.split("=")[1]
				Write-Verbose "Found code from url parameters! [$code]"
			}
		}

		if ($code) {
			Write-Verbose "Getting token using authentication code"
			$url = "https://login.live.com/oauth20_token.srf"
			$method = "Post"					
			#$body="client_id=$ClientId&redirect_URI=$RedirectURI&client_secret=$([uri]::EscapeDataString($AppKey))&code=$code&grant_type=authorization_code&scope="+$Scope
			$body = @{
				"client_id"=$ClientId
				"redirect_URI"=$RedirectURI
				"client_secret"=[uri]::EscapeDataString($AppKey)
				"code"=$code
				"grant_type"="authorization_code"
				"scope"=$Scope
			}
			Write-Verbose "Invoking $method [$url] with body`n$body"
			$Authentication = Invoke-RestMethod -Method post -Uri $url -ContentType "application/x-www-form-urlencoded" -Body $Body 
			Write-Verbose "Response:`n$($Authentication | ConvertTo-Json)"
		} 
		else {
			write-error("Cannot get authentication code. Error: "+$ReturnURI)
		}
		 
	}

	#Add proper expiration timestamp
	if ($Authentication.PSobject.Properties.name -contains "expires_in")
	{
		$expirationDate = (Get-Date).AddSeconds($Authentication.expires_in)
		$Authentication | add-member Noteproperty "expires" $expirationDate
	} 
	else {
		Write-Warning "No expiration...WTF?"
	}

	return $Authentication 
}



function GetODCameraRollItems {
  Param(
    [string ]$AccessToken = $script:OneDriveAccessToken,
    [string] $ItemProperties = "id,file,name,size,@content.downloadUrl,lastModifiedDateTime,photo,video"
  )

  if (-not $AccessToken) {
	Write-Warning "Missing AccessToken!"
	return
  }

  $headers = @{
    Authorization = "Bearer $AccessToken"
    Accept = "application/json"
  }

  $url = "$RootUrl/drive/special/cameraroll/children/?select=$ItemProperties"
  $response = Invoke-RestMethod -Method Get -Uri $url -Headers $headers
  return $response.value
}

function GetOdItemById {
  Param(
    [string ]$AccessToken = $script:OneDriveAccessToke,
    [Parameter(Mandatory=$True)]
    [string]$ItemId,
    [string] $ItemProperties = "id,name,size,@content.downloadUrl,lastModifiedDateTime,photo"
  )

  if (-not $AccessToken) {
	Write-Warning "Missing AccessToken!"
	return
  }

  $headers = @{
    Authorization = "Bearer $AccessToken"
    Accept = "application/json"
  }
  $url = "$RootUrl/drive/items/$ItemId?select=$ItemProperties"
  $response = Invoke-RestMethod -Method Get -Uri $url -Headers $headers
  return $response
}

function RemoveOdItemById {
	Param(
	  [string ]$AccessToken = $script:OneDriveAccessToken,
	  [Parameter(Mandatory=$True)]
	  [string]$ItemId
	)

	if (-not $AccessToken) {
		Write-Warning "Missing AccessToken!"
		return
	  }
  
	$headers = @{
	  Authorization = "Bearer $AccessToken"
	  Accept = "application/json"
	}
	$url = "$RootUrl/drive/items/$ItemId"
	Write-Verbose "Invoking DELETE $url"
	$response = Invoke-RestMethod -Method Delete -Uri $url -Headers $headers
	return $response
}

<#
.SYNOPSIS
Ensure OneDrive item is synced to local NAS

.DESCRIPTION
Ensure OneDrive item is synced to local NAS. Return $true if already exists, $false if need to be downloaded

.PARAMETER TargetPath
Parameter description

.PARAMETER OneDriveItem
Parameter description

.PARAMETER RemoveIfExists
Parameter description

.EXAMPLE
An example

.NOTES
General notes
#>
function EnsureFileSynced {
	Param(
		[string] $TargetPath,
		[object] $OneDriveItem,
		[bool] $RemoveIfExists = $true
	)

	if (-not (Test-Path $TargetPath)) {
		return $false
	}

	Write-Verbose "File [$TargetPath] exists"

	$existingFile = Get-ChildItem $TargetPath

	if ($existingFile.Length -eq $OneDriveItem.size) {
		Write-Verbose "Size match, must be same file"
		if ($RemoveIfExists) {
			RemoveOdItemById -ItemId $OneDriveItem.id
		}
	}
	else {
		WriteLog -Level "Warning" -Msg "File exists but size not matching!"
		WriteLog -Level "Warning" -Msg  "OneDrive: $($OneDriveItem.size)"
		WriteLog -Level "Warning" -Msg "LocalNAS: $($existingFile.Length)"
	}
	return $true
}


