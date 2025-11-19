import mysql.connector
from mysql.connector import Error
from newspaper import Article
import json
import time
import random
from datetime import datetime
from urllib.parse import urlparse
import pytz
from dotenv import load_dotenv
import logging
import os
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
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

# Timezone setup
IST = pytz.timezone('Asia/Kolkata')

# User agents for rotation (avoid blocking)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
]

class ArticleExtractor:
    def __init__(self):
        self.setup_logger()
        self.create_tables()
        self.last_request_time = defaultdict(float)  # Track last request per domain
        self.failed_urls = set()  # Track permanently failed URLs

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

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(console_handler)

    def log(self, message, level='info'):
        """Log messages"""
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'warning':
            self.logger.warning(message)

    def create_db_connection(self):
        """Create and return MySQL connection"""
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            return conn
        except Error as e:
            self.log(f"Database connection error: {str(e)}", 'error')
            return None

    def create_tables(self):
        """Ensure content table and failed_articles table exist"""
        connection = self.create_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Create article_content table
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

            # Create failed_articles tracking table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_articles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                article_id INT NOT NULL,
                url VARCHAR(512),
                error_type VARCHAR(100),
                error_message TEXT,
                attempt_count INT DEFAULT 1,
                last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                should_retry BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (article_id) REFERENCES feed_metadata(id),
                INDEX idx_article_id (article_id),
                INDEX idx_should_retry (should_retry),
                INDEX idx_last_attempt (last_attempt)
            )
            """)

            connection.commit()
            self.log("Database tables verified/created")
            return True
        except Error as e:
            self.log(f"Error creating tables: {str(e)}", 'error')
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def get_random_user_agent(self):
        """Get random user agent to avoid blocking"""
        return random.choice(USER_AGENTS)

    def resolve_google_news_redirect(self, url):
        """
        Resolve Google News redirect URLs to actual article URLs

        Google News RSS feeds contain redirect URLs like:
        https://news.google.com/rss/articles/CBMi...

        These need to be resolved to the actual article URL
        """
        if 'news.google.com' not in url:
            return url

        try:
            # Follow redirects to get final URL
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=10,
                headers={'User-Agent': self.get_random_user_agent()}
            )
            final_url = response.url

            # Verify it's a real article URL (not another Google URL)
            if 'google.com' in final_url and 'news.google.com' in final_url:
                self.log(f"⚠️  Redirect still points to Google: {final_url[:80]}", 'warning')
                return None

            self.log(f"✓ Resolved Google News URL to: {final_url[:80]}...")
            return final_url

        except Exception as e:
            self.log(f"Failed to resolve Google News redirect: {str(e)}", 'error')
            return None

    def rate_limited_request(self, url):
        """
        Implement rate limiting per domain to avoid being blocked
        Waits at least 2 seconds between requests to the same domain
        """
        domain = urlparse(url).netloc
        current_time = time.time()
        time_since_last = current_time - self.last_request_time[domain]

        if time_since_last < 2.0:
            sleep_time = 2.0 - time_since_last
            self.log(f"Rate limiting: waiting {sleep_time:.1f}s for {domain}")
            time.sleep(sleep_time)

        self.last_request_time[domain] = time.time()

    def extract_with_newspaper(self, url):
        """Extract article content using newspaper3k library"""
        try:
            article = Article(url)
            article.config.browser_user_agent = self.get_random_user_agent()
            article.config.request_timeout = 15

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
                'keywords': article.keywords[:10] if article.keywords else [],  # Top 10 keywords
                'summary': article.summary
            }
        except Exception as e:
            raise Exception(f"newspaper3k failed: {str(e)}")

    def extract_with_beautifulsoup(self, url):
        """
        Fallback extraction method using BeautifulSoup
        Used when newspaper3k fails
        """
        try:
            self.log(f"Trying BeautifulSoup fallback for {url[:50]}...")

            response = requests.get(
                url,
                timeout=15,
                headers={'User-Agent': self.get_random_user_agent()}
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                script.decompose()

            # Try to find article content
            # Common article containers
            article_content = (
                soup.find('article') or
                soup.find('div', class_=lambda x: x and ('article' in x.lower() or 'content' in x.lower())) or
                soup.find('div', id=lambda x: x and ('article' in x.lower() or 'content' in x.lower()))
            )

            if article_content:
                paragraphs = article_content.find_all('p')
            else:
                paragraphs = soup.find_all('p')

            # Extract text from paragraphs
            text_content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

            # Extract title
            title = soup.find('h1')
            title_text = title.get_text().strip() if title else ''

            # Extract images
            images = []
            for img in soup.find_all('img', src=True):
                img_url = img['src']
                if img_url.startswith(('http://', 'https://')):
                    images.append(img_url)
                elif img_url.startswith('/'):
                    # Convert relative URL to absolute
                    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    images.append(base_url + img_url)

            # Generate simple summary (first 3 paragraphs)
            summary_paragraphs = [p.get_text().strip() for p in paragraphs[:3] if p.get_text().strip()]
            summary = '\n'.join(summary_paragraphs)

            if not text_content or len(text_content) < 100:
                raise Exception("Insufficient content extracted")

            return {
                'full_text': text_content,
                'cleaned_text': text_content,
                'authors': [],
                'top_image': images[0] if images else None,
                'images': images[:5],
                'keywords': [],
                'summary': summary[:500] if summary else text_content[:500]
            }

        except Exception as e:
            raise Exception(f"BeautifulSoup failed: {str(e)}")

    def extract_article_content_with_retry(self, url, max_retries=3):
        """
        Extract article content with intelligent retry and fallback mechanisms

        Process:
        1. Resolve Google News redirects
        2. Try newspaper3k with exponential backoff
        3. Fallback to BeautifulSoup if newspaper3k fails
        4. Track failures in database
        """
        # Check if URL is in permanently failed list
        if url in self.failed_urls:
            self.log(f"Skipping permanently failed URL: {url[:50]}")
            return None, 'permanently_failed'

        # Step 1: Resolve Google News redirects
        original_url = url
        if 'news.google.com' in url:
            url = self.resolve_google_news_redirect(url)
            if not url:
                return None, 'redirect_failed'

        # Step 2: Apply rate limiting
        self.rate_limited_request(url)

        # Step 3: Try extraction with retry logic
        last_error = None

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.log(f"Retry attempt {attempt + 1}/{max_retries} for {url[:50]}...")

                # Try newspaper3k first
                content = self.extract_with_newspaper(url)

                # Validate content
                if content and content.get('full_text') and len(content['full_text']) > 100:
                    self.log(f"✓ Extracted {len(content['full_text'])} chars from {url[:50]}")
                    return content, None
                else:
                    raise Exception("Insufficient content extracted")

            except Exception as e:
                last_error = str(e)
                error_type = type(e).__name__

                # Check for permanent failures (don't retry these)
                if '404' in str(e) or '410' in str(e):
                    self.log(f"Permanent failure (404/410): {url[:50]}", 'warning')
                    self.failed_urls.add(original_url)
                    return None, 'not_found'

                # Log the error
                self.log(f"Attempt {attempt + 1} failed: {error_type} - {str(e)[:100]}", 'error')

                # Exponential backoff (1s, 2s, 4s)
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    time.sleep(backoff_time)

        # Step 4: Final attempt with BeautifulSoup fallback
        try:
            self.log(f"Trying BeautifulSoup fallback for {url[:50]}...")
            content = self.extract_with_beautifulsoup(url)

            if content and content.get('full_text') and len(content['full_text']) > 100:
                self.log(f"✓ BeautifulSoup extracted {len(content['full_text'])} chars")
                return content, None

        except Exception as e:
            last_error = f"All methods failed. Last: {str(e)}"
            self.log(f"BeautifulSoup also failed: {str(e)[:100]}", 'error')

        # All methods failed
        return None, last_error

    def track_failed_article(self, article_id, url, error_type, error_message):
        """Track failed article extraction in database"""
        connection = self.create_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Check if already exists
            cursor.execute("""
                SELECT id, attempt_count FROM failed_articles
                WHERE article_id = %s
            """, (article_id,))

            existing = cursor.fetchone()

            # Determine if we should retry this article
            should_retry = True
            if error_type in ['not_found', 'permanently_failed', 'redirect_failed']:
                should_retry = False

            if existing:
                # Update existing record
                cursor.execute("""
                    UPDATE failed_articles
                    SET attempt_count = attempt_count + 1,
                        error_message = %s,
                        error_type = %s,
                        should_retry = %s,
                        last_attempt = NOW()
                    WHERE article_id = %s
                """, (error_message[:500], error_type, should_retry, article_id))
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO failed_articles
                    (article_id, url, error_type, error_message, attempt_count, should_retry)
                    VALUES (%s, %s, %s, %s, 1, %s)
                """, (article_id, url[:500], error_type, error_message[:500], should_retry))

            connection.commit()
            return True

        except Error as e:
            self.log(f"Failed to track failure: {str(e)}", 'error')
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def get_unprocessed_urls(self, limit=10):
        """
        Fetch URLs that haven't been processed yet
        Excludes articles that have failed too many times
        """
        connection = self.create_db_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(dictionary=True)

            # Get unprocessed articles, excluding those that shouldn't be retried
            cursor.execute("""
                SELECT fm.id, fm.url, fm.source
                FROM feed_metadata fm
                LEFT JOIN article_content ac ON fm.id = ac.url_id
                LEFT JOIN failed_articles fa ON fm.id = fa.article_id
                WHERE ac.url_id IS NULL
                  AND (fa.article_id IS NULL OR (fa.should_retry = TRUE AND fa.attempt_count < 5))
                ORDER BY fm.published_at DESC
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
        """Save extracted content to database"""
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
            self.log(f"✓ Saved content for URL ID: {url_id}")
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
        """Process a batch of unprocessed articles with enhanced extraction"""
        unprocessed = self.get_unprocessed_urls(batch_size)
        if not unprocessed:
            self.log("No unprocessed articles found")
            return 0

        self.log(f"Processing {len(unprocessed)} articles...")

        processed_count = 0
        failed_count = 0

        for article in unprocessed:
            article_id = article['id']
            url = article['url']
            source = article['source']

            self.log(f"Processing: {source} - {url[:60]}...")

            # Extract with retry and fallback
            content, error = self.extract_article_content_with_retry(url)

            if content:
                if self.save_content(article_id, content):
                    processed_count += 1
                else:
                    self.log(f"✗ Failed to save content for {article_id}", 'error')
            else:
                # Track failure
                self.track_failed_article(article_id, url, error or 'unknown', error or 'Extraction failed')
                failed_count += 1
                self.log(f"✗ Failed to extract: {url[:60]}", 'error')

        self.log(f"Batch complete: ✓ {processed_count} success, ✗ {failed_count} failed")
        return processed_count

    def get_statistics(self):
        """Get extraction statistics"""
        connection = self.create_db_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor(dictionary=True)

            # Overall stats
            cursor.execute("""
                SELECT
                    COUNT(fm.id) as total_articles,
                    COUNT(ac.id) as processed,
                    COUNT(fm.id) - COUNT(ac.id) as unprocessed,
                    ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
                FROM feed_metadata fm
                LEFT JOIN article_content ac ON fm.id = ac.url_id
            """)
            overall = cursor.fetchone()

            # Failed articles by type
            cursor.execute("""
                SELECT
                    error_type,
                    COUNT(*) as count,
                    SUM(CASE WHEN should_retry THEN 1 ELSE 0 END) as retryable
                FROM failed_articles
                GROUP BY error_type
                ORDER BY count DESC
            """)
            failures = cursor.fetchall()

            return {
                'overall': overall,
                'failures': failures
            }

        except Error as e:
            self.log(f"Error getting statistics: {str(e)}", 'error')
            return None
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def run_continuously(self, interval=300):
        """Run the extractor continuously with statistics reporting"""
        self.log("=" * 60)
        self.log("Article Extractor V2 (Enhanced) Started")
        self.log("Features: Google News redirect resolution, retry logic, BeautifulSoup fallback")
        self.log(f"Checking for new articles every {interval//60} minutes")
        self.log("=" * 60)

        cycle_count = 0

        while True:
            try:
                cycle_count += 1
                self.log(f"\n{'='*60}")
                self.log(f"Cycle #{cycle_count} - {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}")
                self.log(f"{'='*60}")

                # Process batch
                processed = self.process_batch()

                # Show statistics every 10 cycles or if nothing processed
                if cycle_count % 10 == 0 or processed == 0:
                    stats = self.get_statistics()
                    if stats and stats['overall']:
                        self.log(f"\n📊 Statistics:")
                        self.log(f"  Total: {stats['overall']['total_articles']:,}")
                        self.log(f"  Processed: {stats['overall']['processed']:,}")
                        self.log(f"  Unprocessed: {stats['overall']['unprocessed']:,}")
                        self.log(f"  Success Rate: {stats['overall']['success_rate']}%")

                        if stats['failures']:
                            self.log(f"\n  Failed by type:")
                            for failure in stats['failures'][:5]:
                                self.log(f"    - {failure['error_type']}: {failure['count']} (retryable: {failure['retryable']})")

                # Adjust sleep time based on activity
                if processed == 0:
                    sleep_time = 60  # 1 minute if nothing to process
                else:
                    sleep_time = interval

                self.log(f"\nNext check in {sleep_time}s...")
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                self.log("\n\nShutting down article extractor...")
                break
            except Exception as e:
                self.log(f"Unexpected error: {str(e)}", 'error')
                time.sleep(60)


if __name__ == '__main__':
    extractor = ArticleExtractor()
    extractor.run_continuously()
