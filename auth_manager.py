import json
import msal
from pathlib import Path
from datetime import datetime, timedelta
from logger import get_logger

class AuthManager:
    def __init__(self, client_id, profile_name, data_dir="./data", auth_timeout=300):
        self.client_id = client_id
        self.profile_name = profile_name
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.auth_timeout = auth_timeout  # Timeout in seconds for device code flow
        
        self.token_file = self.data_dir / f"auth_{profile_name}.json"
        # Note: offline_access is automatically added by MSAL, don't include it manually
        # Use Files.ReadWrite if you want to delete files from OneDrive after syncing
        self.scopes = ["https://graph.microsoft.com/Files.ReadWrite"]
        self.logger = get_logger()
        
        # MSAL Public Client App (no client secret for personal accounts)
        # Use /consumers for personal Microsoft accounts, /common for work+personal, /organizations for work only
        self.app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority="https://login.microsoftonline.com/consumers"
        )
    
    def get_access_token(self, force_device_code=False, force_refresh=False):
        """Get valid access token, refreshing if needed"""
        
        # Try to load existing token
        if self.token_file.exists() and not force_device_code:
            self.logger.info(f"Loading existing token for profile [{self.profile_name}]")
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            # If not forcing a refresh, check if token is still valid
            if not force_refresh:
                expires_at = datetime.fromisoformat(token_data['expires_at'])
                if expires_at > datetime.now() + timedelta(minutes=5):
                    self.logger.info("Reusing cached access token")
                    return token_data['access_token']
            
            # Try to refresh using refresh token
            if 'refresh_token' in token_data:
                self.logger.info("Access token expired or refresh forced, refreshing...")
                result = self._refresh_token(token_data['refresh_token'])
                if result:
                    return result['access_token']
                else:
                    self.logger.warning("Refresh token invalid, need to re-authenticate")
        
        # No valid token, need to authenticate
        self.logger.info("No valid token found, starting device code flow...")
        result = self._device_code_flow()
        
        if result:
            return result['access_token']
        
        return None
    
    def _device_code_flow(self):
        """Authenticate using device code flow with timeout"""
        import time
        import threading
        
        try:
            flow = self.app.initiate_device_flow(scopes=self.scopes)
        except Exception as e:
            self.logger.error(f"Failed to initiate device flow: {e}")
            return None
        
        if "user_code" not in flow:
            self.logger.error(f"Failed to create device flow. Response: {flow}")
            return None
        
        self.logger.info("=" * 50)
        self.logger.info(f"AUTHENTICATION REQUIRED FOR: {self.profile_name}")
        self.logger.info(f"Timeout: {self.auth_timeout} seconds ({self.auth_timeout // 60} minutes)")
        self.logger.info("=" * 50)
        self.logger.info(flow["message"])
        self.logger.info("=" * 50)
        
        # Wait for user to authenticate with timeout
        result_container = [None]
        
        def acquire_token():
            result_container[0] = self.app.acquire_token_by_device_flow(flow)
        
        auth_thread = threading.Thread(target=acquire_token)
        auth_thread.daemon = True
        auth_thread.start()
        auth_thread.join(timeout=self.auth_timeout)
        
        if auth_thread.is_alive():
            # Timeout expired
            self.logger.warning(f"Authentication timeout ({self.auth_timeout}s) expired for [{self.profile_name}], skipping profile")
            return None
        
        result = result_container[0]
        if result and "access_token" in result:
            self.logger.info(f"Authentication successful for [{self.profile_name}]!")
            self._save_token(result)
            return result
        else:
            error_msg = result.get('error_description', 'Unknown error') if result else 'No response'
            self.logger.error(f"Authentication failed: {error_msg}")
            return None
    
    def _refresh_token(self, refresh_token):
        """Refresh access token using refresh token"""
        result = self.app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=self.scopes
        )
        
        if "access_token" in result:
            self.logger.info("Token refreshed successfully")
            self._save_token(result)
            return result
        else:
            self.logger.error(f"Token refresh failed: {result.get('error_description', 'Unknown error')}")
            return None
    
    def _save_token(self, token_result):
        """Save token to file"""
        token_data = {
            'access_token': token_result['access_token'],
            'refresh_token': token_result.get('refresh_token'),
            'expires_at': (datetime.now() + timedelta(seconds=token_result['expires_in'])).isoformat()
        }
        
        with open(self.token_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        self.logger.info(f"Token saved to {self.token_file}")
    
    def logout(self):
        """Remove cached tokens"""
        if self.token_file.exists():
            self.token_file.unlink()
            self.logger.info(f"Removed token file for profile [{self.profile_name}]")
