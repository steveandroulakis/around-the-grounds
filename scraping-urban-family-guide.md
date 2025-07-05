# Scraping Urban Family Brewing Calendar Guide

## Overview

Urban Family Brewing uses a client-side JavaScript application that dynamically loads calendar data from an API endpoint. The public calendar page (`https://app.hivey.io/urbanfamily/public-calendar`) only returns minimal HTML with "Hivey" text, but the actual calendar data is fetched via AJAX calls to a separate API.

## The Problem with Standard HTML Scraping

When you make a standard HTTP request to `https://app.hivey.io/urbanfamily/public-calendar`, you only get:
- Basic HTML structure
- JavaScript code that runs in the browser
- No actual calendar/event data

The calendar data is loaded after the page loads through JavaScript making API calls, so traditional HTML parsing won't work.

## The Solution: Direct API Access

### Discovery Process

Using browser developer tools (Network tab), you can observe the actual API calls:

1. Open `https://app.hivey.io/urbanfamily/public-calendar` in Chrome/Firefox
2. Open Developer Tools → Network tab
3. Look for XHR/Fetch requests
4. Find the API endpoint that returns JSON data

### API Endpoint Details

**URL**: `https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar`

**Method**: GET

**Response**: JSON data containing calendar events

### Required Headers

The API requires specific headers to authenticate/authorize the request (CORS validation):

```bash
curl 'https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: en,en-US;q=0.9,fr;q=0.8,vi;q=0.7,th;q=0.6' \
  -H 'origin: https://app.hivey.io' \
  -H 'referer: https://app.hivey.io/' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
```

### Why These Headers Matter

1. **`origin`** and **`referer`**: Tell the API server where the request originated from. Many APIs check these for CORS (Cross-Origin Resource Sharing) validation to prevent unauthorized access.

2. **`user-agent`**: Makes the request appear to come from a real browser rather than a script. Some APIs block requests that don't have realistic user agents.

3. **`accept`**: Specifies that we want JSON data, which helps the server return the correct content type.

4. **`accept-language`**: Indicates language preferences, may affect localized content.

## Python Implementation

### Using aiohttp (Recommended for async projects)

```python
import aiohttp
import asyncio

async def fetch_urban_family_calendar():
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en,en-US;q=0.9,fr;q=0.8,vi;q=0.7,th;q=0.6',
        'origin': 'https://app.hivey.io',
        'referer': 'https://app.hivey.io/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar',
            headers=headers
        ) as response:
            return await response.json()

# Usage
data = asyncio.run(fetch_urban_family_calendar())
```

### Using requests (For synchronous projects)

```python
import requests

def fetch_urban_family_calendar():
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en,en-US;q=0.9,fr;q=0.8,vi;q=0.7,th;q=0.6',
        'origin': 'https://app.hivey.io',
        'referer': 'https://app.hivey.io/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    }
    
    response = requests.get(
        'https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar',
        headers=headers
    )
    return response.json()

# Usage
data = fetch_urban_family_calendar()
```

## Integration Notes

### For Existing HTML Scraping Projects

If you have an existing project that:
1. Makes simple HTTP requests to brewery websites
2. Parses HTML with BeautifulSoup
3. Extracts calendar/event data

You'll need to:
1. **Change the target URL** from the public calendar page to the API endpoint
2. **Add the required headers** to your HTTP request
3. **Switch from HTML parsing to JSON parsing** - no more BeautifulSoup needed
4. **Update your data extraction logic** to work with JSON structure instead of HTML elements

### Benefits of API Access

- **Faster**: No need to download and parse HTML
- **More reliable**: No dependency on HTML structure changes
- **Cleaner data**: JSON is structured and doesn't require complex parsing
- **Less bandwidth**: Only the data you need, no HTML/CSS/JS

### Potential Issues

1. **API changes**: The endpoint URL or required headers might change
2. **Rate limiting**: The API might implement rate limiting
3. **Authentication**: Future versions might require API keys
4. **Data format changes**: The JSON structure might evolve

### Testing the API

Before integrating, test the API endpoint:

```bash
# Test with curl
curl 'https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar' \
  -H 'origin: https://app.hivey.io' \
  -H 'referer: https://app.hivey.io/' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
```

Examine the JSON response structure to understand what data is available and how to parse it for your specific use case.