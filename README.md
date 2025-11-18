# Arth360 - AI-Powered Financial News & Research Platform

[![Join Telegram Channel](https://img.shields.io/badge/Join%20Telegram-Arth360-blue)](https://t.me/artha360)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](docker-compose.yml)

> Automated news aggregation and AI-powered research brief generation platform for financial markets.

## 🎯 Overview

Arth360 is a microservices-based platform that collects financial news from multiple sources, processes it with AI, and generates comprehensive research briefs for tracked companies. The system runs continuously, aggregating news from Google News, RSS feeds, and delivering insights through Telegram.

### Key Features

- 📰 **Multi-Source News Aggregation** - Collects from 25+ RSS feeds (Google News, Moneycontrol, Economic Times)
- 🤖 **AI-Powered Analysis** - Uses local LLM (Llama 3.1) to summarize and analyze articles
- 📊 **Real-Time Financial Data** - Integrates live stock data via yfinance
- 🔍 **Automated Research Briefs** - Generates daily company research with sentiment analysis
- 📱 **Telegram Publishing** - Auto-publishes curated content to Telegram channels
- 🐳 **Fully Containerized** - Docker-based deployment for easy scaling

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Feeder    │────▶│   Content   │────▶│  Publisher  │────▶│  Telegram   │
│  (RSS Feed) │     │ (Processor) │     │   (Output)  │     │   Channel   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                    │                                        
       │                    │                                        
       ▼                    ▼                                        
┌─────────────────────────────────┐     ┌─────────────┐
│         MySQL Database          │◀────│  Research   │
│  (Articles, Briefs, Tracking)   │     │  Service    │
└─────────────────────────────────┘     └─────────────┘
                                               ▲
                                               │
                                        ┌─────────────┐
                                        │  LMStudio   │
                                        │ (Local LLM) │
                                        └─────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Docker Desktop** (macOS/Windows) or **Docker Engine + docker-compose** (Linux)
- **LMStudio** (for AI analysis) - [Download](https://lmstudio.ai)
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
DB_USER=root
DB_PASSWORD=your_secure_password
DB_NAME=rss_reader

# Telegram Configuration (optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel_id

# LMStudio Configuration
LMSTUDIO_URL=http://host.docker.internal:1234/v1/chat/completions
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
-- User: root, Password: <your_password>, Database: rss_reader

-- Add companies to your watchlist
INSERT INTO user_watchlist (user_id, company_symbol, company_name) VALUES
(1, 'AAPL', 'Apple Inc.'),
(1, 'TSLA', 'Tesla Inc.'),
(1, 'NVDA', 'NVIDIA Corporation'),
(1, 'MSFT', 'Microsoft Corporation'),
(1, 'GOOGL', 'Alphabet Inc.');
```

**6. Monitor the system:**

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f research
docker-compose logs -f feeder

# Check research briefs in database
# Connect via DBeaver and query: SELECT * FROM research_briefs;
```

## 📦 Services

### 1. Feeder Service
**Collects news from RSS feeds**

- Checks 25+ configured RSS feeds every 5 minutes
- Stores article metadata (title, URL, description, published date)
- Handles duplicates and rate limiting
- Sources: Google News (company-specific), Moneycontrol, Economic Times, Mint

**Configuration:** `config.json`

### 2. Content Service
**Processes and enriches articles**

- Extracts full article content from URLs
- Cleans and formats text
- Extracts images and metadata
- Generates article summaries
- Stores processed content in database

### 3. Publisher Service
**Publishes to Telegram**

- Monitors database for new processed articles
- Formats messages with images and summaries
- Publishes to configured Telegram channel
- Tracks published articles to avoid duplicates

### 4. Research Service
**AI-powered research brief generation**

- Runs every hour (configurable)
- Finds articles matching watchlist companies
- Analyzes articles using local LLM (Llama 3.1)
- Fetches real-time stock data (price, volume, P/E ratio)
- Generates comprehensive research briefs
- Saves to database with JSON analysis

**Brief includes:**
- AI-generated article summaries
- Sentiment analysis (Positive/Negative/Neutral)
- Financial impact assessment
- Real-time stock metrics
- Links to original sources

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
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=rss_reader
export LMSTUDIO_URL=http://localhost:1234/v1/chat/completions

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
export DB_USER=root
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
- financial_data: JSON (Stock metrics)
- articles_analyzed: INT
- generated_at: TIMESTAMP
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
- feed_id: INT (Foreign Key → feed_metadata.id)
- published_at: TIMESTAMP
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_HOST` | MySQL hostname | `mysql` | Yes |
| `DB_USER` | Database user | `root` | Yes |
| `DB_PASSWORD` | Database password | - | Yes |
| `DB_NAME` | Database name | `rss_reader` | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - | Optional |
| `TELEGRAM_CHANNEL_ID` | Telegram channel ID | - | Optional |
| `LMSTUDIO_URL` | LMStudio API endpoint | `http://host.docker.internal:1234/v1/chat/completions` | Yes |

### RSS Feed Configuration

Edit `config.json` to add/remove news sources:

```json
{
  "feeds": [
    {
      "name": "Google News - Apple Inc",
      "url": "https://news.google.com/rss/search?q=Apple+Inc+OR+AAPL",
      "source": "google-aapl",
      "headers": {"User-Agent": "Mozilla/5.0"},
      "last_checked": null
    }
  ]
}
```

### Research Service Schedule

**Modify `app.py` for different schedules:**

```python
# Current: Every 1 hour
time.sleep(3600)

# Every 30 minutes
time.sleep(1800)

# Every 6 hours
time.sleep(21600)
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

-- Today's briefs
SELECT * FROM research_briefs
WHERE brief_date = CURDATE();
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
```

### Research service not generating briefs

```bash
# Check if articles exist for your companies
SELECT COUNT(*) FROM feed_metadata 
WHERE title LIKE '%Apple%' OR title LIKE '%AAPL%';

# Verify LMStudio is running
curl http://localhost:1234/v1/models

# Check research service logs
docker-compose logs -f research
```

### Database connection errors

```bash
# Verify .env file exists and has correct credentials
cat .env

# Test MySQL connection
docker exec -it arth360-mysql mysql -uroot -p

# Check if database exists
SHOW DATABASES;
USE rss_reader;
SHOW TABLES;
```

### URL too long errors (Google News)

```sql
-- Increase URL column size
ALTER TABLE feed_metadata DROP INDEX unique_feed_item;
ALTER TABLE feed_metadata MODIFY COLUMN url TEXT;
ALTER TABLE feed_metadata ADD INDEX idx_url (url(255));
```

## 📁 Project Structure

```
Arth360/
├── feeder/
│   ├── Dockerfile
│   └── feeder.py           # RSS feed collector
├── content/
│   ├── Dockerfile
│   └── content.py          # Article processor
├── publisher/
│   ├── Dockerfile
│   └── telegram_publisher.py
├── research-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py              # AI research brief generator
├── stocks/
│   └── stock_scripts.py    # Stock data utilities
├── config.json             # RSS feed configuration
├── docker-compose.yml      # Service orchestration
├── Dockerfile.base         # Base Python image
├── requirements.txt        # Root dependencies
├── .env                    # Environment variables (create this)
├── .gitignore
└── README.md
```

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
- [yfinance](https://github.com/ranaroussi/yfinance) - Stock market data
- [feedparser](https://github.com/kurtmckee/feedparser) - RSS feed parsing
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - Web scraping

## 📞 Support

- **Telegram Channel:** [@artha360](https://t.me/artha360)
- **Issues:** [GitHub Issues](https://github.com/ramc10/Arth360/issues)

---

**Built with ❤️ for the financial research community**
