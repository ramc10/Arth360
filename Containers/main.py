import time
import schedule
from config import FEED_URLS, EXTRACTION_INTERVAL
from database import DatabaseManager
from feed_parser import fetch_all_feeds

def job():
    print("\nRunning news feed extraction job...")
    db = DatabaseManager()
    
    try:
        # Fetch and parse all feeds
        news_items = fetch_all_feeds(FEED_URLS)
        print(f"Fetched {len(news_items)} news items")
        
        # Store in database
        for item in news_items:
            db.insert_news_item(item)
            
    except Exception as e:
        print(f"Error in extraction job: {e}")
    finally:
        db.close()

def main():
    print("Starting News Feed Extractor Service")
    print(f"Will run every {EXTRACTION_INTERVAL} minutes")
    
    # Schedule the job to run immediately and then at intervals
    schedule.every(EXTRACTION_INTERVAL).minutes.do(job)
    
    # Run immediately
    job()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
