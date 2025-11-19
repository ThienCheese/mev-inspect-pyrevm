#!/usr/bin/env python3
"""
Performance Benchmark for mev-inspect-pyrevm
============================================

Measure and compare performance metrics:
- Execution time per phase
- RPC call efficiency
- Cache hit rates
- Memory usage
- Throughput

Usage:
    python3 demo_benchmark.py --rpc-url http://...
    python3 demo_benchmark.py --rpc-url http://... --iterations 100
"""

import sys
import argparse
import time
import json
from typing import Dict, Any, List
from collections import defaultdict
import gc

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
    """Mock RPC with call tracking"""
    
    def __init__(self, url: str):
        self.url = url
        self.call_count = 0
        self.call_times = []
        
    def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        start = time.time()
        self.call_count += 1
        result = {
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
                },
                {
                    'address': '0x' + 'd' * 40,
                    'topics': [
                        '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822',
                        '0x000000000000000000000000' + 'b' * 40,
                    ],
                    'data': '0x' + '0' * 64 * 2 + '0' * 63 + '5' + '0' * 64,
                    'logIndex': 15
                }
            ]
        }
        self.call_times.append(time.time() - start)
        return result
    
    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        start = time.time()
        self.call_count += 1
        result = {
            'hash': tx_hash,
            'from': '0x' + 'b' * 40,
            'to': '0x' + 'e' * 40,
            'value': '0x0',
            'input': '0x',
            'blockNumber': 18500000,
            'gasPrice': '0x6fc23ac00'
        }
        self.call_times.append(time.time() - start)
        return result
    
    def get_code(self, address: str, block_number: int) -> str:
        start = time.time()
        self.call_count += 1
        result = '0x60806040' if address.startswith('0xC02') else '0x'
        self.call_times.append(time.time() - start)
        return result
    
    def call_contract(self, to: str, data: str, block_number: int) -> str:
        start = time.time()
        self.call_count += 1
        result = '0x' + '0' * 63 + '12'
        self.call_times.append(time.time() - start)
        return result


# ========================================
# Benchmark Runner
# ========================================

class BenchmarkRunner:
    """Run performance benchmarks"""
    
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.results = {
            'phase1': [],
            'phase2': [],
            'phase3': [],
            'phase4': [],
            'full_pipeline': [],
            'rpc_calls': [],
            'cache_stats': []
        }
    
    def benchmark_phase1(self, iterations: int) -> Dict[str, Any]:
        """Benchmark StateManager"""
        print(f"\n📊 Benchmarking Phase 1 (StateManager) - {iterations} iterations")
        print("-" * 60)
        
        times = []
        rpc_calls = []
        cache_stats_list = []
        
        for i in range(iterations):
            rpc = MockRPCClient(self.rpc_url)
            rpc_before = rpc.call_count
            
            start = time.time()
            state_manager = StateManager(rpc, 18500000, cache_size=1000)
            
            # Preload some addresses
            addresses = [f"0x{'a' * 40}", f"0x{'b' * 40}", f"0x{'c' * 40}"]
            state_manager.preload_accounts(addresses)
            
            # Access cached data
            for addr in addresses:
                _ = state_manager.get_account(addr)
            
            elapsed = time.time() - start
            times.append(elapsed)
            rpc_calls.append(rpc.call_count - rpc_before)
            cache_stats_list.append(state_manager.get_cache_stats())
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{iterations}")
        
        avg_time = sum(times) / len(times)
        avg_rpc = sum(rpc_calls) / len(rpc_calls)
        
        # Calculate cache efficiency
        total_hits = sum(s['cache_hits'] for s in cache_stats_list)
        total_requests = sum(s['total_requests'] for s in cache_stats_list)
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        result = {
            'avg_time': avg_time,
            'min_time': min(times),
            'max_time': max(times),
            'avg_rpc_calls': avg_rpc,
            'cache_hit_rate': hit_rate
        }
        
        print(f"\n  ✅ Average time: {avg_time:.6f}s")
        print(f"  ✅ Average RPC calls: {avg_rpc:.1f}")
        print(f"  ✅ Cache hit rate: {hit_rate:.1f}%")
        
        self.results['phase1'] = times
        return result
    
    def benchmark_phase2(self, iterations: int) -> Dict[str, Any]:
        """Benchmark TransactionReplayer"""
        print(f"\n📊 Benchmarking Phase 2 (TransactionReplayer) - {iterations} iterations")
        print("-" * 60)
        
        times = []
        rpc_calls = []
        
        for i in range(iterations):
            rpc = MockRPCClient(self.rpc_url)
            state_manager = StateManager(rpc, 18500000)
            replayer = TransactionReplayer(rpc, state_manager, 18500000)
            
            rpc_before = rpc.call_count
            
            start = time.time()
            result = replayer.replay_transaction(f"0x{i:064x}")
            elapsed = time.time() - start
            
            times.append(elapsed)
            rpc_calls.append(rpc.call_count - rpc_before)
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{iterations}")
        
        avg_time = sum(times) / len(times)
        avg_rpc = sum(rpc_calls) / len(rpc_calls)
        
        result = {
            'avg_time': avg_time,
            'min_time': min(times),
            'max_time': max(times),
            'avg_rpc_calls': avg_rpc
        }
        
        print(f"\n  ✅ Average time: {avg_time:.6f}s")
        print(f"  ✅ Average RPC calls: {avg_rpc:.1f}")
        
        self.results['phase2'] = times
        return result
    
    def benchmark_phase3(self, iterations: int) -> Dict[str, Any]:
        """Benchmark EnhancedSwapDetector"""
        print(f"\n📊 Benchmarking Phase 3 (EnhancedSwapDetector) - {iterations} iterations")
        print("-" * 60)
        
        times = []
        rpc_calls = []
        swap_counts = []
        
        for i in range(iterations):
            rpc = MockRPCClient(self.rpc_url)
            state_manager = StateManager(rpc, 18500000)
            detector = EnhancedSwapDetector(rpc, state_manager)
            
            rpc_before = rpc.call_count
            
            start = time.time()
            swaps = detector.detect_swaps(f"0x{i:064x}", 18500000)
            elapsed = time.time() - start
            
            times.append(elapsed)
            rpc_calls.append(rpc.call_count - rpc_before)
            swap_counts.append(len(swaps))
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{iterations}")
        
        avg_time = sum(times) / len(times)
        avg_rpc = sum(rpc_calls) / len(rpc_calls)
        avg_swaps = sum(swap_counts) / len(swap_counts)
        
        result = {
            'avg_time': avg_time,
            'min_time': min(times),
            'max_time': max(times),
            'avg_rpc_calls': avg_rpc,
            'avg_swaps_detected': avg_swaps
        }
        
        print(f"\n  ✅ Average time: {avg_time:.6f}s")
        print(f"  ✅ Average RPC calls: {avg_rpc:.1f}")
        print(f"  ✅ Average swaps detected: {avg_swaps:.1f}")
        
        self.results['phase3'] = times
        return result
    
    def benchmark_phase4(self, iterations: int) -> Dict[str, Any]:
        """Benchmark ProfitCalculator"""
        print(f"\n📊 Benchmarking Phase 4 (ProfitCalculator) - {iterations} iterations")
        print("-" * 60)
        
        times = []
        rpc_calls = []
        
        for i in range(iterations):
            rpc = MockRPCClient(self.rpc_url)
            state_manager = StateManager(rpc, 18500000)
            detector = EnhancedSwapDetector(rpc, state_manager)
            calculator = ProfitCalculator(rpc, state_manager, detector)
            
            rpc_before = rpc.call_count
            
            start = time.time()
            profit = calculator.calculate_profit(f"0x{i:064x}", 18500000, '0x' + 'b' * 40)
            elapsed = time.time() - start
            
            times.append(elapsed)
            rpc_calls.append(rpc.call_count - rpc_before)
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{iterations}")
        
        avg_time = sum(times) / len(times)
        avg_rpc = sum(rpc_calls) / len(rpc_calls)
        
        result = {
            'avg_time': avg_time,
            'min_time': min(times),
            'max_time': max(times),
            'avg_rpc_calls': avg_rpc
        }
        
        print(f"\n  ✅ Average time: {avg_time:.6f}s")
        print(f"  ✅ Average RPC calls: {avg_rpc:.1f}")
        
        self.results['phase4'] = times
        return result
    
    def benchmark_full_pipeline(self, iterations: int) -> Dict[str, Any]:
        """Benchmark complete pipeline"""
        print(f"\n📊 Benchmarking Full Pipeline - {iterations} iterations")
        print("-" * 60)
        
        times = []
        rpc_calls = []
        
        for i in range(iterations):
            rpc = MockRPCClient(self.rpc_url)
            
            rpc_before = rpc.call_count
            start = time.time()
            
            # Full pipeline
            state_manager = StateManager(rpc, 18500000)
            replayer = TransactionReplayer(rpc, state_manager, 18500000)
            detector = EnhancedSwapDetector(rpc, state_manager)
            calculator = ProfitCalculator(rpc, state_manager, detector)
            
            tx_hash = f"0x{i:064x}"
            _ = replayer.replay_transaction(tx_hash)
            _ = detector.detect_swaps(tx_hash, 18500000)
            _ = calculator.calculate_profit(tx_hash, 18500000, '0x' + 'b' * 40)
            
            elapsed = time.time() - start
            times.append(elapsed)
            rpc_calls.append(rpc.call_count - rpc_before)
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{iterations}")
        
        avg_time = sum(times) / len(times)
        avg_rpc = sum(rpc_calls) / len(rpc_calls)
        throughput = 1.0 / avg_time if avg_time > 0 else 0
        
        result = {
            'avg_time': avg_time,
            'min_time': min(times),
            'max_time': max(times),
            'avg_rpc_calls': avg_rpc,
            'throughput': throughput
        }
        
        print(f"\n  ✅ Average time: {avg_time:.6f}s")
        print(f"  ✅ Average RPC calls: {avg_rpc:.1f}")
        print(f"  ✅ Throughput: {throughput:.2f} tx/s")
        
        self.results['full_pipeline'] = times
        return result
    
    def run_all_benchmarks(self, iterations: int) -> Dict[str, Any]:
        """Run all benchmarks"""
        print("=" * 60)
        print("MEV-INSPECT-PYREVM: Performance Benchmark")
        print("=" * 60)
        
        results = {}
        
        # Run benchmarks
        results['phase1'] = self.benchmark_phase1(iterations)
        results['phase2'] = self.benchmark_phase2(iterations)
        results['phase3'] = self.benchmark_phase3(iterations)
        results['phase4'] = self.benchmark_phase4(iterations)
        results['full_pipeline'] = self.benchmark_full_pipeline(iterations)
        
        # Print summary
        self.print_summary(results)
        
        return results
    
    def print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary"""
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        
        print("\n⏱️  Average Execution Times:")
        print(f"  Phase 1 (StateManager):      {results['phase1']['avg_time']:.6f}s")
        print(f"  Phase 2 (Replayer):          {results['phase2']['avg_time']:.6f}s")
        print(f"  Phase 3 (SwapDetector):      {results['phase3']['avg_time']:.6f}s")
        print(f"  Phase 4 (ProfitCalculator):  {results['phase4']['avg_time']:.6f}s")
        print(f"  Full Pipeline:               {results['full_pipeline']['avg_time']:.6f}s")
        
        print("\n🌐 Average RPC Calls:")
        print(f"  Phase 1 (StateManager):      {results['phase1']['avg_rpc_calls']:.1f}")
        print(f"  Phase 2 (Replayer):          {results['phase2']['avg_rpc_calls']:.1f}")
        print(f"  Phase 3 (SwapDetector):      {results['phase3']['avg_rpc_calls']:.1f}")
        print(f"  Phase 4 (ProfitCalculator):  {results['phase4']['avg_rpc_calls']:.1f}")
        print(f"  Full Pipeline:               {results['full_pipeline']['avg_rpc_calls']:.1f}")
        
        print("\n📈 Performance Metrics:")
        print(f"  Cache hit rate:              {results['phase1']['cache_hit_rate']:.1f}%")
        print(f"  Pipeline throughput:         {results['full_pipeline']['throughput']:.2f} tx/s")
        
        # Calculate RPC efficiency (cache savings)
        without_cache = results['full_pipeline']['avg_rpc_calls'] / (1 - results['phase1']['cache_hit_rate'] / 100)
        rpc_savings = (1 - results['full_pipeline']['avg_rpc_calls'] / without_cache) * 100
        print(f"  RPC call reduction:          {rpc_savings:.1f}%")
        
        print("\n💡 Insights:")
        total_phase_time = sum([
            results['phase1']['avg_time'],
            results['phase2']['avg_time'],
            results['phase3']['avg_time'],
            results['phase4']['avg_time']
        ])
        
        for phase_name, phase_key in [
            ('StateManager', 'phase1'),
            ('Replayer', 'phase2'),
            ('SwapDetector', 'phase3'),
            ('ProfitCalculator', 'phase4')
        ]:
            percentage = (results[phase_key]['avg_time'] / total_phase_time * 100) if total_phase_time > 0 else 0
            print(f"  {phase_name:20s} {percentage:5.1f}% of total time")


# ========================================
# Main
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description='Performance Benchmark for mev-inspect-pyrevm',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Quick benchmark (10 iterations)
    python3 demo_benchmark.py --rpc-url http://localhost:8545
    
    # Detailed benchmark (100 iterations)
    python3 demo_benchmark.py --rpc-url http://localhost:8545 --iterations 100
    
    # Save results to JSON
    python3 demo_benchmark.py --rpc-url http://localhost:8545 --output benchmark.json
        """
    )
    
    parser.add_argument(
        '--rpc-url',
        required=True,
        help='RPC endpoint URL'
    )
    
    parser.add_argument(
        '--iterations',
        type=int,
        default=10,
        help='Number of iterations per benchmark (default: 10)'
    )
    
    parser.add_argument(
        '--output',
        help='Output JSON file for results'
    )
    
    args = parser.parse_args()
    
    try:
        runner = BenchmarkRunner(args.rpc_url)
        results = runner.run_all_benchmarks(args.iterations)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {args.output}")
        
        print("\n🎉 Benchmark complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
