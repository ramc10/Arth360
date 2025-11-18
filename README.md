# Arth360.Live

[![Join Telegram Channel](https://img.shields.io/badge/Join%20Telegram-Arth360-blue)](https://t.me/artha360)

A news aggregation system that collects, processes, summarises and publishes news articles to a Telegram channel.

## Architecture

The system consists of several microservices working together to deliver news content:

### Core Services

1. **Feeder Service**
   - Collects news articles from various RSS feeds
   - Stores basic article metadata in the database
   - Runs continuously, checking for new articles

2. **Content Service**
   - Processes articles from the feeder service
   - Extracts full content, images, and metadata
   - Generates article summaries
   - Stores processed content in the database

3. **Publisher Service**
   - Publishes processed articles to Telegram
   - Tracks published articles to avoid duplicates
   - Runs continuously, checking for new content to publish

4. **Stocks Service** (On-Demand)
   - Processes stock market data
   - Runs only when triggered manually
   - Uses the same database as other services

### Database Structure

The system uses MySQL with three main tables:
- `feed_metadata`: Stores basic article information
- `article_content`: Contains processed article content
- `telegram_published`: Tracks published articles

## Prerequisites

Before you begin, ensure you have the following installed:
- Docker and Docker Compose
- Git

### Installing Docker

# Arth360.Live

[![Join Telegram Channel](https://img.shields.io/badge/Join%20Telegram-Arth360-blue)](https://t.me/artha360)

Arth360 is a small microservice-based news aggregation system that collects, processes, summarises and publishes news articles (and optional stock data) to a Telegram channel.

## Overview

The repo contains a set of services that work together:

- `feeder/` — collects RSS feed metadata and stores it in the database
- `content/` — fetches and processes full article content, extracts images, generates summaries
- `publisher/` — publishes processed articles to Telegram and avoids duplicates
- `stocks/` — optional on-demand stock data processing
- `research-service/` — generates research briefs using an LLM (local LMStudio by default)

The project uses MySQL as the primary datastore (see `docker-compose.yml`).

## Quickstart (Docker)

These instructions get the system up quickly using Docker Compose.

Prerequisites:

- Docker Desktop (macOS) or Docker Engine + docker-compose (Linux)
- Git

1. Clone the repo and change directory:

```bash
git clone https://github.com/ramc10/Arth360.git
cd Arth360
```

2. Create a `.env` file in the repo root (example values):

```env
DB_HOST=mysql
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=rss_reader
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=@your_channel_or_id
LMSTUDIO_URL=http://host.docker.internal:1234
```

3. Build the base image (first-time only) and start services:

```bash
# build the base image used by several services
docker build -t arth360-base:latest -f Dockerfile.base .

# start services in background
docker-compose up -d
```

4. Check logs to verify services started correctly:

```bash
docker-compose logs -f
docker-compose logs -f feeder
```

## Running services locally (without Docker)

You can run individual Python services locally for development. Example for the research service:

```bash
# from the repo root
# Arth360.Live

[![Join Telegram Channel](https://img.shields.io/badge/Join%20Telegram-Arth360-blue)](https://t.me/artha360)

Arth360 is a small microservice-based news aggregation system that collects, processes, summarises and publishes news articles (and optional stock data) to a Telegram channel.

## Overview

The repo contains a set of services that work together:

- `feeder/` — collects RSS feed metadata and stores it in the database
- `content/` — fetches and processes full article content, extracts images, generates summaries
- `publisher/` — publishes processed articles to Telegram and avoids duplicates
- `stocks/` — optional on-demand stock data processing
- `research-service/` — generates research briefs using an LLM (local LMStudio by default)

The project uses MySQL as the primary datastore (see `docker-compose.yml`).

## Quickstart (Docker)

These instructions get the system up quickly using Docker Compose.

Prerequisites:

- Docker Desktop (macOS) or Docker Engine + docker-compose (Linux)
- Git

1. Clone the repo and change directory:

```bash
git clone https://github.com/ramc10/Arth360.git
cd Arth360
```

2. Create a `.env` file in the repo root (example values):

```env
DB_HOST=mysql
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=rss_reader
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=@your_channel_or_id
LMSTUDIO_URL=http://host.docker.internal:1234
```

3. Build the base image (first-time only) and start services:

```bash
# build the base image used by several services
docker build -t arth360-base:latest -f Dockerfile.base .

# start services in background
docker-compose up -d
```

4. Check logs to verify services started correctly:

```bash
docker-compose logs -f
docker-compose logs -f feeder
```

## Running services locally (without Docker)

You can run individual Python services locally for development. Example for the research service:

```bash
# from the repo root
# Arth360.Live

[![Join Telegram Channel](https://img.shields.io/badge/Join%20Telegram-Arth360-blue)](https://t.me/artha360)

Arth360 is a lightweight microservice-based news aggregation system. It collects RSS content, processes and summarises articles, optionally enriches with stock data, and publishes to a Telegram channel.

## Contents

- `feeder/` — collects RSS feed metadata and stores it in the DB
- `content/` — fetches full article content, extracts images/metadata and generates summaries
- `publisher/` — publishes articles to Telegram and avoids duplicates
- `stocks/` — on-demand stock data processing and scripts
- `research-service/` — generates research briefs using an LLM (LMStudio by default)

See `docker-compose.yml` for how services are wired together.

## Quickstart (Docker)

Prerequisites: Docker Desktop (macOS) or Docker Engine + docker-compose (Linux) and Git.

1. Clone and enter the repository:

```bash
git clone https://github.com/ramc10/Arth360.git
cd Arth360
```

2. Create a `.env` file in the repo root (example):

```env
DB_HOST=mysql
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=rss_reader
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=@your_channel_or_id
LMSTUDIO_URL=http://host.docker.internal:1234
```

3. Build base image (first time) and start services:

```bash
docker build -t arth360-base:latest -f Dockerfile.base .
docker-compose up -d
```

4. Check logs:

```bash
docker-compose logs -f
docker-compose logs -f feeder
```

## Running a single service locally (example: research-service)

You can run services locally for development. Example for `research-service`:

```bash
cd research-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# set env vars (example)
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=rss_reader
export LMSTUDIO_URL=http://localhost:1234

python app.py
```

Notes:
- `research-service/app.py` expects a MySQL database and optionally an LMStudio-compatible endpoint for summarization. If LMStudio is not reachable, the service will continue but summaries will fail.
- `stocks/` scripts depend on `yfinance` and other packages — see `stocks/` and `requirements.txt`.

## Environment variables

Core environment variables (put in `.env`):

- DB_HOST, DB_USER, DB_PASSWORD, DB_NAME — MySQL connection details
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID — credentials for publishing
- LMSTUDIO_URL — (optional) LMStudio API base URL (e.g. `http://host.docker.internal:1234`)

Each service may accept additional variables — check the service folders for specifics.

## Database (high level)

Important tables used by the services:

- `feed_metadata` — article metadata (title, url, published_at, description)
- `article_content` — processed/cleaned content and extracted data
- `telegram_published` — records of published items to avoid duplicates
- `research_briefs` — generated briefs from `research-service`

If you need schema SQL or migrations, let me know and I can add sample DDL or migration scripts.

## Troubleshooting

- Check container logs: `docker-compose logs -f <service>`
- If running locally, watch stdout from the Python process
- Verify DB connectivity and credentials
- If LLM requests fail, confirm `LMSTUDIO_URL` and that LMStudio/model is running

## Project layout (top-level)

- `docker-compose.yml`, `Dockerfile.base` — docker configuration
- `feeder/`, `content/`, `publisher/`, `stocks/`, `research-service/` — services
- `requirements.txt` — root Python deps used for some scripts

## Contributing / Next steps

- Add a `.env.example` file with the variables above
- Add `RUNNING.md` with step-by-step instructions for each service
- Provide SQL schema or migration scripts for the MySQL schema

If you'd like, I can create `.env.example` and `RUNNING.md` next.

## License

See the included `LICENSE` file for license terms.
