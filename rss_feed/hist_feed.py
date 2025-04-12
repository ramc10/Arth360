import json
import requests
import feedparser
from datetime import datetime, timedelta
import time
import mysql.connector
from mysql.connector import Error
import pytz
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

class WaybackRSSScraper:
    def __init__(self):
        self.running = True
        self.session = requests.Session()
        self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries=3))
        self.setup_logger()
        self.create_tables()
        self.load_config()

    def load_config(self):
        """Load feed configuration from JSON file"""
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
            self.log_console("📋", f"Loaded configuration with {len(self.config['feeds'])} feeds")
        except Exception as e:
            self.log_console("💥", f"Error loading config.json: {str(e)}")
            self.config = {"feeds": []}

    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('WaybackRSSScraper')
        self.logger.setLevel(logging.INFO)
        
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'wayback_rss.log'),
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)

    def log_console(self, emoji, message):
        """Console logging with emojis"""
        print(f"{datetime.now().strftime('%H:%M:%S')} {emoji} {message}")
        self.logger.info(message)

    def create_db_connection(self):
        """Create and return MySQL connection"""
        try:
            conn = mysql.connector.connect(
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_NAME')
            )
            return conn
        except Error as e:
            self.log_console("🔥", f"Database connection error: {str(e)}")
            return None

    def create_tables(self):
        """Ensure required tables exist"""
        connection = self.create_db_connection()
        if not connection:
            self.log_console("❌", "Couldn't connect to database")
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS wayback_rss_articles2 (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                url VARCHAR(512) NOT NULL,
                published_at DATETIME NOT NULL,
                source VARCHAR(50) NOT NULL,
                snapshot_date VARCHAR(14) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_wayback_article (url, snapshot_date)
            )
            """)
            connection.commit()
            self.log_console("🆕", "Database tables ready!")
            return True
        except Error as e:
            self.log_console("💥", f"Error creating tables: {str(e)}")
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def get_wayback_snapshots(self, feed_url, start_date, end_date):
        """Get valid Wayback snapshots between dates"""
        cdx_url = (
            f"https://web.archive.org/cdx/search/cdx"
            f"?url={feed_url}"
            f"&from={start_date.strftime('%Y%m%d')}"
            f"&to={end_date.strftime('%Y%m%d')}"
            f"&filter=statuscode:200"
            f"&output=json"
        )
        
        try:
            response = self.session.get(cdx_url, timeout=30)
            response.raise_for_status()
            snapshots = response.json()
            return [
                f"https://web.archive.org/web/{s[1]}/{s[2]}"
                for s in snapshots[1:]  # Skip header
                if len(s) > 1
            ]
        except Exception as e:
            self.log_console("💥", f"Wayback API error for {feed_url}: {str(e)}")
            return []

    def extract_articles(self, snapshot_url, source):
        """Extract articles from a single snapshot"""
        try:
            response = self.session.get(snapshot_url, timeout=30)
            feed = feedparser.parse(response.text)
            
            articles = []
            for entry in feed.entries:
                pub_date = (
                    datetime(*entry.published_parsed[:6])
                    if hasattr(entry, 'published_parsed') 
                    else datetime.now()
                )
                articles.append({
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'published_at': pub_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': source,
                    'snapshot_date': snapshot_url.split('/web/')[1][:14]
                })
            return articles
        except Exception as e:
            self.log_console("⚠️", f"Error processing {snapshot_url}: {str(e)}")
            return []

    def store_articles(self, articles):
        """Store articles in MySQL database"""
        if not articles:
            return False
        
        connection = self.create_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.executemany("""
            INSERT INTO wayback_rss_articles2 (title, url, published_at, source, snapshot_date)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE title=VALUES(title)
            """, [
                (
                    article['title'],
                    article['url'],
                    article['published_at'],
                    article['source'],
                    article['snapshot_date']
                )
                for article in articles
            ])
            connection.commit()
            self.log_console("💾", f"Stored {len(articles)} articles for {articles[0]['source']}")
            return True
        except Error as e:
            self.log_console("💥", f"Database error: {str(e)}")
            connection.rollback()
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def scrape_feed(self, feed_config, days_to_scrape=365):
        """Scrape a single feed"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_to_scrape)
        
        self.log_console("\n" + "="*50, "")
        self.log_console("🚀", f"Starting scrape for {feed_config['name']}")
        
        # Apply custom headers if specified
        if 'headers' in feed_config:
            self.session.headers.update(feed_config['headers'])
        
        snapshots = self.get_wayback_snapshots(
            feed_config['url'],
            start_date,
            end_date
        )
        
        self.log_console("📸", f"Found {len(snapshots)} snapshots")
        
        total_articles = 0
        for i, snapshot_url in enumerate(snapshots[:1000], 1):  # Limit to 100 snapshots
            self.log_console("🔍", f"Processing snapshot {i}/{len(snapshots)}")
            articles = self.extract_articles(snapshot_url, feed_config['source'])
            if articles:
                self.store_articles(articles)
                total_articles += len(articles)
            time.sleep(3)  # Respect Wayback's rate limits
        
        self.log_console("✅", f"Finished {feed_config['name']} with {total_articles} articles")
        self.log_console("="*50 + "\n", "")
        return total_articles

    def run(self, days_to_scrape=365):
        """Run scraper for all feeds in config"""
        total_articles = 0
        for feed in self.config['feeds']:
            try:
                total_articles += self.scrape_feed(feed, days_to_scrape)
            except Exception as e:
                self.log_console("💥", f"Error processing {feed['name']}: {str(e)}")
                continue
        
        self.log_console("🏁", f"Completed all feeds! Total articles: {total_articles}")
        return total_articles

if __name__ == '__main__':
    scraper = WaybackRSSScraper()
    scraper.run(days_to_scrape=365)  # Scrape last 7 days