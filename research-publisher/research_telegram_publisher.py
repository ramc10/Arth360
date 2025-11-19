import os
import requests
import mysql.connector
from datetime import datetime, timedelta
import logging
import json
from dotenv import load_dotenv
import time
import html
from logging.handlers import TimedRotatingFileHandler

# Load environment variables from base directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

class ResearchBriefPublisher:
    def __init__(self):
        self.setup_logger()
        self.load_config()
        self.validate_credentials()
        self.create_published_table()

    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('ResearchBriefPublisher')
        self.logger.setLevel(logging.INFO)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # File handler for log rotation
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'research_publisher.log'),
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)

        # Console handler for screen output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(console_handler)

    def log(self, message, level='info'):
        """Log messages"""
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)

    def load_config(self):
        """Load configuration from environment variables"""
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        self.db_config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME')
        }

    def validate_credentials(self):
        """Validate Telegram credentials"""
        if not self.telegram_token or not self.channel_id:
            self.logger.error("Missing Telegram configuration in .env file")
            raise ValueError("Telegram credentials not configured")

    def create_published_table(self):
        """Ensure research_briefs_published table exists"""
        conn = self.get_db_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS research_briefs_published (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        brief_id INT NOT NULL,
                        published_at DATETIME NOT NULL,
                        FOREIGN KEY (brief_id) REFERENCES research_briefs(id),
                        UNIQUE KEY unique_brief (brief_id)
                    )
                """)
                self.logger.info("Created/verified research_briefs_published table")
                conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error creating tables: {str(e)}")
            return False
        finally:
            if conn.is_connected():
                conn.close()

    def get_db_connection(self):
        """Create and return database connection"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            self.logger.error(f"Database connection failed: {str(e)}")
            return None

    def get_unpublished_briefs(self, limit=5):
        """Fetch research briefs that haven't been published yet"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            with conn.cursor(dictionary=True) as cursor:
                query = """
                SELECT
                    rb.id, rb.user_id, rb.company_symbol, rb.brief_date,
                    rb.news_summary, rb.financial_data, rb.articles_analyzed,
                    rb.generated_at, uw.company_name
                FROM research_briefs rb
                JOIN user_watchlist uw ON rb.user_id = uw.user_id
                    AND rb.company_symbol = uw.company_symbol
                LEFT JOIN research_briefs_published rbp ON rb.id = rbp.brief_id
                WHERE rbp.brief_id IS NULL
                    AND rb.articles_analyzed > 0
                ORDER BY rb.generated_at DESC
                LIMIT %s
                """
                cursor.execute(query, (limit,))
                results = cursor.fetchall()

                # Parse JSON fields
                for result in results:
                    if result['news_summary']:
                        result['news_summary'] = json.loads(result['news_summary'])
                    if result['financial_data']:
                        result['financial_data'] = json.loads(result['financial_data'])

                return results
        except Exception as e:
            self.logger.error(f"Database query failed: {str(e)}")
            return []
        finally:
            if conn.is_connected():
                conn.close()

    def format_stock_data(self, financial_data):
        """Format stock data section"""
        if not financial_data or 'error' in financial_data:
            return "📊 <i>Stock data unavailable</i>"

        lines = ["📊 <b>Market Data</b>"]

        if financial_data.get('price'):
            price = financial_data['price']
            change = financial_data.get('change_percent', 0)
            change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            lines.append(f"   Price: ${price:.2f} {change_emoji} {change:+.2f}%")

        if financial_data.get('market_cap'):
            market_cap = financial_data['market_cap']
            if market_cap > 1e12:
                lines.append(f"   Market Cap: ${market_cap/1e12:.2f}T")
            elif market_cap > 1e9:
                lines.append(f"   Market Cap: ${market_cap/1e9:.2f}B")

        if financial_data.get('pe_ratio'):
            lines.append(f"   P/E Ratio: {financial_data['pe_ratio']:.2f}")

        if financial_data.get('fifty_two_week_high') and financial_data.get('fifty_two_week_low'):
            high = financial_data['fifty_two_week_high']
            low = financial_data['fifty_two_week_low']
            lines.append(f"   52W Range: ${low:.2f} - ${high:.2f}")

        return "\n".join(lines)

    def extract_sentiment(self, ai_analysis):
        """Extract sentiment from AI analysis"""
        if not ai_analysis:
            return "Neutral", "⚪"

        analysis_lower = ai_analysis.lower()
        if 'sentiment: positive' in analysis_lower or 'bullish' in analysis_lower:
            return "Positive", "🟢"
        elif 'sentiment: negative' in analysis_lower or 'bearish' in analysis_lower:
            return "Negative", "🔴"
        else:
            return "Neutral", "⚪"

    def format_news_summary(self, news_summary):
        """Format news articles section with full AI analysis"""
        if not news_summary:
            return ""

        lines = ["📰 <b>Recent News & Analysis</b>"]

        for idx, article in enumerate(news_summary[:3], 1):  # Top 3 articles
            title = html.escape(article.get('title', 'Untitled')[:100])
            ai_analysis = article.get('ai_analysis', '')
            sentiment, emoji = self.extract_sentiment(ai_analysis)

            lines.append(f"\n{emoji} <b>{idx}. {title}</b>")

            # Format full AI analysis
            if ai_analysis:
                # Clean up the analysis text
                analysis_text = ai_analysis.strip()

                # Remove redundant headers
                analysis_text = analysis_text.replace('Key Points:', '').replace('key points:', '')
                analysis_text = analysis_text.replace('Financial Impact:', '\n💰 Financial Impact:')
                analysis_text = analysis_text.replace('financial impact:', '\n💰 Financial Impact:')

                # Split into lines and format
                analysis_lines = [l.strip() for l in analysis_text.split('\n') if l.strip()]

                formatted_lines = []
                for line in analysis_lines:
                    # Skip sentiment line (already shown as emoji)
                    if 'sentiment:' in line.lower():
                        continue

                    # Format bullet points
                    if line.startswith('•') or line.startswith('-'):
                        formatted_lines.append(f"   {line}")
                    elif line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                        formatted_lines.append(f"   • {line[2:].strip()}")
                    elif '💰' in line or 'Financial Impact' in line:
                        formatted_lines.append(f"\n{line}")
                    else:
                        # Regular text lines
                        if len(line) > 10:  # Filter out very short lines
                            formatted_lines.append(f"   {line}")

                # Add all formatted lines
                for line in formatted_lines:
                    lines.append(html.escape(line))

        return "\n".join(lines)

    def format_brief_message(self, brief):
        """Format the research brief for Telegram"""
        company_name = html.escape(brief.get('company_name', brief['company_symbol']))
        symbol = html.escape(brief['company_symbol'])
        date_str = brief['brief_date'].strftime('%B %d, %Y') if brief.get('brief_date') else datetime.now().strftime('%B %d, %Y')
        articles_count = brief.get('articles_analyzed', 0)

        # Header
        message = (
            f"🔍 <b>Research Brief: {company_name} ({symbol})</b>\n"
            f"📅 {date_str}\n"
            f"📊 {articles_count} articles analyzed\n\n"
        )

        # Stock data
        if brief.get('financial_data'):
            message += self.format_stock_data(brief['financial_data']) + "\n\n"

        # News summary
        if brief.get('news_summary'):
            message += self.format_news_summary(brief['news_summary']) + "\n\n"

        # Footer
        message += "━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"Generated by Arth360 Research\n"
        message += f"⏰ {datetime.now().strftime('%I:%M %p')}"

        # Truncate if too long (Telegram has 4096 char limit)
        if len(message) > 4000:
            message = message[:3997] + "..."

        return message

    def send_to_telegram(self, brief):
        """Send research brief to Telegram channel"""
        message = self.format_brief_message(brief)

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={
                    'chat_id': self.channel_id,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True,
                    'disable_notification': False
                },
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Failed to send message to Telegram: {str(e)}")
            return False

    def mark_as_published(self, brief_id):
        """Mark research brief as published in database"""
        conn = self.get_db_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO research_briefs_published (brief_id, published_at)
                    VALUES (%s, %s)
                """, (brief_id, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to mark as published: {str(e)}")
            conn.rollback()
            return False
        finally:
            if conn.is_connected():
                conn.close()

    def process_briefs(self):
        """Process and publish research briefs"""
        briefs = self.get_unpublished_briefs()
        if not briefs:
            self.logger.info("No new research briefs to publish")
            return 0

        success_count = 0
        for brief in briefs:
            brief_id = brief['id']
            company = brief['company_symbol']

            self.logger.info(f"Publishing brief for {company}...")

            if self.send_to_telegram(brief):
                if self.mark_as_published(brief_id):
                    success_count += 1
                    self.logger.info(f"✓ Published research brief for {company}")
                    time.sleep(5)  # Respect Telegram rate limits (more delay for longer messages)
                else:
                    self.logger.warning(f"✗ Failed to mark as published: {brief_id}")
            else:
                self.logger.error(f"✗ Failed to publish brief: {company}")

        return success_count

    def run(self, interval=3600):
        """Run the publisher continuously (default: every hour)"""
        self.logger.info("Starting Research Brief Publisher service")
        self.logger.info(f"Publishing interval: {interval} seconds ({interval/60:.0f} minutes)")

        try:
            while True:
                self.logger.info("=" * 60)
                self.logger.info(f"Checking for unpublished briefs - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info("=" * 60)

                processed = self.process_briefs()

                if processed > 0:
                    self.logger.info(f"Published {processed} research brief(s)")

                next_run = datetime.now() + timedelta(seconds=interval)
                self.logger.info(f"Next check at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("Stopping publisher...")
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
            raise

if __name__ == "__main__":
    publisher = ResearchBriefPublisher()
    # Run every 30 minutes (1800 seconds)
    # Can be changed to 3600 for hourly, or any other interval
    publisher.run(interval=1800)
