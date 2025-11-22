#!/usr/bin/env python3
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from auth_manager import AuthManager
from onedrive_client import OneDriveClient
from logger import get_logger
import os

class PhotoSync:
    def __init__(self, config_path="config.yaml"):
        self.logger = get_logger()
        self.config = self._load_config(config_path)
        
        # Set data directory
        self.data_dir = Path(os.getenv('DATA_DIR', self.config.get('data_dir', './data')))
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def sync_profile(self, profile):
        """Sync photos for a single profile"""
        profile_name = profile['name']
        dest_folder = Path(profile['destination_folder'])
        remove_downloaded = profile.get('remove_downloaded', False)
        
        self.logger.info("=" * 50)
        self.logger.info(f"Processing profile: {profile_name}")
        
        # Authenticate
        auth_manager = AuthManager(
            client_id=self.config['client_id'],
            profile_name=profile_name,
            data_dir=self.data_dir
        )
        
        access_token = auth_manager.get_access_token()
        if not access_token:
            self.logger.error(f"Authentication failed for profile [{profile_name}], skipping...")
            return
        
        # Get OneDrive items
        od_client = OneDriveClient(access_token)
        items = od_client.get_camera_roll_items()
        
        # Process each item
        synced_count = 0
        skipped_count = 0
        error_count = 0
        deleted_count = 0
        
        for item in items:
            filename = item['name']
            item_id = item['id']
            self.logger.info(f"Processing [{filename}]")
            
            # Skip if not a file
            if 'file' not in item:
                self.logger.debug(f"Skipping [{filename}] - not a file")
                continue
            
            # Get taken date/time
            taken_datetime = self._get_taken_datetime(item)
            if not taken_datetime:
                self.logger.warning(f"No date/time info for [{filename}], skipping...")
                skipped_count += 1
                continue
            
            # Construct storage path: <dest>/2015/2015_01_15/filename.jpg
            storage_path = dest_folder / taken_datetime.strftime('%Y') / taken_datetime.strftime('%Y_%m_%d') / filename
            
            # Check if file already exists
            if storage_path.exists():
                if od_client.verify_file(storage_path, item):
                    self.logger.info(f"File [{filename}] already exists and is valid")
                    
                    # Delete from OneDrive if configured
                    if remove_downloaded:
                        if od_client.delete_item(item_id):
                            deleted_count += 1
                    
                    skipped_count += 1
                    continue
                else:
                    self.logger.warning(f"File [{filename}] exists but invalid, re-downloading...")
                    storage_path.unlink()
            
            # Download file
            if od_client.download_file(item, storage_path):
                # Verify download
                if od_client.verify_file(storage_path, item):
                    self.logger.info(f"Successfully synced [{filename}]")
                    synced_count += 1
                    
                    # Delete from OneDrive if configured
                    if remove_downloaded:
                        if od_client.delete_item(item_id):
                            deleted_count += 1
                else:
                    self.logger.error(f"Download verification failed for [{filename}]")
                    storage_path.unlink()
                    error_count += 1
            else:
                error_count += 1
        
        self.logger.info("=" * 50)
        self.logger.info(f"Profile [{profile_name}] complete:")
        self.logger.info(f"  Synced: {synced_count}")
        self.logger.info(f"  Skipped: {skipped_count}")
        self.logger.info(f"  Errors: {error_count}")
        if remove_downloaded:
            self.logger.info(f"  Deleted from OneDrive: {deleted_count}")
        self.logger.info("=" * 50)
    
    def _get_taken_datetime(self, item):
        """Extract taken datetime from item metadata"""
        # Try photo.takenDateTime first
        if 'photo' in item and item['photo'] and 'takenDateTime' in item['photo']:
            dt_str = item['photo']['takenDateTime']
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        
        # Try video metadata (sometimes in photo.takenDateTime for videos too)
        if 'video' in item and item['video']:
            # Videos might not have takenDateTime in the same place
            pass
        
        # Fallback to file created/modified time
        if 'createdDateTime' in item:
            dt_str = item['createdDateTime']
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        
        if 'lastModifiedDateTime' in item:
            dt_str = item['lastModifiedDateTime']
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        
        return None
    
    def run(self, initial_auth=False):
        """Run sync for all profiles"""
        self.logger.info("*" * 50)
        self.logger.info("PhotoSync Starting...")
        self.logger.info("*" * 50)
        
        for profile in self.config['profiles']:
            try:
                if initial_auth:
                    # Force device code flow for initial setup
                    auth_manager = AuthManager(
                        client_id=self.config['client_id'],
                        profile_name=profile['name'],
                        data_dir=self.data_dir
                    )
                    auth_manager.get_access_token(force_device_code=True)
                else:
                    self.sync_profile(profile)
            except Exception as e:
                self.logger.error(f"Error processing profile [{profile['name']}]: {e}", exc_info=True)
        
        self.logger.info("*" * 50)
        self.logger.info("PhotoSync Done")
        self.logger.info("*" * 50)
    
    def logout(self):
        """Logout all profiles"""
        self.logger.info("Logging out all profiles...")
        for profile in self.config['profiles']:
            auth_manager = AuthManager(
                client_id=self.config['client_id'],
                profile_name=profile['name'],
                data_dir=self.data_dir
            )
            auth_manager.logout()

def main():
    parser = argparse.ArgumentParser(description='Sync photos from OneDrive to local storage')
    parser.add_argument('--logout', action='store_true', help='Remove all cached tokens')
    parser.add_argument('--initial-auth', action='store_true', help='Run initial authentication only')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    
    args = parser.parse_args()
    
    sync = PhotoSync(config_path=args.config)
    
    if args.logout:
        sync.logout()
    else:
        sync.run(initial_auth=args.initial_auth)

if __name__ == '__main__':
    main()
