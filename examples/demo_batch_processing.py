#!/usr/bin/env python3
"""
Batch Processing Demo for mev-inspect-pyrevm
============================================

Process multiple transactions in batch mode with statistics tracking.
Useful for analyzing MEV activity across blocks or time periods.

Usage:
    python3 demo_batch_processing.py --tx-hashes tx1,tx2,tx3 --rpc-url http://...
    python3 demo_batch_processing.py --block 18500000 --rpc-url http://...
    python3 demo_batch_processing.py --input txs.txt --rpc-url http://...
"""

import sys
import argparse
import json
import time
from typing import List, Dict, Any
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, '/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm')

from mev_inspect.state_manager import StateManager
from mev_inspect.replay import TransactionReplayer
from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
from mev_inspect.profit_calculator import ProfitCalculator


# ========================================
# Mock RPC Client
# ========================================

class MockRPCClient:
    """Mock RPC for batch demo"""
    
    def __init__(self, url: str):
        self.url = url
        self.call_count = 0
        
    def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        self.call_count += 1
        return {
            'transactionHash': tx_hash,
            'blockNumber': 18500000,
            'gasUsed': 150000,
            'effectiveGasPrice': 30000000000,
            'logs': [
                {
                    'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                    'topics': [
                        '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                        '0x000000000000000000000000' + 'a' * 40,
                        '0x000000000000000000000000' + 'b' * 40,
                    ],
                    'data': '0x' + '0' * 63 + '5' + '0' * 64,
                    'logIndex': 10
                }
            ]
        }
    
    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        self.call_count += 1
        return {
            'hash': tx_hash,
            'from': '0x' + 'b' * 40,
            'to': '0x' + 'e' * 40,
            'value': '0x0',
            'input': '0x',
            'blockNumber': 18500000,
            'gasPrice': '0x6fc23ac00'
        }
    
    def get_block(self, block_number: int) -> Dict[str, Any]:
        """Get block with transactions"""
        self.call_count += 1
        # Generate mock transaction hashes
        tx_hashes = [f"0x{i:064x}" for i in range(1, 11)]  # 10 transactions
        return {
            'number': block_number,
            'transactions': tx_hashes,
            'timestamp': 1700000000
        }
    
    def get_code(self, address: str, block_number: int) -> str:
        self.call_count += 1
        return '0x60806040' if address.startswith('0xC02') else '0x'
    
    def call_contract(self, to: str, data: str, block_number: int) -> str:
        self.call_count += 1
        return '0x' + '0' * 63 + '12'


# ========================================
# Batch Processor
# ========================================

class BatchProcessor:
    """Process multiple transactions in batch"""
    
    def __init__(self, rpc_url: str):
        self.rpc = MockRPCClient(rpc_url)
        self.state_manager = None
        self.replayer = None
        self.swap_detector = None
        self.profit_calculator = None
        
        # Statistics
        self.stats = {
            'total_txs': 0,
            'successful_txs': 0,
            'failed_txs': 0,
            'total_swaps': 0,
            'total_profit_wei': 0,
            'profitable_txs': 0,
            'mev_types': defaultdict(int),
            'processing_times': [],
            'rpc_calls': 0
        }
    
    def initialize(self, block_number: int):
        """Initialize components for a specific block"""
        print(f"🔧 Initializing components for block {block_number}...")
        
        self.state_manager = StateManager(self.rpc, block_number, cache_size=5000)
        self.replayer = TransactionReplayer(self.rpc, self.state_manager, block_number)
        self.swap_detector = EnhancedSwapDetector(self.rpc, self.state_manager)
        self.profit_calculator = ProfitCalculator(self.rpc, self.state_manager, self.swap_detector)
        
        print(f"✅ Components initialized\n")
    
    def process_transaction(self, tx_hash: str, block_number: int) -> Dict[str, Any]:
        """Process a single transaction"""
        start_time = time.time()
        rpc_before = self.rpc.call_count
        
        result = {
            'tx_hash': tx_hash,
            'success': False,
            'swaps': 0,
            'profit_wei': 0,
            'mev_type': None,
            'error': None
        }
        
        try:
            # Get transaction
            tx = self.rpc.get_transaction(tx_hash)
            searcher = tx['from']
            
            # Detect swaps
            swaps = self.swap_detector.detect_swaps(tx_hash, block_number)
            result['swaps'] = len(swaps)
            self.stats['total_swaps'] += len(swaps)
            
            # Calculate profit
            profit = self.profit_calculator.calculate_profit(tx_hash, block_number, searcher)
            result['profit_wei'] = profit.net_profit_wei
            result['mev_type'] = profit.mev_type
            result['success'] = True
            
            # Update stats
            self.stats['successful_txs'] += 1
            if profit.net_profit_wei > 0:
                self.stats['profitable_txs'] += 1
                self.stats['total_profit_wei'] += profit.net_profit_wei
            self.stats['mev_types'][profit.mev_type] += 1
            
        except Exception as e:
            result['error'] = str(e)
            self.stats['failed_txs'] += 1
        
        # Record timing
        processing_time = time.time() - start_time
        rpc_calls = self.rpc.call_count - rpc_before
        
        result['processing_time'] = processing_time
        result['rpc_calls'] = rpc_calls
        
        self.stats['processing_times'].append(processing_time)
        self.stats['rpc_calls'] += rpc_calls
        self.stats['total_txs'] += 1
        
        return result
    
    def process_batch(self, tx_hashes: List[str], block_number: int) -> List[Dict[str, Any]]:
        """Process a batch of transactions"""
        print(f"📦 Processing {len(tx_hashes)} transactions from block {block_number}")
        print("=" * 60)
        
        # Initialize components
        self.initialize(block_number)
        
        # Process each transaction
        results = []
        for i, tx_hash in enumerate(tx_hashes, 1):
            print(f"\n[{i}/{len(tx_hashes)}] Processing {tx_hash[:10]}...")
            
            result = self.process_transaction(tx_hash, block_number)
            results.append(result)
            
            # Print summary
            if result['success']:
                profit_eth = result['profit_wei'] / 10**18
                print(f"  ✅ Swaps: {result['swaps']}, "
                      f"Profit: {profit_eth:.6f} ETH, "
                      f"Type: {result['mev_type']}")
                print(f"  ⏱️  Time: {result['processing_time']:.3f}s, "
                      f"RPC: {result['rpc_calls']} calls")
            else:
                print(f"  ❌ Failed: {result['error']}")
        
        return results
    
    def print_statistics(self):
        """Print batch processing statistics"""
        print("\n" + "=" * 60)
        print("BATCH PROCESSING STATISTICS")
        print("=" * 60)
        
        print(f"\n📊 Transaction Summary:")
        print(f"  Total processed: {self.stats['total_txs']}")
        print(f"  Successful: {self.stats['successful_txs']}")
        print(f"  Failed: {self.stats['failed_txs']}")
        if self.stats['successful_txs'] > 0:
            success_rate = self.stats['successful_txs'] / self.stats['total_txs'] * 100
            print(f"  Success rate: {success_rate:.1f}%")
        
        print(f"\n💰 Profit Summary:")
        print(f"  Profitable transactions: {self.stats['profitable_txs']}")
        total_profit_eth = self.stats['total_profit_wei'] / 10**18
        print(f"  Total profit: {total_profit_eth:.6f} ETH")
        if self.stats['profitable_txs'] > 0:
            avg_profit_eth = total_profit_eth / self.stats['profitable_txs']
            print(f"  Average profit: {avg_profit_eth:.6f} ETH")
        
        print(f"\n🔄 Swap Summary:")
        print(f"  Total swaps detected: {self.stats['total_swaps']}")
        if self.stats['successful_txs'] > 0:
            avg_swaps = self.stats['total_swaps'] / self.stats['successful_txs']
            print(f"  Average swaps per tx: {avg_swaps:.2f}")
        
        print(f"\n🎯 MEV Type Distribution:")
        for mev_type, count in sorted(self.stats['mev_types'].items(), key=lambda x: x[1], reverse=True):
            percentage = count / self.stats['successful_txs'] * 100 if self.stats['successful_txs'] > 0 else 0
            print(f"  {mev_type}: {count} ({percentage:.1f}%)")
        
        print(f"\n⚡ Performance:")
        if self.stats['processing_times']:
            avg_time = sum(self.stats['processing_times']) / len(self.stats['processing_times'])
            min_time = min(self.stats['processing_times'])
            max_time = max(self.stats['processing_times'])
            print(f"  Average time per tx: {avg_time:.3f}s")
            print(f"  Min time: {min_time:.3f}s")
            print(f"  Max time: {max_time:.3f}s")
            
            total_time = sum(self.stats['processing_times'])
            throughput = len(self.stats['processing_times']) / total_time if total_time > 0 else 0
            print(f"  Throughput: {throughput:.2f} tx/s")
        
        print(f"\n🌐 RPC Efficiency:")
        print(f"  Total RPC calls: {self.stats['rpc_calls']}")
        if self.stats['total_txs'] > 0:
            avg_rpc = self.stats['rpc_calls'] / self.stats['total_txs']
            print(f"  Average RPC per tx: {avg_rpc:.1f}")
        
        # Cache stats
        if self.state_manager:
            cache_stats = self.state_manager.get_cache_stats()
            if cache_stats['total_requests'] > 0:
                hit_rate = cache_stats['cache_hits'] / cache_stats['total_requests'] * 100
                print(f"  Cache hit rate: {hit_rate:.1f}%")
                print(f"  Cache hits: {cache_stats['cache_hits']}")
                print(f"  Cache misses: {cache_stats['cache_misses']}")


# ========================================
# Main
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description='Batch Processing Demo for mev-inspect-pyrevm',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process specific transactions
    python3 demo_batch_processing.py --tx-hashes 0xabc...,0xdef... --rpc-url http://localhost:8545
    
    # Process all transactions in a block
    python3 demo_batch_processing.py --block 18500000 --rpc-url http://localhost:8545
    
    # Process from file (one tx hash per line)
    python3 demo_batch_processing.py --input transactions.txt --rpc-url http://localhost:8545
    
    # Save results to JSON
    python3 demo_batch_processing.py --block 18500000 --rpc-url http://localhost:8545 --output results.json
        """
    )
    
    parser.add_argument(
        '--tx-hashes',
        help='Comma-separated transaction hashes'
    )
    
    parser.add_argument(
        '--block',
        type=int,
        help='Block number to process all transactions from'
    )
    
    parser.add_argument(
        '--input',
        help='Input file with transaction hashes (one per line)'
    )
    
    parser.add_argument(
        '--rpc-url',
        required=True,
        help='RPC endpoint URL'
    )
    
    parser.add_argument(
        '--output',
        help='Output JSON file for results'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of transactions to process'
    )
    
    args = parser.parse_args()
    
    # Collect transaction hashes
    tx_hashes = []
    block_number = 18500000  # Default
    
    if args.tx_hashes:
        tx_hashes = [tx.strip() for tx in args.tx_hashes.split(',')]
    elif args.block:
        print(f"📦 Fetching transactions from block {args.block}...")
        rpc = MockRPCClient(args.rpc_url)
        block = rpc.get_block(args.block)
        tx_hashes = block['transactions']
        block_number = args.block
        print(f"Found {len(tx_hashes)} transactions\n")
    elif args.input:
        print(f"📄 Reading transactions from {args.input}...")
        with open(args.input, 'r') as f:
            tx_hashes = [line.strip() for line in f if line.strip()]
        print(f"Found {len(tx_hashes)} transactions\n")
    else:
        print("❌ Error: Must specify --tx-hashes, --block, or --input")
        sys.exit(1)
    
    # Apply limit
    if args.limit and len(tx_hashes) > args.limit:
        print(f"⚠️  Limiting to {args.limit} transactions (from {len(tx_hashes)})\n")
        tx_hashes = tx_hashes[:args.limit]
    
    # Process batch
    print("=" * 60)
    print("MEV-INSPECT-PYREVM: Batch Processing Demo")
    print("=" * 60)
    print()
    
    try:
        processor = BatchProcessor(args.rpc_url)
        results = processor.process_batch(tx_hashes, block_number)
        
        # Print statistics
        processor.print_statistics()
        
        # Save results
        if args.output:
            output_data = {
                'block_number': block_number,
                'total_transactions': len(tx_hashes),
                'results': results,
                'statistics': dict(processor.stats)
            }
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {args.output}")
        
        print("\n🎉 Batch processing complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
