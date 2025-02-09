import os
import logging
import requests
from datetime import datetime, timedelta
from database import db
from models import CryptoPrice
import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CryptoPriceTracker:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.last_request_time = 0
        self.min_request_interval = 1.2  # Minimum time between requests in seconds
        self.api_key = os.environ.get('COINGECKO_API_KEY', '')  # Get API key from environment variable
        self.crypto_ids = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'USDT': 'tether', 'BNB': 'binancecoin',
            'SOL': 'solana', 'XRP': 'ripple', 'USDC': 'usd-coin', 'ADA': 'cardano',
            'DOGE': 'dogecoin', 'TON': 'the-open-network', 'TRX': 'tron', 'DAI': 'dai',
            'MATIC': 'matic-network', 'DOT': 'polkadot', 'WBTC': 'wrapped-bitcoin',
            'AVAX': 'avalanche-2', 'SHIB': 'shiba-inu', 'LEO': 'leo-token', 'LTC': 'litecoin',
            'UNI': 'uniswap', 'CAKE': 'pancakeswap-token', 'LINK': 'chainlink',
            'ATOM': 'cosmos', 'APE': 'apecoin', 'AAVE': 'aave', 'ETH': 'ethereum',
            'RPL': 'rocket-pool'
        }

    def _rate_limit_wait(self):
        """Ensure we don't exceed API rate limits"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last_request
            logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def _make_request(self, url, params=None, max_retries=3):
        """Make a request to the CoinGecko API with improved error handling"""
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'CryptoIntelligence/1.0',
            'x-cg-pro-api-key': self.api_key
        }
        logger.info("Making API request with key present: %s", bool(self.api_key))

        for attempt in range(max_retries):
            try:
                self._rate_limit_wait()
                logger.debug(f"Making request to {url} with params {params}")

                response = requests.get(url, params=params, headers=headers, timeout=10)

                if response.status_code == 429:  # Rate limit reached
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit hit. Waiting {retry_after} seconds")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    sleep_time = (attempt + 1) * 2
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                continue

        return None

    def fetch_current_prices(self):
        """Fetch current prices for all tracked cryptocurrencies"""
        try:
            logger.info("Starting to fetch current prices")
            ids = ','.join(self.crypto_ids.values())
            api_url = f"{self.base_url}/simple/price"
            params = {
                'ids': ids,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            }

            data = self._make_request(api_url, params)
            if not data:
                logger.error("Failed to fetch current prices")
                return False

            updates = []
            for symbol, coin_id in self.crypto_ids.items():
                if coin_id in data:
                    try:
                        price_data = {
                            'symbol': symbol,
                            'price_usd': data[coin_id]['usd'],
                            'percent_change_24h': data[coin_id].get('usd_24h_change', 0),
                            'last_updated': datetime.utcnow()
                        }
                        updates.append(price_data)
                        logger.debug(f"Processed price data for {symbol}: ${price_data['price_usd']}")
                    except Exception as e:
                        logger.error(f"Error processing {symbol} price: {str(e)}")
                        continue

            try:
                for update in updates:
                    price = CryptoPrice.query.filter_by(symbol=update['symbol']).first()
                    if not price:
                        price = CryptoPrice(symbol=update['symbol'])
                        db.session.add(price)
                        logger.info(f"Created new price record for {update['symbol']}")

                    price.price_usd = update['price_usd']
                    price.percent_change_24h = update['percent_change_24h']
                    price.last_updated = update['last_updated']

                db.session.commit()
                logger.info(f"Successfully updated prices for {len(updates)} cryptocurrencies")
                return True

            except Exception as e:
                logger.error(f"Database error: {str(e)}")
                db.session.rollback()
                return False

        except Exception as e:
            logger.error(f"Error in fetch_current_prices: {str(e)}")
            return False

    def get_historical_prices(self, symbol, days=30, interval='daily', max_retries=3):
        """Fetch historical price data with improved validation and error handling"""
        try:
            logger.info(f"Fetching historical data for {symbol} with {days} days interval {interval}")

            symbol = symbol.upper()
            coin_id = self.crypto_ids.get(symbol)
            if not coin_id:
                logger.error(f"Invalid symbol: {symbol}")
                return None

            api_url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': str(days)
            }

            headers = {
                'Accept': 'application/json',
                'User-Agent': 'CryptoIntelligence/1.0',
                'x-cg-pro-api-key': self.api_key
            }

            for attempt in range(max_retries):
                try:
                    self._rate_limit_wait()
                    logger.info(f"Making request to {api_url} with params {params} (attempt {attempt + 1})")
                    
                    response = requests.get(api_url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        logger.warning(f"Rate limit hit, waiting {retry_after} seconds")
                        time.sleep(retry_after)
                        continue
                        
                    response.raise_for_status()
                    data = response.json()

                    if not data or 'prices' not in data:
                        logger.error(f"Invalid response data for {symbol}")
                        continue

                    logger.info(f"Successfully fetched {len(data['prices'])} price points for {symbol}")
                    return {
                        'prices': data['prices'],
                        'market_caps': data.get('market_caps', []),
                        'total_volumes': data.get('total_volumes', [])
                    }

                except requests.exceptions.RequestException as e:
                    logger.error(f"Request error on attempt {attempt + 1}: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    continue

            error_msg = f"Failed to fetch data for {symbol} after {max_retries} attempts due to rate limits"
            logger.error(error_msg)
            return {'error': error_msg, 'retry_after': 30}

        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return None

def get_latest_prices():
    """Get latest prices for all tracked cryptocurrencies"""
    return CryptoPrice.query.all()

if __name__ == "__main__":
    tracker = CryptoPriceTracker()
    tracker.fetch_current_prices()