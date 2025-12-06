import unittest
from unittest.mock import patch, MagicMock
from tradem_client import Client
from models import User, Account, Wallet, Currency

class TestClient(unittest.TestCase):
    def setUp(self):
        self.email = "test@example.com"
        self.password = "password123"
        self.api_key = "test_api_key"
        self.client = Client(self.email, self.password, self.api_key)

    @patch('requests.post')
    def test_authenticate_success(self, mock_post):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'idToken': 'fake_id_token'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act
        self.client._authenticate()

        # Assert
        self.assertEqual(self.client.api_token, 'fake_id_token')
        mock_post.assert_called_with(
            Client.AUTH_URL,
            json={
                "email": self.email,
                "password": self.password,
                "returnSecureToken": True,
            },
            params={'key': self.api_key},
            verify=False
        )

    @patch('requests.Session.post')
    def test_ui_login_success(self, mock_post):
        # Arrange
        self.client.api_token = 'fake_id_token'
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act
        self.client._ui_login()

        # Assert
        mock_post.assert_called_with(
            f'{Client.BASE_UI_URL}/auth/login',
            headers={'Authorization': 'fake_id_token', 'Content-Type': 'application/json'},
            data='',
            verify=False
        )

    @patch('requests.Session.get')
    def test_get_user_data_success(self, mock_get):
        # Arrange
        mock_response = MagicMock()
        user_data_response = {
            'user': {
                'id': 'user_1',
                'name': 'Test User',
                'accounts': [
                    {'id': 'acc_1', 'wallets': []}
                ]
            }
        }
        mock_response.json.return_value = user_data_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Act
        user = self.client._get_user_data()

        # Assert
        self.assertIsInstance(user, User)
        self.assertEqual(user.id, 'user_1')
        self.assertEqual(len(user.accounts), 1)
        mock_get.assert_called_with(
            f'{Client.BASE_UI_URL}/user',
            verify=False
        )

    @patch.object(Client, '_get_user_data')
    @patch.object(Client, '_ui_login')
    @patch.object(Client, '_authenticate')
    def test_initialize_success(self, mock_auth, mock_ui_login, mock_get_user_data):
        # Arrange
        mock_account = MagicMock()
        mock_account.id = 'acc_1'
        mock_user = MagicMock()
        mock_user.accounts = [mock_account]
        
        def side_effect_get_user_data():
            self.client.user_data = mock_user
        
        mock_get_user_data.side_effect = side_effect_get_user_data

        # Act
        self.client.initialize()

        # Assert
        mock_auth.assert_called_once()
        mock_ui_login.assert_called_once()
        mock_get_user_data.assert_called_once()
        self.assertEqual(self.client.default_account_id, 'acc_1')

    @patch('requests.post')
    def test_create_transaction_success(self, mock_post):
        # Arrange
        self.client.api_token = 'fake_id_token'
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': 'transaction_data'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act
        result = self.client.create_transaction(
            source_wallet_id='source_123',
            dest_wallet_id='dest_456',
            amount_from_source=10.5,
            exchange_rate=0.001
        )

        # Assert
        self.assertEqual(result, {'data': 'transaction_data'})
        mock_post.assert_called_with(
            f'{Client.BASE_API_URL}/transaction',
            headers={'Authorization': 'Bearer fake_id_token'},
            json={
                "sourceWalletId": 'source_123',
                "destWalletId": 'dest_456',
                "amountFromSourceWallet": 10.5,
                "exchangeRate": 0.001
            },
            verify=False
        )

    @patch('requests.get')
    def test_get_wallet_valuation_success(self, mock_get):
        # Arrange
        self.client.api_token = 'fake_id_token'
        self.client.default_account_id = 'default_acc' # Pre-requisite
        
        mock_response = MagicMock()
        mock_response.json.return_value = [{'valuation': 'data'}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Act
        result = self.client.get_wallet_valuation(
            wallet_id='wallet_456',
            limit=5
        )

        # Assert
        self.assertEqual(result, [{'valuation': 'data'}])
        # Should use default account if not provided
        mock_get.assert_called_with(
            f'{Client.BASE_API_URL}/account/default_acc/wallet/wallet_456/valuation',
            headers={'Authorization': 'Bearer fake_id_token'},
            params={'limit': 5},
            verify=False
        )

    def test_get_wallets_success(self):
        # Arrange
        from models import Currency
        curr_usd = Currency(id='USD', type='fiat')
        curr_eur = Currency(id='EUR', type='fiat')
        
        wallet1 = Wallet(id='w1', balance='100', currency_id='USD', currency=curr_usd)
        wallet2 = Wallet(id='w2', balance='50', currency_id='EUR', currency=curr_eur)
        
        account = Account(id='acc_1', name='Main', type='personal', wallets=[wallet1, wallet2])
        user = User(id='u1', name='Test User', accounts=[account])
        
        self.client.user_data = user
        self.client.default_account_id = 'acc_1'

        # Act
        wallets = self.client.get_wallets()

        # Assert
        self.assertEqual(len(wallets), 2)
        self.assertEqual(wallets[0].id, 'w1')
        self.assertEqual(wallets[1].id, 'w2')

    def test_get_wallets_specific_account(self):
        # Arrange
        from models import Currency
        curr_usd = Currency(id='USD', type='fiat')
        curr_eur = Currency(id='EUR', type='fiat')

        wallet1 = Wallet(id='w1', balance='100', currency_id='USD', currency=curr_usd)
        account1 = Account(id='acc_1', name='Acc 1', type='personal', wallets=[wallet1])
        
        wallet2 = Wallet(id='w2', balance='50', currency_id='EUR', currency=curr_eur)
        account2 = Account(id='acc_2', name='Acc 2', type='business', wallets=[wallet2])
        
        user = User(id='u1', name='Test User', accounts=[account1, account2])
        
        self.client.user_data = user
        self.client.default_account_id = 'acc_1'

        # Act
        wallets = self.client.get_wallets(account_id='acc_2')

        # Assert
        self.assertEqual(len(wallets), 1)
        self.assertEqual(wallets[0].id, 'w2')

    def test_get_wallets_no_default_account(self):
        # Arrange
        self.client.user_data = User(id='u1', name='Test', accounts=[])
        self.client.default_account_id = None
        
        # Act & Assert
        with self.assertRaisesRegex(Exception, "Default account is not set"):
            self.client.get_wallets()


class TestBuySell(unittest.TestCase):
    def setUp(self):
        self.client = Client(email="test@example.com", password="password")
        self.client.api_token = "fake_token"
        
        # Mock user data
        self.usd_wallet = Wallet(id="wallet_usd", balance="100000", currency_id="USD", currency=Currency(id="USD", type="FIAT"))
        self.btc_wallet = Wallet(id="wallet_btc", balance="0.5", currency_id="BTC", currency=Currency(id="BTC", type="CRYPTO"))
        
        self.account = Account(id="acc_1", name="Main", type="personal", wallets=[self.usd_wallet, self.btc_wallet])
        self.user = User(id="user_1", name="Test User", accounts=[self.account])
        
        self.client.user_data = self.user
        self.client.default_account_id = "acc_1"
        
        # Mock create_transaction to avoid network calls
        self.client.create_transaction = MagicMock()

    def test_buy_btc_success(self):
        # Mock transaction response
        mock_response = {
            "data": [{
                "attributes": {
                    "sourceWalletId": "wallet_usd",
                    "amountFromSourceWallet": "9000.00",
                    "destWalletId": "wallet_btc",
                    "amountToDestWallet": "0.1",
                    "exchangeRate": "0.000011"
                }
            }]
        }
        self.client.create_transaction.return_value = mock_response

        # Action
        result = self.client.buy('BTC', 0.1)
        
        # Assert
        self.client.create_transaction.assert_called_with(
            source_wallet_id="wallet_usd",
            dest_wallet_id="wallet_btc",
            amount_to_dest=0.1
        )
        
        self.assertEqual(result['amount'], 0.1)
        # Price should be the raw exchange rate from the response
        self.assertEqual(result['price'], 0.000011)
        self.assertEqual(result['position'], 'long')

    def test_sell_btc_success(self):
        # Mock transaction response
        mock_response = {
            "data": [{
                "attributes": {
                    "sourceWalletId": "wallet_btc",
                    "amountFromSourceWallet": "0.1",
                    "destWalletId": "wallet_usd",
                    "amountToDestWallet": "9000.00",
                    "exchangeRate": "90000.0"
                }
            }]
        }
        self.client.create_transaction.return_value = mock_response
        
        # Action
        result = self.client.sell('BTC', 0.1)
        
        # Assert
        self.client.create_transaction.assert_called_with(
            source_wallet_id="wallet_btc",
            dest_wallet_id="wallet_usd",
            amount_from_source=0.1
        )
        
        self.assertEqual(result['amount'], 0.1)
        # Price = Gain / Amount = 9000 / 0.1 = 90000
        self.assertEqual(result['price'], 90000.0)
        self.assertEqual(result['position'], 'short')

    def test_missing_usd_wallet(self):
        # Remove USD wallet
        self.account.wallets = [self.btc_wallet]
        
        with self.assertRaises(Exception) as cm:
            self.client.buy('BTC', 0.1)
        self.assertIn("No USD wallet found", str(cm.exception))

        with self.assertRaises(Exception) as cm:
            self.client.sell('BTC', 0.1)
        self.assertIn("No USD wallet found", str(cm.exception))

    def test_missing_target_wallet(self):
        with self.assertRaises(Exception) as cm:
            self.client.buy('ETH', 0.1)
        self.assertIn("No wallet found for currency ETH", str(cm.exception))

    def test_buy_usd_fails(self):
        with self.assertRaises(Exception) as cm:
            self.client.buy('USD', 100)
        self.assertIn("Cannot buy USD with itself", str(cm.exception))


class TestWebSocket(unittest.TestCase):
    def setUp(self):
        self.client = Client(email="test@example.com", password="password")
        self.client.sio = MagicMock()
        self.client.session = MagicMock()
        self.client.session.cookies.get_dict.return_value = {'connect.sid': 's%3A123', 'other': 'val'}

    def test_connect_socket_success(self):
        # Arrange
        callback = MagicMock()

        # Act
        self.client.connect_socket(on_price_update=callback)

        # Assert
        self.client.sio.on.assert_called_with('rate-update', callback)
        self.client.sio.connect.assert_called_with(
            'https://platform.tradem.online',
            socketio_path='/ui/api/connect/socket',
            transports=['websocket'],
            headers={'Cookie': 'connect.sid=s%3A123; other=val'}
        )

    def test_connect_socket_no_callback(self):
        # Act
        self.client.connect_socket()

        # Assert
        self.client.sio.on.assert_not_called()
        self.client.sio.connect.assert_called()

    def test_connect_socket_failure(self):
        # Arrange
        self.client.sio.connect.side_effect = Exception("Connection failed")

        # Act & Assert
        with self.assertRaisesRegex(Exception, "Connection failed"):
            self.client.connect_socket()

if __name__ == '__main__':
    unittest.main()
