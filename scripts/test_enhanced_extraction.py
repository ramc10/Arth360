#!/usr/bin/env python3
"""
Test Enhanced Article Extraction

Tests the new features:
1. Google News redirect resolution
2. Retry logic with exponential backoff
3. BeautifulSoup fallback
4. Rate limiting

Usage:
    python test_enhanced_extraction.py
"""

import sys
import os

# Add parent directory to path
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


def get_sample_google_news_urls(limit=10):
    """Get sample Google News URLs from database"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT fm.id, fm.url, fm.title, fm.source
            FROM feed_metadata fm
            LEFT JOIN article_content ac ON fm.id = ac.url_id
            WHERE fm.source LIKE 'google-%'
              AND ac.url_id IS NULL
            ORDER BY fm.published_at DESC
            LIMIT %s
        """, (limit,))

        urls = cursor.fetchall()
        cursor.close()
        conn.close()

        return urls

    except Exception as e:
        print(f"Error fetching URLs: {e}")
        return []


def test_redirect_resolution(extractor):
    """Test Google News redirect resolution"""
    print("=" * 80)
    print("TEST 1: Google News Redirect Resolution")
    print("=" * 80)
    print()

    test_urls = get_sample_google_news_urls(5)

    if not test_urls:
        print("No Google News URLs found in database")
        return

    print(f"Testing {len(test_urls)} Google News URLs...")
    print()

    success_count = 0
    for i, url_data in enumerate(test_urls, 1):
        url = url_data['url']
        print(f"{i}. Testing: {url[:80]}...")

        resolved = extractor.resolve_google_news_redirect(url)

        if resolved and resolved != url:
            print(f"   ✓ Resolved to: {resolved[:80]}...")
            success_count += 1
        else:
            print(f"   ✗ Failed to resolve")

        print()

    print(f"Results: {success_count}/{len(test_urls)} successfully resolved")
    print()


def test_full_extraction(extractor):
    """Test full extraction with retry and fallback"""
    print("=" * 80)
    print("TEST 2: Full Extraction (with retry & fallback)")
    print("=" * 80)
    print()

    test_urls = get_sample_google_news_urls(5)

    if not test_urls:
        print("No URLs found to test")
        return

    print(f"Testing full extraction on {len(test_urls)} articles...")
    print()

    success_count = 0
    for i, url_data in enumerate(test_urls, 1):
        url = url_data['url']
        title = url_data['title']

        print(f"{i}. Testing: {title[:60]}...")
        print(f"   URL: {url[:70]}...")

        content, error = extractor.extract_article_content_with_retry(url)

        if content:
            print(f"   ✓ Success!")
            print(f"     - Content length: {len(content['full_text'])} chars")
            print(f"     - Summary length: {len(content.get('summary', ''))} chars")
            print(f"     - Keywords: {len(content.get('keywords', []))}")
            print(f"     - Images: {len(content.get('images', []))}")
            success_count += 1
        else:
            print(f"   ✗ Failed: {error}")

        print()

    print(f"Results: {success_count}/{len(test_urls)} successfully extracted")
    print()


def test_rate_limiting(extractor):
    """Test rate limiting functionality"""
    print("=" * 80)
    print("TEST 3: Rate Limiting")
    print("=" * 80)
    print()

    import time

    test_domain = "https://www.example.com/article1"

    print("Testing rate limiting (should wait ~2 seconds between requests to same domain)...")

    start = time.time()
    extractor.rate_limited_request(test_domain)
    time1 = time.time() - start

    start = time.time()
    extractor.rate_limited_request(test_domain)
    time2 = time.time() - start

    print(f"  First request: {time1:.2f}s")
    print(f"  Second request: {time2:.2f}s (should be ~2s)")

    if time2 >= 1.9:
        print(f"  ✓ Rate limiting working correctly")
    else:
        print(f"  ✗ Rate limiting may not be working")

    print()


def test_statistics(extractor):
    """Test statistics reporting"""
    print("=" * 80)
    print("TEST 4: Statistics")
    print("=" * 80)
    print()

    stats = extractor.get_statistics()

    if stats and stats['overall']:
        overall = stats['overall']

        print("Overall Statistics:")
        print(f"  Total Articles:     {overall['total_articles']:,}")
        print(f"  Processed:          {overall['processed']:,}")
        print(f"  Unprocessed:        {overall['unprocessed']:,}")
        print(f"  Success Rate:       {overall['success_rate']}%")
        print()

        if stats['failures']:
            print("Failed Articles by Type:")
            for failure in stats['failures']:
                print(f"  {failure['error_type']:20} - {failure['count']:4} failures ({failure['retryable']} retryable)")

    print()


def main():
    print()
    print("=" * 80)
    print("ENHANCED ARTICLE EXTRACTOR - TEST SUITE")
    print("=" * 80)
    print()

    # Initialize extractor
    print("Initializing enhanced extractor...")
    extractor = ArticleExtractor()
    print("✓ Extractor initialized")
    print()

    # Run tests
    test_redirect_resolution(extractor)
    test_full_extraction(extractor)
    test_rate_limiting(extractor)
    test_statistics(extractor)

    print("=" * 80)
    print("ALL TESTS COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Review test results above")
    print("2. If tests pass, deploy enhanced content service:")
    print("   docker-compose down content")
    print("   # Backup current content.py")
    print("   cp content/content.py content/content_backup.py")
    print("   cp content/content_v2.py content/content.py")
    print("   docker-compose build content")
    print("   docker-compose up -d content")
    print()
    print("3. Reprocess failed articles:")
    print("   python scripts/reprocess_failed_articles.py --limit 100 --dry-run")
    print("   python scripts/reprocess_failed_articles.py --limit 1000")
    print()


if __name__ == '__main__':
    main()
