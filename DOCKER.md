# Docker Setup for Around the Grounds Temporal Worker

This guide walks you through setting up the Docker containers for the Temporal worker and self-hosted Temporal server.

## Architecture

Two containers run on the same Docker network (`temporal-net`):

- **temporal-server**: Self-hosted Temporal dev server with SQLite persistence
- **around-the-grounds-worker**: The food truck scraping worker

The worker connects to the Temporal server at `temporal-server:7233` via Docker DNS. No authentication or TLS certificates are needed.

## Prerequisites

1. **Docker** installed and running
2. **GitHub App Private Key**: For web deployment (base64 encoded)
3. **Claude API Key**: (Optional) For AI vision analysis

## Quick Start (Local Development)

```bash
# 1. Copy environment template
cp .env.docker .env

# 2. Edit .env with your credentials (GITHUB_APP_PRIVATE_KEY_B64, ANTHROPIC_API_KEY)

# 3. Start both Temporal server and worker
docker compose up --build

# 4. View Temporal Web UI
open http://localhost:8233

# 5. Create a schedule (from another terminal)
TEMPORAL_ADDRESS=localhost:7233 TEMPORAL_NAMESPACE=default \
  uv run python -m around_the_grounds.temporal.schedule_manager create \
    --schedule-id daily-scrape --interval 60 --deploy
```

## Synology NAS Deployment

On Synology, the Temporal server and worker are managed separately. The server is infrastructure (rarely updated), while the worker is deployed automatically via CI/CD.

### Step 1: Set Up Temporal Server

Run once on the Synology (as root):

```bash
# Copy the setup script to Synology
scp scripts/synology-temporal-server.sh admin@<synology-ip>:/volume1/docker/scripts/

# SSH to Synology and run it
ssh admin@<synology-ip>
sudo bash /volume1/docker/scripts/synology-temporal-server.sh
```

This creates:
- Docker network `temporal-net`
- Data directory `/volume1/docker/temporal-data/`
- Auto-restarting `temporal-server` container

Verify: `http://<synology-ip>:8233` should show the Temporal Web UI.

### Step 2: Configure Worker Environment

Update `/volume1/docker/secrets/env-vars.sh` on Synology:

```bash
# Claude Vision API
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# GitHub App Configuration
export GITHUB_APP_PRIVATE_KEY_B64="your-base64-encoded-key"
```

No Temporal connection variables are needed - the worker connects via Docker networking.

### Step 3: Deploy Worker

The worker deploys automatically via CI/CD (GitHub Actions -> Docker Hub -> Synology).

For manual deployment:
```bash
ssh admin@<synology-ip> '/volume1/docker/scripts/deploy-pull.sh'
```

### Step 4: Create Schedule

From any machine that can reach the Synology:

```bash
# For single architecture (current platform)
docker build -t around-the-grounds-worker .

# For multi-architecture (e.g. Mac + x86 target host)
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t around-the-grounds-worker .
```

Or directly on the Synology:
```bash
docker exec temporal-server temporal schedule list
```

If you're using mTLS authentication, you need to prepare your certificates:

1. **Create a certs directory in your project:**
   ```bash
   mkdir -p certs
   ```

2. **Copy your certificates:**
   ```bash
   cp /path/to/your-cert.crt certs/client.crt
   cp /path/to/your-key.key certs/client.key
   ```

3. **Update your `.env` file:**
   ```bash
   TEMPORAL_ADDRESS=your-server.address:7233
   TEMPORAL_NAMESPACE=your-namespace
   TEMPORAL_TLS_CERT=/certs/client.crt
   TEMPORAL_TLS_KEY=/certs/client.key
   CERT_DIR=/path/to/your/certs
   ```

## Step 4: Test Locally

Test the container locally using docker-compose:

```bash
# View server logs
docker logs temporal-server

# Restart server (schedules and data persist)
docker restart temporal-server

# List schedules
docker exec temporal-server temporal schedule list --address localhost:7233

# Upgrade Temporal server
docker pull temporalio/temporal
docker stop temporal-server && docker rm temporal-server
sudo bash /volume1/docker/scripts/synology-temporal-server.sh
```

## Step 5: Manual Docker Run (Alternative)

If you prefer not to use docker-compose:

```bash
docker run -d \
  --name around-the-grounds-worker \
  --restart unless-stopped \
  -e TEMPORAL_ADDRESS="your-namespace.acct.tmprl.cloud:7233" \
  -e TEMPORAL_NAMESPACE="your-namespace" \
  -e TEMPORAL_API_KEY="your-temporal-api-key" \
  -e GITHUB_APP_PRIVATE_KEY_B64="your-base64-encoded-private-key" \
  -e ANTHROPIC_API_KEY="your-anthropic-api-key" \
  around-the-grounds-worker
```

## Step 6: Deploy to Docker Hub

Once tested, push to Docker Hub:

```bash
# Tag for Docker Hub
docker tag around-the-grounds-worker your-dockerhub-username/around-the-grounds-worker:latest

# Push to Docker Hub
docker push your-dockerhub-username/around-the-grounds-worker:latest

# For multi-architecture
docker buildx build --platform linux/amd64,linux/arm64 \
  -t your-dockerhub-username/around-the-grounds-worker:latest \
  --push .
```

## Step 7: Deploy to Your Target Host

On your target host (any machine that can run Docker and reach your Temporal server):

1. Install Docker
2. Pull your image: `docker pull your-dockerhub-username/around-the-grounds-worker:latest`
3. Create a container with the same environment variables as above
4. Start the container

## Environment Variables Reference

### Required Variables

- `GITHUB_APP_PRIVATE_KEY_B64`: GitHub App private key (base64 encoded)

### Optional Variables

- `ANTHROPIC_API_KEY`: Claude API key for vision analysis and haiku generation
- `VISION_ANALYSIS_ENABLED`: Enable/disable vision analysis (default: true)
- `VISION_MAX_RETRIES`: Max retry attempts for vision API (default: 2)
- `VISION_TIMEOUT`: API timeout in seconds (default: 30)
- `TEMPORAL_TASK_QUEUE`: Task queue name (default: food-truck-task-queue)

### Temporal Cloud Variables (only if using Cloud instead of self-hosted)

- `TEMPORAL_ADDRESS`: Cloud address (e.g., `your-namespace.tmprl.cloud:7233`)
- `TEMPORAL_NAMESPACE`: Cloud namespace
- `TEMPORAL_API_KEY`: Cloud API key
- `TEMPORAL_TLS_CERT` / `TEMPORAL_TLS_KEY`: mTLS certificate paths

## Troubleshooting

### Temporal Server Won't Start
1. Check logs: `docker logs temporal-server`
2. Verify data directory permissions: `ls -la /volume1/docker/temporal-data/`
3. Ensure ports 7233 and 8233 are not in use

### Worker Can't Connect to Temporal
1. Check both containers are on `temporal-net`: `docker network inspect temporal-net`
2. Verify Temporal server is healthy: `docker exec temporal-server temporal workflow list --address localhost:7233`
3. Check worker logs: `docker logs around-the-grounds-worker`

### GitHub Authentication Issues

1. Verify your private key is correctly base64 encoded
2. Check that your GitHub App has the correct permissions
3. Ensure the App is installed on your repository

### Temporal Connection Issues

1. Verify your Temporal Cloud credentials
2. Check network connectivity from the container
3. Ensure your namespace and API key are correct

### Vision API Issues

1. Check your Anthropic API key
2. Vision analysis is optional - disable with `VISION_ANALYSIS_ENABLED=false`
3. Monitor API usage and rate limits

## Next Steps

After successful testing, you can:

1. Push to Docker Hub for easy deployment
2. Set up automated builds with GitHub Actions
3. Deploy to your target host
4. Configure monitoring and alerting
5. Set up log aggregation

## Security Notes

- Never commit your `.env` file to version control
- Use Docker secrets in production environments
- Regularly rotate your API keys and GitHub App private key
- Monitor container logs for security issues