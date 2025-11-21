import os
import sys
import logging
import time
import json
import requests
import mysql.connector
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
import pytz

# Import modules
from curator import ArticleCurator
from prompts import (
    get_prompt_for_section,
    get_section_title,
    format_articles_for_prompt
)

# Load environment variables
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))


class NewsletterGenerator:
    """Generates AI newsletter editions using LLM"""

    def __init__(self):
        self.setup_logger()

        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME', 'rss_reader')
        }

        self.lmstudio_url = os.getenv(
            'LMSTUDIO_URL',
            'http://host.docker.internal:1234/v1/chat/completions'
        )

        # Initialize curator
        self.curator = ArticleCurator(self.db_config, self.logger)

        # Value chain areas in order
        self.value_chain_order = ['chips', 'models', 'applications', 'policy', 'business']

    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('NewsletterGenerator')
        self.logger.setLevel(logging.INFO)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # File handler
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'generator.log'),
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

    def test_lmstudio_connection(self):
        """Test if LMStudio is available"""
        try:
            test_url = self.lmstudio_url.replace('/v1/chat/completions', '/v1/models')
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                self.logger.info("✓ LMStudio connection successful")
                return True
            else:
                self.logger.warning("✗ LMStudio responded with error")
                return False
        except Exception as e:
            self.logger.error(f"✗ Cannot connect to LMStudio: {e}")
            return False

    def generate_section_with_llm(self, value_chain_area, articles):
        """Generate a newsletter section using LLM"""
        if not articles:
            self.logger.warning(f"No articles for {value_chain_area}, skipping section")
            return None

        # Format articles for prompt
        articles_summary = format_articles_for_prompt(articles)

        # Get appropriate prompt
        prompt = get_prompt_for_section(value_chain_area)
        full_prompt = prompt.format(articles_summary=articles_summary)

        # Call LLM
        try:
            response = requests.post(
                self.lmstudio_url,
                json={
                    "model": "llama-3.1-8b",
                    "messages": [{"role": "user", "content": full_prompt}],
                    "temperature": 0.7,  # More creative for storytelling
                    "max_tokens": 700  # ~500 words
                },
                timeout=60
            )

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                self.logger.info(f"  ✓ Generated section for {value_chain_area} ({len(content)} chars)")
                return content
            else:
                self.logger.error(f"  ✗ LLM error for {value_chain_area}: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"  ✗ LLM generation failed for {value_chain_area}: {e}")
            return None

    def get_next_edition_number(self):
        """Get the next edition number"""
        conn = self.get_db_connection()
        if not conn:
            return 1

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(edition_number) as max_edition FROM newsletter_editions")
            result = cursor.fetchone()
            cursor.close()

            max_edition = result[0] if result[0] else 0
            return max_edition + 1

        except Exception as e:
            self.logger.error(f"Failed to get edition number: {e}")
            return 1
        finally:
            if conn.is_connected():
                conn.close()

    def save_newsletter(self, publish_date, sections_data, curated_articles):
        """Save newsletter edition and sections to database"""
        conn = self.get_db_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()

            # Get edition number
            edition_number = self.get_next_edition_number()

            # Calculate total word count
            total_words = sum(
                len(section['content'].split())
                for section in sections_data.values()
                if section['content']
            )

            # Count articles used
            articles_used = sum(
                len(articles)
                for articles in curated_articles.values()
            )

            # Generate newsletter title
            title = f"AI Newsletter - Edition #{edition_number}"

            # Create intro text
            intro = (
                f"Welcome to Edition #{edition_number} of our AI Newsletter, "
                f"covering the latest developments across the AI value chain from "
                f"{(publish_date - timedelta(days=4)).strftime('%B %d')} to "
                f"{publish_date.strftime('%B %d, %Y')}."
            )

            # Prepare content JSON
            content_json = {
                'edition_number': edition_number,
                'publish_date': publish_date.isoformat(),
                'sections': sections_data,
                'articles_count': articles_used,
                'word_count': total_words
            }

            # Insert edition
            cursor.execute("""
                INSERT INTO newsletter_editions
                (edition_number, publish_date, title, intro_text, content_json,
                 status, word_count, articles_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                edition_number,
                publish_date.date(),
                title,
                intro,
                json.dumps(content_json),
                'ready',
                total_words,
                articles_used
            ))

            edition_id = cursor.lastrowid

            # Insert sections
            for idx, area in enumerate(self.value_chain_order, 1):
                section = sections_data.get(area)
                if not section or not section['content']:
                    continue

                # Get article IDs
                article_ids = [a['id'] for a in curated_articles.get(area, [])]

                cursor.execute("""
                    INSERT INTO newsletter_sections
                    (edition_id, section_number, section_title, section_content,
                     value_chain_area, article_ids, word_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    edition_id,
                    idx,
                    section['title'],
                    section['content'],
                    area,
                    json.dumps(article_ids),
                    len(section['content'].split())
                ))

            conn.commit()
            cursor.close()

            self.logger.info(f"✓ Newsletter saved: Edition #{edition_number} (ID: {edition_id})")
            return edition_id

        except Exception as e:
            self.logger.error(f"Failed to save newsletter: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn.is_connected():
                conn.close()

    def generate_newsletter(self, publish_date):
        """Generate complete newsletter for a publish date"""
        self.logger.info("=" * 60)
        self.logger.info(f"GENERATING NEWSLETTER FOR {publish_date.strftime('%B %d, %Y')}")
        self.logger.info("=" * 60)

        # Test LLM connection
        if not self.test_lmstudio_connection():
            self.logger.error("LMStudio not available, cannot generate newsletter")
            return None

        # Curate articles
        curated = self.curator.curate_for_newsletter(lookback_hours=96, articles_per_section=5)

        if not curated:
            self.logger.error("Article curation failed")
            return None

        # Generate sections
        sections_data = {}

        for area in self.value_chain_order:
            articles = curated.get(area, [])

            if not articles:
                self.logger.warning(f"No articles for {area}, skipping")
                continue

            self.logger.info(f"\nGenerating section: {area}")
            self.logger.info(f"  Articles to analyze: {len(articles)}")

            # Generate content
            content = self.generate_section_with_llm(area, articles)

            if content:
                sections_data[area] = {
                    'title': get_section_title(area),
                    'content': content,
                    'article_count': len(articles)
                }

                # Rate limiting
                time.sleep(2)
            else:
                self.logger.warning(f"  Failed to generate section for {area}")

        # Check if we have enough sections
        if len(sections_data) < 3:
            self.logger.error(f"Only generated {len(sections_data)} sections, need at least 3")
            return None

        # Save newsletter
        edition_id = self.save_newsletter(publish_date, sections_data, curated)

        if edition_id:
            self.logger.info("=" * 60)
            self.logger.info(f"✓ NEWSLETTER GENERATION COMPLETE")
            self.logger.info(f"  Edition ID: {edition_id}")
            self.logger.info(f"  Sections: {len(sections_data)}")
            total_words = sum(len(s['content'].split()) for s in sections_data.values())
            self.logger.info(f"  Total words: {total_words}")
            self.logger.info("=" * 60)

        return edition_id

    def get_next_publish_date(self):
        """Calculate next publish date (Monday or Thursday at 8 AM IST)"""
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)

        # Publish days: Monday (0) and Thursday (3)
        publish_days = [0, 3]

        # Find next publish day
        current_weekday = now_ist.weekday()

        for day in publish_days:
            if day > current_weekday:
                days_ahead = day - current_weekday
                next_date = now_ist + timedelta(days=days_ahead)
                return next_date.replace(hour=8, minute=0, second=0, microsecond=0)

        # If no day this week, get next Monday
        days_ahead = (7 - current_weekday) + 0  # Next Monday
        next_date = now_ist + timedelta(days=days_ahead)
        return next_date.replace(hour=8, minute=0, second=0, microsecond=0)

    def run(self):
        """Run newsletter generator with IST scheduling"""
        self.logger.info("=" * 60)
        self.logger.info("NEWSLETTER GENERATOR STARTING")
        self.logger.info("=" * 60)
        self.logger.info("Schedule: Monday & Thursday at 8:00 AM IST")
        self.logger.info(f"Database: {self.db_config['host']}/{self.db_config['database']}")
        self.logger.info("=" * 60)

        try:
            while True:
                ist = pytz.timezone('Asia/Kolkata')
                now_ist = datetime.now(ist)

                # Check if it's generation time
                # Generate the night before (11 PM IST = 9 hours before publish)
                weekday = now_ist.weekday()
                hour = now_ist.hour

                # Sunday 11 PM for Monday newsletter
                # Wednesday 11 PM for Thursday newsletter
                should_generate = (
                    (weekday == 6 and hour == 23) or  # Sunday 11 PM
                    (weekday == 2 and hour == 23)     # Wednesday 11 PM
                )

                if should_generate:
                    # Calculate publish date (next day at 8 AM)
                    publish_date = now_ist + timedelta(days=1)
                    publish_date = publish_date.replace(hour=8, minute=0, second=0, microsecond=0)

                    # Generate newsletter
                    self.generate_newsletter(publish_date)

                    # Sleep for 2 hours to avoid duplicate generation
                    self.logger.info("Sleeping for 2 hours to avoid duplicate...")
                    time.sleep(7200)
                else:
                    # Calculate next generation time
                    next_gen = self.get_next_publish_date() - timedelta(hours=9)  # 11 PM night before
                    wait_seconds = (next_gen - now_ist).total_seconds()

                    if wait_seconds < 0:
                        wait_seconds = 3600  # If calculation error, wait 1 hour

                    self.logger.info(
                        f"Next generation: {next_gen.strftime('%Y-%m-%d %H:%M:%S IST')} "
                        f"({wait_seconds/3600:.1f} hours)"
                    )

                    time.sleep(min(wait_seconds, 3600))  # Check at least every hour

        except KeyboardInterrupt:
            self.logger.info("\n\nShutting down Newsletter Generator...")
        except Exception as e:
            self.logger.error(f"\nFatal error: {e}")
            self.logger.info("Retrying in 5 minutes...")
            time.sleep(300)


if __name__ == "__main__":
    generator = NewsletterGenerator()
    generator.run()
