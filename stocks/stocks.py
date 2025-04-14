import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import yfinance as yf
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from dotenv import load_dotenv
import time
from tqdm import tqdm

# Load environment variables from base directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EQUITY_L.csv")

class StocksMonitor:
    def __init__(self):
        self.setup_logger()
        self.create_tables()

    def setup_logger(self):
        self.logger = logging.getLogger('StocksMonitor')
        self.logger.setLevel(logging.INFO)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'stock_monitor.log'),
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)

    def log_console(self, emoji, message):
        print(f"{datetime.now().strftime('%H:%M:%S')} {emoji} {message}")
        self.logger.info(message)

    def create_db_connection(self):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            self.log_console("🛢️", "Database connection established!")
            return conn
        except Error as e:
            self.log_console("🔥", f"Database connection error: {str(e)}")
            return None

    def create_tables(self):
        connection = self.create_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS listed_stocks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL UNIQUE,
                    company_name VARCHAR(255) NOT NULL,
                    exchange ENUM('NSE', 'BSE') NOT NULL,
                    isin VARCHAR(12),
                    sector VARCHAR(100),
                    industry VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ohlc_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    stock_id INT NOT NULL,
                    date DATE NOT NULL,
                    open DECIMAL(10,2),
                    high DECIMAL(10,2),
                    low DECIMAL(10,2),
                    close DECIMAL(10,2),
                    volume BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_stock_date (stock_id, date),
                    FOREIGN KEY (stock_id) REFERENCES listed_stocks(id)
                );
            """)
            connection.commit()
            self.log_console("📦", "Database tables ensured!")
        except Error as e:
            self.log_console("💥", f"Error creating tables: {str(e)}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    def get_sector_industry(self, symbol):
        """Fetch sector and industry information from Yahoo Finance"""
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            info = ticker.info
            return info.get('sector', None), info.get('industry', None)
        except Exception as e:
            self.log_console("⚠️", f"Failed to fetch info for {symbol}: {str(e)}")
            return None, None
        
    def insert_stocks_from_csv(self):
        try:
            # Read CSV with stripped column names
            df = pd.read_csv(CSV_FILE)
            df.columns = df.columns.str.strip()
            
            self.log_console("🔍", f"Columns in CSV: {list(df.columns)}")
            
            # Select and rename available columns
            rename_cols = {
                'SYMBOL': 'symbol',
                'NAME OF COMPANY': 'company_name',
                'ISIN NUMBER': 'isin'
            }
            df = df[list(rename_cols.keys())].rename(columns=rename_cols)
            
            # Add exchange column
            df['exchange'] = 'NSE'
            
            # Clean data
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
            df = df.where(pd.notnull(df), None)
            
            # Database insertion
            connection = self.create_db_connection()
            if connection:
                try:
                    cursor = connection.cursor(dictionary=True)
                    
                    # Insert basic stock info first
                    insert_query = """
                        INSERT INTO listed_stocks 
                        (symbol, company_name, exchange, isin, sector, industry)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            company_name = VALUES(company_name),
                            isin = VALUES(isin)
                    """
                    
                    # Prepare data with None for sector/industry initially
                    data = [(
                        str(row['symbol']),
                        str(row['company_name']),
                        'NSE',
                        str(row['isin']) if row['isin'] else None,
                        None,
                        None
                    ) for _, row in df.iterrows()]
                    
                    cursor.executemany(insert_query, data)
                    connection.commit()
                    self.log_console("✅", f"Inserted/updated {len(df)} basic stock records")
                    
                    # Now update sector and industry info
                    self.log_console("🔄", "Fetching sector/industry info from Yahoo Finance...")
                    
                    # Get stocks missing sector/industry info
                    cursor.execute("""
                        SELECT id, symbol FROM listed_stocks 
                        WHERE sector IS NULL OR industry IS NULL
                    """)
                    stocks_to_update = cursor.fetchall()
                    
                    updated = 0
                    for stock in tqdm(stocks_to_update, desc="Updating sector/industry"):
                        sector, industry = self.get_sector_industry(stock['symbol'])
                        if sector or industry:
                            update_query = """
                                UPDATE listed_stocks 
                                SET sector = %s, industry = %s 
                                WHERE id = %s
                            """
                            cursor.execute(update_query, (sector, industry, stock['id']))
                            connection.commit()
                            updated += 1
                            time.sleep(0.5)  # Rate limiting
                    
                    self.log_console("✅", f"Updated sector/industry for {updated}/{len(stocks_to_update)} stocks")
                    
                except Exception as e:
                    self.log_console("⚠️", f"Database error: {e}")
                    connection.rollback()
                finally:
                    cursor.close()
                    connection.close()
                    
        except Exception as e:
            self.log_console("💥", f"CSV processing error: {e}")
            raise

    def fetch_and_store_ohlc(self, days_back=7, batch_size=50):
        connection = self.create_db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get all NSE stocks
            cursor.execute("SELECT id, symbol FROM listed_stocks WHERE exchange = 'NSE'")
            stocks = cursor.fetchall()
            
            total_stocks = len(stocks)
            self.log_console("🔍", f"Found {total_stocks} NSE stocks to process")

            # Date range for OHLC data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            processed = 0
            errors = 0
            
            for i in range(0, total_stocks, batch_size):
                batch = stocks[i:i + batch_size]
                batch_processed = 0
                
                for stock in batch:
                    try:
                        ticker = f"{stock['symbol']}.NS"
                        
                        # Fetch data with retry logic
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                data = yf.download(
                                    ticker, 
                                    start=start_date, 
                                    end=end_date + timedelta(days=1),  # Include end date
                                    progress=False
                                )
                                break
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    raise
                                time.sleep(2 * (attempt + 1))  # Exponential backoff
                        
                        if data.empty:
                            self.log_console("🔍", f"No data for {ticker}")
                            continue

                        # Prepare data for bulk insert with proper float conversion
                        # Prepare data for bulk insert with proper null handling
                        ohlc_values = []
                        for date_idx, row in data.iterrows():
                            date = date_idx.date()
                            
                            # Convert each field safely
                            open_price = float(row['Open'].iloc[0]) if not pd.isna(row['Open'].iloc[0]) else None
                            high_price = float(row['High'].iloc[0]) if not pd.isna(row['High'].iloc[0]) else None
                            low_price = float(row['Low'].iloc[0]) if not pd.isna(row['Low'].iloc[0]) else None
                            close_price = float(row['Close'].iloc[0]) if not pd.isna(row['Close'].iloc[0]) else None
                            
                            # Handle volume separately since it might not exist
                            volume = None
                            if 'Volume' in row and not pd.isna(row['Volume'].iloc[0]):
                                volume = int(row['Volume'].iloc[0])
                            
                            ohlc_values.append((
                                stock['id'],
                                date,
                                open_price,
                                high_price,
                                low_price,
                                close_price,
                                volume
                            ))

                        # Bulk insert OHLC data
                        insert_query = """
                            INSERT INTO ohlc_data 
                            (stock_id, date, open, high, low, close, volume)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                open = VALUES(open),
                                high = VALUES(high),
                                low = VALUES(low),
                                close = VALUES(close),
                                volume = VALUES(volume)
                        """
                        
                        cursor.executemany(insert_query, ohlc_values)
                        connection.commit()
                        
                        batch_processed += 1
                        processed += 1
                        
                        if len(ohlc_values) > 0:
                            last_date = ohlc_values[-1][1]
                            self.log_console("📈", 
                                f"Stored {len(ohlc_values)} days for {stock['symbol']} (up to {last_date})")
                        else:
                            self.log_console("⚠️", f"No new data for {stock['symbol']}")
                        
                    except Exception as e:
                        errors += 1
                        self.log_console("⚠️", f"Failed {stock['symbol']}: {str(e)}")
                        connection.rollback()
                
                # Brief pause between batches
                time.sleep(2)
                
                self.log_console("🔄", 
                    f"Batch {i//batch_size + 1} complete. Processed: {batch_processed}/{len(batch)}")
            
            self.log_console("🎉", 
                f"OHLC update complete! Processed: {processed}, Errors: {errors}")
                
        except Exception as e:
            self.log_console("💥", f"Fatal error in OHLC update: {str(e)}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()


if __name__ == '__main__':
    monitor = StocksMonitor()
    monitor.insert_stocks_from_csv()
    monitor.fetch_and_store_ohlc(days_back=2) 
    