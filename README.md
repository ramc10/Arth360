# Arth360 - AI-Powered Financial News & Research Platform

[![Join Telegram Channel](https://img.shields.io/badge/Join%20Telegram-Arth360-blue)](https://t.me/artha360)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](docker-compose.yml)

> Automated news aggregation and AI-powered research brief generation platform for financial markets.

## 🎯 Overview

Arth360 is a microservices-based platform that collects financial news from multiple sources, processes it with AI, and generates comprehensive research briefs for tracked companies. The system runs continuously, aggregating news from 35+ RSS feeds and delivering AI-analyzed insights through Telegram.

### Key Features

- 📰 **Multi-Source News Aggregation** - Collects from 35+ RSS feeds (Reuters, CNBC, TechCrunch, Economic Times, Mint, etc.)
- 🤖 **AI-Powered Analysis** - Uses local LLM (Llama 3.1-8b) to summarize and analyze articles
- 📊 **Real-Time Financial Data** - Integrates live stock data via Alpha Vantage API
- 🔍 **Automated Research Briefs** - Generates daily company research with sentiment analysis
- 📱 **Telegram Publishing** - Auto-publishes curated content to Telegram channels
- 🐳 **Fully Containerized** - Docker-based deployment for easy scaling
- 🔄 **Intelligent Retry Logic** - Enhanced content extraction with fallback mechanisms
- 💾 **Smart Caching** - Optimized API usage with 24-hour cache for stock fundamentals

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Feeder    │────▶│   Content   │────▶│  Publisher  │────▶│  Telegram   │
│  (RSS Feed) │     │ (Processor) │     │   (Output)  │     │   Channel   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                    │
       │                    │
       ▼                    ▼
┌─────────────────────────────────┐     ┌──────────────────┐
│         MySQL Database          │◀────│    Research      │
│  (Articles, Briefs, Tracking)   │     │    Service       │
└─────────────────────────────────┘     └──────────────────┘
                                               ▲      ▲
                                               │      │
                                        ┌──────┴──┐  │
                                        │LMStudio │  │
                                        │(Llama3) │  │
                                        └─────────┘  │
                                                     │
                                        ┌────────────┴──────┐
                                        │  Alpha Vantage    │
                                        │  (Stock Data API) │
                                        └───────────────────┘
                                               ▲
                                               │
                                        ┌──────────────────┐
                                        │Research Publisher│
                                        │    Service       │
                                        └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Docker Desktop** (macOS/Windows) or **Docker Engine + docker-compose** (Linux)
- **LMStudio** (for AI analysis) - [Download](https://lmstudio.ai)
- **Alpha Vantage API Key** - [Get Free Key](https://www.alphavantage.co/support/#api-key)
- **Git**
- **MySQL Client** (optional, for database access) - [DBeaver](https://dbeaver.io) recommended

### Installation

**1. Clone the repository:**

```bash
git clone https://github.com/ramc10/Arth360.git
cd Arth360
```

**2. Create environment configuration:**

```bash
# Copy example environment file
cat > .env << 'EOF'
# Database Configuration
DB_HOST=mysql
DB_USER=rss_user
DB_PASSWORD=your_secure_password
DB_NAME=rss_reader

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel_id

# LMStudio Configuration
LMSTUDIO_URL=http://host.docker.internal:1234/v1/chat/completions

# Alpha Vantage API Configuration
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
EOF
```

**3. Start LMStudio (Required for AI analysis):**

- Open LMStudio
- Load model: `llama-3.1-8b-instruct`
- Start server on port `1234`
- Verify: `curl http://localhost:1234/v1/models`

**4. Build and start services:**

```bash
# Build base image
docker build -t arth360-base:latest -f Dockerfile.base .

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

**5. Initialize database and add companies to track:**

```sql
-- Connect to MySQL (localhost:3306)
-- User: rss_user, Password: <your_password>, Database: rss_reader

-- Add companies to your watchlist
INSERT INTO user_watchlist (user_id, company_symbol, company_name) VALUES
(1, 'AAPL', 'Apple Inc.'),
(1, 'TSLA', 'Tesla Inc.'),
(1, 'NVDA', 'NVIDIA Corporation'),
(1, 'MSFT', 'Microsoft Corporation'),
(1, 'GOOGL', 'Alphabet Inc.'),
(1, 'AMZN', 'Amazon.com Inc.'),
(1, 'META', 'Meta Platforms Inc.'),
(1, 'NFLX', 'Netflix Inc.');
```

**6. Monitor the system:**

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f research
docker-compose logs -f feeder
docker-compose logs -f research-publisher

# Check research briefs in database
# Connect via DBeaver and query: SELECT * FROM research_briefs;
```

## 📦 Services

### 1. Feeder Service
**Collects news from RSS feeds**

- Checks 35 configured RSS feeds every 5 minutes
- Stores article metadata (title, URL, description, published date)
- Handles duplicates and rate limiting
- Sources: Reuters, CNBC, TechCrunch, The Verge, Economic Times, Mint, MarketWatch, Yahoo Finance, Hacker News, etc.

**Configuration:** `feeder/config.json`

**Recent Updates:**
- Removed Google News feeds (redirect resolution issues)
- Removed Moneycontrol feeds (403 blocking)
- Optimized with 35 high-quality direct publisher feeds

### 2. Content Service
**Processes and enriches articles**

- Extracts full article content from URLs using newspaper3k
- Enhanced retry logic with exponential backoff (3 attempts)
- BeautifulSoup fallback for extraction failures
- Rate limiting per domain (2-second intervals)
- User agent rotation (8 variants)
- Cleans and formats text
- Generates article summaries
- Failed article tracking to prevent reprocessing
- Expected success rate: 75-85%

**Recent Enhancements:**
- Multi-strategy content extraction
- Intelligent retry mechanisms
- Comprehensive error handling

### 3. Publisher Service
**Publishes to Telegram**

- Monitors database for new processed articles
- Formats messages with images and summaries
- Publishes to configured Telegram channel
- Tracks published articles to avoid duplicates

### 4. Research Service
**AI-powered research brief generation**

- **Runs twice daily** at 8:00 AM and 8:00 PM UTC
- Finds articles matching watchlist companies (last 24 hours)
- Analyzes up to 5 articles per company using local LLM (Llama 3.1-8b)
- Fetches real-time stock data from Alpha Vantage API
- Smart caching: Overview data cached for 24h, quotes fetched fresh
- Generates comprehensive research briefs
- Saves to database with JSON analysis

**API Usage Optimization:**
- **First cycle (Morning):** Quote + Overview = 16 API calls
- **Second cycle (Evening):** Quote only (cached overview) = 8 API calls
- **Total daily:** 24 API calls (within 25/day free tier limit)

**Brief includes:**
- AI-generated article summaries (sentiment analysis)
- Financial impact assessment
- Real-time stock metrics (price, volume, change %)
- Market fundamentals (market cap, P/E ratio, 52-week high/low)
- Links to original sources

### 5. Research Publisher Service
**Publishes research briefs to Telegram**

- Monitors `research_briefs` table for unpublished briefs
- Formats rich HTML messages with full AI analysis text
- Runs every 30 minutes (configurable)
- Includes sentiment indicators (🟢 Positive, 🔴 Negative, ⚪ Neutral)
- Shows comprehensive stock data
- Tracks published briefs to prevent duplicates

**Published message includes:**
- Company name and symbol
- Stock price and % change
- Market cap, P/E ratio, 52-week high/low
- Top 3 news articles with complete AI analysis
- Sentiment indicators and financial impact
- Timestamp and source attribution
- No external "Read more" links - all content self-contained

### 6. Alpha Vantage Integration
**Real-time stock market data**

- Free tier: 25 API calls per day
- Rate limiting: 12 seconds between requests (5 calls/minute)
- Smart caching: 5 minutes for quotes, 24 hours for fundamentals
- Supports US and international stocks
- Comprehensive error handling with clear rate limit messages

**Data provided:**
- Real-time quotes (price, volume, open/high/low)
- Company fundamentals (market cap, P/E ratio, EPS)
- 52-week trading range
- Beta, dividend yield

## 💻 Local Development

### Running Services Locally

**Research Service:**

```bash
cd research-service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DB_HOST=localhost
export DB_USER=rss_user
export DB_PASSWORD=your_password
export DB_NAME=rss_reader
export LMSTUDIO_URL=http://localhost:1234/v1/chat/completions
export ALPHA_VANTAGE_API_KEY=your_api_key

# Run service
python app.py
```

**Feeder Service:**

```bash
cd feeder
python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt

export DB_HOST=localhost
export DB_USER=rss_user
export DB_PASSWORD=your_password
export DB_NAME=rss_reader

python feeder.py
```

## 🗄️ Database Schema

### Core Tables

**feed_metadata**
```sql
- id: INT (Primary Key)
- url: TEXT (Article URL)
- title: VARCHAR(500)
- description: TEXT
- published_at: DATETIME
- source: VARCHAR(100) (Feed identifier)
- fetched_at: TIMESTAMP
```

**article_content**
```sql
- id: INT (Primary Key)
- url_id: INT (Foreign Key → feed_metadata.id)
- cleaned_text: LONGTEXT (Full article content)
- summary: TEXT (Auto-generated summary)
- images: JSON (Extracted images)
- processed_at: TIMESTAMP
```

**research_briefs**
```sql
- id: INT (Primary Key)
- user_id: INT
- company_symbol: VARCHAR(10)
- brief_date: DATE
- news_summary: JSON (AI-analyzed articles)
- financial_data: JSON (Stock metrics from Alpha Vantage)
- articles_analyzed: INT
- generated_at: TIMESTAMP
```

**research_briefs_published**
```sql
- id: INT (Primary Key)
- brief_id: INT (Foreign Key → research_briefs.id)
- published_at: TIMESTAMP
```

**user_watchlist**
```sql
- id: INT (Primary Key)
- user_id: INT
- company_symbol: VARCHAR(10)
- company_name: VARCHAR(200)
- created_at: TIMESTAMP
```

**telegram_published**
```sql
- id: INT (Primary Key)
- article_id: INT (Foreign Key → feed_metadata.id)
- published_at: TIMESTAMP
```

**failed_articles**
```sql
- id: INT (Primary Key)
- url: TEXT (Failed URL)
- error_message: TEXT
- attempts: INT
- last_attempt: TIMESTAMP
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_HOST` | MySQL hostname | `mysql` | Yes |
| `DB_USER` | Database user | `rss_user` | Yes |
| `DB_PASSWORD` | Database password | - | Yes |
| `DB_NAME` | Database name | `rss_reader` | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - | Yes |
| `TELEGRAM_CHANNEL_ID` | Telegram channel ID | - | Yes |
| `LMSTUDIO_URL` | LMStudio API endpoint | `http://host.docker.internal:1234/v1/chat/completions` | Yes |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API key | - | Yes |

### RSS Feed Configuration

Edit `feeder/config.json` to add/remove news sources:

```json
{
  "feeds": [
    {
      "name": "Reuters Business News",
      "url": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
      "source": "reuters-business",
      "headers": {"User-Agent": "Mozilla/5.0"},
      "last_checked": null
    }
  ]
}
```

**Currently Configured Sources (35 feeds):**
- Reuters (Business, Technology)
- CNBC (Top News, Technology, Finance)
- TechCrunch
- The Verge
- Ars Technica
- MarketWatch (Top Stories, Real-time Headlines)
- Seeking Alpha
- Yahoo Finance
- ZDNet
- Wired (Business, Tech)
- Benzinga
- The Motley Fool
- Investor's Business Daily
- Barron's
- Economic Times (Markets, Tech)
- Mint (Markets, Business, Technology, Industry, Money, AI)
- Business Today
- Hindu Business Line (Markets, Tech)
- Financial Express (Markets, Tech)
- CoinDesk
- CoinTelegraph
- Hacker News

### Research Service Schedule

**Current Schedule:** Twice daily at 8:00 AM and 8:00 PM UTC

**Modify `research-service/app.py` for different schedules:**

```python
# Current: Twice daily
run_hours = [8, 20]  # 8 AM and 8 PM UTC

# Three times daily
run_hours = [8, 14, 20]  # Morning, afternoon, evening

# Once daily
run_hours = [8]  # Morning only
```

## 🔍 Viewing Research Briefs

### In DBeaver/MySQL

```sql
-- Latest briefs for all companies
SELECT
    company_symbol,
    brief_date,
    articles_analyzed,
    JSON_EXTRACT(financial_data, '$.price') as price,
    JSON_EXTRACT(financial_data, '$.change_percent') as change_pct,
    JSON_EXTRACT(financial_data, '$.source') as data_source,
    generated_at
FROM research_briefs
ORDER BY generated_at DESC
LIMIT 10;

-- Full brief for specific company
SELECT
    company_symbol,
    JSON_PRETTY(news_summary) as ai_analysis,
    JSON_PRETTY(financial_data) as stock_data
FROM research_briefs
WHERE company_symbol = 'AAPL'
ORDER BY generated_at DESC
LIMIT 1;

-- Today's briefs with stock data
SELECT
    rb.company_symbol,
    JSON_EXTRACT(rb.financial_data, '$.price') as price,
    JSON_EXTRACT(rb.financial_data, '$.market_cap') as market_cap,
    JSON_EXTRACT(rb.financial_data, '$.pe_ratio') as pe_ratio,
    rb.articles_analyzed,
    CASE
        WHEN rbp.id IS NOT NULL THEN 'Published'
        ELSE 'Unpublished'
    END as status
FROM research_briefs rb
LEFT JOIN research_briefs_published rbp ON rb.id = rbp.brief_id
WHERE rb.brief_date = CURDATE()
ORDER BY rb.generated_at DESC;

-- Check published briefs
SELECT
    rb.company_symbol,
    rb.generated_at,
    rbp.published_at,
    TIMESTAMPDIFF(MINUTE, rb.generated_at, rbp.published_at) as publish_delay_minutes
FROM research_briefs rb
JOIN research_briefs_published rbp ON rb.id = rbp.brief_id
ORDER BY rbp.published_at DESC
LIMIT 10;
```

## 🐛 Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs [service_name]

# Verify MySQL is healthy
docker-compose ps mysql

# Restart specific service
docker-compose restart [service_name]

# Rebuild and restart
docker-compose build [service_name] && docker-compose up -d [service_name]
```

### Research service not generating briefs

```bash
# Check if articles exist for your companies
# Connect to MySQL and run:
SELECT COUNT(*) FROM feed_metadata
WHERE (title LIKE '%AAPL%' OR title LIKE '%Apple%')
AND published_at > DATE_SUB(NOW(), INTERVAL 24 HOUR);

# Verify LMStudio is running
curl http://localhost:1234/v1/models

# Check Alpha Vantage API
curl "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey=YOUR_KEY"

# Check research service logs
docker-compose logs -f research

# Verify next scheduled run time
docker logs arth360-research 2>&1 | grep "Next run"
```

### Alpha Vantage API Issues

```bash
# Check daily rate limit status
docker exec arth360-research python3 -c "
from alpha_vantage_client import AlphaVantageClient
client = AlphaVantageClient()
print(client.get_cache_stats())
"

# Test API key
curl "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey=YOUR_KEY"

# Clear cache to force fresh API calls
docker exec arth360-research python3 -c "
from alpha_vantage_client import AlphaVantageClient
client = AlphaVantageClient()
client.clear_cache()
print('Cache cleared')
"
```

**Common Error Messages:**
- `"Daily API rate limit reached (25 requests/day)"` - Wait until next day (resets at midnight UTC)
- `"Rate limit reached. Please wait."` - Hit per-minute limit, service will auto-retry
- `"No data available for this symbol"` - Invalid stock symbol or delisted stock

### Content extraction failing

```bash
# Check content service logs
docker-compose logs -f content

# View failed articles
SELECT url, error_message, attempts, last_attempt
FROM failed_articles
ORDER BY last_attempt DESC
LIMIT 20;

# Check extraction success rate
SELECT
    COUNT(*) as total_articles,
    SUM(CASE WHEN cleaned_text IS NOT NULL THEN 1 ELSE 0 END) as extracted,
    ROUND(100.0 * SUM(CASE WHEN cleaned_text IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM article_content ac
JOIN feed_metadata fm ON ac.url_id = fm.id
WHERE fm.fetched_at > DATE_SUB(NOW(), INTERVAL 24 HOUR);
```

### Database connection errors

```bash
# Verify .env file exists and has correct credentials
cat .env

# Test MySQL connection from container
docker exec arth360-mysql mysql -urss_user -p10_Leomessi rss_reader -e "SHOW TABLES;"

# Check database exists
docker exec arth360-mysql mysql -urss_user -p10_Leomessi -e "SHOW DATABASES;"

# Verify user permissions
docker exec arth360-mysql mysql -urss_user -p10_Leomessi -e "SHOW GRANTS;"
```

### Telegram publishing not working

```bash
# Test bot token
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# Check if bot is admin of channel
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getChatAdministrators?chat_id=@artha360"

# View publisher logs
docker-compose logs -f research-publisher

# Check unpublished briefs
SELECT rb.id, rb.company_symbol, rb.generated_at
FROM research_briefs rb
LEFT JOIN research_briefs_published rbp ON rb.id = rbp.brief_id
WHERE rbp.id IS NULL
AND rb.brief_date >= CURDATE() - INTERVAL 1 DAY;
```

## 📁 Project Structure

```
Arth360/
├── feeder/
│   ├── Dockerfile
│   ├── feeder.py              # RSS feed collector
│   └── config.json            # RSS feed sources (35 feeds)
├── content/
│   ├── Dockerfile
│   └── content.py             # Enhanced article processor with retry logic
├── publisher/
│   ├── Dockerfile
│   └── telegram_publisher.py # Article publisher
├── research-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                 # AI research brief generator (2x daily)
│   └── alpha_vantage_client.py # Stock data API client
├── research-publisher/
│   ├── Dockerfile
│   └── research_telegram_publisher.py # Research brief publisher
├── stocks/
│   └── stock_scripts.py       # Stock data utilities
├── docker-compose.yml         # Service orchestration (6 services)
├── Dockerfile.base            # Base Python image
├── requirements.txt           # Root dependencies
├── .env                       # Environment variables (create this)
├── .gitignore
└── README.md
```

## 🔒 Security Considerations

- Never commit `.env` file to version control
- Use strong database passwords
- Keep API keys secure and rotate periodically
- Limit MySQL port exposure (only localhost:3306)
- Use read-only Telegram bot permissions when possible
- Regularly update dependencies for security patches

## 📊 Performance Metrics

**Expected Throughput:**
- Feeder: ~200-300 articles/day from 35 feeds
- Content Extraction: 75-85% success rate
- Research Briefs: 8 companies × 2 cycles = 16 briefs/day
- Telegram Publishing: Real-time (30-minute check interval)

**Resource Usage:**
- MySQL: ~500MB RAM
- Each service: ~100-200MB RAM
- Total system: ~1.5GB RAM
- Storage: ~5GB for 6 months of articles

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LMStudio](https://lmstudio.ai) - Local LLM inference
- [Alpha Vantage](https://www.alphavantage.co) - Stock market data API
- [feedparser](https://github.com/kurtmckee/feedparser) - RSS feed parsing
- [newspaper3k](https://github.com/codelucas/newspaper) - Article extraction
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - Web scraping fallback

## 📞 Support

- **Telegram Channel:** [@artha360](https://t.me/artha360)
- **Issues:** [GitHub Issues](https://github.com/ramc10/Arth360/issues)

## 📝 Changelog

### v2.0.0 (2025-11-20)
- ✅ Replaced Google News feeds with 35 direct publisher feeds
- ✅ Removed blocked Moneycontrol feeds
- ✅ Integrated Alpha Vantage API for stock data (replaced Yahoo Finance)
- ✅ Enhanced content extraction with retry logic and BeautifulSoup fallback
- ✅ Implemented smart API usage optimization (24 calls/day)
- ✅ Reduced research cycles to 2x daily (8 AM & 8 PM UTC)
- ✅ Added comprehensive error handling and rate limit detection
- ✅ Improved Telegram publishing with full AI analysis text
- ✅ Added market cap, P/E ratio, and 52-week range to briefs
- ✅ Implemented intelligent caching for stock fundamentals

### v1.0.0 (Initial Release)
- Basic RSS feed aggregation
- Simple article extraction
- LLM-powered analysis
- Telegram publishing
- Research brief generation

---

**Built with ❤️ for the financial research community**
