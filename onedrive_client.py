import requests
from pathlib import Path
from datetime import datetime
from logger import get_logger
import hashlib

class OneDriveClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.logger = get_logger()
        
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def get_camera_roll_items(self):
        """Get all items from camera roll folder"""
        endpoint = f"{self.base_url}/me/drive/special/cameraroll/children"
        all_items = []
        
        while endpoint:
            try:
                response = requests.get(endpoint, headers=self.headers)
                response.raise_for_status()
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
            
            # Stream download to handle large files
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
            response = requests.delete(endpoint, headers=self.headers)
            response.raise_for_status()
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
