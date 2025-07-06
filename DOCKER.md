# Docker Setup for Around the Grounds Temporal Worker

This guide walks you through setting up the Docker container for the Temporal worker.

## Prerequisites

1. **GitHub App Private Key**: You'll need your GitHub App private key file
2. **Temporal Cloud Configuration**: Your Temporal Cloud credentials
3. **Claude API Key**: (Optional) For AI vision analysis

## Step 1: Prepare Your GitHub App Private Key

First, you need to base64-encode your GitHub App private key:

```bash
# If your private key is in a file called github-app-private-key.pem
cat github-app-private-key.pem | base64 -w 0

# This will output a long base64 string - copy this for the next step
```

## Step 2: Create Environment File

Copy the template environment file:

```bash
cp .env.docker .env
```

Then edit `.env` and fill in your credentials:

```bash
# Temporal Configuration (choose ONE authentication method)

# Option 1: Temporal Cloud with API Key
TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_API_KEY=your-temporal-api-key

# Option 2: mTLS Authentication (what you're using)
TEMPORAL_ADDRESS=your-server.address:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_TLS_CERT=/certs/client.crt
TEMPORAL_TLS_KEY=/certs/client.key

# GitHub App Configuration
GITHUB_APP_PRIVATE_KEY_B64=your-base64-encoded-private-key-from-step1

# Claude Vision API (optional)
ANTHROPIC_API_KEY=your-anthropic-api-key
```

## Step 3: Build the Docker Image

Build the multi-architecture image:

```bash
# For single architecture (current platform)
docker build -t around-the-grounds-worker .

# For multi-architecture (Mac + x86 Synology)
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t around-the-grounds-worker .
```

## Step 3a: Certificate Setup (mTLS Only)

If you're using mTLS authentication, you need to prepare your certificates:

1. **Create a certs directory in your project:**
   ```bash
   mkdir -p certs
   ```

2. **Copy your certificates:**
   ```bash
   cp /Users/steveandroulakis/Code/certs/steveandroulakis-test-1.sdvdw.crt certs/client.crt
   cp /Users/steveandroulakis/Code/certs/steveandroulakis-test-1.sdvdw-pkcs8.key certs/client.key
   ```

3. **Update your `.env` file:**
   ```bash
   TEMPORAL_ADDRESS=your-server.address:7233
   TEMPORAL_NAMESPACE=your-namespace
   TEMPORAL_TLS_CERT=/certs/client.crt
   TEMPORAL_TLS_KEY=/certs/client.key
   CERT_DIR=/Users/steveandroulakis/Code/certs
   ```

## Step 4: Test Locally

Test the container locally using docker-compose:

```bash
# Run in foreground to see logs
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
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

## Step 7: Deploy to Synology

On your Synology NAS:

1. Install Docker from Package Center
2. Pull your image: `docker pull your-dockerhub-username/around-the-grounds-worker:latest`
3. Create a container with the same environment variables as above
4. Start the container

## Environment Variables Reference

### Required Variables

**For All Setups:**
- `TEMPORAL_ADDRESS`: Your Temporal server address
- `TEMPORAL_NAMESPACE`: Your Temporal namespace
- `GITHUB_APP_PRIVATE_KEY_B64`: Your GitHub App private key (base64 encoded)

**For API Key Authentication:**
- `TEMPORAL_API_KEY`: Your Temporal Cloud API key

**For mTLS Authentication:**
- `TEMPORAL_TLS_CERT`: Path to client certificate inside container (e.g., `/certs/client.crt`)
- `TEMPORAL_TLS_KEY`: Path to client private key inside container (e.g., `/certs/client.key`)
- `CERT_DIR`: Host directory containing certificates (for volume mounting)

### Optional Variables

- `ANTHROPIC_API_KEY`: Claude Vision API key for food truck name extraction
- `VISION_ANALYSIS_ENABLED`: Enable/disable vision analysis (default: true)
- `VISION_MAX_RETRIES`: Max retry attempts for vision API (default: 2)
- `VISION_TIMEOUT`: API timeout in seconds (default: 30)
- `TEMPORAL_TASK_QUEUE`: Task queue name (default: food-truck-task-queue)

## Troubleshooting

### Container Won't Start

1. Check logs: `docker-compose logs`
2. Verify all required environment variables are set
3. Test GitHub App authentication manually

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
3. Deploy to your Synology NAS
4. Configure monitoring and alerting
5. Set up log aggregation

## Security Notes

- Never commit your `.env` file to version control
- Use Docker secrets in production environments
- Regularly rotate your API keys and GitHub App private key
- Monitor container logs for security issues