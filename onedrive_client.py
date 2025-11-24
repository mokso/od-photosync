import requests
from pathlib import Path
from datetime import datetime
from logger import get_logger
import hashlib

class OneDriveClient:
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        self.access_token = self.auth_manager.get_access_token()
        if not self.access_token:
            raise Exception("Failed to get initial access token.")
            
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.logger = get_logger()
        
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def _execute_request(self, method, url, retry=True, **kwargs):
        """Wrapper for requests to handle token refresh"""
        # Use custom headers if provided, else default
        headers = kwargs.pop('headers', self.headers)
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and retry:
                self.logger.info("Access token expired or invalid, refreshing...")
                
                # Refresh token
                new_token = self.auth_manager.get_access_token(force_refresh=True)
                if not new_token:
                    self.logger.error("Failed to refresh access token.")
                    raise e # Re-raise original exception
                
                # Update internal state and headers
                self.access_token = new_token
                self.headers['Authorization'] = f'Bearer {self.access_token}'
                
                # Update headers for the retried request
                headers['Authorization'] = f'Bearer {self.access_token}'
                
                self.logger.info("Retrying request with new token...")
                # Retry the request once more without the retry flag
                return self._execute_request(method, url, retry=False, headers=headers, **kwargs)
            
            # Re-raise for other HTTP errors or if retry is false
            raise e

    def get_camera_roll_items(self):
        """Get all items from camera roll folder"""
        endpoint = f"{self.base_url}/me/drive/special/cameraroll/children"
        all_items = []
        
        while endpoint:
            try:
                response = self._execute_request('GET', endpoint)
                data = response.json()
                
                items = data.get('value', [])
                all_items.extend(items)
                
                # Handle pagination
                endpoint = data.get('@odata.nextLink')
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching camera roll items: {e}")
                break
        
        self.logger.info(f"Found {len(all_items)} items in camera roll")
        return all_items
    
    def download_file(self, item, destination_path):
        """Download file from OneDrive"""
        download_url = item.get('@microsoft.graph.downloadUrl')
        
        if not download_url:
            self.logger.error(f"No download URL for {item['name']}")
            return False
        
        try:
            self.logger.info(f"Downloading {item['name']} to {destination_path}")
            
            # Download does not need auth headers, so we don't use the wrapper
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            destination_path = Path(destination_path)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(destination_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error downloading {item['name']}: {e}")
            return False
    
    def delete_item(self, item_id):
        """Delete item from OneDrive by ID"""
        try:
            endpoint = f"{self.base_url}/me/drive/items/{item_id}"
            self._execute_request('DELETE', endpoint)
            self.logger.info(f"Deleted item {item_id} from OneDrive")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error deleting item {item_id}: {e}")
            return False
    
    @staticmethod
    def get_file_hash(file_path):
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def verify_file(self, local_path, onedrive_item):
        """Verify downloaded file matches OneDrive file"""
        local_path = Path(local_path)
        
        if not local_path.exists():
            return False
        
        # Check file size
        local_size = local_path.stat().st_size
        remote_size = onedrive_item.get('size', 0)
        
        if local_size != remote_size:
            self.logger.warning(f"Size mismatch: local={local_size}, remote={remote_size}")
            return False
        
        # Could also compare hashes if needed
        # OneDrive provides 'file.hashes.sha256Hash' or 'file.hashes.quickXorHash'
        
        return True
    
    def get_items_in_folder(self, folder_path):
        """Get all items in a specific folder path"""
        # Handle root path
        if folder_path == "/" or not folder_path:
            endpoint = f"{self.base_url}/me/drive/root/children"
        else:
            # Remove leading/trailing slashes
            folder_path = folder_path.strip('/')
            endpoint = f"{self.base_url}/me/drive/root:/{folder_path}:/children"
        
        all_items = []
        
        while endpoint:
            try:
                response = self._execute_request('GET', endpoint)
                data = response.json()
                
                items = data.get('value', [])
                all_items.extend(items)
                
                # Handle pagination
                endpoint = data.get('@odata.nextLink')
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching items from {folder_path}: {e}")
                break
        
        self.logger.info(f"Found {len(all_items)} items in {folder_path}")
        return all_items
    
    def upload_file(self, local_path, onedrive_path):
        """Upload file to OneDrive
        
        Args:
            local_path: Path to local file
            onedrive_path: Destination path in OneDrive (e.g., '/Backup/Photos/photo.jpg')
        """
        local_path = Path(local_path)
        
        if not local_path.exists():
            self.logger.error(f"Local file does not exist: {local_path}")
            return False
        
        file_size = local_path.stat().st_size
        
        # For files larger than 4MB, use upload session (resumable upload)
        if file_size > 4 * 1024 * 1024:
            return self._upload_large_file(local_path, onedrive_path)
        else:
            return self._upload_small_file(local_path, onedrive_path)
    
    def _upload_small_file(self, local_path, onedrive_path):
        """Upload small file (< 4MB) in single request"""
        try:
            # Remove leading slash and construct endpoint
            onedrive_path = onedrive_path.lstrip('/')
            endpoint = f"{self.base_url}/me/drive/root:/{onedrive_path}:/content"
            
            with open(local_path, 'rb') as f:
                file_content = f.read()
            
            # Use a specific header for this request, not the default json one
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/octet-stream'
            }
            
            self._execute_request('PUT', endpoint, headers=headers, data=file_content)
            
            self.logger.info(f"Successfully uploaded {local_path.name} to {onedrive_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error uploading {local_path.name}: {e}")
            return False
    
    def _upload_large_file(self, local_path, onedrive_path):
        """Upload large file (>= 4MB) using resumable upload session"""
        try:
            # Create upload session
            onedrive_path = onedrive_path.lstrip('/')
            endpoint = f"{self.base_url}/me/drive/root:/{onedrive_path}:/createUploadSession"
            
            response = self._execute_request('POST', endpoint)
            upload_url = response.json()['uploadUrl']
            
            # Upload in chunks
            chunk_size = 10 * 1024 * 1024  # 10MB chunks
            file_size = local_path.stat().st_size
            
            with open(local_path, 'rb') as f:
                chunk_start = 0
                while chunk_start < file_size:
                    chunk_end = min(chunk_start + chunk_size, file_size)
                    chunk_data = f.read(chunk_size)
                    
                    headers = {
                        'Content-Length': str(len(chunk_data)),
                        'Content-Range': f'bytes {chunk_start}-{chunk_end-1}/{file_size}'
                    }
                    
                    # This request does not need auth headers
                    response = requests.put(upload_url, headers=headers, data=chunk_data)
                    response.raise_for_status()
                    
                    chunk_start = chunk_end
                    self.logger.debug(f"Uploaded {chunk_end}/{file_size} bytes of {local_path.name}")
            
            self.logger.info(f"Successfully uploaded {local_path.name} to {onedrive_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error uploading large file {local_path.name}: {e}")
            return False
    
    def create_folder(self, folder_path):
        """Create a folder in OneDrive if it doesn't exist
        
        Args:
            folder_path: Path to folder (e.g., '/Backup/Photos')
        
        Returns:
            True if folder exists or was created successfully
        """
        folder_path = folder_path.strip('/')
        
        # Check if folder exists
        try:
            endpoint = f"{self.base_url}/me/drive/root:/{folder_path}"
            response = self._execute_request('GET', endpoint, retry=False) # Don't retry on 404
            
            if response.status_code == 200:
                # Folder exists
                return True
        except requests.exceptions.HTTPError as e:
            # If we get a 404, that's fine, we'll create it.
            if e.response.status_code != 404:
                self.logger.error(f"Error checking folder {folder_path}: {e}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error checking folder {folder_path}: {e}")
            return False

        # Create folder hierarchy
        parts = folder_path.split('/')
        current_path = ""
        
        for part in parts:
            parent_path = current_path if current_path else "root"
            current_path = f"{current_path}/{part}" if current_path else part
            
            try:
                # Try to get the folder first
                endpoint = f"{self.base_url}/me/drive/root:/{current_path}"
                response = self._execute_request('GET', endpoint, retry=False)
                
                if response.status_code == 200:
                    continue  # Folder exists
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 404:
                    self.logger.error(f"Error checking sub-folder {current_path}: {e}")
                    return False
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error checking sub-folder {current_path}: {e}")
                return False

            # Create the folder
            try:
                if parent_path == "root":
                    endpoint = f"{self.base_url}/me/drive/root/children"
                else:
                    endpoint = f"{self.base_url}/me/drive/root:/{parent_path}:/children"
                
                data = {
                    "name": part,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "rename"
                }
                
                self._execute_request('POST', endpoint, json=data)
                self.logger.info(f"Created folder: {current_path}")
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error creating folder {current_path}: {e}")
                return False
        
        return True

    def get_all_items_delta(self, folder_path):
        """Get all items in a folder path using delta query for efficiency."""
        folder_path = folder_path.strip('/')
        
        # For delta query, it's most efficient to start from the root.
        # We will filter by path later.
        endpoint = f"{self.base_url}/me/drive/root/delta"

        all_items = []
        self.logger.info(f"Starting delta scan for drive. This may take a while...")
        
        page_count = 0
        while endpoint:
            try:
                page_count += 1
                self.logger.info(f"Fetching delta page {page_count}...")
                response = self._execute_request('GET', endpoint)
                data = response.json()
                
                items = data.get('value', [])
                all_items.extend(items)
                self.logger.info(f"Delta scan progress: fetched {len(all_items)} total items so far.")
                
                # Check for nextLink for pagination, or deltaLink for completion
                if '@odata.deltaLink' in data:
                    self.logger.info("Delta scan complete.")
                    endpoint = None # End of scan
                else:
                    endpoint = data.get('@odata.nextLink')
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error during delta query: {e}")
                break
            
        return all_items
