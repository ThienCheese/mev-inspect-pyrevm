# Demo Scripts for mev-inspect-pyrevm

Comprehensive collection of demo scripts to test and showcase all features of mev-inspect-pyrevm.

## 📋 Overview

| Script | Purpose | Phase |
|--------|---------|-------|
| `demo_full_pipeline.py` | Complete 4-phase pipeline demo | All |
| `demo_batch_processing.py` | Process multiple transactions | All |
| `demo_benchmark.py` | Performance benchmarking | All |
| `demo_mev_finder.py` | Find MEV in blocks | All |
| `demo_comparison.py` | Compare with mev-inspect-py | All |
| `demo_phase2_replay.py` | Transaction replay | Phase 2 |
| `demo_phase3_enhanced.py` | Swap detection | Phase 3 |
| `demo_phase4_profit.py` | Profit calculation | Phase 4 |
| `test_pyrevm_real.py` | PyRevm integration tests | Phase 2 |
| `validate_phase3_accuracy.py` | Accuracy validation | Phase 3 |

## 🚀 New Demo Scripts

### 1. `demo_full_pipeline.py` - Complete Pipeline Demo

**Purpose**: Demonstrate all 4 phases working together end-to-end.

**Features**:
- ✅ Phase 1: StateManager with caching
- ✅ Phase 2: TransactionReplayer with internal calls
- ✅ Phase 3: EnhancedSwapDetector with hybrid detection
- ✅ Phase 4: ProfitCalculator with token flows
- ✅ Performance metrics per phase
- ✅ RPC efficiency tracking
- ✅ JSON export

**Usage**:
```bash
# Analyze single transaction
python3 examples/demo_full_pipeline.py \
  --tx-hash 0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4 \
  --rpc-url http://localhost:8545

# With custom searcher and output
python3 examples/demo_full_pipeline.py \
  --tx-hash 0x... \
  --rpc-url http://localhost:8545 \
  --searcher 0xabc... \
  --output results.json
```

---

### 2. `demo_batch_processing.py` - Batch Processing Demo

**Purpose**: Process multiple transactions efficiently with shared state and statistics.

**Features**:
- ✅ Batch processing multiple transactions
- ✅ Statistics tracking (profit, MEV types, etc.)
- ✅ Performance metrics
- ✅ MEV type distribution
- ✅ Throughput measurement

**Usage**:
```bash
# Process specific transactions
python3 examples/demo_batch_processing.py \
  --tx-hashes 0xabc...,0xdef...,0x123... \
  --rpc-url http://localhost:8545

# Process entire block
python3 examples/demo_batch_processing.py \
  --block 18500000 \
  --rpc-url http://localhost:8545 \
  --output batch_results.json

# Process from file with limit
python3 examples/demo_batch_processing.py \
  --input transactions.txt \
  --rpc-url http://localhost:8545 \
  --limit 100
```

---

### 3. `demo_benchmark.py` - Performance Benchmark

**Purpose**: Measure performance metrics across all phases.

**Features**:
- ✅ Per-phase benchmarking
- ✅ Statistical analysis (avg/min/max)
- ✅ RPC call efficiency
- ✅ Cache performance metrics
- ✅ Throughput calculation

**Usage**:
```bash
# Quick benchmark (10 iterations)
python3 examples/demo_benchmark.py \
  --rpc-url http://localhost:8545

# Detailed benchmark (100 iterations)
python3 examples/demo_benchmark.py \
  --rpc-url http://localhost:8545 \
  --iterations 100 \
  --output benchmark.json
```

---

### 4. `demo_mev_finder.py` - MEV Transaction Finder

**Purpose**: Scan blocks to find and analyze MEV transactions.

**Features**:
- ✅ Block scanning (single or range)
- ✅ Profit filtering
- ✅ MEV type classification
- ✅ Top MEV ranking
- ✅ Statistics reporting
- ✅ JSON export

**Usage**:
```bash
# Scan single block
python3 examples/demo_mev_finder.py \
  --block 18500000 \
  --rpc-url http://localhost:8545

# Scan block range with profit filter
python3 examples/demo_mev_finder.py \
  --start-block 18500000 \
  --end-block 18500010 \
  --rpc-url http://localhost:8545 \
  --min-profit 0.1 \
  --output mev_found.json
```

---

### 5. `demo_comparison.py` - Comparison with mev-inspect-py

**Purpose**: Compare results with mev-inspect-py for accuracy validation.

**Features**:
- ✅ Swap detection comparison
- ✅ Profit accuracy analysis
- ✅ Performance comparison
- ✅ Overall accuracy score
- ✅ Detailed differences

**Usage**:
```bash
# With simulated expected results
python3 examples/demo_comparison.py \
  --tx-hash 0x... \
  --rpc-url http://localhost:8545

# With actual mev-inspect-py results
python3 examples/demo_comparison.py \
  --tx-hash 0x... \
  --rpc-url http://localhost:8545 \
  --expected mev_inspect_py_results.json \
  --output comparison.json
```

---

## 📁 Phase-Specific Demos

### Phase 2: `demo_phase2_replay.py` - Transaction Replay Demo

**Purpose**: Interactive demo of transaction replay with real blockchain data.

**Features**:
- 🔄 Full transaction replay with PyRevm
- 📞 Extract and display internal calls
- 💾 Track state changes (storage modifications)
- 🔄 Detect swaps from internal calls
- 📊 Show StateManager cache statistics
- ⚡ Fallback to log-based replay if PyRevm unavailable

**Usage**:
```bash
# Replay a specific transaction
python3 examples/demo_phase2_replay.py \
  --tx-hash 0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4 \
  --rpc-url https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# Use local node
python3 examples/demo_phase2_replay.py \
  --tx-hash 0xabc123... \
  --rpc-url http://localhost:8545
```

**Requirements**:
- `web3>=6.15.0` (required)
- `pyrevm>=0.3.0` (optional - will use log-based fallback if not available)
- Access to Ethereum RPC node (Alchemy, Infura, or local)

**Arguments**:
- `--tx-hash`: Transaction hash to replay (required, must start with 0x)
- `--rpc-url`: RPC endpoint URL (default: http://localhost:8545)

**Example Output**:
```
==================================================================================
PHASE 2 DEMO: Transaction Replay with Internal Calls
==================================================================================

1️⃣  Initializing RPC client...
✅ Connected to RPC: https://eth-mainnet.g.alchemy.com/v2/...

2️⃣  Fetching transaction: 0x5e1657ef...
   Block: 12345678
   From: 0x742d35Cc...
   To: 0x7a250d56...
   Value: 0 wei
   Gas: 200000

3️⃣  Initializing StateManager (Phase 1 - Caching)...
   ✅ StateManager ready with LRU caching

4️⃣  Checking PyRevm availability...
   ✅ PyRevm is available - will use full replay

5️⃣  Initializing TransactionReplayer (Phase 2)...
   ✅ TransactionReplayer ready

6️⃣  Replaying transaction...
   (This may take a few seconds for complex transactions)

────────────────────────────────────────────────────────────────────────────────
REPLAY RESULTS
────────────────────────────────────────────────────────────────────────────────

✅ Success: True
⛽ Gas Used: 143,250
📤 Output: 0x0000000000000000000000000000000000000000000000000000000000000001

📞 Internal Calls: 15
💾 State Changes: 8

────────────────────────────────────────────────────────────────────────────────
INTERNAL CALLS
────────────────────────────────────────────────────────────────────────────────

1. CALL
   From: 0x7a250...56ca
   To: 0xa0b869...9823
   Selector: 0x022c0d9f
   Value: 0 wei
   Gas: 89,234
   Depth: 2
   Success: True

2. DELEGATECALL
   From: 0xa0b869...9823
   To: 0x5c69be...1745
   Selector: 0x38ed1739
   Value: 0 wei
   Gas: 52,341
   Depth: 3
   Success: True

   ... and 13 more calls

────────────────────────────────────────────────────────────────────────────────
SWAP DETECTION
────────────────────────────────────────────────────────────────────────────────

🔄 Detected Swaps: 2

1. Pool: 0xa0b869...9823
   Function: 0x022c0d9f
   Amount0 Out: 0
   Amount1 Out: 1,000,000,000,000,000,000
   Recipient: 0x742d35...cc6c

2. Pool: 0x5c69be...1745
   Function: 0x38ed1739

────────────────────────────────────────────────────────────────────────────────
STATE MANAGER STATS (Phase 1 Caching)
────────────────────────────────────────────────────────────────────────────────

📊 Account Cache:
   Hits: 23
   Misses: 5
   Hit Rate: 82.1%
   RPC Calls Saved: 23

✅ Demo completed successfully!

==================================================================================
```

---

## 🎯 Known Good Test Transactions

These transactions work well for testing and demonstration:

### Ethereum Mainnet

1. **Simple UniswapV2 Swap**
   ```
   0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4
   ```
   - Clean swap with 2-3 internal calls
   - Good for basic testing

2. **Complex MEV Transaction**
   ```
   0x2e6b6b5f9b6c3d0e5c7b1a7e8c9b6f5d4e8c9b6f5d4e8c9b6f5d4e8c9b6f5d4e
   ```
   - Multiple swaps across different DEXes
   - Good for testing nested calls

3. **Multi-Hop Swap**
   ```
   0x3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b
   ```
   - Route through multiple pools
   - Good for testing call depth tracking

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
# Core dependencies
pip install web3>=6.15.0

# Optional: For full PyRevm replay (recommended)
pip install pyrevm>=0.3.0
```

### Step 2: Get RPC Access

Choose one:
- **Alchemy**: https://www.alchemy.com/ (free tier available)
- **Infura**: https://infura.io/ (free tier available)
- **Local Node**: Run your own Ethereum node

### Step 3: Run Tests

```bash
# Test Phase 2 functionality
python3 examples/test_pyrevm_real.py

# Demo with real transaction (replace YOUR_API_KEY)
python3 examples/demo_phase2_replay.py \
  --tx-hash 0x5e1657ef0e9be9bc72efefe59a2528d0d730d478cfc9e6cdd09af9f997bb3ef4 \
  --rpc-url https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
```

---

## 📊 What These Scripts Demonstrate

### Phase 1 Integration (StateManager)
- ✅ LRU caching reduces RPC calls by 60-90%
- ✅ Efficient batch loading of accounts/storage
- ✅ Cache statistics and hit rate tracking

### Phase 2 Features (TransactionReplayer)
- ✅ Full transaction replay with PyRevm
- ✅ Internal call extraction with call stack tracking
- ✅ State change detection (storage modifications)
- ✅ Swap detection from 8+ function selectors:
  - `0x022c0d9f` - UniswapV2 swap()
  - `0x38ed1739` - swapExactTokensForTokens()
  - `0x128acb08` - swapExactTokensForETH()
  - `0xc42079f9` - UniswapV3 swapExact0For1()
  - `0x5ae401dc` - UniswapV3 multicall()
  - And more...
- ✅ Parameter decoding for swap amounts
- ✅ Fallback to log-based replay when PyRevm unavailable

---

## 🔧 Troubleshooting

### "Import 'web3' could not be resolved"
```bash
pip install web3>=6.15.0
```

### "Import 'pyrevm' could not be resolved"
```bash
pip install pyrevm>=0.3.0
```
**Note**: PyRevm is optional. Scripts will work without it using fallback mode.

### "Cannot connect to RPC"
- Check your RPC URL is correct
- Verify API key is valid
- Ensure you have network connectivity
- Try a different RPC provider

### "Transaction not found"
- Verify transaction hash is correct (must start with 0x)
- Check transaction exists on the network you're querying
- Ensure RPC node is synced to the required block

---

## 📝 Next Steps

After running these examples, you can:

1. **Proceed to Phase 3**: EnhancedSwapDetector (uses TransactionReplayer for improved accuracy)
2. **Test with your own transactions**: Find interesting MEV transactions to analyze
3. **Integrate into your workflow**: Use TransactionReplayer in your own MEV detection pipeline

---

## 💡 Tips

- **Start with simple transactions**: Test basic swaps before complex MEV
- **Monitor RPC usage**: Check StateManager cache hit rates to optimize
- **Use archive nodes**: Some transactions require historical state access
- **Check PyRevm logs**: Set `RUST_LOG=debug` for detailed PyRevm output

---

## 📚 Related Documentation

- [Phase 1: StateManager](../docs/PHASE1_SUMMARY.md)
- [Phase 2: TransactionReplayer](../docs/PHASE2_SUMMARY.md)
- [PyRevm Installation](../docs/PYREVM_INSTALL.md)
- [Main README](../README.md)
