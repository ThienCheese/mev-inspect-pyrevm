#!/usr/bin/env python3
"""
Demo script for Phase 3: EnhancedSwapDetector

This script demonstrates:
1. Hybrid swap detection (logs + internal calls)
2. Confidence scoring system
3. Multi-hop swap detection
4. Comparison with log-only detection

Usage:
    python3 examples/demo_phase3_enhanced.py [--tx-hash TX_HASH] [--rpc-url RPC_URL]
"""

import sys
from pathlib import Path
import argparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
from mev_inspect.state_manager import StateManager


class SimpleRPCClient:
    """Simple RPC client wrapper for demo."""
    
    def __init__(self, rpc_url: str):
        try:
            from web3 import Web3
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not self.w3.is_connected():
                raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")
            print(f"✅ Connected to RPC: {rpc_url}")
        except ImportError:
            raise ImportError("web3.py is required. Install with: pip install web3>=6.15.0")
    
    def get_block(self, block_number, full_transactions=False):
        """Get block data."""
        block = self.w3.eth.get_block(block_number, full_transactions=full_transactions)
        return {
            "number": block["number"],
            "hash": block["hash"].hex(),
            "miner": block["miner"],
            "timestamp": block["timestamp"],
            "gasLimit": block["gasLimit"],
            "baseFeePerGas": block.get("baseFeePerGas", 0),
            "mixHash": block.get("mixHash", b"\x00" * 32),
            "transactions": block.get("transactions", []),
        }
    
    def get_transaction(self, tx_hash):
        """Get transaction data."""
        tx = self.w3.eth.get_transaction(tx_hash)
        return {
            "hash": tx["hash"].hex(),
            "from": tx["from"],
            "to": tx["to"],
            "value": tx["value"],
            "input": tx["input"].hex(),
            "gas": tx["gas"],
            "gasPrice": tx.get("gasPrice", 0),
            "nonce": tx["nonce"],
            "blockNumber": tx["blockNumber"],
        }
    
    def get_transaction_receipt(self, tx_hash):
        """Get transaction receipt."""
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
    
    def get_balance(self, address, block_number):
        """Get account balance at block."""
        return self.w3.eth.get_balance(address, block_number)
    
    def get_code(self, address):
        """Get contract code."""
        code = self.w3.eth.get_code(address)
        return bytes(code)
    
    def get_storage_at(self, address, position, block_number):
        """Get storage at position."""
        storage = self.w3.eth.get_storage_at(address, position, block_number)
        return bytes(storage)


def format_address(address: str) -> str:
    """Format address for display."""
    if not address:
        return "None"
    return f"{address[:6]}...{address[-4:]}"


def format_amount(amount: int, decimals: int = 18) -> str:
    """Format token amount."""
    if amount == 0:
        return "0"
    
    value = amount / (10 ** decimals)
    if value >= 1000:
        return f"{value:,.2f}"
    elif value >= 1:
        return f"{value:.4f}"
    else:
        return f"{value:.8f}"


def demo_enhanced_swap_detection(rpc_url: str, tx_hash: str):
    """Demo enhanced swap detection with hybrid approach."""
    
    print("\n" + "=" * 80)
    print("PHASE 3 DEMO: Enhanced Swap Detection (Hybrid Approach)")
    print("=" * 80)
    print()
    
    # Initialize
    print("1️⃣  Initializing components...")
    rpc = SimpleRPCClient(rpc_url)
    
    # Get transaction info
    print(f"\n2️⃣  Analyzing transaction: {tx_hash}")
    tx = rpc.get_transaction(tx_hash)
    receipt = rpc.get_transaction_receipt(tx_hash)
    block_number = tx["blockNumber"]
    
    print(f"   Block: {block_number}")
    print(f"   From: {tx['from']}")
    print(f"   To: {tx['to']}")
    print(f"   Gas Used: {receipt['gasUsed']:,}")
    print(f"   Status: {'✅ Success' if receipt['status'] == 1 else '❌ Failed'}")
    
    # Initialize StateManager and EnhancedSwapDetector
    print(f"\n3️⃣  Initializing Enhanced Swap Detector...")
    state_manager = StateManager(rpc, block_number)
    
    # Test with hybrid detection
    detector_hybrid = EnhancedSwapDetector(
        rpc_client=rpc,
        state_manager=state_manager,
        use_internal_calls=True,  # Enable hybrid
        min_confidence=0.5
    )
    
    # Test with log-only detection
    detector_logs = EnhancedSwapDetector(
        rpc_client=rpc,
        state_manager=state_manager,
        use_internal_calls=False,  # Disable hybrid
        min_confidence=0.5
    )
    
    print("   ✅ Hybrid detector ready (logs + internal calls)")
    print("   ✅ Log-only detector ready (for comparison)")
    
    # Detect swaps with hybrid approach
    print(f"\n4️⃣  Detecting swaps (HYBRID: logs + internal calls)...")
    print("   (This may take a few seconds...)")
    
    try:
        swaps_hybrid = detector_hybrid.detect_swaps(tx_hash, block_number)
        
        print(f"\n   ✅ Detected {len(swaps_hybrid)} swaps with hybrid approach")
        
        # Detect with log-only for comparison
        print(f"\n5️⃣  Detecting swaps (LOG-ONLY: for comparison)...")
        swaps_logs = detector_logs.detect_swaps(tx_hash, block_number)
        
        print(f"   ✅ Detected {len(swaps_logs)} swaps with log-only approach")
        
        # Display comparison
        print("\n" + "─" * 80)
        print("DETECTION COMPARISON")
        print("─" * 80)
        print(f"\n📊 Hybrid Detection: {len(swaps_hybrid)} swaps")
        print(f"📊 Log-Only Detection: {len(swaps_logs)} swaps")
        
        if len(swaps_hybrid) > len(swaps_logs):
            diff = len(swaps_hybrid) - len(swaps_logs)
            print(f"\n✨ Hybrid detected {diff} additional swap(s)!")
        elif len(swaps_hybrid) < len(swaps_logs):
            diff = len(swaps_logs) - len(swaps_hybrid)
            print(f"\n⚠️  Hybrid filtered out {diff} false positive(s)!")
        else:
            print(f"\n✓ Both methods detected same number of swaps")
        
        # Display hybrid swaps with confidence
        if swaps_hybrid:
            print("\n" + "─" * 80)
            print("HYBRID DETECTION RESULTS (with Confidence Scores)")
            print("─" * 80)
            
            for i, swap in enumerate(swaps_hybrid, 1):
                print(f"\n{i}. Swap at Pool {format_address(swap.pool_address)}")
                print(f"   Protocol: {swap.protocol}")
                print(f"   Detection: {swap.detection_method.upper()}")
                print(f"   Confidence: {swap.confidence:.2%} ", end="")
                
                # Add confidence indicator
                if swap.confidence >= 0.9:
                    print("🟢 (Very High)")
                elif swap.confidence >= 0.7:
                    print("🟡 (High)")
                elif swap.confidence >= 0.5:
                    print("🟠 (Medium)")
                else:
                    print("🔴 (Low)")
                
                if swap.token_in:
                    print(f"   Token In: {format_address(swap.token_in)}")
                if swap.token_out:
                    print(f"   Token Out: {format_address(swap.token_out)}")
                
                if swap.amount_in > 0:
                    print(f"   Amount In: {format_amount(swap.amount_in)}")
                if swap.amount_out > 0:
                    print(f"   Amount Out: {format_amount(swap.amount_out)}")
                
                print(f"   Call Depth: {swap.call_depth}")
                print(f"   Gas Used: {swap.gas_used:,}")
        
        # Detect multi-hop swaps
        print("\n" + "─" * 80)
        print("MULTI-HOP SWAP DETECTION")
        print("─" * 80)
        
        multi_hops = detector_hybrid.detect_multi_hop_swaps(tx_hash, block_number)
        
        if multi_hops:
            print(f"\n🔗 Detected {len(multi_hops)} multi-hop swap sequence(s)!")
            
            for i, mh in enumerate(multi_hops, 1):
                print(f"\n{i}. Multi-Hop Swap ({mh.hop_count} hops)")
                print(f"   Path: {format_address(mh.token_in)} → ... → {format_address(mh.token_out)}")
                print(f"   Pools Used: {', '.join([format_address(p) for p in mh.pools_used])}")
                print(f"   Amount In: {format_amount(mh.amount_in)}")
                print(f"   Amount Out: {format_amount(mh.amount_out)}")
                print(f"   Total Gas: {mh.total_gas_used:,}")
                
                print(f"\n   Hop Details:")
                for j, hop in enumerate(mh.hops, 1):
                    print(f"     {j}. {format_address(hop.pool_address)}")
                    print(f"        In: {format_amount(hop.amount_in)} → Out: {format_amount(hop.amount_out)}")
                    print(f"        Confidence: {hop.confidence:.2%}")
        else:
            print("\n   No multi-hop swaps detected (single swaps only)")
        
        # Display statistics
        print("\n" + "─" * 80)
        print("DETECTION STATISTICS")
        print("─" * 80)
        
        stats = detector_hybrid.get_statistics()
        print(f"\n📈 Hybrid Detector Stats:")
        print(f"   Total Transactions: {stats['total_transactions']}")
        print(f"   Swaps (Log-Only): {stats['swaps_detected_log_only']}")
        print(f"   Swaps (Call-Only): {stats['swaps_detected_internal_calls']}")
        print(f"   Swaps (Hybrid): {stats['swaps_detected_hybrid']}")
        print(f"   Multi-Hop Swaps: {stats['multi_hop_swaps']}")
        
        # Calculate accuracy improvement
        if len(swaps_logs) > 0:
            improvement = ((len(swaps_hybrid) - len(swaps_logs)) / len(swaps_logs)) * 100
            if improvement > 0:
                print(f"\n✨ Hybrid approach found {abs(improvement):.1f}% more swaps!")
            elif improvement < 0:
                print(f"\n✨ Hybrid approach filtered {abs(improvement):.1f}% false positives!")
        
        print("\n✅ Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during detection: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Demo Phase 3: Enhanced Swap Detection with Hybrid Approach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a UniswapV2 swap transaction
  python3 examples/demo_phase3_enhanced.py \\
    --tx-hash 0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4 \\
    --rpc-url https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
  
  # Analyze a complex multi-hop swap
  python3 examples/demo_phase3_enhanced.py \\
    --tx-hash 0xabc123... \\
    --rpc-url http://localhost:8545

Benefits of Hybrid Approach:
  - Higher accuracy (target 80% vs mev-inspect-py)
  - Validates swaps by cross-referencing logs and internal calls
  - Detects multi-hop swaps across multiple pools
  - Assigns confidence scores to filter false positives
  - Works without trace APIs (trace_transaction, etc.)
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
    
    args = parser.parse_args()
    
    # Validate tx hash format
    if not args.tx_hash.startswith("0x") or len(args.tx_hash) != 66:
        print("❌ Error: Transaction hash must start with 0x and be 66 characters long")
        return 1
    
    try:
        return demo_enhanced_swap_detection(args.rpc_url, args.tx_hash)
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
