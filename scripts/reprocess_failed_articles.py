#!/usr/bin/env python3
"""
Reprocess Failed Articles Script

This script reprocesses articles that previously failed extraction.
It uses the enhanced ArticleExtractor with Google News redirect resolution,
retry logic, and BeautifulSoup fallback.

Usage:
    python reprocess_failed_articles.py [options]

Options:
    --limit N       Process N articles (default: 1000)
    --source NAME   Only process articles from specific source
    --days N        Only process articles from last N days (default: 7)
    --dry-run       Show what would be processed without doing it
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add parent directory to path to import content module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content.content_v2 import ArticleExtractor
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'rss_reader')
}


def get_failed_articles(limit=1000, source=None, days=7):
    """Get articles that failed extraction"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT fm.id, fm.url, fm.source, fm.published_at,
                   fa.error_type, fa.attempt_count
            FROM feed_metadata fm
            LEFT JOIN article_content ac ON fm.id = ac.url_id
            LEFT JOIN failed_articles fa ON fm.id = fa.article_id
            WHERE ac.url_id IS NULL
              AND fm.published_at > DATE_SUB(NOW(), INTERVAL %s DAY)
        """

        params = [days]

        if source:
            query += " AND fm.source = %s"
            params.append(source)

        query += " ORDER BY fm.published_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        articles = cursor.fetchall()

        cursor.close()
        conn.close()

        return articles

    except Exception as e:
        print(f"Error fetching failed articles: {e}")
        return []


def get_statistics():
    """Get current extraction statistics"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(fm.id) as total,
                COUNT(ac.id) as processed,
                COUNT(fm.id) - COUNT(ac.id) as unprocessed,
                ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
            FROM feed_metadata fm
            LEFT JOIN article_content ac ON fm.id = ac.url_id
        """)
        overall = cursor.fetchone()

        # Stats by source
        cursor.execute("""
            SELECT
                fm.source,
                COUNT(fm.id) as total,
                COUNT(ac.id) as processed,
                COUNT(fm.id) - COUNT(ac.id) as unprocessed,
                ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
            FROM feed_metadata fm
            LEFT JOIN article_content ac ON fm.id = ac.url_id
            GROUP BY fm.source
            HAVING unprocessed > 0
            ORDER BY unprocessed DESC
            LIMIT 10
        """)
        by_source = cursor.fetchall()

        cursor.close()
        conn.close()

        return {'overall': overall, 'by_source': by_source}

    except Exception as e:
        print(f"Error getting statistics: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Reprocess failed article extractions')
    parser.add_argument('--limit', type=int, default=1000, help='Number of articles to process')
    parser.add_argument('--source', type=str, help='Filter by specific source')
    parser.add_argument('--days', type=int, default=7, help='Only process articles from last N days')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without doing it')
    parser.add_argument('--stats-only', action='store_true', help='Show statistics only')

    args = parser.parse_args()

    print("=" * 80)
    print("REPROCESS FAILED ARTICLES")
    print("=" * 80)
    print()

    # Show current statistics
    print("📊 Current Statistics:")
    print("-" * 80)

    stats = get_statistics()
    if stats and stats['overall']:
        overall = stats['overall']
        print(f"Overall:")
        print(f"  Total Articles:      {overall['total']:,}")
        print(f"  Successfully Processed: {overall['processed']:,}")
        print(f"  Failed/Unprocessed:  {overall['unprocessed']:,}")
        print(f"  Success Rate:        {overall['success_rate']}%")
        print()

        if stats['by_source']:
            print(f"Top Sources with Failed Articles:")
            for source in stats['by_source']:
                print(f"  {source['source']:25} - Unprocessed: {source['unprocessed']:4} / {source['total']:4} ({source['success_rate']}% success)")

    print()

    if args.stats_only:
        return

    # Get failed articles
    print(f"🔍 Fetching failed articles...")
    print(f"   Filters: last {args.days} days", end='')
    if args.source:
        print(f", source={args.source}", end='')
    print(f", limit={args.limit}")
    print()

    failed_articles = get_failed_articles(
        limit=args.limit,
        source=args.source,
        days=args.days
    )

    if not failed_articles:
        print("✓ No failed articles found!")
        return

    print(f"Found {len(failed_articles)} articles to reprocess")
    print()

    if args.dry_run:
        print("DRY RUN - showing what would be processed:")
        print("-" * 80)
        for i, article in enumerate(failed_articles[:20], 1):
            error_info = f" (Previous error: {article['error_type']}, {article['attempt_count']} attempts)" if article['error_type'] else ""
            print(f"{i:3}. [{article['source']:20}] {article['url'][:60]}...{error_info}")

        if len(failed_articles) > 20:
            print(f"... and {len(failed_articles) - 20} more")

        print()
        print("Run without --dry-run to actually process these articles")
        return

    # Confirm before processing
    print("⚠️  About to reprocess articles with enhanced extraction methods:")
    print("   - Google News redirect resolution")
    print("   - Exponential backoff retry")
    print("   - BeautifulSoup fallback")
    print("   - Rate limiting per domain")
    print()

    confirm = input(f"Process {len(failed_articles)} articles? [y/N]: ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return

    # Process articles
    print()
    print("=" * 80)
    print("PROCESSING ARTICLES")
    print("=" * 80)
    print()

    extractor = ArticleExtractor()
    success_count = 0
    failed_count = 0
    start_time = datetime.now()

    for i, article in enumerate(failed_articles, 1):
        article_id = article['id']
        url = article['url']
        source = article['source']

        print(f"\n[{i}/{len(failed_articles)}] Processing: {source}")
        print(f"   URL: {url[:70]}...")

        # Extract with enhanced methods
        content, error = extractor.extract_article_content_with_retry(url)

        if content:
            if extractor.save_content(article_id, content):
                success_count += 1
                print(f"   ✓ Success! Extracted {len(content['full_text'])} characters")
            else:
                failed_count += 1
                print(f"   ✗ Failed to save content")
        else:
            failed_count += 1
            print(f"   ✗ Failed: {error}")
            extractor.track_failed_article(article_id, url, error or 'unknown', error or 'Extraction failed')

        # Progress update every 50 articles
        if i % 50 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(failed_articles) - i) / rate if rate > 0 else 0

            print(f"\n--- Progress: {i}/{len(failed_articles)} ({i/len(failed_articles)*100:.1f}%) ---")
            print(f"    Success: {success_count}, Failed: {failed_count}")
            print(f"    Rate: {rate:.1f} articles/sec, ETA: {eta/60:.1f} minutes")

    # Final statistics
    print()
    print("=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print()

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"Results:")
    print(f"  Total Processed:  {len(failed_articles)}")
    print(f"  ✓ Successful:     {success_count} ({success_count/len(failed_articles)*100:.1f}%)")
    print(f"  ✗ Failed:         {failed_count} ({failed_count/len(failed_articles)*100:.1f}%)")
    print(f"  Time Elapsed:     {elapsed/60:.1f} minutes")
    print(f"  Processing Rate:  {len(failed_articles)/elapsed:.1f} articles/sec")
    print()

    # Show updated statistics
    print("📊 Updated Statistics:")
    print("-" * 80)

    stats = get_statistics()
    if stats and stats['overall']:
        overall = stats['overall']
        print(f"  Total Articles:      {overall['total']:,}")
        print(f"  Successfully Processed: {overall['processed']:,}")
        print(f"  Failed/Unprocessed:  {overall['unprocessed']:,}")
        print(f"  Success Rate:        {overall['success_rate']}%")

    print()
    print("✓ Done!")


if __name__ == '__main__':
    main()
