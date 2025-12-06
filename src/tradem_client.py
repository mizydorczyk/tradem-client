import requests
import logging
from models import User, Wallet
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format='[Client] %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Client:
    API_KEY = 'AIzaSyBOEvN4OzAePlFp1fSRKWJlioA9r2WPZHw'
    AUTH_URL = 'https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword'
    BASE_API_URL = 'https://platform.tradem.online/api'
    BASE_UI_URL = 'https://platform.tradem.online/ui/api'

    def __init__(self, email: str, password: str, api_key: Optional[str] = API_KEY, verify_ssl: Optional[bool] = False):
        self.email = email
        self.password = password
        self.api_key = api_key
        self.verify_ssl = verify_ssl if verify_ssl is not None else False
        self.api_token = None
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        self.user_data = None
        self.default_account_id = None

    def initialize(self):
        logger.info("Initializing...")

        self._authenticate()
        self._ui_login()
        self._get_user_data()
        
        if self.user_data and self.user_data.accounts:
            self.default_account_id = self.user_data.accounts[0].id
            logger.info(f"Default account set to {self.default_account_id}.")
        
        logger.info("Initialization complete")

    def _authenticate(self):
        logger.info("Authenticating...")

        payload = {
            "email": self.email,
            "password": self.password,
            "returnSecureToken": True,
        }
        response = requests.post(self.AUTH_URL, json=payload, params={'key': self.api_key}, verify=self.verify_ssl)
        response.raise_for_status()
        self.api_token = response.json()['idToken']

        logger.info("Authentication successful.")

    def _ui_login(self):
        logger.info("Logging into UI API...")

        url = f'{self.BASE_UI_URL}/auth/login'
        headers = {'Authorization': f'{self.api_token}', 'Content-Type': 'application/json'}
        response = self.session.post(url, headers=headers, data='', verify=self.verify_ssl)
        response.raise_for_status()

        logger.info("UI login successful.")

    def _get_user_data(self):
        logger.info("Fetching user data...")

        url = f'{self.BASE_UI_URL}/user'
        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        self.user_data = User.from_dict(response.json())

        logger.info("User data fetched successfully.")
        return self.user_data

    def create_transaction(self, source_wallet_id: str, dest_wallet_id: str, amount_from_source: Optional[float] = None, amount_to_dest: Optional[float] = None, exchange_rate: Optional[float] = None) -> dict:
        logger.info(f"Creating transaction from {source_wallet_id} to {dest_wallet_id}")
        
        url = f'{self.BASE_API_URL}/transaction'
        payload = {
            "sourceWalletId": source_wallet_id, 
            "destWalletId": dest_wallet_id,
        }

        if amount_from_source is not None:
            payload["amountFromSourceWallet"] = amount_from_source
        if amount_to_dest is not None:
            payload["amountToDestWallet"] = amount_to_dest
        if exchange_rate is not None:
            payload["exchangeRate"] = exchange_rate

        headers = {'Authorization': f'Bearer {self.api_token}'}
        response = requests.post(url, headers=headers, json=payload, verify=self.verify_ssl)
        response.raise_for_status()

        logger.info("Transaction created successfully")
        return response.json()

    def get_wallet_valuation(self, wallet_id: str, account_id: Optional[str] = None, limit: Optional[int] = None, from_time: Optional[int] = None, to_time: Optional[int] = None, offset: Optional[int] = None) -> dict:
        target_account_id = account_id or self.default_account_id
        if not target_account_id:
            raise Exception("Default account is not set. Initialize the client first.")

        logger.info(f"Fetching wallet valuation for wallet {wallet_id}")
        
        url = f'{self.BASE_API_URL}/account/{target_account_id}/wallet/{wallet_id}/valuation'
        params = {}
        
        if limit is not None:
            params['limit'] = limit
        if from_time is not None:
            params['fromTime'] = from_time
        if to_time is not None:
            params['toTime'] = to_time
        if offset is not None:
            params['offset'] = offset

        headers = {'Authorization': f'Bearer {self.api_token}'}
        response = requests.get(url, headers=headers, params=params, verify=self.verify_ssl)
        response.raise_for_status()
        logger.info("Wallet valuation fetched successfully.")
        return response.json()

    def get_wallets(self, account_id: Optional[str] = None) -> List[Wallet]:
        logger.info("Fetching wallets...")
        
        target_account_id = account_id or self.default_account_id
        if not target_account_id:
            raise Exception("Default account is not set. Initialize the client first.")

        for account in self.user_data.accounts:
            if account.id == target_account_id:
                logger.info(f"Found {len(account.wallets)} wallets for account {target_account_id}")
                return account.wallets
        
        logger.warning(f"Account {target_account_id} not found")
        return []

    def _get_wallet_by_currency(self, currency_id: str, wallets: List[Wallet]) -> Optional[Wallet]:
        """Finds a wallet for a specific currency in the provided list."""
        
        for wallet in wallets:
            if wallet.currency_id.lower() == currency_id.lower():
                return wallet
        
        return None

    def buy(self, currency_id: str, amount: float) -> dict:
        """
        Buys a specific amount of a currency using funds from the funding wallet (USD/FIAT).
        
        Args:
            currency_id: The currency to buy (e.g., 'BTC').
            amount: The amount of the currency to buy.
        Returns:
            dict: {"amount": float, "price": float, "position": "long"}
        """

        if not self.default_account_id:
             raise Exception("Default account is not set. Initialize the client first.")

        wallets = self.get_wallets(self.default_account_id)
        
        target_wallet = self._get_wallet_by_currency(currency_id, wallets)
        if not target_wallet:
            raise Exception(f"No wallet found for currency {currency_id}")
            
        funding_wallet = self._get_wallet_by_currency('USD', wallets)
        if not funding_wallet:
            raise Exception("No USD wallet found in the default account.")
        if target_wallet.id == funding_wallet.id:
            raise Exception(f"Cannot buy {currency_id} with itself.")

        response = self.create_transaction(
            source_wallet_id=funding_wallet.id,
            dest_wallet_id=target_wallet.id,
            amount_to_dest=amount
        )
        
        attributes = response['data'][0]['attributes']
        executed_amount = float(attributes['amountToDestWallet'])
        price = float(attributes['exchangeRate'])

        return {
            "amount": executed_amount,
            "price": price,
            "position": "long"
        }

    def sell(self, currency_id: str, amount: float) -> dict:
        """
        Sells a specific amount of a currency creating funds in the funding wallet (USD/FIAT).
         
        Args:
            currency_id: The currency to sell (e.g., 'btc').
            amount: The amount of the currency to sell.
            
        Returns:
             dict: {"amount": float, "price": float, "position": "short"}
        """

        if not self.default_account_id:
             raise Exception("Default account is not set. Initialize the client first.")

        wallets = self.get_wallets(self.default_account_id)

        source_wallet = self._get_wallet_by_currency(currency_id, wallets)
        if not source_wallet:
            raise Exception(f"No wallet found for currency {currency_id}")
            
        funding_wallet = self._get_wallet_by_currency('USD', wallets)
        if not funding_wallet:
            raise Exception("No USD wallet found in the default account.")
        if source_wallet.id == funding_wallet.id:
            raise Exception(f"Cannot sell {currency_id} for itself.")

        response = self.create_transaction(
             source_wallet_id=source_wallet.id,
             dest_wallet_id=funding_wallet.id,
             amount_from_source=amount
        )

        attributes = response['data'][0]['attributes']
        executed_amount = float(attributes['amountFromSourceWallet'])
        price = float(attributes['exchangeRate'])

        return {
            "amount": executed_amount,
            "price": price,
            "position": "short"
        }
