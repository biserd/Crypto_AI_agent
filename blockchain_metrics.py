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
            end_timestamp = int(datetime.now().timestamp())
            start_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
            
            params = {
                'module': 'stats',
                'action': 'dailytx',
                'startdate': start_timestamp,
                'enddate': end_timestamp,
                'sort': 'asc',
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '1':
                return data['result']
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
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '1':
                return data['result']
            return None
        except Exception as e:
            logger.error(f"Error fetching gas oracle: {str(e)}")
            return None
