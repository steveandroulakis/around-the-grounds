# GCP Artifact Registry & GitHub Actions Setup

This document records the GCP infrastructure configured to allow GitHub Actions to push Docker images to Google Artifact Registry using Workload Identity Federation (keyless auth).

## Overview

| Component | Value |
|---|---|
| GCP Project | `event-curation` (project number `21604192945`) |
| Artifact Registry | `us-central1-docker.pkg.dev/event-curation/around-the-grounds/app` |
| Service Account | `github-actions-deployer@event-curation.iam.gserviceaccount.com` |
| WIF Pool | `github-actions` (global) |
| WIF Provider | `github` (OIDC, scoped to `jredding/around-the-grounds-brooklyn`) |

## What Was Created

### 1. Workload Identity Pool

```bash
gcloud iam workload-identity-pools create "github-actions" \
  --location="global" \
  --display-name="GitHub Actions"
```

### 2. OIDC Provider (GitHub)

```bash
gcloud iam workload-identity-pools providers create-oidc "github" \
  --location="global" \
  --workload-identity-pool="github-actions" \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == 'jredding/around-the-grounds-brooklyn'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

The `attribute-condition` restricts token exchange to only this repository.

### 3. Service Account

```bash
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"
```

### 4. IAM Bindings

Artifact Registry Writer (allows pushing images):

```bash
gcloud projects add-iam-policy-binding event-curation \
  --member="serviceAccount:github-actions-deployer@event-curation.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

Workload Identity User (allows GitHub Actions to impersonate the SA):

```bash
gcloud iam service-accounts add-iam-policy-binding \
  github-actions-deployer@event-curation.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/21604192945/locations/global/workloadIdentityPools/github-actions/attribute.repository/jredding/around-the-grounds-brooklyn"
```

### 5. Pre-existing: Artifact Registry Repository

The Docker repository `around-the-grounds` in `us-central1` already existed.

## GitHub Repository Secrets

These must be set manually in the GitHub repo settings (Settings > Secrets and variables > Actions):

| Secret | Value |
|---|---|
| `WIF_PROVIDER` | `projects/21604192945/locations/global/workloadIdentityPools/github-actions/providers/github` |
| `WIF_SERVICE_ACCOUNT` | `github-actions-deployer@event-curation.iam.gserviceaccount.com` |

## How It Works

1. GitHub Actions workflow requests an OIDC token from GitHub
2. The `google-github-actions/auth@v2` action exchanges that token with GCP via the WIF provider
3. GCP validates the token's `repository` claim matches `jredding/around-the-grounds-brooklyn`
4. GCP issues short-lived credentials for `github-actions-deployer` SA
5. `docker/login-action` uses those credentials to authenticate to Artifact Registry
6. The image is pushed to `us-central1-docker.pkg.dev/event-curation/around-the-grounds/app`

## Verification

After setting the GitHub secrets, merge a PR to `main` and confirm:

1. The GitHub Actions workflow succeeds
2. The image appears in Artifact Registry:
   ```bash
   gcloud artifacts docker images list \
     us-central1-docker.pkg.dev/event-curation/around-the-grounds/app \
     --sort-by=~UPDATE_TIME --limit=3
   ```
3. Cloud Run Jobs pick up the new image on next execution

## Teardown

To remove all resources created above:

```bash
# Delete WIF provider and pool
gcloud iam workload-identity-pools providers delete github \
  --location=global --workload-identity-pool=github-actions --quiet

gcloud iam workload-identity-pools delete github-actions \
  --location=global --quiet

# Remove IAM bindings
gcloud projects remove-iam-policy-binding event-curation \
  --member="serviceAccount:github-actions-deployer@event-curation.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Delete service account
gcloud iam service-accounts delete \
  github-actions-deployer@event-curation.iam.gserviceaccount.com --quiet
```
