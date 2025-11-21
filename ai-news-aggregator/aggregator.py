import os
import sys
import logging
import time
import mysql.connector
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv

# Import collectors
from reddit_collector import RedditCollector
from rss_collector import RSSCollector

# Load environment variables
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))


class AINewsAggregator:
    """Main orchestrator for AI news collection"""

    def __init__(self):
        self.setup_logger()
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME', 'rss_reader')
        }

        # Initialize collectors
        self.rss_collector = RSSCollector(self.db_config, self.logger)
        self.reddit_collector = RedditCollector(self.db_config, self.logger)

        # Create tables if they don't exist
        self.initialize_database()

    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('AINewsAggregator')
        self.logger.setLevel(logging.INFO)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # File handler
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'aggregator.log'),
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

    def get_db_connection(self):
        """Create database connection"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return None

    def initialize_database(self):
        """Create tables if they don't exist"""
        conn = self.get_db_connection()
        if not conn:
            self.logger.error("Cannot initialize database: connection failed")
            return False

        try:
            cursor = conn.cursor()

            # Read and execute SQL file
            sql_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'database',
                'init_ai_newsletter.sql'
            )

            if os.path.exists(sql_file):
                self.logger.info("Initializing database schema...")
                with open(sql_file, 'r') as f:
                    sql_content = f.read()

                # Execute each statement separately
                statements = sql_content.split(';')
                for statement in statements:
                    statement = statement.strip()
                    if statement and not statement.startswith('--'):
                        try:
                            cursor.execute(statement)
                        except mysql.connector.Error as e:
                            # Ignore "already exists" errors
                            if 'already exists' not in str(e).lower():
                                self.logger.warning(f"SQL warning: {e}")

                conn.commit()
                self.logger.info("✓ Database schema initialized")
            else:
                self.logger.warning(f"SQL file not found: {sql_file}")

            cursor.close()
            return True

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return False
        finally:
            if conn.is_connected():
                conn.close()

    def cleanup_old_articles(self, days=7):
        """Remove articles older than specified days"""
        conn = self.get_db_connection()
        if not conn:
            return 0

        try:
            cursor = conn.cursor()
            cutoff = datetime.now() - timedelta(days=days)

            cursor.execute("""
                DELETE FROM ai_news_articles
                WHERE published_at < %s
            """, (cutoff,))

            deleted = cursor.rowcount
            conn.commit()
            cursor.close()

            if deleted > 0:
                self.logger.info(f"Cleaned up {deleted} old articles")

            return deleted

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return 0
        finally:
            if conn.is_connected():
                conn.close()

    def get_collection_stats(self):
        """Get statistics about collected articles"""
        conn = self.get_db_connection()
        if not conn:
            return {}

        try:
            cursor = conn.cursor(dictionary=True)

            # Total articles
            cursor.execute("SELECT COUNT(*) as total FROM ai_news_articles")
            stats = cursor.fetchone()

            # By value chain
            cursor.execute("""
                SELECT value_chain_area, COUNT(*) as count
                FROM ai_news_articles
                GROUP BY value_chain_area
                ORDER BY count DESC
            """)
            stats['by_category'] = cursor.fetchall()

            # Recent articles (last 24 hours)
            cursor.execute("""
                SELECT COUNT(*) as recent
                FROM ai_news_articles
                WHERE collected_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """)
            stats['recent_24h'] = cursor.fetchone()['recent']

            cursor.close()
            return stats

        except Exception as e:
            self.logger.error(f"Stats collection failed: {e}")
            return {}
        finally:
            if conn.is_connected():
                conn.close()

    def collect_all_sources(self):
        """Run collection from all sources"""
        self.logger.info("=" * 60)
        self.logger.info(f"COLLECTION CYCLE START - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 60)

        total_collected = 0

        # Collect from RSS feeds
        try:
            rss_count = self.rss_collector.collect_all()
            total_collected += rss_count
        except Exception as e:
            self.logger.error(f"RSS collection failed: {e}")

        # Collect from Reddit
        try:
            reddit_count = self.reddit_collector.collect_all()
            total_collected += reddit_count
        except Exception as e:
            self.logger.error(f"Reddit collection failed: {e}")

        # Cleanup old articles
        self.cleanup_old_articles(days=7)

        # Print statistics
        stats = self.get_collection_stats()

        self.logger.info("=" * 60)
        self.logger.info("COLLECTION CYCLE COMPLETE")
        self.logger.info("=" * 60)
        self.logger.info(f"New articles collected: {total_collected}")
        self.logger.info(f"Total articles in database: {stats.get('total', 0)}")
        self.logger.info(f"Recent articles (24h): {stats.get('recent_24h', 0)}")

        if stats.get('by_category'):
            self.logger.info("\nArticles by category:")
            for cat in stats['by_category']:
                self.logger.info(f"  {cat['value_chain_area']}: {cat['count']}")

        return total_collected

    def run(self, interval_hours=2):
        """Run the aggregator continuously"""
        self.logger.info("=" * 60)
        self.logger.info("AI NEWS AGGREGATOR STARTING")
        self.logger.info("=" * 60)
        self.logger.info(f"Collection interval: {interval_hours} hours")
        self.logger.info(f"Database: {self.db_config['host']}/{self.db_config['database']}")
        self.logger.info("=" * 60)

        try:
            while True:
                # Run collection
                self.collect_all_sources()

                # Calculate next run time
                next_run = datetime.now() + timedelta(hours=interval_hours)
                self.logger.info(f"\nNext collection at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"Sleeping for {interval_hours} hours...\n")

                # Sleep
                time.sleep(interval_hours * 3600)

        except KeyboardInterrupt:
            self.logger.info("\n\nShutting down AI News Aggregator...")
        except Exception as e:
            self.logger.error(f"\nFatal error: {e}")
            self.logger.info("Retrying in 5 minutes...")
            time.sleep(300)


if __name__ == "__main__":
    aggregator = AINewsAggregator()

    # Run every 2 hours
    aggregator.run(interval_hours=2)
