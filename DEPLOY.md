# 🚀 Deployment Guide

This guide walks you through setting up your own food truck tracking website using Around the Grounds, deployed automatically to Vercel.

## 🌟 What You'll Get

- **Live Website**: Mobile-responsive food truck schedule (like [ballard-food-trucks.around-the-grounds.vercel.app](https://ballard-food-trucks.around-the-grounds.vercel.app))
- **Auto-Updates**: Scheduled data refreshes via Temporal or cron
- **Custom Domain**: Optional custom domain like `foodtrucksballard.com`
- **Zero Maintenance**: Automatic deployments via git integration
- **Mobile-First**: Perfect for checking schedules on your phone

## 📋 Prerequisites

- GitHub account
- Vercel account (free)
- Optional: Domain name (~$15/year)
- Optional: Anthropic API key for AI vision analysis

## 🚀 Quick Start (5 minutes)

### 1. Fork the Repository

1. Go to [https://github.com/steveandroulakis/around-the-grounds](https://github.com/steveandroulakis/around-the-grounds)
2. Click "Fork" to create your own copy
3. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/around-the-grounds
   cd around-the-grounds
   ```

### 2. Deploy to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click "New Project"
3. Import your forked repository
4. Configure deployment settings:
   - **Build Command**: `echo "No build needed"`
   - **Output Directory**: `public`
   - **Install Command**: `echo "No install needed"`
5. Click "Deploy"

Your site will be live at `https://your-project-name.vercel.app` within minutes!

### 3. Test the Deployment

1. **Test CLI locally**:
   ```bash
   uv sync
   uv run around-the-grounds
   ```

2. **Test web deployment**:
   ```bash
   uv run around-the-grounds --deploy
   ```

3. **Check your live site**: Visit your Vercel URL to see the updated data

## 🏗️ Detailed Setup

### Environment Variables (Optional)

For AI vision analysis, add environment variables in Vercel dashboard:

1. Go to your Vercel project dashboard
2. Navigate to "Settings" → "Environment Variables"
3. Add:
   - `ANTHROPIC_API_KEY`: Your Claude API key
   - `VISION_ANALYSIS_ENABLED`: `true`

### Custom Domain Setup

#### Option A: Buy Domain Through Vercel
1. In Vercel dashboard, go to "Settings" → "Domains"
2. Click "Buy Domain"
3. Purchase your domain (e.g., `foodtrucksballard.com`)
4. DNS is automatically configured

#### Option B: Use External Domain
1. Buy domain from your preferred registrar
2. In Vercel dashboard, go to "Settings" → "Domains"
3. Add your domain
4. Update DNS records as instructed by Vercel

### Local Development Setup

```bash
# Clone and setup
git clone https://github.com/yourusername/around-the-grounds
cd around-the-grounds
uv sync --dev

# Test CLI
uv run around-the-grounds --verbose

# Test with vision analysis (optional)
export ANTHROPIC_API_KEY="your-api-key"
uv run around-the-grounds --verbose

# Test web deployment
uv run around-the-grounds --deploy
```

## ⏰ Scheduling Updates

### Option A: Temporal (Recommended)

Create a Temporal workflow to run twice daily:

```python
import asyncio
import subprocess
from datetime import timedelta
from temporalio import workflow

@workflow.defn
class FoodTruckUpdateWorkflow:
    @workflow.run
    async def run(self) -> str:
        try:
            # Run the full pipeline: scrape → generate JSON → commit → deploy
            result = subprocess.run([
                'uv', 'run', 'around-the-grounds', 
                '--deploy', '--verbose'
            ], capture_output=True, text=True, check=True)
            
            return f"✅ Successfully updated food truck data: {result.stdout}"
            
        except subprocess.CalledProcessError as e:
            return f"❌ Update failed: {e.stderr}"

# Schedule to run twice daily
@workflow.defn
class FoodTruckScheduleWorkflow:
    @workflow.run
    async def run(self) -> None:
        while True:
            # Run at 8 AM and 6 PM
            await workflow.start_child_workflow(
                FoodTruckUpdateWorkflow.run,
            )
            await asyncio.sleep(timedelta(hours=12))
```

### Option B: GitHub Actions

Create `.github/workflows/update-data.yml`:

```yaml
name: Update Food Truck Data

on:
  schedule:
    - cron: '0 8,18 * * *'  # 8 AM and 6 PM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
        
      - name: Install dependencies
        run: uv sync
        
      - name: Update food truck data
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: uv run around-the-grounds --deploy
```

### Option C: Cron Job

On a server or VPS:

```bash
# Edit crontab
crontab -e

# Add lines for 8 AM and 6 PM daily
0 8 * * * cd /path/to/around-the-grounds && uv run around-the-grounds --deploy
0 18 * * * cd /path/to/around-the-grounds && uv run around-the-grounds --deploy
```

## 🎨 Customizing Your Site

### Update Site Title and Branding

Edit `public/index.html`:

```html
<title>Your City Food Trucks</title>
<h1>🍺 Your City Food Trucks</h1>
<p>Your guide to brewery food trucks around [Your City]</p>
```

### Modify Styling

The CSS is embedded in `public/index.html`. Key customization points:

```css
/* Change color scheme */
.header {
    background: linear-gradient(135deg, #your-color 0%, #your-color2 100%);
}

/* Update accent colors */
.day-header {
    border-bottom: 2px solid #your-accent-color;
}
```

### Add New Breweries

See the [main README](README.md#adding-new-breweries) for detailed instructions on adding brewery parsers.

## 📊 Monitoring & Analytics

### Vercel Analytics

1. In Vercel dashboard, go to "Analytics"
2. Enable analytics for your project
3. View traffic, performance, and user engagement

### Custom Monitoring

Add health checks to your Temporal workflow:

```python
async def health_check():
    try:
        response = requests.get('https://your-domain.com/data.json')
        data = response.json()
        
        # Check data freshness
        updated = datetime.fromisoformat(data['updated'])
        if datetime.now() - updated > timedelta(days=1):
            alert("Food truck data is stale!")
            
        # Check event count
        if data['total_events'] < 5:
            alert("Very few events found - possible scraping issue")
            
    except Exception as e:
        alert(f"Health check failed: {e}")
```

## 💰 Cost Breakdown

### Free Tier (Recommended for personal use)
- **Vercel hosting**: Free (generous limits)
- **GitHub**: Free
- **Anthropic API**: $5/month for light usage
- **Total**: ~$5/month

### With Custom Domain
- **Domain**: ~$10-15/year
- **Everything else**: Same as above
- **Total**: ~$10-20/year + $5/month for API

### Production Scale
- **Vercel Pro**: $20/month (if you exceed free limits)
- **Domain**: ~$15/year
- **Anthropic API**: $20+/month for heavy usage
- **Total**: ~$25-45/month

## 🔧 Troubleshooting

### Common Issues

#### Website Not Updating
```bash
# Check if deployment succeeded
git log --oneline -n 5

# Manually trigger deployment
uv run around-the-grounds --deploy

# Check Vercel deployment status
vercel ls
```

#### Data Not Loading
1. Check browser console for errors
2. Verify `data.json` exists and is valid:
   ```bash
   curl https://your-domain.com/data.json | python -m json.tool
   ```
3. Check Vercel deployment logs

#### Mobile Display Issues
1. Test on actual mobile device
2. Use browser dev tools mobile simulation
3. Check viewport meta tag in HTML
4. Verify responsive CSS breakpoints

#### Scraping Failures
```bash
# Run with verbose logging
uv run around-the-grounds --verbose

# Test individual brewery parsers
uv run python -m pytest tests/parsers/ -v

# Check network connectivity
curl -I https://www.stoupbrewing.com/ballard/
```

### Getting Help

1. **Check logs**: Use `--verbose` flag for detailed output
2. **Run tests**: `uv run python -m pytest` to verify everything works
3. **GitHub Issues**: Report bugs at [GitHub repo](https://github.com/steveandroulakis/around-the-grounds/issues)
4. **Vercel Support**: Check Vercel deployment logs and documentation

## 🚀 Advanced Features

### Custom Data Sources

Add your own brewery parsers - see [CLAUDE.md](CLAUDE.md#adding-new-breweries) for detailed instructions.

### API Endpoints

The web deployment creates these endpoints:
- `GET /`: Main website
- `GET /data.json`: Raw food truck data (CORS-enabled)

Use the JSON endpoint for:
- Mobile apps
- Third-party integrations
- Data analysis
- Custom frontends

### Webhook Integration

Set up webhooks to notify other services when data updates:

```python
# Add to your deployment function
import requests

def notify_webhook(events):
    webhook_url = os.getenv('WEBHOOK_URL')
    if webhook_url:
        requests.post(webhook_url, json={
            'event': 'food_trucks_updated',
            'total_events': len(events),
            'timestamp': datetime.now().isoformat()
        })
```

## 📈 Performance Optimization

### Caching Strategy

The current setup uses:
- **Vercel Edge Cache**: Automatic CDN caching
- **Browser Cache**: JSON data cached for performance
- **Git-based updates**: Only deploys when data actually changes

### Scaling Considerations

- **Multiple cities**: Create separate deployments per city
- **High traffic**: Upgrade to Vercel Pro for better performance
- **Multiple updates**: Consider rate limiting for API calls

## 🎯 Next Steps

1. **Set up monitoring**: Add health checks and alerts
2. **Customize design**: Update colors and branding for your city
3. **Add more breweries**: Expand coverage with additional parsers
4. **Mobile app**: Use the JSON API to build a mobile app
5. **Analytics**: Track usage patterns and popular food trucks

---

**Need help?** Open an issue on [GitHub](https://github.com/steveandroulakis/around-the-grounds/issues) or check the troubleshooting section above.