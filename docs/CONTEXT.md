# MEV Inspector PyRevm - Project Context

> **Last Updated**: November 15, 2025  
> **Purpose**: Comprehensive context document for AI assistants to understand the project structure, architecture, and implementation details.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Design](#architecture--design)
3. [Core Components](#core-components)
4. [Data Models](#data-models)
5. [DEX Support](#dex-support)
6. [Detection Algorithms](#detection-algorithms)
7. [Report Modes](#report-modes)
8. [File Structure](#file-structure)
9. [Key Technologies](#key-technologies)
10. [Development Guidelines](#development-guidelines)

---

## 🎯 Project Overview

### Purpose
MEV Inspector is a comprehensive tool for detecting and analyzing Maximal Extractable Value (MEV) opportunities on Ethereum blockchain, specifically:
- **Arbitrage attacks**: Exploiting price differences across DEXs
- **Sandwich attacks**: Frontrunning and backrunning user transactions

### Key Differentiators
- ✅ Works with **Alchemy Free Tier** (no trace API required)
- ✅ Uses **PyRevm** for accurate local state simulation
- ✅ Supports both **historical detection** and **what-if analysis**
- ✅ **Dual report modes**: Basic (MEV only) and Full (complete details)
- ✅ Multi-DEX support: UniswapV2, UniswapV3, Balancer, Sushiswap, Curve

### Target Users
- MEV researchers analyzing historical data
- Bot developers testing detection algorithms
- Blockchain analysts studying MEV patterns
- Students learning about MEV extraction

---

## 🏗️ Architecture & Design

### High-Level Flow

```
User Input (Block Number)
        ↓
    CLI Interface (cli.py)
        ↓
    MEV Inspector (inspector.py)
        ↓
    ┌───────────────────────────────────┐
    │   RPC Client (rpc.py)             │
    │   - Fetch block data              │
    │   - Get transaction receipts      │
    │   - Query contract state          │
    └───────────────────────────────────┘
        ↓
    ┌───────────────────────────────────┐
    │   DEX Parsers (dex/*.py)          │
    │   - Parse swap events             │
    │   - Extract swap data             │
    │   - Calculate reserves            │
    └───────────────────────────────────┘
        ↓
    ┌───────────────────────────────────┐
    │   Detectors (detectors/*.py)      │
    │   - Arbitrage Detection           │
    │   - Sandwich Detection            │
    │   - What-If Analysis              │
    └───────────────────────────────────┘
        ↓
    ┌───────────────────────────────────┐
    │   State Simulator (simulator.py)  │
    │   - PyRevm EVM simulation         │
    │   - Pool state queries            │
    │   - Profit calculations           │
    └───────────────────────────────────┘
        ↓
    ┌───────────────────────────────────┐
    │   Reporters (reporters/*.py)      │
    │   - Basic Report (MEV only)       │
    │   - Full Report (all details)     │
    │   - Markdown formatting           │
    └───────────────────────────────────┘
        ↓
    Output (Console + JSON Report)
```

### Design Principles

1. **Modularity**: Each component (DEX parser, detector, reporter) is independent
2. **Extensibility**: Easy to add new DEX protocols or detection algorithms
3. **Compatibility**: Works without proprietary trace APIs (Alchemy Free Tier)
4. **Accuracy**: Uses PyRevm for precise EVM state simulation when available
5. **Flexibility**: Dual report modes for different use cases

---

## 🔧 Core Components

### 1. CLI Interface (`mev_inspect/cli.py`)

**Purpose**: Command-line interface using Click framework

**Key Functions**:
- `main()`: Entry point with Click group
- `block()`: Inspect single block command
- `range_cmd()`: Inspect range of blocks command
- `_display_results()`: Format and display MEV findings
- `_aggregate_results()`: Combine results from multiple blocks

**Options**:
```bash
--what-if          # Enable what-if analysis
--report PATH      # Save report to file
--report-mode      # Choose 'basic' or 'full' (default: full)
--rpc-url          # Alchemy RPC URL
--verbose          # Show debug information
```

**Example Flow**:
```python
# User runs: mev-inspect block 12914944 --report result.json --report-mode basic

1. Parse CLI arguments
2. Initialize RPC client with Alchemy URL
3. Create MEVInspector instance
4. Fetch block data via RPC
5. Extract swaps using DEX parsers
6. Detect arbitrages and sandwiches
7. Generate report (basic mode - MEV only)
8. Display results with Rich formatting
9. Save JSON report to file
```

---

### 2. RPC Client (`mev_inspect/rpc.py`)

**Purpose**: Interface with Ethereum nodes via JSON-RPC (no trace support)

**Key Methods**:
- `get_block()`: Fetch block data with/without full transactions
- `get_transaction()`: Get transaction details
- `get_transaction_receipt()`: Get receipt with logs and events
- `get_code()`: Retrieve contract bytecode
- `call()`: Execute read-only contract calls at specific block
- `get_storage_at()`: Read contract storage slots

**Technology**: Web3.py library

**Important Notes**:
- Works with Alchemy Free Tier (no `debug_trace` calls)
- All state queries use standard JSON-RPC methods
- Supports historical queries via block number parameter

---

### 3. MEV Inspector (`mev_inspect/inspector.py`)

**Purpose**: Core orchestrator that coordinates all components

**Key Methods**:

```python
def inspect_block(block_number: int, what_if: bool = False) -> InspectionResults:
    """Main inspection method"""
    1. Fetch block data via RPC
    2. Initialize state simulator at block
    3. Extract swaps from all transactions
    4. Detect historical MEV (arbitrages & sandwiches)
    5. If what_if: detect missed opportunities
    6. Return InspectionResults with all findings
```

```python
def _extract_swaps_with_info(block_number, transactions) -> (List[Swap], List[TransactionInfo]):
    """Extract swaps and collect transaction metadata"""
    1. Iterate through all transactions
    2. Get transaction receipt and logs
    3. Parse method signatures
    4. Count swap events by matching event signatures
    5. Use DEX parsers to parse actual swap data
    6. Collect transaction info (status, gas, logs)
    7. Return both swaps and transaction info
```

**Event Signatures Tracked**:
- `0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822`: UniswapV2 Swap
- `0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67`: UniswapV3 Swap

---

### 4. State Simulator (`mev_inspect/simulator.py`)

**Purpose**: Simulate EVM state for accurate profit calculations

**Two Modes**:

1. **PyRevm Mode** (when installed):
   - Uses Rust-based EVM simulator
   - Extremely fast local simulation
   - Accurate gas calculations
   - Full EVM opcodes support

2. **RPC Fallback Mode** (default):
   - Uses JSON-RPC calls
   - Compatible with any node
   - Slightly slower but works everywhere

**Key Methods**:

```python
def get_pool_state(pool_address: str, dex_type: str) -> Dict:
    """Query DEX pool state at current block"""
    - Load contract code
    - Query reserves/liquidity based on DEX type
    - Return state dict for calculations
```

**DEX-Specific State Queries**:
- UniswapV2: `getReserves()` → (reserve0, reserve1, timestamp)
- UniswapV3: `slot0()` → (sqrtPriceX96, tick, observationIndex)
- Balancer: `getPoolTokens()` → (tokens[], balances[])
- Curve: Multiple getters for reserves and A parameter

---

## 📊 Data Models

### Core Models (`mev_inspect/models.py`)

#### 1. **Swap**
```python
@dataclass
class Swap:
    tx_hash: str              # Transaction hash
    block_number: int         # Block number
    dex: str                  # DEX name (uniswap_v2, uniswap_v3, etc.)
    pool_address: str         # Pool contract address
    token_in: str             # Input token address
    token_out: str            # Output token address
    amount_in: int            # Input amount (raw)
    amount_out: int           # Output amount (raw)
    amount_in_eth: float      # Input in ETH (converted)
    amount_out_eth: float     # Output in ETH (converted)
```

#### 2. **Arbitrage**
```python
@dataclass
class Arbitrage:
    tx_hash: Optional[str]    # None for what-if scenarios
    block_number: int
    path: List[Swap]          # Sequence of swaps forming cycle
    profit_eth: float         # Total profit in ETH
    profit_token: str         # Token address where profit realized
    profit_amount: int        # Profit amount in token units
    gas_cost_eth: float       # Gas cost in ETH
    net_profit_eth: float     # profit_eth - gas_cost_eth
```

**Arbitrage Detection Logic**:
- Find transactions with multiple swaps
- Check if swaps form a cycle (start token = end token)
- Calculate net profit after gas costs
- Filter out unprofitable paths

#### 3. **Sandwich**
```python
@dataclass
class Sandwich:
    frontrun_tx: Optional[str]    # Frontrun transaction
    target_tx: str                # Victim transaction
    backrun_tx: Optional[str]     # Backrun transaction
    block_number: int
    profit_eth: float             # Total profit in ETH
    profit_token: str
    profit_amount: int
    victim_swap: Swap             # The victim's swap
    gas_cost_eth: float
    net_profit_eth: float
    frontrun_swap: Optional[Swap]
    backrun_swap: Optional[Swap]
```

**Sandwich Detection Logic**:
- Group swaps by pool and token pair
- Look for pattern: frontrun → victim → backrun
- All three in same pool and same token pair
- Calculate profit from manipulating victim's swap

#### 4. **TransactionInfo**
```python
@dataclass
class TransactionInfo:
    hash: str
    from_address: str
    to_address: Optional[str]
    value: int                    # ETH value sent
    gas_used: int
    gas_price: int
    status: int                   # 1=success, 0=failed
    log_count: int                # Number of logs emitted
    swap_events_found: int        # Swap events detected
    parsed_swaps: int             # Successfully parsed swaps
    method_signature: Optional[str]  # First 4 bytes of input
    error: Optional[str]
    event_signatures: List[str]   # All event topics
```

#### 5. **InspectionResults**
```python
@dataclass
class InspectionResults:
    block_number: int
    historical_arbitrages: List[Arbitrage]
    historical_sandwiches: List[Sandwich]
    whatif_opportunities: List[WhatIfOpportunity]
    transactions: List[TransactionInfo]    # Full mode only
    all_swaps: List[Swap]                  # Full mode only
    
    def to_dict(self) -> Dict:
        """Full report with all details"""
        
    def to_basic_dict(self) -> Dict:
        """Basic report with MEV findings only"""
```

---

## 🏊 DEX Support

### Base Class (`mev_inspect/dex/base.py`)

```python
class DEXParser(ABC):
    @abstractmethod
    def is_pool(address: str) -> bool:
        """Check if address is a pool"""
    
    @abstractmethod
    def parse_swap(tx_hash, tx_input, receipt_logs, block_number) -> Optional[Swap]:
        """Parse swap from transaction"""
    
    @abstractmethod
    def get_reserves(pool_address: str, block_number: int) -> Dict[str, int]:
        """Get pool reserves/state"""
    
    @abstractmethod
    def calculate_output(pool_address, token_in, token_out, amount_in, block_number) -> int:
        """Calculate swap output"""
```

### Implemented DEXs

#### 1. **UniswapV2** (`uniswap_v2.py`)
- **Event**: `Swap(address indexed sender, uint amount0In, uint amount1In, uint amount0Out, uint amount1Out, address indexed to)`
- **Signature**: `0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822`
- **Formula**: x * y = k (constant product)
- **Reserves**: `getReserves()` returns (reserve0, reserve1, blockTimestampLast)

#### 2. **UniswapV3** (`uniswap_v3.py`)
- **Event**: `Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)`
- **Signature**: `0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67`
- **Formula**: Concentrated liquidity with tick-based pricing
- **State**: `slot0()` for price, `liquidity()` for available liquidity

#### 3. **Sushiswap** (`sushiswap.py`)
- Same as UniswapV2 (fork)
- Different factory/router addresses

#### 4. **Balancer** (`balancer.py`)
- **Weighted pools**: Multiple tokens with different weights
- **Stable pools**: Low-slippage stablecoin pools
- **State**: `getPoolTokens()` returns (tokens[], balances[], lastChangeBlock)

#### 5. **Curve** (`curve.py`)
- **StableSwap**: Optimized for stablecoin swaps
- **CryptoSwap**: For volatile assets
- **Formula**: Hybrid constant sum and constant product

---

## 🔍 Detection Algorithms

### Arbitrage Detector (`mev_inspect/detectors/arbitrage.py`)

#### Historical Detection
```python
def detect_historical(swaps: List[Swap], block_number: int) -> List[Arbitrage]:
    """Detect arbitrages that actually occurred"""
    
    Algorithm:
    1. Group swaps by transaction hash
    2. For each transaction with 2+ swaps:
       a. Try all combinations of swaps
       b. Check if they form a cycle (start token = end token)
       c. Calculate profit = end_amount - start_amount - gas_cost
       d. If profit > 0: Create Arbitrage object
    3. Return all detected arbitrages
```

#### What-If Detection
```python
def detect_whatif(swaps: List[Swap], block_number: int, max_path_length: int = 3) -> List[Dict]:
    """Detect missed opportunities"""
    
    Algorithm:
    1. Build graph of pools and tokens from all swaps
    2. For each token pair:
       a. Find all paths between tokens (up to max_path_length)
       b. Simulate swaps along path using pool states
       c. Calculate potential profit
       d. If profit > 0: Record as missed opportunity
    3. Return all opportunities sorted by profit
```

**Key Methods**:
- `_check_arbitrage_path()`: Validate if swap sequence is profitable
- `_build_pool_graph()`: Create graph for pathfinding
- `_find_arbitrage_paths()`: DFS/BFS to find arbitrage cycles
- `_calculate_path_profit()`: Simulate swaps and compute profit

---

### Sandwich Detector (`mev_inspect/detectors/sandwich.py`)

#### Historical Detection
```python
def detect_historical(swaps: List[Swap], block_number: int) -> List[Sandwich]:
    """Detect sandwiches that actually occurred"""
    
    Algorithm:
    1. Group swaps by pool and token pair
    2. For each group with 3+ swaps:
       a. Look for pattern: swap_i, swap_i+1, swap_i+2
       b. Check if swap_i and swap_i+2 are from same address
       c. Check if swap_i+1 is from different address (victim)
       d. Verify: frontrun buys, victim buys (increases price), backrun sells
       e. Calculate profit from price manipulation
       f. If profit > 0: Create Sandwich object
    3. Return all detected sandwiches
```

#### What-If Detection
```python
def detect_whatif(swaps: List[Swap], block_number: int) -> List[Dict]:
    """Detect missed sandwich opportunities"""
    
    Algorithm:
    1. For each swap (potential victim):
       a. Calculate optimal frontrun amount
       b. Simulate victim's swap after frontrun (worse price)
       c. Calculate optimal backrun amount
       d. Compute profit = backrun_output - frontrun_input - gas_costs
       e. If profit > 0: Record as opportunity
    2. Return all opportunities sorted by profit
```

**Key Methods**:
- `_is_sandwich()`: Validate sandwich pattern
- `_calculate_sandwich_profit()`: Compute profit from price manipulation
- `_calculate_potential_sandwich_profit()`: Simulate hypothetical sandwich

---

## 📊 Report Modes

### Basic Mode (`reporters/basic_reporter.py`)

**Purpose**: Compact report with MEV findings only

**Output Structure**:
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
  "arbitrages": [...],
  "sandwiches": [...],
  "whatif_opportunities": [...]
}
```

**Use Cases**:
- Quick MEV opportunity scanning
- Sharing findings with others
- Analyzing MEV patterns across many blocks
- Lightweight storage

---

### Full Mode (`reporters/json_reporter.py`)

**Purpose**: Complete report with all transaction details

**Output Structure**:
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
  "all_swaps": [...],          // All 42 swaps
  "historical_arbitrages": [...],
  "historical_sandwiches": [...],
  "whatif_opportunities": [...]
}
```

**Use Cases**:
- Debugging detection algorithms
- Analyzing all block activity
- Research on swap patterns
- Validation and testing

---

## 📁 File Structure

```
mev-inspect-pyrevm/
├── README.md                    # Comprehensive documentation
├── CONTEXT.md                   # This file - project context
├── pyproject.toml              # Python dependencies and config
├── test_report_modes.sh        # Test script for report modes
├── .env                        # Environment variables (RPC URL)
├── .gitignore                  # Git ignore rules
│
├── mev_inspect/                # Main package
│   ├── __init__.py            # Package initialization
│   │
│   ├── cli.py                 # Click CLI interface (300 lines)
│   │   ├── main()             # Entry point
│   │   ├── block()            # Single block command
│   │   ├── range_cmd()        # Range command
│   │   └── _display_results() # Format output
│   │
│   ├── inspector.py           # Core MEV inspector (219 lines)
│   │   ├── inspect_block()    # Main inspection logic
│   │   └── _extract_swaps_with_info()  # Parse swaps
│   │
│   ├── rpc.py                 # RPC client (67 lines)
│   │   └── RPCClient class    # Web3 wrapper
│   │
│   ├── simulator.py           # State simulator (264 lines)
│   │   ├── StateSimulator class
│   │   └── PyRevm integration
│   │
│   ├── models.py              # Data models (318 lines)
│   │   ├── Swap, Arbitrage, Sandwich
│   │   ├── TransactionInfo
│   │   ├── InspectionResults
│   │   ├── to_dict()          # Full report
│   │   └── to_basic_dict()    # Basic report
│   │
│   ├── dex/                   # DEX protocol parsers
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract base class
│   │   ├── uniswap_v2.py      # UniswapV2 parser
│   │   ├── uniswap_v3.py      # UniswapV3 parser
│   │   ├── sushiswap.py       # Sushiswap parser
│   │   ├── balancer.py        # Balancer parser
│   │   └── curve.py           # Curve parser
│   │
│   ├── detectors/             # MEV detection algorithms
│   │   ├── __init__.py
│   │   ├── arbitrage.py       # Arbitrage detector (253 lines)
│   │   └── sandwich.py        # Sandwich detector (137 lines)
│   │
│   └── reporters/             # Report generators
│       ├── __init__.py
│       ├── basic_reporter.py  # Basic mode reporter
│       ├── json_reporter.py   # Full mode reporter
│       └── markdown_reporter.py  # Markdown formatter
│
└── result.json                # Example full mode output
```

---

## 🔑 Key Technologies

### Dependencies (pyproject.toml)

```toml
[project]
name = "mev-inspect-pyrevm"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "click>=8.1.0",           # CLI framework
    "web3>=6.15.0",           # Ethereum RPC client
    "eth-abi>=4.2.0",         # ABI encoding/decoding
    "eth-utils>=2.3.0",       # Ethereum utilities
    "pydantic>=2.5.0",        # Data validation (optional)
    "python-dotenv>=1.0.0",   # Environment variables
    "rich>=13.7.0",           # Terminal formatting
    "tabulate>=0.9.0",        # Table formatting
    "aiohttp>=3.9.0",         # Async HTTP (future use)
]
```

### Optional Dependencies

- **pyrevm**: Rust-based EVM simulator for faster local simulation
  - Not required - tool works with RPC fallback
  - Provides significant speed improvement for batch processing

---

## 💻 Development Guidelines

### Adding a New DEX Parser

1. Create new file in `mev_inspect/dex/` (e.g., `newdex.py`)
2. Inherit from `DEXParser` base class
3. Implement required methods:
   - `is_pool()`: Pool detection logic
   - `parse_swap()`: Event parsing
   - `get_reserves()`: State query
   - `calculate_output()`: Swap calculation
4. Add to `__init__.py` exports
5. Register in `inspector.py` and detector classes

Example:
```python
from mev_inspect.dex.base import DEXParser

class NewDEXParser(DEXParser):
    SWAP_EVENT_SIG = "0x..."
    
    def is_pool(self, address: str) -> bool:
        # Check if address is NewDEX pool
        pass
    
    def parse_swap(self, tx_hash, tx_input, receipt_logs, block_number):
        # Parse swap from logs
        pass
```

### Adding a New Detection Algorithm

1. Create detector in `mev_inspect/detectors/`
2. Implement `detect_historical()` and `detect_whatif()`
3. Add to `inspector.py` initialization
4. Create corresponding model in `models.py`
5. Update reporters to handle new MEV type

### Testing Strategy

```bash
# Test single block with basic mode
mev-inspect block 12914944 --report test_basic.json --report-mode basic

# Test with what-if analysis
mev-inspect block 12914944 --what-if --report test_whatif.json

# Test range (be careful - can be slow)
mev-inspect range 12914944 12914946 --report test_range.json

# Validate JSON output
cat test_basic.json | python -m json.tool

# Check for arbitrages
cat test_basic.json | jq '.arbitrages | length'
```

---

## 🔬 Known Limitations

1. **DEX Coverage**: Not all DEXs are fully supported
   - ✅ UniswapV2, UniswapV3, Sushiswap
   - ⚠️ Balancer, Curve (partial support)
   - ❌ 1inch, Bancor, other DEXs

2. **Gas Cost Calculation**: 
   - Currently simplified
   - Should use actual gas price × gas used from receipt

3. **What-If Analysis**:
   - Computationally expensive for many swaps
   - May miss complex multi-hop opportunities

4. **Flash Loans**: Not explicitly detected
   - Would need to detect flash loan protocols
   - Track loan → operations → repayment pattern

5. **Cross-Block MEV**: Only analyzes single blocks
   - No support for cross-block arbitrage
   - Doesn't track uncle/reorg MEV

---

## 📚 Example Workflows

### 1. Finding Arbitrages in Recent Blocks

```bash
# Get latest block
mev-inspect block $(cast block-number) --report-mode basic

# Scan last 100 blocks
LATEST=$(cast block-number)
START=$((LATEST - 100))
mev-inspect range $START $LATEST --report arbitrages.json --report-mode basic

# Extract just profitable arbitrages
cat arbitrages.json | jq '.aggregated.arbitrages[] | select(.net_profit_eth > 0)'
```

### 2. Analyzing Specific Transaction

```bash
# If you know a transaction is an arbitrage, find its block
TX="0x..."
BLOCK=$(cast tx $TX --json | jq .blockNumber)

# Inspect that block
mev-inspect block $BLOCK --report analysis.json --report-mode full --verbose

# Find the specific transaction in output
cat analysis.json | jq ".transactions[] | select(.hash == \"$TX\")"
```

### 3. Comparing DEX Liquidity

```bash
# Extract all swaps from block
mev-inspect block 12914944 --report swaps.json --report-mode full

# Count swaps per DEX
cat swaps.json | jq '.all_swaps | group_by(.dex) | map({dex: .[0].dex, count: length})'
```

---

## 🎓 Understanding MEV Concepts

### Arbitrage

**Definition**: Exploiting price differences across multiple DEXs

**Example**:
```
1. Buy 10 ETH of TOKEN on UniswapV2 for 5000 USDC
2. Sell 10 ETH of TOKEN on SushiSwap for 5100 USDC
3. Profit: 100 USDC - gas costs
```

**Detection**: Look for transactions with:
- Multiple swaps in a cycle
- Same start and end token
- Net profit after gas

### Sandwich Attack

**Definition**: Manipulating victim's transaction by frontrunning and backrunning

**Example**:
```
Block contains:
1. TX 123 (Attacker): Buy 100 ETH of TOKEN → Price increases
2. TX 124 (Victim):   Buy 10 ETH of TOKEN → Gets worse price
3. TX 125 (Attacker): Sell 100 ETH of TOKEN → Profit from inflated price
```

**Detection**: Look for:
- Three consecutive swaps in same pool
- First and third from same address
- Middle transaction (victim) gets worse execution

### What-If Analysis

**Purpose**: Identify opportunities that existed but weren't exploited

**Use Cases**:
- Understand MEV potential of blocks
- Test detection algorithms
- Research MEV extraction strategies
- Bot development and backtesting

---

## 🔧 Environment Setup

### Required Environment Variables

```bash
# .env file
ALCHEMY_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY

# Optional
DEBUG=false
LOG_LEVEL=INFO
```

### Installation for Development

```bash
# Clone repository
git clone <repo-url>
cd mev-inspect-pyrevm

# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate  # or `.venv/bin/activate.fish` for fish shell

# Install in development mode
pip install -e .

# Install optional dependencies
pip install pyrevm  # For faster simulation

# Run tests
./test_report_modes.sh
```

---

## 📝 Common Patterns

### Adding New CLI Option

```python
# In cli.py
@click.option(
    "--new-option",
    type=click.Choice(["value1", "value2"]),
    default="value1",
    help="Description of what this option does",
)
def block(block_number: int, new_option: str, ...):
    # Use new_option in implementation
    pass
```

### Extending Report Format

```python
# In models.py - InspectionResults class
def to_custom_dict(self) -> Dict[str, Any]:
    """Generate custom report format"""
    return {
        "custom_field": "custom_value",
        # ... custom structure
    }

# In cli.py - when saving report
if report_mode == "custom":
    json.dump(results.to_custom_dict(), f, indent=2)
```

### Adding New MEV Type

```python
# 1. Create model in models.py
@dataclass
class Liquidation:
    tx_hash: str
    protocol: str
    profit_eth: float
    # ... other fields

# 2. Add to InspectionResults
@dataclass
class InspectionResults:
    # ... existing fields
    liquidations: List[Liquidation] = field(default_factory=list)

# 3. Create detector in detectors/liquidation.py
class LiquidationDetector:
    def detect_historical(self, transactions, block_number):
        # Detection logic
        pass

# 4. Use in inspector.py
liquidation_detector = LiquidationDetector(...)
results.liquidations = liquidation_detector.detect_historical(...)
```

---

## 🎯 Future Enhancements

### Planned Features
- [ ] Flash loan detection
- [ ] Cross-block MEV analysis
- [ ] More DEX protocol support (1inch, Bancor, etc.)
- [ ] WebSocket support for real-time analysis
- [ ] Database storage for historical data
- [ ] Web UI for visualization
- [ ] Profit calculation improvements
- [ ] Gas optimization strategies
- [ ] MEV-Boost integration

### Performance Improvements
- [ ] Parallel block processing
- [ ] Caching layer for pool states
- [ ] Optimized graph algorithms for pathfinding
- [ ] Batch RPC requests

---

## 📞 Support & Resources

### Documentation
- `README.md`: User-facing documentation
- `CONTEXT.md`: This file - for AI assistants and developers
- Inline code comments for implementation details

### External Resources
- [Flashbots Documentation](https://docs.flashbots.net/)
- [MEV Research](https://explore.flashbots.net/)
- [PyRevm GitHub](https://github.com/bluealloy/pyrevm)
- [Alchemy Documentation](https://docs.alchemy.com/)

---

## 🏷️ Version History

- **v0.1.0** (Current): Initial release with basic/full report modes
  - Arbitrage detection
  - Sandwich detection  
  - What-if analysis
  - Multi-DEX support
  - Dual report modes

---

## ⚠️ IMPORTANT: PyRevm Usage Status

### Current Implementation Status

**PyRevm is NOT actually being used in the current implementation** despite the project name and documentation suggesting otherwise.

#### Code Analysis Results:

1. **PyRevm Import**: The code attempts to import pyrevm but has fallback logic:
   ```python
   try:
       from pyrevm import AccountInfo, BlockEnv, Evm, HexBytes, TransactTo
       PYREVM_AVAILABLE = True
   except ImportError:
       PYREVM_AVAILABLE = False
   ```

2. **Actual Usage**: PyRevm code exists but is:
   - ❌ **Not fully implemented** - Comments indicate "simplified for now"
   - ❌ **Missing critical setup** - State loading not implemented
   - ❌ **Fallback to RPC** - All actual operations use RPC calls
   - ❌ **Not in dependencies** - pyrevm is not in pyproject.toml dependencies

3. **Key Code Evidence** (`simulator.py` lines 47-51):
   ```python
   # Note: In a full implementation, we would need to:
   # 1. Load all account states from the RPC
   # 2. Load all contract code
   # 3. Set up storage for all contracts
   # This is simplified for now - in production, you'd want to cache state
   ```

4. **Actual Behavior**:
   - All pool state queries use `rpc_client.call()`
   - All simulations use `rpc_client.get_storage_at()`
   - PyRevm code paths exist but are incomplete

### Comparison with Flashbots mev-inspect-py

| Feature | mev-inspect-py (Flashbots) | mev-inspect-pyrevm (This Tool) |
|---------|----------------------------|--------------------------------|
| **Trace API Required** | ✅ YES - Requires Erigon traces | ❌ NO - Works with standard RPC |
| **State Simulation** | Uses trace_* APIs | Uses RPC calls (not pyrevm) |
| **Node Requirements** | Erigon/OpenEthereum archival | Any node with eth_call support |
| **Database** | ✅ PostgreSQL required | ❌ No database needed |
| **Architecture** | Kubernetes + Docker | Simple Python CLI |
| **Data Storage** | Persistent in Postgres | JSON files only |
| **Swap Detection** | Trace-based parsing | Event log parsing |
| **Status** | ⚠️ Deprecated by Flashbots | ✅ Active (but incomplete) |

### Key Differences Explained

#### 1. **Trace API Dependency**

**mev-inspect-py (Flashbots)**:
- Requires `debug_traceTransaction` or Erigon trace APIs
- Can see internal calls and state changes
- Needs specialized archive nodes (expensive!)
- Example: Needs nodes like Erigon with full trace support

**mev-inspect-pyrevm (This Tool)**:
- Uses only standard JSON-RPC methods:
  - `eth_getBlockByNumber`
  - `eth_getTransactionReceipt`
  - `eth_call`
  - `eth_getStorageAt`
- Works with **Alchemy Free Tier** ✅
- Works with any standard Ethereum node

#### 2. **Detection Methodology**

**mev-inspect-py (Flashbots)**:
```
Block → Trace all TXs → Parse internal calls → Identify swaps → Detect MEV
        ^^^^^^^^^^^^^^^
        Requires trace API
```

**mev-inspect-pyrevm (This Tool)**:
```
Block → Get receipts → Parse event logs → Identify swaps → Detect MEV
        ^^^^^^^^^^^^^^
        Uses standard RPC
```

#### 3. **Swap Detection Approach**

**mev-inspect-py**:
- Analyzes EVM traces to see internal contract calls
- Can detect swaps even without events
- More comprehensive but requires traces

**mev-inspect-pyrevm**:
- Parses event logs from receipts (Swap events)
- Matches known event signatures:
  - `0xd78ad95...` - UniswapV2 Swap
  - `0xc42079f...` - UniswapV3 Swap
- Faster but may miss some swaps without events

#### 4. **Infrastructure Requirements**

**mev-inspect-py**:
```yaml
Requirements:
- Kubernetes cluster (kind/k8s)
- Docker containers
- PostgreSQL database
- Erigon/OpenEthereum node with trace support
- High-performance infrastructure

Cost: $$$$ (High - specialized nodes needed)
```

**mev-inspect-pyrevm**:
```yaml
Requirements:
- Python 3.10+
- Standard RPC endpoint (Alchemy free tier)
- No database needed
- No Docker/Kubernetes

Cost: $ (Low - free tier RPC works)
```

### Why the Name "pyrevm" is Misleading

The project is named `mev-inspect-pyrevm` but:

1. **PyRevm is not actually used** - All simulations use RPC calls
2. **PyRevm code is incomplete** - Marked as "simplified" in comments
3. **PyRevm is not a dependency** - Not listed in pyproject.toml
4. **Name suggests capability** - Implies advanced EVM simulation not present

**More Accurate Name Would Be**: `mev-inspect-rpc` or `mev-inspect-lite`

### What PyRevm Would Enable (If Implemented)

If PyRevm were fully implemented, it would provide:

1. **Local EVM Simulation**:
   - No RPC calls needed for simulations
   - Much faster for batch processing
   - More accurate gas calculations

2. **Offline Analysis**:
   - Download block data once
   - Run simulations locally
   - No API rate limits

3. **Complex What-If Scenarios**:
   - Simulate hypothetical transactions
   - Test different MEV strategies
   - Model flash loan attacks

### Current Reality vs. Documentation

| Claim in Docs | Reality |
|---------------|---------|
| "Uses pyrevm for simulation" | ❌ Uses RPC calls only |
| "Accurate state simulation" | ⚠️ Limited - no state caching |
| "Works without trace APIs" | ✅ TRUE - this is accurate |
| "Faster with pyrevm" | ❓ Unverified - not implemented |

### Advantages of Current Approach (RPC-only)

Despite not using PyRevm, the tool has real advantages:

1. ✅ **Accessibility**: Works with free RPC providers
2. ✅ **Simplicity**: No complex setup required
3. ✅ **Compatibility**: Any standard Ethereum node works
4. ✅ **Ease of use**: Simple CLI, no database needed
5. ✅ **Good for learning**: Easier to understand codebase

### Limitations vs. Flashbots mev-inspect-py

1. **Less Comprehensive**:
   - May miss swaps without events
   - No internal call analysis
   - Limited to event-emitting protocols

2. **No Historical Database**:
   - Each run is independent
   - No historical trend analysis
   - Can't query past MEV across blocks

3. **Limited Accuracy**:
   - RPC-based state queries are slower
   - No proper state caching
   - Gas calculations are simplified

4. **DEX Coverage**:
   - Only supports protocols with standard events
   - Custom/obscure DEXs not supported
   - Requires manual addition of new protocols

### Recommendations for Improvement

To make this tool truly leverage PyRevm:

1. **Implement Full PyRevm Integration**:
   ```python
   # Need to add:
   - State loading from RPC
   - Account/storage caching
   - Full EVM simulation
   - Transaction replay
   ```

2. **Add PyRevm to Dependencies**:
   ```toml
   dependencies = [
       "pyrevm>=0.3.0",  # Add this
       # ... other deps
   ]
   ```

3. **Implement State Management**:
   - Cache account states
   - Load contract code
   - Set up storage mappings
   - Handle state updates

4. **Add Benchmarks**:
   - Compare RPC vs PyRevm performance
   - Measure accuracy differences
   - Document trade-offs

### Use Cases Where This Tool Excels

Despite limitations, this tool is excellent for:

1. **Learning MEV Concepts**:
   - Simple codebase
   - Clear detection logic
   - Easy to modify

2. **Quick Analysis**:
   - Check specific blocks fast
   - No infrastructure setup
   - Instant results

3. **Development/Testing**:
   - Test detection algorithms
   - Prototype new MEV types
   - Educational purposes

4. **Resource-Constrained Environments**:
   - No database needed
   - Works on laptops
   - Free RPC tier sufficient

### Conclusion

**The tool is NOT using PyRevm** despite its name. It's essentially a **lightweight, RPC-based MEV detector** that:
- ✅ Works great for basic MEV detection
- ✅ Much easier to set up than Flashbots version
- ✅ Perfect for learning and experimentation
- ❌ Not suitable for production MEV bot operations
- ❌ Less comprehensive than trace-based approaches
- ❌ Name is misleading about capabilities

**For Production MEV Bots**: Use Flashbots mev-inspect-py or build your own with full trace support.

**For Learning/Research**: This tool (mev-inspect-pyrevm) is perfect despite not using PyRevm!

---

**End of Context Document**

*This document should be updated whenever major changes are made to the architecture, algorithms, or data models.*

**Last Updated**: November 18, 2025 - Added critical analysis of PyRevm usage status
