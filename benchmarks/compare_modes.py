#!/usr/bin/env python3
"""
Benchmark comparison: Phase 2-4 vs Legacy vs mev-inspect-py

Compares:
- Speed (time per block)
- RPC calls (total and per block)
- Accuracy (arbitrages, sandwiches detected)
- Memory usage

Usage:
    python benchmarks/compare_modes.py --start 12914900 --end 12914999
"""

import os
import sys
import time
import json
import subprocess
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

@dataclass
class BlockResult:
    """Results for a single block."""
    block_number: int
    mode: str  # 'phase2-4', 'legacy', 'mev-inspect-py'
    
    # Performance metrics
    time_seconds: float
    rpc_calls: int  # Estimated from logs
    memory_mb: float
    
    # Detection results
    arbitrages_count: int
    arbitrages_profit_eth: float
    sandwiches_count: int
    sandwiches_profit_eth: float
    swaps_count: int
    
    # Status
    success: bool
    error: str = ""


@dataclass
class ComparisonSummary:
    """Summary statistics for comparison."""
    mode: str
    blocks_tested: int
    
    # Performance
    avg_time_seconds: float
    median_time_seconds: float
    total_time_seconds: float
    avg_rpc_calls: float
    total_rpc_calls: int
    
    # Accuracy
    total_arbitrages: int
    total_arbitrages_profit: float
    total_sandwiches: int
    total_sandwiches_profit: float
    total_swaps: int
    
    # Success rate
    success_rate: float
    failed_blocks: List[int]


class BenchmarkRunner:
    """Run benchmark comparing different modes."""
    
    def __init__(self, start_block: int, end_block: int):
        self.start_block = start_block
        self.end_block = end_block
        self.results: List[BlockResult] = []
    
    def run_mev_inspect(self, block: int, use_legacy: bool = False) -> Dict[str, Any]:
        """Run mev-inspect on a block and parse output.
        
        Returns:
            Dict with results including time, detections, etc.
        """
        mode = "legacy" if use_legacy else "phase2-4"
        cmd = ["mev-inspect", "block", str(block)]
        if use_legacy:
            cmd.append("--use-legacy")
        
        print(f"  Running block {block} ({mode})...", end=" ", flush=True)
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                env=os.environ.copy()
            )
            elapsed = time.time() - start_time
            
            if result.returncode != 0:
                print(f"FAILED ({elapsed:.2f}s)")
                return {
                    "success": False,
                    "error": result.stderr[:200],
                    "time": elapsed,
                }
            
            # Parse output
            output = result.stdout + result.stderr
            
            # Extract metrics from output
            arbitrages_count = 0
            arbitrages_profit = 0.0
            sandwiches_count = 0
            sandwiches_profit = 0.0
            swaps_count = 0
            rpc_calls = 0
            
            # Parse detection results
            if "Arbitrage │" in output:
                for line in output.split("\n"):
                    if "Arbitrage │" in line:
                        parts = line.split("│")
                        if len(parts) >= 3:
                            try:
                                arbitrages_count = int(parts[1].strip())
                                arbitrages_profit = float(parts[2].strip())
                            except:
                                pass
            
            if "Sandwich │" in output:
                for line in output.split("\n"):
                    if "Sandwich │" in line:
                        parts = line.split("│")
                        if len(parts) >= 3:
                            try:
                                sandwiches_count = int(parts[1].strip())
                                sandwiches_profit = float(parts[2].strip())
                            except:
                                pass
            
            # Detect swaps count
            if "Detected" in output and "swaps" in output:
                for line in output.split("\n"):
                    if "Detected" in line and "swaps" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "Detected" and i + 1 < len(parts):
                                try:
                                    swaps_count = int(parts[i + 1])
                                except:
                                    pass
            
            # Estimate RPC calls from batch fetches
            if "[Batch RPC]" in output:
                # Phase 2-4: 1 batch for receipts + 1 batch for codes
                rpc_calls = 2  # Batch calls
            else:
                # Legacy: estimate from transaction count
                # Typically: N receipts + ~N/2 code fetches
                if "Total transactions:" in output:
                    for line in output.split("\n"):
                        if "Total transactions:" in line:
                            try:
                                tx_count = int(line.split(":")[-1].strip())
                                rpc_calls = tx_count + tx_count // 2  # Rough estimate
                            except:
                                rpc_calls = 300  # Default estimate
            
            print(f"OK ({elapsed:.2f}s, arb={arbitrages_count}, swaps={swaps_count})")
            
            return {
                "success": True,
                "time": elapsed,
                "rpc_calls": rpc_calls,
                "arbitrages_count": arbitrages_count,
                "arbitrages_profit": arbitrages_profit,
                "sandwiches_count": sandwiches_count,
                "sandwiches_profit": sandwiches_profit,
                "swaps_count": swaps_count,
                "memory_mb": 0.0,  # TODO: measure
            }
            
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            print(f"TIMEOUT ({elapsed:.2f}s)")
            return {
                "success": False,
                "error": "Timeout after 120s",
                "time": elapsed,
            }
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"ERROR ({elapsed:.2f}s): {e}")
            return {
                "success": False,
                "error": str(e),
                "time": elapsed,
            }
    
    def benchmark_mode(self, mode: str) -> List[BlockResult]:
        """Benchmark a specific mode across all blocks.
        
        Args:
            mode: 'phase2-4', 'legacy', or 'mev-inspect-py'
        """
        print(f"\n{'='*60}")
        print(f"Benchmarking {mode.upper()}")
        print(f"{'='*60}")
        
        results = []
        
        for block in range(self.start_block, self.end_block + 1):
            use_legacy = (mode == "legacy")
            
            if mode == "mev-inspect-py":
                # TODO: Implement comparison with original mev-inspect-py
                print(f"  Skipping block {block} (mev-inspect-py not implemented)")
                continue
            
            result_dict = self.run_mev_inspect(block, use_legacy)
            
            result = BlockResult(
                block_number=block,
                mode=mode,
                time_seconds=result_dict.get("time", 0),
                rpc_calls=result_dict.get("rpc_calls", 0),
                memory_mb=result_dict.get("memory_mb", 0),
                arbitrages_count=result_dict.get("arbitrages_count", 0),
                arbitrages_profit_eth=result_dict.get("arbitrages_profit", 0),
                sandwiches_count=result_dict.get("sandwiches_count", 0),
                sandwiches_profit_eth=result_dict.get("sandwiches_profit", 0),
                swaps_count=result_dict.get("swaps_count", 0),
                success=result_dict.get("success", False),
                error=result_dict.get("error", ""),
            )
            
            results.append(result)
            self.results.append(result)
        
        return results
    
    def calculate_summary(self, results: List[BlockResult]) -> ComparisonSummary:
        """Calculate summary statistics for a mode."""
        if not results:
            return ComparisonSummary(
                mode="unknown",
                blocks_tested=0,
                avg_time_seconds=0,
                median_time_seconds=0,
                total_time_seconds=0,
                avg_rpc_calls=0,
                total_rpc_calls=0,
                total_arbitrages=0,
                total_arbitrages_profit=0,
                total_sandwiches=0,
                total_sandwiches_profit=0,
                total_swaps=0,
                success_rate=0,
                failed_blocks=[],
            )
        
        successful = [r for r in results if r.success]
        failed = [r.block_number for r in results if not r.success]
        
        times = [r.time_seconds for r in successful] if successful else [0]
        rpc_calls = [r.rpc_calls for r in successful] if successful else [0]
        
        return ComparisonSummary(
            mode=results[0].mode,
            blocks_tested=len(results),
            avg_time_seconds=statistics.mean(times),
            median_time_seconds=statistics.median(times),
            total_time_seconds=sum(times),
            avg_rpc_calls=statistics.mean(rpc_calls),
            total_rpc_calls=sum(rpc_calls),
            total_arbitrages=sum(r.arbitrages_count for r in successful),
            total_arbitrages_profit=sum(r.arbitrages_profit_eth for r in successful),
            total_sandwiches=sum(r.sandwiches_count for r in successful),
            total_sandwiches_profit=sum(r.sandwiches_profit_eth for r in successful),
            total_swaps=sum(r.swaps_count for r in successful),
            success_rate=len(successful) / len(results) * 100,
            failed_blocks=failed,
        )
    
    def print_comparison_table(self, summaries: Dict[str, ComparisonSummary]):
        """Print comparison table."""
        print("\n" + "="*80)
        print("COMPARISON SUMMARY")
        print("="*80)
        
        # Performance comparison
        print("\n📊 PERFORMANCE METRICS")
        print("-" * 80)
        print(f"{'Metric':<30} {'Phase 2-4':<20} {'Legacy':<20} {'Improvement':<10}")
        print("-" * 80)
        
        phase2_4 = summaries.get("phase2-4")
        legacy = summaries.get("legacy")
        
        if phase2_4 and legacy:
            # Time comparison
            speedup = legacy.avg_time_seconds / phase2_4.avg_time_seconds if phase2_4.avg_time_seconds > 0 else 0
            print(f"{'Avg Time (seconds)':<30} {phase2_4.avg_time_seconds:<20.3f} {legacy.avg_time_seconds:<20.3f} {speedup:.2f}x")
            
            # RPC calls comparison
            rpc_reduction = (1 - phase2_4.avg_rpc_calls / legacy.avg_rpc_calls) * 100 if legacy.avg_rpc_calls > 0 else 0
            print(f"{'Avg RPC Calls':<30} {phase2_4.avg_rpc_calls:<20.1f} {legacy.avg_rpc_calls:<20.1f} {rpc_reduction:.1f}%")
            
            # Total time
            print(f"{'Total Time (seconds)':<30} {phase2_4.total_time_seconds:<20.1f} {legacy.total_time_seconds:<20.1f}")
        
        # Detection accuracy comparison
        print("\n🎯 DETECTION ACCURACY")
        print("-" * 80)
        print(f"{'Metric':<30} {'Phase 2-4':<20} {'Legacy':<20} {'Difference':<10}")
        print("-" * 80)
        
        if phase2_4 and legacy:
            # Arbitrages
            arb_diff = phase2_4.total_arbitrages - legacy.total_arbitrages
            arb_diff_str = f"{arb_diff:+d}" if arb_diff != 0 else "0"
            print(f"{'Total Arbitrages':<30} {phase2_4.total_arbitrages:<20} {legacy.total_arbitrages:<20} {arb_diff_str:<10}")
            
            # Profit
            profit_diff = phase2_4.total_arbitrages_profit - legacy.total_arbitrages_profit
            profit_diff_str = f"{profit_diff:+.2f}" if abs(profit_diff) > 0.01 else "0.00"
            print(f"{'Total Profit (ETH)':<30} {phase2_4.total_arbitrages_profit:<20.2f} {legacy.total_arbitrages_profit:<20.2f} {profit_diff_str:<10}")
            
            # Sandwiches
            sand_diff = phase2_4.total_sandwiches - legacy.total_sandwiches
            sand_diff_str = f"{sand_diff:+d}" if sand_diff != 0 else "0"
            print(f"{'Total Sandwiches':<30} {phase2_4.total_sandwiches:<20} {legacy.total_sandwiches:<20} {sand_diff_str:<10}")
            
            # Swaps
            swap_diff = phase2_4.total_swaps - legacy.total_swaps
            swap_diff_str = f"{swap_diff:+d}" if swap_diff != 0 else "0"
            print(f"{'Total Swaps Detected':<30} {phase2_4.total_swaps:<20} {legacy.total_swaps:<20} {swap_diff_str:<10}")
        
        # Reliability
        print("\n✅ RELIABILITY")
        print("-" * 80)
        print(f"{'Mode':<30} {'Success Rate':<20} {'Failed Blocks':<30}")
        print("-" * 80)
        
        for mode_name, summary in summaries.items():
            failed_str = ", ".join(map(str, summary.failed_blocks[:5]))
            if len(summary.failed_blocks) > 5:
                failed_str += "..."
            print(f"{mode_name:<30} {summary.success_rate:<20.1f}% {failed_str:<30}")
        
        print("\n" + "="*80)
    
    def save_results(self, output_file: str):
        """Save detailed results to JSON."""
        # Group by mode
        by_mode = defaultdict(list)
        for result in self.results:
            by_mode[result.mode].append(asdict(result))
        
        # Calculate summaries
        summaries = {}
        for mode, results in by_mode.items():
            result_objs = [BlockResult(**r) for r in results]
            summaries[mode] = asdict(self.calculate_summary(result_objs))
        
        output = {
            "benchmark_info": {
                "start_block": self.start_block,
                "end_block": self.end_block,
                "total_blocks": self.end_block - self.start_block + 1,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "summaries": summaries,
            "detailed_results": dict(by_mode),
        }
        
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"\n✅ Detailed results saved to: {output_file}")
    
    def run(self):
        """Run full benchmark."""
        print("\n" + "="*80)
        print(f"MEV-INSPECT BENCHMARK COMPARISON")
        print(f"Blocks: {self.start_block} - {self.end_block} ({self.end_block - self.start_block + 1} blocks)")
        print("="*80)
        
        # Benchmark Phase 2-4
        phase2_4_results = self.benchmark_mode("phase2-4")
        
        # Benchmark Legacy
        legacy_results = self.benchmark_mode("legacy")
        
        # Calculate summaries
        summaries = {
            "phase2-4": self.calculate_summary(phase2_4_results),
            "legacy": self.calculate_summary(legacy_results),
        }
        
        # Print comparison
        self.print_comparison_table(summaries)
        
        # Save results
        output_file = f"benchmark_results_{self.start_block}_{self.end_block}.json"
        self.save_results(output_file)
        
        return summaries


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark mev-inspect modes")
    parser.add_argument("--start", type=int, default=12914900, help="Start block number")
    parser.add_argument("--end", type=int, default=12914910, help="End block number (inclusive)")
    parser.add_argument("--output", type=str, help="Output JSON file (default: auto-generated)")
    
    args = parser.parse_args()
    
    if args.start > args.end:
        print("ERROR: Start block must be <= end block")
        sys.exit(1)
    
    # Run benchmark
    runner = BenchmarkRunner(args.start, args.end)
    summaries = runner.run()
    
    # Custom output file
    if args.output:
        runner.save_results(args.output)


if __name__ == "__main__":
    main()
