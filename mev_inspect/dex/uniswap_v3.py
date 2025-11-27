"""UniswapV3 DEX parser."""

from typing import Dict, List, Optional

from eth_abi import decode
from eth_utils import to_checksum_address
from web3 import Web3

from mev_inspect.dex.base import DEXParser
from mev_inspect.models import Swap


class UniswapV3Parser(DEXParser):
    """Parser for UniswapV3 pools."""

    # Event signatures (keccak256 of event signature)
    SWAP_EVENT_SIG = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"  # Swap(address,address,int256,int256,uint160,uint128,int24)
    SWAP_EVENT_SIG_CLEAN = "c42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"  # Without 0x prefix

    def is_pool(self, address: str) -> bool:
        """Check if address is a UniswapV3 pool."""
        code = self.rpc_client.get_code(address)
        # UniswapV3 pools have specific code patterns
        return len(code) > 100  # Basic check

    def parse_swap(
        self, tx_hash: str, tx_input: str, receipt_logs: List[Dict], block_number: int
    ) -> Optional[Swap]:
        """Parse Swap event from UniswapV3."""
        for log in receipt_logs:
            if not log.get("topics") or len(log["topics"]) < 3:
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
                    pool_address = log.get("address")
                    if hasattr(pool_address, "hex"):
                        pool_address = to_checksum_address(pool_address.hex())
                    else:
                        pool_address = to_checksum_address(pool_address)
                    
                    # Decode Swap event
                    # Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)
                    # Topics: [event_sig, sender, recipient]
                    # Data: amount0, amount1, sqrtPriceX96, liquidity, tick
                    
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
                        
                    # Decode the data
                    decoded = decode(
                        ["int256", "int256", "uint160", "uint128", "int24"],
                        bytes.fromhex(data_hex),
                    )
                    amount0, amount1, sqrt_price_x96, liquidity, tick = decoded
                    
                    # Get token addresses
                    token0 = self._get_token0(pool_address, block_number)
                    token1 = self._get_token1(pool_address, block_number)
                    
                    # Determine direction: positive = in, negative = out
                    if amount0 > 0 and amount1 < 0:
                        # Swapping token0 for token1
                        token_in = token0
                        token_out = token1
                        amount_in = abs(amount0)
                        amount_out = abs(amount1)
                    elif amount1 > 0 and amount0 < 0:
                        # Swapping token1 for token0
                        token_in = token1
                        token_out = token0
                        amount_in = abs(amount1)
                        amount_out = abs(amount0)
                    else:
                        continue
                    
                    # Only create swap if we got valid token addresses
                    if token_in and token_out and amount_in > 0 and amount_out > 0:
                        return Swap(
                            tx_hash=tx_hash,
                            block_number=block_number,
                            dex="uniswap_v3",
                            pool_address=pool_address,
                            token_in=token_in,
                            token_out=token_out,
                            amount_in=amount_in,
                            amount_out=amount_out,
                        )
                except Exception as e:
                    continue

        return None
    
    def _get_token0(self, pool_address: str, block_number: int) -> str:
        """Get token0 address from UniswapV3 pool (with caching)."""
        # Check cache first
        cache_key = f"{pool_address.lower()}_token0"
        if hasattr(self, '_token_cache') and cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
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
        except Exception:
            pass
        return ""
    
    def _get_token1(self, pool_address: str, block_number: int) -> str:
        """Get token1 address from UniswapV3 pool (with caching)."""
        # Check cache first
        cache_key = f"{pool_address.lower()}_token1"
        if hasattr(self, '_token_cache') and cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
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
        except Exception:
            pass
        return ""

    def get_reserves(self, pool_address: str, block_number: int) -> Dict[str, int]:
        """Get liquidity state from UniswapV3 pool."""
        # Read slot0 and liquidity from storage
        try:
            slot0 = self.rpc_client.get_storage_at(pool_address, 0, block_number)
            liquidity = self.rpc_client.get_storage_at(pool_address, 1, block_number)
            # slot0 contains: sqrtPriceX96 (uint160), tick (int24), ...
            # Would need to parse these properly
            # Both are bytes
            return {
                "slot0": int.from_bytes(slot0, "big") if slot0 else 0,
                "liquidity": int.from_bytes(liquidity, "big") if liquidity else 0,
            }
        except Exception:
            return {}

    def calculate_output(
        self,
        pool_address: str,
        token_in: str,
        token_out: str,
        amount_in: int,
        block_number: int,
    ) -> int:
        """Calculate output for UniswapV3 (complex - uses tick math)."""
        # UniswapV3 uses concentrated liquidity and tick-based pricing
        # This is simplified - full implementation would use tick math
        state = self.get_reserves(pool_address, block_number)
        if not state:
            return 0
        # Would implement proper UniswapV3 swap calculation
        return 0

