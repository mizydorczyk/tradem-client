# tradem-client

Python client for the Tradem platform API.

Has been adapted from https://github.com/The-Brawl/the-brawl-client-api by Mateusz Bajorek.

## Project Structure

- `src/`: Source code
    - `tradem_client.py`: Main client class
    - `models.py`: Data models
    - `example.py`: Example usage script
- `requirements.txt`: Python dependencies
- `server_certificate.pem`: SSL certificate bundle

## Configuration

1.  Create a `.env` file in the root directory with your credentials:

```env
EMAIL=your_email@example.com
PASSWORD=your_password
```

## Getting started

1.  Clone the repository.

2.  Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
3.  Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the example from the `src` directory:

```bash
cd src
python3 example.py
```

## Testing

```bash
PYTHONPATH=src python3 -m unittest discover tests
```

## Examples

### Initalize client
```python
import os
from dotenv import load_dotenv
from tradem_client import Client

load_dotenv()

client = Client(
    email=os.getenv('EMAIL'),
    password=os.getenv('PASSWORD'),
    verify_ssl='../server_certificate.pem'
)
client.initialize()
```

### Get wallets
```python

# ...

try:
    wallets = client.get_wallets()
    if wallets:
        print(f"\n{'ID':<40} {'Currency':<10} {'Type':<10} {'Balance':<20}")
        print("-" * 80)
        for wallet in wallets:
            print(f"{wallet.id:<40} {wallet.currency_id.upper():<10} {wallet.currency.type:<10} {wallet.balance:<20}")
except Exception as e:
    print(f"Wallets fetch failed: {e}")
```

### Buy/sell
```python

# ...

try:
    buy_response = client.buy('BTC', 0.0001)
    print(f"Buy successful: {buy_response}")

    sell_response = client.sell('BTC', 0.0001)
    print(f"Sell successful: {sell_response}")
except Exception as e:
    print(f"Transaction failed: {e}")
```

### Live rates
```python
from models import Rates

# ...

def on_price_update(data):
    rates = Rates.from_dict(data)

    target_pairs = ['btc-usd', 'eth-usd']
    formatted = []
    
    for pair in target_pairs:
        if pair in rates:
             formatted.append(f"{pair.upper()}: {rates[pair]}")
    
    if formatted:
        print(f"Rates: {', '.join(formatted)}")

try:
    client.connect_socket(on_price_update=on_price_update)
    client.sio.wait()
except KeyboardInterrupt:
    client.sio.disconnect()
except Exception as e:
    print(f"WebSocket error: {e}")
```
