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
        self.min_request_interval = 1.0  # Minimum time between requests in seconds
        self.crypto_ids = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'USDT': 'tether', 'BNB': 'binancecoin',
            'SOL': 'solana', 'XRP': 'ripple', 'USDC': 'usd-coin', 'ADA': 'cardano',
            'DOGE': 'dogecoin', 'TON': 'the-open-network', 'TRX': 'tron', 'DAI': 'dai',
            'MATIC': 'matic-network', 'DOT': 'polkadot', 'WBTC': 'wrapped-bitcoin',
            'AVAX': 'avalanche-2', 'SHIB': 'shiba-inu', 'LEO': 'leo-token', 'LTC': 'litecoin',
            'UNI': 'uniswap', 'LINK': 'chainlink'
        }

    def _rate_limit_wait(self):
        """Ensure we don't exceed API rate limits"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        self.last_request_time = time.time()

    def get_historical_prices(self, symbol, days=30, interval='daily'):
        """
        Fetch historical price data for a cryptocurrency

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC')
            days: Number of days of historical data
            interval: Data interval ('daily' or 'hourly')
        """
        try:
            coin_id = self.crypto_ids.get(symbol.upper())
            if not coin_id:
                logger.error(f"Symbol not found: {symbol}")
                return None

            self._rate_limit_wait()

            api_url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': interval
            }

            headers = {
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Crypto Intelligence Platform)'
            }

            logger.info(f"Fetching historical data for {symbol} ({coin_id})")
            response = requests.get(api_url, params=params, headers=headers, timeout=15)

            if response.status_code == 429:
                logger.warning("Rate limit reached, waiting before retry")
                time.sleep(60)  # Wait for rate limit to reset
                return None

            if response.status_code != 200:
                logger.error(f"API Error {response.status_code}: {response.text}")
                return None

            data = response.json()
            if not data or 'prices' not in data:
                logger.error(f"Invalid data format received for {symbol}")
                return None

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {symbol}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching data for {symbol}: {str(e)}")
            return None

    def fetch_current_prices(self):
        """Fetch current prices for tracked cryptocurrencies"""
        try:
            self._rate_limit_wait()

            # Join all crypto IDs with commas for the API call
            ids = ','.join(self.crypto_ids.values())

            response = requests.get(
                f"{self.base_url}/simple/price",
                params={
                    'ids': ids,
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true'
                }
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch prices: {response.status_code}")
                return False

            data = response.json()
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
                        logger.info(f"Updated {symbol} price: ${price_data['price_usd']:.2f}")
                    except Exception as e:
                        logger.error(f"Error processing {symbol} price: {str(e)}")
                        continue

            # Batch update prices
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