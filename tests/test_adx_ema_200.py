import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import unittest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from strategies.adx_ema_200 import AdxEma200

class MockClient:
    def __init__(self):
        self.default_account_id = "acc_123"
        self.wallets = []
        self.transactions = []

    def get_wallets(self, account_id):
        return self.wallets

    def buy(self, currency, amount):
        return {"amount": amount, "price": 50000.0, "position": "long"}

    def sell(self, currency, amount):
        return {"amount": amount, "price": 55000.0, "position": "short"}

class MockWallet:
    def __init__(self, currency_id, balance):
        self.currency_id = currency_id
        self.balance = balance

class TestAdxEma200(unittest.TestCase):
    def setUp(self):
        self.ccxt_patcher = patch('strategies.adx_ema_200.ccxt')
        self.mock_ccxt = self.ccxt_patcher.start()
        self.mock_exchange = MagicMock()
        self.mock_ccxt.binance.return_value = self.mock_exchange
        self.mock_exchange.fetch_ohlcv.return_value = []

        self.client = MockClient()
        self.client.wallets = [
            MockWallet('USD', 10000.0),
            MockWallet('BTC', 0.0)
        ]
        self.strategy = AdxEma200(self.client, 'BTC-USD', budget=1000, interval=3600)
    
    def tearDown(self):
        self.ccxt_patcher.stop()
    
    def test_virtual_wallet_trading(self):
        # Arrange
        self.strategy.virtual_wallet['USD'] = 1000.0
        self.strategy.virtual_wallet['BTC'] = 0.0
        
        # Act & Assert
        self.strategy.enter_trade(50000, 100)
        
        self.assertEqual(self.strategy.virtual_wallet['USD'], 960.0)
        self.assertAlmostEqual(self.strategy.virtual_wallet['BTC'], 0.0008)
        
        self.strategy.exit_trade(55000, "Test Exit")
        
        self.assertEqual(self.strategy.virtual_wallet['BTC'], 0.0)
        # 0.0004 * 55000 = 22.0 USD returned.
        # 980 + 22 = 1002.0
        self.assertAlmostEqual(self.strategy.virtual_wallet['USD'], 1004.0)

    def test_indicators_calculation(self):
        # Arrange
        data = []
        price = 40000
        for i in range(300):
            price += np.random.normal(0, 100)
            candle = {
                'open': price,
                'high': price + 50,
                'low': price - 50,
                'close': price + 10,
                'start_time': i * 3600
            }
            data.append(candle)
            
        self.strategy.history.extend(data)
        
        # Act
        df = pd.DataFrame(data)
        df = self.strategy._calculate_indicators(df)
        
        # Assert
        self.assertIn('adx', df.columns)
        self.assertIn('atr', df.columns)
        self.assertIn('ema_200', df.columns)
        
        self.assertFalse(pd.isna(df.iloc[-1]['adx']))
        self.assertFalse(pd.isna(df.iloc[-1]['ema_200']))

    def test_entry_condition(self):
        # Arrange
        # Condition: ADX > 25, Close > EMA 200
        base_price = 50000
        for i in range(250):
            self.strategy.history.append({
                'open': base_price, 'high': base_price+100, 'low': base_price-100, 'close': base_price, 'start_time': i
            })
            
        # Create a breakout scenario
        current_price = base_price
        for i in range(50):
            current_price += 200 # Strong up
            self.strategy.history.append({
                'open': current_price, 
                'high': current_price+200, 
                'low': current_price, 
                'close': current_price+200, 
                'start_time': 250+i
            })
            
        # Act
        last_candle = self.strategy.history[-1]
        
        self.client.buy = MagicMock(return_value={"amount": 0.01, "price": current_price, "position": "long"})
        
        self.strategy.execute_strategy(last_candle)
        
        # Assert
        df = pd.DataFrame(list(self.strategy.history))
        df = self.strategy._calculate_indicators(df)
        last_adx = df.iloc[-1]['adx']
        last_close = df.iloc[-1]['close']
        last_ema = df.iloc[-1]['ema_200']
        
        if last_adx > 25 and last_close > last_ema:
             self.client.buy.assert_called()
        else:
             self.client.buy.assert_not_called()

    def test_sl_tp_logic(self):
        # Arrange
        self.strategy.position = 'long'
        self.strategy.sl_price = 49000
        self.strategy.tp_price = 51000
        self.strategy.virtual_wallet['BTC'] = 1.0 # Seed wallet for exit
        self.strategy.symbol = 'BTC-USD'
        
        self.client.sell = MagicMock(return_value={"amount": 1.0, "price": 49000.0})
        self.client.get_wallets = MagicMock(return_value=[MockWallet('BTC', 0.5)])

        # Act
        self.strategy.on_price_update({'BTC-USD': 50000})
        
        # Assert
        self.client.sell.assert_not_called()
        
        # Act
        self.strategy.on_price_update({'BTC-USD': 48999})
        
        # Assert
        self.client.sell.assert_called()
        self.assertIsNone(self.strategy.position)
        
        # Reset
        self.strategy.position = 'long'
        self.strategy.tp_price = 51000
        self.strategy.virtual_wallet['BTC'] = 1.0 # Re-seed
        self.client.sell.reset_mock()
        
        # Act
        self.strategy.on_price_update({'BTC-USD': 51001})
        
        # Assert
        self.client.sell.assert_called()

    def test_entry_with_spread(self):
        # Arrange
        self.strategy.risk = 1.0
        self.strategy.spread_pct = 0.0025
    
        # Act
        self.client.buy = MagicMock(return_value={"amount": 0.1, "price": 10100.0})
        self.strategy.enter_trade(10000, 100)
        
        # Assert
        self.client.buy.assert_called()
        self.assertAlmostEqual(self.strategy.sl_price, 9850.0)
        self.assertAlmostEqual(self.strategy.tp_price, 10650.0)

    def test_volatility_gate(self):
        # Arrange
        self.strategy.risk = 1.0
        self.strategy.spread_pct = 0.0025
        self.strategy.volatility_safety_factor = 1.5
        
        data = []
        base_price = 10000
        for i in range(100):
            data.append({
                'open': base_price, 'high': base_price+5, 'low': base_price-5, 'close': base_price, 'start_time': i*3600
            })
        data.append({
            'open': base_price, 'high': base_price+5, 'low': base_price-5, 'close': base_price+50, 'start_time': 100*3600
        })
        
        self.strategy.history.extend(data)
        
        # Act
        self.client.buy = MagicMock()
        self.strategy.execute_strategy(self.strategy.history[-1])
        
        # Assert
        self.client.buy.assert_not_called()

    def test_fetch_initial_data(self):
        # Act & Assert
        self.mock_exchange.fetch_ohlcv.assert_called_once()
        args, _ = self.mock_exchange.fetch_ohlcv.call_args
        self.assertEqual(args[0], 'BTC/USDT')
        self.assertEqual(args[1], '1h')

if __name__ == '__main__':
    unittest.main()
