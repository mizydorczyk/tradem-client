import time
import logging
import pandas as pd
import numpy as np
from collections import deque
import ccxt
from tradem_client import Client
from models import Strategy

logger = logging.getLogger(__name__)

class AdxEma200(Strategy):
    def __init__(self, client: Client, symbol: str, budget: float, interval: int = 3600):
        self.client = client
        self.symbol = symbol.lower()
        self.interval = interval
        self.candle = {'open': None, 'high': None, 'low': None, 'close': None, 'start_time': None}
        self.last_candle_time = 0
        
        self.base_currency = self.symbol.split('-')[0].upper()
        self.quote_currency = self.symbol.split('-')[1].upper()
        self.virtual_wallet = {
            self.quote_currency: budget,
            self.base_currency: 0.0
        }
        self.risk = 0.04
        self.spread_pct = 0.0025
        self.volatility_safety_factor = 1.1
        self.adx_level = 25
        self.ema_length = 200
        self.atr_sl_mult = 1.5
        self.atr_tp_mult = 5.5
        
        self.history = deque(maxlen=500)
        self.position = None
        self.sl_price = 0.0
        self.tp_price = 0.0

        self._fetch_initial_data()

    def _get_ccxt_timeframe(self, interval_seconds):
        mapping = {
            60: '1m', 300: '5m', 900: '15m', 1800: '30m',
            3600: '1h', 14400: '4h', 86400: '1d'
        }
        return mapping.get(interval_seconds, '1h')

    def _fetch_initial_data(self):
        try:
            logger.info(f"[{self.symbol.upper()}] Fetching historical data to prevent warmup...")
            exchange = ccxt.binance()
            
            base = self.base_currency
            quote = 'USDT' if self.quote_currency == 'USD' else self.quote_currency
            symbol = f"{base}/{quote}"
            
            timeframe = self._get_ccxt_timeframe(self.interval)
            limit = self.ema_length + 50
            
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            for candle in ohlcv:
                ts_sec = candle[0] / 1000.0
                c = {
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'start_time': ts_sec
                }
                self.history.append(c)
                
            logger.info(f"[{self.symbol.upper()}] Fetched {len(self.history)} candles. Warmup complete.")

        except Exception as e:
            logger.warning(f"[{self.symbol.upper()}] Failed to fetch historical data: {e}. Warmup will be slow.")

    def _calculate_rma(self, series, length):
        return series.ewm(alpha=1/length, adjust=False).mean()

    def _calculate_atr(self, df, length=14):
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = self._calculate_rma(tr, length)
        return atr

    def _calculate_adx(self, df, length=14):
        high = df['high']
        low = df['low']
        
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        plus_dm = pd.Series(plus_dm, index=df.index)
        minus_dm = pd.Series(minus_dm, index=df.index)
        
        atr = self._calculate_atr(df, length)
        
        plus_di = 100 * self._calculate_rma(plus_dm, length) / atr
        minus_di = 100 * self._calculate_rma(minus_dm, length) / atr
        
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = self._calculate_rma(dx, length)

        return adx

    def _calculate_indicators(self, df):
        df['ema_200'] = df['close'].ewm(span=self.ema_length, adjust=False).mean()
        df['adx'] = self._calculate_adx(df)
        df['atr'] = self._calculate_atr(df)

        return df

    def execute_strategy(self, candle: dict):
        logger.info(f"[{self.symbol.upper()}] New candle closed: {candle['close']}")
        
        self.history.append(candle)
        
        if len(self.history) < self.ema_length + 20: 
            logger.info(f"[{self.symbol.upper()}] Gathering data: {len(self.history)}/{self.ema_length + 20}")
            return

        df = pd.DataFrame(list(self.history))
        df = self._calculate_indicators(df)
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        adx = last_row['adx']
        close = last_row['close']
        ema = last_row['ema_200']
        atr = last_row['atr']
        
        logger.info(f"[{self.symbol.upper()}] ADX: {adx:.2f}, EMA: {ema:.2f}, Close: {close:.2f}")

        spread_cost = close * self.spread_pct
        min_required_volatility = spread_cost * self.volatility_safety_factor
        current_volatility = atr * self.atr_sl_mult
        
        if current_volatility < min_required_volatility:
            logger.info(f"[{self.symbol.upper()}] Volatility too low. ATR dist: {current_volatility:.2f} < Min: {min_required_volatility:.2f}")
            return

        if self.position is None:
            if adx > self.adx_level and close > ema:
                logger.info(f"[{self.symbol.upper()}] Entry signal detected.")
                self.enter_trade(close, atr)

    def enter_trade(self, price, atr):
        try:
            available_usd = self.virtual_wallet[self.quote_currency]
            trade_amount_usd = available_usd * self.risk

            amount_in_tokens = trade_amount_usd / price
            result = self.client.buy(self.base_currency, amount_in_tokens)
            exec_price = result['price']
            exec_amount = result['amount']
            
            cost_usd = exec_amount * exec_price
            self.virtual_wallet[self.quote_currency] -= cost_usd
            self.virtual_wallet[self.base_currency] += exec_amount
            
            self.position = 'long'
            self.sl_price = price - (atr * self.atr_sl_mult)
            self.tp_price = exec_price + (atr * self.atr_tp_mult)
            
            logger.info(f"[{self.symbol.upper()}] Bought {exec_amount} @ {exec_price}. SL: {self.sl_price:.2f}, TP: {self.tp_price:.2f}. Virtual Wallet: {self.virtual_wallet}")

        except Exception as e:
            logger.error(f"[{self.symbol.upper()}] Buy failed: {e}")

    def exit_trade(self, price, reason):
        try:
            logger.info(f"[{self.symbol.upper()}] Exiting trade ({reason}) @ {price}")
            
            available_asset = self.virtual_wallet[self.base_currency]
            
            if available_asset > 0:
                result = self.client.sell(self.base_currency, available_asset)
                exec_price = result['price']
                exec_amount = result['amount']
                
                usd_value = exec_amount * exec_price
                self.virtual_wallet[self.base_currency] -= exec_amount
                self.virtual_wallet[self.quote_currency] += usd_value

                logger.info(f"[{self.symbol.upper()}] Sold {exec_amount} @ {exec_price}. Virtual Wallet: {self.virtual_wallet}")
                
                self.position = None
                self.sl_price = 0
                self.tp_price = 0
            else:
                logger.warning(f"[{self.symbol.upper()}] No virtual asset found to sell")
                self.position = None

        except Exception as e:
            logger.error(f"[{self.symbol.upper()}] Sell failed: {e}")

    def on_price_update(self, rates: dict):
        if self.symbol not in rates:
            return

        try:
            price = float(rates[self.symbol])
            now = time.time()
            
            if self.position == 'long':
                if price <= self.sl_price:
                    self.exit_trade(price, "SL Hit")
                elif price >= self.tp_price:
                    self.exit_trade(price, "TP Hit")

            if self.candle['open'] is None:
                self.candle['open'] = price
                self.candle['high'] = price
                self.candle['low'] = price
                self.candle['close'] = price
                self.candle['start_time'] = now 
                self.last_candle_time = now

            self.candle['high'] = max(self.candle['high'], price)
            self.candle['low'] = min(self.candle['low'], price)
            self.candle['close'] = price

            if self.candle['start_time'] and (now - self.candle['start_time'] >= self.interval):
                self.execute_strategy(self.candle.copy())
                
                self.candle = {
                    'open': price,
                    'high': price, 
                    'low': price, 
                    'close': price,
                    'start_time': now
                }
                
        except ValueError:
            logger.error(f"[{self.symbol.upper()}] Could not parse price for {self.symbol}: {rates[self.symbol]}")
