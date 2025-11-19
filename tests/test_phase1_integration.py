"""Integration test for Phase 1: StateManager and caching optimization.

This test validates that:
1. StateManager is properly integrated into StateSimulator
2. Caching reduces RPC calls significantly
3. Preloading optimization works correctly
4. Cache statistics are tracked accurately
"""
from mev_inspect.inspector import MEVInspector
from mev_inspect.simulator import StateSimulator
from mev_inspect.state_manager import StateManager


class MockRPCWithStats:
    """Mock RPC client that tracks call counts for validation."""
    
    def __init__(self):
        self.calls = {
            "get_block": 0,
            "get_transaction": 0,
            "get_transaction_receipt": 0,
            "get_code": 0,
            "get_balance": 0,
            "get_storage_at": 0,
            "call": 0,
        }
        
    def get_block(self, block_number, full_transactions=True):
        self.calls["get_block"] += 1
        return {
            "number": block_number,
            "hash": "0x1234",
            "miner": "0xminer",
            "timestamp": 1234567890,
            "gasLimit": 30000000,
            "baseFeePerGas": 50,
            "mixHash": b"\x00" * 32,
            "transactions": [
                {
                    "hash": "0xabc123",
                    "from": "0xfrom1",
                    "to": "0xto1",
                    "value": 1000,
                    "input": "0x12345678",
                    "gasPrice": 100,
                },
                {
                    "hash": "0xdef456",
                    "from": "0xfrom2",
                    "to": "0xto2",
                    "value": 2000,
                    "input": "0xabcdef00",
                    "gasPrice": 120,
                },
            ],
        }
    
    def get_transaction(self, tx_hash):
        self.calls["get_transaction"] += 1
        return {
            "hash": tx_hash,
            "from": "0xfrom",
            "to": "0xto",
            "value": 1000,
            "input": "0x12345678",
        }
    
    def get_transaction_receipt(self, tx_hash):
        self.calls["get_transaction_receipt"] += 1
        return {
            "transactionHash": tx_hash,
            "status": 1,
            "gasUsed": 21000,
            "logs": [],
        }
    
    def get_code(self, address):
        self.calls["get_code"] += 1
        return b"\x60\x60\x60"
    
    def get_balance(self, address, block_number):
        self.calls["get_balance"] += 1
        return 1000000
    
    def get_storage_at(self, address, position, block_number):
        self.calls["get_storage_at"] += 1
        return b"\x00" * 32
    
    def call(self, to, data, block_number, from_address=None, value=0):
        self.calls["call"] += 1
        return b"\x00" * 32


def test_state_manager_integration():
    """Test StateManager is properly integrated into StateSimulator."""
    rpc = MockRPCWithStats()
    simulator = StateSimulator(rpc, block_number=12345)
    
    # Verify StateManager was initialized
    assert simulator.state_manager is not None
    assert simulator.state_manager.block_number == 12345
    
    print("[PASS] StateManager integration")


def test_caching_reduces_rpc_calls():
    """Test that caching significantly reduces duplicate RPC calls."""
    rpc = MockRPCWithStats()
    sm = StateManager(rpc, block_number=12345)
    
    # First access - should hit RPC
    code1 = sm.get_code("0xcontract1")
    assert rpc.calls["get_code"] == 1
    
    # Second access to same address - should use cache
    code2 = sm.get_code("0xcontract1")
    assert rpc.calls["get_code"] == 1  # Still 1, not 2
    assert code1 == code2
    
    # Storage test
    slot1 = sm.get_storage("0xcontract1", 0)
    assert rpc.calls["get_storage_at"] == 1
    
    slot2 = sm.get_storage("0xcontract1", 0)
    assert rpc.calls["get_storage_at"] == 1  # Cached
    
    # Different slot should trigger new RPC
    slot3 = sm.get_storage("0xcontract1", 1)
    assert rpc.calls["get_storage_at"] == 2
    
    print("[PASS] Caching reduces RPC calls")


def test_preloading_optimization():
    """Test that preload_addresses efficiently loads multiple addresses."""
    rpc = MockRPCWithStats()
    sm = StateManager(rpc, block_number=12345)
    
    addresses = ["0xaddr1", "0xaddr2", "0xaddr3"]
    
    # Preload all addresses
    sm.preload_addresses(addresses)
    
    # Should have called get_balance and get_code for each address
    assert rpc.calls["get_balance"] == 3
    assert rpc.calls["get_code"] == 6  # 3 in get_account + 3 separate get_code
    
    # Now accessing these addresses should use cache
    initial_balance_calls = rpc.calls["get_balance"]
    initial_code_calls = rpc.calls["get_code"]
    
    for addr in addresses:
        sm.get_account(addr)
        sm.get_code(addr)
    
    # No additional RPC calls
    assert rpc.calls["get_balance"] == initial_balance_calls
    assert rpc.calls["get_code"] == initial_code_calls
    
    print("[PASS] Preloading optimization")


def test_cache_statistics():
    """Test that cache statistics are tracked correctly."""
    rpc = MockRPCWithStats()
    sm = StateManager(rpc, block_number=12345)
    
    # Generate some hits and misses
    sm.get_code("0xaddr1")  # miss
    sm.get_code("0xaddr1")  # hit
    sm.get_code("0xaddr2")  # miss
    sm.get_code("0xaddr1")  # hit
    
    stats = sm.stats()
    assert stats["code_hits"] == 2
    assert stats["code_misses"] == 2
    
    # Test storage stats
    sm.get_storage("0xaddr1", 0)  # miss
    sm.get_storage("0xaddr1", 0)  # hit
    sm.get_storage("0xaddr1", 1)  # miss
    
    stats = sm.stats()
    assert stats["storage_hits"] == 1
    assert stats["storage_misses"] == 2
    
    print("[PASS] Cache statistics")


def test_simulator_preload_transaction_addresses():
    """Test StateSimulator.preload_transaction_addresses method."""
    rpc = MockRPCWithStats()
    simulator = StateSimulator(rpc, block_number=12345)
    
    tx_data = {
        "hash": "0xtx1",
        "from": "0xfrom",
        "to": "0xto",
        "value": 1000,
    }
    
    # Preload transaction addresses
    simulator.preload_transaction_addresses(tx_data)
    
    # Should have preloaded both from and to addresses
    assert rpc.calls["get_balance"] >= 2
    assert rpc.calls["get_code"] >= 2
    
    # Subsequent access should use cache
    initial_balance = rpc.calls["get_balance"]
    simulator.state_manager.get_account("0xfrom")
    assert rpc.calls["get_balance"] == initial_balance
    
    print("[PASS] Simulator preload transaction addresses")


def test_cache_stats_method():
    """Test StateSimulator.get_cache_stats method."""
    rpc = MockRPCWithStats()
    simulator = StateSimulator(rpc, block_number=12345)
    
    # Generate some cache activity
    simulator.state_manager.get_code("0xaddr1")
    simulator.state_manager.get_code("0xaddr1")
    simulator.state_manager.get_code("0xaddr2")
    
    # Get formatted stats
    stats = simulator.get_cache_stats()
    
    assert "account_cache" in stats
    assert "storage_cache" in stats
    assert "code_cache" in stats
    
    # Check code cache stats
    assert stats["code_cache"]["hits"] == 1
    assert stats["code_cache"]["misses"] == 2
    assert 0.0 <= stats["code_cache"]["hit_rate"] <= 1.0
    
    print("[PASS] Cache stats method")


def test_inspector_preload_block():
    """Test that MEVInspector preloads addresses from block transactions."""
    rpc = MockRPCWithStats()
    inspector = MEVInspector(rpc)
    
    # Record initial RPC call counts
    initial_code_calls = rpc.calls["get_code"]
    initial_balance_calls = rpc.calls["get_balance"]
    
    # Inspect a block (will trigger preloading)
    try:
        results = inspector.inspect_block(12345, what_if=False)
    except Exception:
        # May fail due to missing dependencies, but preload should have been called
        pass
    
    # Should have preloaded addresses (from + to for each transaction)
    # Block has 2 transactions = 4 addresses max (if all unique)
    assert rpc.calls["get_balance"] > initial_balance_calls
    assert rpc.calls["get_code"] > initial_code_calls
    
    print("[PASS] Inspector preload block")


def _run_all():
    """Run all integration tests."""
    tests = [
        test_state_manager_integration,
        test_caching_reduces_rpc_calls,
        test_preloading_optimization,
        test_cache_statistics,
        test_simulator_preload_transaction_addresses,
        test_cache_stats_method,
        test_inspector_preload_block,
    ]
    
    failures = 0
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as e:
            failures += 1
            print(f"[FAIL] {test_fn.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"[ERROR] {test_fn.__name__}: {e}")
    
    print(f"\nPhase 1 Integration Tests: {len(tests) - failures}/{len(tests)} passed")
    
    if failures == 0:
        print("\n✅ Phase 1 Complete: StateManager fully integrated with caching optimization")
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    _run_all()
