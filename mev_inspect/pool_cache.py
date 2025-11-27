"""Persistent cache for pool token mappings using SQLite.

Pool tokens are IMMUTABLE - once a pool is created, token0/token1 never change.
We can cache them forever and reuse across ALL blocks, eliminating RPC calls.
"""
import sqlite3
from typing import Optional, Tuple, Dict
from pathlib import Path


class PoolTokenCache:
    """SQLite-based persistent cache for pool token pairs."""
    
    def __init__(self, db_path: str = "pool_tokens_cache.db"):
        """Initialize cache database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_table()
        
        # In-memory cache for fast lookups
        self._memory_cache: Dict[str, Tuple[str, str]] = {}
        self._load_memory_cache()
    
    def _create_table(self):
        """Create table if not exists."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pool_tokens (
                pool_address TEXT PRIMARY KEY,
                token0 TEXT NOT NULL,
                token1 TEXT NOT NULL,
                first_seen_block INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pool_address 
            ON pool_tokens(pool_address)
        """)
        self.conn.commit()
    
    def _load_memory_cache(self):
        """Load all entries into memory for fast access."""
        cursor = self.conn.execute(
            "SELECT pool_address, token0, token1 FROM pool_tokens"
        )
        for row in cursor:
            pool, token0, token1 = row
            self._memory_cache[pool.lower()] = (token0.lower(), token1.lower())
        
        print(f"[Pool Cache] Loaded {len(self._memory_cache)} pools from database")
    
    def get(self, pool_address: str) -> Optional[Tuple[str, str]]:
        """Get cached token pair for a pool.
        
        Args:
            pool_address: Pool contract address
            
        Returns:
            (token0, token1) or None if not cached
        """
        return self._memory_cache.get(pool_address.lower())
    
    def set(self, pool_address: str, token0: str, token1: str, block_number: int):
        """Save token pair to cache.
        
        Args:
            pool_address: Pool contract address
            token0: First token address
            token1: Second token address
            block_number: Block where pool was first seen
        """
        pool_key = pool_address.lower()
        
        # Check if already exists
        if pool_key in self._memory_cache:
            return
        
        # Save to database
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO pool_tokens 
                   (pool_address, token0, token1, first_seen_block) 
                   VALUES (?, ?, ?, ?)""",
                (pool_key, token0.lower(), token1.lower(), block_number)
            )
            self.conn.commit()
            
            # Update memory cache
            self._memory_cache[pool_key] = (token0.lower(), token1.lower())
        except sqlite3.IntegrityError:
            # Already exists, ignore
            pass
    
    def set_many(self, pool_tokens: Dict[str, Tuple[str, str]], block_number: int):
        """Batch save multiple pools.
        
        Args:
            pool_tokens: Dict mapping pool_address -> (token0, token1)
            block_number: Block where pools were first seen
        """
        records = [
            (pool.lower(), token0.lower(), token1.lower(), block_number)
            for pool, (token0, token1) in pool_tokens.items()
            if pool.lower() not in self._memory_cache
        ]
        
        if records:
            self.conn.executemany(
                """INSERT OR IGNORE INTO pool_tokens 
                   (pool_address, token0, token1, first_seen_block) 
                   VALUES (?, ?, ?, ?)""",
                records
            )
            self.conn.commit()
            
            # Update memory cache
            for pool, token0, token1, _ in records:
                self._memory_cache[pool] = (token0, token1)
            
            print(f"[Pool Cache] Saved {len(records)} new pools to database")
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dict with total_pools, disk_size_kb
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM pool_tokens")
        total = cursor.fetchone()[0]
        
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        return {
            "total_pools": total,
            "disk_size_kb": size_bytes // 1024,
            "memory_cached": len(self._memory_cache)
        }
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.conn.close()
        except:
            pass


# Global cache instance
_global_cache: Optional[PoolTokenCache] = None


def get_pool_cache() -> PoolTokenCache:
    """Get or create global pool token cache."""
    global _global_cache
    if _global_cache is None:
        _global_cache = PoolTokenCache()
    return _global_cache
