"""RPC client for Ethereum nodes (Alchemy Free Tier compatible - no trace support)."""

from typing import Any, Dict, List, Optional

from web3 import Web3
from web3.types import BlockData, TxData, TxReceipt


class RPCClient:
    """RPC client that works with Alchemy Free Tier (no trace support)."""

    def __init__(self, rpc_url: str):
        """Initialize RPC client."""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {rpc_url}")

    def get_block(self, block_number: int, full_transactions: bool = True) -> BlockData:
        """Get block data."""
        return self.w3.eth.get_block(block_number, full_transactions=full_transactions)

    def get_transaction(self, tx_hash: str) -> TxData:
        """Get transaction data."""
        return self.w3.eth.get_transaction(tx_hash)

    def get_transaction_receipt(self, tx_hash: str) -> TxReceipt:
        """Get transaction receipt."""
        return self.w3.eth.get_transaction_receipt(tx_hash)

    def get_code(self, address: str, block_number: Optional[int] = None) -> str:
        """Get contract code at address."""
        if block_number is not None:
            return self.w3.eth.get_code(Web3.to_checksum_address(address), block_number)
        return self.w3.eth.get_code(Web3.to_checksum_address(address))

    def get_balance(self, address: str, block_number: int) -> int:
        """Get balance at block."""
        return self.w3.eth.get_balance(Web3.to_checksum_address(address), block_number)

    def call(
        self,
        to: str,
        data: str,
        block_number: int,
        from_address: Optional[str] = None,
        value: int = 0,
    ) -> bytes:
        """Call contract at block number."""
        call_params = {
            "to": Web3.to_checksum_address(to),
            "data": data,
        }
        if from_address:
            call_params["from"] = Web3.to_checksum_address(from_address)
        if value > 0:
            call_params["value"] = value

        return self.w3.eth.call(call_params, block_number)

    def get_storage_at(self, address: str, position: int, block_number: int) -> bytes:
        """Get storage slot value."""
        return self.w3.eth.get_storage_at(
            Web3.to_checksum_address(address), position, block_number
        )

    def get_latest_block_number(self) -> int:
        """Get latest block number."""
        return self.w3.eth.block_number
    
    def batch_get_receipts(self, tx_hashes: List[str]) -> Dict[str, TxReceipt]:
        """Batch fetch transaction receipts using JSON-RPC batch request.
        
        Args:
            tx_hashes: List of transaction hashes
            
        Returns:
            Dictionary mapping tx_hash -> receipt
        """
        if not tx_hashes:
            return {}
        
        # Build batch request
        batch_request = [
            {
                "jsonrpc": "2.0",
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
                "id": i
            }
            for i, tx_hash in enumerate(tx_hashes)
        ]
        
        try:
            # Get RPC endpoint URL from provider
            import requests
            from web3.providers import HTTPProvider
            
            if isinstance(self.w3.provider, HTTPProvider):
                rpc_url = self.w3.provider.endpoint_uri
                
                # Make direct HTTP POST request for batch
                response = requests.post(
                    rpc_url,
                    json=batch_request,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                response.raise_for_status()
                results = response.json()
                
                # Parse results
                receipts = {}
                if isinstance(results, list):
                    for item in results:
                        if "result" in item and item["result"]:
                            tx_hash = batch_request[item["id"]]["params"][0]
                            receipts[tx_hash] = item["result"]
                
                return receipts
            else:
                # Not HTTP provider, fallback
                raise Exception("Non-HTTP provider detected")
            
        except Exception as e:
            print(f"Batch receipt fetch failed: {e}, falling back to sequential")
            # Fallback to sequential requests
            receipts = {}
            for tx_hash in tx_hashes:
                try:
                    receipts[tx_hash] = self.get_transaction_receipt(tx_hash)
                except Exception:
                    continue
            return receipts
    
    def batch_get_code(self, addresses: List[str], block_number: Optional[int] = None) -> Dict[str, bytes]:
        """Batch fetch contract code for multiple addresses.
        
        Args:
            addresses: List of addresses
            block_number: Optional block number for historical code
            
        Returns:
            Dictionary mapping address -> code
        """
        if not addresses:
            return {}
        
        # Build batch request
        block_param = hex(block_number) if block_number else "latest"
        batch_request = [
            {
                "jsonrpc": "2.0",
                "method": "eth_getCode",
                "params": [Web3.to_checksum_address(addr), block_param],
                "id": i
            }
            for i, addr in enumerate(addresses)
        ]
        
        try:
            import requests
            from web3.providers import HTTPProvider
            
            if isinstance(self.w3.provider, HTTPProvider):
                rpc_url = self.w3.provider.endpoint_uri
                
                # Make direct HTTP POST request for batch
                response = requests.post(
                    rpc_url,
                    json=batch_request,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                response.raise_for_status()
                results = response.json()
                
                # Parse results
                codes = {}
                if isinstance(results, list):
                    for item in results:
                        if "result" in item:
                            addr = addresses[item["id"]]
                            result = item["result"]
                            codes[addr.lower()] = bytes.fromhex(result[2:]) if result != "0x" else b""
                
                return codes
            else:
                raise Exception("Non-HTTP provider detected")
            
        except Exception as e:
            print(f"Batch code fetch failed: {e}, falling back to sequential")
            # Fallback to sequential
            codes = {}
            for addr in addresses:
                try:
                    code = self.get_code(addr, block_number)
                    codes[addr.lower()] = code if isinstance(code, bytes) else bytes.fromhex(code[2:]) if code != "0x" else b""
                except Exception as get_err:
                    print(f"[RPC DEBUG] Failed to get code for {addr}: {get_err}")
                    codes[addr.lower()] = b""
            print(f"[RPC DEBUG] Sequential fetch got {len(codes)} codes")
            return codes
    
    def batch_get_pool_tokens(
        self, 
        pool_addresses: List[str], 
        block_number: int
    ) -> Dict[str, Dict[str, str]]:
        """Batch fetch token0 and token1 for multiple Uniswap-like pools.
        
        Args:
            pool_addresses: List of pool contract addresses
            block_number: Block number for historical state
            
        Returns:
            Dictionary mapping pool address -> {"token0": address, "token1": address}
        """
        if not pool_addresses:
            return {}
        
        # Build batch request for token0() and token1() calls
        # token0() selector: 0x0dfe1681
        # token1() selector: 0xd21220a7
        batch_request = []
        
        for i, pool in enumerate(pool_addresses):
            pool_checksummed = Web3.to_checksum_address(pool)
            
            # token0() call
            batch_request.append({
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {
                        "to": pool_checksummed,
                        "data": "0x0dfe1681"  # token0()
                    },
                    hex(block_number)
                ],
                "id": i * 2
            })
            
            # token1() call
            batch_request.append({
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {
                        "to": pool_checksummed,
                        "data": "0xd21220a7"  # token1()
                    },
                    hex(block_number)
                ],
                "id": i * 2 + 1
            })
        
        try:
            import requests
            from web3.providers import HTTPProvider
            
            if isinstance(self.w3.provider, HTTPProvider):
                rpc_url = self.w3.provider.endpoint_uri
                
                # Make single HTTP POST request for all calls
                response = requests.post(
                    rpc_url,
                    json=batch_request,
                    headers={"Content-Type": "application/json"},
                    timeout=60  # Longer timeout for large batch
                )
                response.raise_for_status()
                results = response.json()
                
                # Parse results
                tokens = {}
                if isinstance(results, list):
                    for i, pool in enumerate(pool_addresses):
                        try:
                            # Get token0 result (id = i*2)
                            token0_result = next(
                                (r for r in results if r.get("id") == i * 2), 
                                None
                            )
                            # Get token1 result (id = i*2+1)
                            token1_result = next(
                                (r for r in results if r.get("id") == i * 2 + 1), 
                                None
                            )
                            
                            if token0_result and token1_result:
                                token0_hex = token0_result.get("result", "0x")
                                token1_hex = token1_result.get("result", "0x")
                                
                                # Extract address from result (last 40 hex chars = 20 bytes)
                                if token0_hex != "0x" and len(token0_hex) >= 42:
                                    token0 = "0x" + token0_hex[-40:]
                                else:
                                    token0 = None
                                
                                if token1_hex != "0x" and len(token1_hex) >= 42:
                                    token1 = "0x" + token1_hex[-40:]
                                else:
                                    token1 = None
                                
                                if token0 and token1:
                                    tokens[pool.lower()] = {
                                        "token0": token0.lower(),
                                        "token1": token1.lower()
                                    }
                        except Exception as e:
                            # Skip pools that fail to parse
                            continue
                
                return tokens
            else:
                raise Exception("Non-HTTP provider detected")
                
        except Exception as e:
            print(f"Batch pool tokens fetch failed: {e}, falling back to sequential")
            # Fallback to sequential calls
            tokens = {}
            for pool in pool_addresses:
                try:
                    # Call token0()
                    token0 = self.call(
                        pool,
                        "0x0dfe1681",  # token0()
                        block_number
                    )
                    # Call token1()
                    token1 = self.call(
                        pool,
                        "0xd21220a7",  # token1()
                        block_number
                    )
                    
                    if token0 and token1:
                        # Extract address from bytes
                        token0_addr = "0x" + token0.hex()[-40:] if isinstance(token0, bytes) else "0x" + token0[-40:]
                        token1_addr = "0x" + token1.hex()[-40:] if isinstance(token1, bytes) else "0x" + token1[-40:]
                        
                        tokens[pool.lower()] = {
                            "token0": token0_addr.lower(),
                            "token1": token1_addr.lower()
                        }
                except Exception:
                    # Skip pools that fail
                    continue
            
            return tokens

