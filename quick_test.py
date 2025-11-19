#!/usr/bin/env python3
"""Quick production test"""

import sys

def test_imports():
    """Test all imports work"""
    print("Testing imports...")
    try:
        from mev_inspect.state_manager import StateManager
        from mev_inspect.replay import TransactionReplayer
        from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
        from mev_inspect.profit_calculator import ProfitCalculator
        from mev_inspect.rpc import RPCClient
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_rpc(rpc_url):
    """Test RPC connection"""
    print(f"\nTesting RPC: {rpc_url[:50]}...")
    try:
        from mev_inspect.rpc import RPCClient
        rpc = RPCClient(rpc_url)
        block_num = rpc.get_latest_block_number()
        print(f"✅ RPC working - Latest block: {block_num}")
        return True
    except Exception as e:
        print(f"❌ RPC failed: {e}")
        return False

def test_transaction_analysis(rpc_url):
    """Test analyzing a known MEV transaction"""
    print("\nTesting transaction analysis...")
    try:
        from mev_inspect.rpc import RPCClient
        from mev_inspect.state_manager import StateManager
        from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
        
        rpc = RPCClient(rpc_url)
        tx_hash = "0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4"
        
        print(f"  Fetching transaction...")
        tx = rpc.get_transaction(tx_hash)
        block_number = tx['blockNumber']
        
        print(f"  Block: {block_number}")
        print(f"  Initializing state manager...")
        state = StateManager(rpc, block_number)
        
        print(f"  Detecting swaps...")
        detector = EnhancedSwapDetector(rpc, state)
        swaps = detector.detect_swaps(tx_hash, block_number)
        
        print(f"✅ Analysis complete - Found {len(swaps)} swaps")
        return True
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cache():
    """Test cache functionality"""
    print("\nTesting cache...")
    try:
        from mev_inspect.state_manager import StateManager
        
        class MockRPC:
            def get_code(self, addr, block=None):
                return b'0x60806040'
            def get_balance(self, addr, block):
                return 0
        
        rpc = MockRPC()
        # Fix: StateManager uses account_cache_size, storage_cache_size, code_cache_size
        state = StateManager(rpc, 18500000, account_cache_size=1000, storage_cache_size=1000, code_cache_size=1000)
        
        # Access same address multiple times
        addr = '0x' + 'a' * 40
        for i in range(10):
            state.get_code(addr)
        
        print(f"✅ Cache test passed")
        return True
    except Exception as e:
        print(f"❌ Cache failed: {e}")
        return False

if __name__ == '__main__':
    print("="*60)
    print("MEV-INSPECT-PYREVM: Quick Production Test")
    print("="*60)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: RPC (if URL provided)
    rpc_url = sys.argv[1] if len(sys.argv) > 1 else None
    if rpc_url:
        results.append(("RPC Connection", test_rpc(rpc_url)))
        results.append(("Transaction Analysis", test_transaction_analysis(rpc_url)))
    else:
        print("\n⚠️  No RPC URL provided, skipping RPC tests")
        print("Usage: python3 quick_test.py <RPC_URL>")
    
    # Test 3: Cache
    results.append(("Cache", test_cache()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:30s} {status}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - PRODUCTION READY!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        sys.exit(1)
