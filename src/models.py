from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Currency:
    id: str
    type: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get('id'),
            type=data.get('type')
        )

@dataclass
class Wallet:
    id: str
    balance: str
    currency_id: str
    currency: Currency

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get('id'),
            balance=data.get('balance'),
            currency_id=data.get('currencyId'),
            currency=Currency.from_dict(data.get('currency', {}))
        )

@dataclass
class Account:
    id: str
    name: str
    type: str
    wallets: List[Wallet]

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            type=data.get('type'),
            wallets=[Wallet.from_dict(w) for w in data.get('wallets', [])]
        )

@dataclass
class User:
    id: str
    name: str
    accounts: List[Account]

    @classmethod
    def from_dict(cls, data: dict):
        user_data = data.get('user', {})
        return cls(
            id=user_data.get('id'),
            name=user_data.get('name'),
            accounts=[Account.from_dict(a) for a in user_data.get('accounts', [])]
        )

class Strategy:
    """Base class for trading strategies."""
    
    def on_price_update(self, data):
        raise NotImplementedError
