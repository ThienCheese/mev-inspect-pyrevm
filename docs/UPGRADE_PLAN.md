# MEV Inspector PyRevm Upgrade Plan
## From RPC-Only to 80% Flashbots-Level Accuracy

> **Goal**: Implement real PyRevm integration to achieve 80%+ accuracy compared to mev-inspect-py while maintaining ease of setup
> 
> **Target Date**: 4-6 weeks implementation
> 
> **Status**: Planning Phase

---

## 🎯 Project Goals

### Primary Objectives

1. **Achieve 80%+ Detection Accuracy**
   - Match mev-inspect-py on standard arbitrages
   - Match mev-inspect-py on sandwich attacks
   - Detect swaps without events (internal calls)

2. **Maintain Simplicity**
   - No Kubernetes/Docker required
   - No PostgreSQL database needed
   - Works with standard RPC (Alchemy free tier)
   - Simple `pip install` setup

3. **Performance Improvements**
   - 10x faster than pure RPC approach
   - Batch processing capabilities
   - State caching for efficiency

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Arbitrage Detection Rate | 80%+ | Compare with known MEV txs |
| Sandwich Detection Rate | 80%+ | Compare with Flashbots data |
| False Positive Rate | <5% | Manual validation |
| Processing Speed | 10x faster | Benchmark vs current |
| Setup Time | <5 minutes | User testing |

---

## 🏗️ Architecture Design

### Current Architecture (RPC-Only)

```
User → CLI → Inspector → RPC Client → Ethereum Node
                ↓
            Event Parser → Swap Detection → MEV Detection
```

**Limitations**:
- Can't see internal calls
- Miss swaps without events
- Slow for batch processing
- No state caching

### New Architecture (Hybrid PyRevm + RPC)

```
User → CLI → Inspector → Data Layer (RPC) → PyRevm Simulator
                ↓                              ↓
            State Manager ← Cache ← [State Loading]
                ↓                              ↓
            Enhanced Parser ← [Transaction Replay]
                ↓                              ↓
            Multi-Method Swap Detection        ↓
                ↓                              ↓
            MEV Detection ← [Profit Simulation]
```

**Advantages**:
- ✅ See internal calls via transaction replay
- ✅ Detect swaps without events
- ✅ Fast batch processing with state cache
- ✅ Accurate gas and profit calculations
- ✅ Fallback to RPC if PyRevm unavailable

---

## 📦 Component Breakdown

### 1. State Manager (`mev_inspect/state_manager.py`) - NEW

**Purpose**: Manage EVM state efficiently with caching

```python
class StateManager:
    """Manage EVM state with intelligent caching"""
    
    def __init__(self, rpc_client, block_number: int):
        self.rpc = rpc_client
        self.block = block_number
        self.account_cache = LRUCache(maxsize=10000)
        self.storage_cache = LRUCache(maxsize=50000)
        self.code_cache = LRUCache(maxsize=1000)
    
    def get_account(self, address: str) -> Account:
        """Get account with caching"""
        
    def get_storage(self, address: str, slot: int) -> bytes:
        """Get storage slot with caching"""
        
    def get_code(self, address: str) -> bytes:
        """Get contract code with caching"""
        
    def preload_addresses(self, addresses: List[str]):
        """Batch preload accounts for efficiency"""
```

**Key Features**:
- LRU caching to manage memory
- Batch loading for performance
- Lazy loading only what's needed
- Statistics tracking (cache hits/misses)

### 2. PyRevm Simulator (`mev_inspect/simulator.py`) - UPGRADE

**Current**: Stub implementation with RPC fallback
**New**: Full PyRevm integration with proper state management

```python
class StateSimulator:
    """Enhanced simulator with real PyRevm support"""
    
    def __init__(self, rpc_client, block_number: int):
        self.rpc = rpc_client
        self.block_number = block_number
        self.state_manager = StateManager(rpc_client, block_number)
        self.evm = self._init_evm()
    
    def _init_evm(self) -> Evm:
        """Initialize PyRevm with proper block environment"""
        evm = Evm()
        block = self.rpc.get_block(self.block_number)
        
        # Set block environment
        evm.block_env = BlockEnv(
            number=block["number"],
            coinbase=block["miner"],
            timestamp=block["timestamp"],
            gas_limit=block["gasLimit"],
            base_fee=block.get("baseFeePerGas", 0),
            prevrandao=block.get("mixHash", b"\x00" * 32),
        )
        
        return evm
    
    def replay_transaction(self, tx_hash: str) -> ReplayResult:
        """Replay transaction and capture all state changes"""
        # This is the KEY feature that enables trace-like analysis
        
    def simulate_swap(self, pool: str, amount_in: int) -> int:
        """Simulate swap with accurate state"""
```

**Key Enhancements**:
- Proper EVM initialization
- Transaction replay capability
- State change tracking
- Internal call extraction

### 3. Transaction Replay (`mev_inspect/replay.py`) - NEW

**Purpose**: Replay transactions to extract trace-like data

```python
class TransactionReplayer:
    """Replay transactions to extract internal calls and state changes"""
    
    def replay(self, tx_hash: str) -> ReplayResult:
        """
        Replay transaction and return:
        - All internal calls (call, delegatecall, staticcall)
        - State changes (balance, storage, code)
        - Events emitted
        - Gas used per call
        """
        
    def extract_internal_swaps(self, replay_result: ReplayResult) -> List[Swap]:
        """
        Extract swaps from internal calls
        - Match function signatures (swap, swapExact, etc.)
        - Parse call data for amounts
        - Identify token addresses
        """
```

**What This Enables**:
- Detect swaps without events (like mev-inspect-py)
- See multi-hop paths clearly
- Understand complex MEV strategies

### 4. Enhanced Swap Detector (`mev_inspect/detectors/swap_detector.py`) - NEW

**Purpose**: Combine multiple detection methods

```python
class EnhancedSwapDetector:
    """Multi-method swap detection"""
    
    def detect_swaps(self, tx: Transaction) -> List[Swap]:
        """Use multiple methods to find ALL swaps"""
        
        swaps = []
        
        # Method 1: Event-based (fast, works for standard DEXs)
        swaps.extend(self._detect_from_events(tx))
        
        # Method 2: Internal calls (catches event-less swaps)
        swaps.extend(self._detect_from_internal_calls(tx))
        
        # Method 3: State changes (last resort, most accurate)
        swaps.extend(self._detect_from_state_changes(tx))
        
        # Deduplicate and validate
        return self._deduplicate_swaps(swaps)
```

**Detection Rate Target**:
- Event-based: 60% of swaps (fast)
- Internal calls: +25% of swaps (PyRevm replay)
- State changes: +15% of swaps (comprehensive)
- **Total: 100% coverage** (vs 60% current)

### 5. Accurate Profit Calculator (`mev_inspect/profit.py`) - NEW

**Purpose**: Calculate exact MEV profits

```python
class ProfitCalculator:
    """Calculate accurate MEV profits using PyRevm simulation"""
    
    def calculate_arbitrage_profit(self, arb: Arbitrage) -> ProfitResult:
        """
        Simulate the arbitrage path step-by-step:
        1. Get initial balance
        2. Simulate each swap with exact state
        3. Calculate final balance
        4. Subtract exact gas costs
        """
        
    def calculate_sandwich_profit(self, sandwich: Sandwich) -> ProfitResult:
        """
        Simulate sandwich attack:
        1. Frontrun swap → capture state
        2. Victim swap → measure price impact
        3. Backrun swap → calculate profit
        4. Subtract gas costs for all 3 txs
        """
```

**Accuracy Improvements**:
- Exact gas costs (not estimates)
- Precise token amounts (no approximations)
- Account for slippage accurately
- Include all fees (protocol, gas, etc.)

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal**: Set up PyRevm infrastructure properly

- [ ] Add pyrevm to dependencies
- [ ] Create StateManager class
- [ ] Implement account/storage/code caching
- [ ] Test PyRevm initialization and basic operations
- [ ] Benchmark cache performance

**Deliverable**: Working StateManager with >90% cache hit rate

### Phase 2: Transaction Replay (Week 2-3)

**Goal**: Implement transaction replay to extract internal calls

- [ ] Create TransactionReplayer class
- [ ] Implement transaction execution in PyRevm
- [ ] Extract internal calls (call, delegatecall, staticcall)
- [ ] Parse function signatures and parameters
- [ ] Test with known MEV transactions

**Deliverable**: Can extract internal calls from any transaction

### Phase 3: Enhanced Detection (Week 3-4)

**Goal**: Improve swap detection rate from 60% to 95%+

- [ ] Create EnhancedSwapDetector
- [ ] Implement internal call-based detection
- [ ] Add state change-based detection
- [ ] Validate against known swaps
- [ ] Measure detection rate improvement

**Deliverable**: 95%+ swap detection rate

### Phase 4: Accurate Calculations (Week 4-5)

**Goal**: Achieve 80%+ profit calculation accuracy

- [ ] Create ProfitCalculator
- [ ] Implement step-by-step simulation
- [ ] Calculate exact gas costs
- [ ] Compare with known MEV profits
- [ ] Tune parameters

**Deliverable**: 80%+ match on profit calculations

### Phase 5: Testing & Validation (Week 5-6)

**Goal**: Validate against mev-inspect-py dataset

- [ ] Create test suite with known MEV blocks
- [ ] Compare detection results
- [ ] Measure accuracy metrics
- [ ] Fix discrepancies
- [ ] Document performance

**Deliverable**: Validation report showing 80%+ accuracy

### Phase 6: Documentation & Polish (Week 6)

**Goal**: Make tool production-ready

- [ ] Update all documentation
- [ ] Create user guides
- [ ] Add examples and tutorials
- [ ] Performance benchmarks
- [ ] Blog post/paper

**Deliverable**: Complete, documented, production-ready tool

---

## 📊 Technical Specifications

### PyRevm Integration Details

#### State Loading Strategy

```python
# Smart state loading - only load what's needed
def load_transaction_state(tx: Transaction):
    """Load minimal state needed for transaction"""
    
    addresses_to_load = set()
    
    # 1. Transaction participants
    addresses_to_load.add(tx.from_address)
    addresses_to_load.add(tx.to_address)
    
    # 2. Contracts called (from logs)
    for log in tx.logs:
        addresses_to_load.add(log.address)
    
    # 3. Token contracts (from events)
    for event in parse_events(tx.logs):
        if event.type == "Transfer":
            addresses_to_load.add(event.token)
    
    # Batch load all at once
    state_manager.preload_addresses(addresses_to_load)
```

**Efficiency**: Load only ~10-50 accounts per transaction instead of entire state

#### Transaction Replay Process

```python
def replay_transaction(tx: Transaction) -> ReplayResult:
    """Replay transaction step by step"""
    
    # 1. Load state
    load_transaction_state(tx)
    
    # 2. Set up EVM
    evm = create_evm(state_manager)
    
    # 3. Execute transaction
    result = evm.transact(
        caller=tx.from_address,
        transact_to=tx.to_address,
        data=tx.input,
        value=tx.value,
        gas_limit=tx.gas_limit,
    )
    
    # 4. Extract information
    return ReplayResult(
        success=result.is_success(),
        gas_used=result.gas_used(),
        output=result.output(),
        logs=result.logs(),
        state_changes=result.state_changes(),
        internal_calls=extract_calls(result),
    )
```

### Memory Management

**Challenge**: PyRevm can use a lot of memory with full state

**Solution**: Intelligent caching with LRU eviction

```python
# Cache sizes (tunable based on available RAM)
ACCOUNT_CACHE_SIZE = 10_000   # ~10MB
STORAGE_CACHE_SIZE = 50_000   # ~50MB  
CODE_CACHE_SIZE = 1_000       # ~100MB
# Total: ~160MB memory overhead (acceptable)
```

### Performance Targets

| Operation | Current (RPC) | Target (PyRevm) | Improvement |
|-----------|--------------|-----------------|-------------|
| Single block analysis | 30s | 3s | 10x faster |
| 100 block range | 50min | 5min | 10x faster |
| Swap detection rate | 60% | 95% | 1.6x better |
| Profit accuracy | 40% | 80% | 2x better |

---

## 🎓 Key Technical Challenges

### Challenge 1: State Loading

**Problem**: Can't load entire Ethereum state (too large)

**Solution**: 
- Lazy loading - only load accounts touched by transactions
- Predictive loading - analyze transaction input to predict addresses
- Batch loading - load multiple accounts in one RPC call

### Challenge 2: Internal Call Extraction

**Problem**: PyRevm doesn't have built-in call tracer like Geth

**Solution**:
- Hook into PyRevm's execution hooks
- Track CALL, DELEGATECALL, STATICCALL opcodes
- Build call tree manually
- Parse call data to identify swaps

### Challenge 3: Swap Detection Without Events

**Problem**: Some DEXs don't emit standard events

**Solution**:
- Analyze internal calls for swap function signatures
- Look for state changes in token balances
- Match patterns: `token.transfer()` + `pool.sync()`

### Challenge 4: Gas Cost Accuracy

**Problem**: PyRevm gas costs might differ from actual execution

**Solution**:
- Validate against actual transaction receipts
- Tune gas parameters to match mainnet
- Document any discrepancies

---

## 📈 Validation Strategy

### Test Dataset

Use Flashbots MEV-Inspect dataset for validation:

```
Known MEV Blocks:
- Block 12914944: 2 arbitrages (from current result.json)
- Block 12914945-13000000: Historical MEV data
- Total: ~1000 known arbitrages, ~500 known sandwiches
```

### Validation Metrics

```python
def validate_accuracy(our_results, flashbots_results):
    """Compare our detection with Flashbots ground truth"""
    
    metrics = {
        'true_positives': 0,   # We found it, Flashbots found it
        'false_positives': 0,  # We found it, Flashbots didn't
        'false_negatives': 0,  # We missed it, Flashbots found it
        'true_negatives': 0,   # We both didn't find it
    }
    
    accuracy = (TP + TN) / (TP + TN + FP + FN)
    precision = TP / (TP + FP)
    recall = TP / (TP + FN)
    f1_score = 2 * (precision * recall) / (precision + recall)
    
    # Target: accuracy >= 80%, precision >= 85%, recall >= 75%
```

### Continuous Testing

```bash
# Run validation suite
python tests/validate_accuracy.py --blocks 12914944-12915000

# Output:
# ✅ Arbitrage Detection: 83% accuracy (target: 80%)
# ✅ Sandwich Detection: 79% accuracy (target: 80%)  
# ✅ Profit Calculation: 82% accuracy (target: 80%)
# ⚠️  Processing Speed: 8x faster (target: 10x)
```

---

## 🛠️ Developer Guide

### Setting Up Dev Environment

```bash
# Clone repo
git clone <repo-url>
cd mev-inspect-pyrevm

# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate

# Install with PyRevm
pip install -e ".[dev]"
pip install pyrevm>=0.3.0

# Run tests
pytest tests/

# Validate accuracy
python tests/validate_accuracy.py
```

### Adding New DEX Support

```python
# Example: Adding a new DEX with non-standard events

class NewDEXParser(DEXParser):
    """Parser for NewDEX protocol"""
    
    def detect_swap_from_internal_call(self, call: InternalCall) -> Optional[Swap]:
        """Detect swap from internal call signature"""
        
        # NewDEX uses: swapTokens(address,address,uint256)
        if call.function_sig == "0x12345678":
            token_in = parse_address(call.input[0:32])
            token_out = parse_address(call.input[32:64])
            amount_in = parse_uint256(call.input[64:96])
            
            # Simulate to get amount_out
            amount_out = self.simulate_swap(
                call.to_address, 
                token_in, 
                amount_in
            )
            
            return Swap(
                tx_hash=call.tx_hash,
                dex="newdex",
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
            )
```

---

## 📚 References & Resources

### PyRevm Documentation
- [PyRevm GitHub](https://github.com/bluealloy/pyrevm)
- [PyRevm Examples](https://github.com/bluealloy/pyrevm/tree/main/examples)
- [REVM Documentation](https://github.com/bluealloy/revm)

### MEV Research
- [Flashbots Research](https://writings.flashbots.net/)
- [MEV-Inspect-py Source](https://github.com/flashbots/mev-inspect-py)
- [Ethereum MEV Docs](https://ethereum.org/en/developers/docs/mev/)

### Testing Datasets
- [Flashbots MEV-Inspect Data](https://datasets.flashbots.net/)
- [MEV-Explore](https://explore.flashbots.net/)

---

## 🎯 Success Criteria Summary

| Criteria | Minimum | Target | Stretch Goal |
|----------|---------|--------|--------------|
| **Arbitrage Detection** | 75% | 80% | 90% |
| **Sandwich Detection** | 75% | 80% | 90% |
| **Profit Accuracy** | 70% | 80% | 85% |
| **False Positive Rate** | <10% | <5% | <2% |
| **Setup Time** | <10min | <5min | <2min |
| **Processing Speed** | 5x | 10x | 20x |
| **Memory Usage** | <1GB | <500MB | <250MB |

**Overall Success**: Meet 5/7 targets including the 3 detection accuracy metrics

---

## 📅 Timeline

```
Week 1-2: Foundation
├── StateManager implementation
├── PyRevm basic integration
└── Caching system

Week 2-3: Transaction Replay
├── Replay infrastructure
├── Internal call extraction
└── Function signature parsing

Week 3-4: Enhanced Detection
├── Multi-method swap detector
├── Internal call-based detection
└── State change-based detection

Week 4-5: Accurate Calculations
├── ProfitCalculator implementation
├── Step-by-step simulation
└── Gas cost accuracy

Week 5-6: Testing & Validation
├── Test suite creation
├── Accuracy measurement
├── Bug fixes & optimization
└── Documentation

Week 6: Polish & Release
├── Documentation completion
├── Examples & tutorials
├── Performance benchmarks
└── Release v1.0.0
```

---

## 🚀 Next Steps

1. **Review this plan** with team/advisor
2. **Get feedback** on technical approach
3. **Set up development environment** 
4. **Start Phase 1** - StateManager implementation
5. **Weekly progress reviews** to track accuracy improvements

---

**Questions to Answer Before Starting**:

1. ✅ Is 80% accuracy sufficient for our use case?
2. ✅ Do we have access to Flashbots dataset for validation?
3. ✅ What's our target memory budget? (500MB proposed)
4. ✅ Should we support Python 3.9 or only 3.10+?
5. ✅ Do we want to support Windows or Unix only?

---

**Prepared by**: AI Assistant  
**Date**: November 18, 2025  
**Version**: 1.0 (Initial Plan)
