import mysql.connector
from mysql.connector import Error
import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
import requests
from logging.handlers import TimedRotatingFileHandler
from newspaper import Article, Config

# Load environment variables
load_dotenv()

# Timezone setup
UTC = pytz.utc
IST = pytz.timezone('Asia/Kolkata')

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

class ContentBackfiller:
    def __init__(self):
        self.setup_logger()
        # Configure newspaper
        self.news_config = Config()
        self.news_config.browser_user_agent = 'Mozilla/5.0'
        self.news_config.request_timeout = 10
        
    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('ContentBackfiller')
        self.logger.setLevel(logging.INFO)
        
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'content_backfill.log'),
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
        print(f"{datetime.now(IST).strftime('%H:%M:%S')} {emoji} {message}")
        self.logger.info(message)

    def create_db_connection(self):
        """Create and return MySQL connection"""
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            self.log_console("🛢️", "Database connection established!")
            return conn
        except Error as e:
            self.log_console("❌", f"Error connecting to database: {str(e)}")
            return None

    def get_articles_without_content(self):
        """Get articles that don't have content in article_content table"""
        connection = self.create_db_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT fm.* FROM feed_metadata fm
                LEFT JOIN article_content ac ON fm.id = ac.id
                WHERE ac.id IS NULL
            """)
            articles = cursor.fetchall()
            self.log_console("📊", f"Found {len(articles)} articles without content")
            return articles
        except Error as e:
            self.log_console("❌", f"Error fetching articles: {str(e)}")
            return []
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def extract_content(self, url):
        """Extract article content using newspaper3k"""
        try:
            article = Article(url, config=self.news_config)
            article.download()
            article.parse()
            
            # Extract content and image
            content = article.text
            top_image = article.top_image
            
            return {
                'content': content,
                'top_image': top_image
            }
        except Exception as e:
            self.log_console("⚠️", f"Error extracting content: {str(e)}")
            return None

    def store_content(self, article_id, content_data):
        """Store article content in the database"""
        if not content_data or not content_data['content']:
            return False

        connection = self.create_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO article_content (id, content, top_image, extracted_at)
                VALUES (%s, %s, %s, %s)
            """, (
                article_id, 
                content_data['content'],
                content_data['top_image'],
                datetime.now(IST)
            ))
            connection.commit()
            self.log_console("💾", f"Stored content for article ID: {id}")
            return True
        except Error as e:
            self.log_console("❌", f"Error storing content: {str(e)}")
            connection.rollback()
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def process_backlog(self):
        """Process all articles without content"""
        self.log_console("🚀", "Starting content backfill process")
        
        articles = self.get_articles_without_content()
        success_count = 0
        
        for article in articles:
            self.log_console("📝", f"Processing article: {article['title'][:50]}...")
            content_data = self.extract_content(article['url'])
            
            if content_data and self.store_content(article['id'], content_data):
                success_count += 1
            
        self.log_console("✅", f"Completed! Successfully processed {success_count}/{len(articles)} articles")

if __name__ == '__main__':
    backfiller = ContentBackfiller()
    backfiller.process_backlog()


