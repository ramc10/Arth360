import os
import requests
import time
from datetime import datetime

class AlphaVantageClient:
    """
    Alpha Vantage API Client for stock data

    Features:
    - Real-time quotes for US and Indian stocks
    - Company overview (fundamentals)
    - Rate limiting (5 API calls/minute free tier, 500/day)
    - Response caching
    """

    def __init__(self):
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.base_url = 'https://www.alphavantage.co/query'

        # Rate limiting (5 calls/minute on free tier)
        self.last_request_time = {}
        self.min_interval = 12  # 12 seconds between requests (5 calls/min)

        # Cache for stock data (symbol: (data, timestamp))
        self.cache = {}
        self.cache_duration = 300  # 5 minutes

    def _rate_limited_request(self, symbol):
        """Apply rate limiting before making request"""
        current_time = time.time()

        if symbol in self.last_request_time:
            time_since_last = current_time - self.last_request_time[symbol]
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                print(f"  Rate limiting: waiting {wait_time:.1f}s for {symbol}")
                time.sleep(wait_time)

        self.last_request_time[symbol] = time.time()

    def get_quote(self, symbol):
        """
        Get real-time quote for a symbol

        Args:
            symbol: Stock ticker (e.g., 'AAPL', 'RELIANCE.BSE')

        Returns:
            dict: Stock data or error
        """
        # Check cache first
        if symbol in self.cache:
            cached_data, cached_time = self.cache[symbol]
            if time.time() - cached_time < self.cache_duration:
                print(f"  Using cached data for {symbol} (age: {int(time.time() - cached_time)}s)")
                return cached_data

        # Apply rate limiting
        self._rate_limited_request(symbol)

        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if 'Error Message' in data:
                return {
                    'symbol': symbol,
                    'error': f"API Error: {data['Error Message']}"
                }

            if 'Note' in data:
                # Rate limit message
                return {
                    'symbol': symbol,
                    'error': 'Rate limit reached. Please wait.'
                }

            if 'Global Quote' not in data or not data['Global Quote']:
                return {
                    'symbol': symbol,
                    'error': 'No data available for this symbol'
                }

            quote = data['Global Quote']

            # Parse Alpha Vantage response
            stock_data = {
                'symbol': symbol,
                'price': float(quote.get('05. price', 0)),
                'change_percent': float(quote.get('10. change percent', '0').replace('%', '')),
                'volume': int(quote.get('06. volume', 0)),
                'open': float(quote.get('02. open', 0)),
                'high': float(quote.get('03. high', 0)),
                'low': float(quote.get('04. low', 0)),
                'previous_close': float(quote.get('08. previous close', 0)),
                'latest_trading_day': quote.get('07. latest trading day'),
                'source': 'Alpha Vantage'
            }

            # Cache successful response
            self.cache[symbol] = (stock_data, time.time())

            return stock_data

        except requests.exceptions.RequestException as e:
            return {
                'symbol': symbol,
                'error': f'Network error: {str(e)}'
            }
        except (KeyError, ValueError) as e:
            return {
                'symbol': symbol,
                'error': f'Data parsing error: {str(e)}'
            }
        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Unexpected error: {str(e)}'
            }

    def get_company_overview(self, symbol):
        """
        Get company fundamentals (market cap, P/E ratio, etc.)

        Args:
            symbol: Stock ticker

        Returns:
            dict: Company data or error
        """
        # Check cache
        cache_key = f"{symbol}_overview"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            # Overview data cached for 24 hours (doesn't change frequently)
            if time.time() - cached_time < 86400:
                return cached_data

        # Apply rate limiting
        self._rate_limited_request(symbol)

        try:
            params = {
                'function': 'OVERVIEW',
                'symbol': symbol,
                'apikey': self.api_key
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'Error Message' in data or not data:
                return None

            if 'Note' in data:
                return None  # Rate limited

            overview = {
                'market_cap': int(float(data.get('MarketCapitalization', 0))) if data.get('MarketCapitalization') else None,
                'pe_ratio': float(data.get('PERatio', 0)) if data.get('PERatio') and data.get('PERatio') != 'None' else None,
                'fifty_two_week_high': float(data.get('52WeekHigh', 0)) if data.get('52WeekHigh') else None,
                'fifty_two_week_low': float(data.get('52WeekLow', 0)) if data.get('52WeekLow') else None,
                'beta': float(data.get('Beta', 0)) if data.get('Beta') and data.get('Beta') != 'None' else None,
                'dividend_yield': float(data.get('DividendYield', 0)) if data.get('DividendYield') else None,
                'eps': float(data.get('EPS', 0)) if data.get('EPS') and data.get('EPS') != 'None' else None
            }

            # Cache overview data
            self.cache[cache_key] = (overview, time.time())

            return overview

        except Exception as e:
            print(f"  Error fetching overview for {symbol}: {e}")
            return None

    def get_stock_data(self, symbol):
        """
        Get complete stock data (quote + overview)

        This is the main method used by research service

        Args:
            symbol: Stock ticker

        Returns:
            dict: Combined stock data
        """
        print(f"  Fetching {symbol} from Alpha Vantage...")

        # Get real-time quote
        quote_data = self.get_quote(symbol)

        if 'error' in quote_data:
            return quote_data

        # Get company overview (fundamentals)
        # Only fetch if not cached (to save API calls)
        overview = self.get_company_overview(symbol)

        # Combine quote and overview data
        if overview:
            quote_data.update({
                'market_cap': overview.get('market_cap'),
                'pe_ratio': overview.get('pe_ratio'),
                'fifty_two_week_high': overview.get('fifty_two_week_high'),
                'fifty_two_week_low': overview.get('fifty_two_week_low')
            })

        return quote_data

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()

    def get_cache_stats(self):
        """Get cache statistics"""
        return {
            'cached_symbols': len(self.cache),
            'symbols': list(self.cache.keys())
        }
