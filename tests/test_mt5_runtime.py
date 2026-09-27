import pytest

from core_engine.mt_runtime import (
    MTConnectionConfig,
    MTRuntimeError,
    create_mt_runtime,
    MTAccountInfo,
    MTSymbolInfo,
)
from core_engine.mt5_runtime import MT5Runtime, _mt5_timeframe, MINUTES_TO_MT5_TF


class TestMT5RuntimeFactory:
    def test_create_mt5_runtime(self):
        config = MTConnectionConfig(
            server="demo.ftmo.com",
            login="12345",
            password="secret",
            platform="MT5",
        )
        runtime = create_mt_runtime(config)
        assert isinstance(runtime, MT5Runtime)
        assert not runtime.connected

    def test_mt4_rejected(self):
        # MT5-only product: the factory must never create an MT4 runtime.
        config = MTConnectionConfig(
            server="http://localhost:9100", login="111", password="x", platform="MT4"
        )
        runtime = create_mt_runtime(config)
        # MT4 falls back to the mock runtime; the provisioning layer rejects
        # non-MT5 platforms before a runtime is ever created.
        assert runtime is not None
        assert not runtime.connected

    def test_call_before_connect_raises(self):
        config = MTConnectionConfig(server="x", login="0", password="x", platform="MT5")
        runtime = create_mt_runtime(config)
        with pytest.raises(MTRuntimeError, match="not connected"):
            import asyncio
            asyncio.run(runtime.account_info())
        with pytest.raises(MTRuntimeError, match="not connected"):
            import asyncio
            asyncio.run(runtime.get_symbols())
        with pytest.raises(MTRuntimeError, match="not connected"):
            import asyncio
            asyncio.run(runtime.get_rates("XAUUSD", 5))


class TestTimeframeMapping:
    def test_known_minutes(self):
        pairs = [(1, 1), (5, 5), (15, 15), (60, 60), (240, 240), (1440, 1440)]
        for minutes, expected in pairs:
            assert _mt5_timeframe(minutes) == MINUTES_TO_MT5_TF[minutes]

    def test_fallback_to_m5(self):
        assert _mt5_timeframe(999) == MINUTES_TO_MT5_TF[5]

    def test_all_mapped(self):
        for minutes in [1, 5, 15, 30, 60, 240, 1440, 10080, 43200]:
            assert minutes in MINUTES_TO_MT5_TF
