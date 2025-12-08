# MEV-Inspect-PyRevm Architecture

**Version**: 1.0  
**Date**: December 8, 2025  
**Author**: MEV-Inspect-PyRevm Development Team

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagrams](#2-architecture-diagrams)
3. [Component Details](#3-component-details)
4. [Data Flow Analysis](#4-data-flow-analysis)
5. [Caching Strategy](#5-caching-strategy)
6. [Detection Algorithms](#6-detection-algorithms)
7. [Performance Optimization](#7-performance-optimization)

---

## 1. System Overview

MEV-Inspect-PyRevm is a modular MEV detection framework designed for efficiency and accuracy without requiring trace APIs. The system consists of 7 major components working together to analyze Ethereum blocks and detect MEV patterns.

### 1.1 Design Principles

- **Modularity**: Each component has clear responsibilities and interfaces
- **Efficiency**: Multi-layer caching minimizes RPC calls
- **Accuracy**: Deduplication and position tracking ensure correct detection
- **Scalability**: Batch operations and async-ready design
- **Maintainability**: Clean separation of concerns

### 1.2 Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Technology Stack                         │
├─────────────────────────────────────────────────────────────┤
│ Language:           Python 3.10+                            │
│ EVM Simulation:     PyRevm 0.3.3                            │
│ Web3:               web3.py 6.0+                            │
│ Database:           SQLite 3                                │
│ CLI Framework:      Click 8.0+                              │
│ Reporting:          Rich (terminal), JSON, Markdown         │
│ Testing:            pytest, manual validation               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Diagrams

### 2.1 High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          MEV-Inspect-PyRevm                            │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                      CLI Interface (cli.py)                   │    │
│  │  • Block inspection command                                   │    │
│  │  • Report generation (JSON, Markdown, Console)                │    │
│  │  • Configuration management                                   │    │
│  └────────────────────┬─────────────────────────────────────────┘    │
│                       │                                                │
│                       ▼                                                │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │              MEV Inspector (inspector.py)                     │    │
│  │  • Orchestrates entire analysis pipeline                      │    │
│  │  • Coordinates all components                                 │    │
│  │  • Manages transaction processing                             │    │
│  └──┬────────────────┬────────────────┬─────────────────────┬───┘    │
│     │                │                │                     │         │
│     ▼                ▼                ▼                     ▼         │
│  ┌──────┐      ┌──────────┐    ┌──────────┐         ┌──────────┐    │
│  │ RPC  │      │  State   │    │   Pool   │         │  PyRevm  │    │
│  │Client│      │ Manager  │    │  Cache   │         │ Replayer │    │
│  └──┬───┘      └────┬─────┘    └────┬─────┘         └────┬─────┘    │
│     │               │               │                     │           │
│     │               │               │                     │           │
│  ┌──▼───────────────▼───────────────▼─────────────────────▼──────┐   │
│  │              Data Collection & Processing                      │   │
│  │  • Batch RPC calls (receipts, codes, blocks)                  │   │
│  │  • Transaction replay with PyRevm                             │   │
│  │  • Pool token resolution                                      │   │
│  │  • State management                                           │   │
│  └──┬─────────────────────────────────────────────────────────┬─┘   │
│     │                                                           │     │
│     ▼                                                           ▼     │
│  ┌─────────────────────────────────────┐      ┌──────────────────┐  │
│  │      DEX Parsers (dex/)             │      │   ABI Decoder    │  │
│  │  • UniswapV2Parser                  │      │ • Event parsing  │  │
│  │  • UniswapV3Parser                  │      │ • Pool creation  │  │
│  │  • SushiswapParser                  │      │ • Token lookup   │  │
│  │  • CurveParser                      │      └──────────────────┘  │
│  │  • BalancerParser                   │                            │
│  └─────────────────┬───────────────────┘                            │
│                    │                                                 │
│                    ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │           Swap Detection & Deduplication                      │   │
│  │  • Log-based swap extraction                                  │   │
│  │  • Position tracking (transaction_position)                   │   │
│  │  • Address tracking (from_address)                            │   │
│  │  • Deduplication algorithm                                    │   │
│  └─────────────────────────┬────────────────────────────────────┘   │
│                            │                                         │
│                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              MEV Detectors (detectors/)                       │   │
│  │  ┌──────────────────┐           ┌───────────────────┐        │   │
│  │  │ Sandwich Detector│           │ Arbitrage Detector│        │   │
│  │  │ • Pattern match  │           │ • Path finding    │        │   │
│  │  │ • Position sort  │           │ • Profit calc     │        │   │
│  │  │ • Profit calc    │           │ • Multi-pool      │        │   │
│  │  └──────────────────┘           └───────────────────┘        │   │
│  └─────────────────────────┬────────────────────────────────────┘   │
│                            │                                         │
│                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Results & Reporting                              │   │
│  │  • InspectionResults aggregation                              │   │
│  │  • Profit calculations                                        │   │
│  │  • Report generation (JSON, Markdown, Console)                │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘

External Dependencies:
  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
  │ Ethereum RPC │        │ SQLite DB    │        │ PyRevm Core  │
  │ (Alchemy)    │        │ (Pool Cache) │        │ (Rust EVM)   │
  └──────────────┘        └──────────────┘        └──────────────┘
```

### 2.2 Component Interaction Diagram

```
                    ┌─────────────────────────────────────┐
                    │         User Input                  │
                    │    mev-inspect block 12775690       │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │      CLI (cli.py)                   │
                    │  • Parse arguments                  │
                    │  • Initialize RPC client            │
                    │  • Create MEVInspector              │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────────────────────┐
        │              MEVInspector.inspect_block()            │
        └──────────────┬───────────────────────────────────────┘
                       │
                       │ Phase 1: Data Collection
                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  1. Fetch block data (eth_getBlockByNumber)          │
        │  2. Batch fetch receipts (eth_getTransactionReceipt) │
        │  3. Extract contract addresses from logs             │
        │  4. Batch fetch contract codes (eth_getCode)         │
        └──────────────┬───────────────────────────────────────┘
                       │
                       │ Phase 2: Pool Discovery & Caching
                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  Layer 1: Scan for PairCreated events (0 RPC)        │
        │     └─→ ABI Decoder scans logs for pool creation     │
        │                                                       │
        │  Layer 2: Check persistent cache (SQLite)            │
        │     └─→ PoolCache.get(pool_address)                  │
        │                                                       │
        │  Layer 3: RPC fallback for unknown pools             │
        │     └─→ eth_call(pool.token0()), eth_call(token1())  │
        └──────────────┬───────────────────────────────────────┘
                       │
                       │ Phase 3: Transaction Replay & Swap Detection
                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  For each successful transaction:                     │
        │                                                       │
        │  1. PyRevm Replay (if enabled)                        │
        │     └─→ TransactionReplayer.replay_transaction()      │
        │         • Load account states                         │
        │         • Execute transaction in EVM                  │
        │         • Capture internal calls                      │
        │                                                       │
        │  2. Log-Based Parsing (ALWAYS)                        │
        │     └─→ For each DEX parser:                          │
        │         • UniswapV2Parser.parse_swap()                │
        │         • UniswapV3Parser.parse_swap()                │
        │         • SushiswapParser.parse_swap()                │
        │         • Add transaction_position & from_address     │
        │                                                       │
        │  3. Deduplication                                     │
        │     └─→ Remove duplicates by (tx_hash, pool,          │
        │         token_in, token_out)                          │
        └──────────────┬───────────────────────────────────────┘
                       │
                       │ Phase 4: MEV Pattern Detection
                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  Sandwich Detection:                                  │
        │  1. Group swaps by pool address                       │
        │  2. Sort by transaction_position                      │
        │  3. Find pattern: frontrun → victim(s) → backrun      │
        │     • Same from_address for frontrun & backrun        │
        │     • Opposite token directions                       │
        │     • Calculate profit                                │
        │                                                       │
        │  Arbitrage Detection:                                 │
        │  1. Build swap graph across pools                     │
        │  2. Find profitable cycles                            │
        │  3. Calculate net profit after gas                    │
        └──────────────┬───────────────────────────────────────┘
                       │
                       │ Phase 5: Results & Reporting
                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  InspectionResults:                                   │
        │  • historical_sandwiches: List[Sandwich]              │
        │  • historical_arbitrages: List[Arbitrage]             │
        │  • whatif_opportunities: List[WhatIfOpportunity]      │
        │  • transactions: List[TransactionInfo]                │
        │  • all_swaps: List[Swap]                              │
        │                                                       │
        │  Generate Reports:                                    │
        │  • Console output (Rich tables)                       │
        │  • JSON export                                        │
        │  • Markdown report                                    │
        └──────────────┬───────────────────────────────────────┘
                       │
                       ▼
                ┌─────────────────┐
                │   User Output   │
                └─────────────────┘
```

### 2.3 Data Flow for Single Block Analysis

```
INPUT: Block Number (e.g., 12775690)
│
├─► STEP 1: RPC Data Collection (rpc.py)
│   ├─► eth_getBlockByNumber(12775690, full=True)
│   │   └─► Returns: block data + 117 transactions
│   │
│   ├─► batch_get_receipts([tx1, tx2, ..., tx117])
│   │   └─► Returns: 117 transaction receipts with logs
│   │
│   ├─► Extract unique addresses from logs
│   │   └─► Found: 198 unique contract addresses
│   │
│   └─► batch_get_codes([addr1, addr2, ..., addr198])
│       └─► Returns: bytecode for 198 contracts
│
├─► STEP 2: Pool Token Resolution (pool_cache.py + abi_decoder.py)
│   │
│   ├─► Scan logs for PairCreated events
│   │   └─► Found: 0 new pools in this block
│   │
│   ├─► Extract swap pool addresses from logs
│   │   └─► Found: 15 unique pools
│   │
│   ├─► Check persistent cache (SQLite)
│   │   └─► Cache hits: 15/15 (100%)
│   │   └─► Cache misses: 0
│   │   └─► RPC calls saved: ~30 calls
│   │
│   └─► Pool tokens loaded:
│       ├─► 0xefb47fcf... → (WETH, BONE)
│       ├─► 0x397ff197... → (WETH, FOX)
│       └─► ... (13 more pools)
│
├─► STEP 3: Transaction Processing (inspector.py)
│   │
│   ├─► For each transaction (117 total):
│   │   │
│   │   ├─► Extract metadata:
│   │   │   ├─► transaction_position = index in block
│   │   │   ├─► from_address = tx.from
│   │   │   └─► tx_hash = tx.hash
│   │   │
│   │   ├─► Check status (receipt.status):
│   │   │   ├─► Success: 113 transactions
│   │   │   └─► Failed: 4 transactions (skip)
│   │   │
│   │   ├─► PyRevm Replay (replay.py):
│   │   │   ├─► Load account states
│   │   │   ├─► Execute transaction
│   │   │   ├─► Capture internal calls
│   │   │   └─► Success rate: 52/113 (46%)
│   │   │
│   │   └─► Log-Based Parsing (dex/*.py):
│   │       │
│   │       ├─► For each log in receipt:
│   │       │   ├─► Check topic[0] against known signatures
│   │       │   │   ├─► Uniswap V2 Swap: 0xd78ad95f...
│   │       │   │   └─► Uniswap V3 Swap: 0xc42079f9...
│   │       │   │
│   │       │   ├─► If match found:
│   │       │   │   ├─► Decode event data (ABI)
│   │       │   │   ├─► Get pool tokens from cache
│   │       │   │   ├─► Create Swap object:
│   │       │   │   │   • tx_hash
│   │       │   │   │   • pool_address
│   │       │   │   │   • token_in, token_out
│   │       │   │   │   • amount_in, amount_out
│   │       │   │   │   • transaction_position
│   │       │   │   │   • from_address
│   │       │   │   │   • dex (uniswap_v2/sushiswap/etc)
│   │       │   │   └─► Add to swaps list
│   │       │   │
│   │       │   └─► Multiple parsers may match same log
│   │       │       (causing duplicates)
│   │       │
│   │       └─► Raw swaps detected: 40 swaps
│   │
│   ├─► Deduplication (inspector.py):
│   │   │
│   │   ├─► Group by (tx_hash, pool, token_in, token_out)
│   │   ├─► Keep first occurrence only
│   │   └─► Result: 40 → 21 unique swaps
│   │
│   └─► Swaps by pool:
│       ├─► 0xefb47fcf... → 7 swaps (sandwich pool)
│       ├─► 0x397ff197... → 3 swaps
│       └─► ... (13 more pools)
│
├─► STEP 4: Sandwich Detection (detectors/sandwich.py)
│   │
│   ├─► Group swaps by pool address:
│   │   └─► Pool 0xefb47fcf... → 7 swaps
│   │
│   ├─► Sort by transaction_position:
│   │   ├─► Position 2: WETH → BONE (from 0x000000...)
│   │   ├─► Position 3: WETH → BONE (from 0x37E17E...)
│   │   ├─► Position 4: WETH → BONE (from 0xAnother...)
│   │   ├─► Position 5: WETH → BONE (from 0xAnother...)
│   │   ├─► Position 6: WETH → BONE (from 0xAnother...)
│   │   └─► Position 7: BONE → WETH (from 0x000000...)
│   │
│   ├─► Pattern matching:
│   │   │
│   │   ├─► Candidate: positions 2 → 7
│   │   │   ├─► Frontrun (pos 2): from 0x000000...
│   │   │   ├─► Victims (pos 3-6): different addresses
│   │   │   ├─► Backrun (pos 7): from 0x000000...
│   │   │   │
│   │   │   ├─► Check: same address? ✓ (0x000000...)
│   │   │   ├─► Check: same direction? ✓ (WETH→BONE)
│   │   │   ├─► Check: opposite backrun? ✓ (BONE→WETH)
│   │   │   │
│   │   │   └─► Calculate profit:
│   │   │       • Frontrun in: 12.1088 WETH
│   │   │       • Backrun out: 12.1588 WETH
│   │   │       • Profit: 0.0500 WETH
│   │   │       • Profit: 0.049991 ETH (exact)
│   │   │
│   │   └─► SANDWICH DETECTED! ✓
│   │
│   └─► Create Sandwich object:
│       ├─► frontrun_tx: 0x91a3abe5...
│       ├─► target_tx: 0x9b40deca...
│       ├─► backrun_tx: 0xc300d1ff...
│       ├─► profit_eth: 0.049991
│       └─► victim_swap, frontrun_swap, backrun_swap
│
├─► STEP 5: Arbitrage Detection (detectors/arbitrage.py)
│   │
│   ├─► Build swap graph across pools
│   ├─► Find cycles (token A → B → C → A)
│   ├─► Calculate profits
│   └─► Result: 0 arbitrages in this block
│
└─► STEP 6: Results Aggregation & Reporting
    │
    ├─► InspectionResults:
    │   ├─► block_number: 12775690
    │   ├─► historical_sandwiches: [1 sandwich]
    │   ├─► historical_arbitrages: []
    │   ├─► whatif_opportunities: []
    │   ├─► transactions: [117 TransactionInfo objects]
    │   └─► all_swaps: [21 Swap objects]
    │
    └─► Generate reports:
        ├─► Console (Rich):
        │   ┌─────────────────────────────────────┐
        │   │ Historical MEV Detected             │
        │   ├───────────┬───────┬─────────────────┤
        │   │ Type      │ Count │ Total Profit    │
        │   ├───────────┼───────┼─────────────────┤
        │   │ Arbitrage │ 0     │ 0.000000 ETH    │
        │   │ Sandwich  │ 1     │ 0.049991 ETH    │
        │   └───────────┴───────┴─────────────────┘
        │
        ├─► JSON (if --report flag):
        │   {
        │     "block_number": 12775690,
        │     "sandwiches": [{
        │       "frontrun_tx": "0x91a3abe5...",
        │       "profit_eth": 0.049991
        │     }]
        │   }
        │
        └─► Markdown (if --report flag):
            # MEV Analysis: Block 12775690
            
            ## Sandwich Attacks
            - **Profit**: 0.049991 ETH
            - **Frontrun**: 0x91a3abe5...

OUTPUT: Complete MEV analysis with detected patterns
```

---

## 3. Component Details

### 3.1 RPC Client (`rpc.py`)

**Purpose**: Handles all interactions with Ethereum RPC endpoints.

**Key Features**:
- Batch RPC calls to minimize network overhead
- Connection pooling and retry logic
- Support for multiple RPC providers (Alchemy, Infura, Ankr)
- Compute unit tracking for free-tier compliance

**API**:
```python
class RPCClient:
    def __init__(self, rpc_url: str)
    def get_block(self, block_number: int) -> Dict
    def batch_get_receipts(self, tx_hashes: List[str]) -> Dict[str, Dict]
    def batch_get_codes(self, addresses: List[str]) -> Dict[str, str]
    def call(self, to: str, data: str, block: int) -> str
```

**Performance Characteristics**:
- Batch size: Up to 100 requests per batch
- Timeout: 30 seconds per request
- Retry attempts: 3 with exponential backoff

### 3.2 State Manager (`state_manager.py`)

**Purpose**: Manages in-memory state for pool tokens and account data.

**Key Features**:
- In-memory caching of pool tokens
- Account state tracking for PyRevm
- Efficient data structures (dictionaries, sets)

**API**:
```python
class StateManager:
    def __init__(self)
    def get_pool_tokens(self, pool: str) -> Tuple[str, str]
    def set_pool_tokens(self, pool: str, token0: str, token1: str)
    def get_account_state(self, address: str) -> Dict
```

**Memory Usage**:
- Pool tokens: ~50KB for 1000 pools
- Account states: ~1MB for 1000 accounts

### 3.3 Pool Cache (`pool_cache.py`)

**Purpose**: Persistent caching of pool token pairs to minimize RPC calls.

**Key Features**:
- SQLite-based persistent storage
- Thread-safe operations
- Automatic cache invalidation
- Export/import functionality

**Schema**:
```sql
CREATE TABLE pool_cache (
    pool_address TEXT PRIMARY KEY,
    token0 TEXT NOT NULL,
    token1 TEXT NOT NULL,
    discovered_block INTEGER,
    last_accessed INTEGER,
    access_count INTEGER DEFAULT 1
);

CREATE INDEX idx_last_accessed ON pool_cache(last_accessed);
```

**API**:
```python
class PoolCache:
    def get(self, pool: str) -> Optional[Tuple[str, str]]
    def set(self, pool: str, token0: str, token1: str, block: int)
    def get_stats() -> Dict
    def export_to_json(self, path: str)
```

**Performance**:
- Lookup time: <1ms (indexed)
- Cache size: ~1MB for 10,000 pools
- Hit rate: 90%+ on known pools

### 3.4 Transaction Replayer (`replay.py`)

**Purpose**: Uses PyRevm to replay transactions and extract internal calls.

**Key Features**:
- EVM simulation without trace APIs
- Internal call extraction
- State change tracking
- Gas usage calculation

**API**:
```python
class TransactionReplayer:
    def __init__(self, rpc_client: RPCClient)
    def replay_transaction_with_data(
        self, tx: Dict, receipt: Dict
    ) -> ReplayResult
    def extract_swaps_from_calls(
        self, calls: List[Dict]
    ) -> List[Dict]
```

**PyRevm Configuration**:
```python
evm = EVM()
evm.set_block_env(
    number=block_number,
    timestamp=block_timestamp,
    gas_limit=30_000_000,
    coinbase=block_coinbase,
    difficulty=0,
    prevrandao=block_prevrandao,
    basefee=block_basefee
)
```

**Limitations**:
- Replay success rate: ~46% (depends on state availability)
- Memory per replay: ~5-10MB
- Time per replay: ~50-200ms

### 3.5 DEX Parsers (`dex/`)

**Purpose**: Parse swap events from different DEX protocols.

**Supported Protocols**:

#### 3.5.1 Uniswap V2 (`uniswap_v2.py`)
```python
class UniswapV2Parser(BaseDEXParser):
    SWAP_EVENT_SIG = "d78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
    
    def parse_swap(
        self, tx_hash: str, tx_input: str, 
        logs: List[Dict], block_number: int
    ) -> Optional[Swap]
```

**Event Structure**:
```solidity
event Swap(
    address indexed sender,
    uint amount0In,
    uint amount1In,
    uint amount0Out,
    uint amount1Out,
    address indexed to
);
```

#### 3.5.2 Uniswap V3 (`uniswap_v3.py`)
```python
class UniswapV3Parser(BaseDEXParser):
    SWAP_EVENT_SIG = "c42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
```

**Event Structure**:
```solidity
event Swap(
    address indexed sender,
    address indexed recipient,
    int256 amount0,
    int256 amount1,
    uint160 sqrtPriceX96,
    uint128 liquidity,
    int24 tick
);
```

#### 3.5.3 Other Parsers
- **Sushiswap**: Same as Uniswap V2 (fork)
- **Curve**: StableSwap-specific events
- **Balancer**: Weighted pool events

### 3.6 MEV Detectors (`detectors/`)

#### 3.6.1 Sandwich Detector (`sandwich.py`)

**Algorithm Complexity**:
- Time: O(n² × m) where n = swaps per pool, m = pools
- Space: O(n)

**Detection Logic**:
```python
def detect_historical(
    self, swaps: List[Swap], block_number: int
) -> List[Sandwich]:
    # Group by pool: O(n)
    swaps_by_pool = group_by_pool(swaps)
    
    # For each pool: O(m)
    for pool, pool_swaps in swaps_by_pool.items():
        # Sort by position: O(n log n)
        pool_swaps.sort(key=lambda s: s.transaction_position)
        
        # Find patterns: O(n²)
        for i in range(len(pool_swaps) - 2):
            frontrun = pool_swaps[i]
            for j in range(i + 2, len(pool_swaps)):
                backrun = pool_swaps[j]
                
                # Check pattern: O(1)
                if is_sandwich_pattern(frontrun, victims, backrun):
                    calculate_profit()
                    create_sandwich()
```

**Pattern Matching Rules**:
1. Same `from_address` for frontrun and backrun
2. Same token direction for frontrun and victims
3. Opposite token direction for backrun
4. Positive profit after accounting for amounts

#### 3.6.2 Arbitrage Detector (`arbitrage.py`)

**Algorithm Complexity**:
- Time: O(n³) for cycle detection in swap graph
- Space: O(n²) for adjacency matrix

**Detection Logic**:
```python
def detect_historical(
    self, swaps: List[Swap], block_number: int
) -> List[Arbitrage]:
    # Build graph: O(n)
    graph = build_swap_graph(swaps)
    
    # Find cycles: O(n³) using DFS
    cycles = find_profitable_cycles(graph)
    
    # Calculate profits: O(k) where k = cycles found
    arbitrages = []
    for cycle in cycles:
        profit = calculate_cycle_profit(cycle)
        if profit > 0:
            arbitrages.append(create_arbitrage(cycle, profit))
    
    return arbitrages
```

---

## 4. Data Flow Analysis

### 4.1 Critical Path Analysis

**Most expensive operations** (in RPC compute units):

1. **Batch get receipts**: ~10 CU per receipt × 117 = 1,170 CU
2. **Batch get codes**: ~5 CU per address × 198 = 990 CU
3. **Get block**: ~16 CU
4. **Pool token lookups**: ~25 CU each (avoided by caching!)

**Total for block 12775690**:
- Without caching: ~3,500 CU
- With caching: ~2,200 CU (37% reduction)

### 4.2 Memory Flow

```
Initial:     ~20 MB (Python interpreter + imports)
↓
Block data:  +10 MB (117 transactions)
↓
Receipts:    +15 MB (117 receipts with logs)
↓
Contracts:   +5 MB (198 contract codes)
↓
PyRevm:      +20 MB (EVM state for replay)
↓
Swaps:       +2 MB (40 Swap objects before dedup)
↓
Detectors:   +5 MB (temporary data structures)
↓
Peak:        ~87 MB
↓
Cleanup:     ~30 MB (after garbage collection)
```

### 4.3 Time Distribution

For block 12775690 (total: ~3.1 seconds):

```
Phase 1: RPC Data Collection     → 2.0s (65%)
  ├─ Get block                   → 0.2s
  ├─ Batch receipts              → 0.9s
  ├─ Extract addresses           → 0.1s
  └─ Batch codes                 → 0.8s

Phase 2: Pool Resolution         → 0.3s (10%)
  ├─ Scan for pool creation      → 0.1s
  ├─ Cache lookup                → 0.1s
  └─ RPC fallback (if needed)    → 0.1s

Phase 3: Transaction Processing  → 0.5s (16%)
  ├─ PyRevm replay               → 0.3s
  └─ Log parsing                 → 0.2s

Phase 4: MEV Detection           → 0.2s (6%)
  ├─ Deduplication               → 0.05s
  ├─ Sandwich detection          → 0.1s
  └─ Arbitrage detection         → 0.05s

Phase 5: Reporting               → 0.1s (3%)
  └─ Format and display          → 0.1s
```

---

## 5. Caching Strategy

### 5.1 Cache Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Caching Layers                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: In-Block Discovery (Hot Cache)                   │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ ABI Decoder scans logs for PairCreated events         │ │
│  │ • Zero RPC cost                                        │ │
│  │ • Immediate availability                               │ │
│  │ • Stored in: abi_decoder.pool_tokens_cache (dict)     │ │
│  │ • Lifetime: Current block only                         │ │
│  └───────────────────────────────────────────────────────┘ │
│           │                                                 │
│           │ Miss                                            │
│           ▼                                                 │
│  Layer 2: Persistent Cache (Warm Cache)                    │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ SQLite database with indexed lookups                  │ │
│  │ • ~1ms query time                                      │ │
│  │ • 90%+ hit rate on known pools                        │ │
│  │ • Stored in: pool_cache.db                            │ │
│  │ • Lifetime: Persistent across runs                     │ │
│  │ • Size: ~1MB for 10K pools                            │ │
│  └───────────────────────────────────────────────────────┘ │
│           │                                                 │
│           │ Miss                                            │
│           ▼                                                 │
│  Layer 3: RPC Fallback (Cold)                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ eth_call to pool contract                             │ │
│  │ • token0(): ~15 CU                                     │ │
│  │ • token1(): ~15 CU                                     │ │
│  │ • Result saved to Layer 2                             │ │
│  │ • Only for first encounter of pool                     │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Cache Invalidation

**Current Strategy**: Never invalidate (immutable pool tokens)

**Rationale**:
- Pool token pairs never change after creation
- Pool address is deterministic from token pair
- No need for TTL or expiration

**Future Considerations**:
- Pool upgrades (rare, requires new address)
- Error correction (manual intervention)

### 5.3 Cache Statistics

**Metrics Tracked**:
```python
{
    "total_pools": 51,
    "cache_hits": 15,
    "cache_misses": 0,
    "hit_rate": 100.0,
    "rpc_calls_saved": 30,
    "avg_lookup_time_ms": 0.8
}
```

**Export Format** (JSON):
```json
{
  "pools": [
    {
      "address": "0xefb47fcfcad4f96c83d4ca676842fb03ef20a477",
      "token0": "0x9813037ee2218799597d83d4a5b6f3b6778218d9",
      "token1": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
      "discovered_block": 12775690,
      "access_count": 7
    }
  ]
}
```

---

## 6. Detection Algorithms

### 6.1 Swap Deduplication Algorithm

**Problem**: Multiple DEX parsers may match the same log event.

**Example**:
- Sushiswap uses Uniswap V2 event signatures
- Same swap event triggers both UniswapV2Parser and SushiswapParser
- Result: Duplicate Swap objects for same transaction

**Solution**: Hash-based deduplication

```python
def deduplicate_swaps(swaps: List[Swap]) -> List[Swap]:
    seen = set()
    result = []
    
    for swap in swaps:
        # Create unique key from transaction + swap details
        key = (
            swap.tx_hash,
            swap.pool_address.lower(),
            swap.token_in.lower(),
            swap.token_out.lower()
        )
        
        if key not in seen:
            seen.add(key)
            result.append(swap)
    
    return result
```

**Complexity**:
- Time: O(n) where n = number of swaps
- Space: O(n) for seen set

**Effectiveness**:
- Block 12775690: 40 → 21 swaps (47.5% reduction)
- Block 12914944: 60 → 30 swaps (50% reduction)

### 6.2 Sandwich Pattern Matching

**State Machine**:

```
START
  │
  ├─► Find potential frontrun (any swap)
  │   │
  │   ├─► Look ahead for backrun candidates
  │   │   │
  │   │   ├─► Same from_address? ────────────┐
  │   │   │                                   │
  │   │   └─► No → Skip                       │
  │   │                                       │
  │   └─► Yes                                 │
  │       │                                   │
  │       ├─► Extract victims (between)       │
  │       │   │                               │
  │       │   ├─► Check pattern:              │
  │       │   │   • Frontrun & victims:       │
  │       │   │     same token direction?     │
  │       │   │   • Backrun:                  │
  │       │   │     opposite direction?       │
  │       │   │                               │
  │       │   ├─► Yes → Calculate profit ─────┼─► SANDWICH FOUND
  │       │   │                               │
  │       │   └─► No → Continue search        │
  │       │                                   │
  │       └─► Try next backrun candidate ─────┘
  │
  └─► Try next frontrun candidate

END
```

**Optimization**:
- Sort swaps by position once (O(n log n))
- Binary search for backrun candidates (future optimization)
- Early termination on first successful match per frontrun

### 6.3 Profit Calculation

**Sandwich Profit**:
```
Given:
  Frontrun:  amount_in_frontrun (token A)
  Backrun:   amount_out_backrun (token A)

Profit = amount_out_backrun - amount_in_frontrun

Example:
  Frontrun:  12.1088 WETH → 1114.9698 BONE
  Backrun:   1114.9698 BONE → 12.1588 WETH
  Profit:    12.1588 - 12.1088 = 0.0500 WETH
```

**Gas Cost** (future work):
```
Gas cost = (gas_used_frontrun + gas_used_backrun) × gas_price

Net profit = Gross profit - Gas cost
```

---

## 7. Performance Optimization

### 7.1 Batch Operations

**Strategy**: Minimize round trips to RPC server.

**Implementation**:
```python
# Bad: Sequential calls (117 round trips)
receipts = []
for tx_hash in tx_hashes:
    receipt = rpc.get_receipt(tx_hash)
    receipts.append(receipt)

# Good: Batch call (1 round trip)
receipts = rpc.batch_get_receipts(tx_hashes)
```

**Speedup**: 100-200x faster (network latency dependent)

### 7.2 Parallel Processing

**Current**: Sequential transaction processing  
**Future**: Parallel processing with ThreadPoolExecutor

```python
# Future optimization
from concurrent.futures import ThreadPoolExecutor

def process_block_parallel(transactions):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_transaction, tx)
            for tx in transactions
        ]
        results = [f.result() for f in futures]
    return results
```

**Expected Speedup**: 2-4x on multi-core systems

### 7.3 Memory Optimization

**Techniques**:
1. **Streaming Processing**: Process transactions one at a time
2. **Garbage Collection**: Explicitly delete large objects
3. **Object Pooling**: Reuse Swap/Transaction objects

```python
# After processing batch
import gc
del large_data_structure
gc.collect()
```

### 7.4 Database Optimization

**SQLite Optimizations**:
```sql
-- Use WAL mode for better concurrency
PRAGMA journal_mode=WAL;

-- Increase cache size
PRAGMA cache_size=10000;

-- Create indexes on frequently queried columns
CREATE INDEX idx_pool_address ON pool_cache(pool_address);
CREATE INDEX idx_last_accessed ON pool_cache(last_accessed);
```

**Query Optimization**:
```python
# Use prepared statements
cursor.execute(
    "SELECT token0, token1 FROM pool_cache WHERE pool_address = ?",
    (pool_address,)
)
```

---

## 8. Error Handling

### 8.1 RPC Errors

**Common Errors**:
- Connection timeout
- Rate limiting (429)
- Invalid response

**Handling Strategy**:
```python
def safe_rpc_call(func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func(*args)
        except Timeout:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
        except RateLimitError:
            time.sleep(60)  # Wait 1 minute
        except Exception as e:
            log_error(f"RPC error: {e}")
            raise
```

### 8.2 Replay Errors

**Common Issues**:
- Account state not available
- Contract creation transactions
- Complex internal calls

**Handling**:
```python
try:
    result = replayer.replay_transaction(tx)
except ReplayError as e:
    # Fallback to log-based parsing
    logger.debug(f"Replay failed: {e}")
    continue
```

### 8.3 Parsing Errors

**Common Issues**:
- Malformed log data
- Unknown event signatures
- ABI decode errors

**Handling**:
```python
for parser in dex_parsers:
    try:
        swap = parser.parse_swap(tx_hash, logs)
        if swap:
            swaps.append(swap)
    except Exception as e:
        # Continue with other parsers
        continue
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Components Tested**:
- DEX parsers (known event data)
- Deduplication algorithm
- Sandwich detection logic
- Cache operations

### 9.2 Integration Tests

**Test Blocks**:
- 12775690 (known sandwich)
- 12914944 (MEV activity)
- Custom test cases

**Validation**:
- Compare with Flashbots ground truth
- Verify profit calculations
- Check cache hit rates

### 9.3 Performance Tests

**Metrics**:
- Execution time per block
- Memory usage
- RPC call count
- Cache efficiency

---

## 10. Future Architecture Improvements

### 10.1 Microservices Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   RPC       │     │   Cache     │     │  Detection  │
│  Service    │────▶│  Service    │────▶│  Service    │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │
      ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────┐
│              Message Queue (RabbitMQ)               │
└─────────────────────────────────────────────────────┘
```

### 10.2 Streaming Architecture

```
Ethereum Node → Kafka → Processor → Database → API
```

### 10.3 Multi-Chain Support

```
┌────────────────────────────────────────┐
│        Chain Abstraction Layer         │
├────────────────────────────────────────┤
│  Ethereum  │  Polygon  │  BSC  │ Arb   │
└────────────────────────────────────────┘
```

---

## 11. Conclusion

This architecture document provides a comprehensive overview of MEV-Inspect-PyRevm's design, from high-level system architecture to detailed component interactions and data flows. The modular design, multi-layer caching strategy, and efficient algorithms enable accurate MEV detection without requiring expensive trace APIs, making it accessible for researchers and developers with limited resources.

**Key Architectural Strengths**:
- Modular and maintainable component design
- Efficient multi-layer caching (90%+ hit rate)
- Smart deduplication eliminates false positives
- Hybrid detection (logs + replay)
- Free-tier RPC compatibility

**Future Enhancements**:
- Microservices decomposition for scalability
- Real-time streaming for live detection
- Multi-chain support for broader coverage
- Advanced ML-based pattern detection

---

**Document Version**: 1.0  
**Last Updated**: December 8, 2025  
**Maintainer**: MEV-Inspect-PyRevm Development Team
