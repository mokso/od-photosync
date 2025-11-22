# Container Images

Container images are automatically built and published to GitHub Container Registry (GHCR) via GitHub Actions.

## Available Images

**Registry:** `ghcr.io/mokso/od-photosync`

### Tags

| Tag | Description | Use Case |
|-----|-------------|----------|
| `latest` | Latest stable build from `main` branch | Production use |
| `main` | Latest build from `main` branch | Production use |
| `python-rewrite` | Latest build from `python-rewrite` branch | Testing new features |
| `v1.0.0` | Specific version release | Pinned deployments |
| `main-sha-abc1234` | Specific commit from `main` | Rollback/debugging |

## Using Pre-built Images

### Docker Run

```bash
# Pull latest image
docker pull ghcr.io/mokso/od-photosync:latest

# Run with config and data volumes
docker run --rm \
  -v ./data:/app/data \
  -v ./config.yaml:/app/config.yaml:ro \
  -v /mnt/nas/photos:/photos \
  ghcr.io/mokso/od-photosync:latest
```

### Docker Compose

Update your `docker-compose.yml`:

```yaml
services:
  photosync:
    image: ghcr.io/mokso/od-photosync:latest
    # ... rest of config
```

Or use the provided compose file:

```bash
docker-compose pull
docker-compose run --rm photosync
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: CronJob
metadata:
  name: photosync
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: photosync
            image: ghcr.io/mokso/od-photosync:latest
            volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: config.yaml
            - name: data
              mountPath: /app/data
            - name: photos
              mountPath: /photos
          volumes:
          - name: config
            secret:
              secretName: photosync-config
          - name: data
            persistentVolumeClaim:
              claimName: photosync-data
          - name: photos
            persistentVolumeClaim:
              claimName: nas-photos
          restartPolicy: OnFailure
```

## Building Images Locally

### Manual Build

```bash
# Build for current platform
docker build -t photosync:local .

# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 -t photosync:local .
```

### Using docker-compose

```bash
# Use development compose file for local builds
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml run --rm photosync
```

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/docker-build.yml`) automatically:

1. **Triggers on:**
   - Push to `main` or `python-rewrite` branches
   - Creation of version tags (`v*`)
   - Pull requests (build only, no push)
   - Manual workflow dispatch

2. **Builds for:**
   - `linux/amd64` (Intel/AMD)
   - `linux/arm64` (Apple Silicon, Raspberry Pi, ARM servers)

3. **Publishes to:**
   - GitHub Container Registry (ghcr.io)
   - Tagged with branch name, commit SHA, and semantic version

4. **Features:**
   - Layer caching for faster builds
   - Multi-platform support
   - Automatic tagging
   - Metadata labels

## Image Details

### Base Image
- **OS:** Alpine Linux 3.18
- **Python:** 3.12
- **Size:** ~150MB compressed

### Included
- Python application and dependencies
- Configuration template
- Data directories

### Security
- Runs as non-root user (`photosync`)
- Minimal attack surface (Alpine)
- No unnecessary packages

## Version Pinning

For production deployments, pin to a specific version:

```yaml
# Pin to major version (receives updates)
image: ghcr.io/mokso/od-photosync:v1

# Pin to minor version
image: ghcr.io/mokso/od-photosync:v1.0

# Pin to exact version (no updates)
image: ghcr.io/mokso/od-photosync:v1.0.0

# Pin to specific commit (for debugging)
image: ghcr.io/mokso/od-photosync:main-sha-abc1234
```

## Updating

### Latest Tag

```bash
docker pull ghcr.io/mokso/od-photosync:latest
docker-compose up -d  # Recreates container with new image
```

### Specific Version

```bash
# Update to new version
docker pull ghcr.io/mokso/od-photosync:v1.1.0

# Update docker-compose.yml
# image: ghcr.io/mokso/od-photosync:v1.1.0

docker-compose up -d
```

## Troubleshooting

### Authentication Required

If pulling images fails with authentication error:

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Or use GitHub CLI
gh auth token | docker login ghcr.io -u USERNAME --password-stdin
```

**Note:** Public images don't require authentication, but private repos do.

### Image Not Found

Ensure you're using the correct repository name:
- ✅ `ghcr.io/mokso/od-photosync:latest`
- ❌ `ghcr.io/mokso/photosync:latest`

### Platform Issues

If running on ARM (Raspberry Pi, Apple Silicon):

```bash
# Explicitly specify platform
docker pull --platform linux/arm64 ghcr.io/mokso/od-photosync:latest
```

## Development Workflow

1. Make code changes
2. Test locally:
   ```bash
   docker-compose -f docker-compose.dev.yml build
   docker-compose -f docker-compose.dev.yml run --rm photosync
   ```
3. Commit and push to branch
4. GitHub Actions builds and publishes automatically
5. Test pre-built image:
   ```bash
   docker pull ghcr.io/mokso/od-photosync:python-rewrite
   ```
6. Merge to `main` for production release

## Manual Release

To create a versioned release:

```bash
# Tag the commit
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions will automatically:
# - Build the image
# - Tag it as v1.0.0, v1.0, v1, and latest
# - Publish to GHCR
```
