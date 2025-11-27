#!/usr/bin/env python3
"""
Profile mev-inspect-pyrevm to find performance bottlenecks.

Usage:
    python benchmarks/profile_performance.py --block 12914944
    python benchmarks/profile_performance.py --block 12914944 --mode legacy
"""

import cProfile
import pstats
import io
import sys
import os
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("Warning: python-dotenv not installed. Using system environment variables.")

from mev_inspect.inspector import MEVInspector
from mev_inspect.rpc import RPCClient
import argparse


def profile_block_inspection(block_number: int, mode: str = "phase2-4", top_n: int = 30):
    """Profile a single block inspection and show hotspots.
    
    Args:
        block_number: Block to inspect
        mode: "phase2-4" or "legacy"
        top_n: Number of top functions to show
    """
    # Get RPC URL from environment
    rpc_url = os.getenv("ALCHEMY_RPC_URL")
    if not rpc_url:
        raise ValueError("ALCHEMY_RPC_URL not set")
    
    print(f"\n{'='*80}")
    print(f"PROFILING BLOCK {block_number} (Mode: {mode})")
    print(f"{'='*80}\n")
    
    # Initialize inspector
    rpc_client = RPCClient(rpc_url)
    inspector = MEVInspector(rpc_client, use_legacy=(mode == "legacy"))
    
    # Create profiler
    profiler = cProfile.Profile()
    
    # Profile the inspection
    print(f"Starting profiling... (this may take 1-2 minutes)")
    start_time = time.time()
    
    profiler.enable()
    try:
        results = inspector.inspect_block(block_number, what_if=False)
        success = True
        error = None
    except Exception as e:
        success = False
        error = str(e)
        print(f"ERROR: {e}")
    finally:
        profiler.disable()
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"\n{'='*80}")
    print(f"PROFILING COMPLETE")
    print(f"{'='*80}")
    print(f"Total Time: {elapsed:.2f}s")
    print(f"Success: {success}")
    if error:
        print(f"Error: {error}")
    
    if success:
        print(f"\nMEV Results:")
        print(f"  - Arbitrages: {len(results.historical_arbitrages)}")
        print(f"  - Sandwiches: {len(results.historical_sandwiches)}")
        print(f"  - Swaps: {len(results.all_swaps)}")
    
    # Print profile statistics
    print(f"\n{'='*80}")
    print(f"TOP {top_n} HOTSPOTS (by cumulative time)")
    print(f"{'='*80}\n")
    
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    ps.sort_stats('cumulative')
    ps.print_stats(top_n)
    print(s.getvalue())
    
    # Print top functions by total time
    print(f"\n{'='*80}")
    print(f"TOP {top_n} HOTSPOTS (by total time)")
    print(f"{'='*80}\n")
    
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    ps.sort_stats('tottime')
    ps.print_stats(top_n)
    print(s.getvalue())
    
    # Save detailed profile to file
    output_file = f"profile_{mode}_block_{block_number}.prof"
    profiler.dump_stats(output_file)
    print(f"\n✅ Detailed profile saved to: {output_file}")
    print(f"   View with: python -m pstats {output_file}")
    
    # Generate call graph data
    print(f"\n{'='*80}")
    print(f"CALL GRAPH (Top callers)")
    print(f"{'='*80}\n")
    
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    ps.sort_stats('cumulative')
    ps.print_callers(20)
    print(s.getvalue())
    
    return {
        "block_number": block_number,
        "mode": mode,
        "time_seconds": elapsed,
        "success": success,
        "error": error,
        "profile_file": output_file
    }


def compare_modes(block_number: int):
    """Profile both modes and compare."""
    print(f"\n{'#'*80}")
    print(f"# COMPARING MODES FOR BLOCK {block_number}")
    print(f"{'#'*80}\n")
    
    # Profile phase2-4
    result_phase = profile_block_inspection(block_number, "phase2-4", top_n=20)
    
    print(f"\n{'~'*80}\n")
    time.sleep(2)  # Brief pause between runs
    
    # Profile legacy
    result_legacy = profile_block_inspection(block_number, "legacy", top_n=20)
    
    # Summary comparison
    print(f"\n{'='*80}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*80}\n")
    
    print(f"Phase 2-4:")
    print(f"  Time: {result_phase['time_seconds']:.2f}s")
    print(f"  Success: {result_phase['success']}")
    print(f"  Profile: {result_phase['profile_file']}")
    
    print(f"\nLegacy:")
    print(f"  Time: {result_legacy['time_seconds']:.2f}s")
    print(f"  Success: {result_legacy['success']}")
    print(f"  Profile: {result_legacy['profile_file']}")
    
    if result_phase['success'] and result_legacy['success']:
        speedup = result_legacy['time_seconds'] / result_phase['time_seconds']
        print(f"\n⚡ Speedup: {speedup:.2f}x")
    
    return result_phase, result_legacy


def analyze_rpc_calls(block_number: int):
    """Special analysis to count RPC calls."""
    print(f"\n{'='*80}")
    print(f"ANALYZING RPC CALLS FOR BLOCK {block_number}")
    print(f"{'='*80}\n")
    
    rpc_url = os.getenv("ALCHEMY_RPC_URL")
    rpc_client = RPCClient(rpc_url)
    
    # Monkey-patch to count calls
    original_post = rpc_client.w3.provider.make_request if hasattr(rpc_client.w3.provider, 'make_request') else None
    call_counts = {}
    
    def counting_request(method, params):
        call_counts[method] = call_counts.get(method, 0) + 1
        return original_post(method, params)
    
    if original_post:
        rpc_client.w3.provider.make_request = counting_request
    
    # Run inspection
    inspector = MEVInspector(rpc_client, use_legacy=False)
    try:
        results = inspector.inspect_block(block_number, what_if=False)
        print(f"✅ Inspection complete")
        print(f"\nRPC Call Breakdown:")
        for method, count in sorted(call_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {method:30s}: {count:4d} calls")
        print(f"\n  TOTAL: {sum(call_counts.values())} calls")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile mev-inspect-pyrevm performance")
    parser.add_argument("--block", type=int, default=12914944, help="Block number to profile")
    parser.add_argument("--mode", choices=["phase2-4", "legacy", "both"], default="phase2-4",
                       help="Mode to profile")
    parser.add_argument("--top", type=int, default=30, help="Number of top functions to show")
    parser.add_argument("--rpc-analysis", action="store_true", help="Analyze RPC call breakdown")
    
    args = parser.parse_args()
    
    if args.rpc_analysis:
        analyze_rpc_calls(args.block)
    elif args.mode == "both":
        compare_modes(args.block)
    else:
        profile_block_inspection(args.block, args.mode, args.top)
    
    print(f"\n{'='*80}")
    print("PROFILING FINISHED")
    print(f"{'='*80}\n")
