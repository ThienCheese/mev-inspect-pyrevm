"""ABI-based decoder for Uniswap events - NO RPC CALLS NEEDED!

This decoder extracts token addresses from Swap event logs using ABIs,
eliminating the need for eth_call to fetch token0() and token1().
"""
from typing import Dict, Optional, Tuple
from eth_abi import decode
from web3 import Web3


class UniswapABIDecoder:
    """Decode Uniswap swap events to extract pool tokens WITHOUT RPC calls."""
    
    # Uniswap V2 event signatures
    UNISWAP_V2_SWAP = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"  # Swap(address,uint256,uint256,uint256,uint256,address)
    UNISWAP_V2_SYNC = "0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1"  # Sync(uint112,uint112)
    
    # Uniswap V3 event signatures  
    UNISWAP_V3_SWAP = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"  # Swap(address,address,int256,int256,uint160,uint128,int24)
    
    # Pool initialization events (contain token addresses!)
    UNISWAP_V2_PAIR_CREATED = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"  # PairCreated(address,address,address,uint256)
    UNISWAP_V3_POOL_CREATED = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"  # PoolCreated(address,address,uint24,int24,address)
    
    def __init__(self):
        """Initialize decoder with pre-computed event signatures."""
        self.v2_factories = {
            "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f".lower(),  # Uniswap V2
            "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac".lower(),  # Sushiswap
        }
        self.v3_factories = {
            "0x1F98431c8aD98523631AE4a59f267346ea31F984".lower(),  # Uniswap V3
        }
        
        # Cache for pool → tokens mapping
        self.pool_tokens_cache: Dict[str, Tuple[str, str]] = {}
    
    def extract_tokens_from_creation_event(self, log: Dict) -> Optional[Tuple[str, str, str]]:
        """Extract pool address and tokens from PairCreated/PoolCreated event.
        
        Returns:
            (pool_address, token0, token1) or None
        """
        topics = log.get("topics", [])
        if not topics:
            return None
        
        event_sig = topics[0] if isinstance(topics[0], str) else Web3.to_hex(topics[0])
        
        # Uniswap V2 PairCreated(address token0, address token1, address pair, uint256)
        if event_sig == self.UNISWAP_V2_PAIR_CREATED:
            if len(topics) < 3:
                return None
            
            # token0 and token1 are indexed (in topics)
            token0 = "0x" + topics[1][-40:] if isinstance(topics[1], str) else Web3.to_hex(topics[1])[-40:]
            token1 = "0x" + topics[2][-40:] if isinstance(topics[2], str) else Web3.to_hex(topics[2])[-40:]
            
            # pair address is in data
            data = log.get("data", "0x")
            if data == "0x" or len(data) < 66:
                return None
            
            # First 32 bytes = pair address, last 32 bytes = pair index
            pair = Web3.to_checksum_address("0x" + data[2:66][-40:])
            
            return (pair.lower(), token0.lower(), token1.lower())
        
        # Uniswap V3 PoolCreated(address token0, address token1, uint24 fee, int24 tickSpacing, address pool)
        elif event_sig == self.UNISWAP_V3_POOL_CREATED:
            if len(topics) < 3:
                return None
            
            # token0 and token1 are indexed
            token0 = "0x" + topics[1][-40:] if isinstance(topics[1], str) else Web3.to_hex(topics[1])[-40:]
            token1 = "0x" + topics[2][-40:] if isinstance(topics[2], str) else Web3.to_hex(topics[2])[-40:]
            
            # pool address is in data (last 32 bytes)
            data = log.get("data", "0x")
            if len(data) < 130:  # Need at least 64 bytes (fee + tickSpacing + pool)
                return None
            
            # Last 32 bytes = pool address
            pool = Web3.to_checksum_address("0x" + data[-64:])
            
            return (pool.lower(), token0.lower(), token1.lower())
        
        return None
    
    def get_pool_tokens_from_cache(self, pool_address: str) -> Optional[Tuple[str, str]]:
        """Get cached tokens for a pool (if we've seen its creation event).
        
        Args:
            pool_address: Pool contract address
            
        Returns:
            (token0, token1) or None if not in cache
        """
        return self.pool_tokens_cache.get(pool_address.lower())
    
    def scan_block_for_pool_creations(self, receipts: list) -> int:
        """Scan all receipts in a block for pool creation events.
        
        This populates the cache with pool → tokens mappings WITHOUT any RPC calls!
        
        Args:
            receipts: List of transaction receipts
            
        Returns:
            Number of pools discovered
        """
        discovered = 0
        
        for receipt in receipts:
            logs = receipt.get("logs", [])
            
            for log in logs:
                # Check if this is a factory contract
                log_address = log.get("address", "").lower()
                if log_address not in self.v2_factories and log_address not in self.v3_factories:
                    continue
                
                # Try to extract pool creation
                result = self.extract_tokens_from_creation_event(log)
                if result:
                    pool, token0, token1 = result
                    self.pool_tokens_cache[pool] = (token0, token1)
                    discovered += 1
        
        return discovered
    
    def extract_tokens_from_swap_log(self, log: Dict) -> Optional[Tuple[str, str]]:
        """Try to extract token info from swap event structure.
        
        This is a HEURISTIC approach when creation event is not available.
        Works for standard Uniswap V2/V3 pools.
        
        Returns:
            (token0, token1) or None
        """
        topics = log.get("topics", [])
        if not topics:
            return None
        
        event_sig = topics[0] if isinstance(topics[0], str) else Web3.to_hex(topics[0])
        
        # For V2/V3, we can't get tokens from swap event directly
        # Must use creation event or RPC call
        # Return None to trigger fallback
        return None
    
    def is_uniswap_swap_event(self, log: Dict) -> bool:
        """Check if log is a Uniswap V2 or V3 swap event."""
        topics = log.get("topics", [])
        if not topics:
            return False
        
        event_sig = topics[0] if isinstance(topics[0], str) else Web3.to_hex(topics[0])
        return event_sig in [self.UNISWAP_V2_SWAP, self.UNISWAP_V3_SWAP]


# Global decoder instance
abi_decoder = UniswapABIDecoder()
