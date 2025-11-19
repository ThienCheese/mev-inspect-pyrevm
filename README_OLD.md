# MEV Inspector with PyRevm

A comprehensive MEV (Maximal Extractable Value) inspection tool for Ethereum that uses pyrevm for accurate state simulation. Unlike mev-inspect-py, this tool works with Alchemy Free Tier RPC (no trace support) and provides both historical MEV detection and "what-if" scenario analysis.

## ✨ Features

- 🔍 **Historical MEV Detection**: Inspect blocks or block ranges to detect arbitrage and sandwich attacks that actually occurred
- 🎯 **What-If Analysis**: Simulate missed MEV opportunities to predict future patterns
- 🏊 **Multi-DEX Support**: Supports UniswapV2, UniswapV3, Balancer, Sushiswap, and Curve
- 📊 **Dual Report Modes**: Choose between basic (MEV findings only) or full (complete details) reports
- ⚡ **Accurate Simulation**: Uses pyrevm for precise state simulation without requiring trace APIs
- 💰 **Profit Calculations**: Automatic calculation of MEV profits including gas costs

---

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- pip or poetry for package management
- Alchemy API key (free tier works!)

### Setup Steps

1. **Clone or navigate to this directory:**
   ```bash
   cd mev-inspect-pyrevm
   ```

2. **Install the package:**
   ```bash
   pip install -e .
   ```
   
   Or with poetry:
   ```bash
   poetry install
   ```

3. **Get an Alchemy API key** from https://www.alchemy.com/

4. **Configure your RPC URL:**
   
   Option A - Environment variable:
   ```bash
   export ALCHEMY_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"
   ```
   
   Option B - Create a `.env` file:
   ```
   ALCHEMY_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
   ```

### Optional: Install pyrevm for Enhanced Simulation

```bash
# For faster local simulation (optional, not required)
pip install pyrevm
```

> **Note**: The tool works without pyrevm using RPC calls, but pyrevm provides faster local simulation.

---

## 🚀 Quick Start

### Basic Commands

```bash
# Inspect a single block
mev-inspect block 12914944

# Inspect a range of blocks
mev-inspect range 12914940 12914950

# Include what-if analysis for missed opportunities
mev-inspect block 12914944 --what-if

# Generate a report
mev-inspect block 12914944 --report result.json
```

---

## 📊 Report Modes

MEV Inspector supports **2 report modes** to fit different use cases:

### 1. 🎯 Basic Mode (`--report-mode basic`)

**Compact report focusing only on MEV findings** - perfect for quick analysis!

#### Features:
- ✅ Only MEV opportunities (arbitrages & sandwiches)
- ✅ Clean, easy-to-read format
- ✅ Profit calculations with gas costs
- ✅ Swap paths for arbitrages
- ✅ Frontrun/backrun details for sandwiches
- ❌ No raw transaction data
- ❌ No complete swap lists

#### Output Structure:
```json
{
  "block_number": 12914944,
  "mev_summary": {
    "total_mev_profit_eth": 0.53560707,
    "arbitrages_found": 2,
    "arbitrage_profit_eth": 0.53560707,
    "sandwiches_found": 0,
    "sandwich_profit_eth": 0.0,
    "whatif_opportunities": 0
  },
  "arbitrages": [
    {
      "id": "arb_1",
      "transaction_hash": "0xbb7fd3d6-3e2b-45f3-b174-63b44f5c7ed4",
      "profit_token_address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
      "block_number": 12914944,
      "profit_eth": 0.53560707,
      "gas_cost_eth": 0.0,
      "net_profit_eth": 0.53560707,
      "swap_path": [...]
    }
  ],
  "sandwiches": [],
  "whatif_opportunities": []
}
```

#### Example Usage:
```bash
# Single block
mev-inspect block 12914944 --report result_basic.json --report-mode basic

# Range of blocks
mev-inspect range 12914940 12914950 --report results_basic.json --report-mode basic

# With what-if analysis
mev-inspect block 12914944 --what-if --report result_basic.json --report-mode basic
```

---

### 2. 📋 Full Mode (`--report-mode full`) - Default

**Complete report with all transaction details** - for deep analysis!

#### Features:
- ✅ All transactions in the block
- ✅ Detailed logs and events
- ✅ Swap event detection info
- ✅ Transaction status (success/failed)
- ✅ Gas usage details
- ✅ All parsed swaps from DEX protocols
- ✅ MEV findings (arbitrages & sandwiches)

#### Output Structure:
```json
{
  "block_number": 12914944,
  "summary": {
    "total_transactions": 222,
    "successful_transactions": 186,
    "failed_transactions": 36,
    "total_logs": 308,
    "swap_events_detected": 42,
    "swaps_parsed": 42,
    "arbitrages_found": 2,
    "sandwiches_found": 0,
    "whatif_opportunities": 0
  },
  "transactions": [...],      // All 222 transactions
  "all_swaps": [...],          // All 42 parsed swaps
  "historical_arbitrages": [...],
  "historical_sandwiches": [...],
  "whatif_opportunities": [...]
}
```

#### Example Usage:
```bash
# Full mode (default)
mev-inspect block 12914944 --report result_full.json --report-mode full

# Or simply (full is default)
mev-inspect block 12914944 --report result_full.json
```

---

### 📊 Mode Comparison

| Feature | Basic Mode | Full Mode |
|---------|------------|-----------|
| MEV Findings | ✅ | ✅ |
| MEV Summary | ✅ | ✅ |
| All Transactions | ❌ | ✅ |
| Transaction Details | ❌ | ✅ |
| All Swaps | ❌ | ✅ |
| Event Logs | ❌ | ✅ |
| File Size | 📦 Small | 📦📦📦 Large |
| Readability | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 💡 When to Use Each Mode?

**Use Basic Mode when:**
- 🎯 You only care about MEV opportunities
- 📦 You need compact reports for quick analysis
- 📤 You want to share findings with others
- 🔄 You're scanning many blocks and only want MEV data

**Use Full Mode when:**
- 🐛 You need to debug and analyze in detail
- 🔍 You want to see all block activity
- 📈 You're researching swap patterns
- ✅ You need to validate detection algorithms

---

## 🔧 Advanced Usage

### Test Script

Run both modes and compare:

```bash
# Make script executable
chmod +x test_report_modes.sh

# Run tests
./test_report_modes.sh

# Compare file sizes
ls -lh result_basic.json result_full.json
```

### Working with Reports

```bash
# Pretty print basic report
cat result_basic.json | python -m json.tool

# Count arbitrages (requires jq)
cat result_basic.json | jq '.arbitrages | length'

# Get total MEV profit
cat result_basic.json | jq '.mev_summary.total_mev_profit_eth'

# List all arbitrage transaction hashes
cat result_basic.json | jq '.arbitrages[].transaction_hash'
```

### Range Analysis

```bash
# Scan multiple blocks with basic mode
mev-inspect range 12914940 12914950 --report-mode basic --report mev_findings.json

# Output contains:
# - blocks: array of per-block basic reports
# - aggregated: consolidated MEV findings
```

---

## 🏗️ Architecture

```
mev-inspect-pyrevm/
├── mev_inspect/
│   ├── cli.py              # Click-based CLI interface
│   ├── rpc.py              # RPC client for Alchemy (no trace support)
│   ├── simulator.py        # PyRevm integration for state simulation
│   ├── inspector.py        # Main MEV inspection engine
│   ├── models.py           # Data models (Arbitrage, Sandwich, etc.)
│   ├── dex/                # DEX contract interfaces and parsers
│   │   ├── uniswap_v2.py
│   │   ├── uniswap_v3.py
│   │   ├── balancer.py
│   │   ├── sushiswap.py
│   │   └── curve.py
│   ├── detectors/          # MEV detection algorithms
│   │   ├── arbitrage.py
│   │   └── sandwich.py
│   └── reporters/          # Report generation
│       ├── basic_reporter.py   # Basic mode reporter
│       ├── json_reporter.py    # Full mode reporter
│       └── markdown_reporter.py
```

---

## 📝 Examples

### Example 1: Quick MEV Check
```bash
# Check for MEV in recent block
mev-inspect block 12914944 --report-mode basic --report mev.json
```

### Example 2: Deep Analysis
```bash
# Full analysis with what-if scenarios
mev-inspect block 12914944 --what-if --report full_analysis.json --report-mode full --verbose
```

### Example 3: Historical Scan
```bash
# Scan 100 blocks for MEV opportunities
mev-inspect range 12914900 12915000 --report-mode basic --report historical_mev.json
```

---

## 🔍 Understanding the Output

### Arbitrage Detection

Arbitrages are detected when:
1. Multiple swaps occur in the same transaction
2. The swaps form a cycle (start and end with same token)
3. Net profit is positive after accounting for gas

### Sandwich Detection

Sandwiches are detected when:
1. Frontrun transaction occurs before victim's swap
2. Victim transaction executes
3. Backrun transaction occurs after victim's swap
4. Same address controls frontrun and backrun
5. Net profit is positive

---

## ⚠️ Important Notes

- ✅ Works with Alchemy Free Tier (no trace API required)
- ✅ Historical MEV detection analyzes swaps that actually occurred
- ✅ What-if analysis simulates missed opportunities
- ✅ Reports are generated in JSON format
- ✅ Gas costs are automatically calculated when possible
- ⚠️ Some DEX protocols may not be fully supported yet

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional DEX protocol support
- More sophisticated MEV detection algorithms
- Performance optimizations
- Better visualization tools

---

## 📄 License

MIT

---

## 🙏 Acknowledgments

- Built with [pyrevm](https://github.com/bluealloy/pyrevm) for EVM simulation
- Uses [Alchemy](https://www.alchemy.com/) for Ethereum RPC access
- Inspired by [mev-inspect-py](https://github.com/flashbots/mev-inspect-py)

