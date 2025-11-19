#!/usr/bin/env python3
"""
MEV Transaction Finder Demo
===========================

Scan blocks to find and analyze MEV transactions:
- Find transactions with swaps
- Identify profitable MEV activities
- Classify MEV types (arbitrage, sandwich, etc.)
- Export results for analysis

Usage:
    python3 demo_mev_finder.py --start-block 18500000 --end-block 18500010 --rpc-url http://...
    python3 demo_mev_finder.py --block 18500000 --rpc-url http://... --min-profit 0.1
"""

import sys
import argparse
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import asdict

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
    """Mock RPC for demo"""
    
    def __init__(self, url: str):
        self.url = url
        self.call_count = 0
        
    def get_block(self, block_number: int) -> Dict[str, Any]:
        """Get block with transactions"""
        self.call_count += 1
        # Generate mock transaction hashes
        # Simulate: 3 MEV txs, 7 normal txs per block
        tx_hashes = []
        for i in range(10):
            tx_hash = f"0x{block_number:08x}{i:056x}"
            tx_hashes.append(tx_hash)
        
        return {
            'number': block_number,
            'transactions': tx_hashes,
            'timestamp': 1700000000 + (block_number - 18500000) * 12
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
    
    def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        self.call_count += 1
        # Simulate MEV tx with more logs
        is_mev = int(tx_hash[-2:], 16) % 3 == 0  # Every 3rd tx is MEV
        
        logs = []
        if is_mev:
            # MEV transaction: multiple swaps and transfers
            for i in range(3):
                logs.append({
                    'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                    'topics': [
                        '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                        '0x000000000000000000000000' + 'a' * 40,
                        '0x000000000000000000000000' + 'b' * 40,
                    ],
                    'data': '0x' + '0' * 63 + str(i + 1) + '0' * 64,
                    'logIndex': i * 2
                })
                logs.append({
                    'address': '0x' + 'd' * 40,
                    'topics': [
                        '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822',
                        '0x000000000000000000000000' + 'b' * 40,
                    ],
                    'data': '0x' + '0' * 64 * 2 + '0' * 63 + str(i + 1) + '0' * 64,
                    'logIndex': i * 2 + 1
                })
        
        return {
            'transactionHash': tx_hash,
            'blockNumber': 18500000,
            'gasUsed': 200000 if is_mev else 50000,
            'effectiveGasPrice': 30000000000,
            'logs': logs
        }
    
    def get_code(self, address: str, block_number: int) -> str:
        self.call_count += 1
        return '0x60806040' if address.startswith('0xC02') else '0x'
    
    def call_contract(self, to: str, data: str, block_number: int) -> str:
        self.call_count += 1
        return '0x' + '0' * 63 + '12'


# ========================================
# MEV Finder
# ========================================

class MEVFinder:
    """Find and analyze MEV transactions"""
    
    def __init__(self, rpc_url: str):
        self.rpc = MockRPCClient(rpc_url)
        self.found_mev = []
        
        # Statistics
        self.stats = {
            'blocks_scanned': 0,
            'txs_analyzed': 0,
            'mev_found': 0,
            'total_profit_eth': 0.0,
            'mev_by_type': {},
            'scan_time': 0.0
        }
    
    def scan_block(self, block_number: int, min_profit_eth: float = 0.0) -> List[Dict[str, Any]]:
        """Scan a single block for MEV transactions"""
        
        # Initialize components for this block
        state_manager = StateManager(self.rpc, block_number, cache_size=5000)
        replayer = TransactionReplayer(self.rpc, state_manager, block_number)
        detector = EnhancedSwapDetector(self.rpc, state_manager)
        calculator = ProfitCalculator(self.rpc, state_manager, detector)
        
        # Get block
        block = self.rpc.get_block(block_number)
        tx_hashes = block['transactions']
        
        mev_txs = []
        
        for tx_hash in tx_hashes:
            try:
                # Get transaction
                tx = self.rpc.get_transaction(tx_hash)
                searcher = tx['from']
                
                # Quick filter: check for swaps
                swaps = detector.detect_swaps(tx_hash, block_number)
                if not swaps:
                    continue  # Skip if no swaps detected
                
                # Calculate profit
                profit = calculator.calculate_profit(tx_hash, block_number, searcher)
                profit_eth = profit.net_profit_wei / 10**18
                
                # Filter by minimum profit
                if profit_eth < min_profit_eth:
                    continue
                
                # Found MEV!
                mev_tx = {
                    'tx_hash': tx_hash,
                    'block': block_number,
                    'searcher': searcher,
                    'profit_eth': profit_eth,
                    'gas_used': profit.gas_cost_wei / 10**18,
                    'mev_type': profit.mev_type,
                    'swaps': len(swaps),
                    'confidence': profit.confidence
                }
                
                mev_txs.append(mev_tx)
                self.found_mev.append(mev_tx)
                
                # Update stats
                self.stats['mev_found'] += 1
                self.stats['total_profit_eth'] += profit_eth
                self.stats['mev_by_type'][profit.mev_type] = \
                    self.stats['mev_by_type'].get(profit.mev_type, 0) + 1
                
            except Exception as e:
                # Skip failed transactions
                pass
            
            self.stats['txs_analyzed'] += 1
        
        self.stats['blocks_scanned'] += 1
        return mev_txs
    
    def scan_range(self, start_block: int, end_block: int, min_profit_eth: float = 0.0) -> List[Dict[str, Any]]:
        """Scan a range of blocks for MEV"""
        print(f"🔍 Scanning blocks {start_block} to {end_block}")
        print("=" * 60)
        
        start_time = time.time()
        all_mev = []
        
        for block_num in range(start_block, end_block + 1):
            print(f"\n📦 Block {block_num}")
            
            mev_txs = self.scan_block(block_num, min_profit_eth)
            all_mev.extend(mev_txs)
            
            if mev_txs:
                print(f"  ✅ Found {len(mev_txs)} MEV transaction(s)")
                for i, mev in enumerate(mev_txs, 1):
                    print(f"     {i}. {mev['tx_hash'][:10]}... "
                          f"Profit: {mev['profit_eth']:.6f} ETH "
                          f"Type: {mev['mev_type']}")
            else:
                print(f"  ⚪ No MEV found")
        
        self.stats['scan_time'] = time.time() - start_time
        return all_mev
    
    def print_summary(self):
        """Print scan summary"""
        print("\n" + "=" * 60)
        print("MEV SCAN SUMMARY")
        print("=" * 60)
        
        print(f"\n📊 Scan Statistics:")
        print(f"  Blocks scanned: {self.stats['blocks_scanned']}")
        print(f"  Transactions analyzed: {self.stats['txs_analyzed']}")
        print(f"  MEV transactions found: {self.stats['mev_found']}")
        
        if self.stats['txs_analyzed'] > 0:
            mev_rate = self.stats['mev_found'] / self.stats['txs_analyzed'] * 100
            print(f"  MEV rate: {mev_rate:.2f}%")
        
        print(f"\n💰 Profit Summary:")
        print(f"  Total profit: {self.stats['total_profit_eth']:.6f} ETH")
        
        if self.stats['mev_found'] > 0:
            avg_profit = self.stats['total_profit_eth'] / self.stats['mev_found']
            print(f"  Average profit: {avg_profit:.6f} ETH")
            
            # Find most profitable
            most_profitable = max(self.found_mev, key=lambda x: x['profit_eth'])
            print(f"  Highest profit: {most_profitable['profit_eth']:.6f} ETH")
            print(f"    Transaction: {most_profitable['tx_hash']}")
        
        print(f"\n🎯 MEV Type Distribution:")
        for mev_type, count in sorted(self.stats['mev_by_type'].items(), key=lambda x: x[1], reverse=True):
            percentage = count / self.stats['mev_found'] * 100 if self.stats['mev_found'] > 0 else 0
            print(f"  {mev_type}: {count} ({percentage:.1f}%)")
        
        print(f"\n⏱️  Performance:")
        print(f"  Total scan time: {self.stats['scan_time']:.2f}s")
        if self.stats['blocks_scanned'] > 0:
            avg_time_per_block = self.stats['scan_time'] / self.stats['blocks_scanned']
            print(f"  Average per block: {avg_time_per_block:.2f}s")
        if self.stats['txs_analyzed'] > 0:
            avg_time_per_tx = self.stats['scan_time'] / self.stats['txs_analyzed']
            print(f"  Average per tx: {avg_time_per_tx:.4f}s")
    
    def export_results(self, output_file: str):
        """Export found MEV to JSON"""
        data = {
            'statistics': self.stats,
            'mev_transactions': self.found_mev
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"\n💾 Results exported to: {output_file}")
    
    def print_top_mev(self, limit: int = 10):
        """Print top MEV transactions by profit"""
        if not self.found_mev:
            return
        
        print("\n" + "=" * 60)
        print(f"TOP {min(limit, len(self.found_mev))} MEV TRANSACTIONS")
        print("=" * 60)
        
        sorted_mev = sorted(self.found_mev, key=lambda x: x['profit_eth'], reverse=True)
        
        for i, mev in enumerate(sorted_mev[:limit], 1):
            print(f"\n{i}. Transaction: {mev['tx_hash']}")
            print(f"   Block: {mev['block']}")
            print(f"   Searcher: {mev['searcher']}")
            print(f"   Profit: {mev['profit_eth']:.6f} ETH")
            print(f"   Gas Cost: {mev['gas_used']:.6f} ETH")
            print(f"   MEV Type: {mev['mev_type']}")
            print(f"   Swaps: {mev['swaps']}")
            print(f"   Confidence: {mev['confidence']:.2f}")


# ========================================
# Main
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description='MEV Transaction Finder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scan a single block
    python3 demo_mev_finder.py --block 18500000 --rpc-url http://localhost:8545
    
    # Scan a range of blocks
    python3 demo_mev_finder.py --start-block 18500000 --end-block 18500010 --rpc-url http://localhost:8545
    
    # Filter by minimum profit
    python3 demo_mev_finder.py --block 18500000 --rpc-url http://localhost:8545 --min-profit 0.1
    
    # Export results
    python3 demo_mev_finder.py --start-block 18500000 --end-block 18500010 --rpc-url http://localhost:8545 --output mev.json
        """
    )
    
    parser.add_argument(
        '--block',
        type=int,
        help='Single block number to scan'
    )
    
    parser.add_argument(
        '--start-block',
        type=int,
        help='Start block number for range scan'
    )
    
    parser.add_argument(
        '--end-block',
        type=int,
        help='End block number for range scan'
    )
    
    parser.add_argument(
        '--rpc-url',
        required=True,
        help='RPC endpoint URL'
    )
    
    parser.add_argument(
        '--min-profit',
        type=float,
        default=0.0,
        help='Minimum profit in ETH to report (default: 0.0)'
    )
    
    parser.add_argument(
        '--output',
        help='Output JSON file for results'
    )
    
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Show top N MEV transactions (default: 10)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.block:
        start_block = end_block = args.block
    elif args.start_block and args.end_block:
        start_block = args.start_block
        end_block = args.end_block
    else:
        print("❌ Error: Must specify --block or both --start-block and --end-block")
        sys.exit(1)
    
    print("=" * 60)
    print("MEV-INSPECT-PYREVM: MEV Transaction Finder")
    print("=" * 60)
    print()
    
    try:
        finder = MEVFinder(args.rpc_url)
        
        # Scan blocks
        mev_txs = finder.scan_range(start_block, end_block, args.min_profit)
        
        # Print results
        finder.print_summary()
        finder.print_top_mev(args.top)
        
        # Export if requested
        if args.output:
            finder.export_results(args.output)
        
        print("\n🎉 MEV scan complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
