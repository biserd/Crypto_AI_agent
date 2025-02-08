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
        self.min_request_interval = 1.2  # Increased to avoid rate limits
        self.crypto_ids = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'USDT': 'tether', 'BNB': 'binancecoin',
            'SOL': 'solana', 'XRP': 'ripple', 'USDC': 'usd-coin', 'ADA': 'cardano',
            'DOGE': 'dogecoin', 'TON': 'the-open-network', 'TRX': 'tron', 'DAI': 'dai',
            'MATIC': 'matic-network', 'DOT': 'polkadot', 'WBTC': 'wrapped-bitcoin',
            'AVAX': 'avalanche-2', 'SHIB': 'shiba-inu', 'LEO': 'leo-token', 'LTC': 'litecoin',
            'UNI': 'uniswap', 'CAKE': 'pancakeswap-token', 'LINK': 'chainlink',
            'ATOM': 'cosmos', 'APE': 'apecoin', 'AAVE': 'aave'
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

    def _make_request(self, url, params=None, max_retries=3, retry_delay=2):
        """Make a request to the CoinGecko API with retries and error handling"""
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (CryptoIntelligence/1.0)'
        }

        for attempt in range(max_retries):
            try:
                self._rate_limit_wait()
                logger.debug(f"Making request to {url} with params {params}")
                response = requests.get(url, params=params, headers=headers, timeout=10)

                if response.status_code == 429:  # Rate limit
                    wait_time = float(response.headers.get('Retry-After', retry_delay * (attempt + 1)))
                    logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                if response.status_code == 404:
                    logger.error(f"Resource not found: {url}")
                    return None
                logger.error(f"HTTP error on attempt {attempt + 1}: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {str(e)}")

            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))

        return None

    def get_historical_prices(self, symbol, days=30, interval='daily'):
        """Fetch historical price data for a cryptocurrency"""
        try:
            logger.info(f"Fetching historical data for {symbol} with {days} days interval {interval}")

            coin_id = self.crypto_ids.get(symbol.upper())
            if not coin_id:
                logger.error(f"Symbol {symbol} not found in mapping. Available symbols: {', '.join(sorted(self.crypto_ids.keys()))}")
                return None

            api_url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': str(days),
                'interval': interval
            }

            data = self._make_request(api_url, params)
            if not data or 'prices' not in data:
                logger.error(f"Invalid or empty data received for {symbol}")
                return None

            logger.info(f"Successfully fetched {len(data['prices'])} price points for {symbol}")
            return {
                'prices': data['prices'],
                'market_caps': data.get('market_caps', []),
                'total_volumes': data.get('total_volumes', [])
            }

        except Exception as e:
            logger.error(f"Unexpected error fetching data for {symbol}: {str(e)}", exc_info=True)
            return None

    def fetch_current_prices(self):
        """Fetch current prices for tracked cryptocurrencies"""
        try:
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
                        logger.debug(f"Updated {symbol} price: ${price_data['price_usd']:.2f}")
                    except Exception as e:
                        logger.error(f"Error processing {symbol} price: {str(e)}")
                        continue

            try:
                for update in updates:
                    price = CryptoPrice.query.filter_by(symbol=update['symbol']).first()
                    if not price:
                        price = CryptoPrice(symbol=update['symbol'])
                        db.session.add(price)
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

def get_latest_prices():
    """Get latest prices for all tracked cryptocurrencies"""
    return CryptoPrice.query.all()

if __name__ == "__main__":
    tracker = CryptoPriceTracker()
    tracker.fetch_current_prices()