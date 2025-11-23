# Docker Compose Setup Guide

This directory contains multiple docker-compose files for different operations.

## Quick Start

1. **Setup environment:**
   ```bash
   cp .env.example .env
   # Edit .env and set PHOTOS_PATH to your mount point
   ```

2. **Initial authentication:**
   ```bash
   docker-compose -f docker-compose.auth.yml run --rm photosync-auth
   ```

3. **Optional - Build cache (for large collections):**
   ```bash
   docker-compose -f docker-compose.build-cache.yml run --rm photosync-build-cache
   ```

4. **Run scheduled sync:**
   ```bash
   docker-compose up -d
   ```

## Available Compose Files

| File | Purpose | Command |
|------|---------|---------|
| `docker-compose.yml` | Scheduled sync (daemon) | `docker-compose up -d` |
| `docker-compose.auth.yml` | Initial authentication | `docker-compose -f docker-compose.auth.yml run --rm photosync-auth` |
| `docker-compose.build-cache.yml` | Build cache from OneDrive | `docker-compose -f docker-compose.build-cache.yml run --rm photosync-build-cache` |
| `docker-compose.sync-once.yml` | Single sync run | `docker-compose -f docker-compose.sync-once.yml run --rm photosync-once` |

## Environment Variables (.env)

Required:
- `PHOTOS_PATH` - Path to photos on host (mounted as /photos in container)

Optional:
- `TZ` - Timezone (default: UTC)

Example `.env`:
```bash
PHOTOS_PATH=/mnt/kuvat
TZ=Europe/Helsinki
```

## Proxmox LXC Setup

If running in Proxmox LXC with OMV VM:

1. **On Proxmox host, mount OMV share:**
   ```bash
   mkdir -p /mnt/kuvat-share
   mount -t nfs <OMV_IP>:/kuvat-share /mnt/kuvat-share
   echo "<OMV_IP>:/kuvat-share /mnt/kuvat-share nfs defaults,auto 0 0" >> /etc/fstab
   ```

2. **Bind mount to LXC:**
   ```bash
   pct set <CTID> -mp0 /mnt/kuvat-share,mp=/mnt/kuvat
   pct restart <CTID>
   ```

3. **In LXC, set environment:**
   ```bash
   # .env
   PHOTOS_PATH=/mnt/kuvat
   ```

## Common Commands

```bash
# View logs
docker-compose logs -f

# Restart service
docker-compose restart

# Stop service
docker-compose down

# Clear cache
docker-compose run --rm photosync python photosync.py --clear-cache

# Logout (remove tokens)
docker-compose run --rm photosync python photosync.py --logout
```

## Configuration

Edit `config.yaml`:
- For Docker: Use `/photos` as the base path for all folders
- Update `schedule_interval_minutes` for sync frequency
- Add `healthcheck_url` for monitoring

Example paths in config:
```yaml
download_profiles:
  - name: "Profile1"
    destination_folder: "/photos/Profile1"

upload_profiles:
  - name: "Backup"
    source_folder: "/photos/Documents"
    onedrive_folder: "/Backup/Documents"
```
