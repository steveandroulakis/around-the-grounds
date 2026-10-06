# Staging Deployment

A staging worker runs this checkout's code against the same Temporal server as
production, but writes the site to `staging/site/` instead of pushing to the
site's target repo. nginx serves that directory on port 8090, so changes can be
checked from any device that can reach the host (e.g. over Tailscale) before
they go to production.

| | Production | Staging |
|---|---|---|
| Worker container | `around-the-grounds-worker` | `around-the-grounds-worker-staging` |
| Task queue | `food-truck-task-queue` | `food-truck-task-queue-staging` |
| Schedule | `hourly-scrape` (running) | `hourly-scrape-staging` (**paused**) |
| Code | published image | this checkout (bind-mounted) |
| Output | push to `target_repo` | `staging/site/` → `http://<host>:8090` |
| AI haiku / vision | on | off |

## How it works

`deploy_to_git` checks `LOCAL_DEPLOY_DIR`. When it is set, the activity calls
`main.py:_deploy_to_local_dir`, which writes the same files as a real deploy
(template + `data.json` + `events.ics`) into that directory and never touches
git. The staging worker gets no GitHub App credentials, so it cannot push even
by mistake. Its task queue is hardcoded in `docker-compose.staging.yml`: a
staging worker polling the production queue would take production runs.

## Setup

```bash
# Start the worker and web server (connects to Temporal on the Docker host;
# override with STAGING_TEMPORAL_ADDRESS=host:7233)
docker compose -f docker-compose.staging.yml up -d --build

# Create the schedule once, paused so it only runs when triggered
temporal schedule create \
    --address <temporal-host>:7233 \
    --schedule-id hourly-scrape-staging \
    --interval '60m/10m' \
    --type FoodTruckWorkflow \
    --task-queue food-truck-task-queue-staging \
    --workflow-id food-truck-staging \
    --input '{"config_path": null, "deploy": true, "site_key": "ballard-food-trucks"}' \
    --paused
```

## Updating staging

1. Change code or templates in this checkout.
2. Python changes: `docker compose -f docker-compose.staging.yml restart staging-worker`.
   Template changes need no restart. Dependency changes need `up -d --build`.
3. Run it: `temporal schedule trigger --schedule-id hourly-scrape-staging --address <temporal-host>:7233`
   (or **Trigger** on the schedule in the Temporal UI, port 8233).
4. Open `http://<host>:8090`. Responses are sent with `Cache-Control: no-store`.

Leave the schedule paused: staging output only changes when you ask for it.
