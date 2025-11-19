#!/usr/bin/env python3
"""
Demo script for Phase 4: ProfitCalculator.

This script demonstrates profit calculation for MEV transactions including:
- Token flow analysis
- Gas cost calculation
- Net profit determination
- MEV type classification
- Arbitrage detection

Usage:
    python3 examples/demo_phase4_profit.py [--tx-hash TX_HASH] [--rpc-url RPC_URL]
"""

import sys
from pathlib import Path
import argparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mev_inspect.profit_calculator import ProfitCalculator, WETH_ADDRESS
from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
from mev_inspect.state_manager import StateManager


class SimpleRPCClient:
    """Simple RPC client for demo."""
    
    def __init__(self, rpc_url: str):
        try:
            from web3 import Web3
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not self.w3.is_connected():
                raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")
            print(f"✅ Connected to RPC: {rpc_url}")
        except ImportError:
            raise ImportError("web3.py is required. Install with: pip install web3>=6.15.0")
    
    def get_transaction(self, tx_hash):
        tx = self.w3.eth.get_transaction(tx_hash)
        return {
            "hash": tx["hash"].hex(),
            "from": tx["from"],
            "to": tx["to"],
            "value": tx["value"],
            "input": tx["input"].hex(),
            "gas": tx["gas"],
            "gasPrice": tx.get("gasPrice", 0),
            "blockNumber": tx["blockNumber"],
        }
    
    def get_transaction_receipt(self, tx_hash):
        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        logs = []
        for log in receipt["logs"]:
            logs.append({
                "address": log["address"],
                "topics": [topic.hex() for topic in log["topics"]],
                "data": log["data"].hex(),
            })
        
        return {
            "transactionHash": receipt["transactionHash"].hex(),
            "status": receipt["status"],
            "gasUsed": receipt["gasUsed"],
            "logs": logs,
            "blockNumber": receipt["blockNumber"],
        }
    
    def get_block(self, block_number, full_transactions=False):
        block = self.w3.eth.get_block(block_number, full_transactions=full_transactions)
        return {
            "number": block["number"],
            "hash": block["hash"].hex(),
            "timestamp": block["timestamp"],
            "gasLimit": block["gasLimit"],
        }
    
    def get_balance(self, address, block_number):
        return self.w3.eth.get_balance(address, block_number)
    
    def get_code(self, address):
        return bytes(self.w3.eth.get_code(address))
    
    def get_storage_at(self, address, position, block_number):
        return bytes(self.w3.eth.get_storage_at(address, position, block_number))


def format_wei(wei: int) -> str:
    """Format Wei to ETH with proper decimals."""
    eth = wei / 10**18
    return f"{eth:.6f} ETH ({wei:,} Wei)"


def demo_profit_calculation(rpc_url: str, tx_hash: str, searcher_address: str = None):
    """Demo profit calculation for a transaction."""
    
    print("\n" + "=" * 80)
    print("PHASE 4 DEMO: Profit Calculation for MEV Transactions")
    print("=" * 80)
    print()
    
    # Initialize
    print("1️⃣  Initializing components...")
    rpc = SimpleRPCClient(rpc_url)
    
    # Get transaction
    print(f"\n2️⃣  Fetching transaction: {tx_hash}")
    tx = rpc.get_transaction(tx_hash)
    block_number = tx["blockNumber"]
    
    print(f"   Block: {block_number}")
    print(f"   From: {tx['from']}")
    print(f"   To: {tx['to']}")
    print(f"   Gas Price: {tx.get('gasPrice', 0):,} Wei")
    
    # Initialize StateManager and detectors
    print(f"\n3️⃣  Initializing StateManager and SwapDetector...")
    state_manager = StateManager(rpc, block_number)
    swap_detector = EnhancedSwapDetector(rpc, state_manager)
    
    # Initialize ProfitCalculator
    print(f"\n4️⃣  Initializing ProfitCalculator...")
    calculator = ProfitCalculator(
        rpc_client=rpc,
        state_manager=state_manager,
        swap_detector=swap_detector,
        mev_contract=searcher_address
    )
    
    # Calculate profit
    print(f"\n5️⃣  Calculating profit...")
    print("   (This may take a few seconds...)")
    
    try:
        profit = calculator.calculate_profit(
            tx_hash=tx_hash,
            block_number=block_number,
            searcher_address=searcher_address
        )
        
        print("\n" + "─" * 80)
        print("PROFIT CALCULATION RESULTS")
        print("─" * 80)
        
        print(f"\n📊 MEV Type: {profit.mev_type.upper()}")
        print(f"🔍 Detection Method: {profit.method}")
        print(f"📈 Confidence: {profit.confidence:.2%}")
        
        print(f"\n" + "─" * 80)
        print("FINANCIAL BREAKDOWN")
        print("─" * 80)
        
        print(f"\n💰 Gross Profit: {format_wei(profit.gross_profit_wei)}")
        print(f"⛽ Gas Cost: {format_wei(profit.gas_cost_wei)}")
        print(f"{'═' * 40}")
        print(f"📈 Net Profit: {format_wei(profit.net_profit_wei)}")
        
        if profit.is_profitable:
            print(f"\n✅ Transaction is PROFITABLE!")
            roi = (profit.net_profit_wei / profit.gas_cost_wei * 100) if profit.gas_cost_wei > 0 else 0
            print(f"   ROI: {roi:.2f}%")
        else:
            print(f"\n❌ Transaction is NOT profitable (after gas)")
        
        # Token flows
        if profit.tokens_in:
            print(f"\n" + "─" * 80)
            print("TOKENS RECEIVED (IN)")
            print("─" * 80)
            for token, amount in profit.tokens_in.items():
                token_name = "WETH" if token.lower() == WETH_ADDRESS.lower() else token[:10] + "..."
                if token.lower() == WETH_ADDRESS.lower():
                    print(f"   {token_name}: {format_wei(amount)}")
                else:
                    print(f"   {token_name}: {amount:,}")
        
        if profit.tokens_out:
            print(f"\n" + "─" * 80)
            print("TOKENS SENT (OUT)")
            print("─" * 80)
            for token, amount in profit.tokens_out.items():
                token_name = "WETH" if token.lower() == WETH_ADDRESS.lower() else token[:10] + "..."
                if token.lower() == WETH_ADDRESS.lower():
                    print(f"   {token_name}: {format_wei(amount)}")
                else:
                    print(f"   {token_name}: {amount:,}")
        
        # Swaps involved
        if profit.swaps_involved > 0:
            print(f"\n" + "─" * 80)
            print(f"SWAPS: {profit.swaps_involved} detected")
            print("─" * 80)
        
        # Check for arbitrage
        print(f"\n6️⃣  Checking for arbitrage opportunities...")
        arb = calculator.detect_arbitrage(tx_hash, block_number, searcher_address)
        
        if arb:
            print(f"\n" + "─" * 80)
            print("🎯 ARBITRAGE DETECTED!")
            print("─" * 80)
            print(f"\n   Hops: {arb.num_hops}")
            print(f"   Start Token: {arb.start_token[:10]}...")
            print(f"   End Token: {arb.end_token[:10]}...")
            print(f"   Pools Used: {len(arb.pool_path)}")
            for i, pool in enumerate(arb.pool_path, 1):
                print(f"      {i}. {pool[:10]}...")
        else:
            print("   No arbitrage pattern detected")
        
        # Statistics
        print(f"\n" + "─" * 80)
        print("CALCULATOR STATISTICS")
        print("─" * 80)
        
        stats = calculator.get_statistics()
        print(f"\n   Total Analyzed: {stats['total_analyzed']}")
        print(f"   Profitable: {stats['profitable_txs']}")
        print(f"   Unprofitable: {stats['unprofitable_txs']}")
        print(f"   Arbitrage Detected: {stats['arbitrage_detected']}")
        
        print("\n✅ Profit calculation completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during profit calculation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Demo Phase 4: ProfitCalculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Calculate profit for a known MEV transaction
  python3 examples/demo_phase4_profit.py \\
    --tx-hash 0xabc123... \\
    --rpc-url https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
  
  # Specify searcher address
  python3 examples/demo_phase4_profit.py \\
    --tx-hash 0xabc123... \\
    --rpc-url http://localhost:8545 \\
    --searcher 0x1234...

Known MEV transactions to try:
  - Flashbots Bundle: Look for bundles on Flashbots explorer
  - Arbitrage: Multi-hop swap transactions
  - Sandwich: Transactions before/after large swaps
        """
    )
    
    parser.add_argument(
        "--tx-hash",
        required=True,
        help="Transaction hash to analyze (with 0x prefix)"
    )
    
    parser.add_argument(
        "--rpc-url",
        default="http://localhost:8545",
        help="RPC endpoint URL (default: http://localhost:8545)"
    )
    
    parser.add_argument(
        "--searcher",
        help="MEV searcher/bot address (optional, defaults to tx.from)"
    )
    
    args = parser.parse_args()
    
    # Validate tx hash
    if not args.tx_hash.startswith("0x") or len(args.tx_hash) != 66:
        print("❌ Error: Transaction hash must start with 0x and be 66 characters long")
        return 1
    
    try:
        return demo_profit_calculation(args.rpc_url, args.tx_hash, args.searcher)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
