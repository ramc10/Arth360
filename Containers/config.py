import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'password'),
    'database': os.getenv('MYSQL_DATABASE', 'news_feeds')
}

# RSS Feed URLs
FEED_URLS = [
    {
        'name': 'Mint Markets',
        'url': 'https://www.livemint.com/rss/markets',
        'source': 'mint'
    },
    {
        'name': 'Business Standard Markets',
        'url': 'https://www.business-standard.com/rss/markets-106.rss',
        'source': 'business-standard'
    },
    {
        'name': 'Economic Times Market Data',
        'url': 'https://economictimes.indiatimes.com/market-data/rssfeeds/110737294.cms',
        'source': 'economic-times'
    }
]

# Extraction interval in minutes (default: 60 minutes)
EXTRACTION_INTERVAL = int(os.getenv('EXTRACTION_INTERVAL', 60))
