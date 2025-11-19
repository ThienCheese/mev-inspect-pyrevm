#!/usr/bin/env python3
"""
Full Pipeline Demo for mev-inspect-pyrevm
=========================================

This script demonstrates the complete MEV analysis pipeline:
1. StateManager: Efficient state caching
2. TransactionReplayer: Internal call extraction  
3. EnhancedSwapDetector: Hybrid swap detection
4. ProfitCalculator: Profit analysis

Usage:
    python3 demo_full_pipeline.py --tx-hash 0x... --rpc-url http://... --searcher 0x...

Example MEV transactions to try:
    # Arbitrage on mainnet
    --tx-hash 0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4
    
    # Sandwich attack
    --tx-hash 0x7c9d5a6f7a8b4e2c1d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7
"""

import sys
import argparse
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import asdict

# Add parent directory to path
sys.path.insert(0, '/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm')

from mev_inspect.state_manager import StateManager
from mev_inspect.replay import TransactionReplayer
from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
from mev_inspect.profit_calculator import ProfitCalculator


# ========================================
# Mock RPC Client for Testing
# ========================================

class MockRPCClient:
    """Mock RPC client for demo purposes"""
    
    def __init__(self, url: str):
        self.url = url
        self.call_count = 0
        
    def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction receipt"""
        self.call_count += 1
        # Return mock receipt with Transfer events
        return {
            'transactionHash': tx_hash,
            'blockNumber': 18500000,
            'gasUsed': 150000,
            'effectiveGasPrice': 30000000000,  # 30 gwei
            'logs': [
                {
                    'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                    'topics': [
                        '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',  # Transfer
                        '0x000000000000000000000000' + 'a' * 40,  # from
                        '0x000000000000000000000000' + 'b' * 40,  # to (searcher)
                    ],
                    'data': '0x' + '0' * 63 + '5' + '0' * 64,  # 5 WETH
                    'logIndex': 10
                },
                {
                    'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                    'topics': [
                        '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',  # Transfer
                        '0x000000000000000000000000' + 'b' * 40,  # from (searcher)
                        '0x000000000000000000000000' + 'c' * 40,  # to
                    ],
                    'data': '0x' + '0' * 63 + '3' + '0' * 64,  # 3 WETH
                    'logIndex': 20
                },
                # Swap log
                {
                    'address': '0x' + 'd' * 40,  # Pool address
                    'topics': [
                        '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822',  # Swap
                        '0x000000000000000000000000' + 'b' * 40,  # sender
                    ],
                    'data': '0x' + '0' * 64 * 2 + '0' * 63 + '5' + '0' * 64,  # amounts
                    'logIndex': 15
                }
            ]
        }
    
    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction"""
        self.call_count += 1
        return {
            'hash': tx_hash,
            'from': '0x' + 'b' * 40,  # searcher
            'to': '0x' + 'e' * 40,
            'value': '0x0',
            'input': '0x',
            'blockNumber': 18500000,
            'gasPrice': '0x6fc23ac00'  # 30 gwei
        }
    
    def get_code(self, address: str, block_number: int) -> str:
        """Get contract code"""
        self.call_count += 1
        # Return non-empty code for contracts
        if address.startswith('0xC02aaa') or address.startswith('0x' + 'd' * 40):
            return '0x60806040'
        return '0x'
    
    def call_contract(self, to: str, data: str, block_number: int) -> str:
        """Call contract"""
        self.call_count += 1
        # Mock responses for common calls
        if 'name' in data or '06fdde03' in data:
            return '0x' + '0' * 128 + '57726170706564204574686572'  # "Wrapped Ether"
        if 'symbol' in data or '95d89b41' in data:
            return '0x' + '0' * 128 + '57455448'  # "WETH"
        if 'decimals' in data or '313ce567' in data:
            return '0x' + '0' * 63 + '12'  # 18
        return '0x'


# ========================================
# Pipeline Execution
# ========================================

def run_full_pipeline(tx_hash: str, rpc_url: str, searcher_address: Optional[str] = None) -> Dict[str, Any]:
    """
    Run complete MEV analysis pipeline
    
    Args:
        tx_hash: Transaction hash to analyze
        rpc_url: RPC endpoint URL
        searcher_address: Optional searcher address for profit calculation
        
    Returns:
        Dictionary with results from all phases
    """
    results = {
        'transaction': tx_hash,
        'phases': {},
        'timing': {},
        'rpc_stats': {}
    }
    
    # Initialize RPC client
    print(f"🔗 Connecting to RPC: {rpc_url}")
    rpc = MockRPCClient(rpc_url)
    
    # Get transaction details
    tx = rpc.get_transaction(tx_hash)
    receipt = rpc.get_transaction_receipt(tx_hash)
    block_number = tx['blockNumber']
    
    if searcher_address is None:
        searcher_address = tx['from']
    
    print(f"📦 Block: {block_number}")
    print(f"👤 Searcher: {searcher_address}")
    print(f"⛽ Gas Used: {receipt['gasUsed']:,}")
    print()
    
    # ========================================
    # PHASE 1: State Management
    # ========================================
    print("=" * 60)
    print("PHASE 1: StateManager - Efficient State Caching")
    print("=" * 60)
    
    start_time = time.time()
    rpc_before = rpc.call_count
    
    state_manager = StateManager(rpc, block_number, cache_size=1000)
    
    # Preload some addresses
    addresses = [tx['from'], tx['to']] + [log['address'] for log in receipt['logs'][:5]]
    state_manager.preload_accounts(addresses)
    
    phase1_time = time.time() - start_time
    phase1_rpc = rpc.call_count - rpc_before
    
    results['phases']['state_manager'] = {
        'cache_size': 1000,
        'preloaded_addresses': len(addresses),
        'cache_stats': state_manager.get_cache_stats()
    }
    results['timing']['phase1'] = phase1_time
    results['rpc_stats']['phase1'] = phase1_rpc
    
    print(f"✅ StateManager initialized")
    print(f"   Cache size: 1000")
    print(f"   Preloaded: {len(addresses)} addresses")
    print(f"   Time: {phase1_time:.3f}s")
    print(f"   RPC calls: {phase1_rpc}")
    print()
    
    # ========================================
    # PHASE 2: Transaction Replay
    # ========================================
    print("=" * 60)
    print("PHASE 2: TransactionReplayer - Internal Call Extraction")
    print("=" * 60)
    
    start_time = time.time()
    rpc_before = rpc.call_count
    
    replayer = TransactionReplayer(rpc, state_manager, block_number)
    replay_result = replayer.replay_transaction(tx_hash)
    
    phase2_time = time.time() - start_time
    phase2_rpc = rpc.call_count - rpc_before
    
    results['phases']['replay'] = {
        'success': replay_result.success,
        'internal_calls': len(replay_result.internal_calls),
        'state_changes': len(replay_result.state_changes),
        'gas_used': replay_result.gas_used
    }
    results['timing']['phase2'] = phase2_time
    results['rpc_stats']['phase2'] = phase2_rpc
    
    print(f"✅ Transaction replayed")
    print(f"   Success: {replay_result.success}")
    print(f"   Internal calls: {len(replay_result.internal_calls)}")
    print(f"   State changes: {len(replay_result.state_changes)}")
    print(f"   Gas used: {replay_result.gas_used:,}")
    print(f"   Time: {phase2_time:.3f}s")
    print(f"   RPC calls: {phase2_rpc}")
    
    if replay_result.internal_calls:
        print(f"\n   Top 3 internal calls:")
        for i, call in enumerate(replay_result.internal_calls[:3], 1):
            print(f"   {i}. {call.function_name} at {call.to[:10]}... (depth {call.depth})")
    print()
    
    # ========================================
    # PHASE 3: Swap Detection
    # ========================================
    print("=" * 60)
    print("PHASE 3: EnhancedSwapDetector - Hybrid Detection")
    print("=" * 60)
    
    start_time = time.time()
    rpc_before = rpc.call_count
    
    swap_detector = EnhancedSwapDetector(rpc, state_manager)
    swaps = swap_detector.detect_swaps(tx_hash, block_number)
    multi_hop_swaps = swap_detector.detect_multi_hop_swaps(tx_hash, block_number)
    
    phase3_time = time.time() - start_time
    phase3_rpc = rpc.call_count - rpc_before
    
    results['phases']['swap_detection'] = {
        'total_swaps': len(swaps),
        'multi_hop_swaps': len(multi_hop_swaps),
        'avg_confidence': sum(s.confidence for s in swaps) / len(swaps) if swaps else 0,
        'detection_methods': {}
    }
    
    # Count detection methods
    for swap in swaps:
        method = swap.detection_method
        results['phases']['swap_detection']['detection_methods'][method] = \
            results['phases']['swap_detection']['detection_methods'].get(method, 0) + 1
    
    results['timing']['phase3'] = phase3_time
    results['rpc_stats']['phase3'] = phase3_rpc
    
    print(f"✅ Swaps detected")
    print(f"   Total swaps: {len(swaps)}")
    print(f"   Multi-hop swaps: {len(multi_hop_swaps)}")
    if swaps:
        print(f"   Avg confidence: {results['phases']['swap_detection']['avg_confidence']:.2f}")
    print(f"   Time: {phase3_time:.3f}s")
    print(f"   RPC calls: {phase3_rpc}")
    
    if swaps:
        print(f"\n   Detection breakdown:")
        for method, count in results['phases']['swap_detection']['detection_methods'].items():
            print(f"   - {method}: {count}")
        
        print(f"\n   Top 3 swaps:")
        for i, swap in enumerate(swaps[:3], 1):
            token_in_sym = swap.token_in[-6:] if swap.token_in else 'unknown'
            token_out_sym = swap.token_out[-6:] if swap.token_out else 'unknown'
            print(f"   {i}. {token_in_sym} → {token_out_sym} "
                  f"(confidence: {swap.confidence:.2f}, method: {swap.detection_method})")
    print()
    
    # ========================================
    # PHASE 4: Profit Calculation
    # ========================================
    print("=" * 60)
    print("PHASE 4: ProfitCalculator - Profit Analysis")
    print("=" * 60)
    
    start_time = time.time()
    rpc_before = rpc.call_count
    
    profit_calculator = ProfitCalculator(rpc, state_manager, swap_detector)
    profit = profit_calculator.calculate_profit(tx_hash, block_number, searcher_address)
    arb_opportunities = profit_calculator.detect_arbitrage(tx_hash, block_number)
    
    phase4_time = time.time() - start_time
    phase4_rpc = rpc.call_count - rpc_before
    
    results['phases']['profit'] = {
        'gross_profit_wei': profit.gross_profit_wei,
        'gas_cost_wei': profit.gas_cost_wei,
        'net_profit_wei': profit.net_profit_wei,
        'gross_profit_eth': profit.gross_profit_wei / 10**18,
        'net_profit_eth': profit.net_profit_wei / 10**18,
        'mev_type': profit.mev_type,
        'confidence': profit.confidence,
        'tokens_received': len(profit.tokens_received),
        'tokens_sent': len(profit.tokens_sent),
        'arbitrage_opportunities': len(arb_opportunities)
    }
    results['timing']['phase4'] = phase4_time
    results['rpc_stats']['phase4'] = phase4_rpc
    
    print(f"✅ Profit calculated")
    print(f"   Gross profit: {profit.gross_profit_wei / 10**18:.6f} ETH")
    print(f"   Gas cost: {profit.gas_cost_wei / 10**18:.6f} ETH")
    print(f"   Net profit: {profit.net_profit_wei / 10**18:.6f} ETH")
    print(f"   MEV type: {profit.mev_type}")
    print(f"   Confidence: {profit.confidence:.2f}")
    print(f"   Time: {phase4_time:.3f}s")
    print(f"   RPC calls: {phase4_rpc}")
    
    if profit.tokens_received:
        print(f"\n   Tokens received:")
        for token, amount in list(profit.tokens_received.items())[:3]:
            print(f"   - {token[-6:]}: {amount / 10**18:.6f}")
    
    if arb_opportunities:
        print(f"\n   Arbitrage opportunities: {len(arb_opportunities)}")
        for i, arb in enumerate(arb_opportunities[:2], 1):
            print(f"   {i}. Path: {' → '.join([t[-6:] for t in arb.token_path])}")
    print()
    
    # ========================================
    # Summary
    # ========================================
    total_time = sum(results['timing'].values())
    total_rpc = sum(results['rpc_stats'].values())
    
    results['summary'] = {
        'total_time': total_time,
        'total_rpc_calls': total_rpc,
        'cache_efficiency': state_manager.get_cache_stats()
    }
    
    print("=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Total execution time: {total_time:.3f}s")
    print(f"Total RPC calls: {total_rpc}")
    print(f"\nPhase breakdown:")
    print(f"  Phase 1 (State): {results['timing']['phase1']:.3f}s ({phase1_rpc} RPC)")
    print(f"  Phase 2 (Replay): {results['timing']['phase2']:.3f}s ({phase2_rpc} RPC)")
    print(f"  Phase 3 (Detect): {results['timing']['phase3']:.3f}s ({phase3_rpc} RPC)")
    print(f"  Phase 4 (Profit): {results['timing']['phase4']:.3f}s ({phase4_rpc} RPC)")
    
    cache_stats = state_manager.get_cache_stats()
    if cache_stats['total_requests'] > 0:
        hit_rate = cache_stats['cache_hits'] / cache_stats['total_requests'] * 100
        print(f"\nCache efficiency:")
        print(f"  Hit rate: {hit_rate:.1f}%")
        print(f"  Hits: {cache_stats['cache_hits']}")
        print(f"  Misses: {cache_stats['cache_misses']}")
    
    print()
    return results


# ========================================
# Main
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description='Full Pipeline Demo for mev-inspect-pyrevm',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze a transaction
    python3 demo_full_pipeline.py --tx-hash 0x5e1657ef... --rpc-url http://localhost:8545
    
    # Specify searcher address
    python3 demo_full_pipeline.py --tx-hash 0x5e1657ef... --rpc-url http://localhost:8545 --searcher 0xabc...
    
    # Save results to JSON
    python3 demo_full_pipeline.py --tx-hash 0x5e1657ef... --rpc-url http://localhost:8545 --output results.json
        """
    )
    
    parser.add_argument(
        '--tx-hash',
        required=True,
        help='Transaction hash to analyze'
    )
    
    parser.add_argument(
        '--rpc-url',
        required=True,
        help='RPC endpoint URL'
    )
    
    parser.add_argument(
        '--searcher',
        help='Searcher address for profit calculation (defaults to tx sender)'
    )
    
    parser.add_argument(
        '--output',
        help='Output JSON file path'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MEV-INSPECT-PYREVM: Full Pipeline Demo")
    print("=" * 60)
    print()
    
    try:
        results = run_full_pipeline(args.tx_hash, args.rpc_url, args.searcher)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"✅ Results saved to: {args.output}")
        
        print("\n🎉 Pipeline execution complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
