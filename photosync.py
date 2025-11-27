#!/usr/bin/env python3
import argparse
import yaml
import json
import time
import signal
import sys
import schedule
import requests
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
        self.running = True
        
        # Set data directory
        self.data_dir = Path(os.getenv('DATA_DIR', self.config.get('data_dir', './data')))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Healthchecks.io configuration
        self.healthcheck_url = self.config.get('healthcheck_url')
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info("Shutdown signal received, finishing current operation...")
        self.running = False
    
    def _healthcheck_ping(self, status="", message=None):
        """Send ping to healthchecks.io
        
        Args:
            status: "" (start), "/fail" (failure), or leave empty for success
            message: Optional message to include in ping body
        """
        if not self.healthcheck_url:
            return
        
        try:
            url = f"{self.healthcheck_url.rstrip('/')}{status}"
            if message:
                response = requests.post(url, data=message, timeout=10)
            else:
                response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                self.logger.debug(f"Healthcheck ping sent: {status or 'success'}")
            else:
                self.logger.warning(f"Healthcheck ping failed with status {response.status_code}")
        except Exception as e:
            self.logger.warning(f"Failed to send healthcheck ping: {e}")
    
    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _load_upload_cache(self, profile_name):
        """Load upload cache for a profile"""
        cache_file = self.data_dir / f"upload_cache_{profile_name}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                    # Handle both old format (dict) and new format (with metadata)
                    if isinstance(cache_data, dict) and '_metadata' in cache_data:
                        cache = {k: v for k, v in cache_data.items() if k != '_metadata'}
                        metadata = cache_data['_metadata']
                        self.logger.info(f"Loaded cache with {len(cache)} entries")
                        if 'last_scan_watermark' in metadata:
                            watermark = metadata['last_scan_watermark']
                            watermark_dt = datetime.fromisoformat(watermark)
                            self.logger.info(f"Last scan watermark: {watermark_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        return cache_data
                    else:
                        # Old format - just the cache dict
                        self.logger.info(f"Loaded cache with {len(cache_data)} entries (legacy format)")
                        return {'_metadata': {}, **cache_data}
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}, starting fresh")
                return {'_metadata': {}}
        return {'_metadata': {}}
    
    def _save_upload_cache(self, profile_name, cache):
        """Save upload cache for a profile"""
        cache_file = self.data_dir / f"upload_cache_{profile_name}.json"
        try:
            # Count entries (exclude metadata)
            entry_count = len([k for k in cache.keys() if k != '_metadata'])
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved cache with {entry_count} entries")
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")
    
    def _get_all_onedrive_files(self, od_client, folder_path):
        """Get all files from a OneDrive folder using the efficient delta query."""
        all_items = od_client.get_all_items_delta(folder_path)
        
        if not all_items:
            return {}

        all_files_map = {}
        
        # The folder_path from config is the root for this sync profile.
        # We need to filter the delta results to only include items within this path.
        folder_path = folder_path.strip('/')
        path_prefix = f"/drive/root:/{folder_path}" if folder_path else "/drive/root:"

        for item in all_items:
            # Skip folders and items marked as deleted
            if 'folder' in item or 'deleted' in item:
                continue

            # Skip items without path info in parent reference
            if 'parentReference' not in item or 'path' not in item['parentReference']:
                # This can happen for the root item itself, which we can ignore as it's a folder
                continue

            parent_path_str = item['parentReference']['path']
            
            # Check if the item is within our target folder path
            if parent_path_str == path_prefix or parent_path_str.startswith(path_prefix + '/'):
                # Make the path relative to the sync root folder
                relative_folder_path = parent_path_str[len(path_prefix):].lstrip('/')
                
                if relative_folder_path:
                    relative_path = f"{relative_folder_path}/{item['name']}"
                else:
                    relative_path = item['name']
                
                all_files_map[relative_path] = {
                    'size': item.get('size', 0),
                    'id': item.get('id'),
                    'modified': item.get('lastModifiedDateTime')
                }

        return all_files_map
    
    def build_cache_from_onedrive(self, profile):
        """Build upload cache from existing OneDrive files"""
        profile_name = profile['name']
        source_folder = Path(profile['source_folder'])
        onedrive_folder = profile['onedrive_folder']
        preserve_structure = profile.get('preserve_structure', True)
        
        self.logger.info("=" * 50)
        self.logger.info(f"Building cache from OneDrive for profile: {profile_name}")
        
        # Validate source folder exists
        if not source_folder.exists():
            self.logger.error(f"Source folder does not exist: {source_folder}")
            return False
        
        # Check if source folder is empty
        source_folder_contents = list(source_folder.iterdir())
        if not source_folder_contents:
            self.logger.error(f"Source folder is empty: {source_folder}")
            self.logger.error("Cannot build cache from an empty source folder")
            return False
        
        # Display source folder structure for verification
        folders = [p for p in source_folder_contents if p.is_dir()]
        files = [p for p in source_folder_contents if p.is_file()]
        
        self.logger.info(f"\nSource folder verification:")
        self.logger.info(f"  Path: {source_folder}")
        self.logger.info(f"  Subfolders: {len(folders)}")
        self.logger.info(f"  Files: {len(files)}")
        
        if folders:
            self.logger.info(f"  Sample subfolders (first 10): {[p.name for p in folders[:10]]}")
        if files:
            self.logger.info(f"  Sample files (first 10): {[p.name for p in files[:10]]}")
        
        # Count total files recursively
        self.logger.info("  Counting files recursively...")
        total_files = sum(1 for _ in source_folder.rglob('*') if _.is_file())
        self.logger.info(f"  Total files (recursive): {total_files}")
        
        if total_files == 0:
            self.logger.error("No files found in source folder (including subfolders)")
            self.logger.error("Cannot build cache from a folder with no files")
            return False
        
        # Ask for confirmation before proceeding
        self.logger.warning(f"\nAbout to scan OneDrive folder: {onedrive_folder}")
        self.logger.warning(f"This will be matched against: {source_folder}")
        self.logger.warning(f"Expected to match up to {total_files} local files")
        
        # In non-interactive environments, you might want to skip this
        # For now, add a 5-second delay to allow cancellation
        self.logger.warning("\nStarting in 5 seconds... (Ctrl+C to cancel)")
        try:
            for i in range(5, 0, -1):
                self.logger.info(f"  {i}...")
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("\nCache build cancelled by user")
            return False
        
        self.logger.info("\nProceeding with cache build...\n")
        
        # Authenticate
        auth_timeout = self.config.get('auth_timeout_seconds', 300)
        auth_manager = AuthManager(
            client_id=self.config['client_id'],
            profile_name=profile_name,
            data_dir=self.data_dir,
            auth_timeout=auth_timeout
        )
        
        try:
            # Initialize OneDrive client
            od_client = OneDriveClient(auth_manager)
        except Exception as e:
            self.logger.error(f"Authentication failed for profile [{profile_name}]: {e}")
            raise Exception(f"Authentication failed or timed out for profile [{profile_name}]")
        
        # Get all files from OneDrive recursively
        self.logger.info(f"Scanning OneDrive folder: {onedrive_folder}")
        self.logger.info("This may take a while for large folders...")
        
        onedrive_files = self._get_all_onedrive_files(od_client, onedrive_folder)
        
        self.logger.info(f"Found {len(onedrive_files)} files in OneDrive")
        
        if not onedrive_files:
            self.logger.warning("No files found in OneDrive folder")
            self.logger.warning(f"OneDrive folder: {onedrive_folder}")
            self.logger.warning("Make sure the folder path is correct and contains files")
            return False
        
        # Verify reasonable match ratio before proceeding
        if len(onedrive_files) < total_files * 0.1:  # Less than 10% match
            self.logger.warning(f"\nWarning: OneDrive has {len(onedrive_files)} files")
            self.logger.warning(f"         Local has {total_files} files")
            self.logger.warning("This seems like a significant mismatch. Continuing anyway...")
        
        # Build cache by matching with local files
        cache = {}
        matched_count = 0
        missing_local = 0
        
        self.logger.info("\nMatching OneDrive files with local files...")
        
        for relative_path, od_info in onedrive_files.items():
            # Construct local file path
            local_file = source_folder / relative_path.replace('/', '\\')
            
            if local_file.exists() and local_file.is_file():
                # File exists locally, add to cache
                local_size = local_file.stat().st_size
                local_mtime = local_file.stat().st_mtime
                
                # Normalize path for cache key
                cache_key = relative_path.replace('\\', '/')
                
                cache[cache_key] = {
                    'size': local_size,
                    'modified': local_mtime,
                    'uploaded': datetime.now().isoformat(),
                    'onedrive_path': f"{onedrive_folder}/{relative_path}".replace('\\', '/'),
                    'synced_from_onedrive': True  # Mark as synced from OneDrive
                }
                matched_count += 1
                
                if matched_count % 1000 == 0:
                    self.logger.info(f"Processed {matched_count} files...")
            else:
                missing_local += 1
                if missing_local <= 10:  # Only log first 10
                    self.logger.debug(f"File in OneDrive but not local: {relative_path}")
        
        # Final statistics and warnings
        match_percentage = (matched_count / len(onedrive_files) * 100) if onedrive_files else 0
        
        self.logger.info("\n" + "=" * 50)
        self.logger.info(f"Cache build complete for [{profile_name}]:")
        self.logger.info(f"  OneDrive files scanned: {len(onedrive_files)}")
        self.logger.info(f"  Matched with local: {matched_count} ({match_percentage:.1f}%)")
        self.logger.info(f"  In OneDrive only: {missing_local}")
        self.logger.info(f"  Local files total: {total_files}")
        
        if match_percentage < 50:
            self.logger.warning(f"\n  WARNING: Low match rate ({match_percentage:.1f}%)")
            self.logger.warning(f"  This might indicate:")
            self.logger.warning(f"    - Wrong source folder")
            self.logger.warning(f"    - Wrong OneDrive folder")
            self.logger.warning(f"    - Files organized differently")
        
        # Save cache
        self._save_upload_cache(profile_name, cache)
        self.logger.info(f"\n  Cache file: upload_cache_{profile_name}.json")
        self.logger.info("=" * 50)
        
        return True
    
    def sync_download_profile(self, profile):
        """Sync photos from OneDrive to local (download)"""
        profile_name = profile['name']
        dest_folder = Path(profile['destination_folder'])
        remove_downloaded = profile.get('remove_downloaded', False)
        
        self.logger.info("=" * 50)
        self.logger.info(f"Processing download profile: {profile_name}")
        
        # Authenticate
        auth_timeout = self.config.get('auth_timeout_seconds', 300)
        auth_manager = AuthManager(
            client_id=self.config['client_id'],
            profile_name=profile_name,
            data_dir=self.data_dir,
            auth_timeout=auth_timeout
        )
        
        try:
            # Initialize OneDrive client
            od_client = OneDriveClient(auth_manager)
        except Exception as e:
            self.logger.error(f"Authentication failed for profile [{profile_name}], skipping...: {e}")
            raise Exception(f"Authentication failed or timed out for profile [{profile_name}]")
        
        # Get OneDrive items
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
    
    def sync_upload_profile(self, profile):
        """Sync files from local NAS to OneDrive (upload)"""
        profile_name = profile['name']
        source_folder = Path(profile['source_folder'])
        onedrive_folder = profile['onedrive_folder']
        file_patterns = profile.get('file_patterns', ['*.*'])
        remove_uploaded = profile.get('remove_uploaded', False)
        preserve_structure = profile.get('preserve_structure', True)
        use_cache = profile.get('use_cache', True)
        use_watermark = profile.get('use_watermark', False)  # Incremental scan optimization
        
        self.logger.info("=" * 50)
        self.logger.info(f"Processing upload profile: {profile_name}")
        self.logger.info(f"Cache enabled: {use_cache}")
        self.logger.info(f"Watermark enabled: {use_watermark}")
        
        if not source_folder.exists():
            self.logger.error(f"Source folder does not exist: {source_folder}")
            return
        
        # Load cache if enabled
        upload_cache_data = self._load_upload_cache(profile_name) if use_cache else {'_metadata': {}}
        upload_cache = {k: v for k, v in upload_cache_data.items() if k != '_metadata'}
        cache_metadata = upload_cache_data.get('_metadata', {})
        
        # Get last watermark if using incremental scan
        last_watermark = None
        if use_watermark and 'last_scan_watermark' in cache_metadata:
            last_watermark = datetime.fromisoformat(cache_metadata['last_scan_watermark'])
            self.logger.info(f"Using watermark: only processing files modified after {last_watermark.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Authenticate
        auth_timeout = self.config.get('auth_timeout_seconds', 300)
        auth_manager = AuthManager(
            client_id=self.config['client_id'],
            profile_name=profile_name,
            data_dir=self.data_dir,
            auth_timeout=auth_timeout
        )

        try:
            # Initialize OneDrive client
            od_client = OneDriveClient(auth_manager)
        except Exception as e:
            self.logger.error(f"Authentication failed for profile [{profile_name}], skipping...: {e}")
            raise Exception(f"Authentication failed or timed out for profile [{profile_name}]")
        
        # Ensure destination folder exists in OneDrive
        if not od_client.create_folder(onedrive_folder):
            self.logger.error(f"Failed to create OneDrive folder: {onedrive_folder}")
            return
        
        # Process local files
        uploaded_count = 0
        skipped_count = 0
        error_count = 0
        deleted_count = 0
        cache_updated = False
        
        # Collect all files matching patterns (use rglob for recursive search)
        local_files = []
        scan_start_time = datetime.now()
        max_mtime = 0  # Track highest modification time seen
        
        for pattern in file_patterns:
            for file_path in source_folder.rglob(pattern):
                if file_path.is_file():
                    # Apply watermark filter if enabled
                    if use_watermark and last_watermark:
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_mtime <= last_watermark:
                            continue  # Skip files older than watermark
                    
                    local_files.append(file_path)
                    # Track max modification time
                    file_mtime_ts = file_path.stat().st_mtime
                    if file_mtime_ts > max_mtime:
                        max_mtime = file_mtime_ts
        
        # Remove duplicates
        local_files = list(set(local_files))
        
        if use_watermark and last_watermark:
            self.logger.info(f"Found {len(local_files)} files modified after watermark")
        else:
            self.logger.info(f"Found {len(local_files)} local files to process")
        
        if not local_files:
            if use_watermark and last_watermark:
                self.logger.info(f"No new files since last scan")
            else:
                self.logger.warning(f"No files found matching patterns: {file_patterns}")
                self.logger.info(f"Searched in: {source_folder}")
            
            # Update watermark even if no files (scan completed successfully)
            if use_watermark and use_cache:
                cache_metadata['last_scan_watermark'] = scan_start_time.isoformat()
                cache_metadata['last_scan_completed'] = scan_start_time.isoformat()
                upload_cache_data = {'_metadata': cache_metadata, **upload_cache}
                self._save_upload_cache(profile_name, upload_cache_data)
            return
        
        for i, local_file in enumerate(local_files, 1):
            filename = local_file.name
            
            # Construct OneDrive path (preserve or flatten structure)
            if preserve_structure:
                # Preserve folder structure relative to source_folder
                relative_path = local_file.relative_to(source_folder)
                onedrive_path = f"{onedrive_folder}/{relative_path}".replace('\\', '/').replace('//', '/')
                cache_key = str(relative_path).replace('\\', '/')
                display_name = str(relative_path)
            else:
                # Flatten - all files to same folder
                onedrive_path = f"{onedrive_folder}/{filename}".replace('//', '/')
                cache_key = filename
                display_name = filename
            
            # Progress logging for large sets
            if i % 100 == 0:
                self.logger.info(f"Progress: {i}/{len(local_files)} ({i/len(local_files)*100:.1f}%)")
            
            # Get file stats
            local_size = local_file.stat().st_size
            local_mtime = local_file.stat().st_mtime
            
            # Check cache
            if use_cache and cache_key in upload_cache:
                cached_info = upload_cache[cache_key]
                cached_size = cached_info.get('size')
                cached_mtime = cached_info.get('modified')
                
                # Skip if file hasn't changed (same size and modification time)
                if cached_size == local_size and cached_mtime == local_mtime:
                    self.logger.debug(f"Skipping [{display_name}] - in cache and unchanged")
                    skipped_count += 1
                    continue
                else:
                    self.logger.info(f"File changed: [{display_name}] (size: {cached_size}->{local_size})")
            
            # Log upload attempt
            if i % 100 != 0:  # Don't duplicate progress messages
                self.logger.info(f"Processing [{display_name}]")
            
            # Upload file
            if od_client.upload_file(local_file, onedrive_path):
                self.logger.info(f"Successfully uploaded [{display_name}]")
                uploaded_count += 1
                
                # Update cache
                if use_cache:
                    upload_cache[cache_key] = {
                        'size': local_size,
                        'modified': local_mtime,
                        'uploaded': datetime.now().isoformat(),
                        'onedrive_path': onedrive_path
                    }
                    cache_updated = True
                    
                    # Save cache periodically (every 100 files) to avoid data loss
                    if uploaded_count % 100 == 0:
                        self._save_upload_cache(profile_name, upload_cache)
                        self.logger.info(f"Cache checkpoint saved ({len(upload_cache)} entries)")
                
                # Delete local file if configured
                if remove_uploaded:
                    try:
                        local_file.unlink()
                        self.logger.info(f"Deleted local file [{display_name}]")
                        deleted_count += 1
                    except Exception as e:
                        self.logger.error(f"Error deleting local file [{display_name}]: {e}")
            else:
                error_count += 1
        
        # Update watermark and save final cache
        if use_cache:
            if use_watermark:
                # Set watermark to the scan start time (conservative approach)
                # This ensures we don't miss files that were being modified during scan
                cache_metadata['last_scan_watermark'] = scan_start_time.isoformat()
                cache_metadata['last_scan_completed'] = datetime.now().isoformat()
                cache_metadata['files_scanned'] = len(local_files)
                cache_metadata['files_uploaded'] = uploaded_count
                self.logger.info(f"Updated watermark to {scan_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if cache_updated or use_watermark:
                upload_cache_data = {'_metadata': cache_metadata, **upload_cache}
                self._save_upload_cache(profile_name, upload_cache_data)
                self.logger.info(f"Final cache saved with {len(upload_cache)} entries")
        
        self.logger.info("=" * 50)
        self.logger.info(f"Upload profile [{profile_name}] complete:")
        self.logger.info(f"  Uploaded: {uploaded_count}")
        self.logger.info(f"  Skipped: {skipped_count} (cached/unchanged)")
        self.logger.info(f"  Errors: {error_count}")
        if remove_uploaded:
            self.logger.info(f"  Deleted from local: {deleted_count}")
        if use_cache:
            self.logger.info(f"  Cache entries: {len(upload_cache)}")
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
    
    def run_once(self, initial_auth=False):
        """Run sync for all profiles once"""
        # Send start signal to healthchecks.io
        self._healthcheck_ping("/start")
        
        self.logger.info("*" * 50)
        self.logger.info("PhotoSync Starting...")
        self.logger.info("*" * 50)
        
        sync_failed = False
        
        # Process download profiles (OneDrive -> Local)
        download_profiles = self.config.get('download_profiles', [])
        # Legacy support: if 'profiles' exists, treat as download profiles
        if 'profiles' in self.config and not download_profiles:
            download_profiles = self.config['profiles']

        if not download_profiles:
            self.logger.info("No download profiles configured, skipping download step.")
        else:           
            for profile in download_profiles:
                try:
                    if initial_auth:
                        # Force device code flow for initial setup
                        auth_timeout = self.config.get('auth_timeout_seconds', 300)
                        auth_manager = AuthManager(
                            client_id=self.config['client_id'],
                            profile_name=profile['name'],
                            data_dir=self.data_dir,
                            auth_timeout=auth_timeout
                        )
                        auth_manager.get_access_token(force_device_code=True)
                    else:
                        self.sync_download_profile(profile)
                except Exception as e:
                    self.logger.error(f"Error processing download profile [{profile['name']}]: {e}", exc_info=True)
                    sync_failed = True
        
        # Process upload profiles (Local -> OneDrive)
        upload_profiles = self.config.get('upload_profiles', [])

        if not upload_profiles:
            self.logger.info("No upload profiles configured, skipping upload step.")
            return

        for profile in upload_profiles:
            try:
                if initial_auth:
                    # Force device code flow for initial setup
                    auth_timeout = self.config.get('auth_timeout_seconds', 300)
                    auth_manager = AuthManager(
                        client_id=self.config['client_id'],
                        profile_name=profile['name'],
                        data_dir=self.data_dir,
                        auth_timeout=auth_timeout
                    )
                    auth_manager.get_access_token(force_device_code=True)
                else:
                    self.sync_upload_profile(profile)
            except Exception as e:
                self.logger.error(f"Error processing upload profile [{profile['name']}]: {e}", exc_info=True)
                sync_failed = True
        
        self.logger.info("*" * 50)
        self.logger.info("PhotoSync Done")
        self.logger.info("*" * 50)
        
        # Send success or failure signal to healthchecks.io
        if sync_failed:
            self._healthcheck_ping("/fail", "One or more profiles failed during sync")
        else:
            self._healthcheck_ping()  # Success
    
    def run(self, initial_auth=False, schedule_interval=None):
        """Run sync once or continuously on schedule
        
        Args:
            initial_auth: Only run authentication, don't sync
            schedule_interval: Minutes between runs (None = run once and exit)
        """
        if schedule_interval is None:
            # Single run
            self.run_once(initial_auth)
        else:
            # Scheduled continuous runs using schedule library
            self.logger.info("=" * 50)
            self.logger.info(f"Starting scheduled sync mode")
            self.logger.info(f"Interval: every {schedule_interval} minutes")
            self.logger.info(f"Press Ctrl+C to stop")
            self.logger.info("=" * 50)
            
            # Track run count
            self.run_count = 0
            
            def scheduled_job():
                """Wrapper for scheduled runs"""
                if not self.running:
                    return schedule.CancelJob
                
                self.run_count += 1
                self.logger.info(f"\n{'=' * 50}")
                self.logger.info(f"Scheduled Run #{self.run_count}")
                self.logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"{'=' * 50}\n")
                
                try:
                    self.run_once(initial_auth)
                except Exception as e:
                    self.logger.error(f"Error during scheduled run: {e}", exc_info=True)
                
                if not self.running:
                    return schedule.CancelJob
            
            # Schedule the job
            schedule.every(schedule_interval).minutes.do(scheduled_job)
            
            # Run immediately on start
            scheduled_job()
            
            # Run scheduled jobs
            self.logger.info(f"\nNext run in {schedule_interval} minutes...")
            while self.running:
                schedule.run_pending()
                time.sleep(1)
            
            # Cleanup
            schedule.clear()
            self.logger.info("\n" + "=" * 50)
            self.logger.info("Scheduled sync mode stopped")
            self.logger.info(f"Total runs completed: {self.run_count}")
            self.logger.info("=" * 50)
    
    def logout(self):
        """Logout all profiles"""
        self.logger.info("Logging out all profiles...")
        
        # Logout download profiles
        download_profiles = self.config.get('download_profiles', [])
        if 'profiles' in self.config and not download_profiles:
            download_profiles = self.config['profiles']
        
        auth_timeout = self.config.get('auth_timeout_seconds', 300)
        
        for profile in download_profiles:
            auth_manager = AuthManager(
                client_id=self.config['client_id'],
                profile_name=profile['name'],
                data_dir=self.data_dir,
                auth_timeout=auth_timeout
            )
            auth_manager.logout()
        
        # Logout upload profiles
        upload_profiles = self.config.get('upload_profiles', [])
        for profile in upload_profiles:
            auth_manager = AuthManager(
                client_id=self.config['client_id'],
                profile_name=profile['name'],
                data_dir=self.data_dir,
                auth_timeout=auth_timeout
            )
            auth_manager.logout()

def main():
    parser = argparse.ArgumentParser(description='Sync photos from OneDrive to local storage')
    parser.add_argument('--logout', action='store_true', help='Remove all cached tokens')
    parser.add_argument('--initial-auth', action='store_true', help='Run initial authentication only')
    parser.add_argument('--clear-cache', action='store_true', help='Clear upload cache for all profiles')
    parser.add_argument('--build-cache', action='store_true', help='Build upload cache from existing OneDrive files')
    parser.add_argument('--schedule', action='store_true', help='Run continuously on schedule (uses schedule_interval_minutes from config)')
    parser.add_argument('--interval', type=int, help='Override schedule interval in minutes (requires --schedule)')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    
    args = parser.parse_args()
    
    sync = PhotoSync(config_path=args.config)
    
    # print config
    sync.logger.info(f"Loaded config: {json.dumps(sync.config, indent=2)}")

    if args.logout:
        sync.logout()
    elif args.clear_cache:
        # Clear upload caches
        cache_files = list(sync.data_dir.glob('upload_cache_*.json'))
        if cache_files:
            for cache_file in cache_files:
                cache_file.unlink()
                print(f"Deleted: {cache_file.name}")
            print(f"Cleared {len(cache_files)} cache file(s)")
        else:
            print("No cache files found")
    elif args.build_cache:
        # Build cache from OneDrive
        upload_profiles = sync.config.get('upload_profiles', [])
        if not upload_profiles:
            print("No upload profiles configured")
        else:
            for profile in upload_profiles:
                try:
                    sync.build_cache_from_onedrive(profile)
                except Exception as e:
                    sync.logger.error(f"Error building cache for [{profile['name']}]: {e}", exc_info=True)
    else:
        # Determine schedule interval
        schedule_interval = None
        if args.schedule:
            if args.interval:
                schedule_interval = args.interval
            else:
                schedule_interval = sync.config.get('schedule_interval_minutes')
                if not schedule_interval:
                    print("Error: --schedule requires either --interval or schedule_interval_minutes in config")
                    sys.exit(1)
        
        sync.run(initial_auth=args.initial_auth, schedule_interval=schedule_interval)

if __name__ == '__main__':
    main()
