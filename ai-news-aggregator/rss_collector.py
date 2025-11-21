import feedparser
import mysql.connector
from datetime import datetime, timedelta
import logging
import json
import requests
from bs4 import BeautifulSoup
import time


class RSSCollector:
    """Collects AI news from RSS feeds"""

    def __init__(self, db_config, logger=None):
        self.db_config = db_config
        self.logger = logger or logging.getLogger(__name__)

        # User agents for requests
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        ]
        self.current_ua_index = 0

    def get_db_connection(self):
        """Create database connection"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return None

    def get_rss_sources(self):
        """Fetch active RSS sources from database"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, source_name, source_url, category
                FROM ai_news_sources
                WHERE source_type = 'rss' AND active = TRUE
            """)
            sources = cursor.fetchall()
            cursor.close()
            return sources
        except Exception as e:
            self.logger.error(f"Failed to fetch RSS sources: {e}")
            return []
        finally:
            if conn.is_connected():
                conn.close()

    def categorize_by_content(self, title, description):
        """Categorize article based on content keywords"""
        text = (title + ' ' + (description or '')).lower()

        # Value chain categorization
        if any(word in text for word in ['gpu', 'chip', 'nvidia', 'amd', 'tpu', 'hardware', 'semiconductor', 'compute', 'processor']):
            return 'chips'
        elif any(word in text for word in ['model', 'llm', 'gpt', 'claude', 'gemini', 'training', 'research', 'paper', 'arxiv', 'neural', 'transformer']):
            return 'models'
        elif any(word in text for word in ['regulation', 'policy', 'law', 'governance', 'ethics', 'safety', 'alignment', 'government', 'copyright', 'privacy']):
            return 'policy'
        elif any(word in text for word in ['funding', 'investment', 'startup', 'acquisition', 'market', 'revenue', 'valuation', 'ipo', 'venture']):
            return 'business'
        elif any(word in text for word in ['app', 'product', 'tool', 'consumer', 'user', 'interface', 'chatbot', 'assistant', 'application']):
            return 'applications'
        else:
            return 'general'

    def parse_published_date(self, entry):
        """Parse published date from feed entry"""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
            else:
                return datetime.now()
        except Exception:
            return datetime.now()

    def extract_content(self, entry):
        """Extract article content from feed entry"""
        # Try different content fields
        if hasattr(entry, 'content') and entry.content:
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        elif hasattr(entry, 'description'):
            return entry.description
        else:
            return ''

    def clean_html(self, html_content):
        """Clean HTML and extract text"""
        if not html_content:
            return ''

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:5000]  # Limit content size
        except Exception:
            return html_content[:5000]

    def calculate_relevance_score(self, title, description, category):
        """Calculate relevance score based on AI keywords"""
        text = (title + ' ' + (description or '')).lower()

        # High-value AI keywords
        high_value_keywords = [
            'artificial intelligence', 'machine learning', 'deep learning',
            'neural network', 'llm', 'large language model', 'gpt', 'claude',
            'gemini', 'openai', 'anthropic', 'google ai', 'deepmind',
            'breakthrough', 'innovation', 'research', 'nvidia', 'gpu'
        ]

        # Count keyword matches
        score = sum(5 for keyword in high_value_keywords if keyword in text)

        # Bonus for specific categories
        if category in ['models', 'chips', 'policy']:
            score += 10

        # Bonus if 'ai' or 'artificial intelligence' is in title
        if 'ai' in title.lower() or 'artificial intelligence' in title.lower():
            score += 5

        return min(score, 100)  # Cap at 100

    def collect_from_feed(self, source_id, source_name, feed_url, category, hours=48):
        """Collect articles from an RSS feed"""
        try:
            # Parse RSS feed with custom user agent
            feed = feedparser.parse(
                feed_url,
                agent=self.user_agents[self.current_ua_index]
            )

            if feed.bozo and feed.bozo_exception:
                self.logger.warning(f"  {source_name}: Feed parsing warning: {feed.bozo_exception}")

            if not feed.entries:
                self.logger.warning(f"  {source_name}: No entries found")
                return 0

            cutoff_time = datetime.now() - timedelta(hours=hours)
            collected = 0

            conn = self.get_db_connection()
            if not conn:
                return 0

            cursor = conn.cursor()

            for entry in feed.entries:
                try:
                    # Parse date
                    pub_date = self.parse_published_date(entry)

                    # Skip if too old
                    if pub_date < cutoff_time:
                        continue

                    # Extract data
                    title = entry.title if hasattr(entry, 'title') else 'No title'
                    url = entry.link if hasattr(entry, 'link') else ''

                    if not url:
                        continue

                    # Skip if already collected
                    cursor.execute("SELECT id FROM ai_news_articles WHERE url = %s", (url,))
                    if cursor.fetchone():
                        continue

                    # Extract and clean content
                    raw_content = self.extract_content(entry)
                    cleaned_content = self.clean_html(raw_content)
                    description = entry.summary if hasattr(entry, 'summary') else cleaned_content[:500]

                    # Categorize
                    value_chain = self.categorize_by_content(title, description)

                    # Calculate relevance
                    relevance = self.calculate_relevance_score(title, description, value_chain)

                    # Extract author
                    author = entry.author if hasattr(entry, 'author') else 'Unknown'

                    # Insert into database
                    cursor.execute("""
                        INSERT INTO ai_news_articles
                        (source_id, title, url, content, summary, author, published_at,
                         topic_tags, value_chain_area, engagement_score, relevance_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        source_id,
                        title[:500],
                        url[:512],
                        cleaned_content,
                        description[:500] if description else title[:500],
                        author[:200],
                        pub_date,
                        json.dumps([category, value_chain]),
                        value_chain,
                        0,  # RSS feeds don't have engagement metrics
                        relevance
                    ))
                    conn.commit()
                    collected += 1

                except mysql.connector.IntegrityError:
                    # Duplicate entry, skip
                    continue
                except Exception as e:
                    self.logger.error(f"  {source_name}: Error processing entry: {e}")
                    continue

            cursor.close()
            conn.close()

            self.logger.info(f"  {source_name}: Collected {collected} articles")
            return collected

        except Exception as e:
            self.logger.error(f"  {source_name}: Feed collection failed: {e}")
            return 0

    def collect_all(self):
        """Collect from all active RSS sources"""
        sources = self.get_rss_sources()
        if not sources:
            self.logger.info("No active RSS sources configured")
            return 0

        total_collected = 0
        self.logger.info(f"Collecting from {len(sources)} RSS sources...")

        for source in sources:
            collected = self.collect_from_feed(
                source['id'],
                source['source_name'],
                source['source_url'],
                source['category']
            )
            total_collected += collected

            # Rotate user agent
            self.current_ua_index = (self.current_ua_index + 1) % len(self.user_agents)

            # Rate limiting
            time.sleep(2)

        self.logger.info(f"✓ RSS collection complete: {total_collected} articles collected")
        return total_collected
