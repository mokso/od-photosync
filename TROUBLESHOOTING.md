# Troubleshooting Guide

## Common Authentication Errors

### Error: "Application is configured for use by Microsoft Account users only"
```
Please use the /consumers endpoint to serve this request
```

**Fixed in code** - The auth_manager now uses `/consumers` endpoint automatically.

### Error: "The client application must be marked as 'mobile'"
```
AADSTS70002: The provided client is not supported for this feature
```

**Solution**: Enable public client flows in Azure Portal

1. Go to [Azure Portal - App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Select your app
3. Click **Authentication** in the left menu
4. Scroll to **Advanced settings**
5. Set **"Allow public client flows"** to **YES**
6. Click **Save**

### Error: "You cannot use any scope value that is reserved"
```
ValueError: Your input: ['offline_access', 'Files.Read']
```

**Fixed in code** - MSAL automatically adds `offline_access`, we now use the full scope URL: `https://graph.microsoft.com/Files.Read`

### Error: "No valid token found"

**Solution**: Run initial authentication
```bash
python photosync.py --initial-auth
```

### Error: "Token refresh failed"

**Cause**: Refresh tokens expire after 90 days of inactivity

**Solution**: Re-authenticate
```bash
python photosync.py --logout
python photosync.py --initial-auth
```

## Common Runtime Errors

### ModuleNotFoundError: No module named 'msal'

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### FileNotFoundError: config.yaml

**Solution**: Create config file
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

### Permission Denied: /photos/

**Cause**: Container doesn't have write access to mounted volume

**Solution**: Check volume permissions
```bash
chmod -R 755 /mnt/nas/photos
# Or adjust user in Dockerfile
```

## Debugging

### Enable verbose logging

Edit `logger.py` and change console handler level:
```python
console_handler.setLevel(logging.DEBUG)  # Changed from INFO
```

### Check logs

```bash
tail -f data/logs/photosync_*.log
```

### Test authentication manually

```python
from auth_manager import AuthManager

auth = AuthManager(
    client_id="your-client-id",
    profile_name="test",
    data_dir="./data"
)

token = auth.get_access_token(force_device_code=True)
print("Token:", token[:50] if token else None)
```

### Verify OneDrive connection

```python
from onedrive_client import OneDriveClient

client = OneDriveClient(access_token="your-token")
items = client.get_camera_roll_items()
print(f"Found {len(items)} items")
```

## Azure Configuration Checklist

- [ ] App registration created
- [ ] Client ID copied to config.yaml
- [ ] Supported account types: "Personal Microsoft accounts only"
- [ ] API permissions added: Files.Read, offline_access
- [ ] **Allow public client flows: YES** ← Most common issue!
- [ ] Admin consent granted (if required)

## Docker-Specific Issues

### Container exits immediately

Check logs:
```bash
docker-compose logs photosync
```

### Can't write to /photos

Update docker-compose.yml volumes to match your NAS path:
```yaml
volumes:
  - /actual/path/to/nas:/photos
```

### Timezone incorrect

Set in docker-compose.yml:
```yaml
environment:
  - TZ=Your/Timezone  # e.g., Europe/Oslo, America/New_York
```

## Getting Help

If you're still having issues:

1. Check the logs in `data/logs/`
2. Verify Azure app configuration
3. Test with a single profile first
4. Check file permissions
5. Ensure network connectivity to Microsoft Graph API

## Advanced: Test Graph API directly

```bash
# Get device code
curl -X POST https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode \
  -d "client_id=YOUR_CLIENT_ID&scope=https://graph.microsoft.com/Files.Read"

# Authenticate at the URL provided, then get token
curl -X POST https://login.microsoftonline.com/consumers/oauth2/v2.0/token \
  -d "grant_type=urn:ietf:params:oauth:grant-type:device_code&client_id=YOUR_CLIENT_ID&device_code=YOUR_DEVICE_CODE"

# Test API
curl https://graph.microsoft.com/v1.0/me/drive/special/cameraroll/children \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```
