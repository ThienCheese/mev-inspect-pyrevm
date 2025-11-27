"""Sequential pool token fetching with rate limit handling."""
import time
from typing import Dict, List
from web3 import Web3


def sequential_get_pool_tokens(
    w3: Web3,
    pool_addresses: List[str], 
    block_number: int,
    delay_ms: int = 50
) -> Dict[str, Dict[str, str]]:
    """Fetch token0 and token1 for pools sequentially with delay.
    
    Args:
        w3: Web3 instance
        pool_addresses: List of pool contract addresses
        block_number: Block number for historical state
        delay_ms: Delay between calls in milliseconds (default 50ms)
        
    Returns:
        Dictionary mapping pool address -> {"token0": address, "token1": address}
    """
    if not pool_addresses:
        return {}
    
    print(f"[Sequential RPC] Fetching token pairs for {len(pool_addresses)} pools (delay={delay_ms}ms)...")
    
    pool_tokens = {}
    success_count = 0
    fail_count = 0
    delay_sec = delay_ms / 1000.0
    
    for i, pool_addr in enumerate(pool_addresses):
        try:
            pool_checksummed = Web3.to_checksum_address(pool_addr)
            
            # Get token0
            token0_result = w3.provider.make_request(
                "eth_call",
                [{
                    "to": pool_checksummed,
                    "data": "0x0dfe1681"  # token0()
                }, hex(block_number)]
            )
            
            # Small delay to avoid rate limit
            time.sleep(delay_sec)
            
            # Get token1
            token1_result = w3.provider.make_request(
                "eth_call",
                [{
                    "to": pool_checksummed,
                    "data": "0xd21220a7"  # token1()
                }, hex(block_number)]
            )
            
            # Delay between pools
            time.sleep(delay_sec)
            
            token0_hex = token0_result.get("result")
            token1_hex = token1_result.get("result")
            
            if token0_hex and token1_hex:
                # Extract last 40 hex chars (20 bytes) = address
                if len(token0_hex) >= 42 and len(token1_hex) >= 42:
                    token0_addr = "0x" + token0_hex[-40:]
                    token1_addr = "0x" + token1_hex[-40:]
                    
                    pool_tokens[pool_addr.lower()] = {
                        "token0": token0_addr.lower(),
                        "token1": token1_addr.lower()
                    }
                    success_count += 1
                else:
                    fail_count += 1
                    if fail_count <= 3:
                        print(f"[Sequential] Short result for {pool_addr[:12]}... (len={len(token0_hex)}, {len(token1_hex)})")
            else:
                fail_count += 1
                if fail_count <= 3:
                    print(f"[Sequential] Empty result for {pool_addr[:12]}...")
        except Exception as e:
            fail_count += 1
            if fail_count <= 3:
                print(f"[Sequential] Error for {pool_addr[:12]}...: {e}")
    
    print(f"[Sequential RPC] Fetched {success_count}/{len(pool_addresses)} pool token pairs ({fail_count} failures)")
    return pool_tokens
