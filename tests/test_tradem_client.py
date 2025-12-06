import unittest
from unittest.mock import patch, MagicMock
from tradem_client import Client
from models import User, Account, Wallet

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
        with self.assertRaisesRegex(ValueError, "Default account is not set"):
            self.client.get_wallets()

if __name__ == '__main__':
    unittest.main()
