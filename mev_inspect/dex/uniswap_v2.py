"""UniswapV2 DEX parser."""

from typing import Dict, List, Optional

from eth_abi import decode, encode
from eth_utils import to_checksum_address
from web3 import Web3

from mev_inspect.dex.base import DEXParser
from mev_inspect.models import Swap


class UniswapV2Parser(DEXParser):
    """Parser for UniswapV2 pools."""

    # Known UniswapV2 factory addresses
    UNISWAP_V2_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
    SUSHI_FACTORY = "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac"

    # Event signatures (keccak256 of event signature)
    SWAP_EVENT_SIG = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"  # Swap(address,uint256,uint256,uint256,uint256,address)
    SWAP_EVENT_SIG_CLEAN = "d78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"  # Without 0x prefix

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache hit/miss statistics."""
        return {
            "hits": getattr(self, '_cache_hits', 0),
            "misses": getattr(self, '_cache_misses', 0),
            "hit_rate": (getattr(self, '_cache_hits', 0) / max(getattr(self, '_cache_hits', 0) + getattr(self, '_cache_misses', 0), 1)) * 100
        }

    def is_pool(self, address: str) -> bool:
        """Check if address is a UniswapV2 pool."""
        code = self.rpc_client.get_code(address)
        # UniswapV2 pools have specific code patterns
        # Simplified check - in production, verify against factory
        return len(code) > 100  # Basic check

    def parse_swap(
        self, tx_hash: str, tx_input: str, receipt_logs: List[Dict], block_number: int
    ) -> Optional[Swap]:
        """Parse Swap event from UniswapV2."""
        for log in receipt_logs:
            if not log.get("topics") or len(log["topics"]) == 0:
                continue
                
            # Handle both HexBytes and string formats
            first_topic = log["topics"][0]
            if hasattr(first_topic, "hex"):
                topic_hex = first_topic.hex()
            else:
                topic_hex = first_topic if isinstance(first_topic, str) else first_topic.hex()
            
            # Normalize: remove 0x prefix and convert to lowercase
            if topic_hex.startswith("0x"):
                topic_hex_clean = topic_hex[2:].lower()
            else:
                topic_hex_clean = topic_hex.lower()
                
            if topic_hex_clean == self.SWAP_EVENT_SIG_CLEAN:
                try:
                    # Decode Swap event: Swap(address indexed sender, uint amount0In, uint amount1In, uint amount0Out, uint amount1Out, address indexed to)
                    pool_address = log.get("address")
                    if hasattr(pool_address, "hex"):
                        pool_address = to_checksum_address(pool_address.hex())
                    else:
                        pool_address = to_checksum_address(pool_address)
                    
                    data = log.get("data", "0x")
                    if hasattr(data, "hex"):
                        data_hex = data.hex()
                    else:
                        data_hex = data if isinstance(data, str) else data.hex()
                    
                    # Normalize: remove 0x prefix if present
                    if data_hex.startswith("0x"):
                        data_hex = data_hex[2:]
                    
                    if not data_hex or len(data_hex) < 2:
                        continue

                    # Decode event data
                    decoded = decode(
                        ["uint256", "uint256", "uint256", "uint256"],
                        bytes.fromhex(data_hex),
                    )
                    amount0_in, amount1_in, amount0_out, amount1_out = decoded

                    # Determine token_in and token_out
                    if amount0_in > 0 and amount1_out > 0:
                        # Swapping token0 for token1
                        token_in = self._get_token0(pool_address, block_number)
                        token_out = self._get_token1(pool_address, block_number)
                        amount_in = amount0_in
                        amount_out = amount1_out
                    elif amount1_in > 0 and amount0_out > 0:
                        # Swapping token1 for token0
                        token_in = self._get_token1(pool_address, block_number)
                        token_out = self._get_token0(pool_address, block_number)
                        amount_in = amount1_in
                        amount_out = amount0_out
                    else:
                        continue

                    # Only create swap if we got valid token addresses
                    if token_in and token_out:
                        return Swap(
                            tx_hash=tx_hash,
                            block_number=block_number,
                            dex="uniswap_v2",
                            pool_address=pool_address,
                            token_in=token_in,
                            token_out=token_out,
                            amount_in=amount_in,
                            amount_out=amount_out,
                        )
                except Exception:
                    continue

        return None

    def get_reserves(self, pool_address: str, block_number: int) -> Dict[str, int]:
        """Get reserves from UniswapV2 pool."""
        # getReserves() returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)
        try:
            result = self.rpc_client.call(
                pool_address,
                "0x0902f1ac",  # getReserves()
                block_number,
            )
            # result is bytes
            if result and len(result) >= 64:
                reserve0 = int.from_bytes(result[:32], "big")
                reserve1 = int.from_bytes(result[32:64], "big")
                return {"reserve0": reserve0, "reserve1": reserve1}
        except Exception:
            pass
        return {}

    def calculate_output(
        self,
        pool_address: str,
        token_in: str,
        token_out: str,
        amount_in: int,
        block_number: int,
    ) -> int:
        """Calculate output using constant product formula: x * y = k."""
        reserves = self.get_reserves(pool_address, block_number)
        if not reserves:
            return 0

        token0 = self._get_token0(pool_address, block_number)
        token1 = self._get_token1(pool_address, block_number)

        if token_in == token0 and token_out == token1:
            reserve_in = reserves["reserve0"]
            reserve_out = reserves["reserve1"]
        elif token_in == token1 and token_out == token0:
            reserve_in = reserves["reserve1"]
            reserve_out = reserves["reserve0"]
        else:
            return 0

        # Constant product formula with 0.3% fee
        amount_in_with_fee = amount_in * 997
        numerator = amount_in_with_fee * reserve_out
        denominator = (reserve_in * 1000) + amount_in_with_fee
        amount_out = numerator // denominator

        return amount_out

    def _get_token0(self, pool_address: str, block_number: int) -> str:
        """Get token0 address from pool (with caching)."""
        pool_key = pool_address.lower()
        
        # Track cache statistics
        if not hasattr(self, '_cache_hits'):
            self._cache_hits = 0
            self._cache_misses = 0
        
        # PRIORITY 1: Check StateManager pool_tokens_cache (pre-loaded from database)
        if hasattr(self, 'state_manager') and self.state_manager:
            if hasattr(self.state_manager, 'pool_tokens_cache'):
                pool_data = self.state_manager.pool_tokens_cache.get(pool_key)
                if pool_data and 'token0' in pool_data:
                    self._cache_hits += 1
                    return pool_data['token0']
        
        # PRIORITY 2: Check local cache
        cache_key = f"{pool_key}_token0"
        if hasattr(self, '_token_cache') and cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
        # PRIORITY 3: RPC call (fallback)
        self._cache_misses += 1
        try:
            result = self.rpc_client.call(
                pool_address,
                "0x0dfe1681",  # token0()
                block_number,
            )
            if result and len(result) >= 32:
                # Extract last 20 bytes (40 hex chars) for address
                address_bytes = result[-20:] if len(result) >= 20 else result
                token = to_checksum_address("0x" + address_bytes.hex())
                
                # Cache result
                if not hasattr(self, '_token_cache'):
                    self._token_cache = {}
                self._token_cache[cache_key] = token
                return token
        except Exception as e:
            # Silently fail - token address might not be retrievable
            pass
        return ""

    def _get_token1(self, pool_address: str, block_number: int) -> str:
        """Get token1 address from pool (with caching)."""
        pool_key = pool_address.lower()
        
        # PRIORITY 1: Check StateManager pool_tokens_cache (pre-loaded from database)
        if hasattr(self, 'state_manager') and self.state_manager:
            if hasattr(self.state_manager, 'pool_tokens_cache'):
                pool_data = self.state_manager.pool_tokens_cache.get(pool_key)
                if pool_data and 'token1' in pool_data:
                    return pool_data['token1']
        
        # PRIORITY 2: Check local cache
        cache_key = f"{pool_key}_token1"
        if hasattr(self, '_token_cache') and cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
        # PRIORITY 3: RPC call (fallback)
        try:
            result = self.rpc_client.call(
                pool_address,
                "0xd21220a7",  # token1()
                block_number,
            )
            if result and len(result) >= 32:
                # Extract last 20 bytes (40 hex chars) for address
                address_bytes = result[-20:] if len(result) >= 20 else result
                token = to_checksum_address("0x" + address_bytes.hex())
                
                # Cache result
                if not hasattr(self, '_token_cache'):
                    self._token_cache = {}
                self._token_cache[cache_key] = token
                return token
        except Exception as e:
            # Silently fail - token address might not be retrievable
            pass
        return ""

