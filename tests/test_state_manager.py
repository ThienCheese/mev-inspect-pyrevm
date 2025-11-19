import pytest

from mev_inspect.state_manager import StateManager


class MockRPC:
    def __init__(self):
        self.calls = {
            "get_balance": 0,
            "get_code": 0,
            "get_storage_at": 0,
        }

    def get_balance(self, address, block_number):
        self.calls["get_balance"] += 1
        return 1000

    def get_code(self, address):
        self.calls["get_code"] += 1
        # return bytes-like object
        return b"\x60\x60\x60"

    def get_storage_at(self, address, position, block_number):
        self.calls["get_storage_at"] += 1
        return b"\x00" * 32


def test_get_account_and_caching():
    rpc = MockRPC()
    sm = StateManager(rpc, block_number=12345, account_cache_size=2)

    a1 = sm.get_account("0xabc")
    assert a1["balance"] == 1000
    assert a1["code"] == b"\x60\x60\x60"

    # second read should be from cache
    a2 = sm.get_account("0xabc")
    assert rpc.calls["get_balance"] == 1
    assert rpc.calls["get_code"] == 1

    # different address triggers new RPC calls
    sm.get_account("0xdef")
    assert rpc.calls["get_balance"] == 2

    # cache size is 2, adding third address will evict oldest
    sm.get_account("0x111")
    assert len(sm.account_cache) == 2


def test_storage_caching():
    rpc = MockRPC()
    sm = StateManager(rpc, block_number=54321, storage_cache_size=5)

    v1 = sm.get_storage("0xaaa", 0)
    assert isinstance(v1, (bytes, bytearray))
    v2 = sm.get_storage("0xaaa", 0)
    assert rpc.calls["get_storage_at"] == 1


if __name__ == "__main__":
    pytest.main(["-q", "tests/test_state_manager.py"])
