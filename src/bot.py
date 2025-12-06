import os
import logging
from collections import deque
from typing import Optional
from dotenv import load_dotenv
from tradem_client import Client
from models import Rates, Strategy

logger = logging.getLogger(__name__)

def setup_logging():
    def _configure_logger(name, level, fmt):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.propagate = False

    _configure_logger('tradem_client', logging.INFO, '[Client] %(asctime)s - %(levelname)s - %(message)s')
    _configure_logger(__name__, logging.INFO, '[Bot] %(asctime)s - %(name)s - %(levelname)s - %(message)s')

class MovingAverageStrategy(Strategy):
    def __init__(self, client: Client, symbol: str, window_size: int, initial_balances: dict = None):
        self.client = client
        self.symbol = symbol.lower()
        self.window_size = window_size
        self.prices = deque()
        self.running_sum = 0.0
        self.current_sma: Optional[float] = None
        self.position: Optional[str] = None
        
        self.balances = initial_balances or {}
        logger.info(f"Strategy initialized for {self.symbol} with SMA window {self.window_size}")
        if self.balances:
            logger.info(f"[{self.symbol.upper()}] Budget Cap enabled with balances: {self.balances}")
            self._log_status()

    def _log_status(self):
        """Logs the current budget status."""
        logger.info(f"[{self.symbol.upper()}] BUDGET STATUS: {self.balances}")

    def _execute_buy(self, quantity: float, price: float):
        """
        Executes a real buy order if budget permits.
        """
        cost = quantity * price
        
        if self.balances.get('USD', 0) < cost:
            logger.warning(f"[{self.symbol.upper()}] Insufficient BUDGET for BUY. Needed: {cost:.2f}, Have: {self.balances.get('USD', 0):.2f}")
            return False

        logger.info(f"\033[92m[{self.symbol.upper()}] BUDGET APPROVED: Executing buy for {quantity} {self.symbol} @ {price:.2f}...\033[0m")
        
        currency = self.symbol.split('-')[0].upper()

        try:
             self.client.buy(currency, quantity)
        except Exception as e:
             logger.error(f"[{self.symbol.upper()}] Buy failed: {e}")
             return False
        
        self.balances['USD'] = self.balances.get('USD', 0) - cost
        self.balances[currency] = self.balances.get(currency, 0) + quantity
        self._log_status()
        return True

    def _execute_sell(self, quantity: float, price: float):
        """
        Executes a real sell order if budget permits.
        """
        
        currency = self.symbol.split('-')[0].upper()
        
        if self.balances.get(currency, 0) < quantity:
           logger.warning(f"[{self.symbol.upper()}] Insufficient BUDGET for SELL. Needed: {quantity} {currency}, Have: {self.balances.get(currency, 0)}")
           return False

        logger.info(f"\033[91m[{self.symbol.upper()}] BUDGET APPROVED: Executing sell for {quantity} {self.symbol} @ {price:.2f}...\033[0m")

        try:
            self.client.sell(currency, quantity)
        except Exception as e:
            logger.error(f"[{self.symbol.upper()}] Sell failed: {e}")
            return False

        revenue = quantity * price
        self.balances[currency] = self.balances.get(currency, 0) - quantity
        self.balances['USD'] = self.balances.get('USD', 0) + revenue
        self._log_status()

        return True

    def update_price(self, price: float):
        """
        Updates the price history and recalculates the SMA using an optimized incremental approach.
        """

        if len(self.prices) == self.window_size:
            oldest_price = self.prices.popleft()
            self.running_sum -= oldest_price

        self.prices.append(price)
        self.running_sum += price

        if len(self.prices) == self.window_size:
            self.current_sma = self.running_sum / self.window_size

    def execute_strategy(self, current_price: float):
        """Executes a simple crossover strategy."""
        if self.current_sma is None:
            return

        if hasattr(self, "prev_price") and hasattr(self, "prev_sma"):
            crossed_up = self.prev_price <= self.prev_sma and current_price > self.current_sma
            crossed_down = self.prev_price >= self.prev_sma and current_price < self.current_sma

            if crossed_up and self.position != "long":
                quantity = 0.1
                if self._execute_buy(quantity, current_price):
                    self.position = "long"

            elif crossed_down and self.position == "long":
                quantity = 0.1
                if self._execute_sell(quantity, current_price):
                    self.position = "flat"

        self.prev_price = current_price
        self.prev_sma = self.current_sma


    def on_price_update(self, data):
        """
        Callback for WebSocket updates.
        """

        rates = Rates.from_dict(data)
        
        if self.symbol in rates:
            try:
                price = float(rates[self.symbol])
                self.update_price(price)
                self.execute_strategy(price)
            except ValueError:
                logger.error(f"[{self.symbol.upper()}] Could not parse price for {self.symbol}: {rates[self.symbol]}")

def main():
    setup_logging()
    load_dotenv()
    
    client = Client(
        email=os.getenv('EMAIL'),
        password=os.getenv('PASSWORD'),
        verify_ssl='../server_certificate.pem'
    )
    
    try:
        client.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize client: {e}")
        return

    btc_strategy = MovingAverageStrategy(client, symbol='btc-usd', window_size=200, initial_balances={'USD': 50000, 'BTC': 0.5})
    eth_strategy = MovingAverageStrategy(client, symbol='eth-usd', window_size=200, initial_balances={'USD': 50000, 'ETH': 5})

    client.add_price_listener(btc_strategy.on_price_update)
    client.add_price_listener(eth_strategy.on_price_update)

    try:
        client.connect_socket()
        client.sio.wait()
    except KeyboardInterrupt:
        client.sio.disconnect()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
