# Deploy via GHCR (No Build on Server)

This repo is set up to publish Docker images to GitHub Container Registry (GHCR) on every push to `master`.
On small servers (for example 1 vCPU / 512MB RAM / 10GB disk), building images locally often fails with
`no space left on device` or OOM. Use `docker compose pull` instead.

## 1) Publish Images (CI)

Push to `master` and wait for GitHub Actions workflow:
`Publish Docker Images (GHCR)`.

Images:
- `ghcr.io/sardoressketi/audio-dataset-maker-backend:latest`
- `ghcr.io/sardoressketi/audio-dataset-maker-frontend:latest`

## 2) Server Deploy

```bash
cd ~/Audio-dataset-maker
git pull

# Login once (use a GitHub PAT with `read:packages` if needed)
docker login ghcr.io

docker compose pull
docker compose up -d
docker compose ps
```

## 3) Update

```bash
git pull
docker compose pull
docker compose up -d
```

