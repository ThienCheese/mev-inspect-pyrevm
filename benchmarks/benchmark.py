"""Benchmark tool to compare PyRevm mode vs Legacy mode.

This benchmark measures:
1. Speed: Total execution time
2. Accuracy: Number of swaps, arbitrages, sandwiches detected
3. RPC efficiency: Number of RPC calls made
4. Memory usage: Peak memory consumption
5. Detail: Internal calls captured, transaction info completeness
"""

import json
import time
import tracemalloc
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from mev_inspect.inspector import MEVInspector
from mev_inspect.rpc import RPCClient


@dataclass
class BenchmarkMetrics:
    """Metrics collected during benchmark run."""
    mode: str  # "pyrevm" or "legacy"
    block_number: int
    
    # Speed metrics
    total_time_seconds: float
    inspection_time_seconds: float
    
    # Accuracy metrics
    total_transactions: int
    successful_transactions: int
    swaps_detected: int
    arbitrages_detected: int
    sandwiches_detected: int
    
    # Detail metrics
    transactions_with_swaps: int
    avg_swaps_per_transaction: float
    internal_calls_captured: int  # Only for PyRevm mode
    
    # RPC efficiency
    total_rpc_calls: int
    batch_rpc_calls: int
    cache_hit_rate: float
    
    # Memory metrics
    peak_memory_mb: float
    current_memory_mb: float
    
    # Extra info
    error_count: int
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class RPCCallTracker:
    """Wrapper around RPCClient to track number of calls."""
    
    def __init__(self, rpc_client: RPCClient):
        self.rpc_client = rpc_client
        self.call_count = 0
        self.batch_call_count = 0
        self.calls_log: List[Dict[str, Any]] = []
        
    def get_block(self, *args, **kwargs):
        self.call_count += 1
        self.calls_log.append({
            "method": "eth_getBlockByNumber",
            "timestamp": time.time()
        })
        return self.rpc_client.get_block(*args, **kwargs)
    
    def get_transaction_receipt(self, *args, **kwargs):
        self.call_count += 1
        self.calls_log.append({
            "method": "eth_getTransactionReceipt",
            "timestamp": time.time()
        })
        return self.rpc_client.get_transaction_receipt(*args, **kwargs)
    
    def batch_get_receipts(self, *args, **kwargs):
        self.batch_call_count += 1
        self.call_count += 1  # Count as 1 batch call
        self.calls_log.append({
            "method": "eth_batchGetTransactionReceipts",
            "count": len(args[0]) if args else 0,
            "timestamp": time.time()
        })
        return self.rpc_client.batch_get_receipts(*args, **kwargs)
    
    def batch_get_code(self, *args, **kwargs):
        self.batch_call_count += 1
        self.call_count += 1
        self.calls_log.append({
            "method": "eth_batchGetCode",
            "count": len(args[0]) if args else 0,
            "timestamp": time.time()
        })
        return self.rpc_client.batch_get_code(*args, **kwargs)
    
    def batch_get_pool_tokens(self, *args, **kwargs):
        self.batch_call_count += 1
        self.call_count += 1
        self.calls_log.append({
            "method": "eth_batchGetPoolTokens",
            "count": len(args[0]) if args else 0,
            "timestamp": time.time()
        })
        return self.rpc_client.batch_get_pool_tokens(*args, **kwargs)
    
    def get_code(self, *args, **kwargs):
        self.call_count += 1
        self.calls_log.append({
            "method": "eth_getCode",
            "timestamp": time.time()
        })
        return self.rpc_client.get_code(*args, **kwargs)
    
    def call(self, *args, **kwargs):
        self.call_count += 1
        self.calls_log.append({
            "method": "eth_call",
            "timestamp": time.time()
        })
        return self.rpc_client.call(*args, **kwargs)
    
    # Delegate all other attributes to the wrapped client
    def __getattr__(self, name):
        return getattr(self.rpc_client, name)


class BenchmarkRunner:
    """Run benchmarks comparing PyRevm vs Legacy modes."""
    
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        
    def run_benchmark(self, block_number: int, use_legacy: bool = False) -> BenchmarkMetrics:
        """Run benchmark on a single block.
        
        Args:
            block_number: Block to analyze
            use_legacy: If True, use legacy mode. If False, use PyRevm mode.
            
        Returns:
            BenchmarkMetrics with collected metrics
        """
        mode = "legacy" if use_legacy else "pyrevm"
        print(f"\n{'='*60}")
        print(f"Running benchmark: {mode.upper()} mode on block {block_number}")
        print(f"{'='*60}\n")
        
        # Start memory tracking
        tracemalloc.start()
        
        # Initialize RPC client with call tracking
        base_rpc_client = RPCClient(self.rpc_url)
        rpc_tracker = RPCCallTracker(base_rpc_client)
        
        # Initialize inspector
        inspector = MEVInspector(rpc_tracker, use_legacy=use_legacy)
        
        warnings = []
        error_count = 0
        
        # Start timing
        start_time = time.time()
        
        try:
            # Run inspection
            inspection_start = time.time()
            results = inspector.inspect_block(block_number, what_if=False)
            inspection_time = time.time() - inspection_start
            
            # Count internal calls (only available in PyRevm mode)
            internal_calls = 0
            if not use_legacy:
                # TODO: Extract internal_calls count from replay results
                # For now, estimate from transaction info
                pass
            
            # Calculate metrics
            total_transactions = len(results.transactions)
            successful_transactions = sum(
                1 for tx in results.transactions if tx.status == 1
            )
            swaps_detected = len(results.all_swaps)
            transactions_with_swaps = len(set(swap.tx_hash for swap in results.all_swaps))
            avg_swaps_per_tx = (
                swaps_detected / transactions_with_swaps 
                if transactions_with_swaps > 0 else 0
            )
            
            # Get memory stats
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            # Calculate cache hit rate (if available in state_manager)
            cache_hit_rate = 0.0
            # TODO: Extract from state_manager if available
            
            total_time = time.time() - start_time
            
            metrics = BenchmarkMetrics(
                mode=mode,
                block_number=block_number,
                total_time_seconds=total_time,
                inspection_time_seconds=inspection_time,
                total_transactions=total_transactions,
                successful_transactions=successful_transactions,
                swaps_detected=swaps_detected,
                arbitrages_detected=len(results.historical_arbitrages),
                sandwiches_detected=len(results.historical_sandwiches),
                transactions_with_swaps=transactions_with_swaps,
                avg_swaps_per_transaction=avg_swaps_per_tx,
                internal_calls_captured=internal_calls,
                total_rpc_calls=rpc_tracker.call_count,
                batch_rpc_calls=rpc_tracker.batch_call_count,
                cache_hit_rate=cache_hit_rate,
                peak_memory_mb=peak / (1024 * 1024),
                current_memory_mb=current / (1024 * 1024),
                error_count=error_count,
                warnings=warnings
            )
            
            return metrics
            
        except Exception as e:
            print(f"ERROR during benchmark: {e}")
            tracemalloc.stop()
            raise
    
    def compare_modes(self, block_number: int) -> Dict[str, Any]:
        """Run both modes and compare results.
        
        Args:
            block_number: Block to analyze
            
        Returns:
            Dictionary with comparison results
        """
        print(f"\n{'#'*60}")
        print(f"BENCHMARK COMPARISON FOR BLOCK {block_number}")
        print(f"{'#'*60}")
        
        # Run PyRevm mode
        pyrevm_metrics = self.run_benchmark(block_number, use_legacy=False)
        
        # Run Legacy mode
        legacy_metrics = self.run_benchmark(block_number, use_legacy=True)
        
        # Calculate improvements
        speed_improvement = (
            (legacy_metrics.total_time_seconds - pyrevm_metrics.total_time_seconds) 
            / legacy_metrics.total_time_seconds * 100
        )
        
        rpc_reduction = (
            (legacy_metrics.total_rpc_calls - pyrevm_metrics.total_rpc_calls) 
            / legacy_metrics.total_rpc_calls * 100
            if legacy_metrics.total_rpc_calls > 0 else 0
        )
        
        memory_difference = (
            (pyrevm_metrics.peak_memory_mb - legacy_metrics.peak_memory_mb) 
            / legacy_metrics.peak_memory_mb * 100
            if legacy_metrics.peak_memory_mb > 0 else 0
        )
        
        accuracy_difference = {
            "swaps": pyrevm_metrics.swaps_detected - legacy_metrics.swaps_detected,
            "arbitrages": pyrevm_metrics.arbitrages_detected - legacy_metrics.arbitrages_detected,
            "sandwiches": pyrevm_metrics.sandwiches_detected - legacy_metrics.sandwiches_detected,
        }
        
        comparison = {
            "block_number": block_number,
            "timestamp": datetime.now().isoformat(),
            "pyrevm_mode": pyrevm_metrics.to_dict(),
            "legacy_mode": legacy_metrics.to_dict(),
            "improvements": {
                "speed_improvement_percent": speed_improvement,
                "rpc_reduction_percent": rpc_reduction,
                "memory_difference_percent": memory_difference,
            },
            "accuracy_difference": accuracy_difference,
            "summary": self._generate_summary(pyrevm_metrics, legacy_metrics)
        }
        
        return comparison
    
    def _generate_summary(self, pyrevm: BenchmarkMetrics, legacy: BenchmarkMetrics) -> Dict[str, str]:
        """Generate human-readable summary."""
        summary = {}
        
        # Speed comparison
        if pyrevm.total_time_seconds < legacy.total_time_seconds:
            speedup = legacy.total_time_seconds / pyrevm.total_time_seconds
            summary["speed"] = f"PyRevm is {speedup:.2f}x faster ({pyrevm.total_time_seconds:.2f}s vs {legacy.total_time_seconds:.2f}s)"
        else:
            slowdown = pyrevm.total_time_seconds / legacy.total_time_seconds
            summary["speed"] = f"PyRevm is {slowdown:.2f}x slower ({pyrevm.total_time_seconds:.2f}s vs {legacy.total_time_seconds:.2f}s)"
        
        # RPC comparison
        if pyrevm.total_rpc_calls < legacy.total_rpc_calls:
            reduction = (1 - pyrevm.total_rpc_calls / legacy.total_rpc_calls) * 100
            summary["rpc"] = f"PyRevm uses {reduction:.1f}% fewer RPC calls ({pyrevm.total_rpc_calls} vs {legacy.total_rpc_calls})"
        else:
            increase = (pyrevm.total_rpc_calls / legacy.total_rpc_calls - 1) * 100
            summary["rpc"] = f"PyRevm uses {increase:.1f}% more RPC calls ({pyrevm.total_rpc_calls} vs {legacy.total_rpc_calls})"
        
        # Accuracy comparison
        swap_diff = pyrevm.swaps_detected - legacy.swaps_detected
        if swap_diff > 0:
            summary["accuracy"] = f"PyRevm detected {swap_diff} more swaps ({pyrevm.swaps_detected} vs {legacy.swaps_detected})"
        elif swap_diff < 0:
            summary["accuracy"] = f"PyRevm detected {abs(swap_diff)} fewer swaps ({pyrevm.swaps_detected} vs {legacy.swaps_detected})"
        else:
            summary["accuracy"] = f"Both modes detected same number of swaps ({pyrevm.swaps_detected})"
        
        # MEV detection
        arb_diff = pyrevm.arbitrages_detected - legacy.arbitrages_detected
        sand_diff = pyrevm.sandwiches_detected - legacy.sandwiches_detected
        summary["mev"] = f"Arbitrages: {pyrevm.arbitrages_detected} vs {legacy.arbitrages_detected} (diff: {arb_diff:+d}), Sandwiches: {pyrevm.sandwiches_detected} vs {legacy.sandwiches_detected} (diff: {sand_diff:+d})"
        
        # Memory
        mem_diff = pyrevm.peak_memory_mb - legacy.peak_memory_mb
        summary["memory"] = f"PyRevm uses {mem_diff:+.1f}MB more memory ({pyrevm.peak_memory_mb:.1f}MB vs {legacy.peak_memory_mb:.1f}MB)"
        
        return summary
    
    def save_results(self, comparison: Dict[str, Any], output_path: str):
        """Save comparison results to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(comparison, f, indent=2)
        print(f"\nResults saved to: {output_path}")
    
    def print_results(self, comparison: Dict[str, Any]):
        """Print comparison results in a readable format."""
        print(f"\n{'='*60}")
        print("BENCHMARK RESULTS")
        print(f"{'='*60}\n")
        
        print(f"Block Number: {comparison['block_number']}")
        print(f"Timestamp: {comparison['timestamp']}\n")
        
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        for key, value in comparison['summary'].items():
            print(f"{key.upper()}: {value}")
        
        print(f"\n{'='*60}")
        print("DETAILED METRICS")
        print(f"{'='*60}\n")
        
        # Print side-by-side comparison
        pyrevm = comparison['pyrevm_mode']
        legacy = comparison['legacy_mode']
        
        print(f"{'Metric':<40} {'PyRevm':>12} {'Legacy':>12} {'Diff':>12}")
        print("-" * 78)
        
        metrics_to_compare = [
            ("Total Time (s)", "total_time_seconds", "time"),
            ("Inspection Time (s)", "inspection_time_seconds", "time"),
            ("Total Transactions", "total_transactions", "count"),
            ("Successful Transactions", "successful_transactions", "count"),
            ("Swaps Detected", "swaps_detected", "count"),
            ("Arbitrages Detected", "arbitrages_detected", "count"),
            ("Sandwiches Detected", "sandwiches_detected", "count"),
            ("Transactions with Swaps", "transactions_with_swaps", "count"),
            ("Avg Swaps per TX", "avg_swaps_per_transaction", "ratio"),
            ("Total RPC Calls", "total_rpc_calls", "count"),
            ("Batch RPC Calls", "batch_rpc_calls", "count"),
            ("Peak Memory (MB)", "peak_memory_mb", "memory"),
            ("Error Count", "error_count", "count"),
        ]
        
        for label, key, type_ in metrics_to_compare:
            pyrevm_val = pyrevm[key]
            legacy_val = legacy[key]
            
            if type_ == "time":
                diff = pyrevm_val - legacy_val
                print(f"{label:<40} {pyrevm_val:>12.2f} {legacy_val:>12.2f} {diff:>+12.2f}")
            elif type_ == "ratio":
                diff = pyrevm_val - legacy_val
                print(f"{label:<40} {pyrevm_val:>12.3f} {legacy_val:>12.3f} {diff:>+12.3f}")
            elif type_ == "memory":
                diff = pyrevm_val - legacy_val
                print(f"{label:<40} {pyrevm_val:>12.1f} {legacy_val:>12.1f} {diff:>+12.1f}")
            else:  # count
                diff = pyrevm_val - legacy_val
                print(f"{label:<40} {pyrevm_val:>12} {legacy_val:>12} {diff:>+12}")
        
        print("\n" + "=" * 78)


def main():
    """Main benchmark entry point."""
    import os
    from dotenv import load_dotenv
    import argparse
    
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Benchmark PyRevm vs Legacy mode")
    parser.add_argument("block", type=int, help="Block number to benchmark")
    parser.add_argument(
        "--rpc-url",
        default=os.getenv("ALCHEMY_RPC_URL"),
        help="RPC URL (default: from ALCHEMY_RPC_URL env var)"
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="Output file for results (default: benchmark_results.json)"
    )
    parser.add_argument(
        "--mode",
        choices=["both", "pyrevm", "legacy"],
        default="both",
        help="Which mode(s) to benchmark (default: both)"
    )
    
    args = parser.parse_args()
    
    if not args.rpc_url:
        print("ERROR: RPC URL required. Set ALCHEMY_RPC_URL or use --rpc-url")
        return
    
    runner = BenchmarkRunner(args.rpc_url)
    
    if args.mode == "both":
        # Compare both modes
        comparison = runner.compare_modes(args.block)
        runner.print_results(comparison)
        runner.save_results(comparison, args.output)
    else:
        # Run single mode
        use_legacy = args.mode == "legacy"
        metrics = runner.run_benchmark(args.block, use_legacy=use_legacy)
        
        print(f"\n{'='*60}")
        print(f"RESULTS - {metrics.mode.upper()} MODE")
        print(f"{'='*60}\n")
        print(json.dumps(metrics.to_dict(), indent=2))
        
        # Save to file
        with open(args.output, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
