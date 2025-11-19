"""StateManager: lightweight caching layer for RPC-based state access.

Provides LRU caches for account data (balance + code) and storage slots to
reduce RPC calls when replaying/simulating many transactions in a block.

This is intentionally dependency-free (no external cache libs) so it can be
installed easily.
"""
from collections import OrderedDict
from typing import Any, Dict, Iterable, Optional


class LRUCache:
    """Simple LRU cache using OrderedDict.

    get/set are O(1). When capacity is exceeded the oldest entry is evicted.
    """

    def __init__(self, maxsize: int = 1024):
        self.maxsize = int(maxsize)
        self._data: "OrderedDict[str, Any]" = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        v = self._data.get(key)
        if v is None:
            return None
        # mark as recently used
        self._data.move_to_end(key)
        return v

    def set(self, key: str, value: Any):
        if key in self._data:
            # replace and mark recent
            self._data[key] = value
            self._data.move_to_end(key)
            return
        self._data[key] = value
        if len(self._data) > self.maxsize:
            # evict oldest
            self._data.popitem(last=False)

    def clear(self):
        self._data.clear()

    def __len__(self):
        return len(self._data)


class StateManager:
    """Manage on-demand loading and caching of account / storage / code.

    The StateManager expects an RPC client implementing the small subset used
    across the project (see `mev_inspect.rpc.RPCClient`). It holds the block
    number used for all historical reads.
    """

    def __init__(self, rpc_client: Any, block_number: int, *,
                 account_cache_size: int = 5000,
                 storage_cache_size: int = 20000,
                 code_cache_size: int = 1000):
        self.rpc = rpc_client
        self.block_number = int(block_number)

        # caches
        self.account_cache = LRUCache(maxsize=account_cache_size)
        self.storage_cache = LRUCache(maxsize=storage_cache_size)
        self.code_cache = LRUCache(maxsize=code_cache_size)

        # simple stats
        self._stats = {
            "account_hits": 0,
            "account_misses": 0,
            "storage_hits": 0,
            "storage_misses": 0,
            "code_hits": 0,
            "code_misses": 0,
        }

    # -- Account -----------------------------------------------------------------
    def get_account(self, address: str) -> Dict[str, Any]:
        """Return a small account dict: {balance: int, code: bytes}.

        Caches the account result. Address should be in checksum or hex form
        accepted by the underlying RPC client.
        """
        key = str(address).lower()

        cached = self.account_cache.get(key)
        if cached is not None:
            self._stats["account_hits"] += 1
            return cached

        self._stats["account_misses"] += 1

        # load fields from RPC
        try:
            balance = self.rpc.get_balance(address, self.block_number)
        except Exception:
            balance = 0

        try:
            code = self.rpc.get_code(address)
        except Exception:
            code = b""

        account = {"balance": balance, "code": code}
        self.account_cache.set(key, account)
        return account

    # -- Code --------------------------------------------------------------------
    def get_code(self, address: str) -> bytes:
        key = str(address).lower()
        cached = self.code_cache.get(key)
        if cached is not None:
            self._stats["code_hits"] += 1
            return cached

        self._stats["code_misses"] += 1
        try:
            code = self.rpc.get_code(address)
        except Exception:
            code = b""
        self.code_cache.set(key, code)
        return code

    # -- Storage -----------------------------------------------------------------
    def get_storage(self, address: str, slot: int) -> bytes:
        """Get a storage slot value at the configured block number.

        The cache key is (address, slot) stringified to avoid nested maps.
        """
        key = f"{str(address).lower()}:{int(slot)}"
        cached = self.storage_cache.get(key)
        if cached is not None:
            self._stats["storage_hits"] += 1
            return cached

        self._stats["storage_misses"] += 1
        try:
            value = self.rpc.get_storage_at(address, int(slot), self.block_number)
        except Exception:
            value = b"\x00"
        self.storage_cache.set(key, value)
        return value

    # -- Preloading --------------------------------------------------------------
    def preload_addresses(self, addresses: Iterable[str]):
        """Preload code and balance for a set of addresses.

        This uses the individual RPC client methods but skips already-cached
        entries. Implementations that support batch RPC calls can be plugged
        in later.
        """
        for addr in addresses:
            akey = str(addr).lower()
            if self.account_cache.get(akey) is None:
                # call get_account to populate both balance and code cache
                self.get_account(addr)
            if self.code_cache.get(akey) is None:
                self.get_code(addr)

    # -- Utilities ---------------------------------------------------------------
    def stats(self) -> Dict[str, int]:
        """Return simple cache stats (hits/misses)."""
        return dict(self._stats)

    def clear_caches(self):
        self.account_cache.clear()
        self.storage_cache.clear()
        self.code_cache.clear()
        for k in list(self._stats.keys()):
            self._stats[k] = 0
