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

If you don't have Docker installed, follow these steps:

#### For macOS:
1. Download Docker Desktop for Mac from [Docker's official website](https://www.docker.com/products/docker-desktop)
2. Install the downloaded package
3. Start Docker Desktop from your Applications folder

#### For Linux:
```bash
# Update package index
sudo apt-get update

# Install required packages
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up the stable repository
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/arth360.git
   cd arth360
   ```

2. Create a `.env` file with the following variables:
   ```
   DB_HOST=mysql
   DB_USER=root
   DB_PASSWORD=your_password
   DB_NAME=rss_reader
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHANNEL_ID=your_channel_id
   ```

3. Build and start the services:
   ```bash
   # Build the base image
   docker build -t arth360-base:latest -f Dockerfile.base .

   # Start the main services
   docker-compose up -d
   ```

4. To run the stocks service adhoc:
   ```bash
   # Make the script executable
   chmod +x run_stocks.sh

   # Run the stocks service
   ./run_stocks.sh
   ```

## Monitoring

Check service logs:
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f feeder
docker-compose logs -f content
docker-compose logs -f publisher
```

## Troubleshooting

If you encounter issues:
1. Check service logs for errors
2. Verify database tables exist and have correct structure
3. Ensure environment variables are set correctly
4. Try rebuilding containers if changes were made:
   ```bash
   docker-compose build <service_name>
   docker-compose up -d <service_name>
   ```
