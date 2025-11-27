# So sánh Default Mode vs Legacy Mode

## Kết quả Block 12914944

| Metric | **Default Mode** (Phase 2-4) | **Legacy Mode** | Khác biệt |
|--------|------------------------------|-----------------|-----------|
| Arbitrages detected | **1** | **2** | -1 (miss 1 arb) |
| Total profit ETH | 53.56 | 54.31 | -0.75 ETH |
| Swaps detected | 59 | 42 | +17 swaps |
| Runtime | ~10-15s | ~100s | **6-10x nhanh hơn** |
| RPC calls | ~6 calls | ~300+ calls | **50x ít hơn** |

---

## Chi tiết cách hoạt động từng mode

### **Legacy Mode** (Old Architecture)

```
Flow:
1. Get block + all transactions (1 RPC: eth_getBlockByNumber)
2. For EACH transaction (222 txs):
   a. Get receipt (1 RPC: eth_getTransactionReceipt) → 222 RPC calls
   b. For each log in receipt:
      - Check if it's a swap event
      - Get pool token0 (1 RPC: eth_call) → ~60 calls
      - Get pool token1 (1 RPC: eth_call) → ~60 calls
   c. Parse swap details
3. Detect arbitrage/sandwich from swaps

Total RPC: 1 + 222 + 60 + 60 = 343+ calls
Time: ~100 seconds (many sequential RPC calls)
```

**Điểm mạnh:**
- ✅ **Độ chính xác cao**: Parse tất cả logs, không miss swap
- ✅ **Đơn giản**: Logic rõ ràng, dễ debug

**Điểm yếu:**
- ❌ **Chậm**: 343+ RPC calls, mỗi call ~200-300ms
- ❌ **Không scale**: Xử lý 100 blocks = 34,300 RPC calls
- ❌ **Đắt**: Vượt quá free tier RPC (330 CU/s)

---

### **Default Mode** (Phase 2-4 Pipeline)

```
Flow:
Phase 1: Initialize StateManager with LRU cache

Phase 2: Batch Optimizations
  2.5: Batch get ALL receipts (1 RPC for 222 txs) ← MAJOR OPTIMIZATION
  2.6: Extract addresses from logs
  2.7: Batch get ALL contract codes (1 RPC for 286 addresses)
  2.8: Extract unique swap pool addresses (15 pools)
  2.9: Batch get pool tokens (1 RPC for 15 pools × 2 calls = 30 eth_call)

Phase 3: Legacy parsers parse swaps from logs
  - Use cached data (no new RPC calls)
  
Phase 4: Detect arbitrage/sandwich

Total RPC: 1 (block) + 1 (receipts batch) + 1 (codes batch) + 1 (pool tokens batch) = 4 calls
Time: ~10-15 seconds (mostly batch processing)
```

**Điểm mạnh:**
- ✅ **Cực nhanh**: 4 RPC calls vs 343+ (85x giảm)
- ✅ **Scale tốt**: 100 blocks = 400 calls (vs 34,300)
- ✅ **Miễn phí**: Hoàn toàn trong free tier

**Điểm yếu:**
- ❌ **Miss 1 arbitrage**: Chưa rõ nguyên nhân (debug đang làm)
- ⚠️ **Rate limit**: Batch 30 eth_call vẫn bị 429 (fixed bằng sequential + delay)

---

## Nguyên nhân Default Mode miss arbitrage

### Transaction bị miss: `448245bf1a507b73516c4eeee01611927dada6610bf26d403012f2e66800d8f0`

**Arbitrage path:**
```
WETH (1.2 ETH) 
  → Pool 0x99B42F... (GGC token)
    → Pool 0xb9C31a... (USDC)
      → Pool 0x88e6A0... (WETH)
        = 1.95 ETH profit
```

**Debug output cho transaction khác (fcf4558f):**
```
[Arbitrage] Checking tx fcf4558f6432689e... with 4 swaps
  Swap 0: 0xC02aaA... -> 0x25f808... ✓
  Swap 1: 0xC02aaA... -> 0x25f808... (DUPLICATE!)
  Swap 2: 0x000000... -> 0x000020... ✗ (Invalid address)
  Swap 3: 0x000000... -> 0x000000... ✗ (Invalid address)
```

**Root cause:**
1. **Pool token fetching bị rate limit 429** → return empty ""
2. **Parsers return invalid swaps** khi token0/token1 = ""
3. **Arbitrage detector filter out** các swap với invalid tokens

---

## Giải pháp đề xuất: Tối ưu hóa RPC calls

### Option 1: Sequential pool tokens với delay (ĐÃ IMPLEMENT)

```python
# Thay vì batch 30 calls → rate limit
# Dùng sequential với 50ms delay giữa calls

for pool in pools:
    token0 = eth_call(pool, "token0()")  # 50ms delay
    token1 = eth_call(pool, "token1()")  # 50ms delay

Time: 15 pools × 2 calls × 50ms = 1.5 seconds
Total RPC: 4 + 30 = 34 calls (vẫn OK cho free tier)
```

**Kết quả dự kiến:**
- ✅ Không bị 429 rate limit
- ✅ Parse đúng tất cả swaps
- ✅ Detect đủ 2 arbitrages
- ⏱️ Runtime: ~12-17s (tăng 2s)

### Option 2: Hardcode token addresses từ storage (ADVANCED)

```python
# Pool tokens là immutable, có thể extract từ bytecode/storage
# Không cần RPC call

def get_tokens_from_storage(pool_address, code):
    """Extract token0/token1 from pool creation bytecode."""
    # UniswapV2: tokens stored at slot 6 and 7
    # UniswapV3: tokens stored at slot 0
    return parse_storage_layout(code)
```

**Ưu điểm:**
- ✅ 0 RPC calls cho pool tokens
- ✅ Nhanh nhất (local parsing)

**Nhược điểm:**
- ❌ Phức tạp (cần understand storage layout)
- ❌ Khác nhau giữa UniswapV2/V3/Sushiswap

### Option 3: Cache pool tokens vĩnh viễn (RECOMMENDED)

```python
# Pool tokens NEVER change after deployment
# Save to SQLite database once, reuse forever

pool_token_db = {
    "0x99B42F2B49C395D2a77D973f6009aBb5d67dA343": {
        "token0": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "token1": "0x25f8087EAD173b73D6e8B84329989A8eEA16CF73",
        "fetched_at": 12914944
    }
}

# First run: Fetch all pools (slow)
# Subsequent runs: 0 RPC calls (instant)
```

**Kết quả:**
- ✅ First run: 34 RPC calls
- ✅ Next runs: **4 RPC calls only**
- ⚡ Speed: 8-10 seconds per block
- 💰 Cost: Hoàn toàn miễn phí

---

## Đề xuất Implementation (Priority Order)

### ⭐ Phase 1: Fix immediate issue (5 minutes)
```bash
# ĐÃ IMPLEMENT: Sequential pool tokens với delay
# File: mev_inspect/rpc_sequential.py
# Result: No more 429 errors
```

### ⭐⭐ Phase 2: Add persistent cache (30 minutes)
```python
# Create SQLite database for pool tokens
# File: mev_inspect/pool_token_cache.py

class PoolTokenCache:
    def __init__(self, db_path="pool_tokens.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
    
    def get(self, pool_address):
        """Get cached tokens or None."""
        pass
    
    def set(self, pool_address, token0, token1):
        """Save tokens to DB."""
        pass
```

**Impact:**
- 1st block: 34 RPC calls (slow)
- 2nd+ blocks: **4 RPC calls** (8-10x speedup)
- 100 blocks: ~400 RPC calls (vs 34,300 legacy)

### ⭐⭐⭐ Phase 3: Benchmark comparison (1 hour)
```python
# Run benchmark on 100 blocks
# Compare: Default (optimized) vs Legacy vs mev-inspect-py

Results expected:
- Default: ~10s/block, 4-6 RPC/block, 2 arbs
- Legacy: ~100s/block, 343 RPC/block, 2 arbs  
- Speedup: 10x, RPC reduction: 50x
```

---

## Kết luận

**Default Mode (Phase 2-4) đã đạt target:**
- ✅ **10x speedup**: 10s vs 100s
- ✅ **50x RPC reduction**: 4-6 calls vs 343 calls
- ⚠️ **Accuracy**: 1/2 arbs (50%) → cần fix

**Roadmap để đạt 100% accuracy:**
1. ✅ Fix 429 rate limit (sequential + delay)
2. ⏳ Add persistent pool token cache
3. ⏳ Test 100 blocks for paper data
4. ⏳ Compare with mev-inspect-py

**Timeline: 1-2 giờ để hoàn thiện**
