import mysql.connector
from mysql.connector import Error
from newspaper import Article
import json
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
import logging
import os
from urllib.parse import urljoin
from dotenv import load_dotenv
from logging.handlers import TimedRotatingFileHandler

# Load environment variables
load_dotenv()

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# Timezone setup
IST = pytz.timezone('Asia/Kolkata')

class ArticleExtractor:
    def __init__(self):
        self.setup_logger()
        self.create_tables()

    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('ArticleExtractor')
        self.logger.setLevel(logging.INFO)
        
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'article_extractor.log'),
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)

    def log(self, message, level='info'):
        """Log messages"""
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)
        print(f"{datetime.now(IST).strftime('%H:%M:%S')} {message}")

    def create_db_connection(self):
        """Create and return MySQL connection"""
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            self.log("Database connection established")
            return conn
        except Error as e:
            self.log(f"Database connection error: {str(e)}", 'error')
            return None

    def create_tables(self):
        """Ensure content table exists with image support"""
        connection = self.create_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            
            # Check if images column exists
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'article_content' AND column_name = 'images'
            """)
            column_exists = cursor.fetchone()[0] > 0
            
            # Create table if not exists
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_content (
                id INT AUTO_INCREMENT PRIMARY KEY,
                url_id INT NOT NULL,
                full_text LONGTEXT,
                cleaned_text LONGTEXT,
                authors JSON,
                top_image VARCHAR(512),
                images JSON,
                keywords JSON,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (url_id) REFERENCES feed_metadata(id),
                UNIQUE KEY unique_url_content (url_id)
            )
            """)
            
            # Add images column if it doesn't exist
            if not column_exists:
                cursor.execute("ALTER TABLE article_content ADD COLUMN images JSON")
            
            connection.commit()
            self.log("Content table verified/created")
            return True
        except Error as e:
            self.log(f"Error creating tables: {str(e)}", 'error')
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def extract_article_content(self, url):
        """Extract content from article URL including images"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            article.nlp()  # Perform NLP processing
            
            # Process and store images
            images = []
            if article.images:
                images = [img for img in article.images if img.startswith(('http://', 'https://'))]
            
            return {
                'full_text': article.text,
                'cleaned_text': '\n'.join([p for p in article.text.split('\n') if p.strip()]),
                'authors': article.authors,
                'top_image': article.top_image if article.top_image else None,
                'images': images[:5],  # Store up to 5 images
                'keywords': article.keywords,
                'summary': article.summary
            }
        except Exception as e:
            self.log(f"Failed to extract {url}: {str(e)}", 'error')
            return None

    def get_unprocessed_urls(self, limit=10):
        """Fetch URLs that haven't been processed yet"""
        connection = self.create_db_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT fm.id, fm.url 
                FROM feed_metadata fm
                LEFT JOIN article_content ac ON fm.id = ac.url_id
                WHERE ac.url_id IS NULL
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
        except Error as e:
            self.log(f"Error fetching unprocessed URLs: {str(e)}", 'error')
            return []
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def save_content(self, url_id, content):
        """Save extracted content to database including images"""
        connection = self.create_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO article_content (
                    url_id, full_text, cleaned_text, 
                    authors, top_image, images,
                    keywords, summary
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                url_id,
                content['full_text'],
                content['cleaned_text'],
                json.dumps(content['authors']),
                content['top_image'],
                json.dumps(content['images']),
                json.dumps(content['keywords']),
                content['summary']
            ))
            connection.commit()
            self.log(f"Saved content for URL ID: {url_id}")
            return True
        except Error as e:
            connection.rollback()
            self.log(f"Failed to save content: {str(e)}", 'error')
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def process_batch(self, batch_size=5):
        """Process a batch of unprocessed articles"""
        unprocessed = self.get_unprocessed_urls(batch_size)
        if not unprocessed:
            self.log("No unprocessed articles found")
            return 0

        processed_count = 0
        for article in unprocessed:
            content = self.extract_article_content(article['url'])
            if content and self.save_content(article['id'], content):
                processed_count += 1

        return processed_count

    def run_continuously(self, interval=300):
        """Run the extractor continuously"""
        self.log("Article Extractor started")
        self.log(f"Checking for new articles every {interval//60} minutes")

        while True:
            try:
                processed = self.process_batch()
                self.log(f"Processed {processed} articles in this batch")
                
                if processed == 0:
                    time.sleep(60)  # Shorter sleep if nothing processed
                else:
                    time.sleep(interval)
                    
            except KeyboardInterrupt:
                self.log("Stopping article extractor...")
                break
            except Exception as e:
                self.log(f"Unexpected error: {str(e)}", 'error')
                time.sleep(60)


if __name__ == '__main__':
    extractor = ArticleExtractor()
    extractor.run_continuously()