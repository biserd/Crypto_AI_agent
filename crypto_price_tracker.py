import os
import logging
import requests
from datetime import datetime
from database import db
from models import CryptoPrice

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CryptoPriceTracker:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.crypto_ids = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'USDT': 'tether', 'BNB': 'binancecoin',
            'SOL': 'solana', 'XRP': 'ripple', 'USDC': 'usd-coin', 'ADA': 'cardano',
            'DOGE': 'dogecoin', 'TON': 'the-open-network', 'TRX': 'tron', 'DAI': 'dai',
            'MATIC': 'matic-network', 'DOT': 'polkadot', 'WBTC': 'wrapped-bitcoin',
            'AVAX': 'avalanche-2', 'SHIB': 'shiba-inu', 'LEO': 'leo-token', 'LTC': 'litecoin',
            'UNI': 'uniswap', 'LINK': 'chainlink', 'BCH': 'bitcoin-cash', 'XLM': 'stellar',
            'OKB': 'okb', 'NEAR': 'near', 'ICP': 'internet-computer', 'VET': 'vechain',
            'INJ': 'injective-protocol', 'APT': 'aptos', 'ALGO': 'algorand', 'GRT': 'the-graph',
            'FIL': 'filecoin', 'ATOM': 'cosmos', 'IMX': 'immutable-x', 'HBAR': 'hedera-hashgraph',
            'THETA': 'theta-network', 'XTZ': 'tezos', 'EOS': 'eos', 'AAVE': 'aave',
            'MKR': 'maker', 'SAND': 'the-sandbox', 'QNT': 'quant-network', 'CRV': 'curve-dao-token',
            'EGLD': 'elrond-erd-2', 'XDC': 'xdce-crowd-sale', 'FLOW': 'flow', 'NEO': 'neo',
            'KCS': 'kucoin-shares', 'ZEC': 'zcash', 'BTT': 'bittorrent', 'KAVA': 'kava',
            'MANA': 'decentraland', 'TUSD': 'true-usd', 'RUNE': 'thorchain', 'KLAY': 'klay-token',
            'GT': 'gatechain-token', 'BSV': 'bitcoin-sv', 'CHZ': 'chiliz', 'XEC': 'ecash',
            'BEAM': 'beam', 'HT': 'huobi-token', 'FTM': 'fantom', 'IOTA': 'iota',
            'AR': 'arweave', 'CSPR': 'casper-network', 'STX': 'blockstack', 'RNDR': 'render-token',
            'GMX': 'gmx', 'SNX': 'havven', 'CAKE': 'pancakeswap-token', 'GALA': 'gala',
            'DYDX': 'dydx', 'OP': 'optimism', 'MINA': 'mina-protocol', 'CFX': 'conflux-token',
            'WAXP': 'wax', 'ROSE': 'oasis-network', '1INCH': '1inch', 'ENJ': 'enjincoin',
            'NEXO': 'nexo', 'CKB': 'nervos-network', 'RPL': 'rocket-pool', 'WOO': 'woo-network',
            'POLY': 'polymath', 'COMP': 'compound-governance-token', 'DASH': 'dash',
            'BAT': 'basic-attention-token', 'ZIL': 'zilliqa', 'LRC': 'loopring',
            'FLUX': 'zelcash', 'ONE': 'harmony', 'HOT': 'holotoken', 'ICX': 'icon',
            'OCEAN': 'ocean-protocol', 'KDA': 'kadena', 'XEM': 'nem', 'SUSHI': 'sushi',
            'MASK': 'mask-network', 'TWT': 'trust-wallet-token', 'DCR': 'decred',
            'GLM': 'golem', 'SKL': 'skale', 'JASMY': 'jasmycoin', 'AMP': 'amp-token',
            'CELR': 'celer-network', 'QTUM': 'qtum', 'RVN': 'ravencoin', 'ONT': 'ontology',
            'RSR': 'reserve-rights-token', 'ANKR': 'ankr', 'SC': 'siacoin',
            'ONDO': 'ondo-finance'  # Added Ondo token
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

            try:
                db.session.commit()
                return True
            except:
                db.session.rollback()
                # Try one more time
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