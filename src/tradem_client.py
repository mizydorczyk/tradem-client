import requests
import logging
import certifi
from models import User, Account, Wallet
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
            raise ValueError("Default account is not set. Initialize the client first.")

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
            raise ValueError("Default account is not set. Initialize the client first.")

        for account in self.user_data.accounts:
            if account.id == target_account_id:
                logger.info(f"Found {len(account.wallets)} wallets for account {target_account_id}")
                return account.wallets
        
        logger.warning(f"Account {target_account_id} not found")
        return []
