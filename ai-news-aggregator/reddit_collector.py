import praw
import mysql.connector
from datetime import datetime, timedelta
import logging
import os
import json


class RedditCollector:
    """Collects AI-related posts from Reddit subreddits"""

    def __init__(self, db_config, logger=None):
        self.db_config = db_config
        self.logger = logger or logging.getLogger(__name__)

        # Initialize Reddit API client
        self.reddit = self._init_reddit_client()

    def _init_reddit_client(self):
        """Initialize PRAW Reddit client"""
        try:
            reddit = praw.Reddit(
                client_id=os.getenv('REDDIT_CLIENT_ID'),
                client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
                user_agent=os.getenv('REDDIT_USER_AGENT', 'AI Newsletter Aggregator v1.0')
            )
            self.logger.info("✓ Reddit API client initialized")
            return reddit
        except Exception as e:
            self.logger.error(f"✗ Failed to initialize Reddit client: {e}")
            return None

    def get_db_connection(self):
        """Create database connection"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return None

    def get_reddit_sources(self):
        """Fetch active Reddit sources from database"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, source_name, source_url, category
                FROM ai_news_sources
                WHERE source_type = 'reddit' AND active = TRUE
            """)
            sources = cursor.fetchall()
            cursor.close()
            return sources
        except Exception as e:
            self.logger.error(f"Failed to fetch Reddit sources: {e}")
            return []
        finally:
            if conn.is_connected():
                conn.close()

    def extract_subreddit_name(self, url):
        """Extract subreddit name from URL"""
        # https://reddit.com/r/MachineLearning -> MachineLearning
        parts = url.rstrip('/').split('/')
        if 'r' in parts:
            idx = parts.index('r')
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return None

    def categorize_by_content(self, title, selftext):
        """Categorize post based on content keywords"""
        text = (title + ' ' + selftext).lower()

        # Value chain categorization
        if any(word in text for word in ['gpu', 'chip', 'nvidia', 'amd', 'tpu', 'hardware', 'semiconductor', 'compute']):
            return 'chips'
        elif any(word in text for word in ['model', 'llm', 'gpt', 'claude', 'gemini', 'training', 'research', 'paper', 'arxiv']):
            return 'models'
        elif any(word in text for word in ['regulation', 'policy', 'law', 'governance', 'ethics', 'safety', 'alignment', 'government']):
            return 'policy'
        elif any(word in text for word in ['funding', 'investment', 'startup', 'acquisition', 'market', 'revenue', 'valuation', 'ipo']):
            return 'business'
        elif any(word in text for word in ['app', 'product', 'tool', 'consumer', 'user', 'interface', 'chatbot', 'assistant']):
            return 'applications'
        else:
            return 'general'

    def calculate_engagement_score(self, post):
        """Calculate engagement score from Reddit metrics"""
        # Score = upvotes + (comments * 2) + (upvote_ratio * 100)
        score = post.score + (post.num_comments * 2) + (post.upvote_ratio * 100)
        return max(0, score)  # Ensure non-negative

    def collect_from_subreddit(self, source_id, subreddit_name, category, hours=48):
        """Collect posts from a subreddit"""
        if not self.reddit:
            self.logger.warning("Reddit client not available, skipping...")
            return 0

        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            cutoff_time = datetime.now() - timedelta(hours=hours)

            collected = 0
            conn = self.get_db_connection()
            if not conn:
                return 0

            cursor = conn.cursor()

            # Fetch top posts from the last 48 hours
            for post in subreddit.hot(limit=50):  # Check top 50 hot posts
                post_time = datetime.fromtimestamp(post.created_utc)

                # Skip if too old
                if post_time < cutoff_time:
                    continue

                # Skip if already collected
                cursor.execute("SELECT id FROM ai_news_articles WHERE url = %s", (post.url,))
                if cursor.fetchone():
                    continue

                # Determine value chain area
                value_chain = self.categorize_by_content(post.title, post.selftext)

                # Calculate scores
                engagement = self.calculate_engagement_score(post)

                # Extract content
                content = post.selftext if post.selftext else post.title

                try:
                    cursor.execute("""
                        INSERT INTO ai_news_articles
                        (source_id, title, url, content, summary, author, published_at,
                         topic_tags, value_chain_area, engagement_score, relevance_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        source_id,
                        post.title[:500],
                        post.url[:512],
                        content[:10000],  # Limit content size
                        post.title[:500],  # Use title as summary initially
                        str(post.author) if post.author else 'unknown',
                        post_time,
                        json.dumps([subreddit_name.lower()]),
                        value_chain,
                        engagement,
                        0  # Relevance score will be calculated later
                    ))
                    conn.commit()
                    collected += 1
                except mysql.connector.IntegrityError:
                    # Duplicate entry, skip
                    continue
                except Exception as e:
                    self.logger.error(f"Error inserting article from r/{subreddit_name}: {e}")
                    continue

            cursor.close()
            conn.close()

            self.logger.info(f"  r/{subreddit_name}: Collected {collected} posts")
            return collected

        except Exception as e:
            self.logger.error(f"Error collecting from r/{subreddit_name}: {e}")
            return 0

    def collect_all(self):
        """Collect from all active Reddit sources"""
        sources = self.get_reddit_sources()
        if not sources:
            self.logger.info("No active Reddit sources configured")
            return 0

        total_collected = 0
        self.logger.info(f"Collecting from {len(sources)} Reddit sources...")

        for source in sources:
            subreddit_name = self.extract_subreddit_name(source['source_url'])
            if not subreddit_name:
                self.logger.warning(f"Could not extract subreddit from {source['source_url']}")
                continue

            collected = self.collect_from_subreddit(
                source['id'],
                subreddit_name,
                source['category']
            )
            total_collected += collected

        self.logger.info(f"✓ Reddit collection complete: {total_collected} posts collected")
        return total_collected
