from p2phunter.config import build_alias_map, load_config


def test_example_config_loads():
    cfg = load_config("config/config.example.yaml")
    assert set(cfg.exchanges) == {"bybit", "mexc", "bitget"}
    aliases = build_alias_map(cfg.network_aliases)
    assert aliases["TRX"] == "TRC20"
    assert aliases["BEP20(BSC)"] == "BEP20"
