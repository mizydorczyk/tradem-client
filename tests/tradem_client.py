import unittest
from unittest.mock import patch, MagicMock
from tradem_client import Client

class TestClient(unittest.TestCase):
    def setUp(self):
        self.email = "test@example.com"
        self.password = "password123"
        self.api_key = "test_api_key"

    @patch('requests.post')
    def test_authenticate_success(self, mock_post):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'idToken': 'fake_id_token'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act
        client = Client(self.email, self.password, self.api_key)

        # Assert
        self.assertEqual(client.api_token, 'fake_id_token')
        mock_post.assert_called_with(
            Client.AUTH_URL,
            json={
                "email": self.email,
                "password": self.password,
                "returnSecureToken": True,
            },
            params={'key': self.api_key}
        )

    @patch('requests.post')
    def test_create_transaction_success(self, mock_post):
        # Arrange
        with patch.object(Client, 'authenticate') as mock_auth:
            client = Client(self.email, self.password, self.api_key)
            client.api_token = 'fake_id_token'
            mock_response = MagicMock()
            mock_response.json.return_value = {'data': 'transaction_data'}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            # Act
            result = client.create_transaction(
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
        with patch.object(Client, 'authenticate') as mock_auth:
            client = Client(self.email, self.password, self.api_key)
            client.api_token = 'fake_id_token'
            mock_response = MagicMock()
            mock_response.json.return_value = [{'valuation': 'data'}]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            # Act
            result = client.get_wallet_valuation(
                account_id='acc_123',
                wallet_id='wallet_456',
                limit=5
            )

            # Assert
            self.assertEqual(result, [{'valuation': 'data'}])
            mock_get.assert_called_with(
                f'{Client.BASE_API_URL}/account/acc_123/wallet/wallet_456/valuation',
                headers={'Authorization': 'Bearer fake_id_token'},
                params={'limit': 5},
                verify=False
            )

if __name__ == '__main__':
    unittest.main()
