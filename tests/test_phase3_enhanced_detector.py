"""Tests for Phase 3: EnhancedSwapDetector."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from mev_inspect.enhanced_swap_detector import (
    EnhancedSwapDetector,
    EnhancedSwap,
    MultiHopSwap,
    SWAP_EVENT_V2,
    SWAP_EVENT_V3,
)
from mev_inspect.state_manager import StateManager
from mev_inspect.replay import InternalCall


class MockRPCForEnhanced:
    """Mock RPC for testing EnhancedSwapDetector."""
    
    def __init__(self):
        self.transactions = {}
        self.receipts = {}
    
    def add_transaction(self, tx_hash: str, tx_data: dict, receipt_data: dict):
        """Add mock transaction and receipt."""
        self.transactions[tx_hash] = tx_data
        self.receipts[tx_hash] = receipt_data
    
    def get_transaction(self, tx_hash: str):
        return self.transactions.get(tx_hash, {})
    
    def get_transaction_receipt(self, tx_hash: str):
        return self.receipts.get(tx_hash, {})
    
    def get_block(self, block_number, full_transactions=False):
        return {
            "number": block_number,
            "hash": "0x" + "ab" * 32,
            "timestamp": 1234567890,
            "gasLimit": 30000000,
        }
    
    def get_balance(self, address, block_number):
        return 1000000000000000000
    
    def get_code(self, address):
        return b"\x60\x80\x60\x40"
    
    def get_storage_at(self, address, position, block_number):
        return b"\x00" * 32


def test_enhanced_swap_detector_imports():
    """Test that EnhancedSwapDetector can be imported."""
    from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
    
    assert EnhancedSwapDetector is not None
    print("[PASS] EnhancedSwapDetector imported successfully")


def test_enhanced_swap_dataclass():
    """Test EnhancedSwap dataclass."""
    swap = EnhancedSwap(
        tx_hash="0xtx123",
        pool_address="0xpool",
        protocol="UniswapV2",
        token_in="0xtoken0",
        token_out="0xtoken1",
        amount_in=1000000,
        amount_out=2000000,
        from_address="0xuser",
        to_address="0xrouter",
        gas_used=150000,
        detection_method="hybrid",
        confidence=0.95,
        call_depth=2,
        is_multi_hop=False,
        hop_count=1
    )
    
    assert swap.tx_hash == "0xtx123"
    assert swap.pool_address == "0xpool"
    assert swap.protocol == "UniswapV2"
    assert swap.confidence == 0.95
    assert swap.detection_method == "hybrid"
    
    print("[PASS] EnhancedSwap dataclass works correctly")


def test_multi_hop_swap_dataclass():
    """Test MultiHopSwap dataclass."""
    hop1 = EnhancedSwap(
        tx_hash="0xtx123",
        pool_address="0xpool1",
        protocol="UniswapV2",
        token_in="0xtoken0",
        token_out="0xtoken1",
        amount_in=1000000,
        amount_out=2000000,
        from_address="0xuser",
        to_address="0xrouter",
        gas_used=150000,
        detection_method="hybrid",
        confidence=0.95,
        call_depth=2,
        is_multi_hop=True,
        hop_count=2
    )
    
    hop2 = EnhancedSwap(
        tx_hash="0xtx123",
        pool_address="0xpool2",
        protocol="UniswapV2",
        token_in="0xtoken1",
        token_out="0xtoken2",
        amount_in=2000000,
        amount_out=3000000,
        from_address="0xuser",
        to_address="0xrouter",
        gas_used=140000,
        detection_method="hybrid",
        confidence=0.95,
        call_depth=3,
        is_multi_hop=True,
        hop_count=2
    )
    
    multi_hop = MultiHopSwap(
        tx_hash="0xtx123",
        hops=[hop1, hop2],
        total_gas_used=290000
    )
    
    assert multi_hop.hop_count == 2
    assert multi_hop.token_in == "0xtoken0"
    assert multi_hop.token_out == "0xtoken2"
    assert multi_hop.amount_in == 1000000
    assert multi_hop.amount_out == 3000000
    assert len(multi_hop.pools_used) == 2
    assert multi_hop.pools_used == ["0xpool1", "0xpool2"]
    
    print("[PASS] MultiHopSwap dataclass works correctly")


def test_enhanced_detector_initialization():
    """Test EnhancedSwapDetector initialization."""
    rpc = MockRPCForEnhanced()
    state_manager = StateManager(rpc, 12345)
    
    detector = EnhancedSwapDetector(
        rpc_client=rpc,
        state_manager=state_manager,
        use_internal_calls=True,
        min_confidence=0.5
    )
    
    assert detector.rpc_client == rpc
    assert detector.state_manager == state_manager
    assert detector.use_internal_calls is True
    assert detector.min_confidence == 0.5
    assert detector.stats["total_transactions"] == 0
    
    print("[PASS] EnhancedSwapDetector initialization works")


def test_parse_v2_swap_log():
    """Test parsing UniswapV2 Swap log."""
    rpc = MockRPCForEnhanced()
    state_manager = StateManager(rpc, 12345)
    detector = EnhancedSwapDetector(rpc, state_manager)
    
    # Create mock V2 swap log
    # Swap event: amount0In=0, amount1In=1000000, amount0Out=2000000, amount1Out=0
    log = {
        "address": "0xuniswapv2pool",
        "topics": [SWAP_EVENT_V2],
        "data": "0x" + 
            "0000000000000000000000000000000000000000000000000000000000000000" +  # amount0In
            "00000000000000000000000000000000000000000000000000000000000f4240" +  # amount1In = 1000000
            "00000000000000000000000000000000000000000000000000000000001e8480" +  # amount0Out = 2000000
            "0000000000000000000000000000000000000000000000000000000000000000"   # amount1Out
    }
    
    swap = detector._parse_v2_swap_log(log, 0)
    
    assert swap is not None
    assert swap["pool"] == "0xuniswapv2pool"
    assert swap["protocol"] == "UniswapV2"
    assert swap["amount_in"] == 1000000
    assert swap["amount_out"] == 2000000
    assert swap["log_index"] == 0
    
    print("[PASS] V2 swap log parsing works")


def test_parse_v3_swap_log():
    """Test parsing UniswapV3 Swap log."""
    rpc = MockRPCForEnhanced()
    state_manager = StateManager(rpc, 12345)
    detector = EnhancedSwapDetector(rpc, state_manager)
    
    # Create mock V3 swap log
    # amount0 = -1000000 (negative = input), amount1 = 2000000 (positive = output)
    # Use proper two's complement for negative number
    amount0_negative = (-1000000).to_bytes(32, 'big', signed=True)
    amount1_positive = (2000000).to_bytes(32, 'big', signed=True)
    
    log = {
        "address": "0xuniswapv3pool",
        "topics": [SWAP_EVENT_V3],
        "data": "0x" + amount0_negative.hex() + amount1_positive.hex() + "00" * 96
    }
    
    swap = detector._parse_v3_swap_log(log, 0)
    
    assert swap is not None
    assert swap["pool"] == "0xuniswapv3pool"
    assert swap["protocol"] == "UniswapV3"
    assert "amount_in" in swap
    assert "amount_out" in swap
    # Verify amounts are positive (absolute values)
    assert swap["amount_in"] > 0
    assert swap["amount_out"] > 0
    # Verify correct values
    assert swap["amount_in"] == 1000000
    assert swap["amount_out"] == 2000000
    
    print("[PASS] V3 swap log parsing works")


def test_extract_swaps_from_calls():
    """Test extracting swaps from internal calls."""
    rpc = MockRPCForEnhanced()
    state_manager = StateManager(rpc, 12345)
    detector = EnhancedSwapDetector(rpc, state_manager)
    
    # Create mock internal calls
    calls = [
        InternalCall(
            call_type="CALL",
            from_address="0xrouter",
            to_address="0xpool1",
            input_data=bytes.fromhex("022c0d9f") + b"\x00" * 128,
            output_data=b"",
            value=0,
            gas_used=150000,
            success=True,
            depth=2
        ),
        InternalCall(
            call_type="CALL",
            from_address="0xrouter",
            to_address="0xpool2",
            input_data=bytes.fromhex("c42079f9") + b"\x00" * 128,
            output_data=b"",
            value=0,
            gas_used=140000,
            success=True,
            depth=3
        ),
    ]
    
    swaps = detector._extract_swaps_from_calls(calls)
    
    assert len(swaps) == 2
    assert swaps[0]["pool"] == "0xpool1"
    assert swaps[0]["selector"] == "0x022c0d9f"
    assert swaps[0]["depth"] == 2
    assert swaps[1]["pool"] == "0xpool2"
    assert swaps[1]["selector"] == "0xc42079f9"
    assert swaps[1]["depth"] == 3
    
    print("[PASS] Extracting swaps from internal calls works")


def test_cross_reference_swaps():
    """Test cross-referencing log and call swaps."""
    rpc = MockRPCForEnhanced()
    state_manager = StateManager(rpc, 12345)
    detector = EnhancedSwapDetector(rpc, state_manager)
    
    # Swaps found in logs
    log_swaps = [
        {
            "pool": "0xpool1",
            "protocol": "UniswapV2",
            "amount_in": 1000000,
            "amount_out": 2000000,
            "log_index": 0,
        },
        {
            "pool": "0xpool2",
            "protocol": "UniswapV2",
            "amount_in": 500000,
            "amount_out": 1000000,
            "log_index": 1,
        }
    ]
    
    # Swaps found in internal calls
    call_swaps = [
        {
            "pool": "0xpool1",  # Matches log_swaps[0]
            "selector": "0x022c0d9f",
            "depth": 2,
            "gas_used": 150000,
            "call_index": 0,
        },
        {
            "pool": "0xpool3",  # Only in calls, not in logs
            "selector": "0xc42079f9",
            "depth": 3,
            "gas_used": 140000,
            "call_index": 1,
        }
    ]
    
    validated = detector._cross_reference_swaps("0xtx123", log_swaps, call_swaps)
    
    # Should have 3 swaps:
    # 1. pool1 - matched (high confidence)
    # 2. pool2 - log only (medium confidence)
    # 3. pool3 - call only (low confidence)
    assert len(validated) == 3
    
    # Check pool1 (matched) has high confidence
    pool1_swap = next(s for s in validated if s.pool_address == "0xpool1")
    assert pool1_swap.confidence == 0.95
    assert pool1_swap.detection_method == "hybrid"
    
    # Check pool2 (log only) has medium confidence
    pool2_swap = next(s for s in validated if s.pool_address == "0xpool2")
    assert pool2_swap.confidence == 0.65
    assert pool2_swap.detection_method == "log"
    
    # Check pool3 (call only) has lower confidence
    pool3_swap = next(s for s in validated if s.pool_address == "0xpool3")
    assert pool3_swap.confidence == 0.55
    assert pool3_swap.detection_method == "internal_call"
    
    print("[PASS] Cross-referencing swaps works correctly")


def test_group_into_multi_hops():
    """Test grouping swaps into multi-hop sequences."""
    rpc = MockRPCForEnhanced()
    state_manager = StateManager(rpc, 12345)
    detector = EnhancedSwapDetector(rpc, state_manager)
    
    # Create sequence of 3 swaps that form a multi-hop
    swaps = [
        EnhancedSwap(
            tx_hash="0xtx123",
            pool_address="0xpool1",
            protocol="UniswapV2",
            token_in="0xtoken0",
            token_out="0xtoken1",
            amount_in=1000000,
            amount_out=2000000,
            from_address="0xuser",
            to_address="0xrouter",
            gas_used=150000,
            detection_method="hybrid",
            confidence=0.95,
            call_depth=2,
            is_multi_hop=False,
            hop_count=1,
            internal_call_index=0
        ),
        EnhancedSwap(
            tx_hash="0xtx123",
            pool_address="0xpool2",
            protocol="UniswapV2",
            token_in="0xtoken1",
            token_out="0xtoken2",
            amount_in=2000000,
            amount_out=3000000,
            from_address="0xuser",
            to_address="0xrouter",
            gas_used=140000,
            detection_method="hybrid",
            confidence=0.95,
            call_depth=3,
            is_multi_hop=False,
            hop_count=1,
            internal_call_index=1
        ),
        EnhancedSwap(
            tx_hash="0xtx123",
            pool_address="0xpool3",
            protocol="UniswapV2",
            token_in="0xtoken2",
            token_out="0xtoken3",
            amount_in=3000000,
            amount_out=4000000,
            from_address="0xuser",
            to_address="0xrouter",
            gas_used=135000,
            detection_method="hybrid",
            confidence=0.95,
            call_depth=4,
            is_multi_hop=False,
            hop_count=1,
            internal_call_index=2
        ),
    ]
    
    multi_hops = detector._group_into_multi_hops(swaps)
    
    assert len(multi_hops) == 1
    assert multi_hops[0].hop_count == 3
    assert multi_hops[0].token_in == "0xtoken0"
    assert multi_hops[0].token_out == "0xtoken3"
    assert multi_hops[0].amount_in == 1000000
    assert multi_hops[0].amount_out == 4000000
    assert multi_hops[0].total_gas_used == 425000
    
    print("[PASS] Grouping into multi-hops works correctly")


def test_detector_statistics():
    """Test detector statistics tracking."""
    rpc = MockRPCForEnhanced()
    state_manager = StateManager(rpc, 12345)
    detector = EnhancedSwapDetector(rpc, state_manager)
    
    stats = detector.get_statistics()
    
    assert stats["total_transactions"] == 0
    assert stats["swaps_detected_log_only"] == 0
    assert stats["swaps_detected_internal_calls"] == 0
    assert stats["swaps_detected_hybrid"] == 0
    
    # Simulate detection
    detector.stats["total_transactions"] = 10
    detector.stats["swaps_detected_hybrid"] = 25
    
    stats = detector.get_statistics()
    assert stats["total_transactions"] == 10
    assert stats["swaps_detected_hybrid"] == 25
    
    # Reset
    detector.reset_statistics()
    stats = detector.get_statistics()
    assert stats["total_transactions"] == 0
    
    print("[PASS] Statistics tracking works correctly")


def _run_all():
    """Run all Phase 3 tests."""
    print("=" * 80)
    print("PHASE 3: EnhancedSwapDetector - Unit Tests")
    print("=" * 80)
    print()
    
    tests = [
        test_enhanced_swap_detector_imports,
        test_enhanced_swap_dataclass,
        test_multi_hop_swap_dataclass,
        test_enhanced_detector_initialization,
        test_parse_v2_swap_log,
        test_parse_v3_swap_log,
        test_extract_swaps_from_calls,
        test_cross_reference_swaps,
        test_group_into_multi_hops,
        test_detector_statistics,
    ]
    
    passed = 0
    failed = 0
    
    for test_fn in tests:
        print(f"\nRunning: {test_fn.__name__}")
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("=" * 80)
    print(f"Results: {passed}/{len(tests)} tests passed")
    print("=" * 80)
    
    if failed == 0:
        print("\n✅ All Phase 3 tests PASSED!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(_run_all())
