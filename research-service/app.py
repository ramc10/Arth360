import mysql.connector
import requests
import os
from datetime import datetime, timedelta
import json
import time
import sys
from dotenv import load_dotenv
from collections import defaultdict
from alpha_vantage_client import AlphaVantageClient

# Load environment variables
load_dotenv() 

print("=" * 60, flush=True)
print("RESEARCH SERVICE STARTING...", flush=True)
print("=" * 60, flush=True)
sys.stdout.flush()

class ResearchBriefGenerator:
    def __init__(self):
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME', 'rss_reader')
        }
        self.lmstudio_url = os.getenv('LMSTUDIO_URL', 'http://host.docker.internal:1234/v1/chat/completions')

        # Initialize Alpha Vantage client for stock data
        self.alpha_vantage = AlphaVantageClient()
    
    def get_db_connection(self):
        return mysql.connector.connect(**self.db_config)
    
    def summarize_with_llama(self, text, company_name):
        """Use local Llama to summarize article"""
        prompt = f"""Analyze this news article about {company_name}:

{text[:1500]}

Provide:
1. Key Points (2-3 bullets)
2. Financial Impact (if any mentioned)
3. Sentiment: Positive/Negative/Neutral

Be concise."""
        
        try:
            response = requests.post(self.lmstudio_url, json={
                "model": "llama-3.1-8b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 300
            }, timeout=30)
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"LLM Error: {str(e)}"
    
    def get_company_articles(self, company_symbol, hours=24):
        """Get recent articles mentioning company"""
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Using actual schema - url_id is FK, cleaned_text is content
        query = """
            SELECT fm.title, fm.url, fm.description, 
                   ac.cleaned_text, ac.summary, fm.published_at
            FROM feed_metadata fm
            LEFT JOIN article_content ac ON fm.id = ac.url_id
            WHERE (fm.title LIKE %s OR fm.description LIKE %s)
            AND fm.published_at > %s
            ORDER BY fm.published_at DESC
            LIMIT 10
        """
        
        search_term = f"%{company_symbol}%"
        cursor.execute(query, (search_term, search_term, cutoff_time))
        articles = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return articles
    
    def get_stock_data(self, symbol):
        """Get stock data from Alpha Vantage API"""
        print(f"Fetching stock data for {symbol}...")
        stock_data = self.alpha_vantage.get_stock_data(symbol)

        # Log result
        if 'error' in stock_data:
            print(f"  ✗ Error: {stock_data['error']}")
        elif stock_data.get('price'):
            print(f"  Current Price: ${stock_data['price']:.2f}")
            if stock_data.get('change_percent'):
                print(f"  Change: {stock_data['change_percent']:+.2f}%")

        return stock_data
    
    def generate_brief(self, user_id, company_symbol):
        """Generate complete research brief"""
        print(f"\n{'='*60}")
        print(f"Generating brief for {company_symbol}...")
        print(f"{'='*60}")
        
        # Get company name from watchlist
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT company_name FROM user_watchlist WHERE user_id=%s AND company_symbol=%s",
            (user_id, company_symbol)
        )
        result = cursor.fetchone()
        company_name = result['company_name'] if result else company_symbol
        
        # Get articles
        articles = self.get_company_articles(company_symbol, hours=24)
        print(f"Found {len(articles)} articles in last 24 hours")
        
        if len(articles) == 0:
            print(f"No recent articles found for {company_symbol}")
            cursor.close()
            conn.close()
            return None
        
        # Summarize top 5 articles
        summaries = []
        for idx, article in enumerate(articles[:5], 1):
            # Use cleaned_text if available, otherwise description
            text_to_analyze = article.get('cleaned_text') or article.get('description') or article.get('title')
            
            if text_to_analyze:
                print(f"  [{idx}] Analyzing: {article['title'][:60]}...")
                summary = self.summarize_with_llama(text_to_analyze, company_name)
                summaries.append({
                    'title': article['title'],
                    'ai_analysis': summary,
                    'link': article['url'],
                    'published_at': article['published_at'].isoformat() if article.get('published_at') else None,
                    'original_summary': article.get('summary')
                })
                time.sleep(1)  # Rate limit LLM calls
        
        # Get stock data
        print(f"Fetching stock data for {company_symbol}...")
        financial_data = self.get_stock_data(company_symbol)
        
        if financial_data.get('price'):
            print(f"  Current Price: ${financial_data['price']:.2f}")
            if financial_data.get('change_percent'):
                print(f"  Change: {financial_data['change_percent']:+.2f}%")
        
        # Save brief
        brief_data = {
            'news_summary': summaries,
            'financial_data': financial_data,
            'articles_analyzed': len(articles),
            'summaries_generated': len(summaries)
        }
        
        cursor.execute("""
            INSERT INTO research_briefs 
            (user_id, company_symbol, brief_date, news_summary, financial_data, articles_analyzed)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            news_summary = VALUES(news_summary),
            financial_data = VALUES(financial_data),
            articles_analyzed = VALUES(articles_analyzed),
            generated_at = CURRENT_TIMESTAMP
        """, (
            user_id,
            company_symbol,
            datetime.now().date(),
            json.dumps(summaries),
            json.dumps(financial_data),
            len(articles)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✓ Brief saved for {company_symbol}")
        print(f"  - {len(summaries)} articles analyzed")
        print(f"  - Financial data captured")
        
        return brief_data
    
def main():
    """Generate briefs for all users' watchlists"""
    print("\n" + "="*60, flush=True)
    print("RESEARCH BRIEF GENERATOR", flush=True)
    print("="*60 + "\n", flush=True)
    sys.stdout.flush()
    
    generator = ResearchBriefGenerator()
    
    # Test LMStudio connection first
    print("Testing LMStudio connection...", flush=True)
    sys.stdout.flush()
    
    try:
        lmstudio_test_url = os.getenv('LMSTUDIO_URL', 'http://host.docker.internal:1234/v1/chat/completions').replace('/v1/chat/completions', '/v1/models')
        response = requests.get(lmstudio_test_url, timeout=5)
        if response.status_code == 200:
            print("✓ LMStudio is running\n", flush=True)
        else:
            print("✗ LMStudio connection failed", flush=True)
            print("  Continuing anyway...\n", flush=True)
    except Exception as e:
        print(f"✗ Cannot connect to LMStudio: {e}", flush=True)
        print("  Continuing anyway...\n", flush=True)
    
    sys.stdout.flush()
    
    # Run in continuous loop
    while True:
        try:
            print(f"\n{'='*60}", flush=True)
            print(f"STARTING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
            print(f"{'='*60}\n", flush=True)
            sys.stdout.flush()
            
            # Get all users and their watchlists
            conn = generator.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT u.id as user_id, u.email, uw.company_symbol, uw.company_name
                FROM users u
                JOIN user_watchlist uw ON u.id = uw.user_id
                ORDER BY u.id, uw.company_symbol
            """)
            
            watchlist_items = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if not watchlist_items:
                print("No watchlist items found.\n", flush=True)
            else:
                print(f"Processing {len(watchlist_items)} watchlist items...\n", flush=True)
                sys.stdout.flush()
                
                success_count = 0
                error_count = 0
                
                for item in watchlist_items:
                    try:
                        result = generator.generate_brief(
                            item['user_id'], 
                            item['company_symbol']
                        )
                        if result:
                            success_count += 1
                        time.sleep(2)
                    except Exception as e:
                        error_count += 1
                        print(f"✗ Error: {item['company_symbol']}: {e}", flush=True)
                
                print(f"\n{'='*60}", flush=True)
                print(f"CYCLE COMPLETE", flush=True)
                print(f"{'='*60}", flush=True)
                print(f"✓ Success: {success_count}", flush=True)
                print(f"✗ Errors:  {error_count}", flush=True)
                print(f"Total:    {len(watchlist_items)}", flush=True)
            
            # Wait 1 hour before next cycle
            print(f"\nNext run in 1 hour at {(datetime.now() + timedelta(hours=1)).strftime('%H:%M:%S')}\n", flush=True)
            sys.stdout.flush()
            time.sleep(3600)  # 1 hour
            
        except KeyboardInterrupt:
            print("\n\nShutting down...", flush=True)
            break
        except Exception as e:
            print(f"\nFatal error: {e}", flush=True)
            print("Retrying in 5 minutes...\n", flush=True)
            sys.stdout.flush()
            time.sleep(300)

if __name__ == "__main__":
    main()