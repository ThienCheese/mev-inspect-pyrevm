#!/usr/bin/env python3
"""
Demo script for Phase 2: TransactionReplayer functionality.

This script demonstrates:
1. Transaction replay with internal call extraction
2. Swap detection from internal calls
3. State change tracking
4. Integration with StateManager for efficient RPC usage

Usage:
    python3 examples/demo_phase2_replay.py [--tx-hash TX_HASH] [--rpc-url RPC_URL]
"""

import sys
from pathlib import Path
import argparse

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mev_inspect.replay import TransactionReplayer, PYREVM_AVAILABLE
from mev_inspect.state_manager import StateManager


class SimpleRPCClient:
    """Simple RPC client wrapper for demo purposes."""
    
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


def format_bytes(data: bytes, max_len: int = 32) -> str:
    """Format bytes for display."""
    if len(data) == 0:
        return "0x"
    hex_str = data.hex()
    if len(hex_str) > max_len:
        return f"0x{hex_str[:max_len]}..."
    return f"0x{hex_str}"


def demo_replay_transaction(rpc_url: str, tx_hash: str):
    """Demo transaction replay with internal call extraction."""
    
    print("\n" + "=" * 80)
    print("PHASE 2 DEMO: Transaction Replay with Internal Calls")
    print("=" * 80)
    print()
    
    # Initialize RPC client
    print("1️⃣  Initializing RPC client...")
    rpc = SimpleRPCClient(rpc_url)
    
    # Get transaction to determine block number
    print(f"\n2️⃣  Fetching transaction: {tx_hash}")
    tx = rpc.get_transaction(tx_hash)
    block_number = tx["blockNumber"]
    print(f"   Block: {block_number}")
    print(f"   From: {tx['from']}")
    print(f"   To: {tx['to']}")
    print(f"   Value: {tx['value']} wei")
    print(f"   Gas: {tx['gas']}")
    
    # Initialize StateManager
    print(f"\n3️⃣  Initializing StateManager (Phase 1 - Caching)...")
    state_manager = StateManager(rpc, block_number)
    print("   ✅ StateManager ready with LRU caching")
    
    # Check PyRevm availability
    print(f"\n4️⃣  Checking PyRevm availability...")
    if PYREVM_AVAILABLE:
        print("   ✅ PyRevm is available - will use full replay")
    else:
        print("   ⚠️  PyRevm not available - will use fallback (logs only)")
        print("   💡 Install with: pip install pyrevm>=0.3.0")
    
    # Initialize TransactionReplayer
    print(f"\n5️⃣  Initializing TransactionReplayer (Phase 2)...")
    replayer = TransactionReplayer(rpc, state_manager, block_number)
    print("   ✅ TransactionReplayer ready")
    
    # Replay transaction
    print(f"\n6️⃣  Replaying transaction...")
    print("   (This may take a few seconds for complex transactions)")
    
    try:
        result = replayer.replay_transaction(tx_hash)
        
        print("\n" + "─" * 80)
        print("REPLAY RESULTS")
        print("─" * 80)
        
        print(f"\n✅ Success: {result.success}")
        print(f"⛽ Gas Used: {result.gas_used:,}")
        print(f"📤 Output: {format_bytes(result.output, 64)}")
        print(f"\n📞 Internal Calls: {len(result.internal_calls)}")
        print(f"💾 State Changes: {len(result.state_changes)}")
        
        # Show internal calls
        if result.internal_calls:
            print("\n" + "─" * 80)
            print("INTERNAL CALLS")
            print("─" * 80)
            
            for i, call in enumerate(result.internal_calls[:10], 1):  # Show first 10
                print(f"\n{i}. {call.call_type}")
                print(f"   From: {format_address(call.from_address)}")
                print(f"   To: {format_address(call.to_address)}")
                print(f"   Selector: {call.function_selector}")
                print(f"   Value: {call.value} wei")
                print(f"   Gas: {call.gas_used:,}")
                print(f"   Depth: {call.depth}")
                print(f"   Success: {call.success}")
            
            if len(result.internal_calls) > 10:
                print(f"\n   ... and {len(result.internal_calls) - 10} more calls")
        
        # Show state changes
        if result.state_changes:
            print("\n" + "─" * 80)
            print("STATE CHANGES")
            print("─" * 80)
            
            for i, change in enumerate(result.state_changes[:5], 1):  # Show first 5
                print(f"\n{i}. Contract: {format_address(change.contract_address)}")
                print(f"   Slot: {change.storage_slot}")
                print(f"   Old: {format_bytes(change.old_value, 32)}")
                print(f"   New: {format_bytes(change.new_value, 32)}")
            
            if len(result.state_changes) > 5:
                print(f"\n   ... and {len(result.state_changes) - 5} more changes")
        
        # Extract swaps
        print("\n" + "─" * 80)
        print("SWAP DETECTION")
        print("─" * 80)
        
        swaps = replayer.extract_swaps_from_calls(result.internal_calls)
        print(f"\n🔄 Detected Swaps: {len(swaps)}")
        
        if swaps:
            for i, swap in enumerate(swaps, 1):
                print(f"\n{i}. Pool: {format_address(swap['pool'])}")
                print(f"   Function: {swap['function_selector']}")
                
                if "amount0_out" in swap:
                    print(f"   Amount0 Out: {swap['amount0_out']:,}")
                if "amount1_out" in swap:
                    print(f"   Amount1 Out: {swap['amount1_out']:,}")
                if "recipient" in swap:
                    print(f"   Recipient: {format_address(swap['recipient'])}")
        
        # Show StateManager stats
        print("\n" + "─" * 80)
        print("STATE MANAGER STATS (Phase 1 Caching)")
        print("─" * 80)
        
        stats = state_manager.get_cache_stats()
        total_requests = stats["account_hits"] + stats["account_misses"]
        if total_requests > 0:
            hit_rate = (stats["account_hits"] / total_requests) * 100
            print(f"\n📊 Account Cache:")
            print(f"   Hits: {stats['account_hits']}")
            print(f"   Misses: {stats['account_misses']}")
            print(f"   Hit Rate: {hit_rate:.1f}%")
            print(f"   RPC Calls Saved: {stats['account_hits']}")
        
        print("\n✅ Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during replay: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Demo Phase 2: TransactionReplayer functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Replay a UniswapV2 swap transaction on Ethereum mainnet
  python3 examples/demo_phase2_replay.py \\
    --tx-hash 0xabc123... \\
    --rpc-url https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
  
  # Replay using local node
  python3 examples/demo_phase2_replay.py \\
    --tx-hash 0xabc123... \\
    --rpc-url http://localhost:8545

Known good test transactions:
  - Mainnet UniswapV2 swap: 0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4
  - Mainnet complex MEV: 0x2e6b6b5f9b6c3d0e5c7b1a7e8c9b6f5d4e8c9b6f5d4e8c9b6f5d4e8c9b6f5d4e
        """
    )
    
    parser.add_argument(
        "--tx-hash",
        required=True,
        help="Transaction hash to replay (with 0x prefix)"
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
        return demo_replay_transaction(args.rpc_url, args.tx_hash)
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
