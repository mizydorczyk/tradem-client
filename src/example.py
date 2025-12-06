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

# Get wallets
try:
    wallets = client.get_wallets()
    if wallets:
        print(f"\n{'ID':<40} {'Currency':<10} {'Type':<10} {'Balance':<20}")
        print("-" * 80)
        for wallet in wallets:
            print(f"{wallet.id:<40} {wallet.currency_id.upper():<10} {wallet.currency.type:<10} {wallet.balance:<20}")
except Exception as e:
    print(f"Wallets fetch failed: {e}")
