# Comprehensive Plan: Fix Google News RSS Feed Scraping Issues

## 🔍 Problem Analysis

### Current Issues Identified:

1. **Google News URLs are Redirects** ❌
   - RSS feeds contain `news.google.com/rss/articles/...` URLs
   - These are NOT direct article links - they're Google redirect/tracker URLs
   - newspaper3k fails to extract content from these proxy URLs
   - Example: `https://news.google.com/rss/articles/CBMi9AFBVV95cUxQ...` → redirects to actual article

2. **Content Extraction Statistics:**
   - **Total articles in database**: 17,398
   - **Successfully processed**: 8,497 (48.8%)
   - **Failed to extract**: 8,901 (51.2%) ❌

3. **Working Sources:**
   - ✅ Business Today: 2,626 articles
   - ✅ Mint: 5,435 articles (multiple feeds)
   - ✅ Moneycontrol: Some feeds working, some returning 503 errors
   - ❌ Google News: ~7,000+ articles with redirect URLs

4. **Specific Errors:**
   - Google News: Redirect URLs don't contain actual article content
   - Mint: 410 Gone errors (articles deleted/moved)
   - Moneycontrol: 503 Service Unavailable (rate limiting/blocking)

---

## 🎯 Solution Strategy

### **Phase 1: Fix Google News URL Resolution** (CRITICAL - 70% of the problem)

**Problem**: Google News RSS feeds return redirect URLs, not actual article URLs.

**Solution**: Implement URL resolution before content extraction.

#### Option 1A: Follow Redirects Automatically ✅ RECOMMENDED
```python
# Modify content.py to resolve Google News redirects
import requests
from urllib.parse import urlparse

def resolve_google_news_url(url):
    """Resolve Google News redirect to actual article URL"""
    if 'news.google.com' in url:
        try:
            # Follow redirects with proper headers
            response = requests.head(url, allow_redirects=True, timeout=10,
                                    headers={'User-Agent': 'Mozilla/5.0'})
            return response.url  # Returns final destination URL
        except:
            return url
    return url
```

**Pros:**
- Simple implementation
- Works for all Google News feeds
- No API keys needed
- Handles redirects automatically

**Cons:**
- Extra HTTP request per article
- May be rate-limited by Google

#### Option 1B: Use Google News RSS Parser Library ✅ ALTERNATIVE
```python
# Use GoogleNews library that handles redirects
pip install GoogleNews

from GoogleNews import GoogleNews
gn = GoogleNews()
# Has built-in redirect handling
```

**Pros:**
- Purpose-built for Google News
- Better handling of edge cases

**Cons:**
- Additional dependency
- May need maintenance if Google changes structure

#### Option 1C: Extract Original URL from RSS Entry ✅ BEST PERFORMANCE
```python
# Modify feeder.py to extract actual URL from RSS entry
# Google News RSS includes the real URL in the entry
def extract_actual_url_from_rss(entry):
    """Extract actual article URL from Google News RSS entry"""
    # Check if entry has 'link' that's the real URL
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('type') == 'text/html':
                return link.get('href')
    # Fallback: follow redirect
    return resolve_google_news_url(entry.link)
```

**Pros:**
- Most efficient - gets URL at RSS parsing time
- No extra HTTP requests
- Real URLs stored in database

**Cons:**
- Requires modifying feeder service
- RSS structure may vary

---

### **Phase 2: Add Intelligent Retry & Fallback Mechanisms**

#### 2A: Implement Exponential Backoff
```python
def extract_with_retry(url, max_retries=3):
    """Extract article with exponential backoff"""
    for attempt in range(max_retries):
        try:
            # Try newspaper3k
            article = Article(url)
            article.download()
            article.parse()
            return article
        except:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue
            # Final attempt: try alternative method
            return extract_with_beautifulsoup(url)
```

#### 2B: Add Alternative Scraping Methods
```python
# Fallback 1: BeautifulSoup
def extract_with_beautifulsoup(url):
    """Fallback extraction using BeautifulSoup"""
    response = requests.get(url, headers={...})
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract title, content, images
    title = soup.find('h1').get_text()
    paragraphs = soup.find_all('p')
    content = '\n'.join([p.get_text() for p in paragraphs])
    return {'title': title, 'text': content, ...}

# Fallback 2: Playwright (for JavaScript-heavy sites)
from playwright.sync_api import sync_playwright

def extract_with_playwright(url):
    """Extract from JavaScript-rendered pages"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        content = page.content()
        browser.close()
        return parse_html_content(content)
```

---

### **Phase 3: Handle Rate Limiting & Blocking**

#### 3A: Rotate User Agents
```python
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    # Add 10+ more
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)
```

#### 3B: Add Request Delays
```python
# Add delay between requests to same domain
from collections import defaultdict
from time import time

last_request_time = defaultdict(float)

def rate_limited_request(url):
    domain = urlparse(url).netloc
    time_since_last = time() - last_request_time[domain]

    if time_since_last < 2:  # 2 seconds between requests
        time.sleep(2 - time_since_last)

    last_request_time[domain] = time()
    return requests.get(url, ...)
```

#### 3C: Use Proxy Rotation (if needed)
```python
# For heavily rate-limited sites
PROXIES = [
    'http://proxy1.com:8080',
    'http://proxy2.com:8080',
]

def get_with_proxy(url):
    proxy = random.choice(PROXIES)
    return requests.get(url, proxies={'http': proxy, 'https': proxy})
```

---

### **Phase 4: Error Tracking & Recovery**

#### 4A: Track Failed Articles
```python
# Add new table: failed_articles
CREATE TABLE failed_articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT,
    url VARCHAR(512),
    error_type VARCHAR(100),
    error_message TEXT,
    attempt_count INT DEFAULT 1,
    last_attempt TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES feed_metadata(id)
);
```

#### 4B: Implement Smart Retry Logic
```python
def should_retry(error_type, attempt_count):
    """Determine if article should be retried"""
    # Don't retry 404s or 410s (Gone)
    if error_type in ['404', '410']:
        return False

    # Retry 503s up to 5 times
    if error_type == '503' and attempt_count < 5:
        return True

    # Retry timeouts up to 3 times
    if error_type == 'timeout' and attempt_count < 3:
        return True

    return False
```

---

### **Phase 5: Alternative Data Sources** (Long-term)

#### 5A: Add Direct RSS Feeds
Replace Google News with direct publisher feeds:

```json
{
  "feeds": [
    // Replace Google News - AAPL
    {"name": "Reuters Apple", "url": "https://www.reuters.com/companies/AAPL.O/rss"},
    {"name": "Bloomberg Apple", "url": "https://www.bloomberg.com/company/AAPL:US/rss"},

    // Replace Google News - Markets
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"name": "Reuters Markets", "url": "https://www.reuters.com/finance/markets/rss"},
    {"name": "Bloomberg Markets", "url": "https://www.bloomberg.com/markets/rss"},

    // Tech news
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica", "url": "http://feeds.arstechnica.com/arstechnica/index"}
  ]
}
```

#### 5B: Use News APIs
```python
# NewsAPI.org (free tier: 100 requests/day)
# Alternative to RSS scraping
import requests

def fetch_from_newsapi(company):
    """Fetch articles using NewsAPI"""
    api_key = os.getenv('NEWSAPI_KEY')
    url = f"https://newsapi.org/v2/everything?q={company}&apiKey={api_key}"
    response = requests.get(url)
    return response.json()['articles']

# Pros: Clean data, no scraping needed
# Cons: Rate limits, may cost money for high volume
```

#### 5C: Alpha Vantage News API
```python
# Alpha Vantage (free tier: 500 requests/day)
def fetch_from_alphavantage(symbol):
    """Fetch company news from Alpha Vantage"""
    api_key = os.getenv('ALPHAVANTAGE_KEY')
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&apiKey={api_key}"
    response = requests.get(url)
    return response.json()
```

---

## 🚀 Implementation Plan

### **Week 1: Quick Wins (Fix 80% of issues)**

#### Day 1: Fix Google News URL Resolution
- [ ] Implement redirect following in content.py
- [ ] Test with 100 Google News URLs
- [ ] Deploy and monitor

**Code Changes:**
```python
# content/content.py - Add before extract_article_content()

def resolve_final_url(self, url):
    """Resolve Google News redirects to actual article URLs"""
    if 'news.google.com' not in url:
        return url

    try:
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=10,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        final_url = response.url
        self.log(f"Resolved: {url[:50]}... -> {final_url[:50]}...")
        return final_url
    except Exception as e:
        self.log(f"Failed to resolve redirect: {str(e)}", 'error')
        return url

# Modify extract_article_content()
def extract_article_content(self, url):
    # Resolve redirects first
    final_url = self.resolve_final_url(url)

    try:
        article = Article(final_url)  # Use resolved URL
        # ... rest of the code
```

**Expected Impact:**
- Fix ~7,000 Google News articles (40% improvement)
- Success rate: 48% → 80%+

---

#### Day 2-3: Add Retry Logic & Error Handling
- [ ] Implement exponential backoff
- [ ] Add failed_articles tracking table
- [ ] Add BeautifulSoup fallback

**Code Changes:**
```python
# Add to content.py

def extract_with_retry(self, url, max_retries=3):
    """Extract article with intelligent retry"""
    final_url = self.resolve_final_url(url)

    for attempt in range(max_retries):
        try:
            # Try newspaper3k
            article = Article(final_url)
            article.download()
            article.parse()
            article.nlp()
            return self.format_article_data(article)

        except Exception as e:
            error_type = type(e).__name__
            self.log(f"Attempt {attempt+1} failed: {error_type}", 'error')

            if attempt == max_retries - 1:
                # Last attempt: try BeautifulSoup
                return self.extract_with_beautifulsoup(final_url)

            time.sleep(2 ** attempt)  # Exponential backoff

    return None
```

**Expected Impact:**
- Handle transient errors (timeouts, 503s)
- Success rate: 80% → 88%+

---

#### Day 4-5: Rate Limiting & User Agent Rotation
- [ ] Add request delay per domain
- [ ] Rotate user agents
- [ ] Monitor Moneycontrol success rate

**Code Changes:**
```python
# Add to content.py

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
    # Add more
]

from collections import defaultdict
from time import time

self.last_request = defaultdict(float)

def rate_limited_download(self, url):
    """Download with rate limiting per domain"""
    domain = urlparse(url).netloc
    elapsed = time() - self.last_request[domain]

    if elapsed < 2.0:
        time.sleep(2.0 - elapsed)

    article = Article(url)
    article.config.browser_user_agent = random.choice(USER_AGENTS)
    article.download()

    self.last_request[domain] = time()
    return article
```

**Expected Impact:**
- Fix Moneycontrol 503 errors
- Success rate: 88% → 92%+

---

### **Week 2: Advanced Improvements**

#### Day 6-7: Reprocess Failed Articles
- [ ] Create script to reprocess 8,901 failed articles
- [ ] Run in batches to avoid overload
- [ ] Track improvement metrics

**Script:**
```python
# scripts/reprocess_failed_articles.py

def reprocess_failed():
    """Reprocess articles that failed extraction"""
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get articles without content
    cursor.execute("""
        SELECT fm.id, fm.url, fm.source
        FROM feed_metadata fm
        LEFT JOIN article_content ac ON fm.id = ac.url_id
        WHERE ac.url_id IS NULL
        AND fm.published_at > DATE_SUB(NOW(), INTERVAL 7 DAYS)
        ORDER BY fm.published_at DESC
        LIMIT 1000
    """)

    failed_articles = cursor.fetchall()

    print(f"Reprocessing {len(failed_articles)} articles...")

    extractor = ArticleExtractor()
    success_count = 0

    for article in failed_articles:
        content = extractor.extract_with_retry(article['url'])
        if content and extractor.save_content(article['id'], content):
            success_count += 1

        time.sleep(1)  # Rate limit

    print(f"Successfully processed: {success_count}/{len(failed_articles)}")
```

**Expected Impact:**
- Recover ~6,000 previously failed articles
- Success rate: 92% → 95%+

---

#### Day 8-10: Add Alternative Data Sources
- [ ] Add 10-15 direct RSS feeds from major publishers
- [ ] Test NewsAPI integration
- [ ] Compare data quality

**Config Update:**
```json
// feeder/config.json - Add these feeds

{
  "feeds": [
    // Financial News - Direct feeds
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"name": "Reuters Business", "url": "https://www.reuters.com/business/rss"},
    {"name": "Bloomberg Markets", "url": "https://www.bloomberg.com/markets/rss"},
    {"name": "Financial Times", "url": "https://www.ft.com/rss/home"},

    // Tech News
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica", "url": "http://feeds.arstechnica.com/arstechnica/index"},
    {"name": "ZDNet", "url": "https://www.zdnet.com/news/rss.xml"},

    // India-specific
    {"name": "Economic Times Markets", "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
    {"name": "Hindu Business Line", "url": "https://www.thehindubusinessline.com/markets/?service=rss"},
    {"name": "NDTV Profit", "url": "https://www.ndtvprofit.com/rss/markets"}
  ]
}
```

**Expected Impact:**
- Higher quality articles
- Better geographic coverage
- More reliable sources

---

## 📊 Success Metrics

### Before Fix:
- ❌ Total articles: 17,398
- ❌ Processed: 8,497 (48.8%)
- ❌ Failed: 8,901 (51.2%)

### After Phase 1 (Week 1):
- ✅ Total articles: 17,398
- ✅ Processed: 16,000+ (92%+)
- ✅ Failed: 1,400 (8%)

### After Phase 2 (Week 2):
- ✅ Total articles: 25,000+ (new sources)
- ✅ Processed: 23,750+ (95%+)
- ✅ Failed: 1,250 (5%)

---

## 🛠️ Technical Implementation Details

### Files to Modify:

1. **content/content.py** (Primary changes)
   - Add `resolve_final_url()` method
   - Add `extract_with_retry()` method
   - Add `extract_with_beautifulsoup()` fallback
   - Add `rate_limited_download()` method
   - Add USER_AGENTS list

2. **feeder/feeder.py** (Optional optimization)
   - Extract actual URLs from Google News RSS entries
   - Store resolved URLs in database

3. **Database Schema** (New table)
   ```sql
   CREATE TABLE failed_articles (
       id INT AUTO_INCREMENT PRIMARY KEY,
       article_id INT,
       url VARCHAR(512),
       error_type VARCHAR(100),
       error_message TEXT,
       attempt_count INT DEFAULT 1,
       last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (article_id) REFERENCES feed_metadata(id),
       INDEX idx_article_id (article_id),
       INDEX idx_last_attempt (last_attempt)
   );
   ```

4. **feeder/config.json** (New feeds)
   - Add direct RSS feeds from publishers
   - Remove redundant Google News feeds (optional)

5. **New script: scripts/reprocess_failed_articles.py**
   - Batch reprocess failed articles
   - Track success metrics

---

## 🎯 Priority Recommendation

### **START HERE - Highest Impact (Do This First):**

1. ✅ **Fix Google News redirects** (1 day, 40% improvement)
   - Single method addition to content.py
   - Immediate impact on 7,000+ articles

2. ✅ **Add retry logic** (1 day, +8% improvement)
   - Handles transient errors
   - Simple exponential backoff

3. ✅ **Reprocess failed articles** (1 day, huge recovery)
   - Run once after fixes
   - Recover ~6,000 previously failed articles

### **Next Priority:**

4. Add rate limiting (1 day, fixes Moneycontrol 503s)
5. Add alternative sources (2 days, improves data quality)

---

## 📈 Expected Timeline

- **Day 1**: Fix Google News redirects → **80% success rate**
- **Day 2-3**: Add retry & error handling → **88% success rate**
- **Day 4-5**: Rate limiting & user agents → **92% success rate**
- **Day 6-7**: Reprocess failed articles → **95% success rate**
- **Day 8-10**: Add new sources → **Better data quality**

---

## 🔍 Monitoring & Validation

### Daily Checks:
```sql
-- Check extraction success rate
SELECT
    COUNT(fm.id) as total,
    COUNT(ac.id) as processed,
    ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
FROM feed_metadata fm
LEFT JOIN article_content ac ON fm.id = ac.url_id
WHERE fm.published_at > DATE_SUB(NOW(), INTERVAL 1 DAY);

-- Check by source
SELECT
    source,
    COUNT(fm.id) as total,
    COUNT(ac.id) as processed,
    ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
FROM feed_metadata fm
LEFT JOIN article_content ac ON fm.id = ac.url_id
WHERE fm.published_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
GROUP BY source
ORDER BY total DESC;
```

### Alert Thresholds:
- Success rate < 90% for 2 hours → Investigate
- Specific source < 70% → Check for blocking
- No articles processed for 30 minutes → Service down

---

## 💰 Cost Considerations

### Free Solutions (Recommended):
- ✅ Redirect following: $0
- ✅ Retry logic: $0
- ✅ User agent rotation: $0
- ✅ Direct RSS feeds: $0

### Paid Solutions (If Needed):
- NewsAPI: $449/month (100k requests)
- Alpha Vantage: $49/month (5k requests/day)
- ScrapingBee: $49/month (25k API calls)
- Proxy services: $50-200/month

**Recommendation**: Start with free solutions. They should achieve 95%+ success rate.

---

## ✅ Next Steps

**Immediate action items:**

1. Review this plan ✅
2. Decide on implementation approach
3. Implement Phase 1 Day 1 (Google News redirect fix)
4. Test with 100 articles
5. Deploy to production
6. Monitor for 24 hours
7. Proceed to Day 2

**Want me to start implementing?** I can:
- Write the code for Phase 1 Day 1 right now
- Create the complete updated content.py file
- Add the failed_articles tracking table
- Create the reprocessing script

Just say "implement phase 1" and I'll get started! 🚀
