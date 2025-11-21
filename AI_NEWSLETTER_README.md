# AI Newsletter System

A fully automated AI newsletter generation system that publishes comprehensive AI industry updates every Monday and Thursday at 8:00 AM IST.

## Overview

The AI Newsletter system collects news from multiple sources (Reddit, RSS feeds), analyzes them using AI, and generates professional PDF newsletters covering the entire AI value chain:

- **Silicon & Infrastructure** (chips, GPUs, hardware)
- **Models & Research** (new models, papers, breakthroughs)
- **Applications & Products** (consumer apps, enterprise tools)
- **Policy & Governance** (regulations, ethics, laws)
- **Business & Markets** (funding, M&A, strategy)

## Architecture

The system consists of three microservices:

### 1. AI News Aggregator (`ai-news-aggregator/`)
- **Schedule**: Runs every 2 hours
- **Function**: Collects AI news from Reddit and RSS feeds
- **Sources**:
  - Reddit: r/MachineLearning, r/artificial, r/LocalLLaMA, r/StableDiffusion, etc.
  - RSS: TechCrunch, VentureBeat, The Verge, arXiv, OpenAI, Google AI, etc.
- **Output**: Stores articles in `ai_news_articles` table with relevance scores

### 2. Newsletter Generator (`newsletter-generator/`)
- **Schedule**: Sunday 11 PM IST (for Monday) & Wednesday 11 PM IST (for Thursday)
- **Function**: Curates articles and generates 5-section newsletter
- **Process**:
  1. Fetches articles from last 96 hours (4 days)
  2. Scores and ranks by relevance, recency, engagement
  3. Selects top 5 articles per value chain category
  4. Generates story-driven content using LLama 3.1-8b
  5. Saves to `newsletter_editions` table
- **Output**: Structured newsletter with ~500 words per section

### 3. Newsletter Publisher (`newsletter-publisher/`)
- **Schedule**: Monday & Thursday at 8:00 AM IST
- **Function**: Generates PDF and publishes newsletter
- **Process**:
  1. Fetches unpublished newsletter editions
  2. Renders HTML template with Jinja2
  3. Generates professional PDF using WeasyPrint
  4. Saves to `newsletter_pdfs` volume
  5. Marks as published in database
- **Output**: PDF file (e.g., `AI_Newsletter_Edition_1_20250120.pdf`)

## Setup Instructions

### Prerequisites

1. **Docker & Docker Compose** installed
2. **LMStudio** running locally on port 1234 with Llama 3.1-8b model
3. **Reddit API credentials** (free tier)
4. **MySQL database** (handled by docker-compose)

### Step 1: Reddit API Setup

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in:
   - Name: AI Newsletter Aggregator
   - Type: Script
   - Redirect URI: http://localhost:8080
4. Note your `client_id` and `client_secret`

### Step 2: Environment Variables

Add to your `.env` file:

```bash
# Existing variables
DB_HOST=mysql
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=rss_reader

# Reddit API (new)
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=AI Newsletter Aggregator v1.0

# LMStudio (existing)
LMSTUDIO_URL=http://host.docker.internal:1234/v1/chat/completions
```

### Step 3: Database Initialization

Initialize the AI newsletter tables:

```bash
# Connect to MySQL
mysql -u root -p rss_reader

# Run initialization script
source database/init_ai_newsletter.sql
```

Or run from Docker:

```bash
docker exec -i arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader < database/init_ai_newsletter.sql
```

### Step 4: LMStudio Setup

1. Download and install LMStudio from https://lmstudio.ai
2. Download the **Llama 3.1-8b Instruct** model
3. Start the local server on port 1234
4. Verify: `curl http://localhost:1234/v1/models`

### Step 5: Build and Start Services

```bash
# Build base image (if not already built)
docker build -f Dockerfile.base -t arth360-base:latest .

# Build and start all services
docker-compose up -d

# Or start only AI newsletter services
docker-compose up -d ai-news-aggregator newsletter-generator newsletter-publisher
```

### Step 6: Verify Services

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f ai-news-aggregator
docker-compose logs -f newsletter-generator
docker-compose logs -f newsletter-publisher

# Check database
docker exec -it arth360-mysql mysql -u root -p${DB_PASSWORD} -e "
  SELECT COUNT(*) as total_articles FROM rss_reader.ai_news_articles;
  SELECT * FROM rss_reader.v_newsletter_stats;
"
```

## Database Schema

### Main Tables

- **`ai_news_sources`** - Configuration of RSS feeds and Reddit sources
- **`ai_news_articles`** - Collected articles with relevance scores
- **`newsletter_editions`** - Generated newsletter editions
- **`newsletter_sections`** - Individual sections of each newsletter
- **`newsletter_published`** - Publishing tracking and PDF metadata

### Useful Views

- **`v_unpublished_articles`** - Articles not yet processed for newsletter
- **`v_newsletter_stats`** - Newsletter statistics and status

## Usage

### Manual Newsletter Generation

To manually trigger newsletter generation:

```bash
# Connect to generator container
docker exec -it arth360-newsletter-generator python -c "
from generator import NewsletterGenerator
from datetime import datetime
import pytz

gen = NewsletterGenerator()
ist = pytz.timezone('Asia/Kolkata')
publish_date = datetime.now(ist)
edition_id = gen.generate_newsletter(publish_date)
print(f'Generated edition: {edition_id}')
"
```

### Manual PDF Publishing

To manually publish a newsletter:

```bash
# Connect to publisher container
docker exec -it arth360-newsletter-publisher python -c "
from publisher import NewsletterPublisher

pub = NewsletterPublisher()
count = pub.publish_editions()
print(f'Published {count} edition(s)')
"
```

### Accessing PDFs

PDFs are stored in the `newsletter_pdfs` Docker volume:

```bash
# List PDFs
docker exec arth360-newsletter-publisher ls -lh /app/output/

# Copy PDF to local machine
docker cp arth360-newsletter-publisher:/app/output/AI_Newsletter_Edition_1_20250120.pdf ./
```

Or mount a local directory in docker-compose.yml:

```yaml
volumes:
  - ./newsletters:/app/output
```

## Monitoring

### Check Collection Stats

```bash
docker exec -it arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader -e "
  SELECT
    value_chain_area,
    COUNT(*) as article_count,
    AVG(relevance_score) as avg_relevance,
    MAX(published_at) as latest_article
  FROM ai_news_articles
  WHERE published_at > DATE_SUB(NOW(), INTERVAL 7 DAYS)
  GROUP BY value_chain_area;
"
```

### View Newsletter Status

```bash
docker exec -it arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader -e "
  SELECT * FROM v_newsletter_stats ORDER BY edition_number DESC LIMIT 5;
"
```

### Monitor Logs

```bash
# Aggregator logs
docker exec arth360-ai-aggregator tail -f logs/aggregator.log

# Generator logs
docker exec arth360-newsletter-generator tail -f logs/generator.log

# Publisher logs
docker exec arth360-newsletter-publisher tail -f logs/publisher.log
```

## Customization

### Adjust Collection Schedule

Edit `ai-news-aggregator/aggregator.py`:

```python
# Change from 2 hours to 1 hour
aggregator.run(interval_hours=1)
```

### Modify Newsletter Sections

Edit `newsletter-generator/prompts.py` to customize:
- Section titles
- Writing style prompts
- Value chain categories

### Change Publishing Schedule

Edit `newsletter-generator/generator.py` and `newsletter-publisher/publisher.py`:

```python
# Current: Sunday/Wednesday 11 PM for Mon/Thu publish
# Change to different days/times

# In generator.py
should_generate = (
    (weekday == 6 and hour == 23) or  # Sunday 11 PM
    (weekday == 2 and hour == 23)     # Wednesday 11 PM
)

# In publisher.py
should_publish = (
    (weekday == 0 or weekday == 3) and  # Monday or Thursday
    hour == 8 and minute == 0            # 8:00 AM
)
```

### Add More Sources

Edit `database/init_ai_newsletter.sql` to add sources:

```sql
INSERT INTO ai_news_sources (source_type, source_name, source_url, category, active) VALUES
('rss', 'Your Source', 'https://example.com/feed', 'general', TRUE);
```

Or insert via MySQL:

```bash
docker exec -it arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader -e "
  INSERT INTO ai_news_sources (source_type, source_name, source_url, category, active)
  VALUES ('rss', 'Your Source', 'https://example.com/feed', 'general', TRUE);
"
```

## Troubleshooting

### Issue: No articles collected

**Check:**
1. Reddit API credentials are correct
2. RSS feeds are accessible
3. Database connection is working

**Debug:**
```bash
docker-compose logs ai-news-aggregator | grep -i error
```

### Issue: Newsletter generation fails

**Check:**
1. LMStudio is running and accessible
2. Sufficient articles collected (need 3+ per category)
3. Database has articles from last 96 hours

**Debug:**
```bash
# Test LMStudio connection
curl http://localhost:1234/v1/models

# Check article counts
docker exec -it arth360-mysql mysql -u root -p${DB_PASSWORD} rss_reader -e "
  SELECT value_chain_area, COUNT(*) FROM ai_news_articles
  WHERE published_at > DATE_SUB(NOW(), INTERVAL 96 HOUR)
  GROUP BY value_chain_area;
"
```

### Issue: PDF generation fails

**Check:**
1. WeasyPrint dependencies installed correctly
2. Template file exists
3. Sufficient disk space

**Debug:**
```bash
docker-compose logs newsletter-publisher | grep -i error
```

### Issue: Services not starting

**Check:**
1. MySQL is healthy: `docker-compose ps mysql`
2. Port 1234 accessible from containers
3. All environment variables set

**Debug:**
```bash
docker-compose logs mysql
docker-compose logs ai-news-aggregator
```

## File Structure

```
/Users/rc/Projects/Arth360/
├── ai-news-aggregator/
│   ├── aggregator.py          # Main orchestrator
│   ├── reddit_collector.py    # Reddit API integration
│   ├── rss_collector.py        # RSS feed collection
│   ├── requirements.txt
│   ├── Dockerfile
│   └── logs/
├── newsletter-generator/
│   ├── generator.py            # Newsletter generation
│   ├── curator.py              # Article curation
│   ├── prompts.py              # LLM prompts
│   ├── requirements.txt
│   ├── Dockerfile
│   └── logs/
├── newsletter-publisher/
│   ├── publisher.py            # PDF publishing
│   ├── templates/
│   │   └── newsletter.html    # PDF template
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── logs/
│   └── output/                 # Generated PDFs
├── database/
│   └── init_ai_newsletter.sql # Database schema
└── docker-compose.yml          # Service orchestration
```

## Performance

### Expected Resource Usage

- **AI News Aggregator**: ~100 MB RAM, minimal CPU
- **Newsletter Generator**: ~500 MB RAM during generation (LLM calls)
- **Newsletter Publisher**: ~300 MB RAM during PDF generation

### Article Collection Rate

- **RSS Feeds**: ~50-100 articles per 2-hour cycle
- **Reddit**: ~30-50 posts per 2-hour cycle
- **Total**: ~200-300 articles per week

### Newsletter Generation Time

- Article curation: ~10-15 seconds
- LLM generation (5 sections): ~3-5 minutes (with Llama 3.1-8b)
- PDF rendering: ~5-10 seconds
- **Total**: ~5-10 minutes per edition

## Credits

Built using:
- Python 3.9
- LMStudio (Llama 3.1-8b)
- WeasyPrint (PDF generation)
- PRAW (Reddit API)
- MySQL 8.0
- Docker

---

**Questions or Issues?**

Check the logs, verify your configuration, and ensure all dependencies are properly installed.
