import os
import requests
import mysql.connector
from datetime import datetime
import logging
from dotenv import load_dotenv
import time
import html

# Load environment variables
load_dotenv()

class TelegramPublisher:
    def __init__(self):
        self.setup_logger()
        self.load_config()
        self.validate_credentials() 
        self.create_published_table()
        self.failed_articles = {}  # Track failed article attempts

    def setup_logger(self):
        """Configure logging"""
        self.logger = logging.getLogger('TelegramPublisher')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # File handler
        fh = logging.FileHandler('rss_feed/logs/telegram_publisher.log')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def load_config(self):
        """Load configuration from environment variables"""
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        self.db_config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME')
        }

    def validate_credentials(self):
        """Validate Telegram credentials"""
        if not self.telegram_token or not self.channel_id:
            self.logger.error("Missing Telegram configuration in .env file")
            raise ValueError("Telegram credentials not configured")

    def create_published_table(self):
        """Ensure the published articles table exists"""
        conn = self.get_db_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS telegram_published (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        article_id INT NOT NULL,
                        published_at DATETIME NOT NULL,
                        FOREIGN KEY (article_id) REFERENCES feed_metadata(id),
                        UNIQUE KEY unique_article (article_id)
                    )
                """)
                conn.commit()
                self.logger.info("Verified telegram_published table exists")
            return True
        except Exception as e:
            self.logger.error(f"Error creating table: {str(e)}")
            return False
        finally:
            if conn.is_connected():
                conn.close()

    def get_db_connection(self):
        """Create and return database connection"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            self.logger.error(f"Database connection failed: {str(e)}")
            return None

    def get_unpublished_articles(self, limit=5):
        """Fetch articles that haven't been published yet"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            with conn.cursor(dictionary=True) as cursor:
                query = """
                SELECT 
                    fm.id, fm.title as headline, fm.url, 
                    fm.published_at, fm.source,
                    ac.summary, ac.top_image
                FROM feed_metadata fm
                JOIN article_content ac ON fm.id = ac.url_id
                LEFT JOIN telegram_published tp ON fm.id = tp.article_id
                WHERE tp.article_id IS NULL
                ORDER BY fm.published_at DESC
                LIMIT %s
                """
                cursor.execute(query, (limit,))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Database query failed: {str(e)}")
            return []
        finally:
            if conn.is_connected():
                conn.close()

    def format_summary_bullets(self, summary):
        """Convert summary text to bullet points"""
        if not summary:
            return ""
        
        # Split into sentences and clean
        sentences = [s.strip() for s in summary.split('.') if s.strip()]
        
        # Format as bullets (max 5)
        return "\n".join(f"• {sentence}." for sentence in sentences[:5])

    def format_message(self, article):
        """Format the article for Telegram with all requested changes"""
        headline = html.escape(article['headline'])
        source = html.escape(article['source'])
        date_str = article['published_at'].strftime('%b %d, %Y') if article['published_at'] else ''
        
        message = (
            f"<b>{headline}</b>\n\n"
            f"📅 {date_str} | 📰 {source}\n\n"
            f"{self.format_summary_bullets(article['summary'])}\n\n"
            f"<a href='{article['url']}'>Read full article</a>"
        )
        
        # Truncate if too long (Telegram has 4096 char limit)
        return message[:4000] + "..." if len(message) > 4000 else message

    def send_to_telegram(self, article):
        """Send article to Telegram channel in a single message with image"""
        message = self.format_message(article)
        
        # If we have an image, send as photo with caption
        if article.get('top_image'):
            try:
                response = requests.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendPhoto",
                    json={
                        'chat_id': self.channel_id,
                        'photo': article['top_image'],
                        'caption': message,
                        'parse_mode': 'HTML',
                        'disable_web_page_preview': True,
                        'disable_notification': False
                    },
                    timeout=10
                )
                response.raise_for_status()
                return True
            except Exception as e:
                self.logger.error(f"Failed to send image with caption: {str(e)}")
                # Fall back to text-only if image send fails
                return self.send_text_message(message)
        
        # If no image, send as regular text message
        return self.send_text_message(message)

    def send_text_message(self, message):
        """Helper method to send text-only messages"""
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={
                    'chat_id': self.channel_id,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True,
                    'disable_notification': False
                },
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Failed to send text message: {str(e)}")
            return False

    def mark_as_published(self, article_id):
        """Mark article as published in database"""
        conn = self.get_db_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO telegram_published (article_id, published_at)
                    VALUES (%s, %s)
                """, (article_id, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to mark as published: {str(e)}")
            conn.rollback()
            return False
        finally:
            if conn.is_connected():
                conn.close()

    def process_articles(self):
        """Process and publish articles"""
        articles = self.get_unpublished_articles()
        if not articles:
            self.logger.info("No new articles to publish")
            return 0

        success_count = 0
        for article in articles:
            article_id = article['id']
            
            # Check if article has failed too many times
            if article_id in self.failed_articles:
                if self.failed_articles[article_id] >= 5:
                    self.logger.warning(f"Skipping article {article_id} after 5 failed attempts")
                    continue
                self.failed_articles[article_id] += 1
            else:
                self.failed_articles[article_id] = 1
            
            if self.send_to_telegram(article):
                if self.mark_as_published(article_id):
                    success_count += 1
                    self.logger.info(f"Published: {article['headline'][:50]}...")
                    # Remove from failed articles tracking on success
                    if article_id in self.failed_articles:
                        del self.failed_articles[article_id]
                    time.sleep(3)  # Respect Telegram rate limits
                else:
                    self.logger.warning(f"Failed to mark as published: {article_id}")
            else:
                self.logger.error(f"Failed to publish: {article_id}")

        return success_count

    def run(self, interval=300):
        """Run the publisher continuously"""
        self.logger.info("Starting Telegram publisher service")
        try:
            while True:
                processed = self.process_articles()
                sleep_time = 60 if processed == 0 else interval
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            self.logger.info("Stopping publisher...")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    publisher = TelegramPublisher()
    publisher.run()