# Arth360.Live

This project consists of three main services that work together to fetch, process, and publish RSS feed content:

1. `feeder.py` - Fetches RSS feeds and stores them in the database
2. `content.py` - Extracts content from the stored URLs
3. `telegram_publisher.py` - Publishes content to a Telegram channel

## Prerequisites

- Python 3.11 or higher
- MySQL database
- Telegram bot token and channel ID

## Setup

1. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root with the following variables:
   ```
   DB_HOST=your_database_host
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_NAME=your_database_name
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHANNEL_ID=your_telegram_channel_id
   ```

3. Set up the MySQL database and create the required tables by running each service once.

## Running the Services

### Feeder Service
The feeder service continuously monitors RSS feeds and stores new articles in the database:
```bash
python feeder.py
```

### Content Service
The content service processes stored URLs to extract article content:
```bash
python content.py
```

### Telegram Publisher
The publisher service sends processed content to a Telegram channel:
```bash
python telegram_publisher.py
```

## Service Details

### Feeder Service (`feeder.py`)
- Fetches RSS feeds from configured sources
- Stores article metadata in the database
- Runs continuously with configurable check intervals
- Handles feed parsing and error logging

### Content Service (`content.py`)
- Extracts full article content from stored URLs
- Processes and cleans article text
- Stores extracted content in the database
- Handles image extraction and storage

### Telegram Publisher (`telegram_publisher.py`)
- Publishes processed articles to Telegram
- Formats content for Telegram messages
- Handles rate limiting and error recovery
- Tracks published articles to avoid duplicates

## Database Schema

The services use the following main tables:
- `feed_metadata`: Stores RSS feed entries
- `article_content`: Stores extracted article content
- `telegram_published`: Tracks published articles

## Logging

All services write logs to the `logs` directory with daily rotation. Logs include:
- Service status updates
- Error messages
- Processing statistics

## Error Handling

Each service includes:
- Automatic retry mechanisms
- Error logging
- Graceful failure handling
- Database transaction management

## Configuration

Key configuration options can be modified in each service:
- Check intervals
- Batch sizes
- Processing limits
- Logging levels

## Monitoring

Monitor service status through:
- Log files in the `logs` directory
- Database records
- Telegram channel output 
