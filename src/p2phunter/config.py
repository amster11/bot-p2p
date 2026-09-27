"""Загрузка конфига (config/config.yaml) и секретов (переменные окружения / .env)."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ScanCfg(BaseModel):
    interval_sec: int = 45
    stale_after_sec: int = 120


class WorkCfg(BaseModel):
    fiat: str = "RUB"
    assets: list[str] = ["USDT"]
    amount_fiat: Decimal = Decimal(100000)
    min_profit_pct: Decimal = Decimal("1.5")
    spot_symbols: list[str] = []


class FiltersCfg(BaseModel):
    min_seller_orders: int = 50
    min_seller_completion: Decimal = Decimal("0.9")
    max_price_deviation_pct: Decimal = Decimal(5)


class ExchangeCfg(BaseModel):
    enabled: bool = True
    p2p_fee_pct: Decimal = Decimal(0)
    spot_taker_fee_pct: Decimal = Decimal("0.1")
    payment_methods: dict[str, str] = {}


class Config(BaseModel):
    scan: ScanCfg = ScanCfg()
    work: WorkCfg = WorkCfg()
    filters: FiltersCfg = FiltersCfg()
    exchanges: dict[str, ExchangeCfg] = {}
    network_aliases: dict[str, list[str]] = Field(default_factory=dict)


class Secrets(BaseModel):
    bot_token: str = ""
    admin_ids: list[int] = []
    api_keys: dict[str, dict[str, str]] = {}  # биржа -> {key, secret, passphrase}
    ai_api_key: str = ""


def load_dotenv(path: Path) -> None:
    """Минимальный разбор .env без внешних зависимостей. Уже заданные переменные не трогает."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_config(path: Path | str = "config/config.yaml") -> Config:
    path = Path(path)
    if not path.exists():
        path = Path("config/config.example.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Config.model_validate(data)


def load_secrets(env_path: Path | str = ".env") -> Secrets:
    load_dotenv(Path(env_path))
    env = os.environ
    keys = {}
    for name in ("bybit", "mexc", "bitget"):
        up = name.upper()
        keys[name] = {
            "key": env.get(f"{up}_API_KEY", ""),
            "secret": env.get(f"{up}_API_SECRET", ""),
            "passphrase": env.get(f"{up}_API_PASSPHRASE", ""),
        }
    admins = [int(x) for x in env.get("ADMIN_IDS", "").replace(" ", "").split(",") if x]
    return Secrets(
        bot_token=env.get("BOT_TOKEN", ""),
        admin_ids=admins,
        api_keys=keys,
        ai_api_key=env.get("AI_API_KEY", ""),
    )


def build_alias_map(aliases: dict[str, list[str]]) -> dict[str, str]:
    """{"TRX": "TRC20", "TRC20": "TRC20", ...} — сравнение без учёта регистра."""
    out: dict[str, str] = {}
    for canon, names in aliases.items():
        out[canon.upper()] = canon
        for n in names:
            out[str(n).upper()] = canon
    return out
