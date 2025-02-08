import os
import logging
import requests
from datetime import datetime, timedelta

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class EtherscanClient:
    def __init__(self):
        self.api_key = os.environ.get('ETHERSCAN_API_KEY')
        self.base_url = "https://api.etherscan.io/api"

    def get_address_balance(self, address):
        """Get ETH balance for an address"""
        try:
            params = {
                'module': 'account',
                'action': 'balance',
                'address': address,
                'tag': 'latest',
                'apikey': self.api_key
            }
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            if data['status'] == '1':
                return int(data['result']) / 1e18  # Convert from Wei to ETH
            return None
        except Exception as e:
            logger.error(f"Error fetching address balance: {str(e)}")
            return None

    def get_daily_transactions(self, days=7):
        """Get daily transaction count for last n days"""
        try:
            # Calculate the date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            params = {
                'module': 'stats',
                'action': 'dailytx',
                'startdate': int(start_date.timestamp()),
                'enddate': int(end_date.timestamp()),
                'sort': 'asc',
                'apikey': self.api_key
            }

            response = requests.get(self.base_url, params=params)
            if response.status_code != 200:
                logger.error(f"Error response from Etherscan: {response.status_code}")
                return []

            data = response.json()

            if data['status'] == '1' and data['result']:
                # Format the data for the chart
                return [
                    {
                        'date': datetime.fromtimestamp(int(tx['unixTimeStamp'])).strftime('%Y-%m-%d'),
                        'value': int(tx['transactionCount'])
                    }
                    for tx in data['result']
                ]
            logger.warning("No transaction data received from Etherscan")
            return []
        except Exception as e:
            logger.error(f"Error fetching daily transactions: {str(e)}")
            return []

    def get_network_hash_rate(self):
        """Get current network hash rate"""
        try:
            params = {
                'module': 'stats',
                'action': 'ethsupply',
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '1':
                return data['result']
            return None
        except Exception as e:
            logger.error(f"Error fetching network hash rate: {str(e)}")
            return None

    def get_gas_oracle(self):
        """Get current gas prices"""
        try:
            params = {
                'module': 'gastracker',
                'action': 'gasoracle',
                'apikey': self.api_key
            }

            response = requests.get(self.base_url, params=params)
            if response.status_code != 200:
                logger.error(f"Error response from Etherscan gas oracle: {response.status_code}")
                return None

            data = response.json()

            if data['status'] == '1' and data['result']:
                return data['result']
            logger.warning("No gas oracle data received from Etherscan")
            return None
        except Exception as e:
            logger.error(f"Error fetching gas oracle: {str(e)}")
            return None