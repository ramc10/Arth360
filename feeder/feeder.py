import feedparser
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import time
import requests
import certifi
import ssl
import pytz
import logging
import os
import sys
from dotenv import load_dotenv
from logging.handlers import TimedRotatingFileHandler

# Load environment variables from base directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# Configure feedparser SSL
feedparser.api._FeedParserMixin._build_opener = lambda *args, **kwargs: feedparser.api._build_opener(
    *args, **kwargs,
    handlers=[feedparser.api.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where()))]
)

# Timezone setup
UTC = pytz.utc
IST = pytz.timezone('Asia/Kolkata')

# RSS Feed Configuration
# At the top of your script (replace the FEEDS list with this)
import json

# Load feeds from config.json
with open('config.json') as config_file:
    config = json.load(config_file)
    FEEDS = config['feeds']

class RSSFeedMonitor:
    def __init__(self):
        self.running = True
        self.check_interval = 300  # 5 minutes
        self.setup_logger()
        self.create_tables()

    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('RSSFeedMonitor')
        self.logger.setLevel(logging.INFO)
        
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        # File handler for log rotation
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'rss_monitor.log'),
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)
        
        # Console handler for screen output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(console_handler)

    def log(self, emoji, message):
        """Log messages with emoji"""
        log_message = f"{emoji} {message}"
        self.logger.info(log_message)

    def create_db_connection(self):
        """Create and return MySQL connection"""
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            self.log("🛢️", "Database connection established!")
            return conn
        except Error as e:
            self.log("🔥", f"Database connection error: {str(e)}")
            return None

    def create_tables(self):
        """Ensure required tables exist"""
        connection = self.create_db_connection()
        if not connection:
            self.log("❌", "Couldn't connect to database")
            return False

        try:
            cursor = connection.cursor()
            
            # Create feed_metadata table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feed_metadata (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                url VARCHAR(512) NOT NULL,
                published_at DATETIME NOT NULL,
                source VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_feed_item (url, source)
            )
            """)

            # Create article_content table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_content (
                id INT AUTO_INCREMENT PRIMARY KEY,
                url_id INT NOT NULL,
                summary TEXT,
                top_image VARCHAR(512),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (url_id) REFERENCES feed_metadata(id)
            )
            """)
            
            connection.commit()
            self.log("🆕", "Database tables ready!")
            return True
        except Error as e:
            self.log("💥", f"Error creating tables: {str(e)}")
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def parse_feed(self, feed):
        """Parse a single feed and return entries from the last year"""
        try:
            self.log("🔍", f"Checking {feed['name']}")
            
            response = requests.get(
                feed['url'],
                headers=feed['headers'],
                timeout=10
            )
            response.raise_for_status()
            
            parsed = feedparser.parse(response.content)
            new_entries = []
            one_year_ago = datetime.now(IST) - timedelta(days=365)
            
            for entry in parsed.entries:
                try:
                    pub_time = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                    pub_time_ist = pub_time.astimezone(IST)
                    
                    # Only include articles from the last year
                    if pub_time_ist > one_year_ago:
                        if feed['last_checked'] is None or pub_time_ist > feed['last_checked']:
                            description = entry.get('description', '')
                            if description:  # Only add entries with non-empty descriptions
                                new_entries.append({
                                    'title': entry.get('title', ''),
                                    'description': description,
                                    'url': entry.get('link', ''),
                                    'published_at': pub_time_ist,
                                    'source': feed['source']
                                })
                except Exception as e:
                    self.log("⚠️", f"Skipping entry: {str(e)}")
                    continue
            
            feed['last_checked'] = datetime.now(IST)
            self.log("🎉", f"Found {len(new_entries)} new articles in {feed['name']}")
            return new_entries
            
        except Exception as e:
            self.log("🔥", f"Failed to parse {feed['name']}: {str(e)}")
            return []

    def store_articles(self, articles):
        """Store articles in MySQL database with retry logic"""
        if not articles:
            self.log("🤷", "No articles to store")
            return False
        
        connection = self.create_db_connection()
        if not connection:
            self.log("🚫", "No database connection")
            return False

        try:
            cursor = connection.cursor()
            cursor.executemany("""
            INSERT INTO feed_metadata (title, description, url, published_at, source)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE title=VALUES(title), description=VALUES(description)
            """, [
                (
                    article['title'],
                    article['description'],
                    article['url'],
                    article['published_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    article['source']
                )
                for article in articles
            ])
            connection.commit()
            self.log("💾", f"Stored {len(articles)} articles successfully!")
            return True
            
        except Error as e:
            self.log("🔥", f"Database error: {str(e)}")
            connection.rollback()
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def check_all_feeds(self):
        """Check all feeds and store new articles"""
        self.log("\n" + "="*50, "")
        self.log("🚀", "Starting feed check")
        
        all_new_articles = []
        for feed in FEEDS:
            new_articles = self.parse_feed(feed)
            if new_articles:
                if self.store_articles(new_articles):
                    all_new_articles.extend(new_articles)
        
        self.log("🌈", f"Finished! Total new articles: {len(all_new_articles)}")
        self.log("="*50 + "\n", "")
        return len(all_new_articles)

    def run_continuously(self):
        """Run the monitor continuously"""
        self.log("📡", "RSS Feed Monitor started!")
        self.log("⏰", f"Current IST: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("🔁", f"Checking feeds every {self.check_interval//60} minutes")
        
        while self.running:
            try:
                self.check_all_feeds()
                next_check = datetime.now(IST) + timedelta(seconds=self.check_interval)
                self.log("⏳", f"Next check at: {next_check.strftime('%H:%M:%S')}")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.log("\n🛑", "Stopping monitor...")
                self.running = False
            except Exception as e:
                self.log("🔥", f"Unexpected error: {str(e)}")
                time.sleep(60)

if __name__ == '__main__':
    monitor = RSSFeedMonitor()
    monitor.run_continuously()