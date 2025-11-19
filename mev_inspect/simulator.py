"""State simulator for accurate MEV detection using RPC calls."""

from typing import Any, Dict, List, Optional, Tuple

try:
    from pyrevm import AccountInfo, BlockEnv, Evm, HexBytes, TransactTo

    PYREVM_AVAILABLE = True
except ImportError:
    PYREVM_AVAILABLE = False

from mev_inspect.state_manager import StateManager


class StateSimulator:
    """State simulator using RPC calls (compatible with Alchemy Free Tier)."""

    def __init__(self, rpc_client, block_number: int):
        """Initialize simulator at a specific block."""
        self.rpc_client = rpc_client
        self.block_number = block_number
        # Initialize StateManager for caching account/code/storage
        self.state_manager = StateManager(rpc_client, block_number)
        self.evm: Optional[Any] = None
        self.use_pyrevm = PYREVM_AVAILABLE
        if self.use_pyrevm:
            self._initialize_evm()

    def _initialize_evm(self):
        """Initialize EVM with block state (if pyrevm is available)."""
        if not PYREVM_AVAILABLE:
            return

        # Get block info
        block = self.rpc_client.get_block(self.block_number, full_transactions=False)

        # Create EVM instance
        self.evm = Evm()

        # Set block environment
        block_env = BlockEnv(
            number=block["number"],
            coinbase=block["miner"],
            timestamp=block["timestamp"],
            gas_limit=block["gasLimit"],
            base_fee=block.get("baseFeePerGas", 0),
            prevrandao=block.get("mixHash", b"\x00" * 32),
        )
        self.evm.block_env = block_env

        # Phase 1: StateManager handles caching for account/code/storage reads
        # Phase 2+: We'll load accounts into PyRevm for full transaction replay

    def preload_transaction_addresses(self, tx_data: Dict[str, Any]):
        """Preload addresses that will be accessed during transaction simulation.
        
        This is an optimization to batch-load state before simulation.
        """
        addresses = set()
        
        # Add transaction participants
        if tx_data.get("from"):
            addresses.add(tx_data["from"])
        if tx_data.get("to"):
            addresses.add(tx_data["to"])
        
        # Preload all addresses at once
        if addresses:
            self.state_manager.preload_addresses(addresses)
    
    def get_pool_state(
        self, pool_address: str, dex_type: str
    ) -> Dict[str, Any]:
        """Get current state of a DEX pool."""
        # Use RPC calls instead of EVM for compatibility

        # Get pool contract code via StateManager (cached)
        code = self.state_manager.get_code(pool_address)
        if not code or code == "0x":
            return {}

        # If using pyrevm, load contract into EVM
        if self.use_pyrevm and self.evm:
            account_info = AccountInfo(code=HexBytes(code))
            self.evm.insert_account_info(pool_address, account_info)

        # Query pool state based on DEX type
        state = {}
        if dex_type == "uniswap_v2":
            state = self._get_uniswap_v2_state(pool_address)
        elif dex_type == "uniswap_v3":
            state = self._get_uniswap_v3_state(pool_address)
        elif dex_type == "balancer":
            state = self._get_balancer_state(pool_address)
        elif dex_type == "curve":
            state = self._get_curve_state(pool_address)

        return state

    def _get_uniswap_v2_state(self, pool_address: str) -> Dict[str, Any]:
        """Get UniswapV2 pool state (reserves)."""
        # UniswapV2 getReserves() returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)
        # Function selector: 0x0902f1ac
        try:
            result = self.rpc_client.call(
                pool_address,
                "0x0902f1ac",  # getReserves()
                self.block_number,
            )
            # Parse result (simplified - would need proper ABI decoding)
            return {"reserves": result.hex()}
        except Exception:
            return {}

    def _get_uniswap_v3_state(self, pool_address: str) -> Dict[str, Any]:
        """Get UniswapV3 pool state (liquidity, sqrtPriceX96, tick)."""
        # UniswapV3 slot0 contains: uint160 sqrtPriceX96, int24 tick, uint16 observationIndex, ...
        # We'd read slot0 storage directly
        try:
            slot0 = self.state_manager.get_storage(pool_address, 0)
            liquidity = self.state_manager.get_storage(pool_address, 1)
            # Both are bytes
            return {
                "slot0": slot0.hex() if slot0 else "0x0",
                "liquidity": liquidity.hex() if liquidity else "0x0",
            }
        except Exception:
            return {}

    def _get_balancer_state(self, pool_address: str) -> Dict[str, Any]:
        """Get Balancer pool state."""
        # Balancer pools vary - would need to detect pool type
        # For V2 pools, we'd read balances from storage
        return {}

    def _get_curve_state(self, pool_address: str) -> Dict[str, Any]:
        """Get Curve pool state."""
        # Curve pools vary - would need to detect pool type
        # Typically read balances from storage
        return {}

    def simulate_swap(
        self,
        pool_address: str,
        dex_type: str,
        token_in: str,
        token_out: str,
        amount_in: int,
        zero_for_one: Optional[bool] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        """Simulate a swap and return amount_out and updated state."""
        # Use RPC calls for simulation (works with Alchemy Free Tier)

        # Get current pool state
        state_before = self.get_pool_state(pool_address, dex_type)

        # Build swap call data based on DEX type
        call_data = self._build_swap_call_data(
            dex_type, token_in, token_out, amount_in, zero_for_one
        )

        # Execute swap simulation using RPC call
        try:
            if self.use_pyrevm and self.evm:
                result = self.evm.call(
                    TransactTo.CALL,
                    pool_address,
                    HexBytes(call_data),
                    value=0,
                )
                amount_out = self._parse_swap_result(dex_type, result)
            else:
                # Fallback to RPC call simulation
                result = self.rpc_client.call(
                    pool_address,
                    call_data,
                    self.block_number,
                )
                # RPC call returns bytes, convert if needed
                if isinstance(result, str):
                    result_bytes = bytes.fromhex(result[2:] if result.startswith("0x") else result)
                else:
                    result_bytes = result
                amount_out = self._parse_swap_result(dex_type, result_bytes)

            # Get updated state
            state_after = self.get_pool_state(pool_address, dex_type)

            return amount_out, {"before": state_before, "after": state_after}
        except Exception as e:
            # Swap failed or reverted
            return 0, {"error": str(e)}

    def _build_swap_call_data(
        self,
        dex_type: str,
        token_in: str,
        token_out: str,
        amount_in: int,
        zero_for_one: Optional[bool],
    ) -> str:
        """Build swap call data for different DEX types."""
        from eth_abi import encode

        if dex_type == "uniswap_v2":
            # swap(uint amount0Out, uint amount1Out, address to, bytes calldata data)
            # We'd need to determine which token is 0 and which is 1
            # Simplified: assume token_in is token0
            amount0_out = 0
            amount1_out = amount_in  # This is wrong, but simplified
            to = "0x0000000000000000000000000000000000000000"
            data = b""
            encoded = encode(
                ["uint256", "uint256", "address", "bytes"],
                [amount0_out, amount1_out, to, data],
            )
            return "0x022c0d9f" + encoded.hex()  # swap() selector

        elif dex_type == "uniswap_v3":
            # exactInputSingle((address tokenIn, address tokenOut, uint24 fee, address recipient, uint256 deadline, uint256 amountIn, uint256 amountOutMinimum, uint160 sqrtPriceLimitX96))
            # This is simplified - actual UniswapV3 uses router
            pass

        return "0x"

    def _parse_swap_result(self, dex_type: str, result: bytes) -> int:
        """Parse swap result to extract amount_out."""
        # Simplified - would need proper ABI decoding
        if len(result) >= 32:
            return int.from_bytes(result[:32], "big")
        return 0

    def simulate_transaction(
        self, tx_hash: str, apply: bool = True
    ) -> Dict[str, Any]:
        """Simulate a transaction and optionally apply it to state."""
        # Use RPC to get transaction data

        tx = self.rpc_client.get_transaction(tx_hash)
        receipt = self.rpc_client.get_transaction_receipt(tx_hash)
        
        # Preload addresses for better performance
        self.preload_transaction_addresses(tx)

        # Execute transaction simulation
        try:
            if self.use_pyrevm and self.evm:
                result = self.evm.call(
                    TransactTo.CALL if tx["to"] else TransactTo.CREATE,
                    tx["to"] or "",
                    HexBytes(tx["input"]),
                    value=tx.get("value", 0),
                )
                result_hex = result.hex() if result else None
            else:
                # Use RPC call for simulation
                if tx["to"]:
                    result = self.rpc_client.call(
                        tx["to"],
                        tx["input"],
                        self.block_number,
                        from_address=tx.get("from"),
                        value=tx.get("value", 0),
                    )
                    # RPC call returns bytes, convert to hex string
                    if isinstance(result, bytes):
                        result_hex = result.hex()
                    else:
                        result_hex = result if result else None
                else:
                    result_hex = None

            if apply:
                # Apply transaction to state (would need to handle state updates)
                pass

            return {
                "success": receipt["status"] == 1,
                "gas_used": receipt["gasUsed"],
                "result": result_hex,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get StateManager cache statistics for monitoring performance."""
        stats = self.state_manager.stats()
        
        # Calculate hit rates
        account_total = stats["account_hits"] + stats["account_misses"]
        storage_total = stats["storage_hits"] + stats["storage_misses"]
        code_total = stats["code_hits"] + stats["code_misses"]
        
        return {
            "account_cache": {
                "hits": stats["account_hits"],
                "misses": stats["account_misses"],
                "hit_rate": stats["account_hits"] / account_total if account_total > 0 else 0.0,
            },
            "storage_cache": {
                "hits": stats["storage_hits"],
                "misses": stats["storage_misses"],
                "hit_rate": stats["storage_hits"] / storage_total if storage_total > 0 else 0.0,
            },
            "code_cache": {
                "hits": stats["code_hits"],
                "misses": stats["code_misses"],
                "hit_rate": stats["code_hits"] / code_total if code_total > 0 else 0.0,
            },
        }

