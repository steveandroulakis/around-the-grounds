# Web Deployment Workflow

This guide covers the complete web deployment workflow for the Around the Grounds project.

## Overview

The system deploys a complete static website to separate target repositories, which are served by GitHub Pages.

### Two-Repository Architecture

- **Source repo** (this one): Contains scraping code, parsers, site configs, per-site templates
- **Target repos** (one per site): Receive complete websites
  - `steveandroulakis/ballard-food-trucks` — Vercel watches the `public/` subdirectory
  - `jredding/atg-park-slope-music` — GitHub Pages serves repo root
  - `jredding/atg-childrens-events` — GitHub Pages serves repo root

## Quick Start

```bash
# Deploy default site (ballard-food-trucks)
uv run around-the-grounds --deploy

# Deploy a specific site
uv run around-the-grounds --site park-slope-music --deploy

# Deploy all configured sites
uv run around-the-grounds --site all --deploy

# Deploy with verbose logging
uv run around-the-grounds --deploy --verbose
```

## Development & Testing

### Local Preview

Before deploying, generate and test web files locally:

```bash
# Generate web files locally for testing (~60s to scrape all sites)
uv run around-the-grounds --preview

# Serve locally and view in browser
cd public && python -m http.server 8000
# Visit: http://localhost:8000
```

**What `--preview` does:**
- Scrapes fresh data from all venue websites for the selected site
- Copies site-specific templates from `public_templates/<template>/` to `public/`
- Generates `data.json` with current event data
- Generates `events.ics`, the subscribable calendar feed
- Creates complete website in `public/` directory (git-ignored)

This allows you to test web interface changes, verify data accuracy, and debug issues before deploying to production.

### Testing Web Interface Changes

1. **Edit templates**: Make changes to files in `public_templates/<template>/`
2. **Generate preview**: Run `uv run around-the-grounds --preview`
3. **Test locally**: Serve with `cd public && python -m http.server 8000`
4. **Verify changes**: Check http://localhost:8000 in browser
5. **Deploy when ready**: Run `uv run around-the-grounds --deploy`

### Testing Data Generation

```bash
# Test data.json endpoint
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | head -20 && pkill -f "python -m http.server" || true

# Test for specific event data
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | grep "2025-07-06" && pkill -f "python -m http.server" || true

# Test full homepage (basic connectivity)
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/ > /dev/null && echo "✅ Homepage loads" && pkill -f "python -m http.server" || echo "❌ Homepage failed"
```

## Deployment Process

### Manual Deployment

```bash
# Deploy default site
uv run around-the-grounds --deploy

# Deploy a specific site
uv run around-the-grounds --site park-slope-music --deploy

# This command will:
# 1. Scrape all venue websites for the selected site
# 2. Authenticate using GitHub App JWT credentials
# 3. Prepare a working directory:
#    - If the site sets deploy_subdir="": `git init` a fresh repo
#    - If the site sets deploy_subdir="<name>": `git clone` the target repo
# 4. Copy the site-specific template from public_templates/<template>/ into
#    repo root (root mode) or repo/<deploy_subdir>/ (subdir mode)
# 5. Generate web-friendly JSON data (data.json) next to the template
# 6. Stage with `git add .` (root) or `git add <subdir>/` (subdir); skip empty commits
# 7. Commit with a per-site title
# 8. Push — `git push --force origin HEAD:main` (root) or normal push (subdir)
# 9. The target host (GitHub Pages or Vercel) picks up the change and redeploys
```

### Deployment Configuration

Each site has a `target_repo` and (optionally) a `deploy_subdir` configured in its JSON config file under `config/sites/`:

| Site | Target Repo | `deploy_subdir` | Strategy |
|------|-------------|-----------------|----------|
| `ballard-food-trucks` | `steveandroulakis/ballard-food-trucks` | `"public"` | Clone + scoped add to `public/`, normal push (Vercel reads `public/`) |
| `park-slope-music` | `jredding/atg-park-slope-music` | `""` (default) | Fresh `git init` + force-push to repo root (GitHub Pages) |
| `childrens-events` | `jredding/atg-childrens-events` | `""` (default) | Fresh `git init` + force-push to repo root (GitHub Pages) |

When `deploy_subdir` is non-empty, `_deploy_with_github_auth` switches to the clone strategy so that any files outside the subdirectory (e.g. `vercel.json`, `README.md`) are preserved on each deploy.

**Override via CLI**:
```bash
uv run around-the-grounds --deploy --git-repo https://github.com/username/custom-repo.git
```

**Configuration Precedence**:
1. CLI argument (`--git-repo`)
2. Environment variable (`GIT_REPOSITORY_URL`)
3. Site config `target_repo` field

## Scheduled Updates

### Cloud Run Jobs (jredding's production path)

Google Cloud Run Jobs run daily via Cloud Scheduler for jredding's Brooklyn sites:
- `atg-park-slope-music` — 8:15 AM ET
- `atg-childrens-events` — 8:30 AM ET

Each job scrapes its site and deploys to the corresponding GitHub Pages repo.

### Self-hosted Temporal Worker (Ballard production path)

The Ballard food trucks site is deployed by a Temporal worker running in a Docker container on a self-hosted machine. The worker connects to a Temporal server (Temporal Cloud or self-hosted) and picks up scheduled workflow executions. See [SCHEDULES.md](./SCHEDULES.md) for schedule management. The worker invokes the same Python entry points as the Cloud Run path — only the orchestrator differs.

### Temporal Workflows (Alternative)

For Temporal-based scheduling:

```bash
# Execute workflow with deployment
uv run python -m around_the_grounds.temporal.starter --deploy --verbose
```

See [SCHEDULES.md](./SCHEDULES.md) for Temporal schedule management documentation.

## Verifying Deployments

### Check Target Repository

```bash
# Clone a target repository
git clone https://github.com/jredding/atg-park-slope-music.git

# Check latest commit
cd atg-park-slope-music
git log -1

# Verify files are present
ls -la  # Should see: index.html, data.json
```

### Check Live Website

1. **Visit website**: Go to your GitHub Pages URL (e.g., `https://jredding.github.io/atg-park-slope-music/`)
2. **Verify data**: Check that latest events are showing
3. **Test mobile**: Verify responsive design on mobile viewport
4. **Check console**: Open browser dev tools, verify no JavaScript errors

### Monitor GitHub Pages Deployment

1. Go to the target repo on GitHub
2. Click **Settings** > **Pages**
3. Verify the site is deployed from the `main` branch root

## Troubleshooting

### No changes deployed

**Possible causes**:
- Data hasn't actually changed since last deployment
- Templates haven't been modified
- Git thinks there are no changes to commit

**Solutions**:
```bash
# Force deployment by updating timestamp
uv run around-the-grounds --deploy --verbose

# Check if data is actually different
diff public/data.json ~/path/to/ballard-food-trucks/data.json
```

### Website not updating

**Possible causes**:
- Git push to target repository failed
- GitHub Pages deployment is delayed (usually <1 minute)
- Browser cache showing old version

**Solutions**:
```bash
# Check target repository for latest commit
cd ~/path/to/atg-park-slope-music
git pull origin main
git log -1

# Force refresh browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)

# Check GitHub Pages deployment status in repo Settings > Pages
```

### Mobile display issues

**Possible causes**:
- Missing viewport meta tag
- CSS not loading properly
- JavaScript errors on mobile

**Solutions**:
```html
<!-- Ensure viewport meta tag in public_templates/<template>/index.html -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- Test responsive design locally -->
# Open browser dev tools (F12)
# Toggle device toolbar (Cmd+Shift+M)
# Test different viewport sizes
```

### Data fetching errors

**Possible causes**:
- `data.json` not generated correctly
- CORS issues (shouldn't happen with static hosting)
- JavaScript errors preventing fetch

**Solutions**:
```bash
# Verify data.json is valid JSON
cd public
cat data.json | python -m json.tool

# Check for syntax errors
jq . data.json  # If jq is installed

# Test data.json endpoint
curl -s http://localhost:8000/data.json | head -20
```

### Authentication errors

**Possible causes**:
- GitHub App credentials not configured
- Private key expired or invalid
- Repository permissions insufficient

**Solutions**:
```bash
# Verify environment variables are set
echo $GITHUB_APP_ID
echo $GITHUB_APP_PRIVATE_KEY_B64

# Check GitHub App installation
# Visit https://github.com/settings/installations
# Verify app is installed on target repository

# Test authentication
uv run around-the-grounds --deploy --verbose
# Check logs for authentication errors
```

See [DEPLOYMENT.MD](./DEPLOYMENT.MD) for GitHub App configuration details.

## Web Template Structure

### public_templates/

This directory contains per-site web interface templates:

- **`food-trucks/index.html`**: Ballard food trucks template
- **`music/index.html`**: Park Slope indie music template
- **`kids/index.html`**: Brooklyn children's events template

Each site's config specifies which template to use via the `template` field.

### Customizing the Web Interface

1. **Edit templates**: Modify files in `public_templates/<template>/`
2. **Test locally**: Run `--preview --site <key>` and serve locally
3. **Verify changes**: Check http://localhost:8000
4. **Deploy**: Run `--deploy --site <key>` to push changes to target repo

### Generated Files

During deployment, the system generates:

- **data.json**: Event data in web-friendly format
- **events.ics**: Subscribable calendar feed (see below)
- **Complete website**: Site-specific templates + generated data pushed to target repo root

## Calendar Feed (`events.ics`)

Every deploy and every `--preview` writes an RFC 5545 calendar feed next to `data.json`,
generated by `around_the_grounds/utils/ics_generator.py`. It covers the same rolling
7-day window as the website.

**Subscribing:**

The site shows a **Subscribe to calendar** disclosure menu next to the truck count. The options are named
explicitly rather than inferred from the user agent — no single mechanism reaches every
calendar, and UA sniffing silently strands anyone it guesses wrong about (a Proton or
Fastmail user on Android wants the feed URL, not Google). All four yield a **live
subscription** that keeps updating:

| Option | Target | Notes |
|---|---|---|
| Google | `calendar.google.com/calendar/r?cid=<webcal feed>` | Subscribe in a computer browser; Google then syncs to its mobile app |
| Apple | `webcal://.../events.ics` | OS protocol handler — Apple Calendar, and desktop Outlook/Thunderbird/Evolution where they claim the scheme. Does nothing on Android |
| Outlook | `outlook.live.com/calendar/0/addfromweb?url=<https feed>&name=<calendar name>` | `webcal://` does **not** reach Outlook *on the web*, which would fail silently. Subscribing here syncs down to desktop Outlook on the same account |
| Copy feed link | clipboard | For any client with an "add calendar from URL" field — Proton, Fastmail, Zoho, ICSx⁵. Proton has no deep link of any kind |

Live testing confirmed Outlook web accepts HTTPS with a prefilled `name`; webcal failed. The
`outlook.office.com` host is the work/Microsoft-365 equivalent; only the consumer
`outlook.live.com` variant is wired up, since this is a consumer-facing site.

Deliberately omitted: Yahoo Calendar (no subscribe deep link, only single-event, and its
share has collapsed) and every provider without a deep link — those are served by Copy.

The menu explains that the subscription includes all trucks in a separate calendar and that
refresh timing varies by app. It supports keyboard navigation, Escape, and outside-click
dismissal. Copy falls back to `execCommand` when `navigator.clipboard` is
unavailable, which is the case on any non-secure origin (i.e. LAN testing over plain http).

There is deliberately no `.ics` download option: it produces a dead snapshot rather than a
subscription, which is a confusing thing to offer next to three live ones.

> **Testing caveat:** the Google and Outlook options cannot be tested against `localhost`
> or a LAN IP. Both providers fetch the feed from their own servers, so the URL must be
> publicly reachable over https. Use the production site or a tunnel
> (`ssh -R 80:localhost:8000 nokey@localhost.run`). Apple and Copy work fine locally.

Subscribers see events drop off as they pass — the feed is a live 7-day window, not an archive.

**Branding and subscriber expectations:**

An optional `public_url` in each site's config supplies the public homepage. Ballard sets
it to `https://ballardfoodtrucks.com` and uses the name `Ballard Food Trucks`. The value
passes through both CLI web data and Temporal site serialization (older payloads default
to an empty URL). When configured, every entry links to the homepage in both `URL` and
`DESCRIPTION`, with attribution and a reminder to check the latest schedule. Titles stay
focused on the event and venue. Without `public_url`, entries retain their venue URL and
receive no homepage attribution; the music and kids templates remain unchanged.

All entries use `TRANSP:TRANSPARENT` (free availability) and contain no `VALARM`. Clients
may still apply subscribers' own reminder preferences. All-day entries say "Hours not
published"; the default three-hour duration is explicitly labeled as an estimated end.
Per-venue subscriptions and retaining events through scrape failures are separate work.

**Two properties to preserve if you touch the generator:**

1. **Output must be deterministic.** `DTSTAMP` is derived from the event's own start time, never
   `datetime.now()`. A "now" value would make the file differ on every scrape and defeat the
   `git diff --staged --quiet` no-op short-circuit in `_deploy_with_github_auth`, producing an
   empty commit (and a Vercel redeploy) every hour.
2. **UIDs must stay stable.** They're a sha1 of `site_key|venue_key|date|title`, so a truck keeps
   the same calendar entry across refreshes rather than duplicating in subscribers' calendars.

Verify the feed after a deploy:

```bash
# Should report Content-Type: text/calendar (Vercel and GitHub Pages both map .ics by default)
curl -I https://ballardfoodtrucks.com/events.ics

# Round-trip parse locally
uv run python -c "from icalendar import Calendar; \
  print(len(Calendar.from_ical(open('public/events.ics','rb').read()).walk('VEVENT')), 'events')"
```

Only the `food-trucks` template surfaces a subscribe link today; the `music` and `kids` sites
generate the file but have no UI link yet.

## Best Practices

1. **Test locally first**: Always run `--preview --site <key>` before `--deploy`
2. **Check data.json**: Verify generated JSON is valid and contains expected data
3. **Monitor deployments**: Check GitHub Pages status in target repo Settings
4. **Use version control**: Keep track of template changes in source repository
5. **Set up schedules**: Use Cloud Scheduler or Temporal for automated regular updates
6. **Handle errors gracefully**: System continues even if some venues fail
7. **Log verbosely**: Use `--verbose` flag for troubleshooting
8. **Test responsive design**: Check mobile viewport before deploying

## Deployment Checklist

Before deploying:

- [ ] Templates in `public_templates/<template>/` are up to date
- [ ] GitHub App credentials are configured
- [ ] GitHub App installed on target repository
- [ ] GitHub Pages enabled on target repository (deploy from main branch root)
- [ ] Local preview tested and working
- [ ] Data.json contains expected events
- [ ] Mobile responsive design verified

After deploying:

- [ ] Target repository received latest commit
- [ ] GitHub Pages deployment completed successfully
- [ ] Live website shows updated data
- [ ] No JavaScript errors in browser console
- [ ] Mobile view works correctly
- [ ] All venue data is present

Google subscription links must pass the `webcal://` feed URL to `cid`; the HTTPS
variant failed on the live site despite a valid feed. Copy calendar link keeps HTTPS
for manual add-by-URL. Apple uses webcal; Outlook web uses HTTPS with the calendar name.
The Apple option advises turning off Event Alerts. The feed contains no alarms, but
subscription alert preferences are controlled by the calendar app, not the feed.

Obec food-truck hours without AM/PM default to afternoon/evening (1–11 means PM;
12 means noon). Explicit AM/PM and zero-padded/24-hour times are preserved. This
assumption is confined to the Obec parser, not shared with other sites.
