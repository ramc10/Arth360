# Arth360.Live

[![Join Telegram Channel](https://img.shields.io/badge/Join%20Telegram-Arth360-blue)](https://t.me/artha360)
A news aggregation system that collects, processes, and publishes news articles to a Telegram channel.

## Architecture

The system consists of several microservices:

1. **Feeder Service**: Collects news articles from various RSS feeds
2. **Content Service**: Processes and extracts content from collected articles
3. **Publisher Service**: Publishes processed articles to a Telegram channel
4. **Stocks Service**: Adhoc service for stock market data (runs on demand)

## Database Structure

### Tables

1. **feed_metadata**
   - `id`: Primary key
   - `title`: Article title
   - `description`: Article description
   - `url`: Article URL
   - `published_at`: Publication date
   - `source`: News source
   - `created_at`: Record creation timestamp

2. **article_content**
   - `id`: Primary key
   - `url_id`: Foreign key to feed_metadata
   - `full_text`: Complete article text
   - `cleaned_text`: Cleaned version of text
   - `authors`: Article authors (JSON)
   - `top_image`: Main article image URL
   - `images`: Article images (JSON)
   - `keywords`: Article keywords (JSON)
   - `summary`: Article summary
   - `created_at`: Record creation timestamp

3. **telegram_published**
   - `id`: Primary key
   - `article_id`: Foreign key to feed_metadata
   - `published_at`: Publication timestamp

## Setup

1. Clone the repository
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

## Services

### Feeder Service
- Collects news articles from configured RSS feeds
- Stores basic article metadata in `feed_metadata` table
- Runs continuously, checking for new articles

### Content Service
- Processes articles from `feed_metadata`
- Extracts full content, images, and metadata
- Stores processed content in `article_content` table
- Runs continuously, processing unprocessed articles

### Publisher Service
- Publishes processed articles to Telegram
- Marks published articles in `telegram_published` table
- Runs continuously, checking for new content to publish

### Stocks Service
- Runs on demand using `run_stocks.sh`
- Processes stock market data
- Connects to the same database as other services

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

## Database Access

Connect to MySQL:
```bash
docker exec -it arth360-mysql mysql -u root -p
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
