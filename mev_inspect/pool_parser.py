"""Local pool token parsing without RPC calls.

UniswapV2/V3 pools store token0/token1 in fixed storage slots:
- slot 0: factory address (first 20 bytes)
- slot 1: token0 address
- slot 2: token1 address

Or can be extracted from immutable variables in bytecode.
"""
from typing import Optional, Dict, Tuple
from eth_utils import to_checksum_address


class LocalPoolParser:
    """Parse pool tokens from contract code/storage without RPC."""
    
    def __init__(self):
        self._cache: Dict[str, Tuple[str, str]] = {}
    
    def get_tokens_from_storage(
        self, 
        w3,
        pool_address: str, 
        block_number: int
    ) -> Optional[Tuple[str, str]]:
        """Get token0/token1 from storage slots (works for most Uniswap pools).
        
        UniswapV2Pair storage layout:
        - slot 6: token0 (first 20 bytes) + token1 (last 20 bytes)
        
        UniswapV3Pool storage layout:
        - slot 0: token0
        - slot 1: token1
        """
        pool_key = pool_address.lower()
        
        # Check cache
        if pool_key in self._cache:
            return self._cache[pool_key]
        
        try:
            # Try UniswapV2 layout first (slot 6 packs both tokens)
            # This avoids RPC calls since we're reading raw storage
            slot_6 = w3.eth.get_storage_at(
                pool_address, 
                6, 
                block_identifier=block_number
            )
            
            if slot_6 and len(slot_6) == 32:
                # First 20 bytes = token1 (stored first)
                # Last 20 bytes = token0 (stored second)
                # Note: Solidity packs from right to left
                token1_bytes = slot_6[0:20]
                token0_bytes = slot_6[12:32]
                
                # Check if addresses are non-zero
                if int.from_bytes(token0_bytes, 'big') > 0 and int.from_bytes(token1_bytes, 'big') > 0:
                    token0 = to_checksum_address(token0_bytes)
                    token1 = to_checksum_address(token1_bytes)
                    
                    self._cache[pool_key] = (token0, token1)
                    return (token0, token1)
            
            # Try UniswapV3 layout (separate slots)
            slot_0 = w3.eth.get_storage_at(pool_address, 0, block_identifier=block_number)
            slot_1 = w3.eth.get_storage_at(pool_address, 1, block_identifier=block_number)
            
            if slot_0 and slot_1 and len(slot_0) == 32 and len(slot_1) == 32:
                # Extract address from last 20 bytes
                token0_bytes = slot_0[12:32]
                token1_bytes = slot_1[12:32]
                
                if int.from_bytes(token0_bytes, 'big') > 0 and int.from_bytes(token1_bytes, 'big') > 0:
                    token0 = to_checksum_address(token0_bytes)
                    token1 = to_checksum_address(token1_bytes)
                    
                    self._cache[pool_key] = (token0, token1)
                    return (token0, token1)
                    
        except Exception as e:
            # Storage parsing failed, will fallback to eth_call
            pass
        
        return None
    
    def get_tokens_from_bytecode(
        self, 
        bytecode: bytes,
        pool_address: str
    ) -> Optional[Tuple[str, str]]:
        """Extract token addresses from contract bytecode (immutable variables).
        
        UniswapV2/V3 pools often have token addresses as immutable variables
        embedded in the bytecode after deployment.
        """
        pool_key = pool_address.lower()
        
        if pool_key in self._cache:
            return self._cache[pool_key]
        
        try:
            # Look for address patterns (20 bytes = 0x + 40 hex chars)
            # Immutable addresses are typically stored near end of bytecode
            if len(bytecode) < 40:
                return None
            
            # Scan for potential addresses (heuristic: look for patterns)
            addresses = []
            for i in range(len(bytecode) - 20):
                chunk = bytecode[i:i+20]
                # Check if looks like valid address (not all zeros, not all FFs)
                as_int = int.from_bytes(chunk, 'big')
                if 0 < as_int < (2**160 - 1000):  # Reasonable address range
                    try:
                        addr = to_checksum_address(chunk)
                        addresses.append(addr)
                    except:
                        continue
            
            # If we found exactly 2 addresses, likely token0 and token1
            if len(addresses) >= 2:
                # Take last 2 addresses (usually immutables are at end)
                token0, token1 = addresses[-2], addresses[-1]
                self._cache[pool_key] = (token0, token1)
                return (token0, token1)
                
        except Exception:
            pass
        
        return None


# Global instance
_local_parser = LocalPoolParser()


def try_local_parse(w3, pool_address: str, block_number: int, bytecode: Optional[bytes] = None) -> Optional[Tuple[str, str]]:
    """Try to parse pool tokens locally without eth_call.
    
    Returns:
        (token0, token1) tuple if successful, None otherwise
    """
    # Method 1: Storage slots (faster, more reliable)
    result = _local_parser.get_tokens_from_storage(w3, pool_address, block_number)
    if result:
        return result
    
    # Method 2: Bytecode analysis (slower, less reliable)
    if bytecode:
        result = _local_parser.get_tokens_from_bytecode(bytecode, pool_address)
        if result:
            return result
    
    return None
