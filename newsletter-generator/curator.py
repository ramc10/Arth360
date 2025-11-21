import mysql.connector
from datetime import datetime, timedelta
import logging
from collections import defaultdict


class ArticleCurator:
    """Curates articles for newsletter sections"""

    def __init__(self, db_config, logger=None):
        self.db_config = db_config
        self.logger = logger or logging.getLogger(__name__)

        # Value chain areas we need to cover
        self.value_chain_areas = ['chips', 'models', 'applications', 'policy', 'business']

    def get_db_connection(self):
        """Create database connection"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return None

    def get_recent_articles(self, hours=96):
        """
        Fetch recent articles from database
        Default: 96 hours (4 days) for Mon/Thu schedule
        """
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cutoff = datetime.now() - timedelta(hours=hours)

            query = """
                SELECT
                    a.id,
                    a.title,
                    a.url,
                    a.content,
                    a.summary,
                    a.author,
                    a.published_at,
                    a.collected_at,
                    a.topic_tags,
                    a.value_chain_area,
                    a.engagement_score,
                    a.relevance_score,
                    s.source_name,
                    s.category
                FROM ai_news_articles a
                JOIN ai_news_sources s ON a.source_id = s.id
                WHERE a.published_at > %s
                    AND a.content IS NOT NULL
                    AND LENGTH(a.content) > 100
                ORDER BY a.published_at DESC
            """

            cursor.execute(query, (cutoff,))
            articles = cursor.fetchall()
            cursor.close()

            self.logger.info(f"Fetched {len(articles)} articles from last {hours} hours")
            return articles

        except Exception as e:
            self.logger.error(f"Failed to fetch articles: {e}")
            return []
        finally:
            if conn.is_connected():
                conn.close()

    def calculate_composite_score(self, article):
        """
        Calculate composite score for article ranking
        Factors: relevance, recency, engagement, source quality
        """
        score = 0

        # Relevance score (0-100)
        score += article.get('relevance_score', 0)

        # Engagement score (normalized)
        engagement = article.get('engagement_score', 0)
        if engagement > 0:
            score += min(engagement / 10, 50)  # Cap at 50 points

        # Recency bonus (newer = better)
        if article.get('published_at'):
            age_hours = (datetime.now() - article['published_at']).total_seconds() / 3600
            if age_hours < 24:
                score += 30
            elif age_hours < 48:
                score += 20
            elif age_hours < 72:
                score += 10

        # Source quality (research papers, major outlets)
        source = article.get('source_name', '').lower()
        if 'arxiv' in source or 'research' in source:
            score += 15
        elif any(outlet in source for outlet in ['techcrunch', 'verge', 'mit']):
            score += 10

        return score

    def group_by_value_chain(self, articles):
        """Group articles by value chain area"""
        grouped = defaultdict(list)

        for article in articles:
            area = article.get('value_chain_area', 'general')
            grouped[area].append(article)

        return grouped

    def select_top_articles(self, articles, per_category=5):
        """
        Select top articles for each value chain category
        Ensures diversity and quality
        """
        # Calculate scores for all articles
        for article in articles:
            article['composite_score'] = self.calculate_composite_score(article)

        # Group by value chain
        grouped = self.group_by_value_chain(articles)

        # Select top N from each category
        selected = {}

        for area in self.value_chain_areas:
            area_articles = grouped.get(area, [])

            if not area_articles:
                self.logger.warning(f"No articles found for {area}")
                selected[area] = []
                continue

            # Sort by composite score
            area_articles.sort(key=lambda x: x['composite_score'], reverse=True)

            # Take top N
            top_articles = area_articles[:per_category]
            selected[area] = top_articles

            self.logger.info(
                f"  {area}: Selected {len(top_articles)} articles "
                f"(from {len(area_articles)} available)"
            )

        return selected

    def ensure_coverage(self, selected, min_articles=3):
        """
        Ensure each category has minimum articles
        If a category is short, pull from 'general' or other categories
        """
        # Count general articles
        general_pool = selected.get('general', [])
        self.logger.info(f"General pool has {len(general_pool)} articles")

        for area in self.value_chain_areas:
            if len(selected.get(area, [])) < min_articles:
                shortage = min_articles - len(selected.get(area, []))
                self.logger.warning(
                    f"{area} needs {shortage} more articles, pulling from general pool"
                )

                # Try to categorize general articles for this area
                if general_pool:
                    for article in general_pool[:shortage]:
                        selected[area].append(article)

        return selected

    def deduplicate_articles(self, articles):
        """Remove duplicate articles based on URL or very similar titles"""
        seen_urls = set()
        seen_titles = set()
        unique = []

        for article in articles:
            url = article.get('url', '')
            title = article.get('title', '').lower()

            # Normalize title for comparison
            title_words = set(title.split())

            is_duplicate = False

            # Check URL
            if url in seen_urls:
                is_duplicate = True

            # Check title similarity (if >80% words match, consider duplicate)
            for seen_title in seen_titles:
                seen_words = set(seen_title.split())
                if len(title_words) > 0 and len(seen_words) > 0:
                    overlap = len(title_words & seen_words)
                    similarity = overlap / max(len(title_words), len(seen_words))
                    if similarity > 0.8:
                        is_duplicate = True
                        break

            if not is_duplicate:
                seen_urls.add(url)
                seen_titles.add(title)
                unique.append(article)

        if len(unique) < len(articles):
            self.logger.info(f"Removed {len(articles) - len(unique)} duplicate articles")

        return unique

    def curate_for_newsletter(self, lookback_hours=96, articles_per_section=5):
        """
        Main curation method: fetch, score, select, and organize articles
        """
        self.logger.info("=" * 60)
        self.logger.info("CURATING ARTICLES FOR NEWSLETTER")
        self.logger.info("=" * 60)

        # Fetch recent articles
        all_articles = self.get_recent_articles(hours=lookback_hours)

        if not all_articles:
            self.logger.error("No articles found for curation!")
            return None

        # Deduplicate
        all_articles = self.deduplicate_articles(all_articles)
        self.logger.info(f"After deduplication: {len(all_articles)} articles")

        # Select top articles by category
        selected = self.select_top_articles(all_articles, per_category=articles_per_section)

        # Ensure coverage
        selected = self.ensure_coverage(selected, min_articles=3)

        # Calculate total
        total_selected = sum(len(articles) for articles in selected.values())

        self.logger.info("=" * 60)
        self.logger.info(f"CURATION COMPLETE: {total_selected} articles selected")
        self.logger.info("=" * 60)

        return selected
