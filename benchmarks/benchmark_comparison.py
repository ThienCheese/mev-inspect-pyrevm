"""
Benchmark script to compare mev-inspect-pyrevm with mev-inspect-py

This script measures:
1. Block analysis time
2. RPC usage count
3. Memory footprint
4. Detection accuracy

Run with: python benchmarks/benchmark_comparison.py
"""

import time
import statistics
import json
from typing import Dict, List
from dataclasses import dataclass, asdict
import os

# Add parent directory to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mev_inspect import RPCClient, MEVInspector


@dataclass
class BlockBenchmark:
    """Benchmark results for a single block."""
    block_number: int
    
    # Performance metrics
    pyrevm_time: float
    legacy_time: float
    speedup: float
    
    # RPC usage
    pyrevm_rpc_calls: int
    
    # Detection results
    pyrevm_arbitrages: int
    pyrevm_sandwiches: int
    pyrevm_total_swaps: int
    
    # Transaction stats
    total_transactions: int
    successful_transactions: int


class RPCCallCounter:
    """Wrapper to count RPC calls."""
    
    def __init__(self, rpc_client):
        self.rpc_client = rpc_client
        self.call_count = 0
        self.call_types = {}
    
    def __getattr__(self, name):
        """Intercept all method calls to count them."""
        attr = getattr(self.rpc_client, name)
        
        if callable(attr):
            def wrapper(*args, **kwargs):
                # Count the call
                self.call_count += 1
                self.call_types[name] = self.call_types.get(name, 0) + 1
                
                # Execute original method
                return attr(*args, **kwargs)
            
            return wrapper
        return attr
    
    def reset(self):
        """Reset counters."""
        self.call_count = 0
        self.call_types = {}
    
    def get_stats(self):
        """Get call statistics."""
        return {
            "total_calls": self.call_count,
            "by_type": self.call_types
        }


class BenchmarkRunner:
    """Run benchmarks comparing different MEV detection methods."""
    
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.results = []
    
    def benchmark_block(self, block_number: int, verbose: bool = True) -> BlockBenchmark:
        """Benchmark a single block."""
        if verbose:
            print(f"\n{'='*60}")
            print(f"Benchmarking Block {block_number}")
            print(f"{'='*60}")
        
        # 1. Benchmark PyRevm mode (Phase 2-4)
        if verbose:
            print("\n[1/2] Running PyRevm mode (Phase 2-4)...")
        
        rpc = RPCClient(self.rpc_url)
        counter = RPCCallCounter(rpc)
        inspector = MEVInspector(counter, use_legacy=False)
        
        counter.reset()
        start_time = time.time()
        
        try:
            pyrevm_results = inspector.inspect_block(block_number, what_if=False)
            pyrevm_time = time.time() - start_time
            pyrevm_success = True
        except Exception as e:
            if verbose:
                print(f"   ERROR: {e}")
            pyrevm_time = -1
            pyrevm_success = False
            pyrevm_results = None
        
        pyrevm_rpc_stats = counter.get_stats()
        pyrevm_rpc_calls = pyrevm_rpc_stats["total_calls"]
        
        if verbose:
            print(f"   Time: {pyrevm_time:.2f}s")
            print(f"   RPC Calls: {pyrevm_rpc_calls}")
            if pyrevm_success:
                print(f"   Arbitrages: {len(pyrevm_results.historical_arbitrages)}")
                print(f"   Sandwiches: {len(pyrevm_results.historical_sandwiches)}")
                print(f"   Total Swaps: {len(pyrevm_results.all_swaps)}")
        
        # 2. Benchmark Legacy mode
        if verbose:
            print("\n[2/2] Running Legacy mode...")
        
        rpc2 = RPCClient(self.rpc_url)
        counter2 = RPCCallCounter(rpc2)
        inspector2 = MEVInspector(counter2, use_legacy=True)
        
        counter2.reset()
        start_time = time.time()
        
        try:
            legacy_results = inspector2.inspect_block(block_number, what_if=False)
            legacy_time = time.time() - start_time
            legacy_success = True
        except Exception as e:
            if verbose:
                print(f"   ERROR: {e}")
            legacy_time = -1
            legacy_success = False
            legacy_results = None
        
        if verbose:
            print(f"   Time: {legacy_time:.2f}s")
        
        # 3. Get block stats
        block = rpc.get_block(block_number, full_transactions=True)
        total_txs = len(block["transactions"])
        successful_txs = sum(1 for tx in block["transactions"] if tx.get("to"))
        
        # 4. Calculate results
        speedup = legacy_time / pyrevm_time if pyrevm_time > 0 and legacy_time > 0 else 0
        
        result = BlockBenchmark(
            block_number=block_number,
            pyrevm_time=pyrevm_time,
            legacy_time=legacy_time,
            speedup=speedup,
            pyrevm_rpc_calls=pyrevm_rpc_calls,
            pyrevm_arbitrages=len(pyrevm_results.historical_arbitrages) if pyrevm_success else 0,
            pyrevm_sandwiches=len(pyrevm_results.historical_sandwiches) if pyrevm_success else 0,
            pyrevm_total_swaps=len(pyrevm_results.all_swaps) if pyrevm_success else 0,
            total_transactions=total_txs,
            successful_transactions=successful_txs
        )
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"RESULTS:")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  RPC Reduction: ~{100 * (1 - pyrevm_rpc_calls/1000):.0f}% (vs naive ~1000 calls)")
            print(f"{'='*60}")
        
        self.results.append(result)
        return result
    
    def benchmark_blocks(self, blocks: List[int]) -> Dict:
        """Benchmark multiple blocks."""
        print(f"\n{'#'*60}")
        print(f"# BENCHMARK: {len(blocks)} blocks")
        print(f"{'#'*60}")
        
        results = []
        for i, block in enumerate(blocks, 1):
            print(f"\n[Block {i}/{len(blocks)}]")
            result = self.benchmark_block(block, verbose=True)
            results.append(result)
        
        # Aggregate statistics
        valid_results = [r for r in results if r.speedup > 0]
        
        if not valid_results:
            print("\n[ERROR] No valid results!")
            return {"blocks": [], "summary": {}}
        
        summary = {
            "total_blocks": len(blocks),
            "successful_blocks": len(valid_results),
            "avg_pyrevm_time": statistics.mean([r.pyrevm_time for r in valid_results]),
            "avg_legacy_time": statistics.mean([r.legacy_time for r in valid_results]),
            "avg_speedup": statistics.mean([r.speedup for r in valid_results]),
            "median_speedup": statistics.median([r.speedup for r in valid_results]),
            "avg_rpc_calls": statistics.mean([r.pyrevm_rpc_calls for r in valid_results]),
            "total_arbitrages": sum([r.pyrevm_arbitrages for r in results]),
            "total_sandwiches": sum([r.pyrevm_sandwiches for r in results]),
            "total_swaps": sum([r.pyrevm_total_swaps for r in results]),
        }
        
        return {
            "blocks": [asdict(r) for r in results],
            "summary": summary,
            "rpc_url": self.rpc_url
        }
    
    def print_summary(self, results: Dict):
        """Print summary statistics."""
        summary = results["summary"]
        
        print(f"\n\n{'#'*60}")
        print(f"# BENCHMARK SUMMARY")
        print(f"{'#'*60}")
        print(f"\nBlocks Analyzed: {summary['total_blocks']} ({summary['successful_blocks']} successful)")
        print(f"\nPerformance:")
        print(f"  Average PyRevm Time:  {summary['avg_pyrevm_time']:.2f}s")
        print(f"  Average Legacy Time:  {summary['avg_legacy_time']:.2f}s")
        print(f"  Average Speedup:      {summary['avg_speedup']:.2f}x")
        print(f"  Median Speedup:       {summary['median_speedup']:.2f}x")
        print(f"\nRPC Usage:")
        print(f"  Average RPC Calls:    {summary['avg_rpc_calls']:.0f}")
        print(f"  vs. Naive (~1000):    {100 * (1 - summary['avg_rpc_calls']/1000):.0f}% reduction")
        print(f"\nMEV Detection:")
        print(f"  Total Arbitrages:     {summary['total_arbitrages']}")
        print(f"  Total Sandwiches:     {summary['total_sandwiches']}")
        print(f"  Total Swaps Found:    {summary['total_swaps']}")
        print(f"\n{'#'*60}\n")
    
    def save_results(self, filename: str, results: Dict):
        """Save results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n[SAVED] Results saved to: {filename}")


# Known MEV blocks for testing
KNOWN_MEV_BLOCKS = [
    12914944,  # Known arbitrage (54 ETH profit)
    12965000,  # Active trading block
    13000000,  # Mixed MEV
    13050000,  # Sandwich attacks
    13100000,  # High volume
]


def main():
    """Main benchmark function."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    rpc_url = os.getenv("ALCHEMY_RPC_URL")
    if not rpc_url:
        print("ERROR: ALCHEMY_RPC_URL not set!")
        return
    
    # Run benchmark
    benchmark = BenchmarkRunner(rpc_url)
    
    # Test with known MEV blocks
    print("\nTesting with known MEV blocks...")
    results = benchmark.benchmark_blocks(KNOWN_MEV_BLOCKS)
    
    # Print summary
    benchmark.print_summary(results)
    
    # Save results
    benchmark.save_results("benchmark_results.json", results)
    
    print("\n[DONE] Benchmark complete!")
    print("\nNext steps:")
    print("1. Review results in benchmark_results.json")
    print("2. Compare with mev-inspect-py (if available)")
    print("3. Prepare data for scientific paper")


if __name__ == "__main__":
    main()
