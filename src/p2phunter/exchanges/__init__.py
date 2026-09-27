from .base import ExchangeAdapter, ExchangeError
from .bitget import BitgetAdapter
from .bybit import BybitAdapter
from .mexc import MexcAdapter

ADAPTERS: dict[str, type[ExchangeAdapter]] = {
    "bybit": BybitAdapter,
    "mexc": MexcAdapter,
    "bitget": BitgetAdapter,
}

__all__ = ["ADAPTERS", "ExchangeAdapter", "ExchangeError"]
