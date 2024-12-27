import os
import logging
import requests
from datetime import datetime
from app import db
from models import CryptoPrice

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CryptoPriceTracker:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.crypto_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'XRP': 'ripple',
            'USDC': 'usd-coin',
            'ADA': 'cardano',
            'DOGE': 'dogecoin',
            'TON': 'the-open-network',
            'TRX': 'tron',
            'DAI': 'dai',
            'MATIC': 'matic-network',
            'DOT': 'polkadot',
            'WBTC': 'wrapped-bitcoin',
            'AVAX': 'avalanche-2',
            'SHIB': 'shiba-inu',
            'LEO': 'leo-token',
            'LTC': 'litecoin',
            'UNI': 'uniswap',
            'LINK': 'chainlink'
        }

    def fetch_current_prices(self):
        """Fetch current prices for tracked cryptocurrencies"""
        try:
            # Join all crypto IDs with commas for the API call
            ids = ','.join(self.crypto_ids.values())
            
            # Make API request
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
            
            # Update database with new prices
            for symbol, coin_id in self.crypto_ids.items():
                if coin_id in data:
                    try:
                        price = CryptoPrice.query.filter_by(symbol=symbol).first()
                        if not price:
                            price = CryptoPrice(symbol=symbol)
                            db.session.add(price)
                        
                        price.price_usd = data[coin_id]['usd']
                        price.percent_change_24h = data[coin_id].get('usd_24h_change', 0)
                        price.last_updated = datetime.utcnow()
                        
                        logger.info(f"Updated {symbol} price: ${price.price_usd:.2f}")
                    except Exception as e:
                        logger.error(f"Error updating {symbol} price: {str(e)}")
                        continue

            db.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error in fetch_current_prices: {str(e)}")
            db.session.rollback()
            return False

def get_latest_prices():
    """Get latest prices for all tracked cryptocurrencies"""
    return CryptoPrice.query.all()

if __name__ == "__main__":
    tracker = CryptoPriceTracker()
    tracker.fetch_current_prices()
