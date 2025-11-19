"""Tests for Phase 4: ProfitCalculator."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mev_inspect.profit_calculator import (
    ProfitCalculator,
    TokenTransfer,
    ProfitCalculation,
    ArbitrageOpportunity,
    WETH_ADDRESS,
    TRANSFER_EVENT,
)
from mev_inspect.state_manager import StateManager
from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector


class MockRPCForProfit:
    """Mock RPC for testing ProfitCalculator."""
    
    def __init__(self):
        self.transactions = {}
        self.receipts = {}
    
    def add_transaction(self, tx_hash: str, tx_data: dict, receipt_data: dict):
        self.transactions[tx_hash] = tx_data
        self.receipts[tx_hash] = receipt_data
    
    def get_transaction(self, tx_hash: str):
        return self.transactions.get(tx_hash, {})
    
    def get_transaction_receipt(self, tx_hash: str):
        return self.receipts.get(tx_hash, {})
    
    def get_block(self, block_number, full_transactions=False):
        return {
            "number": block_number,
            "hash": "0xabc",
            "timestamp": 1234567890,
            "gasLimit": 30000000,
        }
    
    def get_balance(self, address, block_number):
        return 1000000000000000000
    
    def get_code(self, address):
        return b"\x60\x80"
    
    def get_storage_at(self, address, position, block_number):
        return b"\x00" * 32


def test_profit_calculator_imports():
    """Test that ProfitCalculator can be imported."""
    from mev_inspect.profit_calculator import ProfitCalculator
    
    assert ProfitCalculator is not None
    print("[PASS] ProfitCalculator imported successfully")


def test_token_transfer_dataclass():
    """Test TokenTransfer dataclass."""
    transfer = TokenTransfer(
        token="0xtoken",
        from_address="0xfrom",
        to_address="0xto",
        amount=1000000,
        log_index=5
    )
    
    assert transfer.token == "0xtoken"
    assert transfer.from_address == "0xfrom"
    assert transfer.to_address == "0xto"
    assert transfer.amount == 1000000
    assert transfer.log_index == 5
    
    print("[PASS] TokenTransfer dataclass works")


def test_profit_calculation_dataclass():
    """Test ProfitCalculation dataclass."""
    profit = ProfitCalculation(
        tx_hash="0xtx123",
        mev_type="arbitrage",
        gross_profit_wei=5000000000000000000,  # 5 ETH
        gas_cost_wei=1000000000000000000,  # 1 ETH
        net_profit_wei=4000000000000000000,  # 4 ETH
        tokens_in={"0xweth": 10000000},
        tokens_out={"0xweth": 5000000},
        swaps_involved=3,
        is_profitable=True,
        confidence=0.85,
        method="token_flow_weth"
    )
    
    assert profit.tx_hash == "0xtx123"
    assert profit.mev_type == "arbitrage"
    assert profit.net_profit_wei == 4000000000000000000
    assert profit.is_profitable is True
    assert profit.confidence == 0.85
    
    print("[PASS] ProfitCalculation dataclass works")


def test_arbitrage_opportunity_dataclass():
    """Test ArbitrageOpportunity dataclass."""
    profit = ProfitCalculation(
        tx_hash="0xtx123",
        mev_type="arbitrage",
        gross_profit_wei=5000000000000000000,
        gas_cost_wei=1000000000000000000,
        net_profit_wei=4000000000000000000,
        tokens_in={},
        tokens_out={},
        is_profitable=True,
        confidence=0.9,
        method="hybrid"
    )
    
    arb = ArbitrageOpportunity(
        tx_hash="0xtx123",
        token_path=["0xtoken0", "0xtoken1", "0xtoken2", "0xtoken0"],
        pool_path=["0xpool1", "0xpool2", "0xpool3"],
        profit=profit
    )
    
    assert arb.num_hops == 3
    assert arb.start_token == "0xtoken0"
    assert arb.end_token == "0xtoken0"
    assert arb.profit.net_profit_wei == 4000000000000000000
    
    print("[PASS] ArbitrageOpportunity dataclass works")


def test_calculator_initialization():
    """Test ProfitCalculator initialization."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    
    calculator = ProfitCalculator(
        rpc_client=rpc,
        state_manager=state_manager,
        mev_contract="0xmevbot"
    )
    
    assert calculator.rpc_client == rpc
    assert calculator.state_manager == state_manager
    assert calculator.mev_contract == "0xmevbot"
    assert calculator.stats["total_analyzed"] == 0
    
    print("[PASS] ProfitCalculator initialization works")


def test_extract_token_transfers():
    """Test extracting token transfers from logs."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    calculator = ProfitCalculator(rpc, state_manager)
    
    # Create mock receipt with Transfer events
    receipt = {
        "logs": [
            {
                "address": "0xtoken1",
                "topics": [
                    TRANSFER_EVENT,
                    "0x000000000000000000000000" + "aa" * 20,  # from
                    "0x000000000000000000000000" + "bb" * 20,  # to
                ],
                "data": "0x" + "00" * 31 + "64"  # amount = 100
            },
            {
                "address": "0xtoken2",
                "topics": [
                    TRANSFER_EVENT,
                    "0x000000000000000000000000" + "bb" * 20,  # from
                    "0x000000000000000000000000" + "cc" * 20,  # to
                ],
                "data": "0x" + "00" * 31 + "c8"  # amount = 200
            }
        ]
    }
    
    transfers = calculator._extract_token_transfers(receipt)
    
    assert len(transfers) == 2
    assert transfers[0].token == "0xtoken1"
    assert transfers[0].amount == 100
    assert transfers[1].token == "0xtoken2"
    assert transfers[1].amount == 200
    
    print("[PASS] Token transfer extraction works")


def test_calculate_token_flows():
    """Test calculating token flows for an address."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    calculator = ProfitCalculator(rpc, state_manager)
    
    searcher = "0x" + "aa" * 20
    
    transfers = [
        # Searcher receives 1000 of token1
        TokenTransfer(
            token="0xtoken1",
            from_address="0xother",
            to_address=searcher,
            amount=1000,
            log_index=0
        ),
        # Searcher sends 500 of token2
        TokenTransfer(
            token="0xtoken2",
            from_address=searcher,
            to_address="0xother",
            amount=500,
            log_index=1
        ),
        # Searcher receives 2000 of token2
        TokenTransfer(
            token="0xtoken2",
            from_address="0xother2",
            to_address=searcher,
            amount=2000,
            log_index=2
        ),
    ]
    
    tokens_in, tokens_out = calculator._calculate_token_flows(transfers, searcher)
    
    assert tokens_in["0xtoken1"] == 1000
    assert tokens_in["0xtoken2"] == 2000
    assert tokens_out["0xtoken2"] == 500
    assert "0xtoken1" not in tokens_out
    
    print("[PASS] Token flow calculation works")


def test_classify_mev_type():
    """Test MEV type classification."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    calculator = ProfitCalculator(rpc, state_manager)
    
    searcher = "0x" + "aa" * 20
    
    # Arbitrage pattern: same token in and out, with profit
    transfers = [
        TokenTransfer("0xweth", "0xpool1", searcher, 11000, 0),  # Receive 11 WETH
        TokenTransfer("0xweth", searcher, "0xpool1", 10000, 1),  # Send 10 WETH
        TokenTransfer("0xusdc", "0xpool2", searcher, 20000, 2),  # Receive USDC
        TokenTransfer("0xusdc", searcher, "0xpool2", 20000, 3),  # Send USDC
    ]
    
    mev_type = calculator._classify_mev_type(
        tx={},
        receipt={},
        transfers=transfers,
        searcher_address=searcher
    )
    
    assert mev_type == "arbitrage"
    
    print("[PASS] MEV type classification works")


def test_calculate_gross_profit():
    """Test gross profit calculation."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    calculator = ProfitCalculator(rpc, state_manager)
    
    # Case 1: Profit in WETH
    tokens_in = {WETH_ADDRESS.lower(): 11000000000000000000}  # 11 WETH
    tokens_out = {WETH_ADDRESS.lower(): 10000000000000000000}  # 10 WETH
    
    profit, confidence, method = calculator._calculate_gross_profit(
        tokens_in,
        tokens_out,
        [],
        "0xsearcher"
    )
    
    assert profit == 1000000000000000000  # 1 WETH profit
    assert confidence == 0.8
    assert "weth" in method.lower()
    
    print("[PASS] Gross profit calculation works")


def test_calculate_profit_full():
    """Test full profit calculation."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    calculator = ProfitCalculator(rpc, state_manager)
    
    searcher = "0x" + "aa" * 20
    
    # Create mock transaction with profit
    tx = {
        "hash": "0xtx123",
        "from": searcher,
        "gasPrice": 50000000000,  # 50 Gwei
    }
    
    receipt = {
        "gasUsed": 200000,
        "logs": [
            # Searcher receives 11 WETH
            {
                "address": WETH_ADDRESS,
                "topics": [
                    TRANSFER_EVENT,
                    "0x000000000000000000000000" + "bb" * 20,
                    "0x000000000000000000000000" + searcher[2:],
                ],
                "data": "0x" + hex(11 * 10**18)[2:].zfill(64)
            },
            # Searcher sends 10 WETH
            {
                "address": WETH_ADDRESS,
                "topics": [
                    TRANSFER_EVENT,
                    "0x000000000000000000000000" + searcher[2:],
                    "0x000000000000000000000000" + "bb" * 20,
                ],
                "data": "0x" + hex(10 * 10**18)[2:].zfill(64)
            },
        ]
    }
    
    rpc.add_transaction("0xtx123", tx, receipt)
    
    profit = calculator.calculate_profit("0xtx123", 12345, searcher)
    
    assert profit.tx_hash == "0xtx123"
    assert profit.gross_profit_wei == 1 * 10**18  # 1 WETH profit
    assert profit.gas_cost_wei == 200000 * 50000000000
    assert profit.net_profit_wei == profit.gross_profit_wei - profit.gas_cost_wei
    assert profit.is_profitable is True  # 1 ETH - gas should be positive
    
    print("[PASS] Full profit calculation works")


def test_statistics_tracking():
    """Test statistics tracking."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    calculator = ProfitCalculator(rpc, state_manager)
    
    stats = calculator.get_statistics()
    assert stats["total_analyzed"] == 0
    assert stats["profitable_txs"] == 0
    
    # Simulate some calculations
    calculator.stats["total_analyzed"] = 10
    calculator.stats["profitable_txs"] = 7
    calculator.stats["unprofitable_txs"] = 3
    calculator.stats["total_profit_wei"] = 5000000000000000000
    
    stats = calculator.get_statistics()
    assert stats["total_analyzed"] == 10
    assert stats["profitable_rate"] == 0.7
    assert stats["avg_profit_wei"] > 0
    
    # Reset
    calculator.reset_statistics()
    stats = calculator.get_statistics()
    assert stats["total_analyzed"] == 0
    
    print("[PASS] Statistics tracking works")


def test_format_profit():
    """Test profit formatting."""
    rpc = MockRPCForProfit()
    state_manager = StateManager(rpc, 12345)
    calculator = ProfitCalculator(rpc, state_manager)
    
    profit = ProfitCalculation(
        tx_hash="0xtx123",
        mev_type="arbitrage",
        gross_profit_wei=5000000000000000000,
        gas_cost_wei=1000000000000000000,
        net_profit_wei=4000000000000000000,
        tokens_in={"0xweth": 11000000},
        tokens_out={"0xweth": 6000000},
        swaps_involved=3,
        is_profitable=True,
        confidence=0.85,
        method="token_flow_weth"
    )
    
    formatted = calculator.format_profit(profit)
    
    assert "0xtx123" in formatted
    assert "arbitrage" in formatted
    assert "5,000,000,000,000,000,000" in formatted
    assert "✅ Yes" in formatted
    
    print("[PASS] Profit formatting works")


def _run_all():
    """Run all Phase 4 tests."""
    print("=" * 80)
    print("PHASE 4: ProfitCalculator - Unit Tests")
    print("=" * 80)
    print()
    
    tests = [
        test_profit_calculator_imports,
        test_token_transfer_dataclass,
        test_profit_calculation_dataclass,
        test_arbitrage_opportunity_dataclass,
        test_calculator_initialization,
        test_extract_token_transfers,
        test_calculate_token_flows,
        test_classify_mev_type,
        test_calculate_gross_profit,
        test_calculate_profit_full,
        test_statistics_tracking,
        test_format_profit,
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
            import traceback
            traceback.print_exc()
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
        print("\n✅ All Phase 4 tests PASSED!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(_run_all())
