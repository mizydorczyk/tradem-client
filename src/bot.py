import os
import time
import logging
from collections import deque
from typing import Optional
from dotenv import load_dotenv
from tradem_client import Client
from models import Strategy
from strategies.adx_ema_200 import AdxEma200

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
    _configure_logger(__name__, logging.INFO, '[Bot] %(asctime)s - %(levelname)s - %(message)s')
    _configure_logger('strategies.adx_ema_200', logging.INFO, '[AdxEma200] %(asctime)s - %(levelname)s - %(message)s')


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

    btc_strategy = AdxEma200(client, symbol='BTC-USD', budget=10000, interval=3600)
    eth_strategy = AdxEma200(client, symbol='ETH-USD', budget=10000, interval=3600)

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
