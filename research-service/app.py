import mysql.connector
import requests
import os
from datetime import datetime, timedelta
import json
import time

class ResearchBriefGenerator:
    def __init__(self):
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME', 'rss_reader')
        }
        self.lmstudio_url = "http://host.docker.internal:1234/v1/chat/completions"
    
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
        """Get basic stock data from yfinance"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                open_price = hist['Open'].iloc[-1]
                change_pct = ((current_price / open_price) - 1) * 100
                volume = hist['Volume'].iloc[-1]
            else:
                current_price = None
                change_pct = None
                volume = None
            
            return {
                'symbol': symbol,
                'price': float(current_price) if current_price else None,
                'change_percent': float(change_pct) if change_pct else None,
                'volume': int(volume) if volume else None,
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow')
            }
        except Exception as e:
            print(f"Stock data error for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e)
            }
    
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
    print("\n" + "="*60)
    print("RESEARCH BRIEF GENERATOR")
    print("="*60 + "\n")
    
    generator = ResearchBriefGenerator()
    
    # Test LMStudio connection first
    print("Testing LMStudio connection...")
    try:
        response = requests.get("http://host.docker.internal:1234/v1/models", timeout=5)
        if response.status_code == 200:
            print("✓ LMStudio is running")
        else:
            print("✗ LMStudio connection failed")
            return
    except Exception as e:
        print(f"✗ Cannot connect to LMStudio: {e}")
        print("  Make sure LMStudio is running on port 1234")
        return
    
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
        print("No watchlist items found. Add some companies first!")
        return
    
    print(f"\nProcessing {len(watchlist_items)} watchlist items...\n")
    
    success_count = 0
    error_count = 0
    
    for item in watchlist_items:
        try:
            result = generator.generate_brief(item['user_id'], item['company_symbol'])
            if result:
                success_count += 1
            time.sleep(2)  # Rate limit between companies
        except Exception as e:
            error_count += 1
            print(f"✗ Error generating brief for {item['company_symbol']}: {e}")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"✓ Success: {success_count}")
    print(f"✗ Errors:  {error_count}")
    print(f"Total:    {len(watchlist_items)}")
    print()

if __name__ == "__main__":
    main()