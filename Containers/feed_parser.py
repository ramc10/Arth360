import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

def parse_feed(feed_url, source_name):
    """Parse RSS feed and return cleaned items"""
    print(f"Parsing feed from {source_name}...")
    
    items = []
    feed = feedparser.parse(feed_url)
    
    for entry in feed.entries:
        try:
            # Clean and standardize the published date
            published = entry.get('published', '')
            if not published:
                published = entry.get('pubDate', '')
            
            # Parse the date string into a datetime object
            published_parsed = entry.get('published_parsed', 
                                       entry.get('updated_parsed', 
                                               entry.get('pubDate_parsed', None)))
            if published_parsed:
                published_dt = datetime.fromtimestamp(time.mktime(published_parsed))
            else:
                published_dt = datetime.now()
            
            # Clean description - remove HTML tags
            description = entry.get('description', '')
            if description:
                description = BeautifulSoup(description, 'html.parser').get_text()
            
            # For Economic Times, sometimes the description is in content
            if not description and 'content' in entry:
                for content in entry.content:
                    if content.type == 'text/plain':
                        description = content.value
                        break
            
            item = {
                'title': entry.title,
                'description': description,
                'link': entry.link,
                'published': published_dt,
                'source': source_name
            }
            items.append(item)
        except Exception as e:
            print(f"Error processing entry: {e}")
            continue
    
    return items

def fetch_all_feeds(feed_configs):
    """Fetch and parse all configured feeds"""
    all_items = []
    for feed in feed_configs:
        try:
            items = parse_feed(feed['url'], feed['source'])
            all_items.extend(items)
        except Exception as e:
            print(f"Error fetching feed {feed['name']}: {e}")
            continue
    return all_items
