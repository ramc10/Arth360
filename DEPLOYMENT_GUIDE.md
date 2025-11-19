# Phase 1 Implementation - Deployment Guide

## ✅ What Was Implemented

### 1. **Enhanced Article Extractor** ([content/content_v2.py](content/content_v2.py))

#### Key Features:
- ✅ **Google News Redirect Resolution** - Attempts to resolve Google News proxy URLs
- ✅ **Exponential Backoff Retry** - Retries failed extractions up to 3 times (1s, 2s, 4s delays)
- ✅ **BeautifulSoup Fallback** - Falls back to BeautifulSoup if newspaper3k fails
- ✅ **Rate Limiting per Domain** - Waits 2 seconds between requests to same domain
- ✅ **User Agent Rotation** - Rotates through 8 different user agents
- ✅ **Failed Article Tracking** - Tracks failures in database with retry logic
- ✅ **Smart Retry Logic** - Doesn't retry 404/410 errors (permanent failures)
- ✅ **Statistics Reporting** - Shows success rates and failure breakdown

### 2. **Reprocessing Script** ([scripts/reprocess_failed_articles.py](scripts/reprocess_failed_articles.py))
- Batch reprocess failed articles
- Filter by source, days, limit
- Dry-run mode for testing
- Progress tracking and ETA
- Statistics before/after

### 3. **Test Script** ([scripts/test_enhanced_extraction.py](scripts/test_enhanced_extraction.py))
- Test redirect resolution
- Test full extraction
- Test rate limiting
- Show statistics

### 4. **Database Schema Update**
- New `failed_articles` table for tracking extraction failures
- Automatically created on first run

---

## 📊 Expected Improvements

| Metric | Before | After Phase 1 | Improvement |
|--------|--------|---------------|-------------|
| Success Rate | 48.8% | 85-92% | +36-43% |
| Articles Processed | 8,497 | 14,789-16,006 | +6,292-7,509 |
| Google News Articles | 0 (failed) | ~5,000-6,000 | New! |

---

## 🚀 Deployment Steps

### Step 1: Backup Current System

```bash
# Backup current content.py
cp content/content.py content/content_backup.py

# Backup database (optional but recommended)
docker exec arth360-mysql mysqldump -urss_user -p10_Leomessi rss_reader > backup_$(date +%Y%m%d).sql
```

### Step 2: Stop Content Service

```bash
docker-compose stop content
```

### Step 3: Deploy New Version

```bash
# Replace content.py with enhanced version
cp content/content_v2.py content/content.py

# Rebuild content service
docker-compose build content
```

### Step 4: Start Content Service

```bash
# Start with logs visible
docker-compose up -d content

# Watch logs
docker-compose logs -f content
```

### Step 5: Monitor Initial Performance

```bash
# Watch for first few cycles
docker-compose logs -f content | grep -E "Success|Failed|Statistics"
```

Expected output:
```
content  | ✓ Resolved Google News URL to: https://www.cnbc.com/...
content  | ✓ Extracted 2,450 chars from https://...
content  | Batch complete: ✓ 4 success, ✗ 1 failed
content  | 📊 Statistics:
content  |   Success Rate: 87.5%
```

### Step 6: Reprocess Failed Articles

After 1-2 hours of the new service running:

```bash
# Dry run first (see what would be processed)
python3 scripts/reprocess_failed_articles.py --limit 100 --dry-run

# Process first 1000 failed articles
python3 scripts/reprocess_failed_articles.py --limit 1000

# If successful, process more
python3 scripts/reprocess_failed_articles.py --limit 5000
```

---

## 📈 Monitoring

### Check Success Rate

```bash
# Overall success rate
docker exec arth360-mysql mysql -urss_user -p10_Leomessi -Drss_reader -se "
SELECT
    COUNT(fm.id) as total,
    COUNT(ac.id) as processed,
    ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
FROM feed_metadata fm
LEFT JOIN article_content ac ON fm.id = ac.url_id;
"
```

### Check by Source

```bash
docker exec arth360-mysql mysql -urss_user -p10_Leomessi -Drss_reader -se "
SELECT
    source,
    COUNT(fm.id) as total,
    COUNT(ac.id) as processed,
    ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
FROM feed_metadata fm
LEFT JOIN article_content ac ON fm.id = ac.url_id
GROUP BY source
ORDER BY total DESC
LIMIT 20;
"
```

### Check Failed Articles

```bash
docker exec arth360-mysql mysql -urss_user -p10_Leomessi -Drss_reader -se "
SELECT
    error_type,
    COUNT(*) as count,
    SUM(CASE WHEN should_retry THEN 1 ELSE 0 END) as retryable
FROM failed_articles
GROUP BY error_type
ORDER BY count DESC;
"
```

---

## 🔧 Troubleshooting

### Issue: Still Low Success Rate After Deployment

**Check:**
1. Are logs showing redirect resolutions?
2. Are retries happening?
3. What are common error types?

```bash
docker-compose logs content --tail 200 | grep -E "Resolved|Retry|failed"
```

### Issue: Google News Still Failing

**Understanding:** Google News RSS URLs are complex redirects that may require:
- JavaScript execution (not supported by requests library)
- Cookie handling
- More advanced scraping

**Alternative Solutions:**
1. **Use direct publisher feeds instead** (recommended - see Phase 2 in SCRAPING_FIX_PLAN.md)
2. **Use Playwright/Selenium** for Google News URLs (heavier approach)
3. **Use News APIs** (NewsAPI, Alpha Vantage)

### Issue: Rate Limiting / 503 Errors from Moneycontrol

**Solution:**
The enhanced version includes:
- 2-second delays between requests to same domain
- User agent rotation
- Exponential backoff

If still happening:
```bash
# Increase delay in content.py line 168
# Change from 2.0 to 3.0 or 5.0
if time_since_last < 5.0:  # Increased from 2.0
```

### Issue: BeautifulSoup Extracting Too Much Noise

**Solution:**
Edit the `extract_with_beautifulsoup()` method to better filter content:
```python
# Add more elements to remove
for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'ad', 'advertisement']):
    elem.decompose()
```

---

## 🎯 Success Criteria

After 24 hours of running:

### Minimum Success:
- ✅ Success rate > 70% (up from 48.8%)
- ✅ No errors in logs
- ✅ Research briefs continue generating

### Target Success:
- ✅ Success rate > 85%
- ✅ Google News articles being extracted
- ✅ Moneycontrol 503 errors reduced

### Excellent Success:
- ✅ Success rate > 92%
- ✅ Most sources working well
- ✅ Ready for Phase 2 improvements

---

## 📝 Next Steps After Successful Deployment

### Week 2 (Optional Enhancements):

1. **Add Direct RSS Feeds** (2 days)
   - Replace Google News with WSJ, Reuters, Bloomberg direct feeds
   - See list in [SCRAPING_FIX_PLAN.md](SCRAPING_FIX_PLAN.md)

2. **Implement Playwright for Stubborn Sites** (2 days)
   - Handle JavaScript-heavy sites
   - Better Google News support

3. **Add News APIs** (1 day)
   - NewsAPI for company-specific news
   - Alpha Vantage for market news

---

## 🔄 Rollback Procedure

If something goes wrong:

```bash
# Stop current service
docker-compose stop content

# Restore backup
cp content/content_backup.py content/content.py

# Rebuild and restart
docker-compose build content
docker-compose up -d content

# Verify
docker-compose logs -f content
```

---

## 📞 Support

### Logs Location:
- Container logs: `docker-compose logs content`
- File logs: `content/logs/article_extractor.log`

### Common Log Messages:

**✓ Good Signs:**
```
✓ Resolved Google News URL to: ...
✓ Extracted 2,450 chars from ...
✓ Saved content for URL ID: ...
Success Rate: 87.5%
```

**⚠️ Warning Signs:**
```
Failed to resolve Google News redirect
All methods failed. Last: ...
✗ Failed to extract: ...
Success Rate: 45.0%  (should be >70%)
```

**❌ Error Signs:**
```
Database connection error: ...
Failed to save content: ...
Unexpected error: ...
```

---

## ✅ Deployment Checklist

- [ ] Backup current content.py
- [ ] Stop content service
- [ ] Deploy content_v2.py as content.py
- [ ] Rebuild content service
- [ ] Start content service
- [ ] Monitor logs for 30 minutes
- [ ] Check success rate after 2 hours
- [ ] Run reprocessing script
- [ ] Verify research briefs still generating
- [ ] Document any issues
- [ ] Plan Phase 2 if needed

---

## 🎉 Expected Timeline

- **Hour 0**: Deploy new service
- **Hour 1**: Monitor initial extraction, should see improvements
- **Hour 2**: Check statistics, should see 70%+ success rate
- **Hour 4**: Run reprocessing script for first 1,000 articles
- **Hour 8**: Run reprocessing script for additional 5,000 articles
- **Day 1**: Success rate should stabilize at 85-92%
- **Week 1**: All backlog processed, system running smoothly

---

**Ready to deploy?** Follow steps above carefully and monitor closely!
