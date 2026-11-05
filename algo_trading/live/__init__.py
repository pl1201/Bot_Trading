"""Live trading module"""
from .okx_client import OKXClient
from .exchange_base import ExchangeClient
from .universal_bot import BotConfig
from .binance_sma_bot import main
from typing import Literal

market_type: Literal["spot", "swap"] = "swap"

__all__ = ['OKXClient', 'ExchangeClient', 'BotConfig', 'main']

