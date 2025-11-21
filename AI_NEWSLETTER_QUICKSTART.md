# AI Newsletter - Quick Start Guide

Get your AI newsletter up and running in 15 minutes!

## Prerequisites Checklist

- [ ] Docker & Docker Compose installed
- [ ] LMStudio installed and running on port 1234
- [ ] Llama 3.1-8b model downloaded in LMStudio
- [ ] Reddit account (for API access)

## 5-Minute Setup

### Step 1: Get Reddit API Credentials (2 minutes)

1. Visit https://www.reddit.com/prefs/apps
2. Click "Create App"
3. Fill in:
   - **Name**: AI Newsletter Bot
   - **Type**: Select "script"
   - **Redirect URI**: http://localhost:8080
4. Click "Create app"
5. Copy your **client_id** (under the app name) and **client_secret**

### Step 2: Configure Environment (1 minute)

Add to your `.env` file:

```bash
# Reddit API Credentials
REDDIT_CLIENT_ID=paste_your_client_id_here
REDDIT_CLIENT_SECRET=paste_your_client_secret_here
```

### Step 3: Initialize Database (2 minutes)

```bash
# Run database initialization
docker exec -i arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader < database/init_ai_newsletter.sql
```

### Step 4: Start Services (1 minute)

```bash
# Build and start AI newsletter services
docker-compose up -d ai-news-aggregator newsletter-generator newsletter-publisher
```

### Step 5: Verify Everything Works (1 minute)

```bash
# Check services are running
docker-compose ps | grep "newsletter\|aggregator"

# Expected output:
# arth360-ai-aggregator             running
# arth360-newsletter-generator      running
# arth360-newsletter-publisher      running

# Check logs
docker-compose logs --tail=20 ai-news-aggregator
```

## Test the System

### Option A: Quick Test (5 minutes)

Wait 5 minutes for the aggregator to collect some articles, then check:

```bash
# Check collected articles
docker exec -it arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader -e "
  SELECT COUNT(*) as total,
         MAX(published_at) as latest
  FROM ai_news_articles;
"
```

### Option B: Generate Test Newsletter (10 minutes)

Manually trigger newsletter generation:

```bash
# 1. Generate newsletter
docker exec -it arth360-newsletter-generator python << 'EOF'
from generator import NewsletterGenerator
from datetime import datetime
import pytz

gen = NewsletterGenerator()
ist = pytz.timezone('Asia/Kolkata')
edition_id = gen.generate_newsletter(datetime.now(ist))
print(f"Generated edition ID: {edition_id}")
EOF

# 2. Publish as PDF
docker exec -it arth360-newsletter-publisher python << 'EOF'
from publisher import NewsletterPublisher

pub = NewsletterPublisher()
count = pub.publish_editions()
print(f"Published {count} edition(s)")
EOF

# 3. Copy PDF to local machine
docker cp arth360-newsletter-publisher:/app/output/ ./newsletters/
```

## Production Schedule

Once setup is complete, the system runs automatically:

### Monday & Thursday Schedule (IST)

| Time | Service | Action |
|------|---------|--------|
| Every 2 hours | AI News Aggregator | Collect articles from Reddit & RSS |
| Sunday 11:00 PM | Newsletter Generator | Generate Monday edition |
| Monday 8:00 AM | Newsletter Publisher | Publish Monday PDF |
| Wednesday 11:00 PM | Newsletter Generator | Generate Thursday edition |
| Thursday 8:00 AM | Newsletter Publisher | Publish Thursday PDF |

## What to Expect

### First 2 Hours
- Aggregator collects 50-100 articles
- Articles categorized by AI value chain area
- Relevance scores calculated

### First 4 Days
- 200-300 articles collected
- Sufficient data for first newsletter

### First Newsletter
- 5 sections covering AI value chain
- ~2,500 words total
- Professional PDF format
- Storytelling style (NYT/The Ken quality)

## Next Steps

1. **Monitor collection**: Check logs for article collection
2. **Wait for first newsletter**: Let it run until Monday/Thursday
3. **Review PDF**: Check quality and make adjustments
4. **Customize**: Edit prompts, add sources, adjust schedule

## Quick Commands Reference

```bash
# View aggregator logs
docker-compose logs -f ai-news-aggregator

# View generator logs
docker-compose logs -f newsletter-generator

# Check article stats
docker exec -it arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader -e "
  SELECT value_chain_area, COUNT(*) as count
  FROM ai_news_articles
  WHERE published_at > DATE_SUB(NOW(), INTERVAL 7 DAYS)
  GROUP BY value_chain_area;
"

# List generated PDFs
docker exec arth360-newsletter-publisher ls -lh /app/output/

# Restart a service
docker-compose restart ai-news-aggregator
```

## Troubleshooting

### "No articles collected"
→ Check Reddit API credentials in `.env`
→ Verify RSS feeds are accessible: `docker-compose logs ai-news-aggregator`

### "LMStudio connection failed"
→ Ensure LMStudio is running: `curl http://localhost:1234/v1/models`
→ Check firewall isn't blocking port 1234

### "Newsletter generation failed"
→ Wait for more articles (need 4 days of data)
→ Check LLM is responding: `docker-compose logs newsletter-generator`

### "PDF not generated"
→ Check WeasyPrint installation: `docker-compose logs newsletter-publisher`
→ Verify newsletter edition exists in database

## Support

See [AI_NEWSLETTER_README.md](AI_NEWSLETTER_README.md) for detailed documentation.

---

**Ready to go!** Your AI newsletter system is now running. First newsletter will be generated on the next Monday or Thursday.
